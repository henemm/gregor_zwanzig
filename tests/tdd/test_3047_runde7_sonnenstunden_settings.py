"""#3047 Runde 7, Paket p8: Sonnenstunden ohne ``Settings()``-Neubau je Ort.

``calculate_sunny_hours`` (ohne ``settings``) baute bei jedem Aufruf
``Settings()`` neu (Umgebung + ``.env`` lesen, ~ms je Ort). Seit die
Orte-Kanaele bei jedem Ort das Tages-Aggregat bilden, kostet das je Vergleich
spuerbar Zeit. Erwartung: gleiches Ergebnis, Konfiguration einmal je Lauf
aufgeloest -- eine Aenderung des DNI-Bands in der Umgebung wirkt weiterhin.

Kein Mock: echte ``Settings``, echte Datenpunkte, Zeitmessung relativ zum
Aufruf mit ausdruecklich uebergebenen ``Settings`` (maschinenunabhaengig).
"""
from __future__ import annotations

import time
from datetime import datetime

from app.config import Settings
from app.models import ForecastDataPoint
from services.weather_metrics import WeatherMetricsService, summarize_points


def _orte(n: int = 20) -> list[list[ForecastDataPoint]]:
    return [
        [ForecastDataPoint(ts=datetime(2026, 7, 8, h), t2m_c=20.0, cloud_total_pct=30,
                           dni_wm2=40.0 + 9 * h + o) for h in range(24)]
        for o in range(n)
    ]


def _dauer(fn, orte) -> float:
    beste = float("inf")
    for _ in range(5):
        t = time.perf_counter()
        for dps in orte:
            fn(dps)
        beste = min(beste, time.perf_counter() - t)
    return beste


def test_ergebnis_gleich_wie_mit_ausdruecklichen_settings():
    explizit = Settings()
    for dps in _orte():
        assert WeatherMetricsService.calculate_sunny_hours(dps) == \
            WeatherMetricsService.calculate_sunny_hours(dps, settings=explizit)
        assert summarize_points(dps).sunny_hours == \
            WeatherMetricsService.calculate_sunny_hours(dps, settings=explizit)


def test_zwanzig_orte_ohne_settings_neubau_je_ort():
    orte = _orte(20)
    explizit = Settings()
    WeatherMetricsService.calculate_sunny_hours(orte[0])  # erster Aufruf darf lesen
    ohne = _dauer(WeatherMetricsService.calculate_sunny_hours, orte)
    mit = _dauer(lambda d: WeatherMetricsService.calculate_sunny_hours(d, settings=explizit), orte)
    # Vorher: je Ort ein Settings()-Bau -> ein Vielfaches der reinen Rechnung.
    assert ohne < 3 * mit + 0.002, (
        f"20 Orte ohne settings {ohne * 1000:.1f} ms vs. mit {mit * 1000:.1f} ms: "
        "Settings() wird je Ort neu gebaut")


def test_aenderung_des_dni_bands_wirkt_weiterhin(monkeypatch):
    dps = _orte(1)[0]
    vorher = WeatherMetricsService.calculate_sunny_hours(dps)
    monkeypatch.setenv("GZ_SUNNY_DNI_MIN_WM2", "150")
    monkeypatch.setenv("GZ_SUNNY_DNI_MAX_WM2", "250")
    nachher = WeatherMetricsService.calculate_sunny_hours(dps)
    assert nachher == WeatherMetricsService.calculate_sunny_hours(dps, settings=Settings())
    assert nachher < vorher
    monkeypatch.delenv("GZ_SUNNY_DNI_MIN_WM2")
    monkeypatch.delenv("GZ_SUNNY_DNI_MAX_WM2")
    assert WeatherMetricsService.calculate_sunny_hours(dps) == vorher
