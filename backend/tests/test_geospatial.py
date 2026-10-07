import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_geospatial_rainfall_geojson_structure():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/geospatial/rainfall")
        
    assert response.status_code == 200
    data = response.json()
    
    # Verify standard GeoJSON FeatureCollection structure
    assert "type" in data
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)
    
    if len(data["features"]) > 0:
        feature = data["features"][0]
        assert feature["type"] == "Feature"
        
        # Verify geometry
        assert "geometry" in feature
        assert feature["geometry"]["type"] == "Point"
        assert "coordinates" in feature["geometry"]
        assert len(feature["geometry"]["coordinates"]) == 2
        
        # Verify properties
        assert "properties" in feature
        assert "rainfall_mm" in feature["properties"]
        assert "data_status" in feature["properties"]
        # Explicitly verify the data_status is set, ensuring "simulated" vs "observed" tracking works
        assert feature["properties"]["data_status"] in ["observed", "forecast", "simulated"]
