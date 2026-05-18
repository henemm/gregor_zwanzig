"""
Tests für Issue #257 — Trip-Briefing-Mail: Dunkel-Footer, Pill-System,
Mobile-Karten-Layout, Dark-Mode-Schutz.

SPEC: docs/specs/modules/issue_257_trip_briefing_mail_polish.md
TESTS-SPEC: docs/specs/tests/issue_257_trip_briefing_polish_tests.md
EPIC: #236 (Sub-Issue 3)

RED-Zustand (jetzt):
  html.py hat noch G_PAPER-Footer, kein color-scheme-Meta, kein @media, kein data-label.
  helpers.py hat kein pill_html() → ImportError.
  preview_email.py kennt kein --profile-Argument.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.test_renderers_email import _common_kwargs, _make_token_line


REPO_ROOT = Path(__file__).resolve().parents[2]
HTML_PY = REPO_ROOT / "src" / "output" / "renderers" / "email" / "html.py"


def _render_minimal_html(profile=None) -> str:
    """Rendert ein minimales Trip-Briefing-HTML ohne Netzwerk-Call."""
    from src.output.renderers.email.html import render_html
    kwargs = _common_kwargs()
    token_line = _make_token_line()
    return render_html(
        segments=kwargs["segments"],
        seg_tables=kwargs["seg_tables"],
        trip_name=token_line.trip_name or token_line.stage_name or "Test-Trip",
        report_type=token_line.report_type,
        dc=kwargs["display_config"],
        night_rows=kwargs["night_rows"] or [],
        thunder_forecast=kwargs["thunder_forecast"],
        highlights=kwargs["highlights"],
        changes=kwargs["changes"],
        stage_name=kwargs["stage_name"],
        stage_stats=kwargs["stage_stats"],
        multi_day_trend=kwargs["multi_day_trend"],
        compact_summary=kwargs["compact_summary"],
        daylight=kwargs["daylight"],
        tz=kwargs["tz"],
        friendly_keys=kwargs["friendly_keys"],
        profile=profile,
    )


# ---------------------------------------------------------------------------
# AC-1: Dunkel-Footer
# ---------------------------------------------------------------------------

def test_ac1_footer_has_ink_background():
    """
    AC-1 (Teil 1): Footer-CSS enthält background:#1a1a18 (G_INK).

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN der <style>-Block auf die .footer-Klasse geprüft wird
    THEN enthält diese background:#1a1a18
    """
    html = _render_minimal_html()
    # G_INK = '#1a1a18' — muss im CSS-Block als Footer-Hintergrund erscheinen
    html_compact = html.replace(" ", "").replace("\n", "")
    assert "background:#1a1a18" in html_compact, (
        "Footer-Hintergrund ist noch nicht #1a1a18 (G_INK) — Dunkel-Footer fehlt"
    )


def test_ac1_footer_text_is_white():
    """
    AC-1 (Teil 2): Footer-Text ist weiß (#ffffff).

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN der Footer-CSS-Block analysiert wird
    THEN enthält die .footer-Deklaration color:#ffffff
    """
    html = _render_minimal_html()
    # Im .footer-CSS: color:#ffffff (weißer Text auf dunklem Hintergrund)
    style_block = html.split("</style>")[0] if "</style>" in html else html
    style_compact = style_block.replace(" ", "").replace("\n", "")
    assert "color:#ffffff" in style_compact, (
        "Footer-Textfarbe ist nicht #ffffff — Dunkel-Footer fehlt"
    )


def test_ac1_footer_no_border_top():
    """
    AC-1 (Teil 3): .footer-CSS hat kein border-top.

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN die .footer-CSS-Deklaration analysiert wird
    THEN enthält diese kein border-top
    """
    html = _render_minimal_html()
    if ".footer" in html:
        footer_css_start = html.find(".footer")
        footer_css_end = html.find("}", footer_css_start)
        if footer_css_end > footer_css_start:
            footer_css = html[footer_css_start:footer_css_end]
            assert "border-top" not in footer_css, (
                "footer-CSS enthält noch border-top — soll bei Dunkel-Footer entfernt werden"
            )


# ---------------------------------------------------------------------------
# AC-2: Dark-Mode-Meta-Tag
# ---------------------------------------------------------------------------

def test_ac2_color_scheme_meta_present():
    """
    AC-2: <head> enthält <meta name="color-scheme" content="light">.

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN der <head>-Block auf Meta-Tags geprüft wird
    THEN ist <meta name="color-scheme" content="light"> vorhanden
    """
    html = _render_minimal_html()
    assert 'name="color-scheme"' in html, (
        "<meta name='color-scheme'> fehlt im <head>"
    )
    assert 'content="light"' in html or "content='light'" in html, (
        "color-scheme-Meta hat nicht content='light'"
    )


# ---------------------------------------------------------------------------
# AC-3 + AC-4: pill_html() — Tag-/Pill-System
# ---------------------------------------------------------------------------

def test_ac3_pill_html_good_tone():
    """
    AC-3: pill_html('OK', 'good') → #3a7d44 als BG, #ffffff als Textfarbe, <span>.

    GIVEN pill_html('OK', 'good') aufgerufen
    WHEN das Ergebnis geprüft wird
    THEN enthält der String #3a7d44 als background, #ffffff als color,
         beginnt mit <span und enthält kein var(--)
    """
    from src.output.renderers.email.helpers import pill_html
    result = pill_html("OK", "good")
    assert result.startswith("<span"), f"pill_html gibt kein <span> zurück: {result[:50]}"
    assert "#3a7d44" in result, f"Kein #3a7d44 (G_SUCCESS) in pill_html('OK', 'good'): {result}"
    assert "#ffffff" in result.lower(), f"Kein #ffffff (weiß) in pill_html result: {result}"
    assert "var(--" not in result, "pill_html enthält CSS-Custom-Properties — Outlook-inkompatibel"


def test_ac3_pill_html_is_inline_span():
    """
    AC-3 (Struktur): pill_html-Ergebnis hat border-radius und padding.

    GIVEN pill_html mit beliebigen Werten
    WHEN das Ergebnis geprüft wird
    THEN enthält es border-radius und padding (Pill-Styling)
    """
    from src.output.renderers.email.helpers import pill_html
    result = pill_html("Test", "info")
    assert "border-radius" in result, "Pill hat kein border-radius"
    assert "padding" in result, "Pill hat kein padding"


@pytest.mark.parametrize("tone,expected_bg", [
    ("warn", "#c8882a"),
    ("bad",  "#b33a2a"),
    ("info", "#2a6cb3"),
])
def test_ac4_pill_html_tones(tone, expected_bg):
    """
    AC-4: pill_html mit warn/bad/info liefert korrekte Hex-Hintergrundfarben.

    GIVEN pill_html(label, tone) mit tone='warn'/'bad'/'info'
    WHEN das Ergebnis geprüft wird
    THEN enthält der String den korrekten Hex-Wert als background
    """
    from src.output.renderers.email.helpers import pill_html
    result = pill_html("Label", tone)
    assert expected_bg in result, (
        f"Tone '{tone}': erwartet BG {expected_bg}, nicht in Ergebnis: {result}"
    )


def test_ac4_pill_html_neutral_fallback():
    """
    AC-4 (Fallback): Unbekannter Tone → neutral (heller BG, dunkler Text).

    GIVEN pill_html('X', 'unknown_tone')
    WHEN das Ergebnis geprüft wird
    THEN enthält es #edeae1 als BG und #1a1a18 als Text
    """
    from src.output.renderers.email.helpers import pill_html
    result = pill_html("X", "unknown")
    assert "#edeae1" in result, f"Neutral-Fallback hat nicht #edeae1: {result}"
    assert "#1a1a18" in result, f"Neutral-Fallback hat nicht #1a1a18 (dunkler Text): {result}"


# ---------------------------------------------------------------------------
# AC-5: @media Mobile-Block im <style>
# ---------------------------------------------------------------------------

def test_ac5_mobile_media_query_present():
    """
    AC-5 (Teil 1): <style>-Block enthält @media (max-width: 480px).

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN der <style>-Block auf @media-Regeln geprüft wird
    THEN ist @media (max-width: 480px) vorhanden
    """
    html = _render_minimal_html()
    assert "@media" in html, "@media fehlt komplett im HTML"
    assert "480px" in html, "@media (max-width: 480px) fehlt"


def test_ac5_mobile_table_resp_rule():
    """
    AC-5 (Teil 2): @media-Block enthält table.resp und td::before Regeln.

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN der @media-Block analysiert wird
    THEN enthält dieser table.resp und td::before Selektoren
    """
    html = _render_minimal_html()
    assert "table.resp" in html, "Kein table.resp-Selektor im @media-Block"
    assert "td::before" in html or "td:before" in html, (
        "Kein td::before/td:before im @media-Block (fehlendes data-label Karten-Layout)"
    )


# ---------------------------------------------------------------------------
# AC-6: _render_html_table() — class="resp" + data-label auf <td>
# ---------------------------------------------------------------------------

def test_ac6_table_has_resp_class():
    """
    AC-6 (Teil 1): _render_html_table() gibt <table class="resp"> zurück.

    GIVEN _render_html_table() mit mindestens einer Datenzeile aufgerufen
    WHEN das Ergebnis geprüft wird
    THEN enthält das <table>-Element class="resp"
    """
    from src.output.renderers.email.html import _render_html_table
    rows = [{"time": "08:00", "temp": "15°C", "wind": "12 km/h"}]
    result = _render_html_table(rows, friendly_keys=set())
    assert 'class="resp"' in result or "class='resp'" in result, (
        f"<table> hat kein class='resp': {result[:200]}"
    )


def test_ac6_table_td_has_data_label():
    """
    AC-6 (Teil 2): Jede <td> hat ein data-label-Attribut mit Spalten-Header-Text.

    GIVEN _render_html_table() mit mindestens einer Datenzeile aufgerufen
    WHEN das Ergebnis geprüft wird
    THEN enthält jede <td> ein data-label="..." Attribut
    """
    from src.output.renderers.email.html import _render_html_table
    rows = [{"time": "08:00", "temp": "15°C"}]
    result = _render_html_table(rows, friendly_keys=set())
    assert "data-label=" in result, (
        f"Keine data-label-Attribute auf <td>-Elementen: {result[:300]}"
    )


# ---------------------------------------------------------------------------
# AC-7: Kein hartkodiertes #eee im gerenderten HTML
# ---------------------------------------------------------------------------

def test_ac7_no_hardcoded_eee():
    """
    AC-7: Gerendertes HTML enthält kein hartkodiertes #eee.

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN der HTML-String nach '#eee' (case-insensitive) durchsucht wird
    THEN gibt es keinen Treffer
    """
    import re
    html = _render_minimal_html()
    matches = re.findall(r"#[Ee]{3}\b", html)
    assert not matches, (
        f"Hartkodiertes #eee noch im HTML ({len(matches)}x) — "
        "durch G_INK_FAINT (#9c9a90) ersetzen"
    )


def test_ac7_no_eee_in_source():
    """
    AC-7 (Quelltext): html.py-Quelltext enthält kein hartkodiertes #eee mehr.

    GIVEN der Quelltext von src/output/renderers/email/html.py
    WHEN nach '#eee' gesucht wird
    THEN gibt es keinen Treffer
    """
    import re
    source = HTML_PY.read_text()
    matches = re.findall(r"#[Ee]{3}\b", source)
    assert not matches, (
        f"#eee noch {len(matches)}x in html.py — "
        "durch G_INK_FAINT (#9c9a90) ersetzen"
    )


# ---------------------------------------------------------------------------
# AC-8: preview_email.py --profile Argument
# ---------------------------------------------------------------------------

def test_ac8_preview_script_profile_argument():
    """
    AC-8: scripts/preview_email.py akzeptiert --profile wintersport.

    GIVEN scripts/preview_email.py mit --profile wintersport ausgeführt
    WHEN die erzeugte HTML-Datei auf den Eyebrow-Block geprüft wird
    THEN enthält die Ausgabe 'WINTERSPORT · PISTE' und der Prozess endet mit Exit 0
    """
    import tempfile
    script = REPO_ROOT / "scripts" / "preview_email.py"
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        out_path = f.name

    result = subprocess.run(
        [sys.executable, str(script), "--profile", "wintersport", "--out", out_path],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"preview_email.py --profile wintersport schlägt fehl "
        f"(exit {result.returncode}):\n{result.stderr}"
    )
    html_out = Path(out_path).read_text()
    assert "WINTERSPORT · PISTE" in html_out, (
        "Eyebrow 'WINTERSPORT · PISTE' fehlt in preview_email.py-Ausgabe"
    )
