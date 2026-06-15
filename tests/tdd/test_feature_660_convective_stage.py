"""TDD RED — Feature #660: Gewitter/Hagel-Stufe im Radar-Nowcast.

Spec: docs/specs/modules/radar_convective_stage.md
Test-Manifest: docs/specs/tests/feature_660_convective_stage_tests.md

KEINE MOCKS.
- AC-1/AC-3: reine, deterministische Funktionen mit ECHTEN RadarFrame-/
  NowcastResult-Objekten (kein Mock/patch/MagicMock).
- AC-2: echter HTTP-Call gegen Open-Meteo `minutely_15=...,weather_code` plus
  deterministischer Mapping-Test mit realer WMO-Code-Reihe durch den echten Service.
- AC-4: Alert-Pfad über echte Dependency-Injection (normale Funktion liefert reale
  konvektive RadarFrame-Daten). Die gebaute Alert-Nachricht wird durch echtes
  Ersetzen der `EmailOutput.send`-Methode mit einer Recorder-Funktion abgefangen
  (kein Mock-Objekt, nur Aufzeichnung der real konstruierten Argumente — Muster #612).

In der RED-Phase schlagen die Tests fehl, weil:
- `RadarFrame.is_convective` und `NowcastResult.is_convective` noch nicht existieren,
- `intensity_to_text` noch kein `is_convective`-Argument kennt,
- `_fetch_openmeteo_minutely15` `weather_code` noch nicht auswertet,
- der Radar-Alert die Gewitter-Lage noch nicht kennzeichnet.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import save_trip
from app.trip import Stage, Trip, Waypoint

# Reale Koordinate (München, DE-Abdeckung) für AC-2-Live-Abruf.
_LAT, _LON = 48.137, 11.575

_TRIP_NAME = "E2E Radar Convective"
_TRIP_ID = "e2e-radar-convective"

# WMO-Codes, die Konvektion (Gewitter/Hagel) anzeigen.
_CONVECTIVE_WMO = (95, 96, 99)


# ---------------------------------------------------------------------------
# Helpers (echte Objekte, keine Mocks)
# ---------------------------------------------------------------------------

def _make_today_trip() -> Trip:
    """Trip mit 2 Waypoints — Issue #822 erfordert >= 2 WP für segment-aware alerts."""
    today = date.today()
    stages = [
        Stage(
            id="T1",
            name="Heute-Etappe",
            date=today,
            waypoints=[
                Waypoint(id="W1", name="Start", lat=_LAT, lon=_LON, elevation_m=520),
                Waypoint(id="W2", name="Ziel", lat=_LAT + 0.05, lon=_LON + 0.05,
                         elevation_m=600),
            ],
        ),
    ]
    return Trip(id=_TRIP_ID, name=_TRIP_NAME, stages=stages)


def _convective_frames(onset_minutes: int, rate_mm_h: float):
    """Echte RadarFrame-Objekte: trocken bis onset, danach konvektiver Regen."""
    from providers.brightsky import RadarFrame  # noqa: PLC0415

    now = datetime.now(tz=timezone.utc)
    out = []
    for i in range(0, 120, 5):
        wet = i >= onset_minutes
        out.append(
            RadarFrame(
                timestamp=now + timedelta(minutes=i),
                precip_mm_h=(rate_mm_h if wet else 0.0),
                is_convective=wet,
            )
        )
    return out


# ===========================================================================
# AC-1: Konvektion schlägt die rate-basierte Stufe
# ===========================================================================

def test_ac1_intensity_convective_overrides_rate():
    """AC-1: is_convective=True → 'Starker Hagel/Gewitter', unabhängig von mm/h."""
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService()
    # Auch bei sehr niedriger Rate gewinnt die Konvektions-Stufe.
    assert svc.intensity_to_text(0.2, is_convective=True) == "Starker Hagel/Gewitter"
    assert svc.intensity_to_text(8.0, is_convective=True) == "Starker Hagel/Gewitter"


def test_ac1_intensity_non_convective_unchanged():
    """AC-1: Ohne Konvektion bleibt das 4-Stufen-Verhalten exakt erhalten."""
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService()
    assert svc.intensity_to_text(0.0, is_convective=False) == "Kein Niederschlag"
    assert svc.intensity_to_text(0.3, is_convective=False) == "Leichter Regen"
    assert svc.intensity_to_text(2.5, is_convective=False) == "Mäßiger Regen"
    assert svc.intensity_to_text(8.0, is_convective=False) == "Starker Regen"
    # Default-Argument muss weiterhin existieren und 4-stufig bleiben.
    assert svc.intensity_to_text(8.0) == "Starker Regen"


