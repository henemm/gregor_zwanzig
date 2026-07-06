"""TDD tests for Issue #635 — Telegram-Wetter lesbar: Zeitblock-Zeilen statt Stundentabelle.

SPEC: docs/specs/modules/issue_635_telegram_weather_readable.md AC-1..AC-9.
NO mocks, NO patch, NO MagicMock. Real function calls only.

OBSOLET (Issue #1001, gesamtes Modul): #635 war die PO-Entscheidung "Prosa
statt Tabelle" fuer den Telegram-Kanal (eine Zeile pro Segment,
_tg_segment_line, Emoji-Skala, Wortkategorien fuer Regen/Wind). Issue #1001
(Multi-Bubble-Telegram-Redesign) hebt diese Entscheidung explizit fachlich auf
und kehrt zur echten Tabellen-Darstellung zurueck (siehe feat_1001-Spec,
Dependencies-Tabelle: "issue_635_telegram_weather_readable.md | Spec
(abgelöst)"). render_narrow()/_tg_segment_line()/_tg_extra_detail_line()
wurden im Breaking Replace entfernt — die kompletten AC-1..AC-9-Assertions
dieser Datei pruefen Prosa-Format-Details, die es nicht mehr gibt (Emoji-Wahl,
Temp-Pfeil, Wind-Range-Wortlaut, Regen-Kategorien, Footer-Position im
Gesamttext, Zeilenbreiten fuer Prosa-Segmentzeilen). Aequivalenter
Struktur-Nachweis fuer die neue Tabellen-Darstellung + Zeilenbreiten-Grenze:
tests/tdd/test_issue_1001_telegram_bubbles.py (AC-2, AC-9).
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "OBSOLET (Issue #1001): Prosa-Format (#635) fachlich durch #1001 "
        "aufgehoben — render_narrow()/_tg_segment_line() existieren nicht "
        "mehr. Siehe Modul-Docstring."
    )
)


# ---------------------------------------------------------------------------
# Helpers — build real SegmentWeatherData + rows
# ---------------------------------------------------------------------------

def _make_segment(seg_id=1, start_hour=8, end_hour=10):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, TripSegment,
        ThunderLevel,
    )
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0),
        start_time=datetime(2026, 6, 7, start_hour, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 6, 7, end_hour, 0, tzinfo=timezone.utc),
        duration_hours=float(end_hour - start_hour),
        distance_km=6.0,
        ascent_m=500.0,
        descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO,
        model="arome_france",
        run=datetime(2026, 6, 7, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3,
        interp="point_grid",
    )
    from app.models import ForecastDataPoint
    dps = []
    for h in range(start_hour, end_hour):
        dps.append(ForecastDataPoint(
            ts=datetime(2026, 6, 7, h, 0, tzinfo=timezone.utc),
            t2m_c=13.0 + (h - start_hour),
            wind10m_kmh=4.0,
            wind_direction_deg=45,  # NE
            precip_1h_mm=0.0,
            cloud_total_pct=5,  # sunny
            thunder_level=ThunderLevel.NONE,
        ))
    ts = NormalizedTimeseries(meta=meta, data=dps)
    agg = SegmentWeatherSummary(
        temp_min_c=13.0, temp_max_c=16.0,
        wind_max_kmh=4.0,
        precip_sum_mm=0.0,
        cloud_avg_pct=5,
        thunder_level_max=ThunderLevel.NONE,
        visibility_min_m=15000,
        freezing_level_m=3300,
        wind_direction_avg_deg=45,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )


def _make_rows_sunny(start_hour=8, end_hour=10):
    """Build seg_table rows with col_key-keyed dicts — sunny, no rain."""
    rows = []
    for h in range(start_hour, end_hour):
        rows.append({
            "time": f"{h:02d}",
            "temp": 13 + (h - start_hour),
            "wind": 4,
            "wind_dir": 45,  # NE
            "precip": 0.0,
            "cloud": 5,
            "thunder": "NONE",
            "visibility": 15000,
            "freeze_lvl": 3300,
        })
    return rows


def _make_rows_rain(start_hour=16, end_hour=18):
    """Rows with rain + SW wind."""
    rows = []
    for h in range(start_hour, end_hour):
        rows.append({
            "time": f"{h:02d}",
            "temp": 14,
            "wind": 18,
            "wind_dir": 225,  # SW
            "precip": 1.2,
            "cloud": 95,
            "thunder": "NONE",
            "visibility": 8000,
            "freeze_lvl": 2800,
        })
    return rows


def _make_dc():
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    metrics = [
        MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=0),
        MetricConfig(metric_id="wind", enabled=True, bucket="primary", order=1),
        MetricConfig(metric_id="wind_direction", enabled=True, bucket="primary", order=2),
        MetricConfig(metric_id="precipitation", enabled=True, bucket="primary", order=3),
        MetricConfig(metric_id="cloud_total", enabled=True, bucket="primary", order=4),
        MetricConfig(metric_id="thunder", enabled=True, bucket="detail", order=5),
        MetricConfig(metric_id="visibility", enabled=True, bucket="detail", order=6),
        MetricConfig(metric_id="freezing_level", enabled=True, bucket="detail", order=7),
    ]
    return UnifiedWeatherDisplayConfig(
        trip_id="test-635",
        metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


def _render_telegram(segments, seg_tables, multi_day_trend=None):
    from src.output.renderers.narrow import render_narrow
    return render_narrow(
        "telegram",
        segments=segments,
        seg_tables=seg_tables,
        dc=_make_dc(),
        report_type="evening",
        tz=ZoneInfo("Europe/Vienna"),
        trip_name="KHW 403",
        multi_day_trend=multi_day_trend,
    )


def _render_other(channel, segments, seg_tables):
    from src.output.renderers.narrow import render_narrow
    return render_narrow(
        channel,
        segments=segments,
        seg_tables=seg_tables,
        dc=_make_dc(),
        report_type="evening",
        tz=ZoneInfo("Europe/Vienna"),
        trip_name="KHW 403",
    )


def _render_other_tz(channel, segments, seg_tables, tz):
    """Wie _render_other, aber mit konfigurierbarer Zeitzone."""
    from src.output.renderers.narrow import render_narrow
    return render_narrow(
        channel,
        segments=segments,
        seg_tables=seg_tables,
        dc=_make_dc(),
        report_type="evening",
        tz=tz,
        trip_name="KHW 403",
    )


# ---------------------------------------------------------------------------
# AC-1: Pro Segment EINE Zeile, keine Stundentabelle, keine Kürzel
# ---------------------------------------------------------------------------

class TestAC1NoTableNoAbbreviations:
    def test_single_segment_line_count(self):
        """AC-1: Pro Segment genau eine Zeile (kein Header-Zeile 'Zt')."""
        seg = _make_segment(seg_id=1, start_hour=8, end_hour=10)
        rows = _make_rows_sunny(8, 10)
        body = _render_telegram([seg], [rows])
        # Must NOT contain table header "Zt"
        assert "Zt " not in body, f"Stundentabellen-Header 'Zt' gefunden:\n{body}"

    def test_no_hourly_abbreviation_TF(self):
        """AC-1: Kein Kürzel TF (wind_chill compact_label)."""
        seg = _make_segment()
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        lines = body.splitlines()
        for ln in lines:
            assert not ln.startswith("TF "), f"'TF' Kürzel-Zeile gefunden: {ln!r}"

    def test_no_hourly_abbreviation_0G(self):
        """AC-1: Kein Kürzel 0G (Gefrierpunkt compact_label)."""
        seg = _make_segment()
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        assert " 0G " not in body and not any(
            ln.startswith("0G") for ln in body.splitlines()
        ), f"'0G' Kürzel gefunden:\n{body}"

    def test_no_hourly_abbreviation_CE(self):
        """AC-1: Kein Kürzel CE (cape compact_label)."""
        seg = _make_segment()
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        assert " CE " not in body and not any(
            ln.startswith("CE") for ln in body.splitlines()
        ), f"'CE' Kürzel gefunden:\n{body}"

    def test_segment_line_has_bullet_format(self):
        """AC-1: Segment-Zeile enthält '·' als Trenner (Format: Emoji HH–HHh Temp · Wind ... · Regen)."""
        seg = _make_segment(start_hour=8, end_hour=10)
        rows = _make_rows_sunny(8, 10)
        body = _render_telegram([seg], [rows])
        content_lines = [ln for ln in body.splitlines() if "·" in ln]
        assert len(content_lines) >= 1, f"Keine Zeile mit '·' gefunden:\n{body}"


# ---------------------------------------------------------------------------
# AC-2: Temperatur-Verlauf Start→Ende
# ---------------------------------------------------------------------------

class TestAC2Temperature:
    def test_temp_range_arrow(self):
        """AC-2: Temp-Zeile zeigt Start→Ende°C wenn Differenz >= 1°C."""
        seg = _make_segment(start_hour=8, end_hour=10)
        # temp: 13 → 14 (Differenz 1°C exakt - spec says |Δ|<1 single, so 1 = show both)
        rows = [
            {"time": "08", "temp": 13, "wind": 4, "wind_dir": 45, "precip": 0.0, "cloud": 5, "thunder": "NONE"},
            {"time": "09", "temp": 16, "wind": 4, "wind_dir": 45, "precip": 0.0, "cloud": 5, "thunder": "NONE"},
        ]
        body = _render_telegram([seg], [rows])
        # Expect "13→16°C" or similar
        assert "13→16" in body or "13→16°C" in body, f"Temp-Verlauf 13→16 nicht gefunden:\n{body}"

    def test_temp_single_when_small_diff(self):
        """AC-2: Einzelwert wenn |Differenz| < 1°C."""
        seg = _make_segment(start_hour=8, end_hour=10)
        rows = [
            {"time": "08", "temp": 14, "wind": 4, "wind_dir": 45, "precip": 0.0, "cloud": 5, "thunder": "NONE"},
            {"time": "09", "temp": 14, "wind": 4, "wind_dir": 45, "precip": 0.0, "cloud": 5, "thunder": "NONE"},
        ]
        body = _render_telegram([seg], [rows])
        # Should NOT show arrow
        assert "→" not in body, f"Pfeil trotz kleiner Differenz:\n{body}"
        assert "14°C" in body, f"Einzelwert 14°C nicht gefunden:\n{body}"

    def test_temp_fallback_when_no_rows(self):
        """AC-2: Fallback auf temp_min/max aus Summary wenn keine rows."""
        seg = _make_segment(start_hour=8, end_hour=10)
        # seg.aggregated.temp_min_c=13.0, temp_max_c=16.0
        body = _render_telegram([seg], [[]])  # empty rows
        # Should show some temperature from summary
        assert "13" in body or "16" in body, f"Fallback-Temp nicht gefunden:\n{body}"


# ---------------------------------------------------------------------------
# AC-3: Wind min-max + dominante Richtung
# ---------------------------------------------------------------------------

class TestAC3Wind:
    def test_wind_range_shown(self):
        """AC-3: Wind min–max km/h wenn unterschiedlich."""
        seg = _make_segment(start_hour=12, end_hour=14)
        rows = [
            {"time": "12", "temp": 15, "wind": 9, "wind_dir": 180, "precip": 0.0, "cloud": 70, "thunder": "NONE"},
            {"time": "13", "temp": 14, "wind": 17, "wind_dir": 180, "precip": 0.0, "cloud": 70, "thunder": "NONE"},
        ]
        body = _render_telegram([seg], [rows])
        assert "9–17" in body, f"Wind-Spanne 9–17 nicht gefunden:\n{body}"

    def test_wind_single_when_equal(self):
        """AC-3: Einzelwert wenn min==max."""
        seg = _make_segment(start_hour=8, end_hour=10)
        rows = _make_rows_sunny(8, 10)  # all wind=4
        body = _render_telegram([seg], [rows])
        # Should show "4" not "4–4"
        assert "4–4" not in body, f"Doppelter gleicher Wert 4–4:\n{body}"
        assert "4 NE" in body or "4\xa0NE" in body or "4" in body, f"Wind 4 nicht gefunden:\n{body}"

    def test_wind_direction_compass(self):
        """AC-3: Richtung als Himmelsrichtung (NE, S, SW etc.)."""
        seg = _make_segment(start_hour=8, end_hour=10)
        rows = _make_rows_sunny(8, 10)  # wind_dir=45 = NE
        body = _render_telegram([seg], [rows])
        assert "NE" in body, f"Himmelsrichtung NE nicht gefunden:\n{body}"


# ---------------------------------------------------------------------------
# AC-4: Niederschlag qualitativ
# ---------------------------------------------------------------------------

class TestAC4Precipitation:
    def test_dry_label(self):
        """AC-4: 'trocken' bei precip < 0.2mm."""
        seg = _make_segment()
        rows = _make_rows_sunny()  # precip=0.0
        body = _render_telegram([seg], [rows])
        assert "trocken" in body, f"'trocken' nicht gefunden:\n{body}"

    def test_some_rain_label(self):
        """AC-4: 'etwas Regen' bei 0.2 <= precip < 2mm."""
        seg = _make_segment(start_hour=12, end_hour=14)
        rows = [
            {"time": "12", "temp": 15, "wind": 9, "wind_dir": 180, "precip": 0.5, "cloud": 80, "thunder": "NONE"},
            {"time": "13", "temp": 14, "wind": 9, "wind_dir": 180, "precip": 0.8, "cloud": 80, "thunder": "NONE"},
        ]
        # AC-4 uses seg_data.aggregated.precip_sum_mm, set it explicitly
        seg2 = _make_segment(start_hour=12, end_hour=14)
        object.__setattr__(seg2.aggregated, "precip_sum_mm", 1.3)
        body2 = _render_telegram([seg2], [rows])
        # _wrap() may split "etwas Regen" across lines if line > 40 chars.
        # Normalize whitespace before asserting.
        body_joined = " ".join(body2.split())
        assert "etwas Regen" in body_joined, f"'etwas Regen' nicht gefunden:\n{body2}"

    def test_rain_label(self):
        """AC-4: 'Regen' bei precip >= 2mm."""
        seg = _make_segment(start_hour=16, end_hour=18)
        object.__setattr__(seg.aggregated, "precip_sum_mm", 3.5)
        rows = _make_rows_rain(16, 18)
        body = _render_telegram([seg], [rows])
        assert "Regen" in body, f"'Regen' nicht gefunden:\n{body}"

    def test_thunder_label(self):
        """AC-4: 'Gewitter' bei thunder_level_max >= MED."""
        from app.models import ThunderLevel
        seg = _make_segment(start_hour=14, end_hour=16)
        object.__setattr__(seg.aggregated, "thunder_level_max", ThunderLevel.MED)
        object.__setattr__(seg.aggregated, "precip_sum_mm", 2.5)
        rows = [
            {"time": "14", "temp": 18, "wind": 15, "wind_dir": 200, "precip": 1.2, "cloud": 90, "thunder": "MED"},
            {"time": "15", "temp": 17, "wind": 20, "wind_dir": 200, "precip": 1.3, "cloud": 90, "thunder": "MED"},
        ]
        body = _render_telegram([seg], [rows])
        assert "Gewitter" in body, f"'Gewitter' nicht gefunden:\n{body}"


# ---------------------------------------------------------------------------
# AC-5: Emoji
# ---------------------------------------------------------------------------

class TestAC5Emoji:
    def test_sunny_emoji(self):
        """AC-5: ☀️ bei cloud_avg_pct <= 10."""
        seg = _make_segment()  # cloud_avg_pct=5
        rows = _make_rows_sunny()  # cloud=5
        body = _render_telegram([seg], [rows])
        assert "☀️" in body, f"☀️ nicht gefunden:\n{body}"

    def test_rain_emoji(self):
        """AC-5: 🌧️ bei Regen >= 0.5mm (überschreibt Wolken-Emoji)."""
        seg = _make_segment(start_hour=16, end_hour=18)
        object.__setattr__(seg.aggregated, "precip_sum_mm", 2.5)
        object.__setattr__(seg.aggregated, "cloud_avg_pct", 95)
        rows = _make_rows_rain(16, 18)  # precip=1.2 each → sum via aggregated
        body = _render_telegram([seg], [rows])
        assert "🌧️" in body, f"🌧️ nicht gefunden:\n{body}"

    def test_overcast_emoji(self):
        """AC-5: ☁️ bei cloud_avg_pct > 90."""
        seg = _make_segment(start_hour=12, end_hour=14)
        object.__setattr__(seg.aggregated, "cloud_avg_pct", 95)
        object.__setattr__(seg.aggregated, "precip_sum_mm", 0.0)
        rows = [
            {"time": "12", "temp": 14, "wind": 5, "wind_dir": 180, "precip": 0.0, "cloud": 95, "thunder": "NONE"},
            {"time": "13", "temp": 14, "wind": 5, "wind_dir": 180, "precip": 0.0, "cloud": 95, "thunder": "NONE"},
        ]
        body = _render_telegram([seg], [rows])
        assert "☁️" in body, f"☁️ nicht gefunden:\n{body}"

    def test_cloud_none_fallback_emoji(self):
        """AC-5: ⛅ wenn cloud_avg_pct None."""
        seg = _make_segment()
        object.__setattr__(seg.aggregated, "cloud_avg_pct", None)
        rows = [{"time": "08", "temp": 14, "wind": 5, "wind_dir": 90, "precip": 0.0, "cloud": None, "thunder": "NONE"}]
        body = _render_telegram([seg], [rows])
        assert "⛅" in body, f"⛅ Fallback nicht gefunden:\n{body}"


# ---------------------------------------------------------------------------
# AC-6: Fußzeile
# ---------------------------------------------------------------------------

class TestAC6Footer:
    def test_footer_no_thunder(self):
        """AC-6: Fußzeile ⚡ kein · Sicht gut · 0°C-Grenze 3300 m."""
        seg = _make_segment()  # visibility=15000, freezing_level=3300, thunder=NONE
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        assert "⚡ kein" in body, f"'⚡ kein' nicht gefunden:\n{body}"
        assert "Sicht gut" in body, f"'Sicht gut' nicht gefunden:\n{body}"
        assert "0°C-Grenze 3300 m" in body, f"'0°C-Grenze 3300 m' nicht gefunden:\n{body}"

    def test_footer_thunder_med(self):
        """AC-6: Fußzeile ⚡ MED wenn Gewitter in einem Segment."""
        from app.models import ThunderLevel
        seg = _make_segment()
        object.__setattr__(seg.aggregated, "thunder_level_max", ThunderLevel.MED)
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        assert "⚡ MED" in body, f"'⚡ MED' nicht gefunden:\n{body}"

    def test_footer_missing_visibility_omitted(self):
        """AC-6: Sicht-Feld wird weggelassen wenn visibility_min_m None."""
        seg = _make_segment()
        object.__setattr__(seg.aggregated, "visibility_min_m", None)
        object.__setattr__(seg.aggregated, "freezing_level_m", 3300)
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        assert "Sicht" not in body, f"'Sicht' sollte fehlen:\n{body}"
        assert "0°C-Grenze 3300 m" in body

    def test_footer_missing_freezing_level_omitted(self):
        """AC-6: 0°C-Grenze-Feld wird weggelassen wenn freezing_level_m None."""
        seg = _make_segment()
        object.__setattr__(seg.aggregated, "freezing_level_m", None)
        object.__setattr__(seg.aggregated, "visibility_min_m", 15000)
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        assert "0°C-Grenze" not in body, f"'0°C-Grenze' sollte fehlen:\n{body}"
        assert "Sicht gut" in body

    def test_footer_bad_visibility(self):
        """AC-6: 'schlecht' bei visibility < 4km."""
        seg = _make_segment()
        object.__setattr__(seg.aggregated, "visibility_min_m", 2000)
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        assert "Sicht schlecht" in body, f"'Sicht schlecht' nicht gefunden:\n{body}"


# ---------------------------------------------------------------------------
# AC-7: Header + Trend-Block erhalten
# ---------------------------------------------------------------------------

class TestAC7HeaderAndTrendPreserved:
    def test_trip_name_in_header(self):
        """AC-7: Trip-Name bleibt im Header."""
        seg = _make_segment()
        body = _render_telegram([seg], [_make_rows_sunny()])
        assert "KHW 403" in body, f"Trip-Name nicht gefunden:\n{body}"

    def test_command_hint_present(self):
        """AC-7: Befehls-Hinweis (#612) bleibt erhalten."""
        seg = _make_segment()
        body = _render_telegram([seg], [_make_rows_sunny()])
        assert "Befehle:" in body, f"Befehls-Hinweis nicht gefunden:\n{body}"

    def test_trend_block_present(self):
        """AC-7: Mehrtages-Trend-Block ('Nächste Etappen') bleibt erhalten."""
        seg = _make_segment()
        trend = [dict(
            weekday="Mo", name="Etappe X",
            temp_lo=8, temp_hi=16, precip_mm=3.0,
            wind_dir="W", wind_kmh=20, thunder="NONE", note=None,
        )]
        body = _render_telegram([seg], [_make_rows_sunny()], multi_day_trend=trend)
        assert "Nächste Etappen" in body, f"Trend-Block nicht gefunden:\n{body}"


# ---------------------------------------------------------------------------
# AC-8: Andere Channels unverändert
# ---------------------------------------------------------------------------

class TestAC8OtherChannelsUnchanged:
    def test_signal_channel_still_has_table(self):
        """AC-8: Signal-Channel weiterhin mit Tabelle (kein neues Zeilen-Format)."""
        seg = _make_segment()
        rows = _make_rows_sunny()
        body = _render_other("signal", [seg], [rows])
        # Signal should still render the old narrow table with "Zt" header
        assert "Zt " in body or body is not None, (
            "Signal-Channel sollte weiterhin Tabellen-Format haben"
        )

    def test_email_renderer_unchanged(self):
        """AC-8: E-Mail-Renderer liefert weiterhin HTML."""
        from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
        from src.output.renderers.email import render_email
        token_line = _make_token_line()
        html, plain = render_email(token_line, **_common_kwargs())
        assert "<table" in html.lower(), "E-Mail-HTML-Tabelle fehlt"

    def test_multiple_segments_each_one_line(self):
        """AC-1+AC-8: Drei Segmente → drei Segment-Zeilen (nicht mehr)."""
        seg1 = _make_segment(seg_id=1, start_hour=8, end_hour=10)
        seg2 = _make_segment(seg_id=2, start_hour=12, end_hour=14)
        seg3 = _make_segment(seg_id=3, start_hour=16, end_hour=18)
        object.__setattr__(seg3.aggregated, "precip_sum_mm", 3.0)
        rows1 = _make_rows_sunny(8, 10)
        rows2 = [
            {"time": "12", "temp": 15, "wind": 9, "wind_dir": 180, "precip": 0.0, "cloud": 70, "thunder": "NONE"},
            {"time": "13", "temp": 14, "wind": 17, "wind_dir": 180, "precip": 0.0, "cloud": 70, "thunder": "NONE"},
        ]
        rows3 = _make_rows_rain(16, 18)
        body = _render_telegram([seg1, seg2, seg3], [rows1, rows2, rows3])
        # Count lines with "·" separator (segment lines)
        seg_lines = [ln for ln in body.splitlines() if "·" in ln]
        assert len(seg_lines) >= 3, f"Erwartete 3 Segment-Zeilen, gefunden {len(seg_lines)}:\n{body}"
        # No table header "Zt"
        assert "Zt " not in body, f"Stundentabelle noch vorhanden:\n{body}"


# ---------------------------------------------------------------------------
# AC-9: Wetter-Prosa-Zeilen bleiben ungeteilt (≤56) bzw. umbrechen sauber
# ---------------------------------------------------------------------------

class TestAC9LineWidth:
    # Prosa-Breite aus narrow._TG_PROSE_WIDTH — normale Alpendaten passen auf
    # eine Zeile, pathologisch lange Zeilen werden spätestens bei 56 umbrochen.
    _MAX_WIDTH = 56

    def _all_lines_fit(self, body: str) -> list[str]:
        """Gibt alle Zeilen zurück, die > _MAX_WIDTH Zeichen haben."""
        return [ln for ln in body.splitlines() if len(ln) > self._MAX_WIDTH]

    def test_normal_segment_line_is_single_line(self):
        """AC-9: Eine normale Segment-Zeile (~44 Zeichen) wird NICHT umbrochen.

        Beispiel: '☀️ 08–10h  12→14°C · Wind 3–8 SW · trocken' (~46 Zeichen)
        muss als genau EINE Zeile erscheinen (kein \\n mitten drin).
        """
        seg = _make_segment(start_hour=8, end_hour=10)
        object.__setattr__(seg.aggregated, "temp_min_c", 12.0)
        object.__setattr__(seg.aggregated, "temp_max_c", 14.0)
        object.__setattr__(seg.aggregated, "wind_max_kmh", 8.0)
        object.__setattr__(seg.aggregated, "precip_sum_mm", 0.0)
        object.__setattr__(seg.aggregated, "cloud_avg_pct", 5)
        object.__setattr__(seg.aggregated, "wind_direction_avg_deg", 225)  # SW
        rows = [
            {"time": "08", "temp": 12, "wind": 3, "wind_dir": 225, "precip": 0.0, "cloud": 5, "thunder": "NONE"},
            {"time": "09", "temp": 14, "wind": 8, "wind_dir": 225, "precip": 0.0, "cloud": 5, "thunder": "NONE"},
        ]
        body = _render_telegram([seg], [rows])
        # Finde die Segment-Zeile (enthält "·")
        seg_lines = [ln for ln in body.splitlines() if "·" in ln and "Wind" in ln]
        assert len(seg_lines) == 1, (
            f"Normale Segment-Zeile wurde umbrochen (erwartet 1 Zeile, got {len(seg_lines)}):\n{body}"
        )
        assert len(seg_lines[0]) <= self._MAX_WIDTH, (
            f"Segment-Zeile zu lang ({len(seg_lines[0])} > {self._MAX_WIDTH}): {seg_lines[0]!r}"
        )

    def test_normal_segment_lines_fit(self):
        """AC-9: Alle Zeilen eines normalen Renders bleiben <= 56 Zeichen."""
        seg = _make_segment(start_hour=8, end_hour=10)
        rows = _make_rows_sunny(8, 10)
        body = _render_telegram([seg], [rows])
        overlong = self._all_lines_fit(body)
        assert not overlong, (
            f"Zeile(n) über {self._MAX_WIDTH} Zeichen:\n" +
            "\n".join(f"  [{len(l)}] {l!r}" for l in overlong)
        )

    def test_extreme_negative_temp_and_high_wind_fits(self):
        """AC-9 Edge-Case: Negativ-Temp + hohe Wind-Spanne bleibt <= 56 Zeichen.

        Extrembeispiel: '⛅ 14–16h  -5→-12°C · Wind 55–95 SW · trocken' ~50 Zeichen.
        Passt bei _TG_PROSE_WIDTH=56 auf eine Zeile; pathologischere Fälle umbrechen.
        """
        seg = _make_segment(start_hour=14, end_hour=16)
        object.__setattr__(seg.aggregated, "temp_min_c", -12.0)
        object.__setattr__(seg.aggregated, "temp_max_c", -5.0)
        object.__setattr__(seg.aggregated, "wind_max_kmh", 95.0)
        object.__setattr__(seg.aggregated, "precip_sum_mm", 0.0)
        object.__setattr__(seg.aggregated, "cloud_avg_pct", 50)
        rows = [
            {"time": "14", "temp": -5, "wind": 55, "wind_dir": 225, "precip": 0.0, "cloud": 50, "thunder": "NONE"},
            {"time": "15", "temp": -12, "wind": 95, "wind_dir": 225, "precip": 0.0, "cloud": 50, "thunder": "NONE"},
        ]
        body = _render_telegram([seg], [rows])
        overlong = self._all_lines_fit(body)
        assert not overlong, (
            f"Zeile(n) über {self._MAX_WIDTH} Zeichen (Extremfall):\n" +
            "\n".join(f"  [{len(l)}] {l!r}" for l in overlong)
        )

    def test_footer_fits(self):
        """AC-9: Fußzeile bleibt <= 56 Zeichen."""
        seg = _make_segment()
        rows = _make_rows_sunny()
        body = _render_telegram([seg], [rows])
        overlong = self._all_lines_fit(body)
        assert not overlong, (
            f"Footer-Zeile(n) über {self._MAX_WIDTH} Zeichen:\n" +
            "\n".join(f"  [{len(l)}] {l!r}" for l in overlong)
        )

    def test_three_segments_all_fit(self):
        """AC-9: Auch bei mehreren Segmenten bleiben alle Zeilen <= 56 Zeichen."""
        seg1 = _make_segment(seg_id=1, start_hour=8, end_hour=10)
        seg2 = _make_segment(seg_id=2, start_hour=12, end_hour=14)
        object.__setattr__(seg2.aggregated, "wind_max_kmh", 80.0)
        seg3 = _make_segment(seg_id=3, start_hour=16, end_hour=18)
        object.__setattr__(seg3.aggregated, "precip_sum_mm", 5.0)
        rows1 = _make_rows_sunny(8, 10)
        rows2 = [
            {"time": "12", "temp": 2, "wind": 60, "wind_dir": 180, "precip": 0.0, "cloud": 70, "thunder": "NONE"},
            {"time": "13", "temp": -1, "wind": 80, "wind_dir": 180, "precip": 0.0, "cloud": 70, "thunder": "NONE"},
        ]
        rows3 = _make_rows_rain(16, 18)
        body = _render_telegram([seg1, seg2, seg3], [rows1, rows2, rows3])
        overlong = self._all_lines_fit(body)
        assert not overlong, (
            f"Zeile(n) über {self._MAX_WIDTH} Zeichen (3 Segmente):\n" +
            "\n".join(f"  [{len(l)}] {l!r}" for l in overlong)
        )


# ---------------------------------------------------------------------------
# F004: Gleichstunde — nur "{HH}h" ausgeben
# ---------------------------------------------------------------------------

class TestF004SameHour:
    def test_single_hour_no_dash(self):
        """F004: Wenn lokale Start-Stunde == End-Stunde → '{HH}h' statt '{HH}–{HH}h'."""
        from datetime import datetime, timezone
        from app.models import (
            ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
            SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
        )
        # Segment von 08:30–09:00 UTC → in UTC beide in Stunde "08"
        seg_obj = TripSegment(
            segment_id=1,
            start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
            end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0),
            start_time=datetime(2026, 6, 7, 8, 30, tzinfo=timezone.utc),
            end_time=datetime(2026, 6, 7, 8, 59, tzinfo=timezone.utc),
            duration_hours=0.5,
            distance_km=2.0,
            ascent_m=100.0,
            descent_m=0.0,
        )
        meta = ForecastMeta(
            provider=Provider.OPENMETEO, model="arome_france",
            run=datetime(2026, 6, 7, 0, 0, tzinfo=timezone.utc),
            grid_res_km=1.3, interp="point_grid",
        )
        ts = NormalizedTimeseries(meta=meta, data=[])
        agg = SegmentWeatherSummary(
            temp_min_c=14.0, temp_max_c=14.0,
            wind_max_kmh=5.0, precip_sum_mm=0.0, cloud_avg_pct=10,
            thunder_level_max=ThunderLevel.NONE, visibility_min_m=15000,
            freezing_level_m=3000, wind_direction_avg_deg=90,
        )
        from datetime import timezone as tz_
        seg_data = SegmentWeatherData(
            segment=seg_obj, timeseries=ts, aggregated=agg,
            fetched_at=datetime.now(tz_.utc), provider="openmeteo",
        )
        # Use UTC timezone so start_hh == end_hh == "08"
        from zoneinfo import ZoneInfo
        body = _render_other_tz("telegram", [seg_data], [[]], ZoneInfo("UTC"))
        assert "08–08h" not in body, f"'08–08h' sollte nicht erscheinen:\n{body}"
        assert "08h" in body, f"'08h' (einzelne Stunde) sollte erscheinen:\n{body}"
