"""Live-Nachweis -- MeteoAlarm Spanien am ECHTEN Feed (Issue #1442 S3, AC-16 / Test 16).

SPEC: docs/specs/modules/feat_1442_s3_meteoalarm_spanien.md (AC-16)

Nur ``/e2e-verify`` (lokal; Staging blockt Warn-Hosts per Egress-Guard), Marker ``live``, nicht im
Kern-Testlauf. Fuehrt der Feed gerade keine aktuell gueltige Warnung der Stufe >= 2 fuer eine der
Repraesentativ-Zonen, ist das Ergebnis SKIP mit Grund, NICHT Bestehen.

Der Spanien-Feed traegt keine Polygone (nur ``EMMA_ID``): feste Repraesentativpunkte je Zone.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.official_alerts.meteoalarm import _TYPE_HAZARD_MAP, _leading_int

pytestmark = pytest.mark.live

_PUNKTE = {
    "ES114": (39.766, 2.715),    # Soller, Sierra Tramontana
    "ES115": (39.853, 3.121),    # Alcudia
    "ES116": (39.62, 2.90),      # Interior de Mallorca
    "ES117": (39.57, 2.65),      # Palma
    "ES118": (39.70, 3.35),      # Arta
    "ES113": (38.91, 1.43),      # Ibiza
    "ES219": (40.42, -3.70),     # Madrid
    "ES874": (39.50, 2.15),      # See vor Sa Dragonera
}


def _aktive_zonen(feed: dict, jetzt: datetime) -> list:
    treffer = []
    for w in feed.get("warnings") or []:
        alert = w.get("alert") or {}
        if alert.get("msgType") == "Cancel":
            continue
        infos = alert.get("info") or []
        for info in infos if isinstance(infos, list) else [infos]:
            if "AllClear" in (info.get("responseType") or []):
                continue
            try:
                if not (datetime.fromisoformat(info["onset"].replace("Z", "+00:00")) <= jetzt
                        <= datetime.fromisoformat(info["expires"].replace("Z", "+00:00"))):
                    continue
            except (KeyError, ValueError):
                continue
            level = next((p["value"] for p in info.get("parameter") or []
                          if p.get("valueName") == "awareness_level"), "0")
            if not level.split(";")[0].strip().isdigit() or int(level.split(";")[0]) < 2:
                continue
            # #2696: nur Warntypen, die die App auswertet (Nebel u. a. werden verworfen).
            typ = next((p.get("value") for p in info.get("parameter") or []
                        if p.get("valueName") == "awareness_type"), None)
            if _leading_int(typ) not in _TYPE_HAZARD_MAP:
                continue
            areas = info.get("area") or []
            for area in areas if isinstance(areas, list) else [areas]:
                geo = area.get("geocode") or []
                for g in geo if isinstance(geo, list) else [geo]:
                    if g.get("value") in _PUNKTE:
                        treffer.append(g["value"])
    return treffer


def test_ac16_echter_feed_liefert_warnung_fuer_gewarnte_zone():
    """AC-16: GIVEN der echte Spanien-Feed mit einer aktuell gewarnten Zone, WHEN die Quelle fuer
    einen Punkt dieser Zone abgefragt wird, THEN mindestens 1 Warnung, kein Ausfall."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    meteoalarm_feed._cache.clear()
    feed = meteoalarm_feed._get_cached_feed("ES")
    assert feed is not None, "echter ES-Feed nicht abrufbar"

    jetzt = datetime.now(timezone.utc)
    zonen = _aktive_zonen(feed, jetzt)
    if not zonen:
        pytest.skip("ES-Feed fuehrt gerade keine aktuell gueltige Warnung (>= gelb) fuer eine "
                    "Repraesentativ-Zone -- kein Nachweis moeglich")
    punkt = _PUNKTE[zonen[0]]

    quelle = MeteoAlarmFeedSource("ES")
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES[:] = [quelle]
    try:
        alerts, unavailable = get_official_alerts_with_status(*punkt, now=jetzt)
    finally:
        oa_base._REGISTERED_SOURCES[:] = backup
    assert unavailable is False
    assert len(alerts) >= 1, f"mindestens 1 Warnung erwartet fuer {zonen[0]} {punkt}"
