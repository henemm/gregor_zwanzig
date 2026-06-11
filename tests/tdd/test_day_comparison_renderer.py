"""
TDD RED: DayComparison-Renderer — Vortag-Vergleich-Sektion (Issue #749)

Kein Mock: Tests bauen echte DayComparison/DayComparisonEntry-Objekte direkt.

AC-1: HTML-Sektion enthält Delta-Wert + G_SUCCESS-Farbe bei BETTER
AC-2: render_day_comparison_html(None) gibt "" zurück
AC-3: MISSING-Metriken erscheinen nicht in der Ausgabe
AC-4: WORSE enthält G_DANGER-Farbe + ▼-Zeichen
AC-5: Plain-Text enthält dieselben Delta-Werte ohne HTML-Tags
AC-6: Farb-Tokens kommen aus design_tokens.py (G_SUCCESS/G_DANGER)
AC-7: Kein Mock

SPEC: docs/specs/modules/issue_749_day_comparison_renderer.md
"""
from services.day_comparison import (
    ComparisonDirection,
    DayComparison,
    DayComparisonEntry,
    MetricDelta,
)


def _missing() -> MetricDelta:
    return MetricDelta(delta=None, direction=ComparisonDirection.MISSING)


def _better(delta: float) -> MetricDelta:
    return MetricDelta(delta=delta, direction=ComparisonDirection.BETTER)


def _worse(delta: float) -> MetricDelta:
    return MetricDelta(delta=delta, direction=ComparisonDirection.WORSE)


def _equal(delta: float) -> MetricDelta:
    return MetricDelta(delta=delta, direction=ComparisonDirection.EQUAL)


def _entry(segment_id: int = 1, **kwargs) -> DayComparisonEntry:
    defaults = dict(
        temp_min=_missing(),
        temp_max=_missing(),
        wind_max=_missing(),
        gust_max=_missing(),
        precip_sum=_missing(),
        thunder=_missing(),
    )
    defaults.update(kwargs)
    return DayComparisonEntry(segment_id=segment_id, **defaults)


class TestAC1_HtmlBetterShowsSuccessColor:
    """AC-1: HTML-Sektion enthält Delta-Wert + G_SUCCESS-Farbe (#3a7d44) bei BETTER."""

    def test_better_precip_shows_value_and_success_color(self):
        """
        GIVEN DayComparison mit precip_sum delta=-3.0, direction=BETTER
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe '-3.0' und '#3a7d44' (G_SUCCESS)
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(precip_sum=_better(-3.0)),
        ])
        result = render_day_comparison_html(comparison)

        assert "-3.0" in result or "3.0" in result
        assert "#3a7d44" in result

    def test_better_wind_shows_value_and_success_color(self):
        """
        GIVEN DayComparison mit wind_max delta=-7.0, direction=BETTER
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe '-7.0' und '#3a7d44'
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(wind_max=_better(-7.0)),
        ])
        result = render_day_comparison_html(comparison)

        assert "7.0" in result
        assert "#3a7d44" in result

    def test_html_section_header_present(self):
        """
        GIVEN nicht-leeres DayComparison
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe 'Vortag-Vergleich' als Sektionsüberschrift
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(precip_sum=_better(-3.0)),
        ])
        result = render_day_comparison_html(comparison)

        assert "Vortag-Vergleich" in result


class TestAC2_NoneGuard:
    """AC-2: render_day_comparison_html(None) gibt exakt '' zurück."""

    def test_none_returns_empty_string_html(self):
        """
        GIVEN comparison=None
        WHEN render_day_comparison_html(None) aufgerufen
        THEN Rückgabewert ist exakt '' (kein Whitespace, kein HTML)
        """
        from src.output.renderers.email.html import render_day_comparison_html

        result = render_day_comparison_html(None)

        assert result == ""

    def test_none_returns_empty_string_plain(self):
        """
        GIVEN comparison=None
        WHEN render_day_comparison_plain(None) aufgerufen
        THEN Rückgabewert ist exakt '' (kein Whitespace)
        """
        from src.output.renderers.email.plain import render_day_comparison_plain

        result = render_day_comparison_plain(None)

        assert result == ""

    def test_empty_entries_html(self):
        """
        GIVEN DayComparison mit leerer entries-Liste
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN gibt '' zurück (keine Sektion ohne Inhalt)
        """
        from src.output.renderers.email.html import render_day_comparison_html

        result = render_day_comparison_html(DayComparison(entries=[]))

        assert result == ""


class TestAC3_MissingRowOmitted:
    """AC-3: MISSING-Metriken erscheinen nicht in der Ausgabe."""

    def test_missing_precip_no_niederschlag_row_html(self):
        """
        GIVEN DayComparisonEntry mit precip_sum.direction=MISSING, alle anderen MISSING
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe weder 'Niederschlag' noch '–'-Platzhalter für Niederschlag
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[_entry()])  # alle MISSING
        result = render_day_comparison_html(comparison)

        # Da alle Metriken MISSING, sollte die gesamte Sektion leer/weg sein
        assert "Niederschlag" not in result

    def test_missing_precip_no_dash_placeholder_html(self):
        """
        GIVEN ein Eintrag bei dem precip_sum MISSING, aber wind_max BETTER
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe keine Niederschlags-Zeile (kein '--' oder '–' für Niederschlag)
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(wind_max=_better(-5.0)),
            # precip_sum bleibt MISSING
        ])
        result = render_day_comparison_html(comparison)

        assert "Niederschlag" not in result
        # Wind-Zeile soll da sein
        assert "5.0" in result or "Wind" in result


class TestAC4_HtmlWorseShowsDangerColor:
    """AC-4: WORSE enthält G_DANGER (#b33a2a) + ▼-Zeichen."""

    def test_worse_wind_shows_danger_color_and_arrow(self):
        """
        GIVEN DayComparisonEntry mit wind_max delta=+8.0, direction=WORSE
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe '#b33a2a' (G_DANGER) und '▼'
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(wind_max=_worse(8.0)),
        ])
        result = render_day_comparison_html(comparison)

        assert "#b33a2a" in result
        assert "▼" in result

    def test_worse_gust_shows_danger_color(self):
        """
        GIVEN DayComparisonEntry mit gust_max delta=+15.0, direction=WORSE
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe '#b33a2a'
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(gust_max=_worse(15.0)),
        ])
        result = render_day_comparison_html(comparison)

        assert "#b33a2a" in result


