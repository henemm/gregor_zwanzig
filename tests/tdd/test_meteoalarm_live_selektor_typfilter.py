"""Zonen-Auswahl der MeteoAlarm-Live-Tests waehlt nur Warntypen, die die App auswertet (Issue #2696).

SPEC: docs/specs/fast/fix-2696-meteoalarm-live-nebel.md (AC-1, AC-2, AC-3)

Netzfrei: Die Auswahl-Funktionen der drei Live-Test-Dateien laufen gegen einen Fixture-Feed. Nebel
(``4; Fog``) wird im Produktivcode bewusst verworfen (#1430); die Auswahl darf eine solche Zone nicht
als "gewarnt" melden, sonst meldet der Live-Test ein Rot, das es nicht gibt.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.official_alerts.meteoalarm import _DISCARDED_TYPES, _TYPE_HAZARD_MAP
from tests.tdd import test_meteoalarm_feed_es_live as es_live
from tests.tdd import test_meteoalarm_feed_nordics_live as nordics_live
from tests.tdd import test_meteoalarm_feed_pt_nl_pl_live as ptnlpl_live

JETZT = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
RING = "60.0,20.0 60.0,22.0 62.0,22.0 62.0,20.0 60.0,20.0"
ALLE_TYPEN = sorted(set(_TYPE_HAZARD_MAP) | set(_DISCARDED_TYPES))


def _feed(typ: int, geocode: str | None = None, polygon: str | None = None) -> dict:
    area: dict = {}
    if geocode:
        area["geocode"] = [{"valueName": "EMMA_ID", "value": geocode}]
    if polygon:
        area["polygon"] = [polygon]
    info = {
        "onset": (JETZT - timedelta(hours=1)).isoformat(),
        "expires": (JETZT + timedelta(hours=5)).isoformat(),
        "responseType": [],
        "parameter": [
            {"valueName": "awareness_level", "value": "2; yellow; Moderate"},
            {"valueName": "awareness_type", "value": f"{typ}; Typ"},
        ],
        "area": [area],
    }
    return {"warnings": [{"alert": {"msgType": "Alert", "info": [info]}}]}


def _es(typ: int) -> bool:
    zone = next(iter(es_live._PUNKTE))
    return bool(es_live._aktive_zonen(_feed(typ, geocode=zone), JETZT))


def _ptnlpl(land: str):
    def waehle(typ: int) -> bool:
        zone = next(iter(ptnlpl_live._PUNKTE[land]))
        return bool(ptnlpl_live._aktive_zonen(_feed(typ, geocode=zone), land, JETZT))
    return waehle


def _fi_geocode(typ: int) -> bool:
    return nordics_live._punkt_geocode(_feed(typ, geocode="FI029"), JETZT) is not None


def _polygon(typ: int) -> bool:
    return nordics_live._punkt_polygon(_feed(typ, polygon=RING), JETZT) is not None


WAEHLER = {
    "ES": _es,
    "PT": _ptnlpl("PT"),
    "NL": _ptnlpl("NL"),
    "PL": _ptnlpl("PL"),
    "FI-Geocode": _fi_geocode,
    "NO/SE-Polygon": _polygon,
}


@pytest.mark.parametrize("name", WAEHLER)
def test_ac1_nebel_zone_wird_nicht_gewaehlt(name):
    """AC-1: GIVEN einzige aktive Warnung ist ``4; Fog``, WHEN die Auswahl laeuft, THEN keine Zone."""
    assert 4 in _DISCARDED_TYPES
    assert WAEHLER[name](4) is False


@pytest.mark.parametrize("name", WAEHLER)
def test_ac2_wind_zone_wird_gewaehlt(name):
    """AC-2: GIVEN aktive Windwarnung (Typ 1), WHEN die Auswahl laeuft, THEN wird die Zone gewaehlt."""
    assert WAEHLER[name](1) is True


@pytest.mark.parametrize("name", WAEHLER)
@pytest.mark.parametrize("typ", ALLE_TYPEN)
def test_ac3_gewaehlt_wird_genau_was_die_app_auswertet(name, typ):
    """AC-3: gewaehlt genau dann, wenn der Typ in ``_TYPE_HAZARD_MAP`` steht (Liste aus Produktivcode)."""
    assert WAEHLER[name](typ) is (typ in _TYPE_HAZARD_MAP)
