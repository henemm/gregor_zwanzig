"""TDD RED — Issue #2051 S3: die Guete-Kennzeichnung ("Ortsangabe ab HH:MM
unscharf") und ihre Ausloesebedingung.

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-4, AC-5,
AC-6, AC-7.

Fachlicher Kern (E2/E4): die Guete ist eine Zeitschwelle, kein
Quellen-Merkmal. `LOCATION_SHARPNESS_LIMIT_MIN = 60` -- die Guete-Zeile
erscheint, wenn MINDESTENS EINE der im Text genannten Ereigniszeiten (Beginn
ODER Ende) jenseits von `now + LOCATION_SHARPNESS_LIMIT_MIN` liegt. Genannt
wird die GRENZZEIT selbst (`now + 60 Min`), nicht welcher Wert betroffen ist.

Vier Zusicherungen:
  * AC-4 -- Beginn 75 Min (jenseits): die Guete-Zeile erscheint in allen
    sechs Textstellen, mit der Grenzzeit `now + 60 Min`.
  * AC-5 -- Beginn 20 Min (diesseits, alarmfaehig), Ende 150 Min (jenseits):
    die Guete-Zeile erscheint TROTZDEM, obwohl der Alarm-Pfad den Beginn
    selbst nie ueber 55 Min Vorlauf hinaus ausloest (B3/E4).
  * AC-6 -- Positivkontrolle: derselbe Aufbau erzeugt bei 50 Min KEINE und
    bei 90 Min EINE Guete-Zeile, in EINEM Test.
  * AC-7 -- die Zone zwischen den Raendern: 45/59 Min (diesseits) vs. 61/75
    Min (jenseits), parametrisiert.

RED heute: `NowcastResult` kennt `event_end_minutes` bereits (S1), aber
`OnsetEvent`/die Renderer kennen die Guete-Suffixe nicht -- die erwarteten
Substrings fehlen ersatzlos im gerenderten Text.

Mock-frei: echte `NowcastResult`/`OnsetEvent`-Objekte durch die echten
Projektions- und Renderfunktionen. Die Uhr steht per `freeze_time`.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import render_email, render_subject, render_telegram
from output.renderers.email.starkregen_hint import format_starkregen_hint
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import NowcastResult, RadarNowcastService

# 18:00 Ortszeit Wien (= 16:00 UTC im Sommer). Guete-Grenzzeit now + 60 Min
# = 19:00 lokal -- UNABHAENGIG vom konkret betroffenen Ereigniswert.
_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"
_GUETE_HHMM = "19:00"


def _nowcast(**kw) -> NowcastResult:
    fields = dict(
        onset_minutes=30, intensity_label="Mäßiger Regen", source="radar",
        is_convective=False,
    )
    fields.update(kw)
    return NowcastResult(**fields)


def _texte(nc: NowcastResult) -> dict[str, str]:
    """Die sechs Textstellen fuer EIN NowcastResult (Einzel-Ort-Pfad),
    Muster `test_nowcast_source_reach_textstellen.py`."""
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
    Nowcast-Dienst werden RELATIV ZU DIESER Testdatei aufgeloest."""
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
# AC-4 -- Beginn jenseits der Grenze: alle sechs Stellen tragen die Zeile
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac4_beginn_jenseits_der_grenze_erzeugt_die_guete_zeile_ueberall():
    """AC-4 GIVEN einen Onset-Alarm mit Beginn 75 Minuten in der Zukunft
    (jenseits der 60-Minuten-Guete-Grenze) und einem Ende innerhalb der
    Grenze
    WHEN die Texte gerendert werden
    THEN erscheint in JEDER der sechs Textstellen zusaetzlich
    `Ortsangabe ab 19:00 unscharf`, mit `19:00` = `now + 60 Min`.

    RED heute: keine der sechs Stellen kennt die Guete-Suffixe."""
    nc = _nowcast(onset_minutes=75, event_end_minutes=30)
    texte = _texte(nc)

    ohne_guete = {
        name: text for name, text in texte.items()
        if f"Ortsangabe ab {_GUETE_HHMM} unscharf" not in text
    }
    assert not ohne_guete, (
        f"RED: diese Stellen tragen die Guete-Zeile nicht: {_befund(ohne_guete)}"
    )


