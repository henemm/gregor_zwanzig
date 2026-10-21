"""Verworfenes wird gemeldet (Issue #1737, Wächter #1405 "Sammeln-und-melden").

(1) Stunden der frischen Reihe ohne Anker-Gegenstueck erscheinen nicht als alt -> neu -- das
    wird per ``logger.warning`` mit Bezug #1737 gemeldet.
(2) Metriken der Anzeige-Konfiguration ohne Katalog-Eintrag faellen fuer den Anzeigemodus weg
    (Stundenzeilen ROH) -- ebenfalls gemeldet.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from services.weather_snapshot import _deserialize_timeseries


def _reihe(start: datetime, boeen: list[float]):
    return _deserialize_timeseries({"hourly": [
        {"ts": (start + timedelta(hours=i)).isoformat(), "gust_kmh": v}
        for i, v in enumerate(boeen)
    ]}, "openmeteo")


def test_stunden_ohne_anker_gegenstueck_werden_mit_bezug_1737_gemeldet(caplog):
    from output.renderers.alert.hours import affected_hours

    t0 = datetime(2026, 5, 1, 10, tzinfo=timezone.utc)
    anker = _reihe(t0, [10.0, 10.0])                    # 10Z, 11Z
    frisch = _reihe(t0, [10.0, 90.0, 90.0, 90.0])       # 10Z..13Z -> 12Z, 13Z ohne Anker
    with caplog.at_level(logging.WARNING, logger="output.renderers.alert.hours"):
        out = affected_hours("gust", frisch, anker, threshold=20.0, value_from=10.0,
                             tz=timezone.utc)
    assert [r.time for r in out["hours"]] == ["11:00"], "Vorbedingung: nur gepaarte Stunden"
    meldungen = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("#1737" in m and "2 Stunde" in m for m in meldungen), meldungen


def test_metrik_ohne_katalog_eintrag_im_anzeigemodus_wird_mit_bezug_1737_gemeldet(caplog):
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from services.notification_service import _alert_format_modes

    dc = UnifiedWeatherDisplayConfig(trip_id="t", metrics=[
        MetricConfig(metric_id="gust", enabled=True),
        MetricConfig(metric_id="gibts_nicht", enabled=True),
    ])
    with caplog.at_level(logging.WARNING, logger="services.notification_service"):
        modes = _alert_format_modes(dc)
    assert "gust" in modes["email"], "Vorbedingung: bekannte Metrik wird aufgeloest"
    meldungen = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("#1737" in m and "gibts_nicht" in m for m in meldungen), meldungen
