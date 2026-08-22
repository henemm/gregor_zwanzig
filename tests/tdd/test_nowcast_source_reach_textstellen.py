"""TDD RED — Issue #2051 S3: die Reichweiten-Angabe ("Radar reicht bis
HH:MM") in den sechs Langform-/Briefing-/Kommando-Textstellen.

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-3, AC-9,
AC-10.

Fachlicher Kern: `NowcastResult.source_reach_minutes` (S3) traegt, wie weit
die Quelle tatsaechlich geliefert hat. Additiv durchgereicht ueber die
geteilte Anzeigefassung `source_reach_display` (Muster `event_end_display`,
S1) bis in die sechs Textstellen:

  1. E-Mail-Betreff (`_render_subject_onset`)
  2. E-Mail Trip, Klartext (`_render_email_onset`)
  3. E-Mail Mehr-Orte-Buendel (`_render_email_onset_multi`)
  4. Telegram rich (`_render_telegram_onset`)
  5. Briefing-Kurzfristhinweis (`format_starkregen_hint`)
  6. Kommando-Antwort (`RadarNowcastService.format_now_text`)

Drei Zusicherungen:
  * AC-3 -- mit gesetzter Reichweite und OHNE den R4-Waechter
    (`event_ongoing_beyond_horizon=False`) tragen alle sechs Stellen
    zusaetzlich `Radar reicht bis HH:MM`.
  * AC-9 -- mit gesetztem R4-Waechter (S1-Untergrenzenform, `Regen
    mindestens bis HH:MM`) entfaellt die Reichweiten-Angabe VOLLSTAENDIG
    (E5): die Untergrenzenform traegt die Reichweiten-Aussage bereits
    implizit.
  * AC-10 -- derselbe Waechterfall wie AC-9, zusaetzlich mit einem Beginn
    jenseits der Guete-Grenze: die Guete-Zeile erscheint UNVERAENDERT, die
    E5-Unterdrueckung betrifft ausschliesslich die Reichweiten-Angabe.

RED heute: `NowcastResult` kennt `source_reach_minutes` nicht ->
`TypeError` bereits bei der Konstruktion.

Mock-frei: echte `NowcastResult`/`OnsetEvent`-Objekte durch die echten
Projektions- und Renderfunktionen. Die Uhr steht per `freeze_time`, weil
`to_multi_location_onset_alert_message`, `format_starkregen_hint` und
`format_now_text` ihre Zeitpunkte selbst aus `datetime.now()` bilden.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_subject, render_telegram
from output.renderers.email.starkregen_hint import format_starkregen_hint
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import NowcastResult, RadarNowcastService

# 18:00 Ortszeit Wien (= 16:00 UTC im Sommer).
_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"

# source_reach_minutes=120 -> lokale Reichweiten-Grenzzeit 20:00.
_REACH_MIN = 120
_REACH_HHMM = "20:00"
# event_end_minutes=90 -> lokale Untergrenzen-Zeit 19:30 (S1-Form).
_ENDE_MIN = 90
_ENDE_HHMM = "19:30"
# onset_minutes=75, jenseits der 60-Minuten-Guete-Grenze -> Guete-Grenzzeit
# 19:00 (now + 60 Min, NICHT der Beginn selbst).
_ONSET_JENSEITS_GUETE = 75
_GUETE_HHMM = "19:00"


def _nowcast(**kw) -> NowcastResult:
    fields = dict(
        onset_minutes=30, intensity_label="Mäßiger Regen", source="radar",
        is_convective=False,
    )
    fields.update(kw)
    return NowcastResult(**fields)


def _texte(nc: NowcastResult) -> dict[str, str]:
    """Die sechs Textstellen fuer EIN NowcastResult (Einzel-Ort-Pfad)."""
    einzel = to_multi_location_onset_alert_message(
        [("Sillian", nc)], tz=_TZ, stand_at="17:55",
    )
    buendel = to_multi_location_onset_alert_message(
        [("Sillian", nc), ("Obertilliach", nc)], tz=_TZ, stand_at="17:55",
    )
    _html, plain_einzel = render_email(einzel)
    _html_buendel, plain_buendel = render_email(buendel)
    svc = RadarNowcastService(cache=RadarNowcastCacheService())
    return {
        "email_betreff": render_subject(einzel),
        "email_trip_plain": plain_einzel,
        "email_mehr_orte": plain_buendel,
        "telegram_rich": render_telegram(einzel),
        "briefing_hinweis": format_starkregen_hint(
            nc.intensity_label, nc.onset_minutes, tz=_TZ,
            event_end_minutes=nc.event_end_minutes,
            event_ongoing_beyond_horizon=nc.event_ongoing_beyond_horizon,
            source_reach_minutes=nc.source_reach_minutes,
        ),
        "kommando_antwort": svc.format_now_text(nc, tz=_TZ, include_source=False),
    }


def _befund(treffer: dict[str, str]) -> str:
    return "; ".join(f"{name}={text[:160]!r}" for name, text in sorted(treffer.items()))


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): Projektion, Renderer, Briefing-Hinweis und
    Nowcast-Dienst werden RELATIV ZU DIESER Testdatei aufgeloest -- sonst
    pruefte ein Worktree-Lauf still die Dateien des Hauptrepos."""
    from output.renderers.alert import project as project_module
    from output.renderers.alert import render as render_module
    from output.renderers.email import starkregen_hint as hint_module
    from services import radar_service as radar_module

    arbeitsbaum = Path(__file__).resolve().parents[2]
    for modul in (project_module, render_module, hint_module, radar_module):
        modul_pfad = Path(inspect.getfile(modul)).resolve()
        assert modul_pfad.is_relative_to(arbeitsbaum), (
            f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
        )


