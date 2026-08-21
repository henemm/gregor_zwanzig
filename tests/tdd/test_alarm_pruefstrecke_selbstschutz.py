"""Issue #2050 Scheibe S1: Alarm-Prüfstrecke Selbstschutz.

Jeder Test deckt einen AC aus `docs/specs/modules/alarm_pruefstrecke.md` ab
und nutzt `AlarmPruefstrecke` aus `tests.helpers.alarm_pruefstrecke` (Phase 6
GREEN) gegen die echte Auslöseentscheidung.

Kein Mock()/patch()/MagicMock: echte `RadarNowcastService`-Unterklasse
(`_GuaranteedWetRadar`, Vorbild #952) als DI-Seam, `monkeypatch.setattr` auf
echten Modulfunktionen für die Gate-Sperren (AC-4/5/6). Patch-Ziel für
AC-5/AC-6 ist bewusst `services.trip_alert`, NICHT `services.alert_gate`:
`trip_alert.py` importiert `check_nowcast_gate`/`check_official_alert_gate`
per `from ... import` auf Modulebene (Zeile 22-27) — ein Patch auf
`alert_gate` selbst griffe dort nicht (Vorbild dafür bereits etabliert in
`test_issue_1088_official_alert_triggers.py:800,848`, das genau dieselben
zwei Bausteine auf `trip_alert_mod` patcht). `check_briefing_imminent`
(AC-4) importiert `trip_alert.py` dagegen LOKAL PRO AUFRUF (Zeile 967) —
dort wirkt ein Patch auf `alert_gate` sehr wohl.

SPEC: docs/specs/modules/alarm_pruefstrecke.md
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from freezegun import freeze_time

from app.config import Settings
from app.loader import get_data_dir, save_trip
from app.models import TripReportConfig
from services.alert_gate import GateResult
from services.official_alerts.models import OfficialAlert
from services.throttle_store import ThrottleStore

from tests.tdd.test_952_onset_alert_fidelity import (
    _clean_user, _GuaranteedWetRadar, _trip_with_active_segment,
)
from tests.tdd.test_issue_1070_daily_alert_limit import _deviation_trip, _weather_data

from tests.helpers.alarm_pruefstrecke import AlarmPruefstrecke

_AT = datetime(2026, 4, 5, 10, 0, tzinfo=timezone.utc)


def _uid(tag: str) -> str:
    return f"tdd-2050-s1-{tag}-{uuid.uuid4().hex[:6]}"


def _settings_all_channels() -> Settings:
    return Settings().model_copy(update={
        "smtp_host": "smtp.test.invalid", "smtp_user": "alert@test.invalid",
        "smtp_pass": "secret", "mail_to": "gregor-test@henemm.com",
        "smtp_port": 587, "is_test_mode": False,
        "telegram_bot_token": "test-token-2050", "telegram_chat_id": "99999",
        "sms_to": "+41791234567", "seven_api_key": "test-stub-key",
    })


def _write_premium_profile(uid: str, at: datetime) -> None:
    """Lernt eine frische Garmin-Rückadresse (Pflicht für Premium-SMS,
    `output/channels/premium_sms.py`) und setzt den Tier auf `premium`
    (kein Tageslimit, s. #1070 AC-3)."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    profile = {
        "id": uid, "tier": "premium",
        "premium_sms_reply_to": "+41791234567",
        "premium_sms_reply_at": (at - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }
    (d / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _write_tier(uid: str, tier: str) -> None:
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}), encoding="utf-8")


def _radar_trip(uid: str, trip_id: str, **flags) -> object:
    """Baut das Trip-Fixture INNERHALB von `freeze_time(_AT)`, weil
    `_trip_with_active_segment` sein Ankunftsfenster über `datetime.now()`
    verankert — ohne Freeze wäre das Segment zur gestellten Laufzeit `_AT`
    nicht mehr aktiv."""
    config = TripReportConfig(trip_id=trip_id, alert_on_changes=True, **flags)
    with freeze_time(_AT):
        trip = _trip_with_active_segment(trip_id, config)
    save_trip(trip, user_id=uid)
    return trip


def _cached_fresh():
    return [_weather_data(precip_sum_mm=2.0)], [_weather_data(precip_sum_mm=18.0)]


