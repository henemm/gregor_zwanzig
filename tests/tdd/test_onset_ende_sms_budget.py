"""TDD RED — Issue #2051 Scheibe S1: die Kurznachricht sprengt auch mit
Mengen- UND Ende-Token das Zeichenbudget nicht.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-16.

Fachlicher Kern: die Kurzform traegt seit #2046 die Regenmenge und bekommt in
dieser Scheibe zusaetzlich das Ende-Token. Beides zusammen verbraucht
Zeichenbudget. Geprueft wird der KOMBINIERTE Extremfall — 30-Zeichen-Ortsname
+ `onset_precip_mm=99.9` + spaetes Ende — nicht die alte Marge aus
#2046-AC-9 fortgeschrieben.

Spec-Fassung 1.1 (PO-Entscheid 2026-08-22): das teuerste Ende-Token ist die
UNTERGRENZEN-Form ` >@23:59` (`event_ongoing_beyond_horizon=True`), nicht die
Normalform `@23:59` — Leerzeichen und `>` kommen hinzu. Der Extremfall wird
deshalb mit gesetztem Waechter gebaut; die Normalform ist ein Teilfall davon
und damit mitgedeckt.

Reine Laengenpruefung, KEIN Goldstring-Vergleich: der Wortlaut gehoert
AC-8..AC-12/AC-20 (`test_onset_ende_textstellen.py`,
`test_onset_ende_untergrenze_abgrenzung.py`), hier zaehlt allein, dass der
Text ins Budget passt und der harte Schnitt `body[:limit]` im Normalfall
NICHT greift.

RED-Ursache: `OnsetEvent` kennt `event_ongoing_beyond_horizon` noch nicht ->
`TypeError` beim Konstruktor-Aufruf. Der Waechter muss den Renderer
erreichen, weil nur er (`_sms_onset_ende`) ueber die Token-Form entscheidet;
bis Spec-Stand 1.0 wurde er stromaufwaerts in `event_end_time=None`
aufgeloest.

Mock-frei: echte `OnsetEvent`/`AlertMessage`-Objekte durch den echten
Renderer, feste Zeitangaben (keine Wanduhr).
"""
from __future__ import annotations

import inspect
from pathlib import Path

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import render_sms

SMS_LIMIT = 140
# Deutlich ueber dem Limit: rendert derselbe Aufruf mit grosszuegigem Limit
# denselben Text, hat der harte Schnitt `body[:limit]` NICHT gegriffen.
UNGEDECKELT = 4000


def _extremfall_msg(*, event_end_time: str, ortsname: str) -> AlertMessage:
    """Der kombinierte Grenzfall als echte Nachricht (kein Mock).

    `event_ongoing_beyond_horizon=True` erzwingt die Untergrenzen-Form
    ` >@HH:MM` (Spec v1.1) — die laengste Ende-Schreibweise und damit der
    richtige Massstab fuer das Zeichenbudget."""
    event = OnsetEvent(
        onset_minutes=40, onset_time="18:00", km_from=0.0, km_to=0.0,
        is_convective=False, intensity_label="Starker Regen",
        source_label="Radar (DWD)", location_label=ortsname,
        onset_precip_mm=99.9, event_end_time=event_end_time,
        event_ongoing_beyond_horizon=True,
    )
    return AlertMessage(
        trip_short="Alpen", stand_at="17:20", events=(event,),
        source="Radar (DWD)",
    )


