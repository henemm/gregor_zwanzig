"""Live-Nachweis -- MeteoAlarm Portugal, Niederlande, Polen am ECHTEN Feed (Issue #1442 S3a, AC-14 /
Test 16).

SPEC: docs/specs/modules/feat_1442_s3a_meteoalarm_pt_nl_pl.md (AC-14)

Nur ``/e2e-verify`` (lokal; Staging blockt Warn-Hosts per Egress-Guard), Marker ``live``, nicht im
Kern-Testlauf. Fuehrt ein Feed gerade keine aktuell gueltige Warnung der Stufe >= 2 fuer eine
Zone mit Repraesentativpunkt, ist das Ergebnis fuer dieses Land SKIP mit Grund, NICHT Bestehen.

Die drei Feeds tragen keine Polygone (nur ``EMMA_ID``): feste Repraesentativpunkte je Zone.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.live

_PUNKTE = {
    "PT": {
        "PT001": (39.45, -31.20),   # Azoren West (Flores)
        "PT002": (38.53, -28.45),   # Azoren Mitte (Faial)
        "PT003": (37.75, -25.65),   # Azoren Ost (São Miguel)
        "PT009": (41.15, -8.61),    # Porto
        "PT016": (38.72, -9.14),    # Lissabon
        "PT021": (37.02, -7.93),    # Faro
        "PT023": (32.75, -16.95),   # Madeira Bergland
        "PT024": (32.65, -16.91),   # Madeira Südküste (Funchal)
    },
    "NL": {
        "NL011": (52.37, 4.90),     # Amsterdam
        "NL009": (52.08, 4.30),     # Den Haag
        "NL012": (50.85, 5.69),     # Maastricht
        "NL013": (51.69, 5.30),     # 's-Hertogenbosch
        "NL007": (53.22, 6.57),     # Groningen
        "NL019": (53.40, 5.35),     # Terschelling
        "NL806": (53.36, 5.22),     # West-Terschelling (Waddenzee)
    },
    "PL": {
        "PL1465": (52.23, 21.01),   # Warschau
        "PL1261": (50.06, 19.94),   # Krakau
        "PL1217": (49.30, 19.95),   # Zakopane
        "PL2261": (54.35, 18.65),   # Danzig
        "PL3262": (53.43, 14.55),   # Stettin
        "PL0264": (51.11, 17.03),   # Breslau
        "PL3064": (52.41, 16.93),   # Posen
    },
}


def _aktive_zonen(feed: dict, land: str, jetzt: datetime) -> list:
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
            areas = info.get("area") or []
            for area in areas if isinstance(areas, list) else [areas]:
                geo = area.get("geocode") or []
                for g in geo if isinstance(geo, list) else [geo]:
                    if g.get("value") in _PUNKTE[land]:
                        treffer.append(g["value"])
    return treffer


@pytest.mark.parametrize("land", ["PT", "NL", "PL"])
def test_ac14_echter_feed_liefert_warnung_fuer_gewarnte_zone(land):
    """AC-14: GIVEN der echte Feed des Landes mit einer aktuell gewarnten Zone, WHEN die Quelle fuer
    einen Punkt dieser Zone abgefragt wird, THEN mindestens 1 Warnung, kein Ausfall."""
    import services.official_alerts.base as oa_base
    from services.official_alerts import get_official_alerts_with_status, meteoalarm_feed
    from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource

    meteoalarm_feed._cache.clear()
    # Zeitpruefung VOR dem SKIP-Zweig: der echte Netzabruf passiert HIER (danach Cache-Treffer),
    # ein langsamer Abruf darf nie als SKIP durchgehen. +5 s Marge fuer das Parsen (NL ~1,4 MB).
    start = time.monotonic()
    feed = meteoalarm_feed._get_cached_feed(land)
    dauer = time.monotonic() - start
    assert feed is not None, f"echter {land}-Feed nicht abrufbar"
    assert dauer <= meteoalarm_feed.TIMEOUT + 5, f"{land}-Feedabruf zu langsam: {dauer:.1f} s"

    jetzt = datetime.now(timezone.utc)
    zonen = _aktive_zonen(feed, land, jetzt)
    if not zonen:
        pytest.skip(f"{land}-Feed fuehrt gerade keine aktuell gueltige Warnung (>= gelb) fuer eine "
                    "Repraesentativ-Zone -- kein Nachweis moeglich")
    punkt = _PUNKTE[land][zonen[0]]

    quelle = MeteoAlarmFeedSource(land)
    backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES[:] = [quelle]
    start = time.monotonic()
    try:
        alerts, unavailable = get_official_alerts_with_status(*punkt, now=jetzt)
    finally:
        oa_base._REGISTERED_SOURCES[:] = backup
    dauer = time.monotonic() - start
    # +5 s Marge fuer das Parsen ueber dem Abruf-Timeout.
    assert dauer <= meteoalarm_feed.TIMEOUT + 5, f"{land}-Abfrage zu langsam: {dauer:.1f} s"
    assert unavailable is False
    assert len(alerts) >= 1, f"mindestens 1 Warnung erwartet fuer {zonen[0]} {punkt}"
