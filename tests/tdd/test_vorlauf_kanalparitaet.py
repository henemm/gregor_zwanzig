"""TDD RED — Issue #2261 Teil A (A-1), AC-10: ein Alarm mit Beginn in 170
Minuten erreicht alle vier Kanaele mit demselben Inhalt.

SPEC: docs/specs/modules/feat_2261_a1_radar_vorlauf.md — AC-10 (mit AC-7 und
AC-9 als Inhaltsbausteine).

Alle vier Kanaele (E-Mail, Telegram, SMS, Premium-SMS) sind gleichrangig: die
Empfangslage unterwegs ist unvorhersehbar, jeder Kanal muss dieselbe Frage
beantworten. Geprueft wird deshalb je Kanal der INHALT, nicht nur "es kam
etwas an":

  * Beginn-Uhrzeit mit Tagesbezug (Pruefung 22:30 Ortszeit + 170 Min =
    01:20 des Folgetags, Montag) -- Kopf in der SMS-Bausteinform
    "ab Mo1:20" (AC-9), E-Mail-Detailzeile "ab morgen 01:20", SMS/Premium-SMS
    "@Mo1:20";
  * Intensitaet ("mäßiger Regen" in E-Mail/Telegram; die Kurzform traegt sie
    als Kuerzel `R`);
  * Guetekennzeichnung "Ortsangabe ab 23:30 unscharf" (jetzt + 60 Min) bzw.
    das SMS-Zeichen `?`;
  * KEINE Mengenangabe: Onset 170 + 60 > 180, die Menge waere am Horizont
    abgeschnitten (AC-7).

Aufbau: echte `AlarmPruefstrecke` (echter `check_radar_alerts()`-Lauf,
echter Mail-Sink, lokale Telegram-/seven.io-Stubs), echter
`RadarNowcastService` an der `frame_source`-Naht mit festen, absoluten
15-Minuten-Frames. Die Etappe ist kuerzer als der Punktabstand
(`RADAR_ZONE_POINT_SPACING_KM` = 2 km): genau EIN Messpunkt, dessen
Aufenthaltsfenster offen ist (AC-3 Einzelpunkt-Fall) -- dieser Test misst
die Kanalparitaet, nicht die Fenster-Arithmetik.

Zwei Nutzer, derselbe Zeitpunkt, dieselben Frames: beide muessen alarmiert
werden (faengt zugleich ein Durchsickern von Sperrzeit/Identitaet zwischen
Nutzern).

RED heute: bei Schwelle 55 loest Onset 170 nicht aus.
"""
from __future__ import annotations

import re
import uuid
from datetime import date as date_type
from datetime import datetime, time as time_type, timedelta, timezone
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from app.loader import save_trip
from app.models import TripReportConfig
from app.trip import Stage, TimeWindow, Trip, Waypoint

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.helpers.tagesbezug import expected_day_and_time, extract_day_and_time
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _settings_all_channels, _write_premium_profile,
)

# Island: ganzjaehrig UTC+0 -- Ortszeit == Weltzeit.
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
ISLAND_ZONE = ZoneInfo("Atlantic/Reykjavik")
RATE_MM_H = 2.0  # "Mäßiger Regen" (1.0 <= r < 4.0)

# Mengentoken der Kurzform (`_sms_onset_menge` -> `_fmt_num("R", x)`):
# ein `R` (ggf. mit Ausfall-Zeichen `#`) unmittelbar gefolgt von einer Zahl.
# Ohne Menge folgt `@` bzw. ` now` (zahlenlose Alt-Form `R@HH:MM`).
# Gegen eine echte Positivprobe geeicht in
# `test_vorlauf_anzeige_menge.py::test_menge_bleibt_bei_vollem_fenster`.
MENGEN_TOKEN = re.compile(r"(?<![A-Za-z])R#?\d")
# Langform: eine Zahl mit Einheit mm (z. B. "1,5 mm", "~2 mm").
MENGE_LANGFORM = re.compile(r"\d+(?:[.,]\d+)?\s*mm\b")


def uid(tag: str) -> str:
    return f"tdd-2261-a1-{tag}-{uuid.uuid4().hex[:6]}"


