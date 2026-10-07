from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, JSON, Text
from geoalchemy2 import Geometry
from sqlalchemy.sql import func
import enum
from .database import Base

class ProviderType(enum.Enum):
    IMD = "imd"
    CWC = "cwc"
    COPERNICUS = "copernicus"
    OSM = "osm"
    DEVELOPMENT = "development"

class RiskLevel(enum.Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    SEVERE = "severe"

class DataStatus(enum.Enum):
    OBSERVED = "observed"
    FORECAST = "forecast"
    SIMULATED = "simulated"
    MODELLED = "modelled"

class DataSource(Base):
    __tablename__ = "data_sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    provider_type = Column(Enum(ProviderType))
    data_type = Column(String, nullable=True) # e.g., 'rainfall', 'dem'
    api_endpoint = Column(String, nullable=True)
    health_status = Column(String, default="unknown")
    last_synced = Column(DateTime(timezone=True), nullable=True)

class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    location = Column(Geometry('POINT', srid=4326))
    rainfall_mm = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    data_status = Column(Enum(DataStatus), default=DataStatus.SIMULATED)

class ModelRun(Base):
    __tablename__ = "model_runs"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String, default="Baseline Urban Flood Model")
    model_version = Column(String, default="0.1.0")
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default="QUEUED", index=True) # QUEUED, RUNNING, COMPLETED, FAILED
    execution_time_ms = Column(Integer, nullable=True)
    rainfall_input_id = Column(Integer, ForeignKey("weather_observations.id"), nullable=True)
    dem_source = Column(String, default="Synthetic DEM - DEVELOPMENT DATA")
    data_status = Column(Enum(DataStatus), default=DataStatus.SIMULATED)
    inputs = Column(JSON, nullable=True)
    parameters = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

class FloodPrediction(Base):
    __tablename__ = "flood_predictions"
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("model_runs.id"), index=True)
    geometry = Column(Geometry('POLYGON', srid=4326))
    predicted_depth_meters = Column(Float, nullable=False)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW)
    rainfall_mm = Column(Float, nullable=True)
    elevation_m = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True, default=0.85)
    is_simulated = Column(Boolean, default=True)
    data_status = Column(Enum(DataStatus), default=DataStatus.SIMULATED)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class RiskZone(Base):
    __tablename__ = "risk_zones"
    id = Column(Integer, primary_key=True, index=True)
    geometry = Column(Geometry('POLYGON', srid=4326))
    risk_level = Column(Enum(RiskLevel))
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
