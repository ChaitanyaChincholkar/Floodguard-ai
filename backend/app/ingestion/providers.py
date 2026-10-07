from abc import ABC, abstractmethod
import os
import random
import datetime
import logging
import httpx
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class RainfallProvider(ABC):
    @abstractmethod
    async def fetch_latest(self) -> List[Dict[str, Any]]:
        pass

class IMDMissingCredentialsError(Exception):
    """Raised when IMD API key or authorization credentials are not configured."""
    pass

class IMDRainfallProvider(RainfallProvider):
    """
    Official India Meteorological Department (IMD) Rainfall Data Provider.
    Accesses IMD real-time weather observation REST APIs.
    Requires official IMD API key registration at https://dataservice.imd.gov.in.
    PROVENANCE: REAL RAINFALL — INDIA METEOROLOGICAL DEPARTMENT (OBSERVED)
    """
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None, station_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("IMD_API_KEY")
        self.api_url = api_url or os.getenv("IMD_API_URL", "https://dataservice.imd.gov.in/api/v1/rainfall")
        self.station_id = station_id or os.getenv("IMD_STATION_ID", "43295") # Bengaluru AWS ID

    async def fetch_latest(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            logger.warning("IMD API key missing (IMD_API_KEY env var not set). Formal registration at https://dataservice.imd.gov.in required.")
            raise IMDMissingCredentialsError(
                "IMD API access requires an official API key (IMD_API_KEY). "
                "Register at https://dataservice.imd.gov.in to obtain access credentials."
            )
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        params = {"station": self.station_id}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self.api_url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        return self.normalize_response(data)

    def normalize_response(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        Normalizes raw IMD API JSON response into standard internal schema.
        Unit Normalization: Rainfall converted to millimeters (mm).
        """
        normalized = []
        observations = raw_data.get("observations", raw_data) if isinstance(raw_data, dict) else raw_data
        if not isinstance(observations, list):
            observations = [observations]
            
        for item in observations:
            if not isinstance(item, dict):
                continue
            lon = float(item.get("longitude", item.get("lon", 77.59)))
            lat = float(item.get("latitude", item.get("lat", 12.97)))
            rainfall_raw = float(item.get("rainfall_mm", item.get("rain_24h", item.get("rain", 0.0))))
            temp = float(item.get("temperature", item.get("temp", 25.0))) if item.get("temperature") is not None else None
            
            ts_str = item.get("timestamp", item.get("time"))
            if ts_str:
                try:
                    ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except ValueError:
                    ts = datetime.datetime.now(datetime.timezone.utc)
            else:
                ts = datetime.datetime.now(datetime.timezone.utc)

            normalized.append({
                "station_id": str(item.get("station_id", self.station_id)),
                "station_name": item.get("station_name", "IMD Bengaluru AWS"),
                "lon": lon,
                "lat": lat,
                "rainfall_mm": max(0.0, rainfall_raw),
                "temperature": temp,
                "timestamp": ts,
                "data_status": "observed",
                "provider": "IMDRainfallProvider",
                "source": "India Meteorological Department (IMD)"
            })
        return normalized

class DevelopmentRainfallProvider(RainfallProvider):
    """
    A clearly labeled simulated rainfall provider for development and testing.
    DO NOT use as live data.
    PROVENANCE: SIMULATED DATA — DEVELOPMENT RAINFALL PROVIDER
    """
    async def fetch_latest(self) -> List[Dict[str, Any]]:
        data = []
        for _ in range(5):
            lon = 77.59 + random.uniform(-0.1, 0.1)
            lat = 12.97 + random.uniform(-0.1, 0.1)
            rainfall = random.uniform(0.0, 15.0)
            
            data.append({
                "station_id": "DEV_SIM_01",
                "station_name": "Development Synthetic Station",
                "lon": lon,
                "lat": lat,
                "rainfall_mm": round(rainfall, 2),
                "temperature": round(25.0 + random.uniform(-2, 2), 1),
                "timestamp": datetime.datetime.now(datetime.timezone.utc),
                "data_status": "simulated",
                "provider": "DevelopmentRainfallProvider",
                "source": "Simulated Development Provider"
            })
        return data

def get_rainfall_provider(provider_type: Optional[str] = None) -> RainfallProvider:
    """
    Factory function for Rainfall provider selection.
    Respects RAINFALL_PROVIDER env var ('imd', 'synthetic').
    """
    selected = (provider_type or os.getenv("RAINFALL_PROVIDER", "synthetic")).lower()
    if selected in ["imd", "real", "observed"]:
        return IMDRainfallProvider()
    return DevelopmentRainfallProvider()

class DEMProvider(ABC):
    @abstractmethod
    async def get_area_status(self):
        pass

class CopernicusDEMProvider(DEMProvider):
    async def get_area_status(self):
        return {"status": "available", "source": "Copernicus via AWS S3 Open Data"}

