"""TDD RED: SMS-Token-Verdrahtung fuer 14 bisher wirkungslose Metriken.

Issue #1660 Scheibe B. SPEC: docs/specs/modules/fix_1660b_sms_token_wiring.md

Getestet werden 3 Wertegrammatik-Klassen (DEC-2):
  (a) Threshold-Peak: HU DP CP UV CT CL CM CH
  (b) Invers-Min:      VS NL
  (c) Tageswert:       WD PT SU HP

AC -> Test-Mapping:
  AC-1  test_ac1_humidity_threshold_peak_renders_onset_and_peak
  AC-2  test_ac2_cape_without_threshold_renders_peak_only
  AC-3  test_ac3_visibility_invers_gate_triggers_below_threshold
  AC-4  test_ac4_visibility_invers_gate_not_triggered_above_threshold
  AC-5  test_ac5_freezing_level_without_threshold_always_visible
  AC-6  test_ac6_wind_direction_dominant_sector_over_window (SMSTripFormatter)
  AC-7  test_ac7_precip_type_dominant_majority (SMSTripFormatter)
        test_ac7_precip_type_tie_break_rank (SMSTripFormatter)
  AC-8  test_ac8_sunshine_and_pressure_daily_values (SMSTripFormatter)
  AC-9  test_ac9_deselecting_two_metrics_removes_them_completely
  AC-10 test_ac10_null_form_and_gap_form_for_metric_without_data
  AC-11 test_ac11_golden_byte_identity_without_the_14_new_metrics (GRUEN heute,
        Byte-Identitaets-Wache -- s. Docstring dort)
  AC-16 test_ac16_token_identical_in_morning_and_evening_report

AC-13 (Ratsche) und AC-15 (Staging) sind NICHT Teil dieser Datei (s. Auftrag).

RED-Erwartung: DailyForecast/build_token_line kennen die 14 neuen Felder und
Symbole noch nicht -- die meisten Tests scheitern mit TypeError (unerwartetes
Konstruktor-Keyword) oder AssertionError (Symbol fehlt in der Zeile). Einzige
Ausnahme ist der AC-11-Golden-Test, der HEUTE bereits gruen ist.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    PrecipType,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from output.tokens.builder import build_token_line
from output.tokens.dto import DailyForecast, HourlyValue, MetricSpec, NormalizedForecast
from output.renderers.sms_trip import SMSTripFormatter

_TZ = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Helpers -- Builder-Ebene (direkt gegen build_token_line())
# ---------------------------------------------------------------------------


def _render(today: DailyForecast, config: list[MetricSpec], *,
            report_type: str = "evening", stage_name: str = "Etappe1") -> str:
    forecast = NormalizedForecast(days=(today,))
    line = build_token_line(
        forecast, config, report_type=report_type, stage_name=stage_name,
    )
    return line.render(160)


# ---------------------------------------------------------------------------
# Helpers -- SMSTripFormatter-Ebene (echte Segmente mit Stunden-Zeitreihe)
# ---------------------------------------------------------------------------


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _dp(hour: int, *, day: int = 10, **overrides) -> ForecastDataPoint:
    base = dict(
        ts=datetime(2026, 8, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=5.0, precip_1h_mm=0.0,
        pop_pct=0, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )
    base.update(overrides)
    return ForecastDataPoint(**base)


def _single_day_segment(points: list[ForecastDataPoint]) -> SegmentWeatherData:
    """Ein Segment 04:00-19:00, dessen Zeitreihe genau die uebergebenen Punkte
    enthaelt -- deckt das komplette Tagesfenster ab (day_window.py Konstanten
    4/19), sodass build_day_window_points() alle Punkte uebernimmt."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1500),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1800),
        start_time=datetime(2026, 8, 10, 4, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 10, 19, 0, tzinfo=timezone.utc),
        duration_hours=15.0, distance_km=20.0, ascent_m=800, descent_m=400,
    )
    ts = NormalizedTimeseries(meta=_meta(), data=points)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(temp_min_c=10.0, temp_max_c=20.0),
        fetched_at=datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


# ---------------------------------------------------------------------------
# Klasse (a) -- Threshold-Peak
# ---------------------------------------------------------------------------


def test_ac1_humidity_threshold_peak_renders_onset_and_peak():
    """AC-1: HU mit sms_threshold=85, erstes Erreichen 88@14, Peak 92@17."""
    today = DailyForecast(humidity_hourly=(HourlyValue(14, 88), HourlyValue(17, 92)))
    config = [MetricSpec(symbol="HU", enabled=True, threshold=85.0)]
    line = _render(today, config)
    assert "HU88@14(92@17)" in line, f"HU-Token fehlt/falsch: {line!r}"


