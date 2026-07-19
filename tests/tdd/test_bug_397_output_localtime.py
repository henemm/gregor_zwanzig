"""
TDD RED tests for Bugs #397 / #398 / #399 — Briefing output must be fully in local time.

Background (verified root cause):
    Segment times are stored internally as UTC. A previous fix converted only the
    TABLE data rows to local time (`_dp_to_row` uses `local_hour(dp.ts, tz)`), but
    NOT the segment HEADERS, the night-block arrival hour, or the midnight-crossing
    row filter:

      #397  Segment/destination HEADERS still render UTC
            (`seg.start_time.strftime('%H:%M')` in html.py:236-237 / plain.py:174,176 /
            narrow.py:184-185) → header says "08:00–10:00" while the table rows below
            say 10, 11, 12 (local). Contradiction.

      #398  Night block starts at the UTC arrival hour
            (`arrival_hour = last_seg.segment.end_time.hour`, trip_report.py:89), which
            is compared against `local_dt.hour` in `_extract_night_rows`. For CEST
            (UTC+2) the threshold is 2 h too low → the block starts at local 18:00
            instead of the real local arrival 20:00.

      #399  Midnight-crossing segment filter `start_h <= dp.ts.hour <= end_h`
            (trip_report.py:197) is never satisfiable when start_h > end_h (e.g.
            23…01) → 0 rows ("keine Daten").

These tests drive the REAL formatter pipeline
(`TripReportFormatter().format_email(...)`) with constructed UTC fixtures and
`tz=ZoneInfo("Europe/Berlin")`. NO mocks.

Fixture helpers are adapted from:
    tests/unit/test_trip_report_formatter_v2.py        (_make_segment / _make_timeseries shape)
    tests/integration/test_friendly_format_email_and_alerts.py  (SegmentWeatherSummary shape)
    tests/integration/test_compact_summary.py          (timeseries-with-summary shape)

A July date is used so that Europe/Berlin == CEST (UTC+2): a UTC window of
08:00–10:00 therefore maps to local 10:00–12:00.

Expected at RED-time:
    AC-1, AC-2, AC-3, AC-6 → FAIL (the bug)
    AC-4, AC-5             → PASS (no regression / UTC case unaffected)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models import (
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
from output.renderers.trip_report import TripReportFormatter

# July 2026 → Europe/Berlin observes CEST (UTC+2).
_CEST = ZoneInfo("Europe/Berlin")
_UTC = ZoneInfo("UTC")
_DAY = 15
_MONTH = 7
_YEAR = 2026


# ---------------------------------------------------------------------------
# Fixture helpers (mock-free) — real DTOs only.
# ---------------------------------------------------------------------------

def _dp(hour: int, day: int = _DAY, **overrides) -> ForecastDataPoint:
    """ForecastDataPoint at a given UTC hour with sane defaults."""
    defaults = dict(
        ts=datetime(_YEAR, _MONTH, day, hour, 0, tzinfo=timezone.utc),
        t2m_c=10.0 + hour * 0.1,
        wind10m_kmh=10.0,
        gust_kmh=20.0,
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )
    defaults.update(overrides)
    return ForecastDataPoint(**defaults)


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, _DAY, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _summary() -> SegmentWeatherSummary:
    return SegmentWeatherSummary(
        temp_min_c=8.0,
        temp_max_c=12.0,
        temp_avg_c=10.0,
        wind_max_kmh=15.0,
        gust_max_kmh=25.0,
        precip_sum_mm=0.0,
        cloud_avg_pct=50,
        humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
        wind_chill_min_c=6.0,
    )


def _segment_weather(
    *,
    start_hour: int,
    end_hour: int,
    start_day: int = _DAY,
    end_day: int = _DAY,
    data_points: list[ForecastDataPoint] | None = None,
) -> SegmentWeatherData:
    """Build a SegmentWeatherData with a UTC time window + timeseries.

    The timeseries defaults to one data point per UTC hour 0..23 on `start_day`,
    which is the shape the live formatter expects (it filters by hour).
    """
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200.0),
        start_time=datetime(_YEAR, _MONTH, start_day, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(_YEAR, _MONTH, end_day, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float((end_day - start_day) * 24 + end_hour - start_hour),
        distance_km=5.0,
        ascent_m=200.0,
        descent_m=0.0,
    )
    data = data_points if data_points is not None else [_dp(h) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=_summary(),
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _night_timeseries() -> NormalizedTimeseries:
    """Full night coverage: day D hours 0..23 + day D+1 hours 0..6 (all UTC)."""
    data = [_dp(h, day=_DAY) for h in range(0, 24)] + [
        _dp(h, day=_DAY + 1) for h in range(0, 7)
    ]
    return NormalizedTimeseries(meta=_meta(), data=data)


# ===========================================================================
# AC-1 (#397): Segment headers must be LOCAL, consistent with the table rows.
# ===========================================================================

class TestAC1SegmentHeaderLocalTime:
    """Given UTC window 08:00–10:00 + CEST (UTC+2), header must read 10:00–12:00."""

    def test_html_header_shows_local_time(self):
        seg = _segment_weather(start_hour=8, end_hour=10)
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC1 Trip",
            report_type="morning",
            tz=_CEST,
        )
        html = report.email_html

        # Header must show LOCAL window 10:00–12:00 (currently shows UTC 08:00–10:00).
        assert "10:00" in html and "12:00" in html, (
            "Segment-Header zeigt nicht die Ortszeit 10:00–12:00"
        )
        # The buggy UTC header range must NOT be present.
        assert "08:00" not in html, (
            "Segment-Header zeigt noch UTC 08:00 (Bug #397)"
        )

    def test_plain_header_shows_local_time(self):
        seg = _segment_weather(start_hour=8, end_hour=10)
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC1 Trip",
            report_type="morning",
            tz=_CEST,
        )
        plain = report.email_plain
        assert "10:00" in plain and "12:00" in plain
        assert "08:00" not in plain, "Plain-Header zeigt noch UTC 08:00 (Bug #397)"

    def test_header_and_table_use_same_time_base(self):
        """The table rows already show local 10, 11, 12 — the header must agree."""
        seg = _segment_weather(start_hour=8, end_hour=10)
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC1 Trip",
            report_type="morning",
            tz=_CEST,
        )
        plain = report.email_plain
        sidx = plain.find("Segment 1")
        header_line = plain[sidx:plain.find("\n", sidx)]
        # Table data rows are local (10, 11, 12). The header range must therefore
        # read local 10:00–12:00. The buggy UTC start 08:00 must be gone, and the
        # local end 12:00 (which never appears in the UTC header) must be present.
        assert "08:00" not in header_line, (
            f"Header '{header_line.strip()}' nennt noch die UTC-Startzeit 08:00 (Bug #397)"
        )
        assert "12:00" in header_line, (
            f"Header '{header_line.strip()}' nennt nicht die lokale Endzeit 12:00 — "
            f"Header und Tabelle (10,11,12 lokal) widersprechen sich"
        )


# ===========================================================================
# AC-2 (#398): Night block must start at the LOCAL arrival hour.
# ===========================================================================

class TestAC2NightBlockLocalArrival:
    """Last arrival 18:00 UTC == 20:00 CEST → night block must begin at local 20."""

    def _evening_report(self):
        seg = _segment_weather(start_hour=14, end_hour=18)  # arrives 18:00 UTC = 20:00 local
        return TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC2 Trip",
            report_type="evening",
            night_weather=_night_timeseries(),
            tz=_CEST,
        )

    def test_arrival_label_is_local(self):
        report = self._evening_report()
        plain = report.email_plain
        assert "Ankunft 20:00" in plain, (
            "Nacht-Sektion zeigt nicht die lokale Ankunft 20:00 (Bug #398: zeigt UTC 18:00)"
        )

    def test_night_block_first_row_is_local_arrival(self):
        report = self._evening_report()
        plain = report.email_plain
        # Isolate the night section so segment-table rows don't interfere.
        nidx = plain.find("Nacht am Ziel")
        night_section = plain[nidx:]
        # First night block row must be local 20 — NOT local 18 (UTC arrival hour).
        # Row times are the leading 2-digit hour of each table line.
        row_hours = [
            line.strip().split()[0]
            for line in night_section.splitlines()
            if line.strip()[:2].isdigit()
        ]
        assert row_hours, "Nacht-Block enthält keine Datenzeilen"
        assert row_hours[0] == "20", (
            f"Nacht-Block beginnt bei lokaler Stunde {row_hours[0]}, erwartet 20 "
            f"(Bug #398: beginnt 2 h zu frueh bei 18)"
        )
        assert "18" not in row_hours, (
            "Nacht-Block enthält die lokale Stunde 18 vor der Ankunft (Bug #398)"
        )


# ===========================================================================
# AC-3 (#399): Midnight-crossing segment must still produce table rows.
# ===========================================================================

class TestAC3MidnightCrossingRows:
    """UTC window 23:00–01:00 with data at 23/00/01 → table must not be empty."""

    def test_midnight_segment_table_not_empty(self):
        data = [
            _dp(23, day=_DAY),
            _dp(0, day=_DAY + 1),
            _dp(1, day=_DAY + 1),
        ]
        seg = _segment_weather(
            start_hour=23,
            end_hour=1,
            start_day=_DAY,
            end_day=_DAY + 1,
            data_points=data,
        )
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC3 Trip",
            report_type="morning",
            tz=_CEST,
        )
        plain = report.email_plain
        sidx = plain.find("Segment 1")
        segment_section = plain[sidx:]
        assert "keine Daten" not in segment_section.lower(), (
            "Mitternachts-Segment liefert eine leere Tabelle (Bug #399)"
        )
        # At least one data row must be present (local hours 01/02/03 in CEST).
        row_hours = [
            line.strip().split()[0]
            for line in segment_section.splitlines()
            if line.strip()[:2].isdigit()
        ]
        assert row_hours, "Mitternachts-Segment hat keine Datenzeilen (Bug #399)"


# ===========================================================================
# AC-4 (regression): non-wrapping UTC window keeps identical row selection.
# ===========================================================================

class TestAC4NoRowRegression:
    """UTC window 08:00–10:00 must still select the same 3 hourly data points."""

    def test_row_count_unchanged_for_simple_window(self):
        seg = _segment_weather(start_hour=8, end_hour=10)
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC4 Trip",
            report_type="morning",
            tz=_CEST,
        )
        plain = report.email_plain
        sidx = plain.find("Segment 1")
        segment_section = plain[sidx:plain.find("Generated:", sidx)]
        row_hours = [
            line.strip().split()[0]
            for line in segment_section.splitlines()
            if line.strip()[:2].isdigit()
        ]
        # Today UTC hours 8,9,10 are selected → 3 rows. Filter change must not drop them.
        assert len(row_hours) == 3, (
            f"Erwartet 3 Datenzeilen fuer 08–10 UTC, gefunden {len(row_hours)}: {row_hours}"
        )


# ===========================================================================
# AC-5 (UTC fallback): with tz=UTC, header and table stay 08:00–10:00.
# ===========================================================================

class TestAC5UtcFallbackUnchanged:
    """Should be GREEN already: UTC tz must not shift anything."""

    def test_utc_header_and_rows_unchanged(self):
        seg = _segment_weather(start_hour=8, end_hour=10)
        report = TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC5 Trip",
            report_type="morning",
            tz=_UTC,
        )
        plain = report.email_plain
        sidx = plain.find("Segment 1")
        header_line = plain[sidx:plain.find("\n", sidx)]
        # UTC: header window stays 08:00–10:00.
        assert "08:00" in header_line and "10:00" in header_line, (
            f"UTC-Fall: Header '{header_line.strip()}' weicht von 08:00–10:00 ab"
        )
        # And the data rows stay UTC hours 08/09/10.
        segment_section = plain[sidx:plain.find("Generated:", sidx)]
        row_hours = [
            line.strip().split()[0]
            for line in segment_section.splitlines()
            if line.strip()[:2].isdigit()
        ]
        assert row_hours[:3] == ["08", "09", "10"], (
            f"UTC-Fall: Tabellen-Zeiten verschoben: {row_hours}"
        )


# ===========================================================================
# AC-6 (channel consistency): all channels show the SAME local header time.
# ===========================================================================

class TestAC6ChannelConsistency:
    """Same CEST segment → email html/plain + signal + telegram all local."""

    @pytest.fixture
    def report(self):
        seg = _segment_weather(start_hour=8, end_hour=10)
        return TripReportFormatter().format_email(
            segments=[seg],
            trip_name="AC6 Trip",
            report_type="morning",
            tz=_CEST,
        )

    def test_email_html_local_header(self, report):
        assert "10:00" in report.email_html and "12:00" in report.email_html
        assert "08:00" not in report.email_html

    def test_email_plain_local_header(self, report):
        assert "10:00" in report.email_plain and "12:00" in report.email_plain
        assert "08:00" not in report.email_plain

    @pytest.mark.skip(reason="Signal-Kanal entfernt (Bug #610 Schritt 2/2) — TripReport.signal_text nicht mehr vorhanden")
    def test_signal_local_header(self, report):
        """OBSOLET: Signal-Kanal und TripReport.signal_text wurden in Bug #610 entfernt."""
        pass

    def test_telegram_local_header(self, report):
        """#397-Eigenschaft: Telegram zeigt LOKALE Stunden, nicht UTC.

        Issue #1001: die alte "10–12h"-Prosa-Segment-Zeile (_tg_segment_line)
        wurde entfernt. Die lokale Stunde steckt jetzt in der 'Zt'-Spalte der
        Segment-Tabelle — deren Rows werden bereits VOR dem Renderer via
        local_hour() gebaut (trip_report.py._dp_to_row), Bug #397 bleibt also
        strukturell behoben. Nachweis: lokale Stunden 10/11/12 erscheinen als
        Tabellenzeilen, UTC-Stunde 08 taucht in keiner Zeile als Zeit-Wert auf.
        """
        telegram_text = "\n".join(report.telegram_bubbles)
        assert telegram_text, "report.telegram_bubbles darf nicht leer sein"
        assert "10" in telegram_text and "12" in telegram_text, (
            f"Telegram-Kanal zeigt nicht die lokale Stunde 10/12: {telegram_text!r}"
        )
        # Bug-#397-Kern: UTC-Stunde 08 darf NICHT als Zt-Tabellenzeile auftauchen.
        table_time_values = [
            ln.split()[0] for ln in telegram_text.splitlines()
            if re.match(r"^\d{2}\s", ln)
        ]
        assert "08" not in table_time_values, (
            f"Telegram-Kanal zeigt UTC-Stunde 08 als Zt-Tabellenzeile (Bug #397): "
            f"{table_time_values!r}"
        )

    def test_all_channels_agree_on_local_window(self, report):
        """Alle Kanäle zeigen die LOKALE Stunde (Bug #397 Kern-Eigenschaft).

        E-Mail zeigt "12:00" im Header; Telegram zeigt "12" in der 'Zt'-Spalte
        der Segment-Tabelle. Gemeinsamer Nenner: der String "12" muss in allen
        Kanal-Texten vorhanden sein.

        Signal-Kanal entfernt in Bug #610 (Schritt 2/2).
        """
        channels = {
            "email_html": report.email_html,
            "email_plain": report.email_plain,
            "telegram": "\n".join(report.telegram_bubbles),
        }
        missing = [name for name, txt in channels.items() if not txt or "12" not in txt]
        assert not missing, f"Kanäle ohne lokale Endstunde 12 (Bug #397): {missing}"


