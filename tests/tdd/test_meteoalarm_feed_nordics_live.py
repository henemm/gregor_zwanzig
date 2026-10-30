"""Live-Nachweis -- MeteoAlarm Skandinavien am ECHTEN Feed (Issue #1442 S2, AC-13 / Test 14).

SPEC: docs/specs/modules/feat_1442_s2_meteoalarm_nordics.md (AC-13)

Nur ``/e2e-verify`` bzw. Staging (Marker ``live``), nicht im Kern-Testlauf. Fuehrt ein Feed gerade
keine aktuell gueltige Warnung, ist das Ergebnis SKIP mit Grund, NICHT Bestehen -- eine leere
Liste besteht den Test nicht.

Norwegen/Schweden: Punkt im Polygon der aktuell gueltigen Warnung. Finnland: der Feed traegt keine
Polygone (nur ``EMMA_ID``) -- dort dienen feste Repraesentativpunkte der Zonen (``FI029`` Vaasa,
``FI032`` Turku, ``FI043`` Mariehamn, ``FI806`` vor Hanko).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.live

_FI_PUNKTE = {"FI029": (63.10, 21.62), "FI032": (60.45, 22.27), "FI043": (60.10, 19.94),
              "FI806": (59.70, 23.00)}


def _ring(text: str) -> list[tuple[float, float]]:
    return [tuple(map(float, p.split(","))) for p in text.split()]


def _innenpunkt(ring: list[tuple[float, float]]) -> "tuple[float, float] | None":
    """Ein Punkt sicher im Ring: Mittelpunkt, sonst Mittelpunkte der Kantenmitten zum Schwerpunkt."""
    def inside(lat: float, lon: float) -> bool:
        n, ins, j = len(ring), False, len(ring) - 1
        for i in range(n):
            yi, xi = ring[i]
            yj, xj = ring[j]
            if (xi > lon) != (xj > lon) and lat < (yj - yi) * (lon - xi) / (xj - xi) + yi:
                ins = not ins
            j = i
        return ins

    clat = sum(p[0] for p in ring) / len(ring)
    clon = sum(p[1] for p in ring) / len(ring)
    if inside(clat, clon):
        return clat, clon
    for lat, lon in ring[:: max(1, len(ring) // 50)]:
        cand = ((lat + clat) / 2, (lon + clon) / 2)
        if inside(*cand):
            return cand
    return None


def _aktiv(info: dict, jetzt: datetime) -> bool:
    if "AllClear" in (info.get("responseType") or []):
        return False
    try:
        if datetime.fromisoformat(info["expires"].replace("Z", "+00:00")) < jetzt:
            return False
        if datetime.fromisoformat(info["onset"].replace("Z", "+00:00")) > jetzt:
            return False
    except (KeyError, ValueError):
        return False
    level = next((p["value"] for p in info.get("parameter") or []
                  if p.get("valueName") == "awareness_level"), "0")
    return level.split(";")[0].strip().isdigit() and int(level.split(";")[0]) >= 2


def _punkt_polygon(feed: dict, jetzt: datetime):
    for w in feed.get("warnings") or []:
        alert = w.get("alert") or {}
        if alert.get("msgType") == "Cancel":
            continue
        for info in alert.get("info") or []:
            if not _aktiv(info, jetzt):
                continue
            areas = info.get("area") or []
            for area in areas if isinstance(areas, list) else [areas]:
                for poly in area.get("polygon") or []:
                    punkt = _innenpunkt(_ring(poly))
                    if punkt:
                        return punkt
    return None


def _punkt_geocode(feed: dict, jetzt: datetime):
    for w in feed.get("warnings") or []:
        alert = w.get("alert") or {}
        if alert.get("msgType") == "Cancel":
            continue
        for info in alert.get("info") or []:
            if not _aktiv(info, jetzt):
                continue
            areas = info.get("area") or []
            for area in areas if isinstance(areas, list) else [areas]:
                for g in area.get("geocode") or []:
                    if g.get("value") in _FI_PUNKTE:
                        return _FI_PUNKTE[g["value"]]
    return None


@pytest.mark.parametrize("land", ["NO", "SE", "FI"])
def test_ac13_echter_feed_liefert_warnung_fuer_gewarntes_gebiet(land):
    """AC-13: GIVEN der echte Feed des Landes fuehrt eine aktuell gueltige Warnung, WHEN die Quelle
    fuer einen Punkt in deren Gebiet abgefragt wird, THEN mindestens 1 Warnung, kein Ausfall."""
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource
    import services.official_alerts.base as oa_base

    meteoalarm_feed._cache.clear()
    feed = meteoalarm_feed._get_cached_feed(land)
    assert feed is not None, f"echter {land}-Feed nicht abrufbar"

    jetzt = datetime.now(timezone.utc)
    punkt = _punkt_geocode(feed, jetzt) if land == "FI" else _punkt_polygon(feed, jetzt)
    if punkt is None:
        pytest.skip(f"{land}-Feed fuehrt gerade keine aktuell gueltige Warnung -- kein Nachweis moeglich")

    quelle = MeteoAlarmFeedSource(land)
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES[:] = [quelle]
    try:
        alerts, unavailable = get_official_alerts_with_status(*punkt, now=jetzt)
    finally:
        oa_base._REGISTERED_SOURCES[:] = backup
    assert unavailable is False
    assert len(alerts) >= 1, f"mindestens 1 Warnung erwartet fuer {land} {punkt}"
