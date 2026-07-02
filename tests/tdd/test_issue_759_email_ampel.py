"""TDD tests for Issue #759 — 4-stufige Ampelpunkte fuer Wind/Boen/Regen/Regenwahrscheinlichkeit.

RED phase: All tests fail until implementation is complete.

SPEC: docs/specs/modules/issue_759_669_email_ampel_gewitter.md AC-1..AC-6
IMPORTANT: NO mocks, NO patch, NO MagicMock. Real function calls only.
"""
from __future__ import annotations

from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Shared test helpers (adapted from test_issue_640_trend_threshold_times.py)
# ---------------------------------------------------------------------------

def _hv(hour: int, value: float):
    """Shorthand for HourlyValue."""
    from src.output.tokens.dto import HourlyValue
    return HourlyValue(hour=hour, value=value)


def _common_render_kwargs():
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    kw = _common_kwargs()
    tl = _make_token_line()
    return kw, tl


def _render_html(trend=None):
    kw, tl = _common_render_kwargs()
    from src.output.renderers.email.html import render_html
    return render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name=tl.trip_name or "Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
        sent_at=None,
    )


def _make_seg_table_with_values(wind=None, gust=None, precip=None, pop=None):
    """Build a seg_table with one row containing specific metric values."""
    from datetime import datetime, timezone
    from app.metric_catalog import build_default_display_config
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    from src.output.renderers.email.helpers import dp_to_row

    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=wind,
        gust_kmh=gust,
        precip_1h_mm=precip,
        pop_pct=pop,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        wind_chill_c=12.0,
    )
    dc = build_default_display_config()
    row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
    return [row]


# ---------------------------------------------------------------------------
# AC-1: Wind-Zellen zeigen Ampelpunkt im HTML
# ---------------------------------------------------------------------------

