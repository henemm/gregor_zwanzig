"""
TDD RED: Vortag-Vergleich-Integration F4 (#750) + F6 (#752)

Kein Mock: Tests bauen echte SegmentWeatherData, nutzen den echten
DayComparisonService, echte format_email/render_narrow und echten
WeatherSnapshotService (Datei-Roundtrip).

AC-1: format_email mit day_comparison → Vortag-Vergleich-Sektion in HTML UND Plain
AC-2: format_email mit day_comparison=None → keine Sektion
AC-3: TripReportConfig.show_yesterday_comparison existiert, Default True, abschaltbar
AC-4: format_email akzeptiert day_comparison optional (rückwärtskompatibel)
AC-5: WeatherSnapshotService lädt datierten Snapshot mandantengetrennt (per user_id)
AC-6: render_narrow mit day_comparison → "Vortag:"-Zeile, max 3 Metriken, |delta| desc
AC-7: render_narrow ohne day_comparison → keine "Vortag"-Zeile

SPEC: docs/specs/modules/issue_750_752_vortag_vergleich_integration.md
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Europe/Berlin")


# ---------------------------------------------------------------------------
# Fixtures — echte SegmentWeatherData mit Timeseries + aggregierten Werten
# ---------------------------------------------------------------------------

def _segment_with_weather(segment_id, *, target_date=None, **agg_kwargs):
    """SegmentWeatherData mit Stunden-Timeseries und gesetzten Aggregat-Werten."""
    from app.models import (
        ForecastDataPoint,
        ForecastMeta,
        GPXPoint,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
        TripSegment,
    )

    td = target_date or (date.today() + timedelta(days=1))
    start = datetime.combine(td, time(8, 0), tzinfo=timezone.utc)
    end = datetime.combine(td, time(12, 0), tzinfo=timezone.utc)
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=1500.0),
        end_point=GPXPoint(lat=42.2, lon=9.2, elevation_m=1600.0),
        start_time=start, end_time=end,
        duration_hours=4.0, distance_km=12.0, ascent_m=600.0, descent_m=300.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="icon_seamless",
                        grid_res_km=1.0)
    data = [
        ForecastDataPoint(
            ts=start + timedelta(hours=h),
            t2m_c=12.0 + h, wind10m_kmh=20.0 + h * 3, gust_kmh=35.0 + h * 3,
            precip_1h_mm=0.5, cloud_total_pct=40,
        )
        for h in range(4)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    return SegmentWeatherData(
        segment=seg, timeseries=ts,
        aggregated=SegmentWeatherSummary(**agg_kwargs),
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _comparison(today_segs, yday_segs):
    """Echte DayComparison über den realen Service."""
    from services.day_comparison import DayComparisonService
    return DayComparisonService().compare(today_segs, yday_segs)


def _format(day_comparison=..., segs=None, report_config=...):
    """format_email-Aufruf. day_comparison=...  / report_config=... → kwarg weglassen."""
    from app.metric_catalog import build_default_display_config
    from output.renderers.trip_report import TripReportFormatter

    segs = segs or [_segment_with_weather(1, temp_min_c=8.0, temp_max_c=18.0,
                                          wind_max_kmh=25.0, precip_sum_mm=2.0)]
    kwargs = dict(
        segments=segs, trip_name="GR20 Test", report_type="morning",
        display_config=build_default_display_config(), tz=TZ,
    )
    if day_comparison is not ...:
        kwargs["day_comparison"] = day_comparison
    if report_config is not ...:
        kwargs["report_config"] = report_config
    return TripReportFormatter().format_email(**kwargs)


# ===========================================================================
# AC-1: format_email mit day_comparison → Sektion in HTML UND Plain
# ===========================================================================

class TestAC1EmailSectionRendered:

    def test_one_line_in_html_and_plain(self):
        """
        GIVEN heutige + gestrige Segmente mit echten Deltas (heute wärmer, trockener)
        WHEN format_email(day_comparison=...) erzeugt wird
        THEN erscheint die EINE Vortag-Einordnungszeile in HTML UND Plain —
             KEINE alte Delta-pro-Segment-Tabelle (Issue #790).
        """
        today = [_segment_with_weather(1, temp_min_c=8.0, temp_max_c=18.0,
                                       wind_max_kmh=20.0, precip_sum_mm=2.0)]
        yday = [_segment_with_weather(1, temp_min_c=6.0, temp_max_c=15.0,
                                      wind_max_kmh=35.0, precip_sum_mm=12.0)]
        dc = _comparison(today, yday)

        report = _format(day_comparison=dc, segs=today)

        assert "Vortag: heute" in report.email_html, \
            "HTML-Mail muss die Vortag-Einordnungszeile enthalten"
        assert "Vortag: heute" in report.email_plain, \
            "Plain-Mail muss die Vortag-Einordnungszeile enthalten"
        # Alte Sektion/Segment-Tabelle darf nicht mehr erscheinen
        assert "Vortag-Vergleich" not in report.email_html
        assert "Vortag-Vergleich" not in report.email_plain


# ===========================================================================
# AC-2: format_email mit day_comparison=None → keine Sektion
# ===========================================================================

class TestAC2NoSnapshotNoSection:

    def test_none_renders_no_section(self):
        """
        GIVEN kein Vortag (day_comparison=None)
        WHEN format_email erzeugt wird
        THEN erscheint KEINE Vortag-Vergleich-Sektion
        """
        report = _format(day_comparison=None)
        assert "Vortag-Vergleich" not in report.email_plain
        assert "Vortag-Vergleich" not in report.email_html


# ===========================================================================
# AC-3: TripReportConfig.show_yesterday_comparison
# ===========================================================================

class TestAC3Toggle:

    def test_field_default_true(self):
        """show_yesterday_comparison existiert und ist standardmäßig an."""
        from app.models import TripReportConfig
        assert TripReportConfig().show_yesterday_comparison is True

    def test_field_can_disable(self):
        """show_yesterday_comparison lässt sich abschalten."""
        from app.models import TripReportConfig
        assert TripReportConfig(show_yesterday_comparison=False).show_yesterday_comparison is False

    def test_toggle_off_suppresses_section_even_with_comparison(self):
        """show_yesterday_comparison=False → Sektion fehlt trotz vorhandenem DayComparison."""
        from app.models import TripReportConfig
        today = [_segment_with_weather(1, temp_min_c=8.0, temp_max_c=18.0,
                                       wind_max_kmh=20.0, precip_sum_mm=2.0)]
        yday = [_segment_with_weather(1, temp_min_c=6.0, temp_max_c=15.0,
                                      wind_max_kmh=35.0, precip_sum_mm=12.0)]
        dc = _comparison(today, yday)
        report = _format(day_comparison=dc, segs=today,
                         report_config=TripReportConfig(show_yesterday_comparison=False))
        assert "Vortag-Vergleich" not in report.email_html
        assert "Vortag-Vergleich" not in report.email_plain


# ===========================================================================
# AC-4: Rückwärtskompatibilität — kwarg optional
# ===========================================================================

class TestAC4BackwardCompat:

    def test_optional_day_comparison_kwarg(self):
        """
        GIVEN alter Aufrufstil mit explizitem day_comparison=None
        WHEN format_email aufgerufen wird
        THEN valider TripReport ohne Sektion (Default-Verhalten)
        """
        report = _format(day_comparison=None)
        assert report.email_subject
        assert "Vortag-Vergleich" not in report.email_plain


# ===========================================================================
# AC-5: Mandantentrennung beim Laden des datierten Snapshots
# ===========================================================================

class TestAC5PerUserSnapshot:

    def test_load_dated_is_user_scoped(self, tmp_path, monkeypatch):
        """
        GIVEN userA und userB speichern je einen datierten Vortag-Snapshot
        WHEN load_dated pro user_id geladen wird
        THEN sieht jeder Nutzer nur seine eigenen Werte (keine Vermischung)
        """
        import app.loader as loader
        from services.weather_snapshot import WeatherSnapshotService

        # Persistenz in tmp umlenken — echte Datei-Roundtrips, kein Mock.
        monkeypatch.setattr(
            loader, "get_snapshots_dir",
            lambda uid: tmp_path / uid / "snapshots",
        )

        yday = date.today()
        a_seg = _segment_with_weather(1, target_date=yday, precip_sum_mm=2.0)
        b_seg = _segment_with_weather(1, target_date=yday, precip_sum_mm=99.0)

        WeatherSnapshotService("userA").save_dated("trip1", yday, [a_seg])
        WeatherSnapshotService("userB").save_dated("trip1", yday, [b_seg])

        loaded_a = WeatherSnapshotService("userA").load_dated("trip1", yday)
        loaded_b = WeatherSnapshotService("userB").load_dated("trip1", yday)

        assert loaded_a is not None and loaded_b is not None
        assert loaded_a[0].aggregated.precip_sum_mm == 2.0
        assert loaded_b[0].aggregated.precip_sum_mm == 99.0


# ===========================================================================
# AC-6 / AC-7: Telegram-Kurzform
# ===========================================================================

def _narrow(day_comparison=...):
    """render_telegram_bubbles-Aufruf (Issue #1001). day_comparison=... → kwarg weglassen.

    Gibt alle Bubble-Texte verbunden zurueck (die Vortag-Zeile steckt in der
    Kurzuebersicht-Bubble) — Substring-Assertions bleiben unveraendert gueltig.
    """
    from app.metric_catalog import build_default_display_config
    from output.renderers.narrow import render_telegram_bubbles

    seg = _segment_with_weather(1, temp_min_c=8.0, temp_max_c=18.0,
                                wind_max_kmh=20.0, precip_sum_mm=2.0)
    rows = [{"time": "08:00", "t2m_c": "12", "wind10m_kmh": "20"}]
    kwargs = dict(
        segments=[seg], seg_tables=[rows],
        dc=build_default_display_config(), report_type="morning",
        tz=TZ, trip_name="GR20 Test",
    )
    if day_comparison is not ...:
        kwargs["day_comparison"] = day_comparison
    bubbles = render_telegram_bubbles(**kwargs)
    return "\n".join(b.text for b in bubbles)


class TestAC6TelegramTopThree:

    def test_max_three_metrics_sorted_by_delta(self):
        """
        GIVEN ein Vortag-Vergleich mit 5 abweichenden Metriken
              (precip |10|, wind |8|, gust |6|, temp_max |4|, temp_min |2|)
        WHEN das Telegram-Briefing erzeugt wird
        THEN enthält es eine "Vortag:"-Zeile mit den 3 größten Abweichungen
             (Niederschlag, Wind, Böen); die kleineren (Temperatur) fehlen
        """
        today = [_segment_with_weather(
            1, temp_min_c=10.0, temp_max_c=20.0, wind_max_kmh=28.0,
            gust_max_kmh=46.0, precip_sum_mm=2.0)]
        yday = [_segment_with_weather(
            1, temp_min_c=8.0, temp_max_c=16.0, wind_max_kmh=20.0,
            gust_max_kmh=40.0, precip_sum_mm=12.0)]
        dc = _comparison(today, yday)

        out = _narrow(day_comparison=dc)

        assert "Vortag" in out, "Telegram-Briefing muss eine Vortag-Zeile enthalten"
        vortag_block = out[out.index("Vortag"):]
        # Top-3 nach |delta|: Niederschlag(10), Wind(8), Böen(6)
        assert "Regen" in vortag_block or "Niederschlag" in vortag_block
        assert "Wind" in vortag_block
        assert "Böen" in vortag_block
        # Temperatur (|4| / |2|) liegt außerhalb der Top-3 → darf nicht erscheinen
        assert "Temp" not in vortag_block, \
            "Nur die 3 größten Abweichungen — Temperatur (Rang 4/5) muss fehlen"


class TestAC7TelegramNoSnapshot:

    def test_none_no_vortag_line(self):
        """
        GIVEN kein Vortag-Snapshot (day_comparison=None)
        WHEN das Telegram-Briefing erzeugt wird
        THEN entfällt die Vortag-Zeile komplett
        """
        out = _narrow(day_comparison=None)
        assert "Vortag" not in out
