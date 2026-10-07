from abc import ABC, abstractmethod
import random
import datetime

class RainfallProvider(ABC):
    @abstractmethod
    async def fetch_latest(self):
        pass

class DevelopmentRainfallProvider(RainfallProvider):
    """
    A clearly labeled simulated rainfall provider for development and testing.
    DO NOT use as live data.
    """
    async def fetch_latest(self):
        # Generate some fake data for a bounding box (e.g., Bengaluru area)
        data = []
        for _ in range(5): # Generate 5 points per run
            lon = 77.59 + random.uniform(-0.1, 0.1)
            lat = 12.97 + random.uniform(-0.1, 0.1)
            rainfall = random.uniform(0.0, 15.0) # mm
            
            data.append({
                "lon": lon,
                "lat": lat,
                "rainfall_mm": rainfall,
                "temperature": 25.0 + random.uniform(-2, 2),
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "data_status": "simulated"
            })
        return data

class DEMProvider(ABC):
    @abstractmethod
    async def get_area_status(self):
        pass

class CopernicusDEMProvider(DEMProvider):
    async def get_area_status(self):
        return {"status": "available", "source": "Copernicus via AWS S3 Open Data"}
