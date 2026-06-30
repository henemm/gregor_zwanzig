"""RED tests für fix-911-table-jsx — bestehen nach Implementation.

4 ACs:
- AC-1: class="resp" vollständig durch inline-style ersetzt
- AC-2: explicitly_raw-Gate entfernt → Highlighting gilt immer
- AC-3: OutlookTable border-top:2px solid #1d1c1a + MONO-Font in Cells
- AC-4: AC-10-Tests laufen über render_html (Produktionspfad), bleibt so

Keine Mocks. Echte Renderer werden aufgerufen.
"""
from zoneinfo import ZoneInfo

from tests.tdd.test_issue_911_mail_details import _render, _trend_stage


# ---------------------------------------------------------------------------
# AC-1: class="resp" darf nicht mehr im gerenderten HTML vorkommen
# ---------------------------------------------------------------------------
def test_no_class_resp_in_table():
    """Given Briefing-Mail gerendert, When HTML inspiziert,
    Then kommt 'class="resp"' nicht mehr vor (Outlook-feindliche CSS-Klasse)."""
    html = _render()
    assert 'class="resp"' not in html, (
        'class="resp" darf im gerenderten HTML nicht mehr vorkommen — '
        "CSS-Klassen sind für Outlook problematisch, Style muss inline sein."
    )


def test_no_class_resp_in_empty_table():
    """Given seg_tables mit leerer Row-Liste (Skeleton-Pfad), When gerendert,
    Then enthält das HTML kein 'class="resp"'."""
    html = _render(seg_tables=[[]])
    assert 'class="resp"' not in html, (
        'Auch der leere Tabellen-Skeleton darf kein class="resp" enthalten.'
    )


# ---------------------------------------------------------------------------
# AC-2: Raw-Modus unterdrückt Highlighting NICHT mehr
# ---------------------------------------------------------------------------
def test_raw_mode_still_highlights_gust():
    """Given gust im 'raw'-Format-Modus (kein Indikator), Gust-Wert >45 km/h,
    When über render_email gerendert (baut format_modes + indicator_keys),
    Then trägt die Zelle trotzdem Hintergrund #fad6b8 (warn).

    Läuft über render_email, damit das explicitly_raw-Gate echt aktiv ist:
    format_modes['gust']=='raw' und gust NICHT in indicator_keys → vor dem Fix
    wird das Highlighting unterdrückt (RED). Nach dem Fix gilt es immer (GREEN).
    """
    from datetime import datetime, timezone
    from src.app.models import ForecastDataPoint, ThunderLevel
    from app.metric_catalog import build_default_display_config
    from src.output.renderers.email.helpers import dp_to_row
    from src.output.renderers.email import render_email
    from tests.unit.test_renderers_email import (
        _make_token_line, _make_segment_weather,
    )

    dc = build_default_display_config()
    # Gust auf raw-Format-Modus schalten und Indikator-Anzeige abschalten,
    # sodass gust NICHT in indicator_keys landet → explicitly_raw == True.
    for mc in dc.metrics:
        if mc.metric_id == "gust":
            mc.format_mode = "raw"
            mc.use_friendly_format = False

    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=15.0,
        wind10m_kmh=30.0,
        gust_kmh=55.0,  # >45 → warn
        precip_1h_mm=0.0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        wind_chill_c=12.0,
        snowfall_limit_m=None,
        humidity_pct=55,
    )
    row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
    row["risk"] = "warn"

    token_line = _make_token_line()
    html, _plain = render_email(
        token_line,
        segments=[_make_segment_weather()],
        seg_tables=[[row]],
        display_config=dc,
        tz=ZoneInfo("Europe/Berlin"),
        friendly_keys=set(),
    )

    assert "#fad6b8" in html, (
        "Auch im raw-Modus muss ein Gust-Wert >45 km/h den Warn-Hintergrund "
        "#fad6b8 tragen — das explicitly_raw-Gate wurde entfernt."
    )


# ---------------------------------------------------------------------------
# AC-3: OutlookTable hat border-top:2px solid #1d1c1a + MONO-Font
# ---------------------------------------------------------------------------
def test_outlook_table_has_border_top():
    """Given multi_day_trend mit Daten, When gerendert,
    Then enthält das HTML 'border-top:2px solid #1d1c1a'."""
    trend = [
        _trend_stage(weekday="Di", name="E1", confidence_pct=82),
        _trend_stage(weekday="Mi", name="E2", confidence_pct=55),
    ]
    html = _render(trend=trend)
    assert "border-top:2px solid #1d1c1a" in html, (
        "Die OutlookTable muss eine 2px-Oberkante #1d1c1a tragen (JSX-Vorlage)."
    )


def test_outlook_cells_have_mono_font():
    """Given multi_day_trend mit Daten, When gerendert,
    Then enthält mindestens eine Outlook-Data-Cell font-family mit JetBrains Mono."""
    trend = [
        _trend_stage(weekday="Di", name="E1", confidence_pct=82),
        _trend_stage(weekday="Mi", name="E2", confidence_pct=55),
    ]
    html = _render(trend=trend)
    # Data-Cells der OutlookTable (_otd) müssen MONO-Font tragen
    assert "JetBrains Mono" in html, "JetBrains Mono muss im HTML vorkommen"
    # Genauer: eine <td> der Outlook-Tabelle mit font-family JetBrains Mono
    import re
    td_with_mono = re.search(
        r"<td[^>]*font-family:[^>]*JetBrains Mono[^>]*>", html
    )
    assert td_with_mono is not None, (
        "Mindestens eine <td>-Data-Cell der OutlookTable muss "
        "font-family mit 'JetBrains Mono' tragen (_otd)."
    )
