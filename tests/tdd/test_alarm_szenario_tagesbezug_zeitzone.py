"""Issue #2050 Scheibe S3a — Waechter Sz 9 (B-2): Tagesbezug ueber

Mitternacht im Radar-Zweig, gemessen ueber die ECHTE Ausloeseentscheidung.

SPEC: docs/specs/modules/alarm_szenarien_waechter_4_9_11.md (AC-3, AC-4, AC-5)

`onset_day_offset` (`trip_alert.py:1606-1626`, `day_offset()`,
`utils/timezone.py:138-143`) macht einen ueber Mitternacht rutschenden
Regenbeginn eindeutig -- der Renderer-Baustein `_time_with_day()`
(`render.py:214-242`) haengt bei `day_offset == 1` das Wort "morgen" an,
`_sms_onset_time()` (`render.py:758-771`) das additive Suffix `+1`. Diese
Datei prueft, dass die ECHTE Kette (`check_radar_alerts()` -> Nowcast ->
Renderer) den Tagesbezug traegt, nicht nur der isolierte Renderer-Aufruf
(den bereits `test_alert_onset_day_rollover.py` bewacht).

Trip-Ort: Island (Atlantic/Reykjavik, ganzjaehrig UTC+0) -- Ortszeit ==
Weltzeit, keine zweite Zonenumrechnung verwaescht die Erwartungswerte.

Kein Mock()/patch()/MagicMock: echter `RadarNowcastService` an der DI-Naht
`frame_source=`, Kanaltexte ueber den echten Mail-/Telegram-/seven.io-
Transport der `AlarmPruefstrecke`.
"""
from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime, time as time_type, timedelta, timezone

from freezegun import freeze_time

from app.loader import save_trip
from app.models import TripReportConfig
from app.trip import Stage, Trip, TimeWindow, Waypoint
from services.radar_service import RadarNowcastService

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _settings_all_channels, _write_tier,
)

# Island: UTC+0 ganzjaehrig, keine Sommerzeit -- Ortszeit == UTC.
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
TAG = date_type(2026, 5, 10)
_AT = datetime(2026, 5, 10, 23, 50, tzinfo=timezone.utc)  # 23:50 Ortszeit
# AC-5-Kontrast: bewusst FRUEHER als _AT, damit sowohl Beginn ALS AUCH das
# vom Renderer zusaetzlich gebildete Ende (`event_end_day_offset`, #2051 S1)
# sicher vor Mitternacht bleiben -- bei _AT (23:50) reicht die Deckung eines
# einzelnen Frames (+15 Min Default) sonst selbst ueber Mitternacht hinaus
# und ein "morgen" am ENDE wuerde die Kontrastprobe faelschlich verunreinigen.
_AT_KONTRAST = datetime(2026, 5, 10, 20, 0, tzinfo=timezone.utc)  # 20:00 Ortszeit


def _uid(tag: str) -> str:
    return f"tdd-2050-s3a-sz9-{tag}-{uuid.uuid4().hex[:6]}"


def _sz9_trip(trip_id: str) -> Trip:
    """Trip mit einem Segment, das bei `_AT` (23:50 Ortszeit) aktiv ist --
    `arrival_override` bestimmt die Segmentgrenzen (Prioritaet vor
    `arrival_calculated`, `trip_segments.py:46-49`), unabhaengig vom
    Compute-on-Save der Naismith-Berechnung beim Speichern."""
    wp0 = Waypoint(
        id="G1", name="Start", lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=100.0,
        time_window=TimeWindow(start=time_type(0, 0), end=time_type(19, 0)),
        arrival_override="19:00",
    )
    wp1 = Waypoint(
        id="G2", name="Ziel", lat=ISLAND_LAT + 0.05, lon=ISLAND_LON + 0.05,
        elevation_m=150.0,
        time_window=TimeWindow(start=time_type(19, 0), end=time_type(23, 59)),
        arrival_override="23:59",
    )
    stage = Stage(
        id="T1", name="Tag 1", date=TAG, start_time=time_type(19, 0),
        waypoints=[wp0, wp1],
    )
    trip = Trip(id=trip_id, name="2050 S3a Sz9 Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, send_sms=True,
        alert_on_changes=True,
    )
    return trip


def _aufbau(uid: str, tag: str, *, at: datetime = _AT) -> Trip:
    """SMS ist ein Tier-Merkmal (`sms_allowed()`, `user_tier.py:9-20`) --
    ohne `premium`-Tier faellt der SMS-Kanal aus `_effective_alert_channels`
    heraus, unabhaengig von `report_config.send_sms`."""
    _clean_user(uid)
    _write_tier(uid, "premium")
    trip = _sz9_trip(f"trip-s3a-sz9-{tag}")
    with freeze_time(at):
        save_trip(trip, user_id=uid)
    return trip


