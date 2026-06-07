"""TDD RED — Feature #656: Radar-Nowcasting für Ad-hoc-Abfragen & Alerts.

Spec: docs/specs/modules/radar_nowcast.md
Test-Manifest: docs/specs/tests/feature_656_radar_nowcast_tests.md

KEINE MOCKS. AC-1/AC-3 nutzen echte Fremd-APIs (BrightSky / Open-Meteo).
AC-2 und die Alert-Entscheidung sind reine, deterministische Funktionen, die mit
ECHTEN RadarFrame-/NowcastResult-Objekten geprüft werden (keine Mock-Objekte).
AC-4 prüft den Alert-Pfad über eine echte Dependency-Injection (eine normale
Funktion liefert reale RadarFrame-Daten — kein Mock/patch/MagicMock).

In der RED-Phase schlagen alle Tests fehl, weil die Module
`providers.brightsky` / `services.radar_service` und die Erweiterungen an
`trip_command_processor` / `trip_alert` noch nicht existieren.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import save_trip
from app.trip import Stage, Trip, Waypoint
from services.trip_command_processor import InboundMessage, TripCommandProcessor

# Eine reale Koordinate innerhalb der DWD-RADOLAN-Abdeckung (München).
_DE_LAT, _DE_LON = 48.137, 11.575

_TRIP_NAME = "E2E Radar Nowcast"
_TRIP_ID = "e2e-radar-nowcast"


# ---------------------------------------------------------------------------
# Helpers (echte Objekte, keine Mocks)
# ---------------------------------------------------------------------------

def _make_today_trip() -> Trip:
    """Trip mit einer Etappe HEUTE an einer DE-Koordinate."""
    today = date.today()
    stages = [
        Stage(
            id="T1",
            name="Heute-Etappe",
            date=today,
            waypoints=[
                Waypoint(id="W1", name="Start", lat=_DE_LAT, lon=_DE_LON, elevation_m=520),
                Waypoint(id="W2", name="Ziel", lat=_DE_LAT + 0.05, lon=_DE_LON + 0.05, elevation_m=700),
            ],
        ),
    ]
    return Trip(id=_TRIP_ID, name=_TRIP_NAME, stages=stages)


def _make_msg(body: str) -> InboundMessage:
    return InboundMessage(
        trip_name=_TRIP_NAME,
        body=body,
        sender="gregor-test@henemm.com",
        channel="email",
        received_at=datetime.now(tz=timezone.utc),
    )


def _frames(onset_minutes: int | None, rate_mm_h: float):
    """Baut echte RadarFrame-Objekte: trocken bis onset, danach Regen mit rate."""
    from providers.brightsky import RadarFrame  # noqa: PLC0415

    now = datetime.now(tz=timezone.utc)
    out = []
    for i in range(0, 120, 5):  # 2h in 5-min-Schritten
        if onset_minutes is None or i < onset_minutes:
            rate = 0.0
        else:
            rate = rate_mm_h
        out.append(RadarFrame(timestamp=now + timedelta(minutes=i), precip_mm_h=rate))
    return out


# ===========================================================================
# AC-1: Echter Radar-Abruf via BrightSky
# ===========================================================================

@pytest.mark.live
def test_ac1_brightsky_fetch_radar_returns_real_frames():
    """AC-1: BrightSky liefert echte Radar-Frames für eine DE-Koordinate."""
    from providers.brightsky import BrightSkyProvider, RadarFrame

    provider = BrightSkyProvider()
    frames = provider.fetch_radar(_DE_LAT, _DE_LON)

    assert isinstance(frames, list) and len(frames) >= 1
    assert all(isinstance(f, RadarFrame) for f in frames)
    # Zeitstempel monoton steigend
    ts = [f.timestamp for f in frames]
    assert ts == sorted(ts)
    # Niederschlagsraten numerisch, nicht-negativ
    assert all(isinstance(f.precip_mm_h, (int, float)) and f.precip_mm_h >= 0 for f in frames)


# ===========================================================================
# AC-2: Niederschlagswerte -> deterministischer deutscher Text
# ===========================================================================

def test_ac2_intensity_to_text_levels():
    """AC-2: Korrekte Intensitätsstufen für reale Beispielraten."""
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService()
    assert svc.intensity_to_text(0.0) == "Kein Niederschlag"
    assert svc.intensity_to_text(0.3) == "Leichter Regen"
    assert svc.intensity_to_text(2.5) == "Mäßiger Regen"
    assert svc.intensity_to_text(8.0) == "Starker Regen"


def test_ac2_format_now_text_mentions_onset_and_source():
    """AC-2: Bei bevorstehendem Regen nennt der Text Beginn + Quelle."""
    from services.radar_service import NowcastResult, RadarNowcastService

    svc = RadarNowcastService()
    result = NowcastResult(
        onset_minutes=20,
        intensity_label="Mäßiger Regen",
        source="radar",
        frames=_frames(onset_minutes=20, rate_mm_h=2.5),
    )
    text = svc.format_now_text(result)
    assert "Mäßiger Regen" in text
    # Beginn wird erwähnt (Minuten oder Uhrzeit)
    assert ("20" in text) or ("Min" in text) or (":" in text)
    # Quelle wird genannt
    assert "uelle" in text or "Quelle" in text


def test_ac2_format_now_text_dry():
    """AC-2: Bei Trockenheit klare 'kein Regen'-Aussage ohne Onset."""
    from services.radar_service import NowcastResult, RadarNowcastService

    svc = RadarNowcastService()
    result = NowcastResult(
        onset_minutes=None,
        intensity_label="Kein Niederschlag",
        source="minutely_15",
        frames=_frames(onset_minutes=None, rate_mm_h=0.0),
    )
    text = svc.format_now_text(result)
    assert "Kein Niederschlag" in text or "trocken" in text.lower()


# ===========================================================================
# AC-3: Ad-hoc `### now` Befehl < 10s mit Nowcast-Aussage
# ===========================================================================

@pytest.mark.live
def test_ac3_now_command_returns_nowcast_under_10s():
    """AC-3: `### now` liefert in <10s eine erfolgreiche Nowcast-Antwort."""
    trip = _make_today_trip()
    save_trip(trip)
    try:
        processor = TripCommandProcessor()
        start = time.monotonic()
        result = processor.process(_make_msg("### now"))
        elapsed = time.monotonic() - start

        assert result.success is True
        assert result.command == "now"
        assert elapsed < 10.0
        # Body enthält eine Nowcast-Aussage + Quellenangabe
        body = result.confirmation_body
        assert any(
            kw in body
            for kw in ("Niederschlag", "Regen", "trocken", "Gewitter")
        )
        assert "uelle" in body or "Quelle" in body
    finally:
        from app.loader import get_trips_dir
        p = get_trips_dir() / f"{_TRIP_ID}.json"
        if p.exists():
            p.unlink()


def test_ac3_now_command_without_today_stage_gives_clear_message():
    """AC-3 (Rand): Ohne heutige Etappe klare Meldung statt Absturz."""
    today = date.today()
    trip = Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[Stage(
            id="T1", name="Vergangen", date=today - timedelta(days=10),
            waypoints=[Waypoint(id="W1", name="X", lat=_DE_LAT, lon=_DE_LON, elevation_m=500)],
        )],
    )
    save_trip(trip)
    try:
        result = TripCommandProcessor().process(_make_msg("### now"))
        # Kein heutiger Standort -> klare, positionsbezogene Meldung (nicht der
        # generische "unbekannter Befehl"-Pfad). Beweist, dass `now` als gültiger
        # Befehl erkannt wird und den fehlenden Standort sauber meldet.
        assert result.command == "now"
        body = result.confirmation_body.lower()
        assert any(kw in body for kw in ("etappe", "standort", "position", "heute"))
    finally:
        from app.loader import get_trips_dir
        p = get_trips_dir() / f"{_TRIP_ID}.json"
        if p.exists():
            p.unlink()


# ===========================================================================
# AC-4: Proaktiver Radar-Alert bei Onset <= Schwelle + Throttle
# ===========================================================================

def test_ac4_radar_alert_due_pure_logic():
    """AC-4: Reine Entscheidungsfunktion — Onset <= Schwelle -> Alert fällig."""
    from services.radar_service import NowcastResult
    from services.trip_alert import radar_alert_due

    soon = NowcastResult(
        onset_minutes=10, intensity_label="Starker Regen", source="radar",
        frames=_frames(10, 8.0),
    )
    later = NowcastResult(
        onset_minutes=45, intensity_label="Leichter Regen", source="radar",
        frames=_frames(45, 0.3),
    )
    dry = NowcastResult(
        onset_minutes=None, intensity_label="Kein Niederschlag", source="radar",
        frames=_frames(None, 0.0),
    )
    assert radar_alert_due(soon, threshold_min=20) is True
    assert radar_alert_due(later, threshold_min=20) is False
    assert radar_alert_due(dry, threshold_min=20) is False


def test_ac4_check_radar_alerts_sends_once_then_throttles():
    """AC-4: Genau ein Alert + alert_log-Eintrag; zweiter Lauf throttelt."""
    import json
    from pathlib import Path

    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    user_id = "default"
    trip = _make_today_trip()
    save_trip(trip)

    # Echte Frame-Quelle (normale Funktion, KEIN Mock) liefert Onset in 10 min.
    def real_frame_source(lat: float, lon: float):
        return _frames(onset_minutes=10, rate_mm_h=8.0)

    radar_service = RadarNowcastService(frame_source=real_frame_source)

    # Vorherige Radar-Alert-Spuren für diesen Trip entfernen (deterministisch).
    log_path = Path(f"data/users/{user_id}/alert_log.json")
    if log_path.exists():
        data = json.loads(log_path.read_text())
        data["entries"] = [e for e in data.get("entries", []) if e.get("trip_id") != _TRIP_ID]
        log_path.write_text(json.dumps(data, indent=2))

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
    finally:
        from app.loader import get_trips_dir
        p = get_trips_dir() / f"{_TRIP_ID}.json"
        if p.exists():
            p.unlink()
