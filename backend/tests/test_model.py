import pytest
from httpx import AsyncClient, ASGITransport
import numpy as np
from app.main import app
from app.modeling.dem import SyntheticDEMProvider, CopernicusDEMProvider, get_dem_provider
from app.modeling.terrain import process_dem_terrain, compute_slope
from app.modeling.flood_engine import BaselineFloodModel

def test_synthetic_dem_provider():
    provider = SyntheticDEMProvider()
    data = provider.get_dem_data()
    assert data["source"] == "Development Synthetic DEM"
    assert data["data_status"] == "SIMULATED"
    assert "elevation" in data
    assert data["elevation"].shape == (25, 25)
    assert np.min(data["elevation"]) > 800.0

def test_copernicus_dem_provider():
    provider = CopernicusDEMProvider()
    data = provider.get_dem_data()
    assert data["source"] == "Copernicus DEM GLO-30"
    assert data["data_status"] == "OBSERVED"
    assert data["resolution_m"] == 30
    assert "elevation" in data
    assert data["elevation"].shape == (25, 25)
    assert np.min(data["elevation"]) > 700.0

def test_dem_provider_factory_selection():
    real_prov = get_dem_provider("real")
    assert isinstance(real_prov, CopernicusDEMProvider)

    synth_prov = get_dem_provider("synthetic")
    assert isinstance(synth_prov, SyntheticDEMProvider)

def test_terrain_processing():
    provider = CopernicusDEMProvider()
    dem_data = provider.get_dem_data()
    terrain = process_dem_terrain(dem_data)
    
    assert "slope_deg" in terrain
    assert "depression_depth_m" in terrain
    assert "flow_accumulation" in terrain
    assert terrain["slope_deg"].shape == (25, 25)

def test_baseline_flood_model_simulation():
    provider = CopernicusDEMProvider()
    dem_data = provider.get_dem_data()
    terrain = process_dem_terrain(dem_data)
    
    engine = BaselineFloodModel()
    result = engine.run_simulation(dem_data, terrain, rainfall_mm=60.0)
    
    assert "features" in result
    assert "metrics" in result
    metrics = result["metrics"]
    assert metrics["rainfall_mm"] == 60.0
    assert metrics["affected_cells"] > 0
    assert metrics["max_depth_m"] > 0.05
    assert "risk_counts" in metrics

@pytest.mark.asyncio
async def test_elevation_api_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_status = await ac.get("/api/v1/elevation/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["source"] in ["Copernicus DEM GLO-30", "Development Synthetic DEM"]
        assert "data_status" in status_data
        
        res_area = await ac.get("/api/v1/elevation/area")
        assert res_area.status_code == 200
        area_data = res_area.json()
        assert "bounds" in area_data

@pytest.mark.asyncio
async def test_api_model_run_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Trigger model run
        response = await ac.post("/api/v1/model/run", json={"rainfall_mm": 55.0, "dem_provider": "real"})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        run_id = data["id"]
        assert data["status"] in ["QUEUED", "RUNNING", "COMPLETED"]
        
        # Check run status
        res_status = await ac.get(f"/api/v1/model/runs/{run_id}")
        assert res_status.status_code == 200
        
        # Check geojson prediction output
        res_geojson = await ac.get(f"/api/v1/model/runs/{run_id}/geojson")
        assert res_geojson.status_code == 200
        geojson = res_geojson.json()
        assert geojson["type"] == "FeatureCollection"
        
        # Check statistics endpoint
        res_stats = await ac.get(f"/api/v1/model/runs/{run_id}/statistics")
        assert res_stats.status_code == 200
        stats = res_stats.json()
        assert "metrics" in stats
        assert "provenance" in stats
        assert stats["provenance"]["disclaimer"] == "DEVELOPMENT MODEL — NOT FOR OPERATIONAL DECISION MAKING"

