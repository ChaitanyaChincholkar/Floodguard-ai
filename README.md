# FloodGuard AI --- Urban Flood Nowcasting System

> **Status:** Development prototype, not an operational
> emergency-warning system.

## 1. Project overview

FloodGuard AI is a web-based prototype that combines rainfall inputs and
terrain elevation to estimate possible urban inundation. The dashboard
lets a user run a flood simulation, view the estimated flood extent on
an interactive map, and inspect water-depth and risk summaries.

Current data paths: - **Terrain:** Copernicus DEM GLO-30, processed by
the backend. - **Rainfall:** Open-Meteo model-based forecast data can be
ingested and stored. Manual scenario rainfall and a synthetic
development provider are also supported.

Forecast data, synthetic data, and ground-measured observations must
never be treated as interchangeable.

## 2. How the system works

``` text
React + Vite dashboard
        |
        | HTTP
        v
FastAPI backend <------> PostgreSQL + PostGIS
        |
        v
Celery worker <-------> Redis
        |
        +---- Open-Meteo API (rainfall forecast)
        |
        +---- Copernicus DEM (terrain)
        |
        v
Baseline flood model
        |
        v
Flood polygons, water depth and risk metrics
        |
        v
Statistics API → dashboard + MapLibre/Deck.gl map
```

1.  The user starts a simulation from the dashboard or API.
2.  FastAPI creates/updates the model run and dispatches background work
    through Celery and Redis.
3.  The model task selects the configured rainfall input: manual
    scenario or, when requested through the API, latest ingested
    rainfall records.
4.  The backend obtains terrain data from the DEM provider and
    preprocesses it into a grid.
5.  The baseline model estimates water depth and risk categories.
6.  Results and data-source provenance are stored in PostgreSQL/PostGIS.
7.  The frontend retrieves run status and statistics and renders the map
    and metrics.

## 3. Technologies and skills used

  -----------------------------------------------------------------------
  Area                    Technologies            Purpose
  ----------------------- ----------------------- -----------------------
  Frontend                React, TypeScript/TSX,  Dashboard, controls,
                          Vite                    status panels

  Mapping                 MapLibre GL, Deck.gl    Interactive map and
                                                  flood/rainfall layers

  Backend                 Python, FastAPI,        REST APIs and
                          Pydantic                application logic

  Background processing   Celery, Redis           Asynchronous ingestion
                                                  and model tasks

  Database                PostgreSQL, PostGIS,    Model runs, weather
                          SQLAlchemy, asyncpg     records, spatial data

  Geospatial              Copernicus DEM GLO-30,  Elevation processing
                          Rasterio, GeoJSON       and flood geometry

  Weather                 Open-Meteo API          Model-based
                                                  weather/forecast input

  DevOps                  Docker, Docker Compose  Multi-service local
                                                  environment

  Testing                 pytest                  Automated
                                                  backend/provider tests

  Version control         Git                     Change tracking and
                                                  milestone management
  -----------------------------------------------------------------------

Skills demonstrated: - REST API development and frontend/backend
integration. - External API integration and response normalization. -
Asynchronous job processing with Celery and Redis. - Relational and
geospatial database workflows. - Raster/DEM processing and GeoJSON
handling. - Dockerized development and service debugging. - Automated
testing and data-provenance handling.

## 4. Important project components

  ----------------------------------------------------------------------------
  Path                                     Responsibility
  ---------------------------------------- -----------------------------------
  `frontend/`                              React/Vite dashboard

  `backend/app/main.py`                    FastAPI application setup

  `backend/app/api.py`                     Model-run and statistics API

  `backend/app/ingestion/providers.py`     Rainfall providers and
                                           normalization

  `backend/app/ingestion/tasks.py`         Celery ingestion and model tasks

  `backend/app/modeling/dem.py`            DEM provider

  `backend/app/modeling/terrain.py`        Terrain preprocessing

  `backend/app/modeling/flood_engine.py`   Baseline flood calculation

  `backend/tests/`                         Backend tests

  `docker-compose.yml`                     API, worker, DB, Redis and frontend
                                           services
  ----------------------------------------------------------------------------

These paths reflect the implementation details recorded during
development; verify the current working tree if files have since moved.

## 5. Run the project locally

### Requirements

-   Docker Desktop with Docker Compose
-   Git
-   Browser
-   Internet access for external weather/DEM retrieval

Open PowerShell in the project root (where `docker-compose.yml` exists).

Start/build services:

``` powershell
docker compose up -d --build
```

Check containers:

``` powershell
docker compose ps
```

Open: - Dashboard: http://localhost:5173 - API documentation:
http://localhost:8000/docs

View logs:

``` powershell
docker compose logs --tail 100 api
docker compose logs --tail 100 worker
```

Stop services without deleting persistent data:

``` powershell
docker compose stop
```

Start them again:

``` powershell
docker compose start
```

**Do not use `docker compose down -v` for routine stopping or
troubleshooting.** The `-v` option deletes volumes and can remove
persisted database data.

## 6. How to use the dashboard

1.  Start Docker Compose and open `http://localhost:5173`.
2.  Wait for the system and data-source panels to load.
3.  Review rainfall and DEM source/status labels.
4.  Use the rainfall slider to enter a manual scenario amount.
5.  Click **Run Flood Simulation**.
6.  Wait for the run to complete.
7.  Review inundated area, maximum/mean water depth, inundated grid
    cells and risk breakdown.
