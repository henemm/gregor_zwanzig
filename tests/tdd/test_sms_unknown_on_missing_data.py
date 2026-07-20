"""SMS: `?` (unbekannt) statt `-` (Fehl-Entwarnung) bei Teilausfall (#1328).

Spec: docs/specs/modules/sms_unknown_on_missing_data.md

Bei einem teilweisen Wetterdaten-Ausfall (mindestens ein Segment
`has_error=True` bzw. ohne Zeitreihe) rendert die SMS-Aggregation heute
still `-` ("kein Risiko") fuer jedes Symbol, zu dem im 04-19-Uhr-Fenster
keine Stichprobe vorlag — eine falsche Entwarnung auf dem einzigen Kanal,
der Wanderer unterwegs erreicht. Diese Suite belegt AC-1..AC-4 der Spec.

TDD RED: AC-1 und AC-4 muessen mit dem heutigen Code fehlschlagen (SMS zeigt
`TH:-` statt `TH:?`). AC-2/AC-3 sind Regressionsschutz und duerfen bereits
gruen sein.

Keine Mocks, keine Dateiinhalt-Checks. Reale Fixtures (echte
`SegmentWeatherData`, wie `segment_weather.py:150-158` sie bei
Provider-Fehlern real erzeugt), reale Aufrufe von
`SMSTripFormatter().format_sms()`.
"""
from __future__ import annotations

from datetime import datetime, timezone
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
from src.output.renderers.sms_trip import SMSTripFormatter

_YEAR, _MONTH, _DAY = 2026, 7, 20
_TZ = ZoneInfo("UTC")


