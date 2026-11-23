"""Verworfenes wird gemeldet (Issue #1737, Wächter #1405 "Sammeln-und-melden").

(1) Stunden der frischen Reihe ohne Anker-Gegenstueck erscheinen nicht als alt -> neu -- das
    wird per ``logger.warning`` mit Bezug #1737 gemeldet.
(2) entfallen (#3237): Metriken ohne Katalog-Eintrag fielen nur im Altpfad (Kanal-Listen mit
    rohen Grundauswahl-Eintraegen) fuer den Anzeigemodus weg. Der Alarm liest Roh/Einfach jetzt
    allein aus der Tabelle "Was steht wo", die nur Katalog-Metriken kennt
    (``read_placements``/``grundauswahl``) -- eine solche Metrik erscheint weder im Briefing
    noch im Alarm, es geht kein Anzeigemodus verloren.
"""
from __future__ import annotations
from app.ampel import resolve_ampel

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
                             tz=timezone.utc, ampel=resolve_ampel(None))
    assert [r.time for r in out["hours"]] == ["11:00"], "Vorbedingung: nur gepaarte Stunden"
    meldungen = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("#1737" in m and "2 Stunde" in m for m in meldungen), meldungen
