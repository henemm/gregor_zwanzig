"""TDD RED — Bug #1275: thunder_forecast["+1"] muss die tatsächliche

Gewitter-Lage der morgigen Etappe widerspiegeln, nicht nur die (evtl.
gewitterfreien) Restdaten des letzten Segments von heute.

Root Cause: `TripReportSchedulerService._build_thunder_forecast()`
(src/services/trip_report_scheduler.py) wird mit `segment_weather[-1]`
aufgerufen — dem LETZTEN Segment der HEUTIGEN Etappe — und durchsucht nur
dessen bereits geladene Zeitreihe nach Punkten von morgen. Liegt das
Gewitter-Ereignis an einem anderen Waypoint (der tatsächlichen morgigen
Etappe), wird es nicht erfasst. Die E-Mail-Outlook-Tabelle berechnet den
Gewitter-Level dagegen korrekt über `aggregate_stage()` auf ALLEN Segmenten
der tatsächlichen Folge-Etappe (`_build_stage_trend()`). Dieses Auseinander-
laufen ist der Widerspruch, den der User in #1275 meldet (E-Mail "hoch ab
4 Uhr" vs. SMS "TH+:-").

Mock-frei: echte `SegmentWeatherData`/`ForecastDataPoint`-Objekte (Muster aus
tests/tdd/test_bug_874_th_plus_sms.py), echte Aggregationsfunktion
`aggregate_stage()` (dieselbe, die `_build_stage_trend()` intern nutzt) statt
Mock der Geschäftslogik. Kein Netzwerk, kein Fetch — `_build_thunder_forecast()`
operiert rein auf bereits vorhandenen Zeitreihen.

Spec: docs/specs/bugfix/fix_1275_sms_th_mismatch.md (AC-1)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from src.services.trip_report_scheduler import TripReportSchedulerService
from src.services.weather_metrics import aggregate_stage

_UTC = ZoneInfo("UTC")
_TODAY = date(2026, 7, 15)
_TOMORROW = date(2026, 7, 16)


def _dp(day: date, hour: int, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(day.year, day.month, day.day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=10.0,
        gust_kmh=20.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_TODAY.year, _TODAY.month, _TODAY.day, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _segment(
    segment_id: int,
    lat: float,
    lon: float,
    data_points: list[ForecastDataPoint],
    thunder_level_max: ThunderLevel = ThunderLevel.NONE,
) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=lat, lon=lon, elevation_m=500.0),
        end_point=GPXPoint(lat=lat + 0.01, lon=lon + 0.01, elevation_m=600.0),
        start_time=data_points[0].ts,
        end_time=data_points[-1].ts,
        duration_hours=(data_points[-1].ts - data_points[0].ts).total_seconds() / 3600,
        distance_km=5.0,
        ascent_m=150.0,
        descent_m=0.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(meta=_meta(), data=data_points),
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=thunder_level_max,
            aggregation_config={
                "temp_min_c": "min",
                "temp_max_c": "max",
                "wind_max_kmh": "max",
                "gust_max_kmh": "max",
                "precip_sum_mm": "sum",
                "thunder_level_max": "max",
            },
        ),
        fetched_at=datetime(_TODAY.year, _TODAY.month, _TODAY.day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _today_last_segment_no_thunder_tomorrow() -> SegmentWeatherData:
    """Letztes Segment der HEUTIGEN Etappe — Zeitreihe reicht bis in den

    Folgetag, zeigt dort aber KEIN Gewitter (der Storm liegt an einem
    anderen Waypoint, s. `_next_stage_segment_with_storm()`).
    """
    points = (
        [_dp(_TODAY, h) for h in range(7, 24)]
        + [_dp(_TOMORROW, h) for h in range(0, 12)]
    )
    return _segment(segment_id=1, lat=47.10, lon=11.30, data_points=points)


def _next_stage_segments_with_storm() -> list[SegmentWeatherData]:
    """Die TATSÄCHLICHE morgige Etappe (andere Waypoints als heute) — mit

    einem Gewitter-Hoch um 04:00 an einem ihrer Segmente. Das ist exakt die
    Datengrundlage, die `_build_stage_trend()` für die E-Mail-Outlook-Zeile
    "morgen" via `aggregate_stage()` verwenden würde.
    """
    storm_points = [
        _dp(_TOMORROW, h, thunder=ThunderLevel.HIGH if h == 4 else ThunderLevel.NONE)
        for h in range(0, 24)
    ]
    calm_points = [_dp(_TOMORROW, h) for h in range(0, 24)]
    return [
        _segment(segment_id=10, lat=47.30, lon=11.60, data_points=storm_points,
                  thunder_level_max=ThunderLevel.HIGH),
        _segment(segment_id=11, lat=47.32, lon=11.65, data_points=calm_points,
                  thunder_level_max=ThunderLevel.NONE),
    ]


def scheduler_single_segment_level(segment: SegmentWeatherData) -> ThunderLevel:
    """Kontrast-Helfer: `_build_thunder_forecast()` nur mit dem letzten Segment

    von HEUTE gefüttert. Dessen Zeitreihe zeigt morgen kein Gewitter → NONE.
    Beweist, dass der Bug NICHT an der Aggregationsfunktion liegt, sondern an
    der falschen Datengrundlage (das Gewitter liegt an einem anderen Waypoint
    der morgigen Etappe, der in diesem Einzelsegment gar nicht enthalten ist).
    """
    fc = TripReportSchedulerService()._build_thunder_forecast(
        segment, _TODAY, tz=_UTC,
    )
    entry = (fc or {}).get("+1")
    return entry.get("level") if entry else ThunderLevel.NONE


class TestThunderForecastReflectsActualNextStage:
    """AC-1: thunder_forecast["+1"] muss den Gewitter-Level der tatsächlichen

    morgigen Etappe zeigen, nicht nur die (gewitterfreien) Restdaten des
    letzten Segments von heute.
    """

    def test_thunder_forecast_plus1_matches_next_stage_aggregate(self):
        """
        GIVEN: Heutiges letztes Segment ohne Gewitter morgen + tatsächliche
               morgige Etappe (andere Waypoints) mit Gewitter HIGH um 04:00
        WHEN:  Der Scheduler thunder_forecast["+1"] berechnet
        THEN:  Level muss dem echten Aggregat der morgigen Etappe entsprechen
               (HIGH) — nicht NONE/fehlend, wie es die aktuelle Ein-Segment-
               Logik liefert (Root Cause #1275)
        """
        today_last_segment = _today_last_segment_no_thunder_tomorrow()
        next_stage_segments = _next_stage_segments_with_storm()

        # Sanity-Check: die "korrekte" Referenz (identische Aggregations-
        # funktion wie _build_stage_trend()) muss HIGH ergeben, sonst taugt
        # die Fixture nichts.
        correct_level = aggregate_stage(next_stage_segments).thunder_level_max
        assert correct_level == ThunderLevel.HIGH, (
            f"Fixture-Fehler: aggregate_stage() der morgigen Etappe muss HIGH "
            f"ergeben (Storm-Segment enthalten), war {correct_level!r}"
        )

        # #1275-Fix: _build_thunder_forecast() muss über die Segmente der
        # TATSÄCHLICHEN morgigen Etappe aggregieren (dieselbe Datengrundlage
        # wie die E-Mail-Outlook-Tabelle via aggregate_stage), nicht nur die
        # bereits geladene Zeitreihe des letzten Segments von heute
        # durchsuchen. today_last_segment (kein Gewitter morgen) bleibt als
        # Kontrast dokumentiert: es allein liefert — korrekterweise — NONE,
        # weil das Gewitter an einem anderen Waypoint der morgigen Etappe liegt.
        assert scheduler_single_segment_level(today_last_segment) == ThunderLevel.NONE

        scheduler = TripReportSchedulerService()
        thunder_forecast = scheduler._build_thunder_forecast(
            next_stage_segments, _TODAY, tz=_UTC,
        )

        actual_entry = (thunder_forecast or {}).get("+1")
        actual_level = actual_entry.get("level") if actual_entry else None

        assert actual_level == correct_level, (
            f"thunder_forecast['+1']['level'] muss den tatsächlichen "
            f"Gewitter-Level der morgigen Etappe widerspiegeln "
            f"({correct_level!r}), zeigt aber {actual_level!r} "
            f"(thunder_forecast={thunder_forecast!r}). Root Cause #1275: "
            f"_build_thunder_forecast() durchsucht nur das letzte Segment "
            f"von HEUTE statt die tatsächliche morgige Etappe."
        )


class TestPeakTimeIndependentOfSegmentOrder:
    """F002 (Adversary): Die "ab HH:MM"-Uhrzeit muss die CHRONOLOGISCH früheste

    Stunde des Spitzenlevels sein — unabhängig von der Segment-Listenreihenfolge.
    Bug: `max(dps, key=ORD)` gewinnt bei Level-Gleichstand den zuerst gelisteten
    Punkt, nicht den frühesten.
    """

    def test_earliest_peak_hour_wins_regardless_of_segment_order(self):
        """
        GIVEN: Zwei Segmente derselben Etappe, BEIDE HIGH — das ZUERST gelistete
               spät (10:00), das zweite früher (02:00)
        WHEN:  _build_thunder_forecast() die "+1"-Uhrzeit ableitet
        THEN:  Text zeigt 'ab 02:00' (chronologisch früheste HIGH-Stunde),
               NICHT 'ab 10:00' (Reihenfolge des ersten Segments)
        """
        seg_a_points = [
            _dp(_TOMORROW, h, thunder=ThunderLevel.HIGH if h == 10 else ThunderLevel.NONE)
            for h in range(0, 24)
        ]
        seg_a = _segment(10, 47.30, 11.60, seg_a_points,
                         thunder_level_max=ThunderLevel.HIGH)
        seg_b_points = [
            _dp(_TOMORROW, h, thunder=ThunderLevel.HIGH if h == 2 else ThunderLevel.NONE)
            for h in range(0, 24)
        ]
        seg_b = _segment(11, 47.32, 11.65, seg_b_points,
                         thunder_level_max=ThunderLevel.HIGH)

        fc = TripReportSchedulerService()._build_thunder_forecast(
            [seg_a, seg_b], _TODAY, tz=_UTC,
        )

        assert fc["+1"]["level"] == ThunderLevel.HIGH
        assert "02:00" in fc["+1"]["text"], (
            f"'ab HH:MM' muss die früheste HIGH-Stunde (02:00) zeigen, nicht die "
            f"des zuerst gelisteten Segments (10:00): {fc['+1']['text']!r}"
        )
        assert "10:00" not in fc["+1"]["text"]


class TestAC1RenderedOutputsAgree:
    """F001 / AC-1 (Spec Z.138-140): Vergleich der GERENDERTEN Ausgaben — SMS-

    String gegen E-Mail-Outlook/Vorschau — statt reinem Dict-Inhalts-Check. Der
    Bug #1275 war genau der Widerspruch: E-Mail "hoch ab 4 Uhr" vs. SMS "TH+:-".
    """

    def test_sms_and_email_both_express_high_for_tomorrow(self):
        """
        GIVEN: Storm-Fixture (Gewitter HIGH an einem Waypoint der morgigen
               Etappe) + passende Trend-Zeile (dieselbe Datengrundlage wie die
               Outlook-Tabelle)
        WHEN:  ein Evening-Report gerendert wird (SMS-String + E-Mail)
        THEN:  SMS zeigt 'TH+:H' (nicht 'TH+:-') UND die E-Mail-Outlook/Vorschau
               zeigt HIGH-Gewitter für morgen — beide Kanäle stimmen überein
        """
        from src.output.renderers.trip_report import TripReportFormatter
        from src.output.tokens.dto import HourlyValue

        today_seg = _today_last_segment_no_thunder_tomorrow()
        next_stage = _next_stage_segments_with_storm()
        agg_level = aggregate_stage(next_stage).thunder_level_max

        # Trend-Zeilen wie _build_stage_trend sie aus derselben Etappe baut;
        # +2 (NONE) mit dabei, damit der Trend beide Offsets abdeckt (kein
        # Fallback-Fetch → trip=None ist sicher).
        trend = [
            dict(weekday="Do", date=_TOMORROW, name="Etappe 2",
                 temp_lo=10, temp_hi=20, precip_mm=0.0, wind_dir="N", wind_kmh=15,
                 thunder=agg_level.name, note="",
                 hourly_precip=(), hourly_wind=(), hourly_gust=(),
                 hourly_thunder=(HourlyValue(hour=4, value=2.0),)),
            dict(weekday="Fr", date=date(2026, 7, 17), name="Etappe 3",
                 temp_lo=10, temp_hi=20, precip_mm=0.0, wind_dir="N", wind_kmh=15,
                 thunder="NONE", note="",
                 hourly_precip=(), hourly_wind=(), hourly_gust=(),
                 hourly_thunder=()),
        ]

        scheduler = TripReportSchedulerService()
        thunder_forecast = scheduler._build_thunder_forecast_from_trend_or_fetch(
            None, _TODAY, tz=_UTC, multi_day_trend=trend,
        )

        report = TripReportFormatter().format_email(
            segments=[today_seg],
            trip_name="Testtrip",
            report_type="evening",
            thunder_forecast=thunder_forecast,
            multi_day_trend=trend,
            tz=_UTC,
        )
        sms = report.sms_text
        email = report.email_plain

        assert "TH+:H" in sms, (
            f"SMS muss 'TH+:H' (HIGH-Gewitter morgen) zeigen, sonst der alte "
            f"Bug-Zustand: {sms!r}"
        )
        assert "TH+:-" not in sms, (
            f"SMS darf NICHT 'TH+:-' zeigen (Widerspruch zur E-Mail, Bug #1275): "
            f"{sms!r}"
        )
        assert ("⚡HIGH" in email) or ("Starkes Gewitter" in email), (
            f"E-Mail-Outlook/Vorschau muss HIGH-Gewitter für morgen ausdrücken "
            f"(Übereinstimmung mit der SMS): {email!r}"
        )
