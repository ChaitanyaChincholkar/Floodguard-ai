from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from .models import DataStatus, ProviderType, RiskLevel

class DataSourceResponse(BaseModel):
    id: int
    name: str
    provider_type: ProviderType
    data_type: Optional[str]
    health_status: str
    last_synced: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class DataStatusResponse(BaseModel):
    providers: List[DataSourceResponse]

class RainfallObservationResponse(BaseModel):
    id: int
    source_id: int
    timestamp: datetime
    rainfall_mm: float
    data_status: DataStatus
    longitude: float
    latitude: float

    model_config = ConfigDict(from_attributes=True)

class ElevationAreaResponse(BaseModel):
    message: str
    status: str
    source: str
    data_status: str
    resolution_m: int
    crs: str
    bounds: List[float]

class ModelRunCreate(BaseModel):
    rainfall_mm: Optional[float] = 50.0
    dem_source: Optional[str] = "Copernicus DEM GLO-30"
    dem_provider: Optional[str] = "real" # 'real', 'copernicus', or 'synthetic'

class ModelRunResponse(BaseModel):
    id: int
    model_name: str
    model_version: str
    timestamp: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    execution_time_ms: Optional[int] = None
    dem_source: str
    data_status: DataStatus
    parameters: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ModelStatisticsResponse(BaseModel):
    model_run_id: int
    model_name: str
    model_version: str
    status: str
    data_status: DataStatus
    metrics: Dict[str, Any]
    provenance: Dict[str, str]