def test_ac2_cape_without_threshold_renders_peak_only():
    """AC-2: CP ohne Schwelle -> Peak-only, kein Klammer-Zusatz."""
    today = DailyForecast(cape_hourly=(HourlyValue(16, 1200),))
    config = [MetricSpec(symbol="CP", enabled=True)]
    line = _render(today, config)
    assert "CP1200@16" in line, f"CP-Peak-only-Token fehlt/falsch: {line!r}"
    assert "CP1200@16(" not in line, f"CP darf keinen Klammer-Zusatz haben: {line!r}"


# ---------------------------------------------------------------------------
# Klasse (b) -- Invers-Min
# ---------------------------------------------------------------------------


def test_ac3_visibility_invers_gate_triggers_below_threshold():
    """AC-3: VS-Schwelle 1.0 km, Tagestief 600 m um 11 Uhr -> VS0.6@11
    (km-Umrechnung UND Stunde des Tagestiefs, nicht des Peaks)."""
    today = DailyForecast(visibility_hourly=(
        HourlyValue(9, 3000), HourlyValue(11, 600), HourlyValue(15, 5000),
    ))
    config = [MetricSpec(symbol="VS", enabled=True, threshold=1.0)]
    line = _render(today, config)
    assert "VS0.6@11" in line, f"VS-Invers-Gate-Token fehlt/falsch: {line!r}"


def test_ac4_visibility_invers_gate_not_triggered_above_threshold():
    """AC-4: Tagestief 3.2 km faellt NIE unter die 1.0-km-Schwelle -> Null-Form."""
    today = DailyForecast(visibility_hourly=(
        HourlyValue(9, 3500), HourlyValue(14, 3200), HourlyValue(18, 4000),
    ))
    config = [MetricSpec(symbol="VS", enabled=True, threshold=1.0)]
    line = _render(today, config)
    assert "VS-" in line, f"VS-Null-Form erwartet (Schwelle nicht unterschritten): {line!r}"
    assert "VS3.2" not in line and "VS3200" not in line, (
        f"VS darf bei nicht unterschrittener Schwelle keinen Zahlenwert zeigen: {line!r}"
    )


def test_ac5_freezing_level_without_threshold_always_visible():
    """AC-5: NL ohne Schwelle -> Tiefstwert (1800 m um 6 Uhr) unbedingt sichtbar."""
    today = DailyForecast(freezing_level_hourly=(
        HourlyValue(6, 1800), HourlyValue(12, 2400),
    ))
    config = [MetricSpec(symbol="NL", enabled=True)]
    line = _render(today, config)
    assert "NL1800@6" in line, f"NL-Token fehlt/falsch: {line!r}"


# ---------------------------------------------------------------------------
# Klasse (c) -- Tageswert (Aggregation ueber echte Segmente, SMSTripFormatter)
# ---------------------------------------------------------------------------


def test_ac6_wind_direction_dominant_sector_over_window():
    """AC-6: Mehrheit der Stunden im Sektor NW (315-359 Grad) -> Token WDNW.

    Muss ueber SMSTripFormatter.format_sms() laufen (nicht direkt gegen
    build_token_line()), weil die Sektor-Mehrheitsbildung in
    ``_segments_to_normalized_forecast`` passiert (DEC-2c) -- das ist die
    Wertebeschaffungs-Seite, nicht die reine Grammatik.
    """
    points = []
    # 10 Stunden NW (330 Grad), 4 Stunden Ost (90 Grad), 2 Stunden Sued (200 Grad)
    for h in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13):
        points.append(_dp(h, wind_direction_deg=330))
    for h in (14, 15, 16, 17):
        points.append(_dp(h, wind_direction_deg=90))
    for h in (18, 19):
        points.append(_dp(h, wind_direction_deg=200))
    segments = [_single_day_segment(points)]

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
    )
    assert "WDNW" in sms, f"WD-Sektor-Mehrheitstoken fehlt/falsch: {sms!r}"


def test_ac7_precip_type_dominant_majority():
    """AC-7 (Fall 1): SNOW haeufiger als RAIN/MIXED -> Token PTS."""
    points = []
    for h in (4, 5, 6, 7, 8, 9, 10, 11, 12):
        points.append(_dp(h, precip_type=PrecipType.SNOW))
    for h in (13, 14, 15, 16):
        points.append(_dp(h, precip_type=PrecipType.RAIN))
    for h in (17, 18, 19):
        points.append(_dp(h, precip_type=PrecipType.MIXED))
    segments = [_single_day_segment(points)]

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
    )
    assert "PTS" in sms, f"PT-Dominanz-Token fehlt/falsch: {sms!r}"