def test_ac1_zweiter_lauf_liest_den_von_lauf_eins_gebuchten_cooldown():
    """Lauf 2 schweigt wegen des von Lauf 1 gebuchten Cooldowns — eine
    Kontrolle ohne Lauf 1 löst bei identischen Eingangsdaten trotzdem aus."""
    uid, ctrl = _uid("ac1"), _uid("ac1-ctrl")
    _clean_user(uid); _clean_user(ctrl)
    try:
        trip = _deviation_trip("trip-ac1")
        trip.alert_cooldown_minutes = 120
        cached, fresh = _cached_fresh()
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(at=_AT, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh)
        assert lauf1.triggered_count == 1, "Voraussetzung: Lauf 1 muss auslösen"

        at2 = _AT + timedelta(minutes=30)
        lauf2 = strecke.lauf(at=at2, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh)
        assert lauf2.triggered_count == 0, "Lauf 2 muss durch den Cooldown aus Lauf 1 unterdrückt sein"

        kontrolle = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        lauf_k = kontrolle.lauf(at=at2, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh)
        assert lauf_k.triggered_count == 1, (
            "Gegenprobe: dieselben Eingangsdaten zum selben Zeitpunkt OHNE "
            "Lauf 1 müssen auslösen — Lauf 2s Stille kommt vom gebuchten "
            "Zustand, nicht von unveränderten Eingangsdaten"
        )
    finally:
        _clean_user(uid); _clean_user(ctrl)


def test_ac1b_jeder_lauf_bekommt_eine_eigene_service_instanz():
    """Jeder `.lauf()` baut eine EIGENE `TripAlertService` — `mail_sink` wird
    nur im Konstruktor gesetzt (`trip_alert.py:209`) und ist eine Closure
    über die `mail_calls`-Liste GENAU DIESES Aufrufs. Bei einer über Läufe
    wiederverwendeten Instanz schriebe der Service weiterhin in Lauf 1s
    (bereits verlassene) Liste — Lauf 2s `.mail` bliebe strukturell leer,
    obwohl er auslöst."""
    uid = _uid("ac1b")
    _clean_user(uid)
    try:
        _write_tier(uid, "standard")  # #1555: sonst blockt das Tageslimit den 2. Alarm
        trip1, trip2 = _deviation_trip("trip-ac1b-a"), _deviation_trip("trip-ac1b-b")
        trip1.report_config.send_email = trip2.report_config.send_email = True
        cached, fresh = _cached_fresh()
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf1 = strecke.lauf(at=_AT, zweig="deviation", trip=trip1, cached_weather=cached, fresh_weather=fresh)
        assert lauf1.triggered_count == 1 and lauf1.mail, "Voraussetzung: Lauf 1 muss auslösen und Mail liefern"

        lauf2 = strecke.lauf(
            at=_AT + timedelta(minutes=1), zweig="deviation", trip=trip2,
            cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf2.triggered_count == 1 and lauf2.mail, (
            "Lauf 2 muss SEINE EIGENE Mail-Sink-Liste befüllt sehen — bei einer "
            "über Läufe wiederverwendeten Service-Instanz bliebe lauf2.mail leer"
        )
    finally:
        _clean_user(uid)


def test_ac2_gleicher_lauf_innerhalb_und_ausserhalb_der_ruhezeit_entscheidet_unterschiedlich():
    """Identische Eingangsdaten, nur die gestellte Uhr wechselt zwischen
    Ruhezeit (22-06 Uhr lokal) und Normalzeit."""
    uid = _uid("ac2")
    _clean_user(uid)
    try:
        trip = _deviation_trip("trip-ac2")
        trip.alert_cooldown_minutes = 0
        trip.alert_quiet_from, trip.alert_quiet_to = "22:00", "06:00"
        cached, fresh = _cached_fresh()
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        innerhalb = strecke.lauf(
            at=datetime(2026, 4, 5, 23, 0, tzinfo=timezone.utc), zweig="deviation",
            trip=trip, cached_weather=cached, fresh_weather=fresh,
        )
        ausserhalb = strecke.lauf(
            at=datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc), zweig="deviation",
            trip=trip, cached_weather=cached, fresh_weather=fresh,
        )
        assert innerhalb.triggered_count == 0, "23:00 UTC liegt in der lokalen Ruhezeit"
        assert ausserhalb.triggered_count == 1, "10:00 UTC liegt außerhalb der Ruhezeit"
    finally:
        _clean_user(uid)


