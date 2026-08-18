"""TDD RED — Issue #1948 (Scheibe S1): Zweig-c-Mount in
``RadarNowcastService.get_nowcast`` schreibt vor ``_derive_result``
(Cache-Hit UND Cache-Miss) einen System-Level-Eingangs-Datensatz mit den
rohen Frames.

SPEC: docs/specs/modules/alarm_eingangsprotokoll.md (AC-3)

RED-Grund: ``alert_input_capture.py`` existiert nicht; ``get_nowcast()``
ruft an ihren beiden Mount-Punkten (radar_service.py Z. 199 und Z. 212)
noch keinen Capture-Aufruf auf.

Mock-frei: echte ``RadarFrame``-Objekte, ``_frame_source``-DI-Seam fuer den
Cache-Miss-Zweig (Vorbild ``tests/tdd/test_feature_656_radar_nowcast.py``),
eine echte ``RadarNowcastCacheService``-Instanz fuer den vorbefuellten
Cache-Hit-Zweig (kein Mock/patch).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone


def _capture_dir():
    from app.loader import get_data_root

    return get_data_root() / "debug" / "alert_input" / "nowcast"


def _frames(rate_mm_h: float = 1.5):
    from providers.brightsky import RadarFrame

    now = datetime.now(timezone.utc)
    return [
        RadarFrame(timestamp=now + timedelta(minutes=i), precip_mm_h=rate_mm_h)
        for i in range(0, 30, 5)
    ]


def test_ac3_cache_miss_schreibt_rohe_frames_vor_derive_result():
    """AC-3 (Cache-Miss): GIVEN ``get_nowcast`` ruft ueber die injizierte
    ``_frame_source`` frische Frames ab, WHEN ``_derive_result`` aufgerufen
    wird, THEN existiert vorher ein Eingangs-Datensatz mit denselben rohen
    Frames unter ``data/debug/alert_input/nowcast/``."""
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService

    frames = _frames(rate_mm_h=2.5)
    svc = RadarNowcastService(
        frame_source=lambda lat, lon: frames,
        cache=RadarNowcastCacheService(),  # leer -> garantierter Cache-Miss
    )
    lat, lon = 47.7, 12.3
    result = svc.get_nowcast(lat, lon)
    assert result is not None  # Bestandsverhalten unveraendert

    files = sorted(_capture_dir().glob("*.json"))
    assert files, (
        "Kein Eingangs-Datensatz unter data/debug/alert_input/nowcast/ "
        "gefunden -- get_nowcast() ruft alert_input_capture.capture_system()"
        " am Cache-Miss-Mount-Punkt nicht auf."
    )
    record = json.loads(files[-1].read_text())
    assert record.get("capture_id"), "capture_id fehlt im Eingangs-Datensatz."
    payload = record.get("payload", {})
    assert payload.get("source") == "radar", f"Falsche/fehlende Quelle: {payload!r}"
    raw_frames = payload.get("frames")
    assert raw_frames and len(raw_frames) == len(frames), (
        f"Rohe Frame-Anzahl weicht ab: erwartet {len(frames)}, "
        f"erhalten {raw_frames!r}"
    )


def test_ac3_cache_hit_schreibt_ebenfalls_einen_eingangsdatensatz():
    """AC-3 (Cache-Hit): GIVEN ``get_nowcast`` liefert Frames aus einem
    vorbefuellten Cache-Treffer, WHEN ``_derive_result`` aufgerufen wird,
    THEN existiert AUCH in diesem Zweig vorher ein Eingangs-Datensatz --
    nicht nur beim Cache-Miss."""
    from services.radar_cache import RadarNowcastCacheService
    from services.radar_service import RadarNowcastService, _region_bucket

    cache = RadarNowcastCacheService()
    lat, lon = 47.7, 12.3
    now = datetime.now(timezone.utc)
    frames = _frames(rate_mm_h=4.0)
    cache.put(lat, lon, _region_bucket(lat, lon), frames, "INCA", now=now)

    def _sentinel(_lat, _lon):
        raise AssertionError("_frame_source wurde bei einem Cache-Hit aufgerufen")

    svc = RadarNowcastService(frame_source=_sentinel, cache=cache)
    result = svc.get_nowcast(lat, lon)
    assert result is not None

    files = sorted(_capture_dir().glob("*.json"))
    hit_records = [json.loads(f.read_text()) for f in files]
    matching = [r for r in hit_records if r.get("payload", {}).get("source") == "INCA"]
    assert matching, (
        "Kein Eingangs-Datensatz fuer den Cache-Hit-Zweig gefunden -- "
        "get_nowcast() ruft alert_input_capture.capture_system() am "
        "Cache-Hit-Mount-Punkt (vor dem ersten _derive_result-Aufruf) nicht "
        "auf."
    )
