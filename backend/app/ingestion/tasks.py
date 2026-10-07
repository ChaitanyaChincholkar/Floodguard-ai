import asyncio
import time
import json
import datetime
import logging
from sqlalchemy import select
from geoalchemy2.elements import WKTElement
from shapely.geometry import shape
from shapely.wkt import dumps as wkt_dumps

from ..database import AsyncSessionLocal
from ..models import DataSource, WeatherObservation, ModelRun, FloodPrediction, ProviderType, DataStatus, RiskLevel
from .providers import DevelopmentRainfallProvider, IMDRainfallProvider, get_rainfall_provider
from .celery_app import celery_app
from ..modeling.dem import get_dem_provider, SyntheticDEMProvider
from ..modeling.terrain import process_dem_terrain
from ..modeling.flood_engine import BaselineFloodModel

logger = logging.getLogger(__name__)

async def _ingest_rainfall_async(provider_type: Optional[str] = None):
    provider = get_rainfall_provider(provider_type)
    
    try:
        data = await provider.fetch_latest()
        is_real = isinstance(provider, IMDRainfallProvider)
        db_provider_type = ProviderType.IMD if is_real else ProviderType.DEVELOPMENT
        db_data_status = DataStatus.OBSERVED if is_real else DataStatus.SIMULATED
        provider_name = "India Meteorological Department (IMD)" if is_real else "Simulated Development Provider"
    except Exception as e:
        logger.warning(f"Rainfall provider failed: {e}. Falling back to DevelopmentRainfallProvider (labeled SIMULATED).")
        fallback = DevelopmentRainfallProvider()
        data = await fallback.fetch_latest()
        db_provider_type = ProviderType.DEVELOPMENT
        db_data_status = DataStatus.SIMULATED
        provider_name = "Simulated Development Provider (Fallback: IMD Unavailable)"

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(DataSource).where(DataSource.provider_type == db_provider_type))
        source = result.scalars().first()
        
        if not source:
            source = DataSource(
                name=provider_name,
                provider_type=db_provider_type,
                data_type="rainfall",
                health_status="healthy",
                last_synced=datetime.datetime.now(datetime.timezone.utc)
            )
            session.add(source)
            await session.commit()
            await session.refresh(source)
            
        for obs in data:
            point = WKTElement(f"POINT({obs['lon']} {obs['lat']})", srid=4326)
            new_obs = WeatherObservation(
                source_id=source.id,
                timestamp=obs['timestamp'],
                location=point,
                rainfall_mm=obs['rainfall_mm'],
                temperature=obs['temperature'],
                data_status=db_data_status
            )
            session.add(new_obs)
            
        source.last_synced = datetime.datetime.now(datetime.timezone.utc)
        source.health_status = "healthy"
        await session.commit()
        logger.info(f"Ingested {len(data)} rainfall observations ({db_data_status.value}).")

@celery_app.task(name="ingest_rainfall_data", bind=True, max_retries=3)
def ingest_rainfall_data(self):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(_ingest_rainfall_async())
    except Exception as e:
        logger.error(f"Error ingesting rainfall: {e}")
        self.retry(exc=e, countdown=10)

async def _run_flood_model_async(run_id: int):
    start_time = time.time()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ModelRun).where(ModelRun.id == run_id))
        model_run = result.scalars().first()
        if not model_run:
            logger.error(f"Model run ID {run_id} not found.")
            return
            
        try:
            model_run.status = "RUNNING"
            model_run.started_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
            
            rainfall_mm = 50.0
            provider_override = None
            if model_run.parameters:
                if "rainfall_mm" in model_run.parameters:
                    rainfall_mm = float(model_run.parameters["rainfall_mm"])
                if "dem_provider" in model_run.parameters:
                    provider_override = str(model_run.parameters["dem_provider"])
            else:
                stmt = select(WeatherObservation).order_by(WeatherObservation.timestamp.desc()).limit(10)
                obs_res = await session.execute(stmt)
                recent_obs = obs_res.scalars().all()
                if recent_obs:
                    avg_rain = sum(o.rainfall_mm for o in recent_obs if o.rainfall_mm) / len(recent_obs)
                    rainfall_mm = max(25.0, avg_rain * 5.0)
            
            # Use DEM Factory (supports real Copernicus DEM or synthetic fallback)
            dem_provider = get_dem_provider(provider_override)
            dem_data = dem_provider.get_dem_data()
            
            terrain_data = process_dem_terrain(dem_data)
            
            engine = BaselineFloodModel()
            sim_result = engine.run_simulation(dem_data, terrain_data, rainfall_mm)
            
            features = sim_result["features"]
            is_real_dem = dem_data.get("data_status") == "OBSERVED"
            db_data_status = DataStatus.OBSERVED if is_real_dem else DataStatus.SIMULATED
            
            for feat in features:
                poly_geom = shape(feat["geometry"])
                wkt_poly = WKTElement(wkt_dumps(poly_geom), srid=4326)
                props = feat["properties"]
                
                risk_str = str(props["risk_level"]).lower()
                if risk_str == "moderate":
                    risk_enum = RiskLevel.MODERATE
                elif risk_str == "high":
                    risk_enum = RiskLevel.HIGH
                elif risk_str in ["severe", "very_high"]:
                    risk_enum = RiskLevel.SEVERE
                else:
                    risk_enum = RiskLevel.LOW
                    
                prediction = FloodPrediction(
                    run_id=model_run.id,
                    geometry=wkt_poly,
                    predicted_depth_meters=props["predicted_depth_m"],
                    risk_level=risk_enum,
                    rainfall_mm=props["rainfall_mm"],
                    elevation_m=props["elevation_m"],
                    data_status=db_data_status,
                    is_simulated=not is_real_dem
                )
                session.add(prediction)
                
            execution_time = int((time.time() - start_time) * 1000)
            
            model_run.status = "COMPLETED"
            model_run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            model_run.execution_time_ms = execution_time
            model_run.metrics = sim_result["metrics"]
            model_run.dem_source = dem_data["source"]
            model_run.data_status = db_data_status
            
            await session.commit()
            logger.info(f"Successfully completed flood model run #{run_id} using {dem_data['source']} in {execution_time}ms.")
            
        except Exception as e:
            logger.error(f"Failed model run #{run_id}: {e}", exc_info=True)
            await session.rollback()
            res_fail = await session.execute(select(ModelRun).where(ModelRun.id == run_id))
            fail_run = res_fail.scalars().first()
            if fail_run:
                fail_run.status = "FAILED"
                fail_run.error_message = str(e)
                await session.commit()

@celery_app.task(name="run_flood_model_task", bind=True, max_retries=2)
def run_flood_model_task(self, run_id: int):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(_run_flood_model_async(run_id))
    except Exception as e:
        logger.error(f"Error running flood model task: {e}")
        self.retry(exc=e, countdown=5)
