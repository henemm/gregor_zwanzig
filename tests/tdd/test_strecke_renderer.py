"""TDD RED — Issue #2051 Scheibe S4: die zwei neuen Zonen-Renderer (E3) der
`/strecke`-Antwort -- E-Mail-Tabellenzeile, Telegram-Kurzzeile, Kanalparitaet,
verbotene Muster (E7-unabhaengige Grundregel, dieselbe Musterliste wie
S2a-AC-16/S2b-AC-14) und der explizite Zeitanker (AC-23).

SPEC: docs/specs/modules/feat_2051_s4_strecke_kommando.md — AC-11, AC-12,
AC-20, AC-23.

RED-Ursache: `trip_command_processor._fmt_strecke_email`/
`_fmt_strecke_telegram` existieren noch nicht -> ImportError.

Mock-frei: echte `RainZone`-Objekte, echte Renderer-Funktionen.

Zeitanker (PO/Team-Lead-Entscheidung nach Rueckfrage): die Umrechnung
`onset_minutes`/`event_end_minutes` -> Uhrzeit haengt NICHT an der
Systemuhr, sondern an einem EXPLIZIT durchgereichten dritten Argument
(`now_utc`, derselbe Abrufzeitpunkt, gegen den `_show_strecke` die Nowcasts
geholt hat) -- sonst waere die Bildungsstelle der Uhrzeit unbewacht (beide
Seiten eines Tests laesen sonst dieselbe Systemuhr und ein Rueckfall auf sie
im Produktivcode faenge kein Test). Kein `freeze_time` mehr noetig: der
Anker ist eine normale Testeingabe.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from services.rain_extent import RainZone

_ANKER = datetime(2026, 8, 23, 15, 0, tzinfo=timezone.utc)  # -> 15:00 UTC

# Zone A: onset 0 Min (-> 15:00 am Anker), Ende 90 Min (-> 16:30).
_ZONE_A = RainZone(
    km_from=8.0, km_to=12.0, onset_minutes=0, event_end_minutes=90,
    intensity_label="Mäßiger Regen", source="INCA",
)
# Zone B: onset 130 Min (-> 17:10 am Anker), Ende 160 Min (-> 17:40).
_ZONE_B = RainZone(
    km_from=19.0, km_to=21.0, onset_minutes=130, event_end_minutes=160,
    intensity_label="Starker Regen", source="radar",
)

# Praezisierung (team-lead, nach Adversary-Rueckfrage): ohne das "km"-Praefix
# matcht `(\d+)-(\d+)` JEDE Ziffer-Bindestrich-Ziffer-Folge im Text -- die von
# AC-11 selbst geforderte Zeitschreibweise "HH:MM-HH:MM" erzeugt dadurch
# STRUKTURELL einen Scheintreffer (z. B. "00-16" aus "15:00-16:30", die
# Minuten direkt vor und die Stunde direkt nach dem Bindestrich). `\s*`
# deckt beide Renderer-Schreibweisen ab, falls sie das Leerzeichen nach
# "km" unterschiedlich setzen.
_PAAR_RE = re.compile(r"km\s*(\d+)-(\d+)")
_ZEIT_RE = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")


def _zeile_mit(text: str, teilstring: str) -> str:
    treffer = [z for z in text.splitlines() if teilstring in z]
    assert len(treffer) == 1, (
        f"Testvoraussetzung: genau eine Zeile mit {teilstring!r} erwartet, "
        f"gefunden {len(treffer)}: {treffer!r}\nVoller Text:\n{text}"
    )
    return treffer[0]


# --------------------------------------------------------------------------
# AC-11: E-Mail -- je Zone eine EIGENE Zeile mit allen vier Werten.
# --------------------------------------------------------------------------

def test_ac11_email_zeigt_je_zone_eine_zeile_mit_allen_vier_werten():
    """AC-11 GIVEN zwei Zonen (km 8-12, 'Mäßiger Regen', Quelle 'INCA',
    15:00-16:30; km 19-21, 'Starker Regen', Quelle 'radar', 17:10-17:40),
    gerechnet gegen den Anker 15:00 UTC WHEN die E-Mail-Antwort gerendert
    wird THEN enthaelt der Text fuer JEDE Zone eine eigene Zeile mit allen
    vier Werten.

    Quelle wird als KLARTEXT erwartet (team-lead-Entscheidung, E2): die
    Erwartung wird aus `RadarNowcastService.source_label()` ABGELEITET,
    nicht als Roh-Quellen-Literal ins Testfile geschrieben -- sonst bliebe
    die Uebersetzungsstelle im Renderer unbewacht und der Test friere nur
    zufaellig die heutige Roh-Schreibweise ein."""
    from services.radar_service import RadarNowcastService
    from services.trip_command_processor import _fmt_strecke_email

    text = _fmt_strecke_email((_ZONE_A, _ZONE_B), timezone.utc, _ANKER)
    svc = RadarNowcastService()
    label_inca = svc.source_label("INCA")
    label_radar = svc.source_label("radar")

    zeile_a = _zeile_mit(text, "km 8-12")
    for erwartet in ("km 8-12", "15:00-16:30", "Mäßiger Regen", label_inca):
        assert erwartet in zeile_a, (
            f"AC-11: Zeile 1 muss {erwartet!r} enthalten:\n{zeile_a!r}"
        )

    zeile_b = _zeile_mit(text, "km 19-21")
    for erwartet in ("km 19-21", "17:10-17:40", "Starker Regen", label_radar):
        assert erwartet in zeile_b, (
            f"AC-11: Zeile 2 muss {erwartet!r} enthalten:\n{zeile_b!r}"
        )
    assert zeile_a != zeile_b, "AC-11: die beiden Zonen muessen VERSCHIEDENE Zeilen sein"


# --------------------------------------------------------------------------
# AC-12: Telegram -- GENAU zwei Zeilen, km/Uhrzeit-Paritaet zur E-Mail.
# --------------------------------------------------------------------------

def test_ac12_telegram_hat_genau_zwei_zeilen_und_zahlen_stimmen_mit_email_ueberein():
    """AC-12 GIVEN denselben Zwei-Zonen-Aufbau wie AC-11 (derselbe Anker)
    WHEN die Telegram-Antwort gerendert wird THEN enthaelt der Text GENAU
    zwei Zeilen (eine je Flaeche), UND alle aus beiden Texten extrahierten
    km-Zahlen UND Uhrzeiten (Regex) stimmen zwischen E-Mail- und
    Telegram-Fassung exakt ueberein."""
    from services.trip_command_processor import (
        _fmt_strecke_email,
        _fmt_strecke_telegram,
    )

    email_text = _fmt_strecke_email((_ZONE_A, _ZONE_B), timezone.utc, _ANKER)
    telegram_text = _fmt_strecke_telegram((_ZONE_A, _ZONE_B), timezone.utc, _ANKER)

    telegram_zeilen = [z for z in telegram_text.splitlines() if z.strip()]
    assert len(telegram_zeilen) == 2, (
        f"AC-12: Telegram-Antwort muss GENAU 2 Zeilen haben (eine je "
        f"Flaeche), erhalten {len(telegram_zeilen)}:\n{telegram_text!r}"
    )

    km_email = _PAAR_RE.findall(email_text)
    km_telegram = _PAAR_RE.findall(telegram_text)
    zeit_email = _ZEIT_RE.findall(email_text)
    zeit_telegram = _ZEIT_RE.findall(telegram_text)

    erwartete_km = [("8", "12"), ("19", "21")]
    erwartete_zeit = [("15:00", "16:30"), ("17:10", "17:40")]

    assert km_email == erwartete_km, f"AC-12: E-Mail-km-Paare {km_email} != {erwartete_km}"
    assert km_telegram == erwartete_km, f"AC-12: Telegram-km-Paare {km_telegram} != {erwartete_km}"
    assert zeit_email == erwartete_zeit, f"AC-12: E-Mail-Zeiten {zeit_email} != {erwartete_zeit}"
    assert zeit_telegram == erwartete_zeit, f"AC-12: Telegram-Zeiten {zeit_telegram} != {erwartete_zeit}"

    # F008 (Adversary-Befund team-lead): E3 sagt Telegram OHNE Quelle-Spalte
    # (Platzgrund) -- bisher pruefte kein Test das. Positivkontrolle im
    # SELBEN Test (Quelle steht in der E-Mail-Fassung sehr wohl), damit die
    # Negativ-Pruefung unten nicht nur das Fehlen von etwas prueft, das es
    # vielleicht nirgends gibt.
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService()
    label_inca = svc.source_label("INCA")
    label_radar = svc.source_label("radar")
    assert label_inca in email_text and label_radar in email_text, (
        f"Testvoraussetzung (Positivkontrolle): die E-Mail-Fassung muss "
        f"beide Quellen-Label enthalten -- email_text={email_text!r}"
    )
    assert label_inca not in telegram_text and label_radar not in telegram_text, (
        f"F008: die Telegram-Fassung darf KEIN Quellen-Label enthalten "
        f"(E3: ohne Quelle-Spalte) -- telegram_text={telegram_text!r}"
    )


# --------------------------------------------------------------------------
# AC-20: verbotene Muster (Ankunftszeit-Rechnung, Handlungsempfehlung,
#        Begegnungspunkt-Aussage) -- keines darf erscheinen.
# --------------------------------------------------------------------------

# Dieselbe Musterliste wie S2a-AC-16/S2b-AC-14
# (test_regen_ausdehnung_textstellen.py::_VERBOTENE_MUSTER).
_VERBOTENE_MUSTER = [
    "verlass dich nicht",
    "solltest du",
    "bis dahin solltest",
    "rechne damit, dass du",
    "sei vorsichtig",
    "achte darauf, dass du",
    "plane damit",
    "du erreichst",
    "wirst du dort",
    "wirst du diese zone",
    "bist du dort",
    "kommst du dort an",
    "wenn du ankommst",
]


def _pruefe(kandidaten: dict[str, str]) -> dict[str, list[str]]:
    treffer: dict[str, list[str]] = {}
    for name, text in kandidaten.items():
        text_klein = text.lower()
        gefunden = [m for m in _VERBOTENE_MUSTER if m in text_klein]
        if gefunden:
            treffer[name] = gefunden
    return treffer


def test_ac20_beide_renderer_enthalten_keine_verbotenen_muster():
    """AC-20 GIVEN eine Zonen-Antwort in E-Mail- ODER Telegram-Fassung mit
    gesetzten Zonen WHEN der Text auf eine Liste verbotener Muster geprueft
    wird THEN enthaelt der Text KEINES dieser Muster.

    Positivkontrolle des Detektors (Lehre aus #2054, Muster S2a-AC-16): ein
    synthetischer, ABSICHTLICH verbotener Satz muss von DERSELBEN
    Pruefschleife erkannt werden."""
    from services.trip_command_processor import (
        _fmt_strecke_email,
        _fmt_strecke_telegram,
    )

    email_text = _fmt_strecke_email((_ZONE_A, _ZONE_B), timezone.utc, _ANKER)
    telegram_text = _fmt_strecke_telegram((_ZONE_A, _ZONE_B), timezone.utc, _ANKER)

    synthetischer_verstoss = _pruefe({
        "synthetisch": "km 8-12. Du erreichst diese Zone in 45 Minuten.",
    })
    assert synthetischer_verstoss, (
        "Vorbedingung: der Detektor muss einen ABSICHTLICH eingebauten "
        "Verstoss erkennen -- sonst waere die Negativpruefung unten trivial "
        "wahr."
    )

    treffer = _pruefe({"email": email_text, "telegram": telegram_text})
    assert not treffer, f"AC-20: verbotene Formulierung gefunden: {treffer}"


# --------------------------------------------------------------------------
# AC-23: der Zeitanker ist eine ECHTE Eingabe -- zwei verschiedene Anker
#        verschieben die gebildeten Uhrzeiten um GENAU ihre Differenz.
# --------------------------------------------------------------------------

def test_ac23_zwei_anker_verschieben_die_uhrzeiten_um_genau_ihre_differenz():
    """AC-23 GIVEN dieselbe Zonen-Fixture, EINMAL gegen Anker A (15:00 UTC)
    und EINMAL gegen Anker B (15:00 UTC + 47 Minuten) gerendert WHEN die
    gebildeten Uhrzeiten beider Laeufe verglichen werden THEN unterscheiden
    sie sich um EXAKT die Anker-Differenz (47 Minuten) -- nicht nur
    "irgendeine" Uhrzeit erscheint, sondern die Verschiebung ist die
    Anker-Differenz selbst.

    Faengt einen Rueckfall auf die Systemuhr im Renderer: wuerde
    `datetime.now()` statt des uebergebenen Ankers gelesen, waeren die
    Uhrzeiten beider Laeufe IDENTISCH (dieselbe reale Uhrzeit beim
    Testlauf) statt um 47 Minuten verschoben -- die Differenz-Pruefung
    unten wuerde durchfallen."""
    from services.trip_command_processor import _fmt_strecke_email

    versatz = timedelta(minutes=47)
    anker_a = _ANKER
    anker_b = _ANKER + versatz

    text_a = _fmt_strecke_email((_ZONE_A,), timezone.utc, anker_a)
    text_b = _fmt_strecke_email((_ZONE_A,), timezone.utc, anker_b)

    zeiten_a = _ZEIT_RE.findall(text_a)
    zeiten_b = _ZEIT_RE.findall(text_b)

    assert zeiten_a and zeiten_b, (
        f"Testvoraussetzung: beide Texte muessen eine Zeitspanne enthalten -- "
        f"a={text_a!r}, b={text_b!r}"
    )
    assert zeiten_a != zeiten_b, (
        f"AC-23: unterschiedliche Anker muessen unterschiedliche Uhrzeiten "
        f"ergeben (sonst liest der Renderer die Systemuhr statt des Ankers): "
        f"a={zeiten_a}, b={zeiten_b}"
    )

    def _als_datetime(hhmm: str, bezug: datetime) -> datetime:
        stunde, minute = (int(x) for x in hhmm.split(":"))
        return bezug.replace(hour=stunde, minute=minute, second=0, microsecond=0)

    beginn_a = _als_datetime(zeiten_a[0][0], anker_a)
    beginn_b = _als_datetime(zeiten_b[0][0], anker_b)
    ende_a = _als_datetime(zeiten_a[0][1], anker_a)
    ende_b = _als_datetime(zeiten_b[0][1], anker_b)

    assert (beginn_b - beginn_a) == versatz, (
        f"AC-23: die Beginn-Uhrzeit muss sich um EXAKT die Anker-Differenz "
        f"({versatz}) verschieben, tatsaechlich {beginn_b - beginn_a} "
        f"({zeiten_a[0][0]!r} -> {zeiten_b[0][0]!r})"
    )
    assert (ende_b - ende_a) == versatz, (
        f"AC-23: die Ende-Uhrzeit muss sich um EXAKT die Anker-Differenz "
        f"({versatz}) verschieben, tatsaechlich {ende_b - ende_a} "
        f"({zeiten_a[0][1]!r} -> {zeiten_b[0][1]!r})"
    )
