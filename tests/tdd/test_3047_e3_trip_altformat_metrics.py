"""Issue #3047 Runde 7, Befund E3 (hoch): Trip-Altformat in ``display_config.metrics[]``.

SPEC: docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md
(§2 Punkt 8 Altbestand; CLAUDE.md „Bestandsdaten bleiben erhalten").

Kette aus Nutzersicht: rohes Trip-JSON -> echter Loader -> Kaskade ->
Renderer -> Versandweg; gelesen wird die aufgezeichnete Mail.

* Das Altformat (Zeichenkette ``"wind"``, Objekt ohne ``enabled``) und die
  Nutzlast, die der Reiter Wetter nach dem Fix schreibt (nur Objekte mit
  ``metric_id``), zeigen dieselben Spalten: Wind und Boeen, keine Temperatur.
* Ein einzelner Eintrag ohne ``metric_id`` (frueher im Browser gespreizte
  Zeichenkette ``{"0":"w",...}``) traegt keine Groesse: der Loader verwirft
  NUR diesen Eintrag (mit Warnung), nicht den ganzen Trip -- sonst fallen
  Briefings und Alarme fuer den Trip still weg.

Kein ``Mock()``/``patch()``/``MagicMock``; einzige Naht ist der Transport.
Die ``user_id`` ist die eines frischen Profils, nie ``"default"``.
"""
from __future__ import annotations

import logging

from tests.helpers.einstellung_gleich_mail_trip import html_tabellen
from tests.tdd._einstellung_gleich_mail_trip_fixtures import (
    mail_teile, render_trip_mit_ausblick, trip_json,
)

#: So schreibt der Reiter Wetter den Altbestand nach dem Fix (Frontend-Test
#: ``e3_trip_altformat_metrics.test.ts``).
NACH_FIX = [
    {"metric_id": "wind", "enabled": True},
    {"metric_id": "gust", "bucket": "primary", "order": 1, "enabled": True},
    {"metric_id": "temperature", "enabled": False},
]
ALTFORMAT = ["wind", {"metric_id": "gust", "bucket": "primary", "order": 1},
             {"metric_id": "temperature", "enabled": False}]
GESPREIZT = {"0": "w", "1": "i", "2": "n", "3": "d", "enabled": False}


def _trip(metrics: list) -> dict:
    data = trip_json(["wind", "gust"])
    data["display_config"]["metrics"] = metrics
    return data


def _etappen_spalten(monkeypatch, metrics: list) -> list[list[str]]:
    mitschrift, _geladen, _uid = render_trip_mit_ausblick(monkeypatch, _trip(metrics), mit_ausblick=False)
    html, _text = mail_teile(mitschrift)
    assert html, "Vollformat ohne HTML-Teil"
    tabellen = html_tabellen(html)["etappe"]
    assert tabellen, "Etappen-Stundentabelle fehlt"
    return [t.spalten for t in tabellen]


def _pruefe_wind_boeen(spalten: list[list[str]], wo: str) -> None:
    for s in spalten:
        assert "wind" in s and "gust" in s, f"{wo}: Wind/Boeen fehlen in {s}"
        assert "temperature" not in s, f"{wo}: abgewaehlte Temperatur in {s}"


def test_nach_fix_gespeicherter_trip_zeigt_wind_und_boeen(monkeypatch):
    _pruefe_wind_boeen(_etappen_spalten(monkeypatch, NACH_FIX), "nach Fix")


def test_altformat_und_fix_nutzlast_zeigen_dieselben_spalten(monkeypatch):
    alt = _etappen_spalten(monkeypatch, ALTFORMAT)
    _pruefe_wind_boeen(alt, "Altformat")
    assert alt == _etappen_spalten(monkeypatch, NACH_FIX), "Speichern im Reiter aendert die Mail"


def test_kaputter_eintrag_verwirft_nur_den_eintrag_nicht_den_trip(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="app.loader"):
        spalten = _etappen_spalten(monkeypatch, [*NACH_FIX, GESPREIZT])
    _pruefe_wind_boeen(spalten, "mit kaputtem Eintrag")
    assert spalten == _etappen_spalten(monkeypatch, NACH_FIX)
    assert any("metric_id" in r.getMessage() for r in caplog.records), "keine Warnung zum verworfenen Eintrag"
