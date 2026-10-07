from abc import ABC, abstractmethod
import os
import urllib.request
import logging
import numpy as np
from typing import Dict, Any, Tuple, Optional
import rasterio
from rasterio.windows import from_bounds
from rasterio.enums import Resampling

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "dem_cache")

def validate_dem_metadata(elevation: np.ndarray, crs_str: str, bounds: Tuple[float, float, float, float]) -> bool:
    """
    Validates DEM raster values, CRS, and extent bounds.
    Raises ValueError if validation checks fail.
    """
    if elevation is None or elevation.size == 0:
        raise ValueError("Invalid DEM: Elevation matrix is empty.")
    if not np.isfinite(elevation).all():
        raise ValueError("Invalid DEM: Elevation contains non-finite NaN/Inf values.")
    if not crs_str:
        raise ValueError("Invalid DEM: CRS metadata is missing.")
    min_lon, min_lat, max_lon, max_lat = bounds
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("Invalid DEM: Extent bounds are invalid.")
    return True

class DEMProvider(ABC):
    @abstractmethod
    def get_dem_data(self, bounds: Tuple[float, float, float, float] = (77.50, 12.88, 77.70, 13.08), grid_size: Tuple[int, int] = (25, 25)) -> Dict[str, Any]:
        """
        Returns DEM metadata and elevation matrix.
        bounds: (min_lon, min_lat, max_lon, max_lat)
        grid_size: (cols, rows)
        """
        pass

class SyntheticDEMProvider(DEMProvider):
    """
    Clearly labeled synthetic DEM provider for development and testing fallback.
    DO NOT present as Copernicus or real-world satellite DEM.
    PROVENANCE: DEVELOPMENT DATA — SYNTHETIC DEM
    """
    def get_dem_data(self, bounds: Tuple[float, float, float, float] = (77.50, 12.88, 77.70, 13.08), grid_size: Tuple[int, int] = (25, 25)) -> Dict[str, Any]:
        min_lon, min_lat, max_lon, max_lat = bounds
        cols, rows = grid_size
        
        lons = np.linspace(min_lon, max_lon, cols)
        lats = np.linspace(min_lat, max_lat, rows)
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        
        base_elevation = 930.0 - 50.0 * ((lon_grid - min_lon) / (max_lon - min_lon) + (lat_grid - min_lat) / (max_lat - min_lat)) / 2.0
        
        hill1 = 15.0 * np.exp(-((lon_grid - 77.58)**2 / 0.005 + (lat_grid - 12.98)**2 / 0.005))
        hill2 = 12.0 * np.exp(-((lon_grid - 77.65)**2 / 0.004 + (lat_grid - 13.04)**2 / 0.004))
        
        depression1 = -22.0 * np.exp(-((lon_grid - 77.63)**2 / 0.003 + (lat_grid - 12.93)**2 / 0.003))
        depression2 = -18.0 * np.exp(-((lon_grid - 77.56)**2 / 0.003 + (lat_grid - 13.01)**2 / 0.003))
        depression3 = -15.0 * np.exp(-((lon_grid - 77.68)**2 / 0.002 + (lat_grid - 12.97)**2 / 0.002))
        
        elevation = base_elevation + hill1 + hill2 + depression1 + depression2 + depression3
        validate_dem_metadata(elevation, "EPSG:4326", bounds)
        
        return {
            "source": "Development Synthetic DEM",
            "provider": "SyntheticDEMProvider",
            "data_status": "SIMULATED",
            "label": "DEVELOPMENT DATA — SYNTHETIC DEM",
            "crs": "EPSG:4326",
            "resolution_m": 100,
            "units": "meters",
            "bounds": bounds,
            "grid_size": grid_size,
            "lons": lons,
            "lats": lats,
            "elevation": elevation,
            "min_elevation_m": float(np.min(elevation)),
            "max_elevation_m": float(np.max(elevation)),
            "cell_size_lon": (max_lon - min_lon) / cols,
            "cell_size_lat": (max_lat - min_lat) / rows,
            "is_cached": False
        }

