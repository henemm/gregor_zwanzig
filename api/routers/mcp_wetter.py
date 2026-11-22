"""MCP-Konnektor „Gregor Wetter“: stuendliche Rohwerte in Ortszeit (Issue #3281, Scheibe 1).

SPEC: docs/specs/modules/mcp_wetter_konnektor.md

Go ruft diesen Endpunkt erst nach der Kontingent-Buchung auf (``X-GZ-Core-Auth``,
ADR-0062). Keine Bewertung, kein Renderer: ausgegeben werden die Rohfelder des
Datenpunkts mit ihrer Einheit aus dem Katalog; die Sonnenminuten je Stunde
kommen aus der einen DNI-Umrechnung des Bestands (ADR-0127). Der Endpunkt liest
keine Nutzerdaten.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone, tzinfo
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.fehler import api_fehler
from i18n import t
from utils.timezone import local_dt, to_utc, tz_for_coords

router = APIRouter()
logger = logging.getLogger(__name__)

#: Hoechstzeitraum je Abruf (Spec: maximal 7 Tage) und Standard ohne Angabe.
HOECHSTZEITRAUM = timedelta(days=7)
STANDARDZEITRAUM = timedelta(hours=24)
_STUNDE = timedelta(hours=1)

#: Ausgegebene Rohfelder des Datenpunkts (Namen bleiben unuebersetzt, ADR-0104).
_ROHFELDER = (
    "t2m_c", "precip_1h_mm", "pop_pct", "wind10m_kmh", "gust_kmh",
    "wind_direction_deg", "cloud_total_pct", "thunder_level", "wmo_code",
    "snowfall_limit_m", "freezing_level_m",
)
_SONNENMINUTEN = "sonnenminuten"


def _einheiten() -> dict[str, str]:
    """Einheit je ausgegebenem Feld; Rohfelder nach dem Katalog (``dp_field``)."""
    from app.metric_catalog import get_all_metrics

    katalog: dict[str, str] = {}
    for metrik in get_all_metrics():
        katalog.setdefault(metrik.dp_field, metrik.unit)
    einheiten = {feld: katalog.get(feld, "") for feld in _ROHFELDER}
    einheiten["wmo_code"] = "WMO"
    einheiten[_SONNENMINUTEN] = "min"
    return einheiten


def _zeitpunkt(text: str, zone: tzinfo, parameter: str) -> datetime:
    """ISO-8601-Zeitpunkt; ohne Offset gilt die Ortszeit. Ergebnis in UTC."""
    try:
        zeitpunkt = datetime.fromisoformat(text)
    except ValueError:
        raise api_fehler(422, "mcp_zeitpunkt_ungueltig", None, parameter=parameter) from None
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=zone)
    return to_utc(zeitpunkt)


def _zeitraum(von: Optional[str], bis: Optional[str], zone: tzinfo) -> tuple[datetime, datetime, bool]:
    """Volle Stunden [start, ende) in UTC, hoechstens 7 Tage; begrenzt=True bei Kuerzung.

    bis muss nach von liegen (ungerundet, wie die Pruefung in Go)."""
    beginn = _zeitpunkt(von, zone, "von") if von else datetime.now(timezone.utc)
    schluss = _zeitpunkt(bis, zone, "bis") if bis else None
    if schluss is not None and schluss <= beginn:
        raise api_fehler(422, "mcp_bis_vor_von", None)
    start = beginn.replace(minute=0, second=0, microsecond=0)
    if schluss is None:
        ende = start + STANDARDZEITRAUM
    else:
        abgerundet = schluss.replace(minute=0, second=0, microsecond=0)
        ende = abgerundet if abgerundet == schluss else abgerundet + _STUNDE
    begrenzt = ende - start > HOECHSTZEITRAUM
    if begrenzt:
        ende = start + HOECHSTZEITRAUM
    return start, ende, begrenzt


def _stunde(punkt, zone: tzinfo, band: tuple[float, float]) -> dict:
    """Eine Stunde: Ortszeit mit Offset, vorhandene Rohfelder, Sonnenminuten."""
    from services.weather_metrics import WeatherMetricsService

    zeile: dict = {"zeit": local_dt(punkt.ts, zone).isoformat()}
    for feld in _ROHFELDER:
        inhalt = getattr(punkt, feld, None)
        if inhalt is not None:
            zeile[feld] = inhalt.value if isinstance(inhalt, Enum) else inhalt
    if punkt.dni_wm2 is not None:
        anteil = WeatherMetricsService.dni_to_sunny_fraction(punkt.dni_wm2, *band)
        zeile[_SONNENMINUTEN] = round(anteil * 60)
    return zeile


@router.get("/api/_internal/mcp/wetter")
def get_mcp_wetter(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    von: Optional[str] = Query(default=None, max_length=40),
    bis: Optional[str] = Query(default=None, max_length=40),
    # Issue #1991 (wie /forecast): optionaler Hoehen-Override; ohne Angabe
    # ermittelt Open-Meteo die Hoehe selbst aus dem DEM.
    elevation_m: Optional[int] = Query(default=None),
):
    from app.config import Location, Settings
    from providers.base import get_provider

    zone = tz_for_coords(lat, lon)
    start, ende, begrenzt = _zeitraum(von, bis, zone)
    try:
        reihe = get_provider("openmeteo").fetch_forecast(
            Location(latitude=lat, longitude=lon, elevation_m=elevation_m), start=start, end=ende,
            enrich_ensemble=False, enrich_snow=False,
        )
    except Exception as e:
        # Wie /forecast (#2961): Ausnahmetext nur ins Log, nach aussen Katalogtext.
        logger.warning("MCP-Wetterabruf fehlgeschlagen (%s): %s", type(e).__name__, e)  # i18n-log
        raise HTTPException(status_code=502, detail={
            "error": "provider_error",
            "detail": t("api.fehler.wetterdienst_fehler", "de"),
        }) from None

    settings = Settings()
    band = (settings.sunny_dni_min_wm2, settings.sunny_dni_max_wm2)
    stunden = [_stunde(p, zone, band) for p in reihe.data if start <= to_utc(p.ts) < ende]
    if not stunden:
        # Vergangenheit oder jenseits des Vorhersagehorizonts: Hinweis statt leerer Liste.
        raise api_fehler(422, "mcp_zeitraum_ausserhalb", None)
    return {
        "lat": lat, "lon": lon, "zeitzone": str(zone),
        "von": local_dt(start, zone).isoformat(), "bis": local_dt(ende, zone).isoformat(),
        "begrenzt": begrenzt, "einheiten": _einheiten(), "stunden": stunden,
    }
