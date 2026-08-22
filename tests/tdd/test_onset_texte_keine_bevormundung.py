"""TDD RED — Issue #2051 Scheibe S1: die Ende-Angabe bleibt eine WETTERAUSSAGE
und wird nicht zur Handlungsempfehlung.

SPEC: docs/specs/modules/feat_2051_s1_dauer_und_ende.md — AC-17.

Produkt-Grundsatz (PO, mehrfach bekraeftigt): Gregor Zwanzig liefert Daten,
keine Ratschlaege. Der Nutzer ist Profi und entscheidet selbst, was ein
Regenende fuer seine Tour bedeutet. Eine Ende-Angabe verfuehrt genau dazu,
den naechsten Schritt gleich mitzurechnen — "bei Planzeit bist du um 20:10
bei km 14, also …". Das waere eine Konsequenz aus dem Datum, nicht das Datum,
und zoege eine Nachfuehrpflicht nach sich, sobald sich die Planung aendert.

Geprueft werden die Textstellen, die in `render.py` bzw. im Nowcast-Dienst
entstehen — Betreff, E-Mail Trip, E-Mail Mehr-Orte, Telegram rich, Kurzform,
Kommando-Antwort (`format_now_text`). Der Briefing-Kurzfristhinweis
(`format_starkregen_hint`) fehlt hier bewusst: seine erweiterte Signatur
entsteht in der Parallelsitzung; ihn hier mit geratener Aufrufform zu pruefen
naegelte eine fremde Entwurfsentscheidung fest.

Der Cooldown-Hinweis ("Du erhaeltst diese Warnung hoechstens einmal in …")
bleibt ausdruecklich ausserhalb der Pruefung: er ist Zustell-Metatext ueber
das Meldeverhalten des Systems, keine Aussage ueber Wetter oder Position des
Nutzers. Deshalb wird ohne `cooldown_display` gerendert.

RED-Ursache: `OnsetEvent`/`NowcastResult` kennen die Ende-Felder noch nicht
-> `TypeError`. Eine reine Negativpruefung waere ohne diesen Aufbau heute
trivial gruen; geprueft wird deshalb der ENDE-TRAGENDE Text, den es heute
noch nicht geben kann.

Mock-frei: echte Modelle durch die echten Renderer, feste Zeitangaben.
"""
from __future__ import annotations

import re
from zoneinfo import ZoneInfo

import pytest

from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)

TZ = ZoneInfo("Europe/Vienna")

# Anrede in der zweiten Person bzw. Hoeflichkeitsform. Im Wetterdatentext hat
# sie nichts verloren — dort stehen Ort, Beginn, Ende, Menge, sonst nichts.
_ZWEITE_PERSON_RE = re.compile(
    r"\b(du|dir|dich|dein|deine|deinem|deinen|deiner|deines"
    r"|Sie|Ihnen|Ihr|Ihre|Ihrem|Ihren|Ihrer|Ihres)\b"
)
# Zeit-/Orts-/Streckenangabe — der zweite Bestandteil einer Positions-Rechnung
# ueber den Nutzer.
_ZEIT_ODER_ORT_RE = re.compile(
    r"\d{1,2}:\d{2}|\bkm\s*\d|\bkm\b|\b\d+\s*Min\b|\bStunden?\b"
)
# Ausdrueckliche Positions-Rechnungen ueber den Nutzer, unabhaengig davon, ob
# im selben Satz eine Zahl steht.
_POSITIONSRECHNUNG = (
    "bei planzeit", "bist du", "waerst du", "wärst du", "erreichst du",
    "triffst du", "befindest du", "stehst du", "kommst du",
)
# Handlungsempfehlungs-Vokabular.
_EMPFEHLUNG = (
    "empfehlung", "empfohlen", "wir empfehlen", "wir raten", "solltest",
    "sollten sie", "am besten", "besser umkehren", "plane ", "such dir",
    "brich ab", "warte ab",
)


