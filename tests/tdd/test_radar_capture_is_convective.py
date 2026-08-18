"""TDD-RED: Issue #1948 Scheibe S2 — AC-8 ``is_convective`` je Frame im
Zweig-c-Mitschnitt (S1-Erweiterung, einzige Aenderung an S1-Code).

SPEC: docs/specs/modules/alarm_testeinspeisung.md

``RadarNowcastService._capture_nowcast_frames`` (radar_service.py:660-676)
schreibt heute je Frame nur ``timestamp``/``precip_mm_h`` -- ``is_convective``
liegt auf ``RadarFrame.is_convective`` bereits vor, wird aber nicht mit
weggeschrieben. Ohne das Feld deckt eine Zweig-c-Mitschnittdatei nicht alle
Pflichtfelder von ``NowcastFramesPayload`` ab (Scheibe S2).

RED-Grund: ``is_convective`` fehlt im geschriebenen Datensatz.

Mock-frei: echte ``RadarFrame``-Objekte (DI-Seam ``frame_source``), echte
``RadarNowcastCacheService``-Instanz (leer -> garantierter Cache-Miss),
echte Dateilese-Pruefung. Kein ``real_data_root``-Marker: die autouse-
Isolation (``_isolate_data_root``) leitet ``get_data_root()`` in einen
tmp-Pfad um, wie im Vorbild ``tests/unit/test_radar_service_capture.py``.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


def _capture_dir():
    from app.loader import get_data_root

    return get_data_root() / "debug" / "alert_input" / "nowcast"


def test_ac8_capture_records_is_convective_per_frame_matching_raw_value():
    from providers.brightsky import RadarFrame
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService, _nowcast_source_key

    lat, lon = 47.601234, 12.897654
    now = datetime.now(timezone.utc)
    frames = [
        RadarFrame(timestamp=now + timedelta(minutes=5), precip_mm_h=3.0, is_convective=True),
        RadarFrame(timestamp=now + timedelta(minutes=10), precip_mm_h=1.0, is_convective=False),
    ]
    svc = RadarNowcastService(
        frame_source=lambda la, lo: frames,
        cache=RadarNowcastCacheService(),  # leer -> garantierter Cache-Miss
    )
    result = svc.get_nowcast(lat, lon)
    assert result is not None  # Bestandsverhalten unveraendert

    key = _nowcast_source_key(lat, lon)
    matches = sorted(_capture_dir().glob(f"{key}_*.json"))
    assert matches, (
        f"Kein Eingangs-Datensatz fuer source_key {key!r} unter "
        f"{_capture_dir()} gefunden -- get_nowcast() ruft "
        f"alert_input_capture.capture_system() nicht am Cache-Miss-Mount-"
        f"Punkt auf."
    )
    record = json.loads(matches[-1].read_text())
    raw_frames = record.get("payload", {}).get("frames")
    assert raw_frames and len(raw_frames) == 2, (
        f"Unerwartete Frame-Anzahl im Mitschnitt: {raw_frames!r}"
    )
    assert raw_frames[0].get("is_convective") is True, (
        f"AC-8: Frame 0 (RadarFrame.is_convective=True) fehlt/falsch im "
        f"Mitschnitt: {raw_frames[0]!r}"
    )
    assert raw_frames[1].get("is_convective") is False, (
        f"AC-8: Frame 1 (RadarFrame.is_convective=False) fehlt/falsch im "
        f"Mitschnitt: {raw_frames[1]!r}"
    )
