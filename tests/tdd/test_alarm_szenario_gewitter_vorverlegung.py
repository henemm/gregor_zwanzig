"""Issue #2050 Scheibe S2a — Waechter 2: Szenario 3 durch die ECHTE Ausloeseentscheidung.

SPEC: docs/specs/modules/alarm_szenarien_waechter_2_3.md (AC-5..AC-7)

Was die 10 bestehenden Tests in `test_onset_shift_alert.py` NICHT pruefen:
alle zehn setzen an `WeatherChangeDetectionService.detect_changes()` an. Ein
Grep ueber alle 41 Testdateien, die `check_and_send_alerts` aufrufen,
gefiltert auf `thunder_onset`, liefert NULL Treffer. Damit ist insbesondere
die Konfigurations-Weiche `DeviationAlertEngine._select_detector()`
unbewacht: ein Trip kann den Alarmtyp konfigurativ gar nicht erreichen, ohne
dass ein Test das bemerkt. Diese Datei faehrt beides ueber die
`AlarmPruefstrecke` (`zweig="deviation"` -> `check_and_send_alerts()`).

Kein Mock()/patch()/MagicMock: die Kanaltexte kommen ueber den echten
Telegram-Transport (lokaler HTTP-Stub der Pruefstrecke) bzw. `mail_sink`.

ZEITZONE: die Etappe liegt in Island (UTC+0 ganzjaehrig) — die Erwartungen
"17:00"/"15:00" stehen als LITERAL im Test und werden nicht aus derselben
Zonen-Aufloesung gezogen, die der Pruefling benutzt.

WORTLAUT: geprueft wird ausschliesslich #1468-Bestand (beide Uhrzeiten,
Pfeil, Richtungswort) — KEINE Formulierung, die #2020 Scheibe 2 aendert.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from app.models import (
    ForecastMeta, GPXPoint, MetricConfig, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, TripReportConfig, TripSegment,
    UnifiedWeatherDisplayConfig,
)
from app.trip import Stage, Trip, Waypoint

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import (
    _settings_all_channels, _write_tier,
)

# Island: UTC+0 ganzjaehrig, keine Sommerzeit.
ISLAND_LAT, ISLAND_LON = 64.13, -21.90
TAG = date(2026, 8, 20)
_AT = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)

# Die beiden Uhrzeiten des Szenarios (Anker 17 Uhr, frischer Stand 15 Uhr).
ANKER_STUNDE, FRISCH_STUNDE = 17, 15


def _uid(tag: str) -> str:
    return f"tdd-2050-s2a-w2-{tag}-{uuid.uuid4().hex[:6]}"


def _utc(stunde: int) -> datetime:
    """Naiver UTC-Zeitstempel (Hausnorm src/utils/timezone.py)."""
    return datetime(TAG.year, TAG.month, TAG.day, stunde, 0)


def _gewitter_trip(trip_id: str, *, onset_level: str) -> Trip:
    """Trip, dessen Weather-Tab Gewitter beobachtet und dessen
    `metric_alert_levels["thunder_onset"]` auf `onset_level` steht.

    `metrics=[thunder]` ist Pflicht (#961 "Deaktivieren-Luecke":
    `expand_per_metric_levels()` ueberspringt einen Level-Eintrag, dessen
    Katalog-Metrik auf dem Weather-Tab nicht aktiv ist) — und genau EINE
    aktive Metrik, damit der Backfill keine zweite Alarmquelle einschaltet.
    """
    wp = Waypoint(id="G1", name="Start", lat=ISLAND_LAT, lon=ISLAND_LON,
                  elevation_m=1000.0)
    stage = Stage(id="T1", name="Tag 1", date=TAG, waypoints=[wp])
    trip = Trip(
        id=trip_id, name="2050 S2a Gewitter-Trip", stages=[stage],
        display_config=UnifiedWeatherDisplayConfig(
            trip_id=trip_id,
            metrics=[MetricConfig(metric_id="thunder", enabled=True)],
            metric_alert_levels={"thunder_onset": onset_level},
        ),
    )
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=True, alert_on_changes=True,
    )
    trip.alert_cooldown_minutes = 0
    return trip


def _stand(onset_stunde: int) -> list:
    """Ein Etappen-Datenstand mit `thunder_onset_utc` zur genannten Stunde."""
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=ISLAND_LAT, lon=ISLAND_LON, elevation_m=1000.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=ISLAND_LAT + 0.1, lon=ISLAND_LON + 0.1,
                           elevation_m=1200.0, distance_from_start_km=8.0),
        start_time=_utc(6).replace(tzinfo=timezone.utc),
        end_time=_utc(18).replace(tzinfo=timezone.utc),
        duration_hours=12.0, distance_km=8.0, ascent_m=500.0, descent_m=200.0,
    )
    return [SegmentWeatherData(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="test", grid_res_km=1.0),
            data=[],
        ),
        aggregated=SegmentWeatherSummary(thunder_onset_utc=_utc(onset_stunde)),
        fetched_at=_AT - timedelta(hours=1), provider="openmeteo",
    )]


def _lauf(uid: str, trip: Trip):
    _write_tier(uid, "premium")
    strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
    return strecke.lauf(
        at=_AT, zweig="deviation", trip=trip,
        cached_weather=_stand(ANKER_STUNDE), fresh_weather=_stand(FRISCH_STUNDE),
    )


def test_ac5_gewitterbeginn_von_17_auf_15_uhr_loest_genau_einen_alarm_aus():
    """AC-5: Anker 17:00, frischer Stand 15:00, `thunder_onset` aktiv ->
    GENAU EIN Alarm ueber `check_and_send_alerts()`. Unterschied zu den zehn
    bestehenden Tests: hier laufen Konfigurations-Weiche
    (`_select_detector`), Freigabe-Kette und echter Versand mit."""
    uid = _uid("ac5")
    try:
        _clean_user(uid)
        lauf = _lauf(uid, _gewitter_trip("trip-2050-s2a-ac5", onset_level="standard"))
        assert lauf.triggered_count == 1, (
            f"AC-5: die Vorverlegung {ANKER_STUNDE}:00 -> {FRISCH_STUNDE}:00 muss "
            f"ueber die echte Ausloeseentscheidung GENAU EINEN Alarm ergeben. "
            f"War triggered_count={lauf.triggered_count}."
        )
        assert lauf.telegram or lauf.mail, (
            "AC-5: mindestens ein Kanal muss den Alarm ausliefern "
            f"(telegram={lauf.telegram!r} mail={lauf.mail!r})."
        )
    finally:
        _clean_user(uid)


def test_ac6_alarmtext_nennt_beide_uhrzeiten_und_die_richtung_nach_vorne():
    """AC-6: derselbe Lauf wie AC-5; der ausgelieferte Telegram-Text nennt
    17:00 UND 15:00 und macht durch Pfeil + Richtungswort erkennbar, dass
    sich der Beginn nach VORNE verschoben hat (#1468-Bestand)."""
    uid = _uid("ac6")
    try:
        _clean_user(uid)
        lauf = _lauf(uid, _gewitter_trip("trip-2050-s2a-ac6", onset_level="standard"))
        assert lauf.telegram, (
            f"AC-6 Vorbedingung: der Lauf muss ueber Telegram ausliefern "
            f"(triggered_count={lauf.triggered_count})."
        )
        text = "\n".join(lauf.telegram)
        for uhrzeit in (f"{ANKER_STUNDE}:00", f"{FRISCH_STUNDE}:00"):
            assert uhrzeit in text, (
                f"AC-6: der Alarmtext nennt {uhrzeit} nicht.\n{text}"
            )
        assert "→" in text, (
            f"AC-6: der Alarmtext zeigt die Verschiebung nicht als "
            f"'alt → neu' (#1468-Bestand).\n{text}"
        )
        assert "früher" in text, (
            f"AC-6: der Alarmtext benennt die Richtung nicht — ein um zwei "
            f"Stunden VORVERLEGTER Beginn muss als 'früher' erscheinen.\n{text}"
        )
        assert "später" not in text, (
            f"AC-6: der Alarmtext dreht die Richtung um.\n{text}"
        )
    finally:
        _clean_user(uid)


def test_ac7_abgeschalteter_alarmtyp_verhindert_den_alarm_bei_gleicher_wetterlage():
    """AC-7: identischer Lauf zu AC-5, nur `metric_alert_levels`-Level "off"
    -> KEIN Alarm, obwohl die Wetterdaten unveraendert denselben
    Gewitterbeginn-Sprung zeigen. Die Positivkontrolle (aktiver Level, eigene
    `user_id`) laeuft im selben Test: ohne sie waere die Gegenprobe auch dann
    gruen, wenn ueberhaupt nichts ausloest."""
    uid, kontrolle = _uid("ac7"), _uid("ac7-ctrl")
    try:
        _clean_user(uid)
        _clean_user(kontrolle)
        lauf_kontrolle = _lauf(
            kontrolle, _gewitter_trip("trip-2050-s2a-ac7", onset_level="standard"),
        )
        assert lauf_kontrolle.triggered_count == 1, (
            "AC-7 Positivkontrolle: derselbe Aufbau MIT aktivem Level muss "
            f"ausloesen (war {lauf_kontrolle.triggered_count}) — sonst prueft "
            "die Gegenprobe unten nichts."
        )

        lauf = _lauf(uid, _gewitter_trip("trip-2050-s2a-ac7", onset_level="off"))
        assert lauf.triggered_count == 0, (
            f"AC-7: bei abgeschaltetem `thunder_onset`-Level darf die "
            f"Konfigurations-Weiche (_select_detector) den Alarmtyp gar nicht "
            f"erst auswerten. War triggered_count={lauf.triggered_count}."
        )
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms), (
            f"AC-7: kein Kanal darf etwas ausliefern: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} "
            f"premium_sms={lauf.premium_sms!r}"
        )
    finally:
        _clean_user(uid)
        _clean_user(kontrolle)
