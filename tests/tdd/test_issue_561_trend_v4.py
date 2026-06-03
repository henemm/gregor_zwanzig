"""
Tests for Issue #561 — Multi-Day Trend v4.0: Spalten-Layout im Abendbericht.

SPEC: docs/specs/modules/multi_day_trend.md v4.0

RED-Zustand (jetzt):
  - _deg_to_compass() + _trend_note() fehlen im Scheduler-Modul
  - HTML-Renderer nutzt noch old keys (stage_name/summary), nicht name/temp_lo/...
  - HTML-Renderer: kein 2px-Haarlinie, kein table-layout:fixed, kein "05 · Ausblick"
  - Plain-Text-Renderer: kein ⚡-Format
"""
from __future__ import annotations
import pytest
from zoneinfo import ZoneInfo


def _trend_stage(
    weekday="Mo", name="Sóller → Tossals Verds",
    temp_lo=8, temp_hi=16, precip_mm=3.0,
    wind_dir="W", wind_kmh=20, thunder="NONE", note=None,
):
    return dict(weekday=weekday, name=name, temp_lo=temp_lo, temp_hi=temp_hi,
                precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
                thunder=thunder, note=note)


def _render_html(trend):
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    from src.output.renderers.email.html import render_html
    kw = _common_kwargs()
    tl = _make_token_line()
    return render_html(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name=tl.trip_name or "Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
    )


def _render_plain(trend):
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    from src.output.renderers.email.plain import render_plain
    kw = _common_kwargs()
    tl = _make_token_line()
    return render_plain(
        segments=kw["segments"], seg_tables=kw["seg_tables"],
        trip_name=tl.trip_name or "Test-Trip", report_type="evening",
        dc=kw["display_config"], night_rows=[], thunder_forecast=None,
        highlights=[], changes=None, stage_name=kw["stage_name"],
        stage_stats=None, multi_day_trend=trend, compact_summary=None,
        daylight=None, tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=kw["friendly_keys"], profile=None, stability_result=None,
    )


# ===========================================================================
# Hilfsfunktionen im Scheduler-Modul
# ===========================================================================

class TestSchedulerHelpers:

    def test_deg_to_compass_exists(self):
        """Given Scheduler-Modul / When _deg_to_compass importiert / Then kein ImportError."""
        from services.trip_report_scheduler import _deg_to_compass  # noqa

    def test_deg_to_compass_west(self):
        """Given 270 Grad / When _deg_to_compass(270) / Then 'W'."""
        from services.trip_report_scheduler import _deg_to_compass
        assert _deg_to_compass(270) == "W"

    def test_deg_to_compass_north(self):
        """Given 0 Grad / When _deg_to_compass(0) / Then 'N'."""
        from services.trip_report_scheduler import _deg_to_compass
        assert _deg_to_compass(0) == "N"

    def test_deg_to_compass_none_returns_empty(self):
        """Given None / When _deg_to_compass(None) / Then ''."""
        from services.trip_report_scheduler import _deg_to_compass
        assert _deg_to_compass(None) == ""

    def test_trend_note_exists(self):
        """Given Scheduler-Modul / When _trend_note importiert / Then kein ImportError."""
        from services.trip_report_scheduler import _trend_note  # noqa

    def test_trend_note_none_when_all_normal(self):
        """Given NONE/1.0mm/25kmh / When _trend_note() / Then None."""
        from services.trip_report_scheduler import _trend_note
        assert _trend_note("NONE", 1.0, 25) is None

    def test_trend_note_thunder_med_returns_text(self):
        """Given thunder=MED / When _trend_note() / Then nicht-leerer String."""
        from services.trip_report_scheduler import _trend_note
        note = _trend_note("MED", 0.0, 20)
        assert note is not None and len(note) > 5


# ===========================================================================
# AC-2: HTML — Spalten-Layout
# ===========================================================================

