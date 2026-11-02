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
    """Verhalten statt Quelltext: jeder Fehlwert-Pfad der drei Renderer
    (Compare-HTML, Ausblick-Zelle, Telegram/narrow) liefert NO_VALUE."""
    from output.metric_format import NO_VALUE
    from output.renderers.compare_outlook_metric_ids import format_outlook_value
    from output.renderers.narrow import _cell, _overview_line

    assert NO_VALUE == EN
    assert format_outlook_value(None, {"kind": "numeric"}) == NO_VALUE
    assert _cell("gibt_es_nicht", {}, set()) == NO_VALUE
    assert _overview_line("temperature", [[]], set()).endswith(f" {NO_VALUE}")


@pytest.mark.parametrize("lang", ["de", "en"])
def test_compare_mail_enthaelt_keinen_em_dash(lang):
    """Die gerenderte Compare-Mail (inkl. Fehl-Ort und Ausblick) traegt
    nirgends mehr den EM DASH -- auch nicht als Teil eines Zelltexts."""
    from output.renderers.email.compare_html import render_compare_html

    html = render_compare_html(_result(), outlook_enabled=True, lang=lang)
    assert EM not in html


def _load_validator():
    import importlib.util

    pfad = ROOT / ".claude" / "hooks" / "email_spec_validator.py"
    spec = importlib.util.spec_from_file_location("email_spec_validator_1670", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("lang", ["de", "en"])
def test_validator_akzeptiert_en_dash_als_fehlwert(lang):
    """Echt gerenderte Mail mit Fehl-Ort: der Validator akzeptiert die
    EN-DASH-Fehlwerte; mit EM DASH statt EN DASH wuerde er sie ablehnen."""
    from output.renderers.email.compare_html import render_compare_html

    mod = _load_validator()
    html = render_compare_html(_result(), outlook_enabled=True, lang=lang)
    assert mod.extract_table_rows(html, lang), "Uebersichtstabelle nicht gefunden"
    assert mod.validate_format(html, lang=lang) == []
    assert mod.validate_plausibility(html, lang=lang) == []
    mit_em = html.replace(EN, EM)
    assert mod.validate_format(mit_em, lang=lang) != [], (
        "EM DASH wird noch als Fehlwert akzeptiert")
