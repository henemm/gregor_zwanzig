"""Detektions-Unit-Tests fuer die Ziel-Datenluecke (Issue #1331/#1334 Option C).

SPEC: docs/specs/modules/daywindow_gap_and_midnight_fix.md

Fix-Loop 4 (Option C): ``day_window.night_gap()`` (Fix-Loop 3, rechnete die
Luecke NACH) ist ersatzlos entfernt, nachdem F004-F007 wiederholt zeigten,
dass Nachrechnen an Kanten abweicht. ``services.notification_service.
compute_has_gap()`` leitet die Luecke jetzt DIREKT aus dem echten
Renderer-Ergebnis (``day_window.build_day_window_points()``) ab —
Erkennung == Anzeige per Konstruktion. Diese Suite portiert alle bisherigen
``night_gap()``-Szenarien auf ``compute_has_gap()`` (Regressionsschutz).

Fix-Loop 5 (F008): ``day_window.segments_have_gap()`` wurde ENTFERNT.
``sms_trip.py``/``narrow.py`` verodern das gerenderte ``has_gap`` nicht mehr
zusaetzlich mit ihr — sie flaggte jedes ``has_error``-Segment, auch wenn
dessen Stunden im 4-19-Fenster von Nachbarsegmenten (inkl. Stundengrenzen)
redundant gedeckt waren (SMS/Telegram zeigten dann `?`, obwohl E-Mail
"kein Gewitter" zeigte). ``compute_has_gap()`` allein ist jetzt der einzige
Berechnungspunkt fuer alle vier Kanaele; ein ECHTER Fensterausfall fehlt in
``build_day_window_points()`` real und wird davon ohnehin erkannt. Echte
Fixtures, keine Mocks.
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
from src.output.renderers.trip_report import TripReportFormatter
from src.services.notification_service import compute_has_gap

_TZ = ZoneInfo("UTC")


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0, interp="point_grid",
    )


def _dp(hour: int, *, day: int = 20) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=15.0, wind10m_kmh=5.0, gust_kmh=5.0, precip_1h_mm=0.0,
        pop_pct=0, cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _segment(
    start_h: int, end_h: int, *, has_error: bool = False,
    start_day: int = 20, end_day: int = 20,
) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=datetime(2026, 7, start_day, start_h, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, end_day, end_h, 0, tzinfo=timezone.utc),
        duration_hours=abs(float(end_h - start_h)) or 1.0,
        distance_km=8.0, ascent_m=200.0, descent_m=0.0,
    )
    if has_error:
        return SegmentWeatherData(
            segment=seg, timeseries=None, aggregated=SegmentWeatherSummary(),
            fetched_at=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
            provider="openmeteo", has_error=True, error_message="provider timeout",
        )
    data = [_dp(h, day=start_day) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(temp_min_c=10.0, temp_max_c=20.0),
        fetched_at=datetime(2026, 7, 20, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _night_weather(start_h: int, end_h: int) -> NormalizedTimeseries:
    data = [_dp(h) for h in range(start_h, end_h + 1)]
    return NormalizedTimeseries(meta=_meta(), data=data)


class TestComputeHasGapMatchesRenderedOutput:
    """``compute_has_gap()`` isoliert: Ankunft <= 19 + fehlende Nachtdaten ->
    True. Portiert von ``TestNightGapDetection`` (Fix-Loop 3) — dieselben
    Szenarien, jetzt gegen die konstruktionsbasierte Ableitung."""

    def test_arrival_before_window_end_and_no_night_weather_is_a_gap(self):
        segments = [_segment(8, 12)]  # Ankunft 12:00 <= 19
        assert compute_has_gap(segments, None, _TZ) is True

    def test_arrival_before_window_end_and_empty_night_weather_is_a_gap(self):
        segments = [_segment(8, 12)]
        empty = NormalizedTimeseries(meta=_meta(), data=[])
        assert compute_has_gap(segments, empty, _TZ) is True

    def test_arrival_before_window_end_with_complete_night_weather_is_no_gap(self):
        segments = [_segment(8, 12)]
        night = _night_weather(12, 19)
        assert compute_has_gap(segments, night, _TZ) is False

    def test_arrival_after_window_end_is_never_a_gap_even_without_night_weather(self):
        """Ueber-Flagging-Schutz (#1334 AC-6): Ankunft nach 19:00 erwartet
        keine Nach-Ankunft-Stunden im Tagesfenster."""
        segments = [_segment(15, 20)]  # Ankunft 20:00 > 19
        assert compute_has_gap(segments, None, _TZ) is False

    def test_arrival_exactly_at_window_end_is_no_gap_segment_covers_it(self):
        """F006-Regressionsschutz: Ankunft==19:00 -> das letzte Segment liefert
        Stunde 19 bereits inklusive aus seiner eigenen Zeitreihe
        (build_day_window_points() filtert start_h<=h<=end_h, end_h=19).
        night_weather muss dafuer NICHTS mehr beitragen -- auch ``None`` ist
        dann kein Fehlalarm."""
        segments = [_segment(15, 19)]  # Ankunft 19:00 == Fensterende, inklusiv
        assert compute_has_gap(segments, None, _TZ) is False

    def test_night_weather_covering_only_hours_after_arrival_is_no_gap(self):
        """F006-Kernfall: night_weather deckt genau arrival_hour+1..19 ab --
        OHNE die Ankunftsstunde selbst (die liefert das Segment)."""
        segments = [_segment(8, 15)]  # Ankunft 15:00
        night = _night_weather(16, 19)  # NICHT 15 -- das liefert das Segment
        assert compute_has_gap(segments, night, _TZ) is False

    def test_empty_segments_is_never_a_gap(self):
        assert compute_has_gap([], None, _TZ) is False

    def test_night_weather_covering_only_pre_arrival_hours_is_a_gap(self):
        """F004-Regression: Scheduler-Fallback liefert bei Nachtabruf-Fehler
        ``last_segment.timeseries`` statt ``None`` (trip_report_scheduler.py
        ``_fetch_night_weather``). Diese Zeitreihe ist nicht-leer, deckt aber
        wegen des #1334-Filters (end-exklusiv) NIE Stunden ab der Ankunfts-
        stunde ab. Nicht-Leere allein darf ``compute_has_gap`` nicht als
        "abgedeckt" werten -- sonst Fehl-Entwarnung trotz 0 echter Zieldaten."""
        segments = [_segment(8, 15)]  # Ankunft 15:00
        pre_arrival_only = _night_weather(8, 14)  # nur Stunden VOR Ankunft
        assert compute_has_gap(segments, pre_arrival_only, _TZ) is True

    def test_night_weather_covering_arrival_through_end_is_no_gap(self):
        segments = [_segment(8, 15)]  # Ankunft 15:00
        real_night = _night_weather(15, 19)  # deckt [Ankunft..19] echt ab
        assert compute_has_gap(segments, real_night, _TZ) is False

    def test_night_weather_covering_only_one_hour_of_window_is_a_gap(self):
        """F005-Kernfall: nur EINE Stunde des erwarteten Fensters vorhanden
        (hier Stunde 15 von 15-19) darf nicht als "vollstaendig abgedeckt"
        durchgehen -- der Renderer laesst die fehlenden Stunden 16-19 aus."""
        segments = [_segment(8, 15)]  # Ankunft 15:00, Fenster 15-19
        data = [_dp(15)]
        partial = NormalizedTimeseries(meta=_meta(), data=data)
        assert compute_has_gap(segments, partial, _TZ) is True

    def test_night_weather_missing_one_hour_in_the_middle_is_a_gap(self):
        """Loch in der Mitte: alle Stunden 12-19 ausser 17 vorhanden."""
        segments = [_segment(8, 12)]  # Ankunft 12:00, Fenster 12-19
        data = [_dp(h) for h in range(12, 20) if h != 17]
        holey = NormalizedTimeseries(meta=_meta(), data=data)
        assert compute_has_gap(segments, holey, _TZ) is True

    def test_night_weather_covering_exactly_all_expected_hours_is_no_gap(self):
        """Ueber-Flagging-Guard: exakte Deckung des erwarteten Fensters darf
        keinen neuen Fehlalarm ausloesen -- inkl. Randfall Ankunft==19 (das
        erwartete ``night_weather``-Fenster ist dann leer, da Stunde 19
        bereits vom Segment selbst geliefert wird, s. F006)."""
        segments = [_segment(15, 19)]  # Ankunft 19:00, night-Fenster leer
        exact = NormalizedTimeseries(meta=_meta(), data=[_dp(19)])
        assert compute_has_gap(segments, exact, _TZ) is False


class TestF007OvernightSingleSegmentFullRawSeries:
    """F007 (Option-C-Regressionsschutz): Einzelsegment mit Ankunft exakt
    03:00 (``DAY_WINDOW_START_HOUR - 1``) und einer vollen 24h-Roh-Zeitreihe.
    ``build_day_window_points()`` behandelt das als Wraparound-Fenster
    (``start_h(4) > end_h(3)`` -> ``h >= 4 or h <= 3``, deckt alle 24
    Stunden ab) und fuellt 4..19 vollstaendig -- OHNE ``night_weather``.
    Vor Option C flaggte ``night_gap()`` diesen Fall faelschlich als Luecke,
    weil es die Wraparound-Logik von ``build_day_window_points()`` NICHT
    nachbildete."""

    def _overnight_segment(self) -> SegmentWeatherData:
        return _segment(20, 3, start_day=20, end_day=21)  # Ankunft 03:00

    def test_overnight_arrival_at_3am_with_full_raw_series_is_no_gap(self):
        segments = [self._overnight_segment()]
        assert compute_has_gap(segments, None, _TZ) is False

    def test_overnight_arrival_at_3am_produces_no_marker_via_format_email(self):
        """Beweis ueber den ECHTEN Pfad (nicht nur die Detektion): SMS zeigt
        KEIN Unsicherheits-``?`` (Marker ``TH:-`` statt ``TH:?``)."""
        segments = [self._overnight_segment()]
        has_gap = compute_has_gap(segments, None, _TZ)
        assert has_gap is False, "Vorbedingung: F007 darf keinen Gap melden"

        report = TripReportFormatter().format_email(
            segments, trip_name="E1", report_type="morning",
            stage_name="E1", tz=_TZ, has_gap=has_gap,
        )
        assert "TH:-" in report.sms_text, f"SMS: {report.sms_text}"
        assert "TH:?" not in report.sms_text, f"SMS: {report.sms_text}"


class TestF008RedundantSegmentErrorNoFalseGap:
    """F008 (Adversary-Fund, Fix-Loop 5): ein ``has_error``-Segment, dessen
    Stunden im gerenderten 4-19-Fenster von Nachbarsegmenten (inklusive
    Stundengrenzen) redundant gedeckt sind, darf KEINEN Kanal-Fehlalarm
    ausloesen. Vor dem Fix verodern ``sms_trip.py``/``narrow.py`` zusaetzlich
    mit ``day_window.segments_have_gap()`` (jedes ``has_error``-Segment ->
    True), obwohl ``compute_has_gap()`` (aus dem echten Renderer-Ergebnis)
    hier False liefert -- SMS/Telegram zeigten `?`, waehrend E-Mail
    'kein Gewitter' zeigte (ADR-0025-Widerspruch). ``segments_have_gap()``
    selbst ist mit diesem Fix-Loop ersatzlos entfernt (in ``src/`` seit dem
    Entfernen dieser Veroderung ungenutzt)."""

    def _redundant_error_segments(self):
        # seg1 (10-10, has_error) ist eine Sub-Stunde -- ihre einzige Stunde
        # (10) liefern sowohl seg0 (4-10, inklusive Ende) als auch seg2
        # (10-19, inklusive Start) bereits real.
        return [
            _segment(4, 10),
            _segment(10, 10, has_error=True),
            _segment(10, 19),
        ]

    def test_compute_has_gap_is_false_despite_segment_error(self):
        segments = self._redundant_error_segments()
        assert compute_has_gap(segments, None, _TZ) is False

    def test_all_four_channels_agree_no_marker_via_format_email(self):
        segments = self._redundant_error_segments()
        has_gap = compute_has_gap(segments, None, _TZ)
        assert has_gap is False, "Vorbedingung: redundanter Segmentfehler ist kein echter Gap"

        report = TripReportFormatter().format_email(
            segments, trip_name="E1", report_type="morning",
            stage_name="E1", tz=_TZ, has_gap=has_gap,
        )

        assert "TH:-" in report.sms_text, f"SMS: {report.sms_text}"
        assert "TH:?" not in report.sms_text, f"SMS: {report.sms_text}"

        telegram_text = "\n".join(report.telegram_bubbles)
        assert "⚡ kein" in telegram_text, f"Telegram: {telegram_text}"
        assert "⚡ ?" not in telegram_text, f"Telegram: {telegram_text}"

        assert "kein Gewitter" in report.email_plain, f"E-Mail: {report.email_plain}"
        assert "Gewitter ?" not in report.email_plain, f"E-Mail: {report.email_plain}"


class TestF008RealWindowFailureFlagsAllChannels:
    """Korrektheits-Check (Auftrag, Fix-Loop 5): ein ECHTER Segmentfehler, der
    eine 4-19-Fensterstunde WIRKLICH fehlen laesst (nicht redundant von
    Nachbarn gedeckt, kein ``night_weather``), muss weiterhin von
    ``compute_has_gap()`` erkannt werden und in ALLEN vier Kanaelen `?`
    ausloesen -- keine echte Luecken-Erkennung geht durch die F008-Aenderung
    verloren."""

    def _real_failure_segments(self):
        # Einziges Segment 4-19 mit has_error=True: build_day_window_points()
        # liefert dafuer KEINE Punkte, kein night_weather ergaenzt sie.
        return [_segment(4, 19, has_error=True)]

    def test_compute_has_gap_is_true_for_real_window_failure(self):
        segments = self._real_failure_segments()
        assert compute_has_gap(segments, None, _TZ) is True

    def test_all_four_channels_show_unknown_marker_via_format_email(self):
        segments = self._real_failure_segments()
        has_gap = compute_has_gap(segments, None, _TZ)
        assert has_gap is True, "Vorbedingung: echter Fensterausfall ist ein Gap"

        report = TripReportFormatter().format_email(
            segments, trip_name="E1", report_type="morning",
            stage_name="E1", tz=_TZ, has_gap=has_gap,
        )

        assert "TH:?" in report.sms_text, f"SMS: {report.sms_text}"
        assert "TH:-" not in report.sms_text, f"SMS: {report.sms_text}"

        telegram_text = "\n".join(report.telegram_bubbles)
        assert "⚡ ?" in telegram_text, f"Telegram: {telegram_text}"

        assert "Gewitter ?" in report.email_plain, f"E-Mail: {report.email_plain}"
        assert "kein Gewitter" not in report.email_plain, f"E-Mail: {report.email_plain}"
