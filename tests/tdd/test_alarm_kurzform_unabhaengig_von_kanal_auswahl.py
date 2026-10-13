"""Waechter #2455 (Nachpruefung): Alarm-Kurzform = SMS-Text, unabhaengig von der Telegram-Auswahl.

Alarm-Texte (Trip UND Ortsvergleich) lesen keine Kanal-Auswahl. Bei
``telegram_style=kurzform`` ist der Telegram-Text der SMS-Text und aendert sich
nicht, wenn nur die Telegram-Auswahl wechselt (AC-1/AC-2). Echte lokale
Aufzeichnungs-Server, keine Mocks.
"""
from __future__ import annotations

import dataclasses

import pytest

import output.channels.telegram as tg_module
from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from services.notification_service import NotificationService
from tests.helpers.nutzer_tier import nutzer_mit_tier
from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import engine_naht, fixture_dict, transport_einrichten
from tests.tdd.test_compare_alarm_einstellung_auslieferung_kette import _lauf, _nutzer
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


@pytest.fixture
def mit(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def _vergleich_alarm(mit, telegram_ids: list[str]) -> tuple[str, str]:
    """Echter Eingang: Preset-JSON auf Platte -> ``CompareAlertService`` -> Aufzeichner."""
    vorlage = fixture_dict("alarm_kanaele")
    vorlage["send_telegram"] = vorlage["send_sms"] = False
    vorlage["alert_channels"] = {"email": False, "telegram": True, "sms": True, "premium_sms": False}
    vorlage["alert_channel_thresholds"] = {}
    vorlage["display_config"]["telegram_style"] = "kurzform"
    vorlage["display_config"]["channel_active_metrics"] = {
        "sms": [{"metric_id": "temperature", "aggregation": "max"}],
        "telegram": [{"metric_id": m, "aggregation": "max"} for m in telegram_ids],
    }
    n = _nutzer(vorlage, "premium")
    snap, gemeldet, _ = _lauf(mit, "abweichung", n, "HIGH")
    assert gemeldet == 1, "Vorbedingung: der Alarmlauf hat versendet"
    assert snap.sendungen("telegram") and snap.sendungen("sms"), snap
    return snap.sendungen("telegram")[-1]["body"], snap.sendungen("sms")[-1]["body"]


def test_vergleich_alarm_kurzform_ist_sms_text_bei_abweichender_telegram_auswahl(mit):
    """AC-2: Ortsvergleich-Alarm (Abweichung) durch ``CompareAlertService`` mit
    ``telegram_style=kurzform``: Telegram-Text == SMS-Text, und er bleibt gleich, wenn nur
    ``channel_active_metrics.telegram`` des Presets wechselt (SMS-Auswahl identisch)."""
    tg_a, sms_a = _vergleich_alarm(mit, ["temperature"])
    tg_b, sms_b = _vergleich_alarm(mit, ["wind", "precipitation", "gust"])
    assert sms_a, "Setup: SMS-Text darf nicht leer sein"
    assert tg_a == sms_a and tg_b == sms_b, "Kurzform: Telegram-Text muss der SMS-Text sein"
    assert tg_b == tg_a, "Telegram-Auswahl darf den Kurzform-Alarm nicht veraendern"
