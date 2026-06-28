"""Issues #906 + #907: Render-Bugs in der Briefing-Mail (echter Output, mock-frei).

#906: Trend-Chip-Temperatur darf keine rohen HTML-Entities zeigen.
#907: Stats-Grid-Zellen dürfen kein ungültiges 'nonepadding:' CSS haben.

Beide Tests prüfen den gerenderten HTML-INHALT (nicht nur Existenz) — die QA-Lücke,
durch die diese Defekte bei #898-901 rutschten.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_issue_790_briefing_simplify import _build_segments, _render_html  # noqa: E402


def _scheduler_trend_stage(weekday: str, lo: int, hi: int) -> dict:
    """Trend-Dict wie trip_report_scheduler.py es liefert: temp_lo/temp_hi,
    KEINE temp_min_c/temp_max_c."""
    return {
        "weekday": weekday, "name": "von A nach B", "temp_lo": lo, "temp_hi": hi,
        "precip_mm": 0.0, "wind_dir": "W", "wind_kmh": 12, "thunder": "NONE",
        "note": None, "confidence_pct": 80,
        "hourly_precip": (), "hourly_wind": (), "hourly_gust": (), "hourly_thunder": (),
    }


# --- #906: Trend-Chip-Entities ---

def test_906_trend_chip_no_raw_entities():
    trend = [_scheduler_trend_stage("Mi", 10, 18), _scheduler_trend_stage("Do", 8, 14)]
    html = _render_html(_build_segments(), multi_day_trend=trend)
    start = html.rfind("padding:24px 28px 16px")
    section = html[start:html.find("Antwort-Kommandos", start)] if start != -1 else html
    assert "&#" not in section, f"rohe HTML-Entity im Trend-Chip:\n{section[:500]}"
    assert "&amp;#" not in section, f"doppelt-escapte Entity im Trend-Chip:\n{section[:500]}"
    assert "thinsp" not in section, f"literales 'thinsp' im Trend-Chip:\n{section[:500]}"


def test_906_trend_chip_temp_readable():
    html = _render_html(_build_segments(), multi_day_trend=[_scheduler_trend_stage("Mi", 10, 18)])
    start = html.rfind("padding:24px 28px 16px")
    section = html[start:] if start != -1 else html
    assert re.search(r"10\s*–\s*18", section), f"lesbare Range '10–18' fehlt:\n{section[:500]}"


# --- #907: nonepadding ---

def test_907_no_invalid_nonepadding_css():
    """Stats-Grid darf kein ungültiges 'nonepadding:' enthalten (border='none'
    ohne Semikolon mit padding: verkettet)."""
    html = _render_html(
        _build_segments(),
        stage_stats={"distance_km": 12.3, "ascent_m": 428, "descent_m": 421, "max_elevation_m": 1943},
    )
    assert "nonepadding" not in html, (
        "Ungültiges CSS 'nonepadding:' im Stats-Grid (border='none' ohne Semikolon)"
    )


def test_907_last_stat_cell_valid_style():
    """Die letzte Stat-Zelle (Segmente) hat ein valides padding-Style ohne 'none'-Präfix."""
    html = _render_html(
        _build_segments(),
        stage_stats={"distance_km": 12.3, "ascent_m": 428, "descent_m": 421, "max_elevation_m": 1943},
    )
    # Alle <td>-Styles im Stats-Grid: keiner darf mit 'none' direkt vor 'padding' stehen
    for m in re.finditer(r'<td style="([^"]*)"', html):
        style = m.group(1)
        assert not style.startswith("nonepadding"), f"ungültiges Style: {style}"