def test_ac3_telegram_ratenbegrenzung_aus_lauf_eins_ueberlebt_nicht_bis_lauf_zwei(monkeypatch):
    """Lauf 1 erschöpft die prozessweite Telegram-Ratenbegrenzung
    (`max_per_window=1`). Ohne Cache-Reset bliebe Lauf 2 trotz eigener,
    unabhängig auslösefähiger Eingangsdaten stumm — die Gegenprobe am Ende
    unterdrückt den Reset gezielt und zeigt genau das."""
    uid, ctrl = _uid("ac3"), _uid("ac3-ctrl")
    _clean_user(uid); _clean_user(ctrl)
    try:
        # Free-Tier-Reserve (#1555) ließe den zweiten Deviation-Alarm schon
        # am Tageslimit scheitern, bevor die Ratenbegrenzung geprüft wird —
        # `standard` hat genug Budget, um NUR die Ratenbegrenzung zu messen.
        _write_tier(uid, "standard"); _write_tier(ctrl, "standard")
        settings = _settings_all_channels().model_copy(
            update={"telegram_rate_limit_max_per_window": 1},
        )
        cached, fresh = _cached_fresh()
        trip1, trip2 = _deviation_trip("trip-ac3-a"), _deviation_trip("trip-ac3-b")
        trip1.alert_cooldown_minutes = trip2.alert_cooldown_minutes = 0
        strecke = AlarmPruefstrecke(user_id=uid, settings=settings)
        lauf1 = strecke.lauf(at=_AT, zweig="deviation", trip=trip1, cached_weather=cached, fresh_weather=fresh)
        assert lauf1.telegram, "Voraussetzung: Lauf 1 muss den einzigen Ratenlimit-Slot verbrauchen"

        # 1s Abstand, nicht mehr: `freeze_time` verschiebt auch
        # `time.monotonic()` (Basis der Ratenbegrenzung) — nahe der
        # Fensterlänge (60s) verfiele der Slot aus Lauf 1 ohnehin natürlich,
        # unabhängig vom Reset.
        lauf2 = strecke.lauf(
            at=_AT + timedelta(seconds=1), zweig="deviation",
            trip=trip2, cached_weather=cached, fresh_weather=fresh,
        )
        assert lauf2.triggered_count == 1 and lauf2.telegram, (
            "Lauf 2 muss trotz Lauf 1s Ratenlimit-Verbrauch senden — der "
            "Cache-Reset der Prüfstrecke darf Lauf 1s Zustand nicht durchschlagen lassen"
        )

        # Gegenprobe: derselbe Ablauf, aber der Reset wird gezielt
        # unterdrückt -- ohne ihn MUSS Lauf 2 scheitern, sonst bewiese der
        # Haupttest oben nichts über den Reset selbst. `SEND_SLOT_MAX_WAIT_
        # SECONDS=0` lässt die Drossel SOFORT abbrechen statt real zu warten
        # -- unter `freeze_time` steht `time.monotonic()` still, ein
        # positiver Wert liefe in eine Endlosschleife (real erlebt: Timeout).
        import output.channels.telegram as telegram_mod
        import tests.helpers.alarm_pruefstrecke as harness_mod
        monkeypatch.setattr(telegram_mod, "SEND_SLOT_MAX_WAIT_SECONDS", 0)

        trip3, trip4 = _deviation_trip("trip-ac3-c"), _deviation_trip("trip-ac3-d")
        trip3.alert_cooldown_minutes = trip4.alert_cooldown_minutes = 0
        kontrolle = AlarmPruefstrecke(user_id=ctrl, settings=settings)
        lauf3 = kontrolle.lauf(at=_AT, zweig="deviation", trip=trip3, cached_weather=cached, fresh_weather=fresh)
        assert lauf3.telegram, "Voraussetzung Gegenprobe: erster Lauf muss senden"

        monkeypatch.setattr(harness_mod, "reset_telegram_rate_limit_for_tests", lambda: None)
        lauf4 = kontrolle.lauf(
            at=_AT + timedelta(seconds=1), zweig="deviation",
            trip=trip4, cached_weather=cached, fresh_weather=fresh,
        )
        # `triggered_count` bleibt UNGEPRÜFT: er zählt bereits den Versuch
        # (Anti-Pattern #656, `notification_service.py:104-110/1059`), nicht
        # die Zustellung. `telegram` (Stub-Abgriff) ist der einzige Nachweis.
        assert not lauf4.telegram, (
            "Gegenprobe: OHNE Cache-Reset muss Lauf 2 am durchgeschlagenen "
            "Telegram-Ratenlimit aus Lauf 1 scheitern — sonst beweist der "
            "Haupttest nichts über den Reset selbst"
        )
    finally:
        _clean_user(uid); _clean_user(ctrl)


def test_ac4_briefing_naehe_sperre_unterdrueckt_deviation_alarm_auf_allen_kanaelen(monkeypatch):
    """`check_briefing_imminent` erzwungen gesperrt — ein bekannt
    auslösendes Deviation-Szenario darf über KEINEN Kanal etwas liefern."""
    import services.alert_gate as alert_gate_mod
    monkeypatch.setattr(alert_gate_mod, "check_briefing_imminent", lambda **kw: True)

    uid = _uid("ac4")
    _clean_user(uid)
    try:
        trip = _deviation_trip("trip-ac4")
        trip.alert_cooldown_minutes = 0
        cached, fresh = _cached_fresh()
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(at=_AT, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh)
        assert lauf.triggered_count == 0
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms)
    finally:
        _clean_user(uid)


