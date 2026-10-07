from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from .database import get_db, engine
from . import models, api

app = FastAPI(
    title="FloodGuard AI API",
    description="Backend API for FloodGuard AI - Real-Time Urban Flood Nowcasting",
    version="0.1.0",
)

app.include_router(api.router)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import asyncio

@app.on_event("startup")
async def startup():
    max_retries = 5
    for i in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                
                # Safely update PostgreSQL ENUM types
                enum_migrations = [
                    "ALTER TYPE risklevel ADD VALUE IF NOT EXISTS 'very_high';",
                    "ALTER TYPE datastatus ADD VALUE IF NOT EXISTS 'modelled';"
                ]
                for enum_stmt in enum_migrations:
                    try:
                        await conn.execute(text(enum_stmt))
                    except Exception as e:
                        print(f"Enum update note: {e}")

                await conn.run_sync(models.Base.metadata.create_all)
                
                # Ensure new columns on existing tables are migrated safely without table drops
                migrations = [
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS model_name VARCHAR DEFAULT 'Baseline Urban Flood Model';",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS rainfall_input_id INTEGER;",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS dem_source VARCHAR DEFAULT 'Development Synthetic DEM';",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS data_status VARCHAR DEFAULT 'simulated';",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS parameters JSON;",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS metrics JSON;",
                    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS error_message TEXT;",
                    "ALTER TABLE flood_predictions ADD COLUMN IF NOT EXISTS risk_level VARCHAR DEFAULT 'low';",
                    "ALTER TABLE flood_predictions ADD COLUMN IF NOT EXISTS rainfall_mm FLOAT;",
                    "ALTER TABLE flood_predictions ADD COLUMN IF NOT EXISTS elevation_m FLOAT;",
                    "ALTER TABLE flood_predictions ADD COLUMN IF NOT EXISTS data_status VARCHAR DEFAULT 'simulated';",
                    "ALTER TABLE flood_predictions ADD COLUMN IF NOT EXISTS timestamp TIMESTAMP WITH TIME ZONE;"
                ]
                for stmt in migrations:
                    try:
                        await conn.execute(text(stmt))
                    except Exception as migration_err:
                        print(f"Migration note: {migration_err}")
                        
            print("Successfully connected to the database and initialized/migrated tables.")
            break
        except Exception as e:
            print(f"Database connection attempt {i+1} failed: {e}")
            if i < max_retries - 1:
                print("Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                raise e

@app.get("/")
async def root():
    return {"message": "Welcome to FloodGuard AI API"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "online",
        "database": db_status
    }