def _dp(hour: int, thunder: ThunderLevel = ThunderLevel.NONE) -> ForecastDataPoint:
    """Ein Stunden-Datenpunkt der regulaeren (fehlerfreien) Segment-Zeitreihe."""
    return ForecastDataPoint(
        ts=datetime(_YEAR, _MONTH, _DAY, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=5.0,
        gust_kmh=5.0,
        precip_1h_mm=0.0,
        pop_pct=0,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _trip_segment(start_h: int, end_h: int) -> TripSegment:
    return TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(_YEAR, _MONTH, _DAY, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(_YEAR, _MONTH, _DAY, end_h, 0, tzinfo=timezone.utc),
        duration_hours=float(end_h - start_h),
        distance_km=8.0,
        ascent_m=200.0,
        descent_m=0.0,
    )


def _error_segment(start_h: int = 4, end_h: int = 9) -> SegmentWeatherData:
    """Wie ``segment_weather.py:150-158`` bei Provider-Fehlern real erzeugt:
    leere ``SegmentWeatherSummary()``, ``timeseries=None``, ``has_error=True``."""
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=None,
        aggregated=SegmentWeatherSummary(),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
        has_error=True,
        error_message="provider timeout",
    )


def _regular_segment(
    start_h: int = 9,
    end_h: int = 17,
    thunder_by_hour: dict[int, ThunderLevel] | None = None,
) -> SegmentWeatherData:
    """Vollstaendiges, fehlerfreies Segment mit 24h-Zeitreihe."""
    tb = thunder_by_hour or {}
    data = [_dp(h, tb.get(h, ThunderLevel.NONE)) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _format(segments: list[SegmentWeatherData]) -> str:
    return SMSTripFormatter().format_sms(
        segments, stage_name="E1", report_type="morning", tz=_TZ,
    )


class TestAC1ShowsUnknownTokenOnSegmentError:
    """AC-1: Ein Segment mit ``has_error=True`` im Fenster plus ein
    reguläres Segment ohne Gewitter-Ereignis -> `TH:?` statt `TH:-`.

    Verschaerfte Regel (PO-Entscheidung 2026-07-20): jede Entwarnung `-` im
    Fenster wird bei einer Datenluecke zu `?`, nicht nur bei fehlender
    Stichprobe -> auch `R?`/`PR?`/`W?`/`G?` erwartet."""

    def test_sms_shows_unknown_token_when_segment_has_error(self):
        segments = [_error_segment(), _regular_segment()]
        sms = _format(segments)

        assert "TH:?" in sms, (
            f"Erwartet `TH:?` (unbekannt, weil eine Etappe wegen "
            f"Provider-Fehler keine Daten beitragen konnte), stattdessen "
            f"faelschliche Entwarnung.\nSMS: {sms}"
        )
        assert "TH:-" not in sms, f"Fehl-Entwarnung `TH:-` darf nicht erscheinen.\nSMS: {sms}"
        assert "E1: N10 D20 R? PR? W? G? TH:? TH+:-" in sms, (
            f"Erwartet, dass die verschaerfte Regel jede Entwarnung im "
            f"lueckenhaften Fenster zu `?` macht (R/PR/W/G/TH:).\nSMS: {sms}"
        )


class TestAC2KeepsFoundRiskDespiteGap:
    """AC-2 (sicherheitskritisch): ein gefundener Wert wird NIE durch `?`
    ersetzt, auch wenn andere Segmente im Fenster Datenluecken haben."""

    def test_sms_keeps_found_risk_despite_other_segment_gap(self):
        segments = [
            _error_segment(),
            _regular_segment(thunder_by_hour={10: ThunderLevel.HIGH}),
        ]
        sms = _format(segments)

        assert "TH:H@10" in sms, f"Erwartet den gefundenen Gewitter-Wert.\nSMS: {sms}"
        assert "TH:?" not in sms, (
            f"Ein erkanntes Gewitter darf nie durch `?` verschluckt werden "
            f"(Sicherheitsprinzip der Spec).\nSMS: {sms}"
        )


class TestAC3RegressionNoGapStaysDash:
    """AC-3 (Regressionsschutz): ohne Datenluecke bleibt `-` unveraendert."""

    def test_sms_shows_dash_when_no_gap(self):
        segments = [_regular_segment(start_h=4, end_h=9), _regular_segment(start_h=9, end_h=17)]
        sms = _format(segments)

        assert "TH:-" in sms, f"Erwartet weiterhin `-` ohne Datenluecke.\nSMS: {sms}"
        assert "TH:?" not in sms, f"Kein `?` ohne Datenluecke erwartet.\nSMS: {sms}"


def _regular_segment_with_multiple_warnings(
    start_h: int = 9, end_h: int = 17,
) -> SegmentWeatherData:
    """Regulaeres, fehlerfreies Segment mit MEHREREN echten Warnwerten ueber
    Schwelle an Stunde 10 (Gewitter HIGH, Wind 45 km/h, Regen 5mm). Boen und
    Regenwahrscheinlichkeit bleiben unterschwellig/0 (kein Fund -> `?`)."""
    data = []
    for h in range(0, 24):
        if h == 10:
            data.append(ForecastDataPoint(
                ts=datetime(_YEAR, _MONTH, _DAY, h, 0, tzinfo=timezone.utc),
                t2m_c=15.0, wind10m_kmh=45.0, gust_kmh=5.0,
                precip_1h_mm=5.0, pop_pct=0, cloud_total_pct=50,
                thunder_level=ThunderLevel.HIGH, humidity_pct=55,
            ))
        else:
            data.append(_dp(h))
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=_trip_segment(start_h, end_h),
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=45.0,
            gust_max_kmh=25.0, precip_sum_mm=5.0,
            thunder_level_max=ThunderLevel.HIGH,
        ),
        fetched_at=datetime(_YEAR, _MONTH, _DAY, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


class TestSMSKeepsFoundValuesDespiteGapForMultipleMetrics:
    """Verschaerfte Regel (PO 2026-07-20): eine Datenluecke im Fenster
    entwertet JEDE Entwarnung `-` zu `?` — aber unterdrueckt NIE einen
    tatsaechlich gefundenen Warnwert, auch nicht bei mehreren Metriken
    gleichzeitig (Gewitter, Wind, Regen)."""

    def test_sms_shows_found_values_despite_gap_for_multiple_metrics(self):
        segments = [_error_segment(), _regular_segment_with_multiple_warnings()]
        sms = _format(segments)

        # Gefundene Warnwerte erscheinen unveraendert mit echtem Wert.
        assert "TH:H@10" in sms, f"Erwartet gefundenes Gewitter.\nSMS: {sms}"
        assert "W45@10" in sms, f"Erwartet gefundenen Wind-Wert.\nSMS: {sms}"
        assert "R5.0@10" in sms, f"Erwartet gefundenen Regen-Wert.\nSMS: {sms}"

        # Fuer diese drei Groessen darf trotz Luecke KEIN `?` erscheinen.
        assert " TH:?" not in sms, f"Gewitter-Fund darf nicht zu `?` werden.\nSMS: {sms}"
        assert " W?" not in sms, f"Wind-Fund darf nicht zu `?` werden.\nSMS: {sms}"
        assert " R?" not in sms, f"Regen-Fund darf nicht zu `?` werden.\nSMS: {sms}"

        # Groessen OHNE Fund (Boeen, Regenwahrscheinlichkeit) zeigen `?`.
        assert "PR?" in sms, f"Erwartet `?` fuer PR ohne Fund.\nSMS: {sms}"
        assert "G?" in sms, f"Erwartet `?` fuer G ohne Fund.\nSMS: {sms}"


class TestAC4LengthBudget:
    """AC-4: `?` belegt genau die Wertstelle, kein Zusatztext -> SMS bleibt
    innerhalb des 160-Zeichen-Budgets."""

    def test_sms_unknown_token_stays_within_length_budget(self):
        segments = [_error_segment(), _regular_segment()]
        sms = _format(segments)

        assert len(sms) <= 160, f"SMS ueberschreitet 160 Zeichen ({len(sms)}).\nSMS: {sms}"
