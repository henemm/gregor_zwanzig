"""Alarm-Vorschau folgt je Kanal der Anzeige-Konfiguration des Trips (Issue #1737, AC-2 + AC-11).

Ein Trip zeigt Boeen in der E-Mail EINFACH (Wort, z. B. "sehr stark") und in Telegram ROH (Zahl).
Die Vorschau ueber den echten Router-Einstieg mit dem Oberflaechen-Body traegt je Kanal dieselben
Stundenzeilen wie der Versand -- also E-Mail EINFACH, Telegram ROH, nicht beide roh.

Naehte wie AC-11: Anker im nutzergebundenen Speicher, frische Reihe ueber ``GZ_TEST_FIXTURE_DIR``.
"""
from __future__ import annotations

from tests.integration.test_briefing_preview_bundle import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_hour_rows import (
    TRIP_STURM, _cell, _plant, _rows, _trip_anker_schreiben, _trip_body, _trip_versand,
)
from tests.tdd.test_alert_preview_real_stage_ids import _trip_mit_echter_etappe


def _einfach_in_mail_roh_in_telegram(uid: str):
    from app.loader import save_trip
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    trip = _trip_mit_echter_etappe(uid)
    trip.display_config = UnifiedWeatherDisplayConfig(
        trip_id=trip.id, metrics=[MetricConfig(metric_id="gust", enabled=True)],
        metric_alert_levels={"wind_gust": "standard"},
        per_channel_layouts={
            "email": [MetricConfig(metric_id="gust", enabled=True, format_mode="simplified")],
            "telegram": [MetricConfig(metric_id="gust", enabled=True, format_mode="raw")],
        },
    )
    save_trip(trip, user_id=uid)
    return trip


def test_vorschau_zeigt_je_kanal_den_anzeigemodus_des_trips_wie_der_versand(
    env, monkeypatch, tmp_path,  # noqa: F811
):
    from api.routers.validator import AlertPreviewBody, alert_preview

    uid = env
    trip = _einfach_in_mail_roh_in_telegram(uid)
    _trip_anker_schreiben(monkeypatch, tmp_path, uid, trip, {}, "anker-modus")
    _plant(tmp_path, monkeypatch, "sturm", TRIP_STURM)
    assert _cell("gust", 90.0, "simplified") != _cell("gust", 90.0, "raw"), (
        "Vorbedingung: EINFACH und ROH sehen bei Boeen verschieden aus")

    mails, tgs = _trip_versand(monkeypatch, uid, trip)
    mail_zeilen, tg_zeilen = _rows(mails[0]), _rows(tgs[0])
    assert len(mail_zeilen) == 3 and len(tg_zeilen) == 3, "Vorbedingung: Versand traegt Zeilen"
    assert _cell("gust", 90.0, "simplified") in mail_zeilen[-1][1], (
        f"Vorbedingung: Versand-Mail ist EINFACH: {mail_zeilen!r}")
    assert _cell("gust", 90.0, "raw") in tg_zeilen[-1][1], (
        f"Vorbedingung: Versand-Telegram ist ROH: {tg_zeilen!r}")

    vorschau = alert_preview(
        trip.id, AlertPreviewBody.model_validate(_trip_body()), user_id=uid)
    assert _rows(vorschau["email_plain"]) == mail_zeilen
    assert _rows(vorschau["telegram"]) == tg_zeilen
