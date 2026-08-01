"""Gemeinsame Fixtures fuer Issue #1410 (Tiefsttemperatur unterwegs + gefuehlte
Temperatur in den Kurzformen).

Kein Test-Modul (fuehrender Unterstrich -> pytest sammelt es nicht ein), nur
echte Datenmodell-Objekte und echte Renderer-Aufrufe. Kein ``Mock()``, kein
``patch()``, kein Netz, keine Mail. Vorbild fuer den Aufbau:
``tests/tdd/test_night_temp_evening_only.py`` (Segmente + ``night_weather`` +
Ortszeit) und ``tests/tdd/_trip_aggregation_fixtures.py`` (geteilte
Fixture-Datei ohne Test-Sammlung).

Wertelandschaft (bewusst sechs UNTERSCHEIDBARE Temperaturen, damit jede
Verwechslung von Quelle/Fenster im Testergebnis sichtbar wird):

| Groesse | gemessen | gefuehlt |
|---|---|---|
| kaelteste Gehzeit-Stunde (lokal 08:00) | 3 °C (``K``) | 1 °C (``FK``) |
| waermste Gehzeit-Stunde (lokal 11:00)  | 20 °C (``D``) | 18 °C (``FD``) |
| Nacht-Tiefst am Ziel (Folgetag 03:00)  | 11 °C (``N``) | 9 °C (``FN``) |

Die Nacht-Zeitreihe traegt ausserhalb ihres Tiefpunkts MILDERE Werte
(14 °C / 12 °C), damit ``N``/``FN`` nachweislich ein Minimum ueber das
Nachtfenster sind und nicht zufaellig ein konstanter Wert.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)

YEAR, MONTH, DAY = 2026, 7, 20
TZ = ZoneInfo("Europe/Paris")  # GR20-typisch, CEST = UTC+2 im Juli

WALK_START_H = 8   # Ortszeit
ARRIVAL_H = 12     # Ortszeit, Etappenende == Ankunft am Ziel
COLD_HOUR = 8      # kaelteste Gehzeit-Stunde (Ortszeit)
WARM_HOUR = 11     # waermste Gehzeit-Stunde (Ortszeit)
NIGHT_LOW_HOUR = 3  # Folgetag, Ortszeit — Tiefpunkt der Nacht am Ziel

HIKE_MIN_C = 3.0          # K  — kaelteste Stunde unterwegs, gemessen
HIKE_MAX_C = 20.0         # D  — Tages-Hoechst, gemessen
NIGHT_MIN_C = 11.0        # N  — Nacht-Tiefst am Ziel, gemessen
FELT_HIKE_MIN_C = 1.0     # FK — kaelteste Stunde unterwegs, gefuehlt
FELT_HIKE_MAX_C = 18.0    # FD — Tages-Hoechst, gefuehlt
FELT_NIGHT_MIN_C = 9.0    # FN — Nacht-Tiefst am Ziel, gefuehlt

_HIKE_BASE_C = 15.0
_FELT_HIKE_BASE_C = 13.0
_NIGHT_BASE_C = 14.0
_FELT_NIGHT_BASE_C = 12.0

STAGE_NAME = "E7"


def local_to_utc(day: int, hour: int) -> datetime:
    """Ortszeit-Wanduhr (Europe/Paris) -> echter UTC-Instant."""
    return datetime(YEAR, MONTH, day, hour, 0, tzinfo=TZ).astimezone(timezone.utc)


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(YEAR, MONTH, DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _dp(
    day: int,
    hour: int,
    *,
    temp: float,
    felt: float,
    precip: float = 0.0,
    pop: int = 0,
    wind: float = 12.0,
    gust: float = 22.0,
    thunder: ThunderLevel = ThunderLevel.NONE,
) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=local_to_utc(day, hour),
        t2m_c=temp,
        wind_chill_c=felt,
        wind10m_kmh=wind,
        gust_kmh=gust,
        precip_1h_mm=precip,
        pop_pct=pop,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def segment(day: int = DAY) -> SegmentWeatherData:
    """Wander-Segment lokal 08:00-12:00 mit VOLLER 24h-Zeitreihe.

    Die Zeitreihe traegt zusaetzlich Regen-/Wind-/Boeen-/Gewitter-Verlaeufe mit
    Einsatz- und Spitzenstunde, damit die SMS-Zeile realistisch lang wird
    (Grundlage fuer den Kuerzungs-Nachweis AC-6) — die Temperaturwerte selbst
    bleiben davon unberuehrt.
    """
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0,
                             distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1400.0,
                           distance_from_start_km=12.0),
        start_time=local_to_utc(day, WALK_START_H),
        end_time=local_to_utc(day, ARRIVAL_H),
        duration_hours=float(ARRIVAL_H - WALK_START_H),
        distance_km=12.0,
        ascent_m=900.0,
        descent_m=100.0,
    )
    data: list[ForecastDataPoint] = []
    for h in range(0, 24):
        if h == COLD_HOUR:
            temp, felt = HIKE_MIN_C, FELT_HIKE_MIN_C
        elif h == WARM_HOUR:
            temp, felt = HIKE_MAX_C, FELT_HIKE_MAX_C
        else:
            temp, felt = _HIKE_BASE_C, _FELT_HIKE_BASE_C
        data.append(_dp(
            day, h, temp=temp, felt=felt,
            precip=0.5 if h == 5 else (8.4 if h == WARM_HOUR else 0.0),
            pop=40 if h == 5 else (95 if h == WARM_HOUR else 0),
            wind=45.0 if h == 10 else 12.0,
            gust=70.0 if h == 10 else 22.0,
            thunder=ThunderLevel.MED if h == WARM_HOUR else ThunderLevel.NONE,
        ))
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=_meta(), data=data),
        aggregated=SegmentWeatherSummary(
            temp_min_c=HIKE_MIN_C,
            temp_max_c=HIKE_MAX_C,
            temp_avg_c=_HIKE_BASE_C,
            wind_chill_min_c=FELT_HIKE_MIN_C,
            wind_chill_max_c=FELT_HIKE_MAX_C,
            wind_max_kmh=45.0,
            gust_max_kmh=70.0,
            precip_sum_mm=8.9,
            pop_max_pct=95,
            cloud_avg_pct=50,
            thunder_level_max=ThunderLevel.MED,
        ),
        fetched_at=datetime(YEAR, MONTH, day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def night_weather(day: int = DAY) -> NormalizedTimeseries:
    """Nacht-Zeitreihe Ankunft (12:00) -> 06:00 Folgetag am Etappenziel.

    Tiefpunkt um 03:00 Folgetag (gemessen 11 °C / gefuehlt 9 °C), sonst
    milder — so beweist ein korrekter Nachtwert, dass ueber das Nachtfenster
    MINIMIERT wurde.
    """
    points: list[ForecastDataPoint] = []
    for h in range(ARRIVAL_H, 24):
        points.append(_dp(day, h, temp=_NIGHT_BASE_C, felt=_FELT_NIGHT_BASE_C))
    for h in range(0, 7):
        if h == NIGHT_LOW_HOUR:
            temp, felt = NIGHT_MIN_C, FELT_NIGHT_MIN_C
        else:
            temp, felt = _NIGHT_BASE_C, _FELT_NIGHT_BASE_C
        points.append(_dp(day + 1, h, temp=temp, felt=felt))
    return NormalizedTimeseries(meta=_meta(), data=points)


def dc(*metric_ids: str) -> UnifiedWeatherDisplayConfig:
    """Displaykonfiguration mit genau den genannten Metriken aktiv."""
    return UnifiedWeatherDisplayConfig(
        trip_id="i1410",
        metrics=[MetricConfig(metric_id=m, enabled=True) for m in metric_ids],
    )


# ---------------------------------------------------------------------------
# Beobachtungs-Helfer (lesen ausschliesslich gerenderten Text)
# ---------------------------------------------------------------------------

TEMP_SYMBOLS = ("N", "K", "D", "FN", "FK", "FD")


def sms_body(sms: str) -> str:
    """SMS ohne Etappen-Praefix ('E7: ' -> Rest)."""
    return sms.split(": ", 1)[1] if ": " in sms else sms


def sms_token_value(sms: str, symbol: str) -> Optional[str]:
    """Wert eines Temperatur-Tokens aus der gerenderten SMS.

    ``fullmatch`` auf dem einzelnen Token schliesst Praefix-Verwechslungen
    strukturell aus: 'SD12' ist kein 'D'-Token, 'FK1' kein 'K'-Token
    (#1435 E3b: das frühere Beispiel hieß 'SN12').
    ``None`` = Symbol kommt in der Zeile nicht vor.
    """
    pattern = re.compile(rf"{re.escape(symbol)}(-?\d+|-|\?)$")
    for token in sms_body(sms).split(" "):
        m = pattern.fullmatch(token)
        if m:
            return m.group(1)
    return None


def present_symbols(sms: str, symbols=TEMP_SYMBOLS) -> set[str]:
    """Teilmenge von ``symbols``, die in der gerenderten SMS vorkommt."""
    return {s for s in symbols if sms_token_value(sms, s) is not None}


def overview_bubble(report) -> str:
    """Die Kurzuebersicht-Bubble aus einem ``TripReport``."""
    for bubble in report.telegram_bubbles:
        if "Kurzübersicht" in bubble:
            return bubble
    return ""


def overview_line(report, label: str) -> str:
    """Die Kurzuebersicht-Zeile einer Metrik ('T ...' bzw. 'TF ...')."""
    for line in overview_bubble(report).splitlines():
        if line.startswith(f"{label} "):
            return line
    return ""


def compact_body(summary_text: str) -> str:
    """Kurzzusammenfassung ohne Titel-Praefix ('E7: ' -> Rest)."""
    return summary_text.split(": ", 1)[1] if ": " in summary_text else ""


def compact_parts(summary_text: str) -> list[str]:
    """Die ``', '``-getrennten Satzteile der Kurzzusammenfassung."""
    body = compact_body(summary_text)
    return body.split(", ") if body else []