class TestAC5_PlainTextVariant:
    """AC-5: Plain-Text enthält dieselben Delta-Werte ohne HTML-Tags."""

    def test_plain_contains_delta_value_no_html(self):
        """
        GIVEN DayComparison mit precip_sum delta=-3.0, BETTER
        WHEN render_day_comparison_plain(comparison) aufgerufen
        THEN enthält Ausgabe '3.0' und kein HTML-Tag (<div, <td, <tr, style=)
        """
        from src.output.renderers.email.plain import render_day_comparison_plain

        comparison = DayComparison(entries=[
            _entry(precip_sum=_better(-3.0)),
        ])
        result = render_day_comparison_plain(comparison)

        assert "3.0" in result
        assert "<" not in result

    def test_plain_section_header(self):
        """
        GIVEN nicht-leeres DayComparison
        WHEN render_day_comparison_plain(comparison) aufgerufen
        THEN enthält Ausgabe 'Vortag-Vergleich' als Sektionsüberschrift
        """
        from src.output.renderers.email.plain import render_day_comparison_plain

        comparison = DayComparison(entries=[
            _entry(wind_max=_better(-7.0)),
        ])
        result = render_day_comparison_plain(comparison)

        assert "Vortag-Vergleich" in result

    def test_plain_better_shows_up_arrow(self):
        """
        GIVEN BETTER wind_max
        WHEN render_day_comparison_plain(comparison) aufgerufen
        THEN enthält Ausgabe '▲' (Aufwärts-Pfeil für Verbesserung)
        """
        from src.output.renderers.email.plain import render_day_comparison_plain

        comparison = DayComparison(entries=[
            _entry(wind_max=_better(-5.0)),
        ])
        result = render_day_comparison_plain(comparison)

        assert "▲" in result

    def test_plain_worse_shows_down_arrow(self):
        """
        GIVEN WORSE precip_sum
        WHEN render_day_comparison_plain(comparison) aufgerufen
        THEN enthält Ausgabe '▼'
        """
        from src.output.renderers.email.plain import render_day_comparison_plain

        comparison = DayComparison(entries=[
            _entry(precip_sum=_worse(5.0)),
        ])
        result = render_day_comparison_plain(comparison)

        assert "▼" in result