def test_ac7_precip_type_tie_break_rank():
    """AC-7 (Fall 2, Gleichstand): gleich viele RAIN- wie SNOW-Stunden ->
    SNOW gewinnt nach Schwere-Rang (FREEZING_RAIN > SNOW > MIXED > RAIN) ->
    Token PTS."""
    points = []
    for h in (4, 6, 8, 10, 12):
        points.append(_dp(h, precip_type=PrecipType.SNOW))
    for h in (5, 7, 9, 11, 13):
        points.append(_dp(h, precip_type=PrecipType.RAIN))
    segments = [_single_day_segment(points)]

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
    )
    assert "PTS" in sms, f"PT-Gleichstand-Rang-Token fehlt/falsch (SNOW muss RAIN schlagen): {sms!r}"


def test_ac8_sunshine_and_pressure_daily_values():
    """AC-8: SU (Sonnenstunden, DNI-Ableitung ueber
    WeatherMetricsService.calculate_sunny_hours) und HP (Tagesmittel-Luftdruck)
    -- beide gerundet ganzzahlig.

    Die erwarteten Werte werden ueber denselben geteilten Helfer berechnet,
    an den die Spec delegiert (DEC-2c) -- kein erfundenes Golden, sondern der
    tatsaechliche Referenzwert des bestehenden Aggregations-Codes.
    """
    from services.weather_metrics import WeatherMetricsService

    pressures = [1010.0, 1012.0, 1013.0, 1015.0, 1017.0, 1014.0]
    points = []
    for i, h in enumerate(range(4, 20)):
        dni = 200.0 if 9 <= h <= 16 else 0.0
        pressure = pressures[i % len(pressures)]
        points.append(_dp(h, dni_wm2=dni, pressure_msl_hpa=pressure))
    segments = [_single_day_segment(points)]

    expected_sunny_hours = WeatherMetricsService.calculate_sunny_hours(points)
    expected_pressure_avg = sum(p.pressure_msl_hpa for p in points) / len(points)

    sms = SMSTripFormatter().format_sms(
        segments, stage_name="Etappe1", report_type="evening", tz=_TZ,
    )
    assert f"SU{round(expected_sunny_hours)}" in sms, (
        f"SU-Token fehlt/falsch (erwartet SU{round(expected_sunny_hours)}): {sms!r}"
    )
    assert f"HP{round(expected_pressure_avg)}" in sms, (
        f"HP-Token fehlt/falsch (erwartet HP{round(expected_pressure_avg)}): {sms!r}"
    )


# ---------------------------------------------------------------------------
# Abwahl, Null-Form/Gap, Byte-Identitaet, Morning/Evening-Paritaet
# ---------------------------------------------------------------------------


def test_ac9_deselecting_two_metrics_removes_them_completely():
    """AC-9: CP und UV werden abgewaehlt (enabled=False angehaengt, analog
    trip_report.py's disabled_specs-Muster #944) -- sie duerfen danach WEDER
    mit Wert NOCH als Null-Form erscheinen. HU bleibt unveraendert sichtbar."""
    today = DailyForecast(
        humidity_hourly=(HourlyValue(14, 88), HourlyValue(17, 92)),
        cape_hourly=(HourlyValue(16, 1200),),
        uv_hourly=(HourlyValue(13, 8),),
    )
    base_config = [
        MetricSpec(symbol="HU", enabled=True, threshold=85.0),
        MetricSpec(symbol="CP", enabled=True),
        MetricSpec(symbol="UV", enabled=True),
    ]
    before = _render(today, base_config)
    assert "HU88@14(92@17)" in before
    assert "CP1200@16" in before
    assert "UV8@13" in before

    after_config = base_config + [
        MetricSpec(symbol="CP", enabled=False),
        MetricSpec(symbol="UV", enabled=False),
    ]
    after = _render(today, after_config)
    assert "HU88@14(92@17)" in after, (
        f"HU muss nach Abwahl von CP/UV unveraendert bleiben: {after!r}"
    )
    assert "CP" not in after, f"CP muss nach Abwahl VOLLSTAENDIG fehlen (auch keine Null-Form): {after!r}"
    assert "UV" not in after, f"UV muss nach Abwahl VOLLSTAENDIG fehlen (auch keine Null-Form): {after!r}"