class TestWindAmpelDotFourLevels:
    """AC-1: fmt_val('wind', ..., html=True) liefert Ampelpunkt statt km/h-Zahl."""

    def test_issue759_wind_ampel_dot_four_levels(self):
        """AC-1: Wind-Werte 20/40/60/75 km/h → Zellen zeigen 🟢/🟡/🟠/🔴."""
        from src.output.renderers.email.helpers import fmt_val

        # html=True muss Ampelpunkt liefern
        assert fmt_val("wind", 20, html=True) == "🟢", f"Got: {fmt_val('wind', 20, html=True)!r}"
        assert fmt_val("wind", 40, html=True) == "🟡", f"Got: {fmt_val('wind', 40, html=True)!r}"
        assert fmt_val("wind", 60, html=True) == "🟠", f"Got: {fmt_val('wind', 60, html=True)!r}"
        assert fmt_val("wind", 75, html=True) == "🔴", f"Got: {fmt_val('wind', 75, html=True)!r}"

        # html=True darf KEINE km/h-Zahl enthalten
        result_20 = fmt_val("wind", 20, html=True)
        assert "km/h" not in result_20 and "20" not in result_20, (
            f"html=True should NOT contain numeric value: {result_20!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: Boen-Grenzwert ≥80 km/h → rot (Eckwert bewahrt)
# ---------------------------------------------------------------------------

class TestGustAmpelRedBoundary80:
    """AC-2: Boen-Zellen zeigen Ampelpunkt; rote Stufe beginnt bei ≥80 km/h."""

    def test_issue759_gust_ampel_red_boundary_80(self):
        """AC-2: fmt_val('gust', 79, html=True) → 🟠; ('gust', 80, html=True) → 🔴."""
        from src.output.renderers.email.helpers import fmt_val

        result_79 = fmt_val("gust", 79, html=True)
        result_80 = fmt_val("gust", 80, html=True)

        assert result_79 == "🟠", f"79 km/h should be 🟠, got: {result_79!r}"
        assert result_80 == "🔴", f"80 km/h should be 🔴, got: {result_80!r}"

        # Vier Stufen: 40→🟢, 55→🟡, 70→🟠, 85→🔴
        assert fmt_val("gust", 40, html=True) == "🟢"
        assert fmt_val("gust", 55, html=True) == "🟡"
        assert fmt_val("gust", 70, html=True) == "🟠"
        assert fmt_val("gust", 85, html=True) == "🔴"


# ---------------------------------------------------------------------------
# AC-3: Regen-Zellen zeigen Ampelpunkt
# ---------------------------------------------------------------------------

class TestPrecipAmpelDotFourLevels:
    """AC-3: fmt_val('precip', ..., html=True) liefert 4-stufigen Ampelpunkt."""

    def test_issue759_precip_ampel_dot_four_levels(self):
        """AC-3: Regen-Werte 0/2/6/12 mm → Zellen zeigen 🟢/🟡/🟠/🔴."""
        from src.output.renderers.email.helpers import fmt_val

        assert fmt_val("precip", 0.5, html=True) == "🟢", f"Got: {fmt_val('precip', 0.5, html=True)!r}"
        assert fmt_val("precip", 2, html=True) == "🟡", f"Got: {fmt_val('precip', 2, html=True)!r}"
        assert fmt_val("precip", 6, html=True) == "🟠", f"Got: {fmt_val('precip', 6, html=True)!r}"
        assert fmt_val("precip", 12, html=True) == "🔴", f"Got: {fmt_val('precip', 12, html=True)!r}"

        # Grenzen: <1 → 🟢, ≥1 → 🟡, ≥5 → 🟠, ≥10 → 🔴
        assert fmt_val("precip", 0, html=True) == "🟢"
        assert fmt_val("precip", 1, html=True) == "🟡"
        assert fmt_val("precip", 5, html=True) == "🟠"
        assert fmt_val("precip", 10, html=True) == "🔴"


# ---------------------------------------------------------------------------
# AC-4: Regenwahrscheinlichkeit-Zellen zeigen Ampelpunkt
# ---------------------------------------------------------------------------

class TestPopAmpelDotFourLevels:
    """AC-4: fmt_val('pop', ..., html=True) liefert 4-stufigen Ampelpunkt."""

    def test_issue759_pop_ampel_dot_four_levels(self):
        """AC-4: pop-Werte 10/40/65/85 % → Zellen zeigen 🟢/🟡/🟠/🔴."""
        from src.output.renderers.email.helpers import fmt_val

        assert fmt_val("pop", 10, html=True) == "🟢", f"Got: {fmt_val('pop', 10, html=True)!r}"
        assert fmt_val("pop", 40, html=True) == "🟡", f"Got: {fmt_val('pop', 40, html=True)!r}"
        assert fmt_val("pop", 65, html=True) == "🟠", f"Got: {fmt_val('pop', 65, html=True)!r}"
        assert fmt_val("pop", 85, html=True) == "🔴", f"Got: {fmt_val('pop', 85, html=True)!r}"

        # Grenzen: <30 → 🟢, ≥30 → 🟡, ≥60 → 🟠, ≥80 → 🔴
        assert fmt_val("pop", 0, html=True) == "🟢"
        assert fmt_val("pop", 30, html=True) == "🟡"
        assert fmt_val("pop", 60, html=True) == "🟠"
        assert fmt_val("pop", 80, html=True) == "🔴"


# ---------------------------------------------------------------------------
# AC-5: Plain-Text bleibt numerisch und ASCII
# ---------------------------------------------------------------------------

class TestPlainTextStaysNumericAscii:
    """AC-5: html=False liefert numerische Werte ohne Ampel-Emoji."""

    def test_issue759_plain_text_stays_numeric_ascii(self):
        """AC-5: fmt_val(..., html=False) fuer die 4 Keys liefert numerisch, kein Ampel-Emoji."""
        from src.output.renderers.email.helpers import fmt_val

        # Wind: numerisch
        result_wind = fmt_val("wind", 40, html=False)
        assert "40" in result_wind, f"Wind plain should contain '40': {result_wind!r}"
        assert result_wind.isascii(), f"Wind plain should be ASCII: {result_wind!r}"
        assert "🟡" not in result_wind and "🟢" not in result_wind, (
            f"Wind plain must NOT contain ampel emoji: {result_wind!r}"
        )

        # Gust: numerisch
        result_gust = fmt_val("gust", 55, html=False)
        assert "55" in result_gust, f"Gust plain should contain '55': {result_gust!r}"
        assert result_gust.isascii(), f"Gust plain should be ASCII: {result_gust!r}"
        assert "🟡" not in result_gust, f"Gust plain must NOT contain ampel emoji: {result_gust!r}"

        # Precip: numerisch
        result_precip = fmt_val("precip", 2, html=False)
        assert "2" in result_precip, f"Precip plain should contain '2': {result_precip!r}"
        assert result_precip.isascii(), f"Precip plain should be ASCII: {result_precip!r}"
        assert "🟡" not in result_precip, f"Precip plain must NOT contain ampel emoji: {result_precip!r}"

        # Pop: numerisch
        result_pop = fmt_val("pop", 40, html=False)
        assert "40" in result_pop, f"Pop plain should contain '40': {result_pop!r}"
        assert result_pop.isascii(), f"Pop plain should be ASCII: {result_pop!r}"
        assert "🟡" not in result_pop, f"Pop plain must NOT contain ampel emoji: {result_pop!r}"


# ---------------------------------------------------------------------------
# AC-6: Ampel-Legende im HTML-Mail-Body
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Issue #814 AC-10: fmt_val an neue Quelle use_friendly_format angleichen.
#
# Die bestehenden Tests koppeln Ampel an `html=True` OHNE format_modes.
# Das zementiert den Bug: html=True allein reicht nicht — es muss
# use_friendly_format=True (via build_format_modes → Ampel-Modus) kommen.
#
# Diese neuen Tests pruefen das SOLL-Verhalten nach dem Fix:
#   - Roh (use_friendly_format=False) → Zahl auch in HTML (kein Ampel)
#   - Einfach (use_friendly_format=True) → Ampel-Emoji in HTML
# ---------------------------------------------------------------------------

def _make_wind_dp_high():
    """Datenpunkt mit Wind 55 km/h (ueber Gelb-Schwelle 30 km/h)."""
    from datetime import datetime, timezone
    from app.models import ForecastDataPoint, ThunderLevel
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=20.0, wind10m_kmh=55.0, gust_kmh=70.0, precip_1h_mm=0.0,
        pop_pct=10, cloud_total_pct=40, thunder_level=ThunderLevel.NONE,
        wind_chill_c=18.0,
    )