def kurzer_trip(trip_id: str, tag: date_type, start: str, ende: str) -> Trip:
    """Ein-Segment-Etappe, aktiv zwischen `start` und `ende` Ortszeit (Island),
    Strecke ~0,6 km < Punktabstand 2 km -> genau EIN Messpunkt.

    `arrival_override` bestimmt die Segmentgrenzen unabhaengig vom
    Compute-on-Save (Muster `test_alarm_szenario_tagesbezug_zeitzone.py`)."""
    h0, m0 = (int(x) for x in start.split(":"))
    h1, m1 = (int(x) for x in ende.split(":"))
    wp0 = Waypoint(
        id="G1", name="Start", lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=100.0,
        time_window=TimeWindow(start=time_type(0, 0), end=time_type(h0, m0)),
        arrival_override=start,
    )
    wp1 = Waypoint(
        id="G2", name="Ziel", lat=ISLAND_LAT + 0.004, lon=ISLAND_LON + 0.004,
        elevation_m=120.0,
        time_window=TimeWindow(start=time_type(h0, m0), end=time_type(h1, m1)),
        arrival_override=ende,
    )
    stage = Stage(
        id="T1", name="Tag 1", date=tag, start_time=time_type(h0, m0),
        waypoints=[wp0, wp1],
    )
    trip = Trip(id=trip_id, name="Vorlauf Testtrip", stages=[stage])
    return trip


def alle_kanaele_konfig(trip_id: str, *, telegram_style: str = "rich") -> TripReportConfig:
    return TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, send_sms=True,
        send_premium_sms=True, alert_on_changes=True,
        telegram_style=telegram_style,
    )


