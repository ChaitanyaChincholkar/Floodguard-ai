from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func
from typing import List
import json
from geoalchemy2.functions import ST_X, ST_Y, ST_AsGeoJSON
from .database import get_db
from . import models, schemas
from .ingestion.tasks import run_flood_model_task, _run_flood_model_async
from .modeling.dem import get_dem_provider

router = APIRouter(prefix="/api/v1")

# Existing Rainfall & Elevation Endpoints
@router.get("/data/status", response_model=schemas.DataStatusResponse)
async def get_data_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.DataSource))
    providers = result.scalars().all()
    return {"providers": providers}

@router.get("/rainfall/latest", response_model=List[schemas.RainfallObservationResponse])
async def get_latest_rainfall(db: AsyncSession = Depends(get_db)):
    stmt = select(
        models.WeatherObservation,
        ST_X(models.WeatherObservation.location).label("lon"),
        ST_Y(models.WeatherObservation.location).label("lat")
    ).order_by(models.WeatherObservation.timestamp.desc()).limit(100)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    response = []
    for obs, lon, lat in rows:
        response.append(schemas.RainfallObservationResponse(
            id=obs.id,
            source_id=obs.source_id,
            timestamp=obs.timestamp,
            rainfall_mm=obs.rainfall_mm,
            data_status=obs.data_status,
            longitude=lon,
            latitude=lat
        ))
    return response

@router.get("/rainfall/history", response_model=List[schemas.RainfallObservationResponse])
async def get_rainfall_history(db: AsyncSession = Depends(get_db)):
    stmt = select(
        models.WeatherObservation,
        ST_X(models.WeatherObservation.location).label("lon"),
        ST_Y(models.WeatherObservation.location).label("lat")
    ).order_by(models.WeatherObservation.timestamp.desc()).limit(500)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    return [
        schemas.RainfallObservationResponse(
            id=obs.id,
            source_id=obs.source_id,
            timestamp=obs.timestamp,
            rainfall_mm=obs.rainfall_mm,
            data_status=obs.data_status,
            longitude=lon,
            latitude=lat
        ) for obs, lon, lat in rows
    ]

@router.get("/elevation/status")
async def get_elevation_status(db: AsyncSession = Depends(get_db)):
    provider = get_dem_provider()
    try:
        dem_data = provider.get_dem_data()
        return {
            "status": "AVAILABLE" if dem_data.get("is_cached") else "READY",
            "source": dem_data.get("source"),
            "provider": dem_data.get("provider"),
            "ready": True,
            "resolution_m": dem_data.get("resolution_m"),
            "crs": dem_data.get("crs"),
            "data_status": dem_data.get("data_status"),
            "is_cached": dem_data.get("is_cached", False)
        }
    except Exception as e:
        return {
            "status": f"Unhealthy: {str(e)}",
            "source": "Development Synthetic DEM (Fallback)",
            "ready": True,
            "data_status": "SIMULATED"
        }

@router.get("/elevation/area", response_model=schemas.ElevationAreaResponse)
async def get_elevation_area(db: AsyncSession = Depends(get_db)):
    provider = get_dem_provider()
    dem_data = provider.get_dem_data()
    return {
        "message": f"Elevation Area Available from {dem_data['source']}",
        "status": "ready",
        "source": dem_data["source"],
        "data_status": dem_data["data_status"],
        "resolution_m": dem_data["resolution_m"],
        "crs": dem_data["crs"],
        "bounds": list(dem_data["bounds"])
    }

@router.get("/geospatial/rainfall")
async def get_geospatial_rainfall(db: AsyncSession = Depends(get_db)):
    stmt = select(
        models.WeatherObservation,
        ST_X(models.WeatherObservation.location).label("lon"),
        ST_Y(models.WeatherObservation.location).label("lat")
    ).order_by(models.WeatherObservation.timestamp.desc()).limit(1000)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    features = []
    for obs, lon, lat in rows:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "id": obs.id,
                "rainfall_mm": obs.rainfall_mm,
                "temperature": obs.temperature,
                "timestamp": obs.timestamp.isoformat() if obs.timestamp else None,
                "data_status": obs.data_status.value if obs.data_status else "simulated"
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

# ==========================================
# MILESTONE 4/5A: FLOOD MODELING ENDPOINTS
# ==========================================