def _render_wind_via_render_email(*, use_friendly: bool):
    """Rendert Wind via render_email — benutzt build_format_modes (KEIN fmt_val direkt).

    Dies ist der korrekte Weg: Die Entscheidung Ampel/Zahl soll allein durch
    use_friendly_format gesteuert werden, nicht durch html=True allein.
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from app.metric_catalog import build_default_display_config
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    from src.output.renderers.email import render_email
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.tokens.dto import TokenLine

    dp = _make_wind_dp_high()
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in ("temperature", "wind")
        mc.use_friendly_format = use_friendly
        mc.format_mode = None  # kein explizites format_mode → use_friendly_format wirkt

    row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=12.0, elevation_m=500.0),
        end_point=GPXPoint(lat=47.1, lon=12.1, elevation_m=900.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=6.0, ascent_m=400.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=2.0, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=55.0, gust_max_kmh=70.0, precip_sum_mm=0.0,
        cloud_avg_pct=40, humidity_avg_pct=50,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=18.0,
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )
    tl = TokenLine(trip_name="759-Angleich-Test", report_type="evening", stage_name="Test")
    return render_email(
        tl, segments=[seg_data], seg_tables=[[row]],
        display_config=dc, tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
        email_format="full", changes=None,
    )


def _data_cells_759(html: str) -> list[str]:
    """Extrahiert Daten-Zellen der Stundentabelle (class='resp')."""
    import re
    m = re.search(r'<table[^>]*data-table="resp"[^>]*>.*?</table>', html, re.S)
    if not m:
        return []
    return re.findall(r'<td[^>]*data-label="[^"]*"[^>]*>(.*?)</td>', m.group(0), re.S)


_AMPEL_EMOJIS_759 = ("🟢", "🟡", "🟠", "🔴")


class TestIssue759WindAmpelNeuQuelle:
    """AC-10: #759-Test an neue Quelle use_friendly_format angleichen.

    Die neuen Tests pruefen das SOLL-Verhalten via render_email (nicht direkt
    fmt_val mit html=True), damit der Bug nicht erneut festgeschrieben wird.
    """

    def test_issue759_wind_ampel_roh_is_number(self):
        """AC-10 RED: Wind Roh (use_friendly=False) = Zahl in HTML, kein Ampel-Emoji.

        Schlaegt HEUTE fehl: build_format_modes gibt 'raw' fuer wind auch bei
        use_friendly=False (weil es sowieso immer 'raw' gibt). Nach Fix muss
        Roh explizit 'raw' ergeben (kein unbeabsichtigter Ampel-Modus).
        Dieser Test sichert, dass Roh=Zahl stabil bleibt.
        """
        html, _plain = _render_wind_via_render_email(use_friendly=False)
        cells = _data_cells_759(html)
        assert cells, "HTML muss Wind-Zellen haben"
        ampel_cells = [c for c in cells if any(e in c for e in _AMPEL_EMOJIS_759)]
        assert not ampel_cells, (
            f"AC-10: Wind Roh muss Zahl liefern, kein Ampel-Emoji. "
            f"Daten-Zellen: {cells!r}"
        )
        # Muss numerisch sein (55 km/h)
        numeric_cells = [c for c in cells if "55" in c or "km" in c.lower()]
        assert numeric_cells, (
            f"AC-10: Wind Roh muss '55' (km/h-Wert) enthalten. Daten-Zellen: {cells!r}"
        )

    def test_issue759_wind_ampel_einfach_html_is_emoji(self):
        """AC-10 RED: Wind Einfach (use_friendly=True) = Ampel-Emoji in HTML.

        Schlaegt HEUTE fehl: build_format_modes gibt 'raw' fuer wind auch bei
        use_friendly=True → kein Ampel → Zahl statt Ampel.
        """
        html, _plain = _render_wind_via_render_email(use_friendly=True)
        cells = _data_cells_759(html)
        assert cells, "HTML muss Wind-Zellen haben"
        ampel_cells = [c for c in cells if any(e in c for e in _AMPEL_EMOJIS_759)]
        assert ampel_cells, (
            f"AC-10 RED: Wind Einfach (use_friendly=True) muss Ampel-Emoji zeigen. "
            f"Daten-Zellen: {cells!r}. "
            f"(Bug: build_format_modes gibt 'raw' statt Ampel-Modus)"
        )