def feste_frames(at: datetime, onset_min: int, *, rate: float = RATE_MM_H):
    """Echter `frame_source`: 15-Minuten-Raster bis `at + 180`, auf den
    Beginn ausgerichtet (der erste nasse Frame liegt exakt bei
    `at + onset_min`), davor trocken, ab dort nass. Absolute Zeitstempel,
    keine Wanduhr-Ableitung je Aufruf."""
    versatz = onset_min % 15

    def _frames(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame

        return [
            RadarFrame(
                timestamp=at + timedelta(minutes=m),
                precip_mm_h=(rate if m >= onset_min else 0.0),
                is_convective=False,
            )
            for m in range(versatz, 181, 15)
        ]

    return _frames


def pruef_lauf(nutzer: str, at: datetime, trip: Trip, frame_source):
    """Premium-Profil (Tier premium + frische Garmin-Rueckadresse) VOR dem
    Bau der Pruefstrecke -- ihr Konstruktor liest das Profil zurueck."""
    from services.radar_service import RadarNowcastService

    _write_premium_profile(nutzer, at)
    with freeze_time(at):
        save_trip(trip, user_id=nutzer)
    strecke = AlarmPruefstrecke(user_id=nutzer, settings=_settings_all_channels())
    return strecke.lauf(
        at=at, zweig="radar", trip=trip,
        radar_service=RadarNowcastService(frame_source=frame_source),
    )


# Sonntag, 2026-05-10, 22:30 Ortszeit (Island, UTC+0).
_AT = datetime(2026, 5, 10, 22, 30, tzinfo=timezone.utc)
_ONSET = 170


def test_alarm_bei_onset_170_erreicht_alle_vier_kanaele():
    """AC-10: Given ein Nutzer mit E-Mail, Telegram, SMS und Premium-SMS und
    Regen, der laut Radar in 170 Minuten beginnt (01:20 am Folgetag)
    When der Radar-Prueflauf laeuft
    Then erhalten ALLE VIER Kanaele den Alarm mit Beginn-Uhrzeit samt
    Tagesbezug, Intensitaet, Guetekennzeichnung und OHNE Mengenangabe --
    fuer zwei verschiedene Nutzer.

    RED heute: Schwelle 55 -> bei Onset 170 kein Alarm."""
    beginn_utc = _AT + timedelta(minutes=_ONSET)
    beginn_kurz = expected_day_and_time(beginn_utc, _AT, ISLAND_ZONE, style="kurzform")
    beginn_lang = expected_day_and_time(beginn_utc, _AT, ISLAND_ZONE)
    guete_lang = expected_day_and_time(_AT + timedelta(minutes=60), _AT, ISLAND_ZONE)
    # Von Hand: 22:30 + 170 = 01:20 am Montag; 22:30 + 60 = 23:30 am selben Tag.
    assert beginn_kurz == ("Mo", "1:20") and beginn_lang == ("morgen", "01:20")
    assert guete_lang == (None, "23:30")
    kopf = f"ab {beginn_kurz[0]}{beginn_kurz[1]}"   # "ab Mo1:20" (AC-9)
    sms_beginn = f"@{beginn_kurz[0]}{beginn_kurz[1]}"  # "@Mo1:20"

    for nr in (1, 2):
        nutzer = uid(f"ac10-n{nr}")
        _clean_user(nutzer)
        try:
            trip = kurzer_trip(f"trip-2261-ac10-{nr}", _AT.date(), "22:00", "23:59")
            trip.report_config = alle_kanaele_konfig(trip.id)
            lauf = pruef_lauf(nutzer, _AT, trip, feste_frames(_AT, _ONSET))

            assert lauf.triggered_count == 1, (
                f"AC-10 (Nutzer {nr}): Regen in {_ONSET} Min muss einen Alarm "
                f"ausloesen (war {lauf.triggered_count}). Fehlender Schritt: "
                f"RADAR_ONSET_THRESHOLD_MIN ist nicht aus NOWCAST_HORIZON_MIN "
                f"(180) abgeleitet."
            )
            for kanal, msgs in (
                ("E-Mail", lauf.mail), ("Telegram", lauf.telegram),
                ("SMS", lauf.sms), ("Premium-SMS", lauf.premium_sms),
            ):
                assert len(msgs) == 1, (
                    f"AC-10 (Nutzer {nr}): {kanal} muss genau EINE Nachricht "
                    f"erhalten, war {msgs!r} -- kein Kanal ersetzt einen anderen."
                )

            betreff, koerper = lauf.mail[0]
            mail = f"{betreff}\n{koerper}"
            telegram = lauf.telegram[0]
            sms = lauf.sms[0]
            premium = lauf.premium_sms[0]

            # Beginn mit Tagesbezug.
            for name, text in (("Betreff", betreff), ("Telegram-Kopf", telegram.split("\n", 1)[0])):
                assert kopf in text, (
                    f"AC-10/AC-9 (Nutzer {nr}): {name} muss den Beginn als "
                    f"'{kopf}' nennen.\n{text}"
                )
                assert f"in {_ONSET} Min" not in text, (
                    f"AC-10/AC-9 (Nutzer {nr}): {name} nennt Restminuten.\n{text}"
                )
            assert extract_day_and_time(koerper, "· ab") == beginn_lang, (
                f"AC-10 (Nutzer {nr}): E-Mail-Detailzeile muss den Beginn als "
                f"{beginn_lang!r} tragen.\n{koerper}"
            )
            for name, text in (("SMS", sms), ("Premium-SMS", premium)):
                assert sms_beginn in text, (
                    f"AC-10 (Nutzer {nr}): {name} muss das Beginn-Token "
                    f"'{sms_beginn}' (Tagesbezug als Wochentagskuerzel) "
                    f"tragen.\n{text!r}"
                )

            # Intensitaet.
            for name, text in (("E-Mail", mail), ("Telegram", telegram)):
                assert "mäßiger regen" in text.lower(), (
                    f"AC-10 (Nutzer {nr}): {name} muss die Intensitaet "
                    f"'mäßiger Regen' nennen.\n{text}"
                )
            for name, text in (("SMS", sms), ("Premium-SMS", premium)):
                # Regen-Kuerzel + Beginn-Token OHNE Zahl dazwischen
                # (`R@Mo1:20`, zahlenlose Form -- AC-7).
                assert f"R{sms_beginn}" in text, (
                    f"AC-10 (Nutzer {nr}): {name} muss 'R{sms_beginn}' tragen "
                    f"(Regen-Kuerzel, Beginn mit Tagesbezug, keine Menge "
                    f"dazwischen).\n{text!r}"
                )

            # Guetekennzeichnung.
            for name, text in (("E-Mail", mail), ("Telegram", telegram)):
                assert extract_day_and_time(text, "Ortsangabe ab") == guete_lang, (
                    f"AC-10 (Nutzer {nr}): {name} muss 'Ortsangabe ab "
                    f"{guete_lang[1]} unscharf' tragen.\n{text}"
                )
                assert "unscharf" in text
            for name, text in (("SMS", sms), ("Premium-SMS", premium)):
                assert "?" in text, (
                    f"AC-10 (Nutzer {nr}): {name} muss das Guete-Zeichen '?' "
                    f"tragen.\n{text!r}"
                )

            # Keine Mengenangabe (AC-7).
            for name, text in (("SMS", sms), ("Premium-SMS", premium)):
                assert not MENGEN_TOKEN.search(text), (
                    f"AC-10/AC-7 (Nutzer {nr}): {name} traegt eine Mengenangabe, "
                    f"obwohl das 60-Min-Fenster ab Beginn ({_ONSET}+60 > 180) am "
                    f"Horizont abgeschnitten ist.\n{text!r}"
                )
            for name, text in (("E-Mail", mail), ("Telegram", telegram)):
                assert not MENGE_LANGFORM.search(text), (
                    f"AC-10/AC-7 (Nutzer {nr}): {name} traegt eine Mengenangabe."
                    f"\n{text}"
                )

            # Gleicher Inhalt in SMS und Premium-SMS (beide tragen sms_body).
            assert sms == premium, (
                f"AC-10 (Nutzer {nr}): SMS und Premium-SMS weichen ab:\n"
                f"SMS={sms!r}\nPremium={premium!r}"
            )
        finally:
            _clean_user(nutzer)