8.  Inspect flood extent and rainfall layers on the map.
9.  Check the completed run's rainfall and DEM provenance.

### Using ingested Open-Meteo rainfall

The backend supports an opt-in `use_latest_rainfall` option on the
model-run API. When enabled, the task uses the latest ingested rainfall
records according to the existing source-selection logic.

At the last verification point, the browser showed the Open-Meteo
forecast label for a completed run. A dedicated dashboard control for
choosing ingested rainfall was still listed as outstanding. Do not
assume the rainfall slider automatically uses Open-Meteo.

## 7. Data sources: what the labels mean

  -----------------------------------------------------------------------
  Source                              Meaning
  ----------------------------------- -----------------------------------
  Copernicus DEM GLO-30               Elevation/terrain input; not
                                      rainfall

  Open-Meteo                          Model-based weather/forecast data;
                                      not necessarily a local rain-gauge
                                      measurement

  Development rainfall provider       Synthetic development/test values

  Manual slider                       User-defined rainfall scenario
  -----------------------------------------------------------------------

Historical synthetic rows may remain in the database alongside
Open-Meteo rows. A model run's source label should reflect the input
actually used for that run.

## 8. Model behavior and limitations

The current engine is a **baseline heuristic model**, not a full
hydrodynamic flood solver. Its documented approach uses effective
rainfall and terrain-related factors to estimate water depth, then
classifies depth into risk levels.

Previously documented thresholds: - Low: 0.05--0.15 m - Moderate:
0.15--0.35 m - High: 0.35--0.60 m - Severe: at least 0.60 m

Known limitations: - It is not a full Saint-Venant/shallow-water
simulation. - Runoff and terrain assumptions need local calibration. -
Underground storm drains and detailed urban drainage are not
represented. - Grid resolution and study-area coverage limit local
accuracy. - Rainfall may be forecast, synthetic, or user-entered
scenario data. - A previously reported minimum rainfall floor of 25 mm
can affect model input when recent ingested rainfall averages to zero;
verify current code before changing it. - Automatic periodic ingestion
was not configured in the last verification report. - A dedicated
dashboard control for selecting ingested rainfall was not yet
implemented in that report. - Model run #24 was previously reported as
stuck in `QUEUED`; its current state needs checking.

**Do not use this prototype as the sole basis for evacuation, emergency
response, or public flood warnings.** Operational use requires
hydrological/hydraulic validation, local calibration, quality-controlled
observations, uncertainty analysis, monitoring and expert review.

## 9. Testing

The last reported full backend test result during Open-Meteo end-to-end
verification was:

``` text
37 passed
2 warnings (FastAPI deprecation warnings)
```

This is a historical result, not a guarantee that later working-tree
changes still pass.

Run the backend suite:

``` powershell
docker compose exec api pytest -q
```

Run a focused test module after checking its current filename:

``` powershell
docker compose exec api pytest -q tests/test_rainfall_providers.py
```

If tests fail with database connection/authentication errors, inspect
actual container and Compose settings before changing credentials or
deleting data.

## 10. Last verified status and remaining work

Previously reported as verified: - Open-Meteo request returned HTTP 200
for the Bengaluru request used in verification. - Seven hourly records
were stored as provider `OPEN_METEO`, status `FORECAST`. - A model run
using ingested rainfall reported Open-Meteo provenance separately from
Copernicus DEM provenance. - A manual slider run reported user-defined
scenario provenance. - Backend tests reported 37 passed and 2
warnings. - A later browser screenshot showed a completed simulation
with the Open-Meteo forecast source label.

Still to verify/finish: 1. Review the latest uncommitted changes in
`tasks.py`, `test_model_task_failure.py`, and `StatusPanel.tsx`; quota
interruption prevented a complete review. 2. Confirm whether the
`Development Provider / SIMULATED` row in the Data Sources table is a
valid historical record or a stale latest-status display. 3. Inspect
model run #24 without deleting or manually altering database records. 4.
Decide whether to add safe periodic ingestion after reviewing the
existing Celery configuration. 5. Add a dashboard control for ingested
rainfall only if still required. 6. Re-run focused tests and the full
backend suite after remaining changes. 7. Perform a final browser
verification.

## 11. Interview-ready explanation

"FloodGuard AI is a geospatial flood-nowcasting prototype. I built a
React dashboard connected to a FastAPI backend. The backend uses
PostgreSQL/PostGIS for model and spatial data, Celery and Redis for
background ingestion and simulation jobs, Copernicus DEM GLO-30 for
terrain, and Open-Meteo for model-based rainfall input. The baseline
model estimates water depth and risk zones, and the frontend visualizes
the results using MapLibre and Deck.gl. The project also involves
Docker-based setup, external API integration, data provenance and
automated testing. It is a development prototype and requires
hydrological validation before operational use."

In interviews, say **"Open-Meteo model-based forecast data"**, not
"ground-measured rainfall"; and say **"baseline flood-estimation
prototype"**, not "production-accurate flood prediction." Explain your
own contribution accurately and distinguish completed features from
pending work.