# ---------------------------------------------------------------------------
# AC-5 -- der Alarm-Pfad-Fall: Ende jenseits der Grenze, Beginn diesseits
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac5_guete_zeile_erscheint_auch_wenn_nur_das_ende_jenseits_liegt():
    """AC-5 GIVEN einen Onset-Alarm mit Beginn 20 Minuten in der Zukunft
    (diesseits der Grenze, alarmfaehig unter `RADAR_ONSET_THRESHOLD_MIN`)
    und einem Ende 150 Minuten in der Zukunft (jenseits der Grenze)
    WHEN die Texte gerendert werden
    THEN erscheint die Guete-Zeile TROTZDEM, mit der Grenzzeit `19:00`
    (`now + 60 Min`) -- NICHT mit dem Beginn (20 Min) oder dem Ende (150
    Min) selbst.

    Genau der Fall aus B3/E4: der Alarm-Pfad selbst loest den Beginn nie
    ueber 55 Minuten Vorlauf hinaus aus und wuerde diese Guete-Zeile sonst
    stumm lassen.

    RED heute: keine Stelle kennt die Guete-Suffixe."""
    nc = _nowcast(onset_minutes=20, event_end_minutes=150)
    text = _texte(nc)["email_trip_plain"]

    assert f"Ortsangabe ab {_GUETE_HHMM} unscharf" in text, (
        f"RED: die Guete-Zeile fehlt, obwohl nur das ENDE jenseits der "
        f"Grenze liegt: {text!r}"
    )
    assert "Ortsangabe ab 18:20" not in text, (
        f"Die Guete-Zeile darf nicht den Beginn (20 Min) nennen: {text!r}"
    )
    assert "Ortsangabe ab 20:30" not in text, (
        f"Die Guete-Zeile darf nicht das Ende (150 Min) nennen, sondern "
        f"ausschliesslich die Grenzzeit: {text!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- Positivkontrolle: derselbe Aufbau, ein verschobener Wert
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_UTC)
def test_ac6_positivkontrolle_50_minuten_ohne_90_minuten_mit_guete_zeile():
    """AC-6 GIVEN zwei Onset-Alarme mit identischem Aufbau bis auf die
    betroffene Ereigniszeit -- einmal 50 Minuten (diesseits), einmal 90
    Minuten (jenseits der 60-Minuten-Grenze)
    WHEN die Texte gerendert werden
    THEN fehlt die Guete-Zeile beim 50-Minuten-Fall VOLLSTAENDIG UND
    derselbe Testaufbau erzeugt die Guete-Zeile, sobald ausschliesslich die
    betroffene Zeit auf 90 Minuten verschoben wird -- dieselbe Konstruktion,
    ein verschobener Wert, gegensaetzliches Ergebnis, in EINEM Test.

    RED heute: keine Stelle kennt die Guete-Suffixe -- der 90-Minuten-Fall
    bleibt ohne Zeile."""
    diesseits = _texte(_nowcast(onset_minutes=50))["email_trip_plain"]
    jenseits = _texte(_nowcast(onset_minutes=90))["email_trip_plain"]

    assert "Ortsangabe ab" not in diesseits, (
        f"Bei 50 Minuten (diesseits der Grenze) darf keine Guete-Zeile "
        f"entstehen: {diesseits!r}"
    )
    assert f"Ortsangabe ab {_GUETE_HHMM} unscharf" in jenseits, (
        f"RED: bei 90 Minuten (jenseits der Grenze) muss dieselbe "
        f"Konstruktion die Guete-Zeile erzeugen: {jenseits!r}"
    )


# ---------------------------------------------------------------------------
# AC-7 -- die Zone ZWISCHEN den Raendern (Lehre aus S1 -> #2075)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "minuten,erwartet_guete",
    [
        (45, False),  # deutlich diesseits
        (59, False),  # knapp diesseits
        (61, True),   # knapp jenseits
        (75, True),   # deutlich jenseits
    ],
)
@freeze_time(_FROZEN_UTC)
def test_ac7_guete_zeile_kippt_zwischen_59_und_61_minuten(minuten, erwartet_guete):
    """AC-7 GIVEN vier Faelle mit der betroffenen Ereigniszeit bei genau 45,
    59, 61 und 75 Minuten -- zwei knapp diesseits, zwei knapp jenseits der
    60-Minuten-Grenze (die Zone ZWISCHEN den Raendern aus S1, Lehre aus
    #2075: zwei ACs pruefen dort nur die blossen Raender 0/180 bzw. exakt
    60 und lassen die Zone dazwischen ungeprueft)
    WHEN die Guete-Zeile fuer jeden Fall geprueft wird
    THEN fehlt sie bei 45 und 59 Minuten und erscheint bei 61 und 75
    Minuten.

    RED heute: keine Stelle kennt die Guete-Suffixe -- 61 und 75 bleiben
    ohne Zeile."""
    text = _texte(_nowcast(onset_minutes=minuten))["email_trip_plain"]

    guete_vorhanden = "Ortsangabe ab" in text
    assert guete_vorhanden == erwartet_guete, (
        f"RED/Zone: bei {minuten} Minuten erwartet Guete-Zeile="
        f"{erwartet_guete}, tatsaechlich {guete_vorhanden}: {text!r}"
    )