class CopernicusDEMProvider(DEMProvider):
    """
    Real DEM Provider accessing Copernicus DEM GLO-30 via AWS S3 Open Data.
    Downloads, validates, and caches GLO-30 rasters locally.
    PROVENANCE: REAL DEM — COPERNICUS DEM GLO-30 (OBSERVED)
    """
    S3_URL = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N12_00_E077_00_DEM/Copernicus_DSM_COG_10_N12_00_E077_00_DEM.tif"
    CACHE_FILE = "Copernicus_DSM_COG_10_N12_00_E077_00_DEM.tif"

    def __init__(self, fallback_on_failure: bool = True):
        self.fallback_on_failure = fallback_on_failure
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.local_cache_path = os.path.join(CACHE_DIR, self.CACHE_FILE)

    def _ensure_local_cache(self) -> str:
        if os.path.exists(self.local_cache_path) and os.path.getsize(self.local_cache_path) > 1000:
            return self.local_cache_path
        
        logger.info(f"Downloading Copernicus DEM GLO-30 tile to local cache: {self.local_cache_path}")
        try:
            urllib.request.urlretrieve(self.S3_URL, self.local_cache_path)
            return self.local_cache_path
        except Exception as e:
            logger.warning(f"Failed to download Copernicus DEM GLO-30 to local cache: {e}. Will attempt direct HTTP streaming.")
            return self.S3_URL

    def get_dem_data(self, bounds: Tuple[float, float, float, float] = (77.50, 12.88, 77.70, 13.08), grid_size: Tuple[int, int] = (25, 25)) -> Dict[str, Any]:
        try:
            source_path = self._ensure_local_cache()
            with rasterio.open(source_path) as ds:
                min_lon, min_lat, max_lon, max_lat = bounds
                cols, rows = grid_size
                
                # Window crop corresponding to Bengaluru study bounds
                window = from_bounds(min_lon, min_lat, max_lon, max_lat, ds.transform)
                
                # Resample raster window to requested grid_size for model compatibility
                elevation = ds.read(
                    1,
                    window=window,
                    out_shape=(rows, cols),
                    resampling=Resampling.bilinear
                ).astype(np.float64)
                
                # Replace nodata values if present
                if ds.nodata is not None:
                    elevation = np.where(elevation == ds.nodata, np.nanmean(elevation), elevation)
                elevation = np.nan_to_num(elevation, nan=885.0)
                
                crs_str = str(ds.crs) if ds.crs else "EPSG:4326"
                validate_dem_metadata(elevation, crs_str, bounds)
                
                lons = np.linspace(min_lon, max_lon, cols)
                lats = np.linspace(min_lat, max_lat, rows)
                
                return {
                    "source": "Copernicus DEM GLO-30",
                    "provider": "CopernicusDEMProvider (AWS S3 Public Open Data)",
                    "data_status": "OBSERVED",
                    "label": "REAL DEM — COPERNICUS DEM GLO-30",
                    "crs": crs_str,
                    "resolution_m": 30,
                    "units": "meters",
                    "bounds": bounds,
                    "grid_size": grid_size,
                    "lons": lons,
                    "lats": lats,
                    "elevation": elevation,
                    "min_elevation_m": round(float(np.min(elevation)), 2),
                    "max_elevation_m": round(float(np.max(elevation)), 2),
                    "cell_size_lon": (max_lon - min_lon) / cols,
                    "cell_size_lat": (max_lat - min_lat) / rows,
                    "is_cached": os.path.exists(self.local_cache_path),
                    "cache_path": self.local_cache_path
                }
        except Exception as e:
            logger.error(f"Copernicus DEM provider failed: {e}", exc_info=True)
            if self.fallback_on_failure:
                logger.info("Falling back to SyntheticDEMProvider (labeled SIMULATED).")
                fallback = SyntheticDEMProvider()
                data = fallback.get_dem_data(bounds, grid_size)
                data["source"] = "Synthetic DEM (Fallback: Copernicus Unavailable)"
                return data
            raise e

def get_dem_provider(provider_type: Optional[str] = None) -> DEMProvider:
    """
    Factory function for DEM provider selection.
    Respects DEM_PROVIDER env var ('real', 'copernicus', 'synthetic').
    """
    selected = (provider_type or os.getenv("DEM_PROVIDER", "real")).lower()
    if selected in ["synthetic", "development", "simulated"]:
        return SyntheticDEMProvider()
    return CopernicusDEMProvider()
