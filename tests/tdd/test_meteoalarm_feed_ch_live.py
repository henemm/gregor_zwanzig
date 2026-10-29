"""Live-Nachweis -- MeteoAlarm Schweiz am ECHTEN Feed (Issue #1442 S1, AC-11 / Test 12).

SPEC: docs/specs/modules/feat_1442_s1_meteoalarm_ch.md (AC-11)

Nur ``/e2e-verify`` bzw. Staging (Marker ``live``), nicht im Kern-Testlauf. Ein leerer Feed (gerade
keine aktuell gueltige Warnung) ist SKIP mit Grund, NICHT Bestehen -- eine leere Liste besteht den
Test nicht.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.live


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


def test_ac11_echter_ch_feed_liefert_warnung_fuer_gewarnte_gemeinde():
    """AC-11: GIVEN der echte CH-Feed fuehrt eine aktuell gueltige Warnung, WHEN die Quelle fuer
    einen Punkt in deren Polygon abgefragt wird, THEN mindestens 1 Warnung, kein Ausfall."""
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    meteoalarm_feed._cache.clear()
    feed = meteoalarm_feed._get_cached_feed("CH")
    assert feed is not None, "echter CH-Feed nicht abrufbar"

    jetzt = datetime.now(timezone.utc)
    punkt = None
    for w in feed.get("warnings") or []:
        alert = w.get("alert") or {}
        if alert.get("msgType") == "Cancel":
            continue
        for info in alert.get("info") or []:
            if not str(info.get("language", "")).lower().startswith("de"):
                continue
            expires = info.get("expires")
            try:
                if expires and datetime.fromisoformat(expires.replace("Z", "+00:00")) < jetzt:
                    continue
            except ValueError:
                continue
            if "AllClear" in (info.get("responseType") or []):
                continue
            for area in info.get("area") or []:
                for poly in area.get("polygon") or []:
                    punkt = _innenpunkt(_ring(poly))
                    if punkt:
                        break
                if punkt:
                    break
            if punkt:
                break
        if punkt:
            break
    if punkt is None:
        pytest.skip("CH-Feed fuehrt gerade keine aktuell gueltige Warnung -- kein Nachweis moeglich")

    ch = MeteoAlarmFeedSource("CH")
    import services.official_alerts.base as oa_base

    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES[:] = [ch]
    try:
        alerts, unavailable = get_official_alerts_with_status(*punkt, now=jetzt)
    finally:
        oa_base._REGISTERED_SOURCES[:] = backup
    assert unavailable is False
    assert len(alerts) >= 1, f"mindestens 1 Warnung erwartet fuer {punkt}"
