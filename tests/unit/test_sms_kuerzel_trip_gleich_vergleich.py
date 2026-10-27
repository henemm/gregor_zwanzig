"""Waechter (#2232, AC-3): dieselbe Wettergroesse traegt in der Trip-SMS und in
der Vergleichs-SMS DASSELBE Kuerzel.

SPEC: docs/specs/modules/fix_2232_kuerzel_ein_modell_trip_vergleich.md

Genau die Luecke, die ADR-0011 Nachtrag E7 (2026-08-15) bis heute ausdruecklich
erlaubte: Trip sendet ``L``/``D``/``FL``/``FD``, der Ortsvergleich sendete fuer
dieselben Groessen ``D-``/``D+``/``TF-``/``TF+``. Ab dieser Scheibe ist das ein
Pflicht-Gate.

Bauprinzip (wie ``test_sms_token_symbol_register_ratchet.py``): **kein Abtippen
erwarteter Kuerzel**. Der Test rendert beide Wege mit denselben Zahlen und
stellt die Ergebnisse GEGENEINANDER -- eine gemeinsame Fehlfarbe faellt damit
zwar nicht auf, eine Divergenz aber immer, und genau die ist der Pruefgegenstand.
Zwei Stichproben ausserhalb der Temperatur-Familie (Wind, Regen) sichern, dass
der Waechter nicht nur die vier umgebauten Groessen sieht.

Test-Politik (CLAUDE.md, Schicht "Kern"): deterministisch, kein Netz, kein
Mock/``patch()``, kein Versand.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from output.renderers import comparison as comparison_mod
from output.renderers.comparison import _sms_metric_cell
from output.tokens import builder as builder_mod
from output.tokens.builder import build_token_line
from output.tokens.dto import (
    DailyForecast, HourlyValue, MetricSpec, NormalizedForecast,
)

from app.user import LocationResult, SavedLocation

# Issue #1409: Prueflinge relativ zur eigenen Testdatei aufloesen -- sonst misst
# ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie und meldet falsches Gruen.
_REPO = Path(__file__).resolve().parents[2]

# Alle Trip-Token-Symbole, die der Builder unbedingt (auch ohne Wert) erzeugt.
# Sie werden je Fall bis auf EINES abgeschaltet, damit genau ein Token uebrig
# bleibt und die Zuordnung Groesse -> Kuerzel eindeutig ist. Ohne das
# verschmelzen ``L`` und ``D`` zum Bereichs-Token ``D9/24`` (#1824 A).
_TRIP_SYMBOLS = ("N", "L", "D", "FN", "FL", "FD", "R", "PR", "W", "G", "TH:")

# (Fallname, Trip-Feld+Wert fuer DailyForecast, Compare-Renderer-ID,
#  LocationResult-Feld+Wert). BEIDE Seiten bekommen dieselbe Zahl -- der Wert
#  ist hier nicht der Pruefgegenstand, aber ein abweichender Wert wuerde einen
#  Formatierungsunterschied als Kuerzelunterschied tarnen.
_FAELLE = [
    ("Tages-Hoechsttemperatur", {"temp_max_c": 24.0}, "temp_max", {"temp_max": 24.0}),
    ("Tages-Tiefsttemperatur", {"temp_min_c": 9.0}, "temp_min", {"temp_min": 9.0}),
    ("gefuehlte Tages-Hoechsttemperatur",
     {"wind_chill_max_c": 21.0}, "wind_chill_max", {"wind_chill_max": 21.0}),
    ("gefuehlte Tages-Tiefsttemperatur",
     {"wind_chill_min_c": 7.0}, "wind_chill_min", {"wind_chill_min": 7.0}),
    # Zwei Stichproben AUSSERHALB der Temperatur-Familie: sie waren nie
    # verschieden und muessen es bleiben -- sonst prueft dieser Waechter nur
    # die vier Groessen, die diese Scheibe ohnehin anfasst.
    ("Wind", {"wind_hourly": (HourlyValue(12, 15),)}, "wind_max", {"wind_max": 15.0}),
    ("Niederschlag",
     {"rain_hourly": (HourlyValue(12, 3.0),)}, "precip_sum", {"precip_sum_mm": 3.0}),
]


def _trip_kuerzel_ermitteln(trip_feld: dict) -> str:
    """Probiert jedes Trip-Symbol einzeln durch und liefert das eine, das mit
    DIESEM Feld einen Token erzeugt. Bewusst abgetastet statt getippt (Muster
    ``test_sms_token_symbol_register_ratchet.py`` Bauprinzip 2): eine
    Umbenennung im Builder faellt hier auf, statt still mitzuwandern."""
    treffer = []
    for symbol in _TRIP_SYMBOLS:
        forecast = NormalizedForecast(days=(DailyForecast(**trip_feld),))
        tokens = [
            t for t in build_token_line(
                forecast,
                [MetricSpec(symbol=s, enabled=s == symbol) for s in _TRIP_SYMBOLS],
                report_type="morning", stage_name="E1",
            ).tokens
            if t.category == "forecast" and t.value not in ("-", "?")
        ]
        if tokens:
            treffer.append(tokens[0].symbol.rstrip(":"))
    assert len(treffer) == 1, (
        f"Testaufbau: {trip_feld!r} erzeugt {treffer!r} statt genau eines "
        "Trip-Kuerzels."
    )
    return treffer[0]


def _vergleich_kuerzel(renderer_id: str, loc_feld: dict) -> str:
    """Das Kuerzel, das die VERGLEICHS-SMS fuer dieselbe Groesse sendet --
    aus der echten Zellenerzeugung, nicht aus einer Nachbildung."""
    loc = LocationResult(
        location=SavedLocation(id="a", name="Andermatt", lat=47.0, lon=11.0,
                               elevation_m=600),
        **loc_feld,
    )
    zelle = _sms_metric_cell(loc, renderer_id)
    assert zelle, (
        f"Testaufbau: der Ortsvergleich rendert fuer {renderer_id!r} keine "
        "SMS-Zelle (kein Wert oder kein Kuerzel)."
    )
    return zelle.split(" ", 1)[0]


def test_waechter_prueft_den_code_dieses_arbeitsbaums():
    """#1409: beide Prueflinge muessen aus DIESEM Arbeitsbaum stammen."""
    for modul in (builder_mod, comparison_mod):
        pfad = Path(modul.__file__).resolve()
        assert str(pfad).startswith(str(_REPO)), (
            f"Der Waechter prueft nicht den Code dieses Arbeitsbaums, sondern "
            f"{pfad} (erwartet unterhalb {_REPO})."
        )


