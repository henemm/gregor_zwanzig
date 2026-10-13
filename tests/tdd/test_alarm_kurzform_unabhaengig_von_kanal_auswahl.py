"""Waechter #2455 (Nachpruefung): Alarm-Kurzform = SMS-Text, unabhaengig von der Telegram-Auswahl.

Alarm-Texte (Trip UND Ortsvergleich) lesen keine Kanal-Auswahl. Bei
``telegram_style=kurzform`` ist der Telegram-Text der SMS-Text und aendert sich
nicht, wenn nur die Telegram-Auswahl wechselt (AC-1/AC-2). Echte lokale
Aufzeichnungs-Server, keine Mocks.
"""
from __future__ import annotations

import dataclasses

import output.channels.telegram as tg_module
from app.models import GPXPoint, MetricConfig, UnifiedWeatherDisplayConfig
from services.notification_service import NotificationService
from tests.helpers.nutzer_tier import nutzer_mit_tier
from tests.tdd.test_telegram_kurzstil_trip_alert import (
    _SMSStub, _TelegramStub, _make_change, _make_segment_data, _make_trip, _settings,
)


def _mit_telegram_auswahl(trip, telegram_ids: list[str]):
    cfg = UnifiedWeatherDisplayConfig(
        trip_id=trip.id,
        metrics=[MetricConfig(metric_id="temperature", enabled=True)],
        per_channel_layouts={
            "sms": [MetricConfig(metric_id="temperature", enabled=True)],
            "telegram": [MetricConfig(metric_id=m, enabled=True) for m in telegram_ids],
        },
    )
    return dataclasses.replace(trip, display_config=cfg)


def _trip_alarm(monkeypatch, uid: str, telegram_ids: list[str]) -> tuple[str, str]:
    tg, sms = _TelegramStub(), _SMSStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg.base_url)
        svc = NotificationService(settings=_settings(sms_port=sms.port), user_id=nutzer_mit_tier(uid))
        trip = _mit_telegram_auswahl(_make_trip("kurzform", send_sms=True), telegram_ids)
        svc.send_deviation_alert(
            trip=trip, weather=[_make_segment_data()], changes=[_make_change()],
            effective_channels={"telegram", "sms"}, telegram_style="kurzform",
        )
        assert len(tg.sent) == 1 and len(sms.received) == 1
        return tg.sent[0]["text"], sms.received[0]["text"]
    finally:
        tg.stop()
        sms.stop()


def test_trip_alarm_kurzform_ist_sms_text_bei_abweichender_telegram_auswahl(monkeypatch):
    """AC-1."""
    tg_a, sms_a = _trip_alarm(monkeypatch, "tdd-2455-na-a", ["temperature"])
    tg_b, sms_b = _trip_alarm(monkeypatch, "tdd-2455-na-b", ["wind", "precipitation", "gust"])
    assert sms_a, "Setup: SMS-Text darf nicht leer sein"
    assert tg_a == sms_a and tg_b == sms_b, "Kurzform: Telegram-Text muss der SMS-Text sein"
    assert tg_b == tg_a, "Telegram-Auswahl darf den Kurzform-Alarm nicht veraendern"


def _vergleich_alarm(monkeypatch, uid: str) -> tuple[str, str]:
    tg, sms = _TelegramStub(), _SMSStub()
    try:
        monkeypatch.setattr(tg_module, "TELEGRAM_API_BASE", tg.base_url)
        svc = NotificationService(settings=_settings(sms_port=sms.port), user_id=nutzer_mit_tier(uid))
        point = GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0)
        svc.send_multi_location_deviation_alert(
            entities=[("Ort A", [point], [_make_change()])],
            effective_channels={"telegram", "sms"}, telegram_style="kurzform",
        )
        assert len(tg.sent) == 1 and len(sms.received) == 1
        return tg.sent[0]["text"], sms.received[0]["text"]
    finally:
        tg.stop()
        sms.stop()


def test_vergleich_alarm_kurzform_ist_sms_text(monkeypatch):
    """AC-2: der Ortsvergleich-Alarm bekommt die Auswahl nicht als Eingabe; Telegram == SMS, stabil."""
    tg_a, sms_a = _vergleich_alarm(monkeypatch, "tdd-2455-na-c")
    tg_b, sms_b = _vergleich_alarm(monkeypatch, "tdd-2455-na-d")
    assert sms_a and tg_a == sms_a and tg_b == sms_b
    assert tg_b == tg_a
