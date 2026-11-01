"""Stundenreihen fuer die Alarm-Vorschau (Issue #1737, Spec v1.1 Schritt 8).

EIN Baustein fuer Trip UND Ortsvergleich (ADR-0021): die Vorschau liest die
ALTE Reihe (Anker) und holt die FRISCHE Reihe aus genau denselben Quellen wie
der Versand -- strikt ueber die echte `user_id` (nie "default"). Die Reihen
aus dem Anfrage-Inhalt werden nie gelesen.

Fail-soft: kein Anker -> keine Reihen (kein Abruf); scheiternder Frisch-Abruf
-> keine Reihen, kein Fehler. Die Vorschau schreibt nichts.

Abruf-Naht: `fetch` ist austauschbar (Funktionsparameter); im Betrieb der
echte Abruf wie im Versand, im Test die Fixture-Naht (`GZ_TEST_FIXTURE_DIR`).
Zeitbudget: `deadline` (gemeinsam fuer alle Abrufe einer Vorschau), Standard
`PREVIEW_FETCH_BUDGET_S`.
"""
from __future__ import annotations

import contextvars
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Gesamt-Zeitbudget fuer die Beschaffung der Vorschau-Reihen (alle Abrufe
# einer Vorschau zusammen, sie laufen seriell je Segment bzw. Ort). Der Go-
# Proxy bricht die Alarm-Vorschau nach 30 s ab (`internal/handler/
# preview_proxy.go`, `previewProxyTimeout`), ein einzelner Open-Meteo-Abruf darf
# bis 30 s dauern. 15 s lassen die andere Haelfte fuer Anker-Lesen, Rendern und
# Netz -- laeuft das Budget ab, zeigt die Vorschau keine Stundenzeilen (AC-10)
# statt in den Proxy-Timeout zu laufen (AC-11).
PREVIEW_FETCH_BUDGET_S = 15.0


def preview_deadline(budget_s: float = PREVIEW_FETCH_BUDGET_S) -> float:
    """Frist (`time.monotonic()`) fuer alle Abrufe EINER Vorschau."""
    return time.monotonic() + budget_s


def _within(deadline: float, fn: Callable, *args, **kwargs):
    """`fn(*args, **kwargs)` mit Frist; abgelaufen -> `TimeoutError`. Der
    Abruf laeuft in einem Hilfsfaden (mit dem Kontext des Aufrufers) und wird
    bei Fristablauf nicht abgewartet."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Zeitbudget der Vorschau-Reihen erschoepft")
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        ctx = contextvars.copy_context()
        return pool.submit(ctx.run, fn, *args, **kwargs).result(timeout=remaining)
    finally:
        pool.shutdown(wait=False)


def trip_preview_series(
    trip, *, user_id: str, now_utc: datetime,
    fetch: Optional[Callable] = None, deadline: Optional[float] = None,
) -> tuple[Optional[list], Optional[list]]:
    """(Anker-Segmente, frische Segmente) eines Trips dieses Nutzers --
    dieselbe Quelle wie `check_and_send_alerts` (`_get_cached_weather` mit
    Tagesbezug, `_fetch_fresh_weather`). `(None, None)` ohne Anker oder
    frische Reihe."""
    from services.trip_alert import TripAlertService

    svc = TripAlertService(user_id=user_id)
    try:
        anchor = svc._get_cached_weather(
            trip, tagesgleicher_anker_noetig=True, now_utc=now_utc, nur_lesen=True,
        )
        if not anchor:
            return None, None
        fresh = _within(
            deadline if deadline is not None else preview_deadline(),
            fetch or svc._fetch_fresh_weather, anchor,
        )
    except Exception as e:  # noqa: BLE001 -- Vorschau ist fail-soft (AC-11)
        logger.warning(
            "Alarm-Vorschau Trip %s: Stundenreihen nicht beschaffbar (%s: %s) "
            "-- Vorschau ohne Stundenzeilen (vgl. #1737)", trip.id, type(e).__name__, e,
        )
        return None, None
    fresh = [w for w in fresh or [] if getattr(w, "timeseries", None)]
    return (anchor, fresh) if fresh else (None, None)


def compare_preview_point(
    preset: dict, preset_id: str, loc, *, user_id: str,
    fetch: Optional[Callable] = None, deadline: Optional[float] = None,
):
    """(frischer Punkt, Anker-Punkt) eines Orts dieses Nutzers -- dieselbe
    Quelle und dieselben Argumente wie `compare_alert._vorbereite_ort`/`_abruf`.
    `(None, None)` ohne Anker oder bei scheiterndem Frisch-Abruf."""
    from services.compare_alert import CompareAlertService
    from services.compare_location_weather_source import CompareLocationWeatherSource
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.report_config_resolver import resolve_compare_time_window

    try:
        cached = CompareWeatherSnapshotService(user_id=user_id).load(preset_id, loc.id)
        # Wie der Versand: Anker > 26 h -> kein Alarm, also keine Stundenzeilen.
        if not cached or CompareAlertService._anchor_too_old(cached[0], preset_id, loc.id):
            return None, None
        start_hour, end_hour = resolve_compare_time_window(preset)
        zusatz = {"elevation_m": loc.elevation_m, "user_id": user_id}
        if cached[0].target_date is not None:
            zusatz["target_date"] = cached[0].target_date
        fresh = _within(
            deadline if deadline is not None else preview_deadline(),
            fetch or CompareLocationWeatherSource().fetch,
            loc.id, loc.lat, loc.lon, start_hour, end_hour, **zusatz,
        )
    except Exception as e:  # noqa: BLE001 -- Vorschau ist fail-soft (AC-11)
        logger.warning(
            "Alarm-Vorschau Ortsvergleich %s/%s: Stundenreihen nicht beschaffbar "
            "(%s: %s) -- Vorschau ohne Stundenzeilen (vgl. #1737)",
            preset_id, loc.id, type(e).__name__, e,
        )
        return None, None
    if not getattr(fresh, "timeseries", None):
        return None, None
    return fresh, cached[0]