def _quelle(versatz_min: float):
    """Ein einzelnes nasses Frame `versatz_min` Minuten nach der gestellten
    Uhr -- der Regenbeginn, den `RadarNowcastService` daraus ableitet. Kein
    nachfolgendes trockenes Frame -> das Ende bleibt die Untergrenze der
    Deckung (fuer AC-3/AC-4 unerheblich, dort wird nur der BEGINN geprueft)."""
    def _frames(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        jetzt = datetime.now(timezone.utc)
        return [RadarFrame(timestamp=jetzt + timedelta(minutes=versatz_min), precip_mm_h=5.0)]
    return _frames


def _quelle_kontrast():
    """AC-5: nasses Frame bei +5 Min, TROCKENES Frame bei +20 Min -- ein
    BEOBACHTETES Ende (letztes nasses Frame, +5 Min), damit weder Beginn noch
    Ende in die Naehe von Mitternacht geraten (s. `_AT_KONTRAST`)."""
    def _frames(lat: float, lon: float) -> list:
        from providers.brightsky import RadarFrame
        jetzt = datetime.now(timezone.utc)
        return [
            RadarFrame(timestamp=jetzt + timedelta(minutes=5), precip_mm_h=5.0),
            RadarFrame(timestamp=jetzt + timedelta(minutes=20), precip_mm_h=0.0),
        ]
    return _frames


def _radar(quelle) -> RadarNowcastService:
    return RadarNowcastService(frame_source=quelle)


def _lauf(uid: str, trip: Trip, quelle, *, at: datetime = _AT):
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    return strecke.lauf(at=at, zweig="radar", trip=trip, radar_service=_radar(quelle))


def _kanaltext(lauf) -> str:
    mail = "\n".join(f"{betreff}\n{koerper}" for betreff, koerper in lauf.mail)
    return mail + "\n" + "\n".join(lauf.telegram)


def test_ac3_regenbeginn_ueber_mitternacht_traegt_tagesbezug_im_langtext():
    """AC-3: Prueflauf um 23:50 Ortszeit, abgeleiteter Regenbeginn 33 Minuten
    spaeter auf 00:23 des Folgetags (`onset_day_offset == 1`) -> Mail-/
    Telegram-Text traegt einen erkennbaren Tagesbezug ("morgen") statt der
    nackten, mehrdeutigen Uhrzeit."""
    uid = _uid("ac3")
    try:
        trip = _aufbau(uid, "ac3")
        lauf = _lauf(uid, trip, _quelle(33))
        assert lauf.triggered_count == 1, (
            f"AC-3 Vorbedingung: der Lauf muss ausloesen (war "
            f"{lauf.triggered_count})."
        )
        text = _kanaltext(lauf)
        assert "morgen 00:23" in text, (
            f"AC-3: kein erkennbarer Tagesbezug fuer den Mitternachts-"
            f"Ueberlauf ('morgen 00:23' erwartet).\n{text}"
        )
    finally:
        _clean_user(uid)


def test_ac4_sms_kurzform_traegt_additiven_tagessuffix():
    """AC-4: derselbe ausloesende Lauf wie AC-3; der SMS-Text traegt den
    additiven Tagessuffix `+1` (`_sms_onset_time()`), unterscheidbar von
    einer taggleichen Beginnzeit ohne Suffix."""
    uid = _uid("ac4")
    try:
        trip = _aufbau(uid, "ac4")
        lauf = _lauf(uid, trip, _quelle(33))
        assert lauf.triggered_count == 1, (
            f"AC-4 Vorbedingung: der Lauf muss ausloesen (war "
            f"{lauf.triggered_count})."
        )
        sms_text = "\n".join(lauf.sms)
        assert "0:23+1" in sms_text, (
            f"AC-4: die Kurzform traegt den Tagessuffix '+1' nicht.\n{sms_text}"
        )
        ohne_suffix = sms_text.replace("0:23+1", "")
        assert "0:23" not in ohne_suffix, (
            f"AC-4: '0:23' erscheint auch OHNE das '+1'-Suffix -- die "
            f"Kurzform muss den Tagessuffix IMMER an dieser Uhrzeit "
            f"tragen.\n{sms_text}"
        )
    finally:
        _clean_user(uid)


def test_ac5_regenbeginn_noch_am_selben_tag_bleibt_ohne_tagesbezug():
    """AC-5: unabhaengiger Lauf mit identischem Aufbau, aber Regenbeginn noch
    am selben Ortstag (`onset_day_offset == 0`) -> weder Mail-/Telegram-Text
    noch SMS-Text tragen einen Tagesbezug/Suffix -- der Unterschied zu
    AC-3/AC-4 kommt ausschliesslich vom Feldwert, nicht von einer anderen
    Textvorlage."""
    uid = _uid("ac5")
    try:
        trip = _aufbau(uid, "ac5", at=_AT_KONTRAST)
        # 20:00 + 5 Min Beginn, + 20 Min beobachtetes Ende -- beides deutlich
        # vor Mitternacht (s. `_quelle_kontrast`-Docstring).
        lauf = _lauf(uid, trip, _quelle_kontrast(), at=_AT_KONTRAST)
        assert lauf.triggered_count == 1, (
            f"AC-5 Vorbedingung: der Lauf muss ausloesen (war "
            f"{lauf.triggered_count})."
        )
        text = _kanaltext(lauf)
        assert "20:05" in text, f"AC-5 Vorbedingung: die Beginnzeit 20:05 fehlt.\n{text}"
        assert "morgen" not in text, (
            f"AC-5: ohne Tageswechsel darf kein 'morgen'-Zusatz erscheinen.\n{text}"
        )
        sms_text = "\n".join(lauf.sms)
        assert "+" not in sms_text, (
            f"AC-5: die Kurzform darf ohne Tageswechsel keinen "
            f"Tagessuffix tragen.\n{sms_text}"
        )
    finally:
        _clean_user(uid)
