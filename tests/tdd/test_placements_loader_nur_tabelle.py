"""Trip-Ladeweg: wann ``display_config`` "nur die Tabelle" ist (#3122 B2b).

SPEC: docs/specs/modules/feat_3122_was_steht_wo.md Teil A Nr. 1, 3.5, 9.

Nur ein ``display_config``, das ausschliesslich ein ``placements``-OBJEKT
traegt (so legt es der Go-PUT bei einem Trip ohne ``display_config`` an), gilt
wie ein fehlendes ``display_config`` (Profil-Default). Alles andere laedt wie
auf ``main``: ``placements`` kein Objekt = Register-Standard, ``placements`` im
Modell ``None``; ``{}``/``null`` = Register-Standard, ohne Fehler.

Kern-Schicht: echter Loader (``load_trip_from_dict`` = Parser von
``load_trip``), kein Mock.
"""
from __future__ import annotations

import pytest

BASIS = {"id": "t-nur", "name": "T", "stages": [{"id": "T1", "name": "E", "date": "2026-07-14",
         "waypoints": [{"id": "W1", "name": "S", "lat": 47.27, "lon": 11.40, "elevation_m": 600},
                       {"id": "W2", "name": "Z", "lat": 47.29, "lon": 11.42, "elevation_m": 900}]}]}
TABELLE = {"version": 1, "rows": [{"metric_id": "wind"}], "zukunft": 1}


def _laden(**extra):
    from app.loader import load_trip_from_dict

    return load_trip_from_dict({**BASIS, **extra}).display_config


def _aktiv(dc) -> list[str]:
    return [m.metric_id for m in dc.metrics if m.enabled]


def _register_standard() -> list[str]:
    """``display_config`` vorhanden, ohne ``metrics`` und ohne ``placements``."""
    return _aktiv(_laden(display_config={"show_night_block": True}))


def _profil_default() -> list[str]:
    return _aktiv(_laden())


def test_vorbedingung_die_zwei_standards_unterscheiden_sich():
    assert _register_standard() != _profil_default()


def test_nur_tabellen_objekt_gilt_wie_fehlendes_display_config():
    dc = _laden(display_config={"placements": TABELLE})
    assert _aktiv(dc) == _profil_default()
    assert dc.placements == TABELLE


@pytest.mark.parametrize("wert", [None, [], "x", 3, [{"metric_id": "wind"}]])
def test_placements_kein_objekt_ist_nicht_nur_tabelle(wert):
    dc = _laden(display_config={"placements": wert})
    assert _aktiv(dc) == _register_standard(), "wie auf main: Register-Standard"
    assert dc.placements is None


@pytest.mark.parametrize("roh", [{}, None])
def test_leeres_und_null_display_config_laden_wie_auf_main(roh):
    dc = _laden(display_config=roh)
    assert _aktiv(dc) == _register_standard()
    assert dc.placements is None


def test_tabelle_plus_weiteres_feld_ist_nicht_nur_tabelle():
    dc = _laden(display_config={"placements": TABELLE, "show_night_block": True})
    assert _aktiv(dc) == _register_standard()
    assert dc.placements == TABELLE
