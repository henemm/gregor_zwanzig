"""Live-Nachweis -- MeteoAlarm Belgien am ECHTEN Feed (Issue #1442 S3c, AC-16 / Test 16).

SPEC: docs/specs/modules/feat_1442_s3c_meteoalarm_be.md (AC-16)

Nur ``/e2e-verify`` (Marker ``live``), nicht im Kern-Testlauf. Fuehrt der Feed gerade keine aktuell
gueltige, von der App auswertbare Warnung, ist das Ergebnis SKIP mit Grund, NICHT Bestehen.
Bekannt (#2696): reine Nebelwarnungen waehlt der Selektor nicht als "gewarntes Gebiet" (der geteilte
Mapper verwirft Nebel bewusst, #1430).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.live

# Repraesentativer Punkt je Kennung (EMMA-Zone bzw. ueber die Tabelle uebersetzte NUTS2-Provinz).
_PUNKT_JE_EMMA = {
    "BE001": (49.68, 5.81), "BE002": (51.22, 4.40), "BE003": (51.05, 3.72), "BE004": (50.85, 4.35),
    "BE005": (50.45, 3.95), "BE006": (50.47, 4.87), "BE007": (50.93, 5.34), "BE008": (50.63, 5.57),
    "BE009": (51.21, 3.22), "BE801": (51.23, 2.92),
}


def _auswertbar(alert: dict, jetzt: datetime) -> bool:
    for info in alert.get("info") or []:
        params = {p["valueName"]: p["value"] for p in info.get("parameter") or []}
        stufe = str(params.get("awareness_level", "")).split(";")[0].strip()
        art = str(params.get("awareness_type", "")).split(";")[0].strip()
        if stufe in ("", "1") or art == "4":  # gruen und Nebel verwirft der Mapper
            continue
        von = datetime.fromisoformat(info["onset"]).astimezone(timezone.utc)
        bis = datetime.fromisoformat(info["expires"]).astimezone(timezone.utc)
        if von <= jetzt < bis:
            return True
    return False


def _punkt(feed: dict, jetzt: datetime):
    from services.official_alerts import meteoalarm_feed

    for w in feed.get("warnings") or []:
        alert = w.get("alert") or {}
        if alert.get("msgType") == "Cancel" or not _auswertbar(alert, jetzt):
            continue
        for info in alert.get("info") or []:
            for area in info.get("area") or []:
                for g in area.get("geocode") or []:
                    emma = meteoalarm_feed._BE_NUTS2_TO_EMMA.get(g["value"], g["value"]) \
                        if g["valueName"] == "NUTS2" else g["value"]
                    if emma in _PUNKT_JE_EMMA:
                        return _PUNKT_JE_EMMA[emma]
    return None


def test_ac16_echter_feed_liefert_warnung_fuer_gewarntes_gebiet():
    """AC-16: GIVEN der echte BE-Feed fuehrt eine aktuell gueltige, auswertbare Warnung, WHEN die Quelle
    fuer einen Punkt in deren Gebiet abgefragt wird, THEN mindestens 1 Warnung, kein Ausfall."""
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource
    import services.official_alerts.base as oa_base

    assert "BE" in meteoalarm_feed._FEED_PATHS, "BE-Quelle nicht eingerichtet"
    meteoalarm_feed._cache.clear()
    feed = meteoalarm_feed._get_cached_feed("BE")
    assert feed is not None, "echter BE-Feed nicht abrufbar"

    jetzt = datetime.now(timezone.utc)
    punkt = _punkt(feed, jetzt)
    if punkt is None:
        pytest.skip("BE-Feed fuehrt gerade keine aktuell gueltige, auswertbare Warnung -- kein Nachweis moeglich")

    quelle = MeteoAlarmFeedSource("BE")
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES[:] = [quelle]
    try:
        alerts, unavailable = get_official_alerts_with_status(*punkt, now=jetzt)
    finally:
        oa_base._REGISTERED_SOURCES[:] = backup
    assert unavailable is False
    assert len(alerts) >= 1, f"mindestens 1 Warnung erwartet fuer BE {punkt}"