def _onset_event(**kw) -> OnsetEvent:
    """Ein Trip-Radar-Onset-Ereignis MIT abgeleitetem Ende (feste Zeiten)."""
    fields = dict(
        onset_minutes=30, onset_time="18:00", km_from=8.0, km_to=14.0,
        is_convective=False, intensity_label="Mäßiger Regen",
        source_label="Radar (DWD)", segment_id="Ziel",
        onset_precip_mm=2.5, event_end_time="20:10",
    )
    fields.update(kw)
    return OnsetEvent(**fields)


def _onset_msg(*events: OnsetEvent) -> AlertMessage:
    """Bewusst OHNE `cooldown_display` — s. Modul-Kopf."""
    return AlertMessage(
        trip_short="KHW 403", stand_at="17:30", events=tuple(events),
        source="Radar (DWD)",
    )


def _texte_mit_ende() -> dict[str, str]:
    """Alle in dieser Scheibe geprueften Textstellen, jeweils MIT gesetztem
    Ende. Der Aufbau selbst ist die RED-Ursache: die Ende-Felder existieren
    heute nicht."""
    from output.renderers.alert.project import to_multi_location_onset_alert_message
    from services.radar_service import NowcastResult, RadarNowcastService

    einzel = _onset_msg(_onset_event())
    _html, plain = render_email(einzel)

    buendel = to_multi_location_onset_alert_message(
        [
            ("Zermatt", NowcastResult(
                onset_minutes=20, intensity_label="Mäßiger Regen",
                source="radar", is_convective=False, event_end_minutes=80,
            )),
            ("Chamonix", NowcastResult(
                onset_minutes=35, intensity_label="Leichter Regen",
                source="AROME-FR", is_convective=False, event_end_minutes=95,
            )),
        ],
        tz=TZ, stand_at="10:00",
    )
    _b_html, b_plain = render_email(buendel)

    # Echter, aufrufbarer `frame_source` (kein Mock): `format_now_text` ruft
    # ihn nicht auf, aber ein DI-Seam ohne Netzweg ist der ehrliche Aufbau.
    dienst = RadarNowcastService(frame_source=lambda lat, lon: [])
    kommando = dienst.format_now_text(
        NowcastResult(
            onset_minutes=30, intensity_label="Mäßiger Regen", source="radar",
            is_convective=False, event_end_minutes=150,
        ),
        tz=TZ,
    )

    return {
        "E-Mail-Betreff": render_subject(einzel),
        "E-Mail Trip": plain,
        "E-Mail Mehr-Orte": b_plain,
        "Telegram rich": render_telegram(einzel),
        "Kurzform (SMS/Premium-SMS/Telegram-Kurzstil)": render_sms(einzel),
        "Kommando-Antwort": kommando,
    }


def _saetze(text: str) -> list[str]:
    """Grobe Satz-/Zeilenzerlegung — die Nachbarschaft, in der Pronomen und
    Zeitangabe zusammen eine Positions-Rechnung ergeben."""
    return [s for s in re.split(r"[.\n·|]", text) if s.strip()]


def _verstoesse(text: str) -> list[str]:
    """Alle gefundenen Bevormundungs-Muster eines Textes."""
    gefunden: list[str] = []
    klein = text.lower()
    for phrase in _POSITIONSRECHNUNG:
        if phrase in klein:
            gefunden.append(f"Positions-Rechnung ueber den Nutzer: {phrase!r}")
    for phrase in _EMPFEHLUNG:
        if phrase in klein:
            gefunden.append(f"Handlungsempfehlung: {phrase!r}")
    for satz in _saetze(text):
        pronomen = _ZWEITE_PERSON_RE.search(satz)
        angabe = _ZEIT_ODER_ORT_RE.search(satz)
        if pronomen and angabe:
            gefunden.append(
                f"Anrede {pronomen.group(0)!r} zusammen mit der Angabe "
                f"{angabe.group(0)!r} im Satz {satz.strip()!r}"
            )
    return gefunden