class TestAC6_ColorTokensFromDesignSystem:
    """AC-6: Farb-Tokens kommen aus design_tokens.py."""

    def test_success_color_matches_design_token(self):
        """
        GIVEN G_SUCCESS aus design_tokens.py = '#3a7d44'
        WHEN render_day_comparison_html(BETTER-Comparison) aufgerufen
        THEN verwendet die Ausgabe exakt diesen Hex-Wert
        """
        from src.output.renderers.email.design_tokens import G_SUCCESS
        from src.output.renderers.email.html import render_day_comparison_html

        assert G_SUCCESS == "#3a7d44"

        comparison = DayComparison(entries=[_entry(precip_sum=_better(-1.0))])
        result = render_day_comparison_html(comparison)

        assert G_SUCCESS in result

    def test_danger_color_matches_design_token(self):
        """
        GIVEN G_DANGER aus design_tokens.py = '#b33a2a'
        WHEN render_day_comparison_html(WORSE-Comparison) aufgerufen
        THEN verwendet die Ausgabe exakt diesen Hex-Wert
        """
        from src.output.renderers.email.design_tokens import G_DANGER
        from src.output.renderers.email.html import render_day_comparison_html

        assert G_DANGER == "#b33a2a"

        comparison = DayComparison(entries=[_entry(wind_max=_worse(10.0))])
        result = render_day_comparison_html(comparison)

        assert G_DANGER in result


class TestMultiSegment:
    """Multi-Segment: Segment-Header nur wenn >1 Eintrag."""

    def test_single_segment_no_segment_header_html(self):
        """
        GIVEN DayComparison mit genau 1 Eintrag
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe kein 'Segment 1:'-Label
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[_entry(1, wind_max=_better(-5.0))])
        result = render_day_comparison_html(comparison)

        assert "Segment 1" not in result

    def test_multi_segment_shows_segment_headers_html(self):
        """
        GIVEN DayComparison mit 2 Einträgen (segment_id 1 und 2)
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe 'Segment 1' und 'Segment 2'
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(1, wind_max=_better(-5.0)),
            _entry(2, precip_sum=_worse(3.0)),
        ])
        result = render_day_comparison_html(comparison)

        assert "Segment 1" in result
        assert "Segment 2" in result


class TestTemperatureNeutral:
    """Temperatur ist neutral (EQUAL) — kein Pfeil, kombinierte Min/Max-Anzeige."""

    def test_temperature_shown_without_direction_arrow_html(self):
        """
        GIVEN temp_min delta=+2.0 (EQUAL) und temp_max delta=+4.0 (EQUAL)
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe Temperatur-Werte aber weder '▲' noch '▼'
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(temp_min=_equal(2.0), temp_max=_equal(4.0)),
        ])
        result = render_day_comparison_html(comparison)

        # Temperatur-Sektion vorhanden
        assert "2" in result or "4" in result
        # Kein Pfeil für Temperatur
        assert "▲" not in result
        assert "▼" not in result


class TestThunderOrdinal:
    """Gewitter: Ordinal-Delta als Text."""

    def test_thunder_better_shows_stufen_text_html(self):
        """
        GIVEN thunder delta=-2 (BETTER)
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe '2 Stufen' oder 'Stufen' und G_SUCCESS-Farbe
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(thunder=MetricDelta(delta=-2.0, direction=ComparisonDirection.BETTER)),
        ])
        result = render_day_comparison_html(comparison)

        assert "Stufen" in result or "stufen" in result.lower()
        assert "#3a7d44" in result

    def test_thunder_equal_shows_unveraendert_html(self):
        """
        GIVEN thunder delta=0 (EQUAL)
        WHEN render_day_comparison_html(comparison) aufgerufen
        THEN enthält Ausgabe 'unverändert'
        """
        from src.output.renderers.email.html import render_day_comparison_html

        comparison = DayComparison(entries=[
            _entry(thunder=MetricDelta(delta=0.0, direction=ComparisonDirection.EQUAL)),
        ])
        result = render_day_comparison_html(comparison)

        assert "unverändert" in result
