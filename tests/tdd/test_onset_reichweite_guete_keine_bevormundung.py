"""TDD RED — Issue #2051 S3: Reichweite und Guete sind ein DATUM, keine
Handlungsempfehlung.

SPEC: docs/specs/modules/feat_2051_s3_reichweite_und_guete.md — AC-15.

Fachlicher Kern (Ticket-Grundprinzip, projektweit): Gregor Zwanzig liefert
Daten, keine Handlungsempfehlungen -- das Produkt ist fuer Profis, die
selbst entscheiden. Reichweite (`Radar reicht bis HH:MM`) und Guete
(`Ortsangabe ab HH:MM unscharf`) sagen NUR, was die Quelle hergibt, nicht
was der Nutzer tun soll. Keine der sieben Textstellen darf eine Formulierung
tragen, die eine Rechnung ueber den Nutzer anstellt ("verlass dich nicht
darauf", "bis dahin solltest du ...").

RED heute: `NowcastResult`/`OnsetEvent` kennen die neuen Felder nicht ->
`TypeError` bereits bei der Konstruktion -- die Positivkontrolle (Reichweite
und Guete stehen ueberhaupt im Text) schlaegt zuerst fehl.

Mock-frei: echte `NowcastResult`/`OnsetEvent`-Objekte durch die echten
Projektions- und Renderfunktionen. Die Uhr steht per `freeze_time`.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from output.renderers.alert.project import to_multi_location_onset_alert_message
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from output.renderers.email.starkregen_hint import format_starkregen_hint
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import NowcastResult, RadarNowcastService

_TZ = ZoneInfo("Europe/Vienna")
_FROZEN_UTC = "2026-08-21 16:00:00+00:00"

# Beginn jenseits der Guete-Grenze (Guete triggert) UND gesetzte Reichweite
# (Reichweite triggert, event_ongoing_beyond_horizon=False -> nicht durch E5
# unterdrueckt) -- beide Angaben gleichzeitig im Text.
_ONSET_MIN = 75
_ENDE_MIN = 30
_REACH_MIN = 120

# Formulierungen, die eine Handlungsempfehlung oder eine Rechnung ueber den
# Nutzer waeren (Ticket-Grundprinzip) -- Beispiele aus der Spec plus
# naheliegende Varianten.
_VERBOTENE_MUSTER = [
    "verlass dich nicht",
    "solltest du",
    "bis dahin solltest",
    "rechne damit, dass du",
    "sei vorsichtig",
    "achte darauf, dass du",
    "plane damit",
]


def _nowcast() -> NowcastResult:
    return NowcastResult(
        onset_minutes=_ONSET_MIN, intensity_label="Mäßiger Regen", source="radar",
        is_convective=False, event_end_minutes=_ENDE_MIN,
        event_ongoing_beyond_horizon=False, source_reach_minutes=_REACH_MIN,
    )


def _sieben_textstellen() -> dict[str, str]:
    nc = _nowcast()
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
        "kurzform": render_sms(einzel),
        "briefing_hinweis": format_starkregen_hint(
            nc.intensity_label, nc.onset_minutes, tz=_TZ,
            event_end_minutes=nc.event_end_minutes,
            event_ongoing_beyond_horizon=nc.event_ongoing_beyond_horizon,
            source_reach_minutes=nc.source_reach_minutes,
        ),
        "kommando_antwort": svc.format_now_text(nc, tz=_TZ, include_source=False),
    }


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


@freeze_time(_FROZEN_UTC)
def test_ac15_keine_der_sieben_textstellen_traegt_eine_handlungsempfehlung():
    """AC-15 GIVEN einen Onset-Alarm mit gesetzter Reichweite UND
    Guete-Zeile (beide Angaben im Text)
    WHEN alle sieben Textstellen auf Formulierungen geprueft werden, die
    eine Handlungsempfehlung oder eine Positions-/Uhrzeit-Rechnung ueber den
    Nutzer enthalten
    THEN enthaelt KEINE der sieben Texte eine solche Formulierung --
    ausschliesslich ein Datum ueber die Aussage.

    Die Positivkontrolle (Reichweite und Guete stehen ueberhaupt im Text)
    steht im selben Test: ohne sie waere die Negativpruefung trivial wahr,
    weil der heutige Code beide Angaben noch gar nicht kennt.

    RED heute: `NowcastResult` kennt `source_reach_minutes` nicht
    (`TypeError`)."""
    texte = _sieben_textstellen()

    ohne_reichweite = {
        name: text for name, text in texte.items() if "Radar reicht bis" not in text
        and "?" not in text
    }
    # Die Kurzform traegt keine "Radar reicht bis"-Zeile (E6) -- dort zaehlt
    # das Guete-Zeichen als Positivkontrolle, nicht der Reichweiten-Satz.
    ohne_reichweite.pop("kurzform", None)
    assert not ohne_reichweite, (
        f"Vorbedingung: diese Stellen tragen weder Reichweite noch Guete: "
        f"{sorted(ohne_reichweite)}"
    )
    assert "Ortsangabe ab" in texte["email_trip_plain"] or "?" in texte["kurzform"], (
        "Vorbedingung: die Guete-Angabe muss irgendwo im Text stehen, sonst "
        "prueft dieser Test nichts Neues."
    )

    def _pruefe(kandidaten: dict[str, str]) -> dict[str, list[str]]:
        gefunden: dict[str, list[str]] = {}
        for name, text in kandidaten.items():
            text_klein = text.lower()
            treffer_hier = [m for m in _VERBOTENE_MUSTER if m in text_klein]
            if treffer_hier:
                gefunden[name] = treffer_hier
        return gefunden

    # Positivkontrolle des DETEKTORS selbst (nicht der Produktivfunktion):
    # ein synthetischer, ABSICHTLICH verbotener Satz muss von DERSELBEN
    # Pruefschleife erkannt werden -- sonst waere die Negativpruefung unten
    # trivial wahr, weil `_VERBOTENE_MUSTER`/die Schleife selbst nie greifen
    # KOENNTE (z. B. falscher Variablenname, leere Liste, Gross-/
    # Kleinschreibungsfehler). Lehre aus #2054: ein "not in"/"leere Menge"-
    # Befund ohne Nachweis, dass er sonst ANSCHLUEGE, prueft nichts.
    synthetischer_verstoss = _pruefe({
        "synthetisch": "Radar reicht bis 20:00. Verlass dich nicht darauf.",
    })
    assert synthetischer_verstoss, (
        "Vorbedingung: der Detektor muss einen ABSICHTLICH eingebauten "
        "Verstoss erkennen -- sonst waere die Negativpruefung unten "
        "trivial wahr."
    )

    treffer = _pruefe(texte)

    assert not treffer, (
        f"RED/AC-15: verbotene Handlungsempfehlung gefunden: {treffer}\n"
        f"Texte: { {k: v[:200] for k, v in texte.items()} }"
    )