def test_ac5_amtliches_gate_gesperrt_unterdrueckt_offiziellen_alarm_auf_allen_kanaelen(monkeypatch):
    """`check_official_alert_gate` erzwungen gesperrt — eine amtliche
    Warnung, die sonst versendet würde, darf über KEINEN Kanal raus."""
    import services.trip_alert as trip_alert_mod
    monkeypatch.setattr(
        trip_alert_mod, "check_official_alert_gate",
        lambda **kw: GateResult(False, "test-sperre"),
    )
    uid = _uid("ac5")
    _clean_user(uid)
    try:
        trip = _deviation_trip("trip-ac5")
        trip.alert_cooldown_minutes = 0
        alert = OfficialAlert(source="tdd-2050-ac5", hazard="thunderstorm", level=3, label="Gewitterwarnung")
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(at=_AT, zweig="official", trip=trip, official_notices=[(alert, ["1"])])
        assert lauf.triggered_count == 0
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms)
    finally:
        _clean_user(uid)


def test_ac6_nowcast_gate_gesperrt_unterdrueckt_radar_onset_auf_allen_kanaelen(monkeypatch):
    """`check_nowcast_gate` erzwungen gesperrt — ein garantierter Radar-Onset
    (Vorbild `_GuaranteedWetRadar`) darf über KEINEN Kanal raus."""
    import services.trip_alert as trip_alert_mod
    monkeypatch.setattr(
        trip_alert_mod, "check_nowcast_gate",
        lambda **kw: GateResult(False, "test-sperre"),
    )
    uid = _uid("ac6")
    _clean_user(uid)
    try:
        trip = _radar_trip(uid, "trip-ac6", send_email=True)
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(at=_AT, zweig="radar", trip=trip, radar_service=_GuaranteedWetRadar(onset_minutes=12))
        assert lauf.triggered_count == 0
        assert not (lauf.mail or lauf.telegram or lauf.sms or lauf.premium_sms)
    finally:
        _clean_user(uid)


def test_ac7_vorbelegter_cooldown_unterdrueckt_einen_sonst_faelligen_alarm():
    """Cooldown wird VOR dem Lauf über `ThrottleStore.record` gesetzt — der
    Lauf zeigt die Wirkung, eine Kontrolle ohne Vorbelegung löst aus."""
    uid, ctrl = _uid("ac7"), _uid("ac7-ctrl")
    _clean_user(uid); _clean_user(ctrl)
    try:
        trip = _deviation_trip("trip-ac7")
        trip.alert_cooldown_minutes = 120
        cached, fresh = _cached_fresh()
        ThrottleStore(uid).record("trip", trip.id, _AT - timedelta(minutes=10))

        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(at=_AT, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh)
        assert lauf.triggered_count == 0, "Vorbelegter Cooldown muss den sonst fälligen Alarm unterdrücken"

        kontrolle = AlarmPruefstrecke(user_id=ctrl, settings=_settings_all_channels())
        lauf_k = kontrolle.lauf(at=_AT, zweig="deviation", trip=trip, cached_weather=cached, fresh_weather=fresh)
        assert lauf_k.triggered_count == 1, "Gegenprobe: ohne Vorbelegung muss derselbe Lauf auslösen"
    finally:
        _clean_user(uid); _clean_user(ctrl)


def test_ac8_ausloesender_lauf_liefert_gerenderten_inhalt_auf_allen_vier_kanaelen():
    """Radar-Onset über alle vier Kanäle — Inhalt kommt ausschließlich über
    `mail_sink` bzw. die lokalen Stubs, kein echter externer Versand."""
    uid = _uid("ac8")
    _clean_user(uid)
    try:
        _write_premium_profile(uid, _AT)
        trip = _radar_trip(
            uid, "trip-ac8", send_email=True, send_telegram=True,
            send_sms=True, send_premium_sms=True,
        )
        strecke = AlarmPruefstrecke(user_id=uid, settings=_settings_all_channels())
        lauf = strecke.lauf(at=_AT, zweig="radar", trip=trip, radar_service=_GuaranteedWetRadar(onset_minutes=12))
        assert lauf.triggered_count == 1
        assert lauf.mail and lauf.telegram and lauf.sms and lauf.premium_sms, (
            f"Alle vier Kanäle müssen Inhalt liefern: mail={lauf.mail!r} "
            f"telegram={lauf.telegram!r} sms={lauf.sms!r} premium_sms={lauf.premium_sms!r}"
        )
    finally:
        _clean_user(uid)