# ===========================================================================
# AC-7 (F001 fix): SMS-Vorschau-Token müssen die LOKALE Peak-Stunde nennen.
# ===========================================================================

class TestAC7SmsPreviewLocalTokens:
    """Fix-Runde F001: render_sms_preview muss tz an format_sms durchreichen.

    Vorher: SMSTripFormatter().format_sms(...) wurde OHNE tz= aufgerufen → die
    Stunden-Token (R…@h / W…@h / G…@h) zeigten die UTC-Stunde (z.B. @8) statt
    der Ortszeit (@10 für CEST).

    Zwei Verteidigungslinien, beide mock-frei:
      1. Echter Formatter-Lauf: format_sms(..., tz=CEST) verschiebt @8 → @10.
      2. Quell-/Aufruf-Check: render_sms_preview reicht das in _build_report
         berechnete trip_tz tatsächlich an format_sms weiter.
    """

    def _rainy_segment(self) -> SegmentWeatherData:
        """UTC-Fenster 08:00–10:00, Regen+Wind+Böen > 0 → sichtbare @h-Token.

        Wind/Böen überschreiten die Erwähnungsschwelle EINDEUTIG erst ab
        UTC-Stunde 8 (Stunden 0–7: 5.0/10.0 = unter Schwelle; ab 8: 30.0/50.0)
        — damit ist "erste Stunde ≥ Schwelle" unabhängig von der Tagesfenster-
        breite (#1317) immer 8 UTC, und die Assertions prüfen ausschließlich
        die Zeitzonen-Verschiebung (Bug #397).
        """
        rainy_summary = SegmentWeatherSummary(
            temp_min_c=8.0,
            temp_max_c=12.0,
            temp_avg_c=10.0,
            wind_max_kmh=30.0,
            gust_max_kmh=50.0,
            precip_sum_mm=5.0,
            cloud_avg_pct=50,
            humidity_avg_pct=55,
            thunder_level_max=ThunderLevel.NONE,
            wind_chill_min_c=6.0,
        )
        base = _segment_weather(start_hour=8, end_hour=10)
        data = [
            _dp(h, wind10m_kmh=(30.0 if h >= 8 else 5.0), gust_kmh=(50.0 if h >= 8 else 10.0))
            for h in range(0, 24)
        ]
        ts = NormalizedTimeseries(meta=_meta(), data=data)
        return SegmentWeatherData(
            segment=base.segment,
            timeseries=ts,
            aggregated=rainy_summary,
            fetched_at=base.fetched_at,
            provider=base.provider,
        )

    def test_format_sms_cest_shifts_peak_hour_to_local(self):
        """Peak bei UTC 08:00 → CEST-Token muss @10 zeigen, nicht @8."""
        from src.output.renderers.sms_trip import SMSTripFormatter

        seg = self._rainy_segment()
        line = SMSTripFormatter().format_sms(
            [seg], stage_name="Test", report_type="morning", tz=_CEST,
        )
        assert "@10" in line, (
            f"CEST-SMS-Token zeigt nicht die lokale Peak-Stunde @10: {line!r}"
        )
        assert "@8" not in line, (
            f"CEST-SMS-Token zeigt noch die UTC-Stunde @8 (Bug #397/F001): {line!r}"
        )

    def test_format_sms_utc_keeps_utc_hour(self):
        """Regression: tz=UTC darf die Peak-Stunde nicht verschieben (@8 bleibt)."""
        from src.output.renderers.sms_trip import SMSTripFormatter

        seg = self._rainy_segment()
        line = SMSTripFormatter().format_sms(
            [seg], stage_name="Test", report_type="morning", tz=_UTC,
        )
        assert "@8" in line, f"UTC-Fall: Peak-Stunde @8 fehlt: {line!r}"
        assert "@10" not in line, f"UTC-Fall: Stunde fälschlich verschoben: {line!r}"

    def test_preview_service_delegates_sms_to_sent_text(self):
        """Quell-Check: render_sms_preview liefert den mit trip_tz gerenderten
        Versandtext (report.sms_text) statt eines eigenen format_sms-Aufrufs.

        Issue #954 (Bug B): der frühere, redundante ``format_sms(..., tz=trip_tz)``
        -Pfad in render_sms_preview ist entfallen; die Vorschau gibt jetzt exakt
        ``report.sms_text`` zurück. Die Ortszeit-Garantie (Bug #397/F001) bleibt
        erhalten, weil ``_build_report`` das trip_tz berechnet und über
        ``format_email(tz=trip_tz)`` in ``report.sms_text`` einrendert — belegt
        behavioral durch ``test_format_sms_cest_shifts_peak_hour_to_local``. Wir
        patchen NICHTS.
        """
        import inspect  # doc-compliance-test

        from src.services import preview_service

        src = inspect.getsource(preview_service.PreviewService.render_sms_preview)
        assert "report.sms_text" in src, (  # doc-compliance-test
            "render_sms_preview gibt nicht mehr report.sms_text zurück — die "
            "Vorschau würde vom echten Versand (mit trip_tz) divergieren (#954/#397)"
        )

        build_src = inspect.getsource(preview_service.PreviewService._build_report)
        # _build_report muss trip_tz berechnen und an format_email durchreichen —
        # nur so trägt report.sms_text die Ortszeit (Bug #397/F001).
        assert "trip_tz" in build_src, (
            "_build_report berechnet kein trip_tz mehr — report.sms_text kann die "
            "Ortszeit nicht garantieren (Bug #397/F001)"
        )