@router.post("/model/run", response_model=schemas.ModelRunResponse)
async def create_model_run(
    payload: schemas.ModelRunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Triggers a baseline urban flood modeling run using Real or Synthetic DEM.
    """
    dem_prov = payload.dem_provider or "real"
    target_dem_source = "Copernicus DEM GLO-30" if dem_prov.lower() in ["real", "copernicus"] else "Development Synthetic DEM"
    target_data_status = models.DataStatus.OBSERVED if dem_prov.lower() in ["real", "copernicus"] else models.DataStatus.SIMULATED
    
    new_run = models.ModelRun(
        model_name="Baseline Urban Flood Model",
        model_version="0.1.0",
        status="QUEUED",
        dem_source=payload.dem_source or target_dem_source,
        data_status=target_data_status,
        parameters={"rainfall_mm": payload.rainfall_mm or 50.0, "dem_provider": dem_prov}
    )
    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)
    
    try:
        run_flood_model_task.delay(new_run.id)
    except Exception:
        background_tasks.add_task(_run_flood_model_async, new_run.id)
        
    return new_run

@router.get("/model/runs", response_model=List[schemas.ModelRunResponse])
async def list_model_runs(db: AsyncSession = Depends(get_db)):
    stmt = select(models.ModelRun).order_by(models.ModelRun.timestamp.desc()).limit(20)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/model/runs/latest", response_model=schemas.ModelRunResponse)
async def get_latest_model_run(db: AsyncSession = Depends(get_db)):
    stmt = select(models.ModelRun).order_by(models.ModelRun.timestamp.desc()).limit(1)
    result = await db.execute(stmt)
    run = result.scalars().first()
    if not run:
        run = models.ModelRun(
            model_name="Baseline Urban Flood Model",
            model_version="0.1.0",
            status="QUEUED",
            dem_source="Copernicus DEM GLO-30",
            data_status=models.DataStatus.OBSERVED,
            parameters={"rainfall_mm": 50.0, "dem_provider": "real"}
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        await _run_flood_model_async(run.id)
        await db.refresh(run)
    return run

@router.get("/model/runs/{run_id}", response_model=schemas.ModelRunResponse)
async def get_model_run_status(run_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(models.ModelRun).where(models.ModelRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Model run #{run_id} not found")
    return run

@router.get("/model/runs/{run_id}/predictions")
@router.get("/model/runs/{run_id}/geojson")
async def get_model_run_geojson(run_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(
        models.FloodPrediction,
        ST_AsGeoJSON(models.FloodPrediction.geometry).label("geom_json")
    ).where(models.FloodPrediction.run_id == run_id)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    features = []
    for pred, geom_json in rows:
        geom_dict = json.loads(geom_json) if geom_json else None
        if not geom_dict:
            continue
            
        features.append({
            "type": "Feature",
            "geometry": geom_dict,
            "properties": {
                "id": pred.id,
                "run_id": pred.run_id,
                "predicted_depth_m": pred.predicted_depth_meters,
                "risk_level": pred.risk_level.value if hasattr(pred.risk_level, "value") else str(pred.risk_level),
                "rainfall_mm": pred.rainfall_mm,
                "elevation_m": pred.elevation_m,
                "data_status": pred.data_status.value if hasattr(pred.data_status, "value") else "simulated",
                "is_simulated": pred.is_simulated,
                "model_version": "0.1.0"
            }
        })
        
    return {
        "type": "FeatureCollection",
        "features": features
    }

@router.get("/model/runs/{run_id}/statistics", response_model=schemas.ModelStatisticsResponse)
async def get_model_run_statistics(run_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(models.ModelRun).where(models.ModelRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalars().first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Model run #{run_id} not found")
        
    metrics = run.metrics or {
        "rainfall_mm": 50.0,
        "affected_cells": 0,
        "affected_area_sqkm": 0.0,
        "max_depth_m": 0.0,
        "mean_depth_m": 0.0,
        "risk_counts": {"low": 0, "moderate": 0, "high": 0, "severe": 0}
    }
    
    is_real = "Copernicus" in (run.dem_source or "")
    
    provenance = {
        "rainfall_source": "DevelopmentRainfallProvider",
        "rainfall_status": "SIMULATED",
        "dem_source": run.dem_source or "Copernicus DEM GLO-30",
        "dem_status": "OBSERVED" if is_real else "SIMULATED",
        "model_name": run.model_name,
        "model_version": run.model_version,
        "disclaimer": "DEVELOPMENT MODEL — NOT FOR OPERATIONAL DECISION MAKING"
    }
    
    return schemas.ModelStatisticsResponse(
        model_run_id=run.id,
        model_name=run.model_name,
        model_version=run.model_version,
        status=run.status,
        data_status=run.data_status,
        metrics=metrics,
        provenance=provenance
    )
