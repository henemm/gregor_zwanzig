"""TDD RED — #1457 S2c AC-4: eigenes, HERGELEITETES Zeitbudget fuer ICON-EU.

Spec: docs/specs/modules/feat_1457_s2c_icon_eu_luekenfueller.md (AC-4)

Vermessung und Testart: siehe Modul-Docstring von
`tests/tdd/_dwd_eu_fixtures.py` (Punkt 6: gemessene Latenz je Datei ~0,085 s
aus 0,043-0,069 s Download plus 0,035 s bz2/rasterio-Auswertung).

RED-GRUND: `providers.dwd_eu` existiert nicht -> ModuleNotFoundError.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from providers import dwd, meteofrance  # noqa: E402
from providers import openmeteo as om  # noqa: E402
from tests.tdd._dwd_eu_fixtures import (  # noqa: E402
    ABRUZZEN, dwd_eu, eu_server, hauptquelle_laeuft,
)

import pytest  # noqa: E402

# Live-Schicht (Test-Politik, CLAUDE.md): braucht echtes Netz/echte Dienste --
# lief im Kern nie gruen (CI-Vermessung 2026-08-04, #1196) und gehoert per
# Marker in den /e2e-verify-Lauf, nicht auf eine Ausnahmeliste.
pytestmark = pytest.mark.live


# Volles Vorhersagefenster (24 h, deckungsgleich mit `dwd_eu.FORECAST_HOURS`).
# NICHT beliebig kuerzbar: der Anschluss leitet das Abruffenster aus der Reihe
# ab, eine kurze Reihe deckelt die Abrufzahl also selbst — dann prueft der Test
# die Fixture statt der Zeitgrenze (Adversary F003, Runde 2). Die Vergleichs-
# messung unten haelt genau das offen.
_VOLLES_FENSTER_H = 24
_ABRUF_SCHWELLE = 8


def test_ac4_erschoepftes_gewitterbudget_bricht_nur_die_anreicherung_ab(monkeypatch):
    """AC-4: Given ein langsamer ICON-EU-Dienst und ein klein gesetztes
    Gewitter-Zeitbudget, When eine Vorhersage ueber den regulaeren Weg geholt
    wird, Then bricht NUR die Anreicherung nach wenigen Abrufen ab und die
    Grundvorhersage kommt vollstaendig.

    Gezaehlt werden ABRUFE, nicht Laufzeit — ein Laufzeit-Test misst die
    Maschine, nicht die Zeitgrenze (Projektlehre). Ohne eigene Zeitgrenze
    liefe der Gewitter-Abruf ueber alle Zeitschritte durch und dehnte jeden
    Vorhersage-Abruf entsprechend.

    Zwei Laeufe ueber denselben regulaeren Weg, damit die Zahl etwas BEDEUTET:
    zuerst mit grosszuegigem Budget und schnellem Dienst — das ergibt die
    natuerliche Obergrenze des Fensters —, dann mit kleiner Zeitgrenze gegen
    einen langsamen Dienst. Nur der Unterschied zwischen beiden belegt, dass
    die Zeitgrenze abbricht; eine feste Schwelle allein waere schon durch die
    Fixture erfuellt und bliebe auch bei abgeschalteter Zeitgrenze gruen
    (genau dieser Fehler war Adversary-Befund F003).
    """
    with hauptquelle_laeuft(monkeypatch, ABRUZZEN, stunden=_VOLLES_FENSTER_H):
        monkeypatch.setattr(dwd_eu(), "THUNDER_FETCH_DEADLINE_SECONDS", 60.0)
        with eu_server(monkeypatch) as schnell:
            om.OpenMeteoProvider().fetch_forecast(ABRUZZEN, enrich_ensemble=False)
            ohne_zeitdruck = len(schnell.abrufe)

        monkeypatch.setattr(dwd_eu(), "THUNDER_FETCH_DEADLINE_SECONDS", 0.4)
        with eu_server(monkeypatch, verzoegerung_s=0.15) as langsam:
            reihe = om.OpenMeteoProvider().fetch_forecast(
                ABRUZZEN, enrich_ensemble=False
            )
            abrufe = len(langsam.abrufe)

    assert ohne_zeitdruck > _ABRUF_SCHWELLE, (
        f"Ohne Zeitdruck kamen nur {ohne_zeitdruck} Abrufe zustande — die "
        f"Fixture deckelt schon unterhalb der Schwelle ({_ABRUF_SCHWELLE}). "
        "Dann kann dieser Test die Zeitgrenze nicht mehr nachweisen, egal wie "
        "die Assertionen unten ausfallen"
    )
    assert reihe.data, "Die Vorhersage ist leer — der Abbruch hat sie mitgerissen"
    assert any(dp.t2m_c is not None for dp in reihe.data), (
        "Temperatur fehlt — die Grundvorhersage wurde vom Gewitter-Abbruch "
        "beschaedigt, obwohl sie ihr eigenes Budget hat"
    )
    assert abrufe >= 1, "Es wurde gar nicht abgerufen — nichts geprueft"
    assert abrufe < ohne_zeitdruck, (
        f"Mit Zeitgrenze kamen genauso viele Abrufe ({abrufe}) zustande wie "
        f"ohne ({ohne_zeitdruck}) — die Zeitgrenze bricht nichts ab"
    )
    assert abrufe <= _ABRUF_SCHWELLE, (
        f"{abrufe} Abrufe bei einem Budget von 0,4 s und 0,15 s je Abruf — die "
        "Zeitgrenze greift nicht"
    )


def test_ac4_das_budget_ist_hergeleitet_und_nicht_von_den_nachbarn_uebernommen():
    """AC-4, Herleitungs-Haelfte: Given die gemessene Abrufzahl von ICON-EU
    (EIN Signal, kein Hagel, kein Kumulations-Anker — also hoechstens die
    Haelfte der ICON-D2-Abrufe), When das eigene Zeitbudget festgelegt wird,
    Then ist es kleiner als das von ICON-D2 und weder mit diesem noch mit dem
    von Meteo-France identisch.

    Beide Nachbarwerte (90 s fuer bis zu 48 ICON-D2-Abrufe, 45 s fuer 24
    Meteo-France-Abrufe) waeren bequem zu uebernehmen. Genau das verbietet die
    Spec: die Zahl muss aus der eigenen Abrufzahl mal der eigenen gemessenen
    Latenz kommen. Dieser Waechter kann eine falsche Herleitung nicht
    beweisen, aber die beiden naheliegenden Kopien ausschliessen.
    """
    eigen = dwd_eu().THUNDER_FETCH_DEADLINE_SECONDS
    assert isinstance(eigen, (int, float)) and eigen > 0, (
        f"Das Gewitter-Zeitbudget ist {eigen!r} — kein brauchbarer Wert"
    )
    assert len(tuple(dwd_eu().THUNDER_PARAMS)) == 1, (
        f"ICON-EU liefert gemessen genau EIN Gewittersignal, der Provider "
        f"fuehrt aber {tuple(dwd_eu().THUNDER_PARAMS)} — dann traegt die "
        "Herleitung 'halb so viele Abrufe wie ICON-D2' nicht mehr"
    )
    assert eigen != dwd.THUNDER_FETCH_DEADLINE_SECONDS, (
        f"Das Budget ist mit {eigen} identisch zu ICON-D2 — uebernommen statt "
        "hergeleitet"
    )
    assert eigen != meteofrance.THUNDER_FETCH_DEADLINE_SECONDS, (
        f"Das Budget ist mit {eigen} identisch zu Meteo-France — uebernommen "
        "statt hergeleitet"
    )
    assert eigen < dwd.THUNDER_FETCH_DEADLINE_SECONDS, (
        f"Das Budget ({eigen} s) ist nicht kleiner als das von ICON-D2 "
        f"({dwd.THUNDER_FETCH_DEADLINE_SECONDS} s), obwohl ICON-EU hoechstens "
        "halb so viele Dateien holt"
    )
