"""#2210 AC-7..AC-10: Rueckbau toter Code, keine leere Stundentabelle bei abgewaehlten Metriken."""
from __future__ import annotations

from zoneinfo import ZoneInfo

from tests.tdd.test_bug305_mobile_email import _FULL_ROW, _build_seg_data, _render_full_html


def test_ac7_toter_mobil_code_entfernt():  # doc-compliance-test
    import output.renderers.email.html as html_modul

    assert not hasattr(html_modul, "_render_mobile_hour_list")


def test_ac7_trip_mail_rendert_weiter():
    assert "<table" in _render_full_html()


def test_ac8_alle_metriken_abgewaehlt_keine_tabelle():
    from output.renderers.email.html import _render_html_table

    rows = [_FULL_ROW.copy() for _ in range(3)]
    assert _render_html_table(rows, friendly_keys=set(), allowed_col_keys=set()) == ""


def test_ac9_ganze_mail_ohne_stundengeruest():
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html

    dc = build_default_display_config()
    for m in dc.metrics:
        m.enabled = False
    html = render_html(
        segments=[_build_seg_data()], seg_tables=[[_FULL_ROW.copy() for _ in range(5)]],
        trip_name="KHW 403", report_type="morning", dc=dc, night_rows=[],
        thunder_forecast=None, highlights=[], changes=None,
        stage_name="Etappe", stage_stats={"distance_km": 14.5, "ascent_m": 820},
        multi_day_trend=None, compact_summary="Guter Wandertag.", daylight=None,
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )
    assert "KHW 403" in html
    assert ">Time</th>" not in html
    assert ">Risk</th>" not in html


def test_ac10_sichtbare_metrik_behaelt_geruest():
    from output.renderers.email.html import _render_html_table

    rows = [_FULL_ROW.copy() for _ in range(3)]
    out = _render_html_table(rows, friendly_keys=set(), allowed_col_keys={"wind"})
    assert "Time" in out and "Risk" in out
    assert "<thead>" in _render_html_table(rows, friendly_keys=set())
    assert "<thead>" in _render_html_table([], friendly_keys=set(), allowed_col_keys=set())