# ===========================================================================
# AC-8 (F002 fix): E-Mail-Betreff-Datum (Fallback) muss LOKAL sein.
# ===========================================================================

class TestAC8SubjectLocalDate:
    """Fix-Runde F002: _generate_subject nutzte das UTC-Datum als Fallback.

    Segment-Start UTC 22:30 entspricht in CEST (UTC+2) bereits 00:30 des
    Folgetags. Ohne stage_name fällt der Betreff auf das Datum zurück — das
    muss das LOKALE Datum (Folgetag) sein, nicht das UTC-Datum.
    """

    def _subject_for(self, *, tz: ZoneInfo) -> str:
        # Start UTC 22:30 am _DAY → lokal CEST 00:30 am _DAY+1.
        seg_base = _segment_weather(start_hour=22, end_hour=23)
        seg = TripSegment(
            segment_id=1,
            start_point=seg_base.segment.start_point,
            end_point=seg_base.segment.end_point,
            start_time=datetime(_YEAR, _MONTH, _DAY, 22, 30, tzinfo=timezone.utc),
            end_time=datetime(_YEAR, _MONTH, _DAY, 23, 30, tzinfo=timezone.utc),
            duration_hours=1.0,
            distance_km=5.0,
            ascent_m=200.0,
            descent_m=0.0,
        )
        seg_weather = SegmentWeatherData(
            segment=seg,
            timeseries=seg_base.timeseries,
            aggregated=seg_base.aggregated,
            fetched_at=seg_base.fetched_at,
            provider=seg_base.provider,
        )
        report = TripReportFormatter().format_email(
            segments=[seg_weather],
            trip_name="AC8 Trip",
            report_type="morning",
            tz=tz,
        )
        return report.email_subject

    def test_subject_uses_local_date_cest(self):
        """CEST: Betreff enthält das lokale Folgetag-Datum (16.07.2026), nicht 15.07."""
        subject = self._subject_for(tz=_CEST)
        local_date = f"{_DAY + 1:02d}.{_MONTH:02d}.{_YEAR}"   # 16.07.2026
        utc_date = f"{_DAY:02d}.{_MONTH:02d}.{_YEAR}"          # 15.07.2026
        assert local_date in subject, (
            f"Betreff nennt nicht das lokale Datum {local_date} (Bug #397/F002): {subject!r}"
        )
        assert utc_date not in subject, (
            f"Betreff nennt noch das UTC-Datum {utc_date} (Bug #397/F002): {subject!r}"
        )

    def test_subject_uses_utc_date_when_tz_utc(self):
        """Regression: tz=UTC → Betreff bleibt beim UTC-Datum (15.07.2026)."""
        subject = self._subject_for(tz=_UTC)
        utc_date = f"{_DAY:02d}.{_MONTH:02d}.{_YEAR}"          # 15.07.2026
        assert utc_date in subject, (
            f"UTC-Fall: Betreff nennt nicht das UTC-Datum {utc_date}: {subject!r}"
        )
