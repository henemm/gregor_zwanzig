"""
TDD RED Tests for M5a: GPX Proxy (Python FastAPI + Go Proxy).

Tests the Python FastAPI endpoint POST /api/gpx/parse that wraps
gpx_to_stage_data() for the SvelteKit frontend via Go proxy.

SPEC: docs/specs/modules/gpx_proxy.md
"""
import pytest
from pathlib import Path

# Sample GPX file for testing (real Komoot GPX from data/)
_SAMPLE_GPX = Path("data/2026-01-17_2753214331_Tag 1_ von Valldemossa nach Deià.gpx")


# ============================================================================
# Test 1: GPX router is registered in FastAPI app
# ============================================================================

def test_gpx_router_registered():
    """
    GIVEN: The FastAPI app with all routers
    WHEN: Checking registered routes
    THEN: POST /api/gpx/parse exists
    """
    from api.main import app

    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/gpx/parse" in routes, (
        f"POST /api/gpx/parse not found in routes: {routes}"
    )


# ============================================================================
# Test 2: Successful GPX parse returns stage with waypoints
# ============================================================================

def test_gpx_parse_returns_stage_with_waypoints():
    """
    GIVEN: A valid GPX file (real Komoot export)
    WHEN: POST /api/gpx/parse with the file as multipart
    THEN: Returns 200 with name, date, and non-empty waypoints[]
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)

    assert _SAMPLE_GPX.exists(), f"Sample GPX not found: {_SAMPLE_GPX}"
    with open(_SAMPLE_GPX, "rb") as f:
        response = client.post(
            "/api/gpx/parse",
            files={"file": ("test.gpx", f, "application/gpx+xml")},
        )

    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "date" in data
    assert "waypoints" in data
    assert isinstance(data["waypoints"], list)
    assert len(data["waypoints"]) >= 1


# ============================================================================
# Test 3: Waypoints have correct structure
# ============================================================================

def test_gpx_parse_waypoint_structure():
    """
    GIVEN: A successful GPX parse response
    WHEN: Checking a waypoint in the response
    THEN: Has id, name, lat, lon, elevation_m, time_window
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    with open(_SAMPLE_GPX, "rb") as f:
        response = client.post(
            "/api/gpx/parse",
            files={"file": ("test.gpx", f, "application/gpx+xml")},
        )

    assert response.status_code == 200
    wp = response.json()["waypoints"][0]

    assert "id" in wp
    assert "name" in wp
    assert "lat" in wp
    assert "lon" in wp
    assert "elevation_m" in wp
    assert "time_window" in wp
    assert isinstance(wp["lat"], (int, float))
    assert isinstance(wp["lon"], (int, float))
    assert isinstance(wp["elevation_m"], int)


# ============================================================================
# Test 4: Query params stage_date and start_hour are forwarded
# ============================================================================

def test_gpx_parse_with_stage_date():
    """
    GIVEN: A valid GPX file
    WHEN: POST /api/gpx/parse?stage_date=2026-06-15&start_hour=7
    THEN: Returns stage with date=2026-06-15
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    with open(_SAMPLE_GPX, "rb") as f:
        response = client.post(
            "/api/gpx/parse?stage_date=2026-06-15&start_hour=7",
            files={"file": ("test.gpx", f, "application/gpx+xml")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-06-15"


# ============================================================================
# Test 5: Missing file returns 422
# ============================================================================

def test_gpx_parse_no_file_returns_422():
    """
    GIVEN: The FastAPI endpoint is available
    WHEN: POST /api/gpx/parse without file field
    THEN: Returns 422 (FastAPI validation error)
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.post("/api/gpx/parse")

    assert response.status_code == 422


# ============================================================================
# Test 6: Invalid GPX content returns 400
# ============================================================================

def test_gpx_parse_invalid_content_returns_400():
    """
    GIVEN: A file that is not valid GPX XML
    WHEN: POST /api/gpx/parse with that file
    THEN: Returns 400 with error detail
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.post(
        "/api/gpx/parse",
        files={"file": ("bad.gpx", b"this is not gpx xml", "application/gpx+xml")},
    )

    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


# ============================================================================
# Test 7: Invalid start_hour rejected
# ============================================================================

def test_gpx_parse_invalid_start_hour_returns_422():
    """
    GIVEN: A valid GPX file
    WHEN: POST /api/gpx/parse?start_hour=25
    THEN: Returns 422 (validation: ge=0, le=23)
    """
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    with open(_SAMPLE_GPX, "rb") as f:
        response = client.post(
            "/api/gpx/parse?start_hour=25",
            files={"file": ("test.gpx", f, "application/gpx+xml")},
        )

    assert response.status_code == 422
