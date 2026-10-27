"""TDD RED — Issue #2051 S1: Ende-Angabe in der Inbound-Kommando-Antwort.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-14.

Fachlicher Kern: `format_now_text` ist die Antwort auf das Inbound-Kommando
(Textstelle 7) und einer der beiden ungedeckelten Pfade — genau der Pfad, aus
dem der im Ticket geschilderte Realfall stammt. Sie nennt heute nur den
Beginn und muss zusaetzlich das Ende im Wortlaut `letzter Regen gegen HH:MM`
nennen.

RED heute: `NowcastResult` kennt `event_end_minutes` /
`event_ongoing_beyond_horizon` nicht -> `TypeError` beim Konstruktor.

Mock-frei: echte `NowcastResult`-Objekte durch den echten Formatierer; die
Uhr steht per `freeze_time` fest, weil `format_now_text` intern
`datetime.now()` liest. Eigener Cache je Service, damit kein prozessweit
geteilter Zustand mitwirkt.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from services.radar_cache import RadarNowcastCacheService
from services.radar_service import (
    _NOWCAST_HORIZON_MIN, NowcastResult, RadarNowcastService,
)

# 18:00 Ortszeit Wien (= 16:00 UTC im Sommer): Beginn 18:30 (+30 Min),
# Ende 19:30 (+90 Min).
_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"
_BEGINN_TEXT = "Starker Regen ab ca. 18:30 (in ~30 Min)"
_ENDE_TEXT = "letzter Regen gegen 19:30"

_UNSET = object()


def _nowcast(*, event_end_minutes: object = _UNSET,
             event_ongoing_beyond_horizon: object = _UNSET) -> NowcastResult:
    """`NowcastResult` mit gesetztem Beginn; die neuen Felder nur auf
    ausdruecklichen Wunsch setzen (Sentinel-Muster) — so bleibt die
    Vergleichsfassung ohne die Felder unabhaengig vom Erweiterungsstand."""
    fields = dict(
        onset_minutes=30, intensity_label="Starker Regen", source="radar",
        is_convective=False,
    )
    if event_end_minutes is not _UNSET:
        fields["event_end_minutes"] = event_end_minutes
    if event_ongoing_beyond_horizon is not _UNSET:
        fields["event_ongoing_beyond_horizon"] = event_ongoing_beyond_horizon
    return NowcastResult(**fields)


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
# AC-14 — die Kommando-Antwort nennt das Ende
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac14_kommando_antwort_nennt_das_ende():
    """AC-14 GIVEN ein `NowcastResult` mit gesetztem `event_end_minutes`
    (90 Minuten -> 19:30 Ortszeit)
    WHEN `format_now_text(result, tz=...)` als Antwort auf ein
    Inbound-Kommando gerendert wird
    THEN enthaelt der Text ZUSAETZLICH zur bestehenden Beginn-Zeile
    `letzter Regen gegen 19:30`.

    RED heute: `NowcastResult` kennt `event_end_minutes` nicht
    (`TypeError`)."""
    text = _text(_nowcast(event_end_minutes=90,
                          event_ongoing_beyond_horizon=False))

    assert _BEGINN_TEXT in text, (
        f"Die bestehende Beginn-Zeile darf nicht verlorengehen: {text!r}"
    )
    assert _ENDE_TEXT in text, (
        f"RED: Ende-Angabe {_ENDE_TEXT!r} fehlt in der Kommando-Antwort: "
        f"{text!r}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac14_ohne_ende_bleibt_die_heutige_antwort_byte_identisch():
    """AC-14 (Alt-Fall, AC-19) GIVEN ein `NowcastResult` ohne ableitbares
    Ende (`event_end_minutes=None`)
    WHEN die Kommando-Antwort einmal mit gesetztem `None` und einmal ganz
    ohne das Feld gerendert wird
    THEN sind beide Texte byte-identisch und tragen keine Ende-Angabe — das
    additive Feld mit Default bricht keinen Alt-Aufrufer.

    RED heute: `NowcastResult` kennt das Feld nicht (`TypeError`)."""
    mit_none = _text(_nowcast(event_end_minutes=None))
    ohne_feld = _text(_nowcast())

    assert mit_none == ohne_feld, (
        "Ein ungesetztes Ende darf die Kommando-Antwort nicht anfassen.\n"
        f"  mit None  = {mit_none!r}\n  ohne Feld = {ohne_feld!r}"
    )
    assert "letzter Regen gegen" not in mit_none, (
        f"Ohne ableitbares Ende darf keines behauptet werden: {mit_none!r}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac14_kein_ende_bei_gesetztem_horizont_waechter():
    """AC-14 (Waechter, AC-5) GIVEN ein `NowcastResult`, dessen Block bis zum
    Horizont nass bleibt (`event_ongoing_beyond_horizon=True`, Ende-Wert nur
    der Horizont)
    WHEN die Kommando-Antwort gerendert wird
    THEN erscheint KEINE Ende-Angabe — bei abgeschnittener Zeitreihe ist das
    echte Ende unbekannt und darf nicht behauptet werden.

    RED heute: `NowcastResult` kennt die beiden Felder nicht (`TypeError`)."""
    text = _text(_nowcast(event_end_minutes=_NOWCAST_HORIZON_MIN,
                          event_ongoing_beyond_horizon=True))

    assert _BEGINN_TEXT in text, (
        f"Die Beginn-Zeile bleibt auch bei gesetztem Waechter stehen: {text!r}"
    )
    assert "letzter Regen gegen" not in text, (
        f"Bei gesetztem Horizont-Waechter darf kein Ende behauptet werden: "
        f"{text!r}"
    )