def _langer_ortsname() -> str:
    name = "Obertilliacher Bergwiesenalm".ljust(30, "x")
    assert len(name) == 30, "Voraussetzung: 30-Zeichen-Ortsname"
    return name


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der geprueften Renderer wird RELATIV ZU DIESER
    Testdatei aufgeloest — sonst pruefte ein Worktree-Lauf still die Datei des
    Hauptrepos und lieferte falsches Gruen."""
    from output.renderers.alert import render as render_module

    modul_pfad = Path(inspect.getfile(render_module)).resolve()
    arbeitsbaum = Path(__file__).resolve().parents[2]
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


def test_ac16_kombinierter_extremfall_bleibt_im_zeichenbudget():
    """AC-16 GIVEN einen Onset-Alarm mit 30 Zeichen langem Ortsnamen, der
    Extremmenge `onset_precip_mm=99.9` UND dem spaeten
    Ende-UNTERGRENZEN-Token (` >@23:59`, `event_ongoing_beyond_horizon=True`)
    WHEN `render_sms(msg, limit=140)` rendert
    THEN bleibt der Text bei hoechstens 140 Zeichen.

    Reine Laengenpruefung (Spec-Vorgabe), kein Goldstring.

    RED heute: `OnsetEvent` kennt `event_ongoing_beyond_horizon` nicht
    (`TypeError`)."""
    sms = render_sms(
        _extremfall_msg(event_end_time="23:59", ortsname=_langer_ortsname()),
        limit=SMS_LIMIT,
    )

    assert len(sms) <= SMS_LIMIT, (
        f"RED: {len(sms)} Zeichen ueberschreiten das Render-Limit "
        f"{SMS_LIMIT}: {sms!r}"
    )


def test_ac16_der_harte_schnitt_greift_im_extremfall_nicht():
    """AC-16 (Kern der Zusicherung) GIVEN denselben Extremfall
    WHEN derselbe Aufruf einmal mit `limit=140` und einmal ungedeckelt
    gerendert wird
    THEN sind beide Texte IDENTISCH — der harte Schnitt `body[:limit]` hat
    also nicht gegriffen.

    Ohne diese Pruefung waere die Laengenpruefung oben trivial erfuellbar:
    ein abgeschnittener Text ist immer kurz genug. Der Schnitt bleibt als
    letzte Reissleine bestehen, darf im Normalfall aber nie sichtbar werden —
    ein abgeschnittenes Ende-Token waere im Satellitenkanal eine falsche
    Angabe, keine fehlende. Bei der Untergrenzen-Form waere ein Schnitt sogar
    doppelt gefaehrlich: faellt das `>` weg, liest sich die Untergrenze als
    bekanntes Ende.

    RED heute: `OnsetEvent` kennt `event_ongoing_beyond_horizon` nicht
    (`TypeError`)."""
    ortsname = _langer_ortsname()
    gedeckelt = render_sms(
        _extremfall_msg(event_end_time="23:59", ortsname=ortsname), limit=SMS_LIMIT,
    )
    ungedeckelt = render_sms(
        _extremfall_msg(event_end_time="23:59", ortsname=ortsname), limit=UNGEDECKELT,
    )

    assert gedeckelt == ungedeckelt, (
        "RED: der harte Schnitt greift im Extremfall — der Text ist bei "
        f"limit={SMS_LIMIT} kuerzer als ungedeckelt.\n"
        f"  gedeckelt   ({len(gedeckelt)}) = {gedeckelt!r}\n"
        f"  ungedeckelt ({len(ungedeckelt)}) = {ungedeckelt!r}"
    )


def test_ac16_extremfall_bleibt_gsm7_tauglich():
    """AC-16 (Zeichenvorrat) GIVEN denselben Extremfall
    WHEN `render_sms(msg, limit=140)` rendert
    THEN ist der Text ASCII-rein.

    Ein einziges Zeichen ausserhalb von GSM-7 wuerde die Nachricht auf
    UCS-2 umstellen und die tatsaechliche Kapazitaet von 160 auf 70 Zeichen
    halbieren — die Zeichenzahl allein bewiese das Budget dann nicht. Das `>`
    der Untergrenzen-Form ist GSM-7-Basiszeichen und aendert daran nichts;
    genau das wird hier nachgewiesen statt angenommen.

    RED heute: `OnsetEvent` kennt `event_ongoing_beyond_horizon` nicht
    (`TypeError`)."""
    sms = render_sms(
        _extremfall_msg(event_end_time="23:59", ortsname=_langer_ortsname()),
        limit=SMS_LIMIT,
    )

    assert sms.isascii(), f"Kurznachricht ist nicht ASCII-rein: {sms!r}"
