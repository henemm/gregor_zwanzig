"""TDD RED -- Dringlichkeit aus der Ampelfarbe, Kanal-Schwelle, D4 unveraendert
(Issue #2793 S2b, Spec feat_2793_s2_alarm_stufenwechsel.md §1/§3; AC-9, AC-12).

AC-9 laeuft ueber den echten Trip-Einstieg gegen die echten Kanal-Ausgaenge
(``tests/helpers/kanal_fake_transporte.py``: lokale HTTP-Gegenstellen fuer
seven.io, skriptbare SMTP-Gegenstelle) -- gezaehlt wird am Draht, der Grund
steht im echten Alarm-Protokoll.

AC-12 (D4): Nullgradgrenze und Gewitter-Beginn laufen bis S7 auf der heutigen
Δ-Logik. Der Vorher-Stand (Betreff, Kopf, Dringlichkeit) ist hier aus dem
Lauf VOR S2b (Commit 85c3024) festgehalten; ausgeblendet sind nur die
Uhrzeiten (``HH:MM``), die vom Zeitpunkt des Laufs abhaengen.

Kein ``Mock()``/``patch()``/``MagicMock``.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import MetricConfig, TripReportConfig, UnifiedWeatherDisplayConfig
from app.trip import Stage, Trip, Waypoint

from tests.helpers.alert_log_fixtures import (
    LAT, LON, read_log, reason_for_channel, settings_email_only, weather,
)
from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.kanal_fake_transporte import KanalRig, kanal_auswahl, premium_profil_schreiben
from tests.helpers.ortstag import ortstag


def _uid(tag: str) -> str:
    return f"tdd-2793-d-{tag}-{uuid.uuid4().hex[:6]}"


def _trip(trip_id: str, *, alarm_ab: dict | None = None, metrics: tuple[str, ...],
          levels: dict | None = None) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=ortstag(LAT, LON),
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(
        id=trip_id, name="Ampel-Trip", stages=[stage], official_warnings=None, corridors=[],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id=cid, enabled=True) for cid in metrics],
            metric_alert_levels=levels,
            ampel={"template": "allgemein",
                   "metrics": {m: {"alarm_ab": ab} for m, ab in (alarm_ab or {}).items()}},
        ),
    )
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, alert_on_changes=True,
        morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = 0
    trip.official_alert_triggers_enabled = False
    return trip


@pytest.fixture
def rig(monkeypatch):
    r = KanalRig(monkeypatch)
    yield r
    r.stoppen()


def _rig_lauf(rig: KanalRig, uid: str, trip: Trip, alt: dict, neu: dict) -> None:
    from services.trip_alert import TripAlertService

    jetzt = datetime.now(timezone.utc)
    premium_profil_schreiben(uid, reply_at=jetzt - timedelta(minutes=5))
    TripAlertService(
        settings=rig.settings(premium_reply_at=jetzt - timedelta(minutes=5)),
        user_id=uid, throttle_hours=0,
    ).check_and_send_alerts(trip, [weather(1, **alt)], fresh_weather=[weather(1, **neu)])


def _letzter_alarm(uid: str) -> dict:
    log = read_log(uid)
    eintraege = [e for e in log["entries"] + log["not_delivered"]
                 if (e.get("changes_count") or 0) > 0]
    assert eintraege, f"kein Alarm-Eintrag im Protokoll: {log!r}"
    return eintraege[-1]


# ═══════════════ AC-9 — Kanal-Schwelle liest die Farb-Dringlichkeit ══════════

def test_ac9_verschaerfung_gelb_auf_orange_erreicht_nur_die_email(rig):
    """AC-9 GIVEN Kanal-Schwelle E-Mail „gering", SMS „hoch" / WHEN eine
    Verschaerfung gelb -> orange (Boeen 40 -> 55) ausloest / THEN nur die
    E-Mail, SMS mit ``below_channel_threshold`` im Protokoll.

    RED heute: Δ 15 < 20 -> gar kein Alarm."""
    uid = _uid("ac9a")
    trip = _trip("trip-ac9a", alarm_ab={"gust": "orange"}, metrics=("gust",))
    trip.alert_channels = kanal_auswahl("email", "sms")
    trip.alert_channel_thresholds = {"email": "LOW", "sms": "HIGH"}
    _rig_lauf(rig, uid, trip, {"gust_max_kmh": 40.0}, {"gust_max_kmh": 55.0})

    assert rig.anzahl_angenommen("email") == 1, rig
    assert rig.anzahl_versuche("sms") == 0, rig
    eintrag = _letzter_alarm(uid)
    assert eintrag["severity"] == "MODERATE", eintrag
    assert reason_for_channel(eintrag, "sms") == "below_channel_threshold", eintrag


def test_ac9_entwarnung_rot_auf_gelb_erreicht_beide_kanaele(rig):
    """AC-9 GIVEN dieselben Schwellen / WHEN Entwarnung rot -> gelb (70 -> 35,
    unter „Alarm ab Orange") / THEN Dringlichkeit hoch (verlassene Farbe rot,
    D3), E-Mail UND SMS werden beliefert."""
    uid = _uid("ac9b")
    trip = _trip("trip-ac9b", alarm_ab={"gust": "orange"}, metrics=("gust",))
    trip.alert_channels = kanal_auswahl("email", "sms")
    trip.alert_channel_thresholds = {"email": "LOW", "sms": "HIGH"}
    _rig_lauf(rig, uid, trip, {"gust_max_kmh": 70.0}, {"gust_max_kmh": 35.0})

    assert rig.anzahl_angenommen("email") == 1, rig
    assert rig.anzahl_angenommen("sms") == 1, rig
    assert _letzter_alarm(uid)["severity"] == "HIGH"


# ═════════ AC-12 — Nullgradgrenze und Gewitter-Beginn wie vor S2 (D4) ════════

_UHRZEIT = re.compile(r"\d{2}:\d{2}")


def _ohne_uhrzeit(text: str) -> str:
    return _UHRZEIT.sub("HH:MM", text)


def _mail_lauf(uid: str, trip: Trip, alt: dict, neu: dict,
               roh: list | None = None) -> tuple[str, str]:
    """``(Betreff, Text)`` mit ``HH:MM``; ``roh`` erhaelt die ungekuerzte Mail."""
    from services.trip_alert import TripAlertService

    mails: list = roh if roh is not None else []
    TripAlertService(
        settings=settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body, **_kw: mails.append((subject, body)),
    ).check_and_send_alerts(trip, [weather(1, **alt)], fresh_weather=[weather(1, **neu)])
    assert mails, "AC-12 Voraussetzung: die D4-Metrik muss weiterhin alarmieren."
    subject, body = mails[-1]
    return _ohne_uhrzeit(subject), _ohne_uhrzeit(body)


def test_ac12_nullgradgrenze_standard_faellt_450_m_wie_vor_s2():
    """AC-12 GIVEN Nullgradgrenze „standard" (Δ 400 m) / WHEN sie um 450 m
    faellt / THEN derselbe Alarm, dieselbe Dringlichkeit, derselbe Kopf."""
    uid = _uid("ac12a")
    trip = _trip("trip-ac12a", metrics=("freezing_level",),
                 levels={"freezing_level": "standard"})
    subject, body = _mail_lauf(
        uid, trip, {"freezing_level_m": 3000}, {"freezing_level_m": 2550},
    )
    assert subject == VORHER_NULLGRAD_BETREFF, subject
    assert body.splitlines() == VORHER_NULLGRAD_TEXT, body
    assert _letzter_alarm(uid)["severity"] == "LOW"


#: Feste Uhr fuer den Beginn-Fall (F301, Fix-Loop 4): 06:00 UTC = 08:00 Ortszeit
#: am Trip-Ort (47 N / 11 O, Europe/Vienna, Sommerzeit). Anker 12:00 UTC und
#: neuer Beginn 10:00 UTC liegen damit beide am Versandtag (14:00 und 12:00
#: Ortszeit; Anker +6 h, neu +4 h wie im Vorher-Lauf) und in der Zukunft -- genau der Fall, den der Vorher-Stand
#: (85c3024) aufgenommen hat: Tageswort entfaellt, kein „seit". Mit der
#: Wanduhr lag der Anker ab 18:00 UTC am Folgetag („morgen HH:MM") und der
#: Test war rot, ohne dass der Pruefling falsch war.
_BEGINN_UHR = datetime(2026, 8, 11, 6, 0, tzinfo=timezone.utc)


def test_ac12_gewitter_beginnt_zwei_stunden_frueher_wie_vor_s2():
    """AC-12 GIVEN aktiver Gewitterbeginn-Alarm („standard": ab 1 h frueher) /
    WHEN das Gewitter 2 h frueher beginnt / THEN derselbe Alarm wie vor S2.

    Die Gewitter-Ampel ist hier „Nie", damit allein der Beginn zaehlt. Die Uhr
    steht fest (``_BEGINN_UHR``), damit der Test rund um die Uhr denselben
    Fall prueft; zusaetzlich zum Vorher-Stand mit ``HH:MM`` werden die
    Ortszeiten selbst geprueft (12:00 neu, 14:00 Anker -- Sommerzeit +2 h)."""
    from freezegun import freeze_time

    with freeze_time(_BEGINN_UHR):
        uid = _uid("ac12b")
        trip = _trip("trip-ac12b", alarm_ab={"thunder": "never"}, metrics=("thunder",),
                     levels={"thunder_onset": "standard", "thunder_level": "off"})
        t0 = datetime.now(timezone.utc)
        assert t0 == _BEGINN_UHR, "Voraussetzung: die feste Uhr greift im Pruefling."
        roh: list = []
        subject, body = _mail_lauf(
            uid, trip,
            {"thunder_onset_utc": t0 + timedelta(hours=6)},
            {"thunder_onset_utc": t0 + timedelta(hours=4)},
            roh=roh,
        )
        dringlichkeit = _letzter_alarm(uid)["severity"]
    assert subject == VORHER_BEGINN_BETREFF, subject
    assert body.splitlines() == VORHER_BEGINN_TEXT, body
    assert dringlichkeit == VORHER_BEGINN_DRINGLICHKEIT
    roh_betreff, roh_text = roh[-1]
    assert "Gewitter-Beginn 12:00 (2 h früher)" in roh_betreff, roh_betreff
    assert "Gewitter-Beginn: 14:00 → 12:00 (2 h früher · Segment 1)" in roh_text, roh_text
    assert "Stand: heute 08:00" in roh_text, roh_text


# Vorher-Stand, gemessen auf 85c3024 (vor S2b) mit genau diesen Laeufen
# (Uhrzeiten durch HH:MM ersetzt).
VORHER_NULLGRAD_BETREFF = "[Ampel-Trip] Segment 1 · ↓ Nullgradgrenze: 3.000 m→2.550 m"
VORHER_NULLGRAD_TEXT = [
    "Nullgradgrenze 3.000 m → 2.550 m seit dem Briefing", "",
    "↓ Änderung über deiner Alarm-Schwelle (400 m)", "",
    "Nullgradgrenze · m: 3.000 m ↓ 2.550 m",
    "Änderung 450 m: über Alarm-Schwelle 400 m ✗",
    "Wo & wann: Segment 1", "",
    "Stand: heute HH:MM · verglichen mit HH:MM", "",
    "Abweichungs-Alarm · Open-Meteo",
]
VORHER_BEGINN_BETREFF = "[Ampel-Trip] Segment 1 · Gewitter-Beginn HH:MM (2 h früher)"
VORHER_BEGINN_TEXT = [
    "Gewitter-Beginn verschiebt sich", "",
    "Gewitter-Beginn: HH:MM → HH:MM (2 h früher · Segment 1)", "",
    "Stand: heute HH:MM", "",
    "Abweichungs-Alarm · Open-Meteo",
]
VORHER_BEGINN_DRINGLICHKEIT = "HIGH"
