"""TDD RED — Issue #2283 Scheibe S1, AC-1 + AC-2 (Python-Kern).

Spec: docs/specs/modules/shared_preview_tab.md

Gewaehlte Python-Route (Go-Dispatcher `GET /api/briefings/{id}/preview?kind=`
proxied 1:1 darauf, `user_id` injiziert der Go-Proxy aus der Session):

    GET /api/briefings/{entity_id}/preview?kind=route|vergleich&user_id=<uid>
        [&type=morning|evening&date=YYYY-MM-DD&demo=true]   (type/demo nur route)

Antwortform (beide kinds gleich):

    {"subject": str,
     "email_html": str,
     "sms": {"text": str, "char_count": int},
     "telegram": {"body": str, "bubbles"?: list[str]}}

Referenz (Gleichheit je Kanal, keine Render-Funktion gemockt):
- kind=route: die bestehenden Einzelrouten desselben Trips —
  `subject` ↔ `GET /api/preview/{id}/sms` .subject (die E-Mail-Route liefert
  nur HTML, keinen Betreff); `email_html` ↔ `GET …/email` (Body);
  `sms.text`/`sms.char_count` ↔ `GET …/sms` .token_line/.char_count;
  `telegram.body`/`telegram.bubbles` ↔ `GET …/telegram` .body/.bubbles.
- kind=vergleich: `POST /api/preview/compare/{id}` —
  `sms.text` ↔ `sms`, `sms.char_count` ↔ `sms_char_count`,
  `telegram.body` ↔ `telegram`, `subject`/`email_html` gleichnamig.

Netzfrei: Trip-Seite ueber `demo=true` (FixtureProvider, Issue #483); die
Vergleichs-Seite ersetzt nur die teure Upstream-Naht `ComparisonEngine.run`
durch eine echte Subklasse (Haus-Muster test_compare_preview_service.py).
Die Renderer bleiben echt.

RED-Grund: die Route `/api/briefings/{id}/preview` existiert im Python-Core
noch nicht → 404 vom Router. Die Einzelrouten-Probe in jedem Test ist heute
GRUEN (belegt, dass die Fixture traegt).
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.loader import get_briefings_dir, get_data_dir, save_location
from app.models import ForecastDataPoint, ThunderLevel
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

TRIP_DATE = (date.today() + timedelta(days=1)).isoformat()
COMPARE_DATE = date(2026, 7, 8)


# ---------------------------------------------------------------------------
# Umgebung
# ---------------------------------------------------------------------------


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolierter Daten-Root ueber beide Zugriffsformen (Muster
    test_compare_preview_service.py::compare_env); echte Nutzerkennung,
    niemals 'default'."""
    from app import loader as app_loader

    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app_loader, "_DATA_ROOT", str(data_root))
    try:
        from src.app import loader as src_loader

        monkeypatch.setattr(src_loader, "_DATA_ROOT", str(data_root))
    except ImportError:  # pragma: no cover
        pass
    return f"tdd-2283-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def client():
    from api.routers import preview

    app = FastAPI()
    app.include_router(preview.router)
    return TestClient(app, raise_server_exceptions=False)


def _seed_trip(user_id: str, trip_id: str, name: str) -> None:
    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": trip_id,
        "name": name,
        "stages": [
            {
                "id": "T1", "name": "Etappe 1", "date": TRIP_DATE,
                "waypoints": [
                    {"id": "G1", "name": "Start", "lat": 47.2692, "lon": 11.4041,
                     "elevation_m": 600},
                    {"id": "G2", "name": "Ziel", "lat": 47.3010, "lon": 11.4500,
                     "elevation_m": 1200},
                ],
            }
        ],
    }
    (trips_dir / f"{trip_id}.json").write_text(json.dumps(payload), encoding="utf-8")


def _dp(hour: int) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(COMPARE_DATE.year, COMPARE_DATE.month, COMPARE_DATE.day, hour, 0),
        t2m_c=22.0, wind_chill_c=21.0, wind10m_kmh=11.0, gust_kmh=19.0,
        precip_1h_mm=0.0, cloud_total_pct=35, uv_index=5.0,
        thunder_level=ThunderLevel.NONE, pop_pct=10, visibility_m=9000,
    )


class EngineCalls:
    def __init__(self) -> None:
        self.count = 0


