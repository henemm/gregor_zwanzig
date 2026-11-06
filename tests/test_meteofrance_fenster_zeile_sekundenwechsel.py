"""TDD RED — Issue #2771 (Epic #1196): der warme Abruf des
Météo-France-Zwischenspeichers darf nicht an einem Sekundenwechsel scheitern.

Nutzersicht (Entwickler/CI): der Kerntest
``test_meteofrance_fenster_zeile.py::test_ac14_warmer_abruf_aus_dem_zwischenspeicher_hat_null_downloads``
wird zufaellig rot. Ursache: der Test-Helfer ``_abruf`` bildet bei JEDEM
Aufruf ``start = datetime.now(timezone.utc)`` mit Sekunden. Der Cache-Schluessel
des Providers enthaelt die Sekunden (``src/providers/meteofrance.py``); faellt
zwischen erstem und zweitem Abruf ein Sekundenwechsel, geht der "warme"
Abruf doch ans Netz. Produktiv tritt das nicht auf, weil
``thunder_enrichment._bezugszeitpunkt`` auf die volle Stunde kuerzt.

Dieser Test faehrt den AC-14-Ablauf ueber denselben Helfer ``_abruf`` (ohne
eigenen Bezugszeitpunkt, wie die Bestandsaufrufer) und erzwingt den
Sekundenwechsel, indem er zwischen beiden Abrufen bis zum naechsten
Sekundenbeginn wartet (<= 1 s).

RED-Grund heute: der zweite Abruf geht nach dem Sekundenwechsel ans Netz.
GREEN nach Fix: ``_abruf`` nimmt ``start`` als Parameter; ohne Angabe gilt die
volle Stunde (spiegelt ``_bezugszeitpunkt``). Kein Netz, kein Mock.
"""
from __future__ import annotations

import logging
import time

from providers import meteofrance as mf
from tests.test_meteofrance_fenster_zeile import (  # noqa: F401  (mf_ok = Fixture)
    _abruf,
    _fenster_zeilen,
    mf_ok,
)


def _bis_zum_naechsten_sekundenbeginn() -> None:
    jetzt = time.time()
    time.sleep(1.0 - (jetzt - int(jetzt)) + 0.02)


def _nicht_kurz_vor_der_vollen_stunde() -> None:
    """Liegt der Start in den letzten 3 s einer Stunde, bis ueber die volle
    Stunde warten -- sonst traefe der erzwungene Wechsel auch die Stunde."""
    rest = 3600 - (time.time() % 3600)
    if rest < 3.0:
        time.sleep(rest + 0.05)


def test_warmer_abruf_ueber_einen_sekundenwechsel_hat_null_downloads(mf_ok, caplog):  # noqa: F811
    """AC-2 (#2771): GIVEN ein Meteo-France-Provider mit gefuelltem
    Zwischenspeicher nach dem ersten Abruf
    WHEN zwischen erstem und zweitem Abruf ein Sekundenwechsel erzwungen wird
    THEN hat der warme Abruf null Downloads und die Fensterzeile lautet
    ``(0, geladen)``."""
    _nicht_kurz_vor_der_vollen_stunde()
    provider = mf.MeteoFranceDirectProvider()
    _abruf(provider)
    geladen = len(mf_ok)
    assert geladen, "kein Meteo-France-Abruf -- Ort nicht zustaendig?"

    _bis_zum_naechsten_sekundenbeginn()
    caplog.clear()
    caplog.set_level(logging.INFO)
    _abruf(provider)

    assert len(mf_ok) == geladen, "warmer Abruf nach Sekundenwechsel ging doch ans Netz"
    assert _fenster_zeilen(caplog) == [(0, geladen)]