@pytest.mark.parametrize(
    "name,trip_feld,renderer_id,loc_feld",
    _FAELLE, ids=[f[0] for f in _FAELLE],
)
def test_trip_und_vergleich_senden_dasselbe_kuerzel(
    name: str, trip_feld: dict, renderer_id: str, loc_feld: dict,
):
    """AC-3: Trip-Token-Kuerzel == Vergleichs-Zellen-Kuerzel, je Groesse.

    Ist-Zustand vor dieser Scheibe: Trip ``D``/``L``/``FD``/``FL`` gegen
    Vergleich ``D+``/``D-``/``TF+``/``TF-`` -- vier von sechs Faellen rot.
    """
    trip = _trip_kuerzel_ermitteln(trip_feld)
    vergleich = _vergleich_kuerzel(renderer_id, loc_feld)
    assert trip == vergleich, (
        f"{name}: die Trip-SMS sendet {trip!r}, die Vergleichs-SMS "
        f"{vergleich!r} -- dieselbe Wettergroesse traegt auf zwei Kanaelen "
        "zwei Kuerzel. Der Empfaenger kann sie nicht als dieselbe Groesse "
        "erkennen (#2232; ADR-0011 Nachtrag E7 erlaubte das bis 2026-09-09)."
    )


@pytest.mark.parametrize(
    "renderer_id,loc_feld,trip_feld,eltern_kennung",
    [
        ("temp_min", {"temp_min": 9.0}, {"temp_min_c": 9.0}, "temperature"),
        ("wind_chill_max", {"wind_chill_max": 21.0}, {"wind_chill_max_c": 21.0},
         "wind_chill"),
    ],
    ids=["Tagestiefst -> temperature", "gefuehlt Hoechst -> wind_chill"],
)
def test_der_waechter_faengt_eine_verfaelschte_kuerzel_aufloesung(
    renderer_id: str, loc_feld: dict, trip_feld: dict, eltern_kennung: str,
):
    """Gegenprobe (Mutations-Nachweis): biegt man die Kuerzel-Aufloesung auf die
    ELTERN-Groesse zurueck -- also auf den Stand vor #2232 --, MUSS der
    Waechter oben anschlagen.

    Ohne diese Gegenprobe waere nicht belegt, dass er ueberhaupt etwas bewacht;
    er koennte auch nur zwei gleich falsche Werte vergleichen. Gemessen wird an
    den beiden Groessen, deren Eltern-Kuerzel sich vom Kind-Kuerzel
    UNTERSCHEIDET (`temperature`->`D` statt `L`, `wind_chill`->`TF` statt `FD`)
    -- bei `temp_max` waeren beide zufaellig `D` und die Gegenprobe blind.

    Die echte Tabelle bleibt unberuehrt: Kopie, danach wiederhergestellt (kein
    `git checkout`, kein Monkeypatch-Modul)."""
    original = dict(comparison_mod._RENDERER_TO_CATALOG_METRIC_ID)
    try:
        comparison_mod._RENDERER_TO_CATALOG_METRIC_ID[renderer_id] = eltern_kennung
        verfaelscht = _vergleich_kuerzel(renderer_id, loc_feld)
    finally:
        comparison_mod._RENDERER_TO_CATALOG_METRIC_ID.clear()
        comparison_mod._RENDERER_TO_CATALOG_METRIC_ID.update(original)

    trip = _trip_kuerzel_ermitteln(trip_feld)
    assert verfaelscht != trip, (
        f"Die Gegenprobe ueber {eltern_kennung!r} erzeugt dasselbe Kuerzel wie "
        f"der Trip (beide {trip!r}) -- der Waechter kann eine falsche "
        "Kuerzel-Aufloesung dann nicht von einer richtigen unterscheiden."
    )
    # Und die echte Tabelle ist wiederhergestellt.
    assert _vergleich_kuerzel(renderer_id, loc_feld) == trip
