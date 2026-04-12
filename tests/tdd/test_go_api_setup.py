"""
TDD RED Tests for M1: Go API Setup + Python FastAPI Wrapper.

Tests the Python FastAPI wrapper endpoints that Go will proxy to.
All tests MUST FAIL until api/ module is implemented.

SPEC: docs/specs/modules/go_api_setup.md
"""
import pytest


# ============================================================================
# Test 1: FastAPI app exists and is importable
# ============================================================================

def test_fastapi_app_importable():
    """
    GIVEN: The api package exists
    WHEN: Importing the FastAPI app
    THEN: Import succeeds and app is a FastAPI instance
    """
    from api.main import app
    from fastapi import FastAPI
    assert isinstance(app, FastAPI)


# ============================================================================
# Test 2: Health endpoint returns OK
# ============================================================================

def test_health_endpoint():
    """
    GIVEN: The FastAPI app is running
    WHEN: GET /health
    THEN: Returns 200 with status=ok and version
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ============================================================================
# Test 3: Config endpoint returns settings without secrets
# ============================================================================

def test_config_endpoint_returns_settings():
    """
    GIVEN: The FastAPI app is running with valid .env
    WHEN: GET /config
    THEN: Returns 200 with non-sensitive settings fields
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/config")

    assert response.status_code == 200
    data = response.json()
    assert "latitude" in data
    assert "longitude" in data
    assert "provider" in data
    assert "forecast_hours" in data


def test_config_endpoint_excludes_secrets():
    """
    GIVEN: The FastAPI app is running
    WHEN: GET /config
    THEN: Response does NOT contain SMTP passwords or API keys
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/config")
    data = response.json()

    assert "smtp_pass" not in data
    assert "smtp_user" not in data
    assert "sms_api_key" not in data
    assert "signal_api_key" not in data
    assert "imap_pass" not in data


# ============================================================================
# Test 4: Forecast endpoint returns NormalizedTimeseries
# ============================================================================

def test_forecast_endpoint_returns_timeseries():
    """
    GIVEN: The FastAPI app is running
    WHEN: GET /forecast?lat=47.27&lon=11.40&hours=24
    THEN: Returns 200 with meta + data array
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/forecast", params={
        "lat": 47.27,
        "lon": 11.40,
        "hours": 24,
    })

    assert response.status_code == 200
    data = response.json()
    assert "meta" in data
    assert "data" in data
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 24


def test_forecast_meta_has_provider_info():
    """
    GIVEN: A successful forecast response
    WHEN: Checking the meta block
    THEN: Contains provider, model, run datetime
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/forecast", params={
        "lat": 47.27,
        "lon": 11.40,
        "hours": 24,
    })

    meta = response.json()["meta"]
    assert "provider" in meta
    assert "model" in meta
    assert "run" in meta
    assert meta["provider"] in ["OPENMETEO", "GEOSPHERE", "MOSMIX", "MET"]


def test_forecast_data_has_correct_fields():
    """
    GIVEN: A successful forecast response
    WHEN: Checking a data point
    THEN: Contains ts and t2m_c at minimum
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/forecast", params={
        "lat": 47.27,
        "lon": 11.40,
        "hours": 24,
    })

    point = response.json()["data"][0]
    assert "ts" in point
    assert "T" in point["ts"]
    # F001: Timestamps MUST have timezone info (ISO8601 with +00:00 or Z)
    assert "+" in point["ts"] or point["ts"].endswith("Z"), \
        f"Timestamp missing timezone: {point['ts']}"
    assert "t2m_c" in point


def test_forecast_enums_serialized_as_strings():
    """
    GIVEN: A forecast response with thunder_level present
    WHEN: Checking enum serialization
    THEN: Enums are strings (e.g. "NONE") not integers
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/forecast", params={
        "lat": 47.27,
        "lon": 11.40,
        "hours": 48,
    })

    for point in response.json()["data"]:
        if "thunder_level" in point:
            assert isinstance(point["thunder_level"], str)
            assert point["thunder_level"] in ["NONE", "MED", "HIGH"]
            break


# ============================================================================
# Test 5: Forecast error handling
# ============================================================================

def test_forecast_missing_params_returns_422():
    """
    GIVEN: The FastAPI app is running
    WHEN: GET /forecast without required lat/lon
    THEN: Returns 422 validation error
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/forecast")

    assert response.status_code == 422