def test_ac10_null_form_and_gap_form_for_metric_without_data():
    """AC-10: CT gewaehlt, keine Stundenwerte -> CT-; bei zusaetzlicher
    Datenluecke (has_data_gap=True) -> CT?."""
    config = [MetricSpec(symbol="CT", enabled=True)]

    today_no_gap = DailyForecast(cloud_total_hourly=(), has_data_gap=False)
    line_no_gap = _render(today_no_gap, config)
    assert "CT-" in line_no_gap, f"CT-Null-Form erwartet: {line_no_gap!r}"

    today_gap = DailyForecast(cloud_total_hourly=(), has_data_gap=True)
    line_gap = _render(today_gap, config)
    assert "CT?" in line_gap, f"CT-Gap-Form '?' erwartet: {line_gap!r}"
    assert "CT-" not in line_gap, f"bei Gap darf keine '-'-Form mehr stehen: {line_gap!r}"


def test_ac11_golden_byte_identity_without_the_14_new_metrics():
    """AC-11 (Byte-Identitaets-Wache): Bestands-Trip ohne jede der 14 neuen
    Metriken -- die gerenderte Zeile MUSS zeichengleich zum Stand VOR dieser
    Aenderung bleiben.

    GRUEN HEUTE (bewusste Ausnahme laut Auftrag): der erwartete String wurde
    mit dem AKTUELLEN (unveraenderten) build_token_line() erzeugt und hier
    eingefroren -- dieser Test bewacht Byte-Identitaet, er reproduziert kein
    fehlendes Verhalten.
    """
    today = DailyForecast(
        temp_min_c=8.0, temp_max_c=19.0,
        rain_hourly=(HourlyValue(6, 0.3), HourlyValue(15, 1.8)),
        pop_hourly=(HourlyValue(10, 35.0), HourlyValue(16, 80.0)),
        wind_hourly=(HourlyValue(11, 15.0), HourlyValue(14, 22.0)),
        gust_hourly=(HourlyValue(11, 20.0), HourlyValue(14, 35.0)),
        thunder_hourly=(HourlyValue(15, 2),),
        wind_chill_c=-3.0, wind_chill_min_c=-3.0, wind_chill_max_c=5.0,
    )
    config = [
        MetricSpec(symbol="K", enabled=True),
        MetricSpec(symbol="D", enabled=True),
        MetricSpec(symbol="R", enabled=True, threshold=0.2),
        MetricSpec(symbol="PR", enabled=True, threshold=20.0),
        MetricSpec(symbol="W", enabled=True, threshold=10.0),
        MetricSpec(symbol="G", enabled=True, threshold=20.0),
        MetricSpec(symbol="TH:", enabled=True, threshold=1.0),
        MetricSpec(symbol="FK", enabled=True),
        MetricSpec(symbol="FD", enabled=True),
    ]
    evening = _render(today, config, report_type="evening", stage_name="Etappe 3 Bergsee")
    morning = _render(today, config, report_type="morning", stage_name="Etappe 3 Bergsee")

    assert evening == (
        "Etappe 3 B: N- K8 D19 FK-3 FD5 R0.3@6(1.8@15) PR35%@10(80%@16) "
        "W15@11(22@14) G20@11(35@14) TH:M@15 WC-3"
    ), f"Byte-Identitaet gebrochen (evening): {evening!r}"
    assert morning == (
        "Etappe 3 B: K8 D19 FK-3 FD5 R0.3@6(1.8@15) PR35%@10(80%@16) "
        "W15@11(22@14) G20@11(35@14) TH:M@15 WC-3"
    ), f"Byte-Identitaet gebrochen (morning): {morning!r}"


def test_ac16_token_identical_in_morning_and_evening_report():
    """AC-16: eine der 14 Metriken (hier CP) erscheint in Morgen- UND
    Abendbriefing identisch -- kein Nacht-Sonderfall wie bei N/FN."""
    today = DailyForecast(cape_hourly=(HourlyValue(16, 1200),))
    config = [MetricSpec(symbol="CP", enabled=True, morning_enabled=True, evening_enabled=True)]

    morning = _render(today, config, report_type="morning")
    evening = _render(today, config, report_type="evening")

    assert "CP1200@16" in morning, f"CP fehlt im Morgenbriefing: {morning!r}"
    assert "CP1200@16" in evening, f"CP fehlt im Abendbriefing: {evening!r}"