# ---------------------------------------------------------------------------
# AC-3 -- Reichweite gesetzt, ohne R4-Waechter: alle sechs tragen sie
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac3_reichweite_erscheint_in_allen_sechs_textstellen():
    """AC-3 GIVEN ein `OnsetEvent`/`NowcastResult` mit gesetzter Reichweite
    (`source_reach_minutes=120`) und `event_ongoing_beyond_horizon=False`
    WHEN alle sechs Langform-/Briefing-/Kommando-Textstellen gerendert
    werden
    THEN enthaelt JEDE zusaetzlich zur bestehenden Beginn-Angabe
    `Radar reicht bis 20:00`.

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht
    (`TypeError`)."""
    nc = _nowcast(source_reach_minutes=_REACH_MIN, event_ongoing_beyond_horizon=False)
    texte = _texte(nc)

    ohne_reichweite = {
        name: text for name, text in texte.items()
        if f"Radar reicht bis {_REACH_HHMM}" not in text
    }
    assert not ohne_reichweite, (
        f"RED: diese Stellen tragen die Reichweite nicht: {_befund(ohne_reichweite)}"
    )


# ---------------------------------------------------------------------------
# AC-9 -- R4-Waechter gesetzt: die Reichweiten-Angabe entfaellt VOLLSTAENDIG
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac9_untergrenzenform_unterdrueckt_die_reichweite_vollstaendig():
    """AC-9 GIVEN denselben Aufbau EINMAL mit `event_ongoing_beyond_horizon
    =True` (S1-Untergrenzenform, `Regen mindestens bis HH:MM`) und EINMAL mit
    `False` -- sonst identisch (gleiches `event_end_minutes`, gleiche
    `source_reach_minutes`), nur der EINE Waechter verschoben
    WHEN die sechs betroffenen Textstellen fuer BEIDE Faelle gerendert
    werden
    THEN fehlt `Radar reicht bis` bei `True` VOLLSTAENDIG (die
    Untergrenzenform traegt die Reichweiten-Aussage bereits implizit, E5)
    UND derselbe Aufbau erzeugt `Radar reicht bis 20:00` bei `False` in
    JEDER der sechs Stellen -- Positivkontrolle: erst das Paar beweist, dass
    die Unterdrueckung aus E5 tatsaechlich WIRKT und nicht bloss nichts
    verdrahtet ist (Muster AC-6, Lehre aus #2075-Fehlklassifikation ohne
    Gegenprobe).

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht
    (`TypeError`)."""
    waechter_gesetzt = _texte(_nowcast(
        event_end_minutes=_ENDE_MIN, event_ongoing_beyond_horizon=True,
        source_reach_minutes=_REACH_MIN,
    ))
    waechter_nicht_gesetzt = _texte(_nowcast(
        event_end_minutes=_ENDE_MIN, event_ongoing_beyond_horizon=False,
        source_reach_minutes=_REACH_MIN,
    ))

    ohne_untergrenze = {
        name: text for name, text in waechter_gesetzt.items()
        if f"Regen mindestens bis {_ENDE_HHMM}" not in text
    }
    assert not ohne_untergrenze, (
        f"Vorbedingung: die S1-Untergrenzenform muss ueberall stehen: "
        f"{_befund(ohne_untergrenze)}"
    )

    mit_reichweite_trotz_waechter = {
        name: text for name, text in waechter_gesetzt.items()
        if "Radar reicht bis" in text
    }
    assert not mit_reichweite_trotz_waechter, (
        f"RED/E5: diese Stellen zeigen die Reichweite trotz gesetztem "
        f"R4-Waechter -- Dopplung mit der Untergrenzenform: "
        f"{_befund(mit_reichweite_trotz_waechter)}"
    )

    ohne_reichweite_ohne_waechter = {
        name: text for name, text in waechter_nicht_gesetzt.items()
        if f"Radar reicht bis {_REACH_HHMM}" not in text
    }
    assert not ohne_reichweite_ohne_waechter, (
        f"Positivkontrolle: derselbe Aufbau MUSS die Reichweite zeigen, "
        f"sobald ausschliesslich der R4-Waechter auf False steht -- sonst "
        f"beweist die Negativpruefung oben nur eine ueberhaupt nicht "
        f"existierende Angabe, keine echte Unterdrueckung: "
        f"{_befund(ohne_reichweite_ohne_waechter)}"
    )


