"""TDD RED — Issue #2051 S1: Ende-Angabe im Briefing-Kurzfristhinweis.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-13.

Fachlicher Kern: der Briefing-Kurzfristhinweis (Textstelle 6) transportiert
heute nur `intensity_label` und `onset_minutes` — die Datenform
(`starkregen_nowcast: tuple[str, int] | None`) ist fuer Ende und Waechter zu
eng. `format_starkregen_hint` bekommt die beiden zusaetzlichen Angaben
additiv als Schluesselwort-Argumente:

    format_starkregen_hint(
        intensity_label, onset_minutes, *, tz,
        event_end_minutes=None, event_ongoing_beyond_horizon=False,
    )

Additiv und defaultet: ein Alt-Aufrufer, der die neuen Argumente nicht
uebergibt, bekommt byte-identisch den heutigen Text (AC-19).

RED heute: `format_starkregen_hint` kennt die beiden Argumente nicht
-> `TypeError: unexpected keyword argument`; `NowcastResult` kennt die
Quellfelder nicht -> `TypeError` beim Konstruktor.

Mock-frei: echte Funktion, echte `NowcastResult`-Objekte; die Uhr steht per
`freeze_time` fest, weil `format_starkregen_hint` intern `datetime.now()`
liest.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.email.starkregen_hint import format_starkregen_hint
from services.radar_service import NowcastResult

# 18:00 Ortszeit Wien (= 16:00 UTC im Sommer): Beginn 18:30 (+30 Min),
# Ende 19:30 (+90 Min).
_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"
_BEGINN_TEXT = "Starker Regen ab ca. 18:30 (in ~30 Min)"
_ENDE_TEXT = "letzter Regen gegen 19:30"

_UNSET = object()


def _nowcast(**kw) -> NowcastResult:
    """`NowcastResult` mit gesetztem Beginn; neue Felder nur auf
    ausdruecklichen Wunsch (Sentinel-Muster)."""
    fields = dict(
        onset_minutes=30, intensity_label="Starker Regen", source="radar",
        is_convective=False,
    )
    fields.update({k: v for k, v in kw.items() if v is not _UNSET})
    return NowcastResult(**fields)


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der geprueste Briefing-Baustein wird RELATIV
    ZU DIESER Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still
    die Datei des Hauptrepos."""
    from output.renderers.email import starkregen_hint as hint_module

    modul_pfad = Path(inspect.getfile(hint_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


# ---------------------------------------------------------------------------
# AC-13 — der Hinweis nennt zusaetzlich das Ende
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac13_briefing_hinweis_nennt_das_ende():
    """AC-13 GIVEN ein Nowcast-Ergebnis mit gesetztem Ende
    (`event_end_minutes=90`) und `event_ongoing_beyond_horizon=False`
    WHEN `format_starkregen_hint(...)` den Briefing-Kurzfristhinweis rendert
    THEN enthaelt der Text ZUSAETZLICH zur bestehenden Beginn-Angabe die
    Ende-Angabe im Wortlaut `letzter Regen gegen HH:MM`.

    RED heute: `format_starkregen_hint` kennt die erweiterte Datenform nicht
    (`TypeError: unexpected keyword argument`)."""
    text = format_starkregen_hint(
        "Starker Regen", 30, tz=_TZ,
        event_end_minutes=90, event_ongoing_beyond_horizon=False,
    )

    assert _BEGINN_TEXT in text, (
        f"Die bestehende Beginn-Angabe darf nicht verlorengehen: {text!r}"
    )
    assert _ENDE_TEXT in text, (
        f"RED: Ende-Angabe {_ENDE_TEXT!r} fehlt im Briefing-Hinweis: {text!r}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac13_ohne_ende_bleibt_die_heutige_form_byte_identisch():
    """AC-13 (Alt-Aufrufer, AC-19) GIVEN denselben Hinweis OHNE ableitbares
    Ende (`event_end_minutes=None`)
    WHEN er einmal mit den neuen Argumenten und einmal ganz ohne sie
    gerendert wird
    THEN sind beide Texte byte-identisch und tragen KEINE Ende-Angabe — die
    Erweiterung ist additiv und defaultet, kein Bruch fuer Alt-Aufrufer.

    RED heute: der Aufruf mit den neuen Argumenten schlaegt mit `TypeError`
    fehl."""
    mit_none = format_starkregen_hint(
        "Starker Regen", 30, tz=_TZ,
        event_end_minutes=None, event_ongoing_beyond_horizon=False,
    )
    ohne_argumente = format_starkregen_hint("Starker Regen", 30, tz=_TZ)

    assert mit_none == ohne_argumente, (
        "Ein ungesetztes Ende darf den Hinweistext nicht anfassen.\n"
        f"  mit None       = {mit_none!r}\n"
        f"  ohne Argumente = {ohne_argumente!r}"
    )
    assert "letzter Regen gegen" not in mit_none, (
        f"Ohne ableitbares Ende darf keines behauptet werden: {mit_none!r}"
    )


@freeze_time(_FROZEN_UTC)
def test_ac13_ende_stammt_aus_dem_nowcast_ergebnis():
    """AC-13 (Datenform) GIVEN ein `NowcastResult`, das Beginn UND Ende
    traegt
    WHEN seine Felder — so wie der Briefing-Pfad sie transportiert — an
    `format_starkregen_hint` durchgereicht werden
    THEN erscheint dieselbe Ende-Angabe im Hinweistext: die Angabe stammt aus
    dem Nowcast-Ergebnis, nicht aus einer zweiten Quelle.

    RED heute: `NowcastResult` kennt die beiden Felder nicht (`TypeError`)."""
    nc = _nowcast(event_end_minutes=90, event_ongoing_beyond_horizon=False)

    text = format_starkregen_hint(
        nc.intensity_label, nc.onset_minutes, tz=_TZ,
        event_end_minutes=nc.event_end_minutes,
        event_ongoing_beyond_horizon=nc.event_ongoing_beyond_horizon,
    )

    assert _ENDE_TEXT in text, (
        f"RED: das Ende aus dem NowcastResult kommt im Briefing-Hinweis nicht "
        f"an: {text!r}"
    )