def install_recording_engine(monkeypatch, calls: EngineCalls) -> None:
    """Echte Subklasse der ComparisonEngine, die ihr Ergebnis AUS den
    uebergebenen Orten baut (kein Netz, keine vorgegebene Antwort)."""
    import services.comparison_engine as ce_mod
    from app.user import ComparisonResult, LocationResult

    original = ce_mod.ComparisonEngine

    class RecordingEngine(original):  # echte Subklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            locations = list(locations or [])
            calls.count += 1
            return ComparisonResult(
                locations=[
                    LocationResult(
                        location=loc, score=90 - 7 * i, temp_max=22.0 + i,
                        temp_min=12.0 + i, wind_max=11.0, gust_max=19.0,
                        cloud_avg=35, sunny_hours=6, official_alerts=[],
                        hourly_data=[_dp(9), _dp(12), _dp(15)],
                    )
                    for i, loc in enumerate(locations)
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date", COMPARE_DATE),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", RecordingEngine)
    import services.compare_preview_service as svc_mod

    if hasattr(svc_mod, "ComparisonEngine"):
        monkeypatch.setattr(svc_mod, "ComparisonEngine", RecordingEngine)


def seed_compare(user_id: str, preset_id: str, locations: list[SavedLocation]) -> None:
    for loc in locations:
        save_location(loc, user_id=user_id)
    write_compare_briefings(
        get_data_dir(user_id),
        [{
            "id": preset_id,
            "name": "Urlaubsorte 2283",
            "user_id": user_id,
            "location_ids": [loc.id for loc in locations],
            "schedule": "daily",
            "profil": "ALLGEMEIN",
            "hour_from": 9,
            "hour_to": 16,
            "forecast_hours": 48,
            "empfaenger": ["a@example.invalid"],
            "created_at": "2026-07-01T00:00:00Z",
        }],
    )


# ---------------------------------------------------------------------------
# Referenz-Abrufe ueber die bestehenden Einzelrouten
# ---------------------------------------------------------------------------


def _trip_reference(client, trip_id: str, user_id: str, report_type: str) -> dict:
    params = {"user_id": user_id, "type": report_type, "date": TRIP_DATE, "demo": "true"}
    email = client.get(f"/api/preview/{trip_id}/email", params=params)
    sms = client.get(f"/api/preview/{trip_id}/sms", params=params)
    tg = client.get(f"/api/preview/{trip_id}/telegram", params=params)
    for name, resp in (("email", email), ("sms", sms), ("telegram", tg)):
        assert resp.status_code == 200, (
            f"Fixture-Probe: Einzelroute {name} muss heute 200 liefern, war "
            f"{resp.status_code}: {resp.text[:300]}"
        )
    sms_j, tg_j = sms.json(), tg.json()
    return {
        "subject": sms_j["subject"],
        "email_html": email.text,
        "sms": {"text": sms_j["token_line"], "char_count": sms_j["char_count"]},
        "telegram": {"body": tg_j["body"], "bubbles": tg_j.get("bubbles")},
    }


def _compare_reference(client, preset_id: str, user_id: str) -> dict:
    resp = client.post(
        f"/api/preview/compare/{preset_id}",
        params={"user_id": user_id, "date": COMPARE_DATE.isoformat()},
    )
    assert resp.status_code == 200, (
        f"Fixture-Probe: POST /api/preview/compare muss heute 200 liefern, war "
        f"{resp.status_code}: {resp.text[:300]}"
    )
    j = resp.json()
    return {
        "subject": j["subject"],
        "email_html": j["email_html"],
        "sms": {"text": j["sms"], "char_count": j["sms_char_count"]},
        "telegram": {"body": j["telegram"], "bubbles": None},
    }


def _assert_bundle_matches(bundle: dict, refs: list[dict], label: str) -> None:
    """Gleichheit je Kanal gegen die Referenz. Zwei Referenz-Abrufe (vor und
    nach dem Buendel) fangen einen Minutenwechsel in Zeitstempeln ab: das
    Buendel muss je Kanal einer der beiden Referenzen gleichen."""
    for key in ("subject", "email_html", "sms", "telegram"):
        assert key in bundle, f"{label}: Feld '{key}' fehlt in der Buendelantwort: {sorted(bundle)}"
    assert set(bundle["sms"]) >= {"text", "char_count"}, bundle["sms"]
    assert "body" in bundle["telegram"], bundle["telegram"]

    def _cands(getter):
        return [getter(r) for r in refs]

    assert bundle["subject"] in _cands(lambda r: r["subject"]), f"{label}: subject weicht ab"
    assert bundle["email_html"] in _cands(lambda r: r["email_html"]), (
        f"{label}: email_html weicht von der Einzelroute ab"
    )
    assert bundle["sms"]["text"] in _cands(lambda r: r["sms"]["text"]), (
        f"{label}: sms.text weicht ab: {bundle['sms']['text']!r}"
    )
    assert bundle["sms"]["char_count"] == len(bundle["sms"]["text"])
    assert bundle["sms"]["char_count"] in _cands(lambda r: r["sms"]["char_count"])
    assert bundle["telegram"]["body"] in _cands(lambda r: r["telegram"]["body"]), (
        f"{label}: telegram.body weicht ab"
    )
    ref_bubbles = _cands(lambda r: r["telegram"]["bubbles"])
    assert bundle["telegram"].get("bubbles") in ref_bubbles, (
        f"{label}: telegram.bubbles weicht ab: {bundle['telegram'].get('bubbles')!r}"
    )


# ---------------------------------------------------------------------------
# AC-1 — kind=route
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("report_type", ["morning", "evening"])
def test_trip_bundle_preview_equals_single_channel_routes(env, client, report_type):
    """AC-1: GIVEN ein angemeldeter Nutzer mit einem Trip
    WHEN er GET /api/briefings/{id}/preview?kind=route (gleiche type/date/demo)
    aufruft
    THEN enthaelt EINE Antwort subject, email_html, sms{text,char_count} und
    telegram{body,bubbles?}, je Kanal identisch zu den bisherigen Einzelrouten.

    RED: Route fehlt im Python-Core → 404."""
    user_id = env
    _seed_trip(user_id, "trip-2283", "Bündel-Trip 2283")

    ref_before = _trip_reference(client, "trip-2283", user_id, report_type)
    resp = client.get(
        "/api/briefings/trip-2283/preview",
        params={"kind": "route", "user_id": user_id, "type": report_type,
                "date": TRIP_DATE, "demo": "true"},
    )
    ref_after = _trip_reference(client, "trip-2283", user_id, report_type)

    assert resp.status_code == 200, (
        f"AC-1: Buendelroute muss 200 liefern, war {resp.status_code}: {resp.text[:200]}"
    )
    _assert_bundle_matches(resp.json(), [ref_before, ref_after], f"route/{report_type}")


# ---------------------------------------------------------------------------
# AC-2 — kind=vergleich
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_locations", [1, 3])
def test_compare_bundle_preview_has_same_shape_and_equals_compare_route(
    env, client, monkeypatch, n_locations,
):
    """AC-2: GIVEN ein angemeldeter Nutzer mit einem Ortsvergleich
    WHEN er GET /api/briefings/{id}/preview?kind=vergleich aufruft
    THEN bekommt er dieselbe Antwortform wie bei kind=route
    (subject, email_html, sms{text,char_count}, telegram{body}) und den
    Inhalt von POST /api/preview/compare/{id} fuer dieselbe Eingabe — genau
    EIN Engine-Lauf je Ort fuer das Buendel.

    RED: Route fehlt im Python-Core → 404."""
    user_id = env
    all_locs = [
        SavedLocation(id="loc-ibk", name="Innsbruck", lat=47.27, lon=11.39, elevation_m=574),
        SavedLocation(id="loc-bz", name="Bozen", lat=46.50, lon=11.35, elevation_m=262),
        SavedLocation(id="loc-mer", name="Meran", lat=46.67, lon=11.16, elevation_m=325),
    ]
    seed_compare(user_id, "cp-2283", all_locs[:n_locations])
    calls = EngineCalls()
    install_recording_engine(monkeypatch, calls)

    ref_before = _compare_reference(client, "cp-2283", user_id)
    calls.count = 0
    resp = client.get(
        "/api/briefings/cp-2283/preview",
        params={"kind": "vergleich", "user_id": user_id, "date": COMPARE_DATE.isoformat()},
    )
    bundle_calls = calls.count
    ref_after = _compare_reference(client, "cp-2283", user_id)

    assert resp.status_code == 200, (
        f"AC-2: Buendelroute (vergleich) muss 200 liefern, war {resp.status_code}: "
        f"{resp.text[:200]}"
    )
    bundle = resp.json()
    _assert_bundle_matches(bundle, [ref_before, ref_after], f"vergleich/{n_locations}")
    for loc in all_locs[:n_locations]:
        assert loc.name in bundle["email_html"], f"Ort {loc.name} fehlt in der Vorschau"
    assert bundle_calls == n_locations, (
        f"AC-2: das Buendel darf nur EINEN Engine-Lauf je Ort ausloesen "
        f"(kein Mehrfachrendern je Kanal), waren {bundle_calls} fuer {n_locations} Orte"
    )