# ---------------------------------------------------------------------------
# AC-10 -- E5-Unterdrueckung betrifft NUR die Reichweite, nicht die Guete
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac10_guete_zeile_bleibt_trotz_e5_unterdrueckung_unveraendert():
    """AC-10 GIVEN denselben Aufbau wie AC-9 (Beginn jenseits der
    Guete-Grenze, `onset_minutes=75`), EINMAL mit `event_ongoing_beyond_
    horizon=True` und EINMAL mit `False` -- sonst identisch
    WHEN die Texte fuer BEIDE Faelle gerendert werden
    THEN erscheint die Guete-Zeile `Ortsangabe ab 19:00 unscharf` in BEIDEN
    Faellen UNVERAENDERT (der Beginn ist in beiden Faellen derselbe, die
    Guete-Entscheidung haengt nicht am R4-Waechter), WAEHREND `Radar reicht
    bis` NUR bei `True` fehlt und bei `False` (Positivkontrolle) erscheint
    -- die E5-Unterdrueckung betrifft ausschliesslich die
    Reichweiten-Angabe, beide Entscheidungen bleiben unabhaengig
    voneinander.

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht
    (`TypeError`)."""
    waechter_gesetzt = _texte(_nowcast(
        onset_minutes=_ONSET_JENSEITS_GUETE,
        event_end_minutes=_ENDE_MIN, event_ongoing_beyond_horizon=True,
        source_reach_minutes=_REACH_MIN,
    ))
    waechter_nicht_gesetzt = _texte(_nowcast(
        onset_minutes=_ONSET_JENSEITS_GUETE,
        event_end_minutes=_ENDE_MIN, event_ongoing_beyond_horizon=False,
        source_reach_minutes=_REACH_MIN,
    ))

    for label, texte in (
        ("Waechter=True", waechter_gesetzt), ("Waechter=False", waechter_nicht_gesetzt),
    ):
        ohne_guete = {
            name: text for name, text in texte.items()
            if f"Ortsangabe ab {_GUETE_HHMM} unscharf" not in text
        }
        assert not ohne_guete, (
            f"RED ({label}): diese Stellen tragen die Guete-Zeile nicht -- "
            f"sie muss unabhaengig vom R4-Waechter stehen: {_befund(ohne_guete)}"
        )

    mit_reichweite_trotz_waechter = {
        name: text for name, text in waechter_gesetzt.items()
        if "Radar reicht bis" in text
    }
    assert not mit_reichweite_trotz_waechter, (
        f"Die Reichweite darf trotz Guete-Fall weiter unterdrueckt bleiben "
        f"(E5, unabhaengig von der Guete-Entscheidung): "
        f"{_befund(mit_reichweite_trotz_waechter)}"
    )

    ohne_reichweite_ohne_waechter = {
        name: text for name, text in waechter_nicht_gesetzt.items()
        if f"Radar reicht bis {_REACH_HHMM}" not in text
    }
    assert not ohne_reichweite_ohne_waechter, (
        f"Positivkontrolle: derselbe Aufbau (inkl. Guete-Fall) MUSS die "
        f"Reichweite zeigen, sobald ausschliesslich der R4-Waechter auf "
        f"False steht -- sonst beweist die Negativpruefung oben nur eine "
        f"ueberhaupt nicht existierende Angabe: "
        f"{_befund(ohne_reichweite_ohne_waechter)}"
    )
