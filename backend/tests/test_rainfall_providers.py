"""
Milestone 5B: Real Rainfall Data Integration -- Provider Tests
Tests for IMDRainfallProvider, DevelopmentRainfallProvider, fallback logic,
and ingestion task behavior.
"""
import pytest
import datetime

from app.ingestion.providers import (
    IMDRainfallProvider,
    IMDMissingCredentialsError,
    DevelopmentRainfallProvider,
    get_rainfall_provider,
)


# ---------------------------------------------------------------------------
# IMDRainfallProvider -- credential guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_imd_missing_credentials_raises_specific_error():
    """IMDRainfallProvider must raise IMDMissingCredentialsError when API key absent."""
    provider = IMDRainfallProvider(api_key=None)
    with pytest.raises(IMDMissingCredentialsError) as exc_info:
        await provider.fetch_latest()
    assert "dataservice.imd.gov.in" in str(exc_info.value)
    assert "IMD_API_KEY" in str(exc_info.value)


# ---------------------------------------------------------------------------
# IMDRainfallProvider -- normalize_response edge cases
# ---------------------------------------------------------------------------

def test_imd_normalization_full_observation():
    """Standard full observation dict normalizes correctly."""
    provider = IMDRainfallProvider(api_key="DUMMY")
    raw = {
        "observations": [
            {
                "station_id": "43295",
                "station_name": "Bengaluru AWS",
                "longitude": 77.5946,
                "latitude": 12.9716,
                "rainfall_mm": 18.3,
                "temperature": 24.5,
                "timestamp": "2026-10-07T06:00:00Z",
            }
        ]
    }
    result = provider.normalize_response(raw)
    assert len(result) == 1
    obs = result[0]
    assert obs["station_id"] == "43295"
    assert obs["lon"] == pytest.approx(77.5946)
    assert obs["lat"] == pytest.approx(12.9716)
    assert obs["rainfall_mm"] == pytest.approx(18.3)
    assert obs["temperature"] == pytest.approx(24.5)
    assert obs["data_status"] == "observed"
    assert obs["provider"] == "IMDRainfallProvider"
    assert obs["source"] == "India Meteorological Department (IMD)"
    assert isinstance(obs["timestamp"], datetime.datetime)


def test_imd_normalization_negative_rainfall_clamped():
    """Negative rainfall values must be clamped to 0.0."""
    provider = IMDRainfallProvider(api_key="DUMMY")
    raw = {"observations": [{"station_id": "X", "rainfall_mm": -5.0}]}
    result = provider.normalize_response(raw)
    assert result[0]["rainfall_mm"] == 0.0


def test_imd_normalization_alternate_field_names():
    """Provider should handle alternate field names: rain_24h, lat/lon aliases."""
    provider = IMDRainfallProvider(api_key="DUMMY")
    raw = {"observations": [{"station_id": "X", "rain_24h": 32.0, "lon": 77.61, "lat": 13.00}]}
    result = provider.normalize_response(raw)
    assert result[0]["rainfall_mm"] == pytest.approx(32.0)
    assert result[0]["lon"] == pytest.approx(77.61)


def test_imd_normalization_missing_timestamp_defaults_to_utcnow():
    """Missing timestamp should default to UTC now, not crash."""
    provider = IMDRainfallProvider(api_key="DUMMY")
    raw = {"observations": [{"station_id": "X", "rainfall_mm": 5.0}]}
    before = datetime.datetime.now(datetime.timezone.utc)
    result = provider.normalize_response(raw)
    after = datetime.datetime.now(datetime.timezone.utc)
    ts = result[0]["timestamp"]
    assert ts.tzinfo is not None
    assert before <= ts <= after


def test_imd_normalization_iso_timestamp_with_z_suffix():
    """Z-suffixed ISO timestamps must parse without error."""
    provider = IMDRainfallProvider(api_key="DUMMY")
    raw = {"observations": [{"station_id": "X", "rainfall_mm": 1.0, "timestamp": "2026-06-15T09:30:00Z"}]}
    result = provider.normalize_response(raw)
    ts = result[0]["timestamp"]
    assert ts.year == 2026 and ts.month == 6 and ts.day == 15


def test_imd_normalization_multiple_observations():
    """Multiple observations in one response should all be normalized."""
    provider = IMDRainfallProvider(api_key="DUMMY")
    raw = {"observations": [
        {"station_id": "A", "rainfall_mm": 10.0},
        {"station_id": "B", "rainfall_mm": 20.0},
        {"station_id": "C", "rainfall_mm": 0.0},
    ]}
    result = provider.normalize_response(raw)
    assert len(result) == 3
    assert result[1]["rainfall_mm"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# DevelopmentRainfallProvider
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dev_provider_schema():
    """DevelopmentRainfallProvider must return clearly labeled simulated records."""
    provider = DevelopmentRainfallProvider()
    data = await provider.fetch_latest()
    assert len(data) > 0
    for obs in data:
        assert obs["data_status"] == "simulated"
        assert obs["provider"] == "DevelopmentRainfallProvider"
        assert obs["rainfall_mm"] >= 0.0
        assert isinstance(obs["timestamp"], datetime.datetime)
        assert 77.40 <= obs["lon"] <= 77.80
        assert 12.80 <= obs["lat"] <= 13.10


@pytest.mark.asyncio
async def test_dev_provider_not_labeled_as_imd():
    """Simulated provider source field must NOT claim to be IMD."""
    provider = DevelopmentRainfallProvider()
    data = await provider.fetch_latest()
    for obs in data:
        assert "India Meteorological Department" not in obs["source"]
        assert "IMD" not in obs["source"]


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def test_factory_imd_aliases():
    """Factory must recognise imd, real, observed as IMD provider."""
    for alias in ["imd", "real", "observed"]:
        p = get_rainfall_provider(alias)
        assert isinstance(p, IMDRainfallProvider)


def test_factory_synthetic_aliases():
    """Factory must default to DevelopmentRainfallProvider for synthetic/unknown aliases."""
    for alias in ["synthetic", "development", "dev", "unknown", None]:
        p = get_rainfall_provider(alias)
        assert isinstance(p, DevelopmentRainfallProvider)


# ---------------------------------------------------------------------------
# Ingestion task fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_fallback_when_credentials_missing():
    """_ingest_rainfall_async with provider_type=imd but no IMD_API_KEY must
    silently fall back to DevelopmentRainfallProvider and succeed (not raise)."""
    from app.ingestion.tasks import _ingest_rainfall_async
    await _ingest_rainfall_async(provider_type="imd")