class TestHtmlTrendLayout:

    def test_html_paper_tint_and_border(self):
        """AC-2: Trend-Block hat 2px-Haarlinie + Paper-Tint."""
        html = _render_html([_trend_stage()])
        assert "border-top:2px solid #1a1a18" in html, "2px-Haarlinie fehlt"
        assert "background:#f6f4ee" in html, "Paper-Tint #f6f4ee fehlt"

    def test_html_fixed_table_layout(self):
        """AC-2: Spalten fluchten via table-layout:fixed."""
        html = _render_html([_trend_stage("Mo"), _trend_stage("Di", name="Di-Etappe")])
        assert "table-layout:fixed" in html, "table-layout:fixed fehlt"

    def test_html_column_headers_present(self):
        """AC-2: Spaltenköpfe TEMP · REGEN · WIND · GEWITTER."""
        html = _render_html([_trend_stage()]).lower()
        for col in ("temp", "regen", "wind", "gewitter"):
            assert col in html, f"Spalte '{col}' fehlt"

    def test_html_weekday_and_name(self):
        """AC-2: Etappenname und Wochentag erscheinen."""
        html = _render_html([_trend_stage(weekday="Mo", name="Sóller → Tossals Verds")])
        assert "Mo" in html and "Sóller" in html

    def test_html_zero_precip_shows_dash(self):
        """AC-5: precip_mm=0 → '–' statt '0 mm'."""
        html = _render_html([_trend_stage(precip_mm=0.0)])
        has_dash = "&ndash;" in html or "–" in html
        assert has_dash, "Null-Niederschlag muss '–' zeigen, nicht '0 mm'"

    def test_html_high_precip_is_blue_bold(self):
        """AC-6: precip_mm > 1 → #2c5a8c + font-weight:700."""
        html = _render_html([_trend_stage(precip_mm=8.0)])
        assert "#2c5a8c" in html, "Hoher Regen muss blau (#2c5a8c) sein"
        assert "font-weight:700" in html, "Hoher Regen muss fett sein"

    def test_html_high_wind_is_accent(self):
        """AC-6: wind_kmh > 30 → #c45a2a."""
        html = _render_html([_trend_stage(wind_kmh=35)])
        assert "#c45a2a" in html, "Starker Wind muss accent-Farbe (#c45a2a) haben"

    def test_html_thunder_med_colored_square(self):
        """AC-2: thunder=MED → Quadrat #c08a1a + Wort 'MED'."""
        html = _render_html([_trend_stage(thunder="MED")])
        assert "#c08a1a" in html, "Thunder MED braucht Quadrat #c08a1a"
        assert "MED" in html, "Thunder MED braucht Wort 'MED'"

    def test_html_thunder_none_shows_kein(self):
        """AC-2: thunder=NONE → Quadrat #9a958a + Wort 'kein'."""
        html = _render_html([_trend_stage(thunder="NONE")])
        assert "#9a958a" in html, "Thunder NONE braucht Quadrat #9a958a"
        assert "kein" in html, "Thunder NONE braucht Wort 'kein'"

    def test_html_note_shown_when_thunder_med(self):
        """AC-7: note erscheint wenn thunder != NONE."""
        html = _render_html([_trend_stage(thunder="MED", note="Gewitter möglich.")])
        assert "Gewitter" in html, "Hinweis-Text muss bei thunder=MED erscheinen"

    def test_html_no_block_when_no_trend(self):
        """AC-3/C5: multi_day_trend=None → kein Block."""
        html = _render_html(None)
        assert "Nächste Etappen" not in html

    def test_html_eyebrow_ausblick(self):
        """AC-2: Eyebrow '05 · Ausblick' nach Design-Spec."""
        html = _render_html([_trend_stage()])
        assert "Ausblick" in html, "Eyebrow 'Ausblick' fehlt"


# ===========================================================================
# AC-8: Plain-Text — Mono-Block
# ===========================================================================

class TestPlainTrendFormat:

    def test_plain_heading(self):
        """AC-8: Heading 'Nächste Etappen' im Plain-Text."""
        plain = _render_plain([_trend_stage()])
        assert "Nächste Etappen" in plain

    def test_plain_thunder_none_lightning_dash(self):
        """AC-8: thunder=NONE → '⚡–' oder '⚡-'."""
        plain = _render_plain([_trend_stage(thunder="NONE")])
        assert "⚡–" in plain or "⚡-" in plain, "Plain thunder=NONE muss '⚡–' zeigen"

    def test_plain_thunder_med_lightning_med(self):
        """AC-8: thunder=MED → '⚡MED'."""
        plain = _render_plain([_trend_stage(thunder="MED")])
        assert "⚡MED" in plain, "Plain thunder=MED muss '⚡MED' zeigen"

    def test_plain_shows_weekday_and_name(self):
        """AC-8: Wochentag + Etappenname erscheinen."""
        plain = _render_plain([_trend_stage(weekday="Di", name="Tossals Verds → Lluc")])
        assert "Di" in plain and "Tossals Verds" in plain

    def test_plain_no_block_when_empty(self):
        """AC-3: multi_day_trend=None → kein Block."""
        plain = _render_plain(None)
        assert "Nächste Etappen" not in plain
