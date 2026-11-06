"""Issue #1670 (TDD RED) AC-5/AC-6: Ausblick-Wind ohne Daten zeigt "–", nicht "0".

Spec: docs/specs/modules/fix_1670_mail_formatdetails.md
Echte Punkte, echter build_outlook_row/render_outlook_table, kein Mock.
"""
from __future__ import annotations
from app.ampel import resolve_ampel

import re
from datetime import datetime, timezone

from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
from output.renderers.email.outlook import build_outlook_row, render_outlook_table

EN = "–"


def _pts(wind, gust):
    return [
        ForecastDataPoint(
            ts=datetime(2026, 11, 3, h, 0, tzinfo=timezone.utc),
            t2m_c=8.0, wind10m_kmh=wind, gust_kmh=gust, precip_1h_mm=0.0,
            thunder_level=ThunderLevel.NONE,
        )
        for h in (8, 12, 16)
    ]


def _cells(html):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)[1:]
    return [re.sub(r"<[^>]+>", "", c).strip()
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[0], re.S)]


def _render(wind, gust, wmax, gmax):
    summary = SegmentWeatherSummary(wind_max_kmh=wmax, gust_max_kmh=gmax)
    row = build_outlook_row(summary, _pts(wind, gust), "Di", timezone.utc, context="vergleich")
    return render_outlook_table([row], show_acc=False, ampel=resolve_ampel(None))


def test_ohne_winddaten_zeigen_wind_und_boeen_strich():
    cells = _cells(_render(None, None, None, None))
    assert "0" not in cells, cells
    assert cells.count(EN) >= 2, cells


def test_mit_winddaten_bleibt_zelle_unveraendert():
    cells = _cells(_render(15.0, 25.0, 15.0, 25.0))
    assert "15" in cells and "25" in cells, cells


def test_boeen_nie_unter_wind_bei_konsistenten_daten():
    cells = _cells(_render(15.0, 25.0, 15.0, 25.0))
    wind, boeen = cells.index("15"), cells.index("25")
    assert wind < boeen
    assert int(cells[boeen]) >= int(cells[wind])
