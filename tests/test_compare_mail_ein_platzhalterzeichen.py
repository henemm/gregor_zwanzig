"""Issue #1670 (TDD RED) AC-3/AC-4: ein einziger "kein Wert"-Platzhalter.

Spec: docs/specs/modules/fix_1670_mail_formatdetails.md
Heute: Compare-Mail mischt EM DASH "—" (Uebersicht, Tabellen, Warn-Zelle)
mit EN DASH "–" (Ausblick). Echte DTOs, echter Renderer, kein Mock.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.user import ComparisonResult, LocationResult, SavedLocation

ROOT = Path(__file__).resolve().parent.parent
EM = "—"
EN = "–"


def _loc(i, name):
    return SavedLocation(id=i, name=name, lat=47.0, lon=11.0, elevation_m=1500)


def _result():
    ok = [
        LocationResult(location=_loc(f"o{n}", f"Ort{n}"), score=50,
                       wind_max=20.0, gust_max=30.0, cloud_avg=40, temp_max=5.0,
                       sunny_hours=3, snow_depth_cm=50.0, snow_new_cm=2.0)
        for n in (1, 2)
    ]
    leer = LocationResult(location=_loc("o3", "Ort3"), score=0, error="Timeout")
    return ComparisonResult(locations=ok + [leer], time_window=(9, 16),
                            target_date=date.today(), created_at=datetime.now())


@pytest.mark.parametrize("lang", ["de", "en"])
def test_keine_zelle_oder_span_besteht_nur_aus_em_dash(lang):
    from output.renderers.email.compare_html import render_compare_html

    html = render_compare_html(_result(), outlook_enabled=True, lang=lang)
    nur_em = re.findall(rf"<(?:td|span|th)[^>]*>\s*{EM}\s*</(?:td|span|th)>", html)
    assert nur_em == [], f"{len(nur_em)} Platzhalter-Zellen mit EM DASH"
    assert re.search(rf">\s*{EN}\s*<", html), "EN-DASH-Platzhalter fehlt ganz"


def test_platzhalter_kommt_aus_einer_konstante():
    from output.metric_format import NO_VALUE

    assert NO_VALUE == EN
    for rel in ("src/output/renderers/email/compare_html.py",
                "src/output/renderers/compare_outlook_metric_ids.py",
                "src/output/renderers/narrow.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")  # doc-compliance-test
        assert f'"{EM}"' not in src, rel
        assert f'"{EN}"' not in src, rel


def test_validator_akzeptiert_en_dash_als_fehlwert():
    src = (ROOT / ".claude/hooks/email_spec_validator.py").read_text(encoding="utf-8")  # doc-compliance-test
    assert f'val == "{EN}"' in src
    assert f'val == "{EM}"' not in src