# ---------------------------------------------------------------------------
# Selbstkontrolle des Pruefers — sonst waere die Negativpruefung wertlos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("beispiel", [
    "Regen ab 18:00 · bei Planzeit bist du um 20:10 bei km 14.",
    "Letzter Regen gegen 20:10. Wir empfehlen, die Etappe vorzuziehen.",
    "Du solltest vor 18:00 auf der Hütte sein.",
])
def test_der_pruefer_faengt_bekannte_bevormundungs_saetze(beispiel):
    """Vorbedingung (kein AC): der Muster-Pruefer dieser Datei muss echte
    Verstoss-Saetze auch tatsaechlich fangen.

    Ohne diese Positivkontrolle bestuende die Negativpruefung unten auch
    dann, wenn der Ausdruck gar nichts trifft — sie waere gruen aus dem
    falschen Grund. Dieser Test darf (und soll) schon heute gruen sein."""
    assert _verstoesse(beispiel), (
        f"Der Pruefer erkennt diesen Verstoss nicht: {beispiel!r}"
    )


def test_der_pruefer_schlaegt_bei_reinen_wetterdaten_nicht_an():
    """Vorbedingung (kein AC): der Pruefer darf einen reinen Datentext NICHT
    beanstanden — sonst waere die Negativpruefung unten unerfuellbar und
    bewiese nichts ueber die Implementierung.

    Darf schon heute gruen sein."""
    sauber = (
        "Regen in 30 Min\nWo & wann: km 8–14 · ab 18:00\n"
        "letzter Regen gegen 20:10\nIntensität: Mäßiger Regen\n"
        "Quelle: Radar (DWD)"
    )
    assert _verstoesse(sauber) == [], (
        f"Der Pruefer beanstandet einen reinen Datentext: {_verstoesse(sauber)}"
    )


# ---------------------------------------------------------------------------
# AC-17 — keine Bevormundung in irgendeiner der Ende-tragenden Textstellen
# ---------------------------------------------------------------------------


def test_ac17_keine_textstelle_enthaelt_eine_handlungsempfehlung():
    """AC-17 GIVEN jede der in dieser Scheibe gerenderten Textstellen MIT
    gesetztem Ende
    WHEN der Text auf Handlungsempfehlungen oder Positions-/Zeit-Rechnungen
    ueber den Nutzer geprueft wird
    THEN enthaelt KEINE der Stellen eine solche Formulierung — ausschliesslich
    Wetterdaten (Beginn, Ende, Menge, Ort).

    RED heute: `OnsetEvent`/`NowcastResult` kennen die Ende-Felder nicht
    (`TypeError` beim Aufbau der Texte) — der Ende-tragende Text, um den es
    geht, laesst sich noch gar nicht erzeugen."""
    befunde = {
        name: _verstoesse(text) for name, text in _texte_mit_ende().items()
    }
    beanstandet = {k: v for k, v in befunde.items() if v}

    assert not beanstandet, (
        "Bevormundende Formulierung in Ende-tragenden Texten:\n"
        + "\n".join(f"  {k}: {v}" for k, v in beanstandet.items())
    )


def test_ac17_die_ende_angabe_bleibt_ein_reines_datum():
    """AC-17 (Kern) GIVEN dieselben Textstellen
    WHEN die Umgebung der Ende-Angabe betrachtet wird
    THEN steht dort die Uhrzeit allein — keine daraus abgeleitete Aussage
    ueber Streckenposition, Restzeit des Nutzers oder Tourverlauf.

    Geprueft wird der Satz, in dem die Ende-Angabe steht: er darf keine
    Anrede in der zweiten Person tragen.

    RED heute: die Ende-Angabe existiert noch nicht (`TypeError` beim
    Aufbau)."""
    texte = _texte_mit_ende()
    gefunden_in: list[str] = []
    for name, text in texte.items():
        for satz in _saetze(text):
            if "letzter Regen gegen" not in satz and "@" not in satz:
                continue
            gefunden_in.append(name)
            pronomen = _ZWEITE_PERSON_RE.search(satz)
            assert pronomen is None, (
                f"{name}: die Ende-Angabe steht in einem Satz mit Anrede "
                f"{pronomen.group(0)!r}: {satz.strip()!r}"
            )
    assert gefunden_in, (
        "RED: keine der geprueften Textstellen traegt ueberhaupt eine "
        f"Ende-Angabe: {texte!r}"
    )
