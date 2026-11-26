"""MCP-Konnektor „Gregor Wetter“: Regen-/Gewitter-Nowcast (Issue #3398, Scheibe 2).

SPEC: docs/specs/modules/mcp_wetter_vollstaendig.md

Go ruft diesen Endpunkt erst nach der Kontingent-Buchung auf (``X-GZ-Core-Auth``,
ADR-0062). Die Werte kommen aus genau einem ``RadarNowcastService.get_nowcast``
(dieselbe Quellkette wie Briefings und Alarme, kein zweiter Abruf) und werden
nur auf die festgelegten Protokollfelder abgebildet (deutsche Token, nie
uebersetzt, ADR-0104). Ohne ``user_id``: der Endpunkt liest keine Nutzerdaten.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional

from fastapi import APIRouter, Query

from utils.timezone import local_dt, tz_for_coords

router = APIRouter()

_HORIZONT = timedelta(minutes=180)


def _token(label: str) -> str:
    """Stabiler Intensitaets-Token = Suffix des Katalogschluessels ``alarm.radar.intensitaet.*``."""
    from services.radar_service import _INTENSITY_KEYS

    return _INTENSITY_KEYS[label].rsplit(".", 1)[1]


def _frames(frames: list, jetzt: datetime, zone: tzinfo) -> list[dict]:
    """Frames im Fenster [jetzt, jetzt+180 min] in Ortszeit mit Offset."""
    fenster = sorted((f for f in frames if jetzt <= f.timestamp <= jetzt + _HORIZONT),
                     key=lambda f: f.timestamp)
    return [{"zeit": local_dt(f.timestamp, zone).isoformat(), "mm_h": f.precip_mm_h,
             "konvektiv": bool(f.is_convective), "hagel": bool(getattr(f, "hail", False))}
            for f in fenster]


def _zusammenfassung(ergebnis, frames: list[dict]) -> dict:
    """Protokollfelder; ohne Daten (gedrosselt/Ausfall) keine erfundenen Werte."""
    from services.radar_service import _DRY_THRESHOLD_MM_H

    ohne_daten = ergebnis.throttled or ergebnis.data_unavailable
    token = None if ohne_daten else _token(ergebnis.intensity_label)
    return {
        "beginn_min": ergebnis.onset_minutes,
        "ende_min": ergebnis.event_end_minutes,
        # Beginn in 0 Minuten heisst fuer den Fragenden ebenfalls "laeuft schon".
        "laeuft_bereits": ergebnis.already_running or ergebnis.onset_minutes == 0,
        "intensitaet": token,
        "konvektiv": ergebnis.is_convective,
        "hagel": any(f["hagel"] for f in frames if f["mm_h"] >= _DRY_THRESHOLD_MM_H),
        "max_mm_h_erste_stunde": None if ohne_daten else ergebnis.max_rate_mm_h,
        "summe_erste_stunde_mm": None if ohne_daten else round(ergebnis.window_precip_mm, 2),
        "quelle": ergebnis.source,
        "reichweite_min": ergebnis.source_reach_minutes,
        "ueber_horizont_hinaus": ergebnis.event_ongoing_beyond_horizon,
        "gedrosselt": ergebnis.throttled,
        "nicht_verfuegbar": ergebnis.data_unavailable,
        # Ausdrueckliches "trocken" nur mit Frames im Fenster, nie bei leerer Datenlage.
        "trocken": token == "trocken" and bool(frames) and ergebnis.onset_minutes is None
        and not ergebnis.already_running,
    }


@router.get("/api/_internal/mcp/nowcast")
def get_mcp_nowcast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    elevation_m: Optional[int] = Query(default=None),
):
    from services.radar_service import RadarNowcastService

    zone = tz_for_coords(lat, lon)
    # Prioritaet user_briefing: Go hat das Kontingent bereits gebucht, der Core
    # bucht nicht doppelt; user_id=None (nutzerfrei, Spec S2).
    ergebnis = RadarNowcastService().get_nowcast(
        lat, lon, elevation_m, priority="user_briefing", user_id=None,
    )
    frames = _frames(ergebnis.frames, datetime.now(timezone.utc), zone)
    return {"lat": lat, "lon": lon, "zeitzone": str(zone),
            **_zusammenfassung(ergebnis, frames), "frames": frames}
