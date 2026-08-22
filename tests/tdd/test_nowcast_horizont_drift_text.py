"""TDD RED — Issue #2051 S1: Horizont-Drift im Trockenzweig von
`format_now_text`.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-18.

Fachlicher Kern: der Trockenzweig sagt heute "In den nächsten 2 Stunden kein
Regen erwartet." — geprueft werden seit #1945 aber 3 Stunden
(`_NOWCAST_HORIZON_MIN = 180`). Die Aussage ist damit zu KURZ gegriffen: der
Nutzer bekommt eine Entwarnung fuer zwei Stunden, obwohl die Quelle drei
Stunden abgedeckt hat. Zwei Zusicherungen:

  * der Text nennt "3 Stunden" und nicht mehr "2 Stunden",
  * die Zahl ist an `_NOWCAST_HORIZON_MIN` GEKOPPELT und nicht als zweite,
    unabhaengige Zahl danebengeschrieben — sonst driftet sie beim naechsten
    Mal genauso auseinander. Nachgewiesen wird das, indem die Konstante zur
    LAUFZEIT veraendert wird und der Text mitwandern muss; ein Vergleich
    gegen die selbst ausgerechnete Zahl waere von einem hart getippten `3`
    ununterscheidbar.

RED heute: der Trockenzweig sagt "2 Stunden" -> beide Zusicherungen
schlagen fehl (fehlender bzw. verbotener Substring).

Mock-frei: echtes `NowcastResult` durch den echten Formatierer, eigener
Cache je Service.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

from services.radar_cache import RadarNowcastCacheService
from services.radar_service import (
    INTENSITY_DRY, NowcastResult, RadarNowcastService,
)

_TZ = ZoneInfo("Europe/Vienna")


def _trockenes_ergebnis() -> NowcastResult:
    """Kein Regen im gesamten Nowcast-Fenster: kein Beginn, kein Ausfall,
    keine Drosselung — der reine Trockenzweig."""
    return NowcastResult(
        onset_minutes=None, intensity_label=INTENSITY_DRY, source="radar",
    )


def _text(result: NowcastResult) -> str:
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return svc.format_now_text(result, tz=_TZ, include_source=False)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der geprueste Formatierer wird RELATIV ZU
    DIESER Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die
    Datei des Hauptrepos."""
    from services import radar_service as radar_module

    modul_pfad = Path(inspect.getfile(radar_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-18 — der Trockenzweig nennt 3 Stunden
# ---------------------------------------------------------------------------


def test_ac18_trockenzweig_nennt_drei_stunden():
    """AC-18 GIVEN den Trockenzweig von `format_now_text` (kein Regen im
    gesamten Nowcast-Fenster)
    WHEN der Text gerendert wird
    THEN lautet die Zeitangabe "In den nächsten 3 Stunden kein Regen
    erwartet." — konsistent mit `_NOWCAST_HORIZON_MIN = 180` seit #1945,
    nicht mehr "2 Stunden".

    RED heute: der Zweig sagt "In den nächsten 2 Stunden kein Regen
    erwartet."."""
    text = _text(_trockenes_ergebnis())

    assert "In den nächsten 3 Stunden kein Regen erwartet." in text, (
        f"RED: der Trockenzweig nennt nicht die tatsaechlich geprueften "
        f"3 Stunden: {text!r}"
    )
    assert "2 Stunden" not in text, (
        f"Die veraltete 2-Stunden-Aussage steht noch im Text — sie entwarnt "
        f"fuer eine kuerzere Spanne, als die Quelle abgedeckt hat: {text!r}"
    )


def test_ac18_stundenzahl_haengt_am_horizont_und_nicht_an_einer_kopie(monkeypatch):
    """AC-18 (Kopplung) GIVEN denselben Trockenzweig
    WHEN `_NOWCAST_HORIZON_MIN` ZUR LAUFZEIT auf einen anderen Wert gesetzt
    wird (120 bzw. 240 Minuten)
    THEN wandert die Stundenzahl im Text mit (2 bzw. 4 Stunden) — der Text
    liest die Konstante, statt eine zweite, unabhaengig gepflegte Zahl zu
    tragen. Genau diese Doppelpflege hat die heutige Drift erzeugt.

    Der Beleg MUSS ueber eine Veraenderung der Konstante laufen. Ein Test, der
    die erwartete Zahl selbst aus `_NOWCAST_HORIZON_MIN` ausrechnet und dann
    nur den fertigen String vergleicht, ist bei 180 Min von einem hart
    getippten `3` im Produktivcode ununterscheidbar (Adversary-Fund F002,
    2026-08-22: genau diese Mutation blieb gruen).

    Gepatcht wird die MODUL-Referenz (`radar_service._NOWCAST_HORIZON_MIN`),
    weil der Formatierer die Konstante bei jedem Aufruf ueber den
    Modul-Namensraum aufloest (`radar_service.py:519`) — waere sie beim Import
    an einen lokalen Namen gebunden, ginge der Patch ins Leere und der Test
    waere derselbe wertlose Nachweis in neuer Form.

    RED heute: der Text nennt 2 statt 3 Stunden."""
    from services import radar_service as radar_module

    assert radar_module._NOWCAST_HORIZON_MIN == 180, (
        f"Vorbedingung: Ist-Horizont 180 Min (seit #1945), ist aber "
        f"{radar_module._NOWCAST_HORIZON_MIN} Min."
    )
    assert "In den nächsten 3 Stunden" in _text(_trockenes_ergebnis()), (
        "Vorbedingung: der Ist-Horizont muss den AC-18-Wortlaut ergeben."
    )

    for horizont_min, erwartete_stunden in ((120, 2), (240, 4)):
        monkeypatch.setattr(radar_module, "_NOWCAST_HORIZON_MIN", horizont_min)

        text = _text(_trockenes_ergebnis())

        assert (
            f"In den nächsten {erwartete_stunden} Stunden kein Regen erwartet."
            in text
        ), (
            f"RED: bei einem Horizont von {horizont_min} Min muss der Text "
            f"{erwartete_stunden} Stunden nennen — er tut es nicht, die Zahl "
            f"ist also nicht an die Konstante gekoppelt: {text!r}"
        )