# ===========================================================================
# AC-2: Konvektions-Flag aus echtem Open-Meteo weather_code
# ===========================================================================

@pytest.mark.live
def test_ac2_openmeteo_frames_have_convective_flag():
    """AC-2: Echter Open-Meteo-Abruf → jeder Frame trägt ein bool is_convective."""
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService()
    frames = svc._fetch_openmeteo_minutely15(_LAT, _LON)
    assert frames, "Open-Meteo lieferte keine Frames"
    for f in frames:
        assert isinstance(f.is_convective, bool)


def test_ac2_weathercode_maps_to_convective():
    """AC-2: WMO 95/96/99 → konvektiv; alles andere → nicht konvektiv (echte Logik)."""
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService()
    for code in _CONVECTIVE_WMO:
        assert svc._is_convective_weathercode(code) is True
    for code in (0, 3, 61, 63, 65, 80, 82):
        assert svc._is_convective_weathercode(code) is False
    assert svc._is_convective_weathercode(None) is False


# ===========================================================================
# AC-3: Durchschlagen in NowcastResult + Text
# ===========================================================================

def test_ac3_derive_result_convective_label_and_text():
    """AC-3: Konvektiver nasser Frame → Result-Flag, Label und Text nennen Gewitter."""
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService(
        frame_source=lambda lat, lon: _convective_frames(onset_minutes=10, rate_mm_h=3.0)
    )
    result = svc.get_nowcast(_LAT, _LON)

    assert result.is_convective is True
    assert result.intensity_label == "Starker Hagel/Gewitter"

    text = svc.format_now_text(result)
    assert "Starker Hagel/Gewitter" in text


# ===========================================================================
# AC-4: Proaktiver Alert kennzeichnet Gewitter, genau einmal
# ===========================================================================

def test_ac4_radar_alert_convective_marked_once_then_throttles():
    """AC-4: 1 Alert mit Gewitter-Kennzeichnung + alert_log HIGH; 2. Lauf throttelt."""
    import json
    from pathlib import Path

    from outputs.email import EmailOutput
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    user_id = "default"
    trip = _make_today_trip()
    save_trip(trip)

    radar_service = RadarNowcastService(
        frame_source=lambda lat, lon: _convective_frames(onset_minutes=10, rate_mm_h=4.0)
    )

    log_path = Path(f"data/users/{user_id}/alert_log.json")
    if log_path.exists():
        data = json.loads(log_path.read_text())
        data["entries"] = [e for e in data.get("entries", []) if e.get("trip_id") != _TRIP_ID]
        log_path.write_text(json.dumps(data, indent=2))

    # Echte Aufzeichnung der gebauten Alert-Nachricht (kein Mock — normale Funktion,
    # die die real konstruierten Argumente festhält und den Versand unterdrückt).
    captured: list[dict] = []
    original_send = EmailOutput.send

    def _recording_send(self, *args, **kwargs):
        captured.append({"args": args, "kwargs": kwargs})
        return None

    EmailOutput.send = _recording_send
    try:
        svc = TripAlertService(user_id=user_id, radar_service=radar_service)
        svc.clear_radar_throttle(_TRIP_ID)
        sent_first = svc.check_radar_alerts()
        sent_second = svc.check_radar_alerts()

        assert sent_first == 1
        assert sent_second == 0  # Throttle greift

        entries = json.loads(log_path.read_text()).get("entries", [])
        radar_entries = [e for e in entries if e.get("trip_id") == _TRIP_ID]
        assert len(radar_entries) == 1
        assert radar_entries[0].get("severity") == "HIGH"

        # Gewitter-Kennzeichnung in der real gebauten Nachricht (Subject oder Body).
        assert captured, "Kein Alert-Versand abgefangen"
        blob = json.dumps(captured[0], ensure_ascii=False)
        assert "Gewitter" in blob
    finally:
        EmailOutput.send = original_send
        from app.loader import get_trips_dir
        p = get_trips_dir() / f"{_TRIP_ID}.json"
        if p.exists():
            p.unlink()
