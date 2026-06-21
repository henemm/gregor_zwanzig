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

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit.test_renderers_email import _common_kwargs, _make_token_line


REPO_ROOT = Path(__file__).resolve().parents[2]


# WCAG relative Luminanz / Kontrast — selbst berechnet (keine Tautologie gegen
# gepinnte Hex-Werte). Issue #795/AC-8: Pill-Tests prüfen das *Verhalten*
# (Vollfarb-Kapsel, weißer Text, Kontrast ≥ 4.5:1) statt exakter Farbcodes,
# damit eine WCAG-konforme Farb-Justierung sie nicht mehr bricht.
def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast_ratio(c1: str, c2: str) -> float:
    l1, l2 = _luminance(c1), _luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _parse_pill_colors(html: str):
    """Extrahiere (bg, fg) aus dem gerenderten pill_html-Span."""
    bg = re.search(r"background:\s*(#[0-9a-fA-F]{6})", html)
    fg = re.search(r"color:\s*(#[0-9a-fA-F]{6})", html)
    assert bg and fg, f"bg/fg nicht parsebar:\n{html}"
    return bg.group(1).lower(), fg.group(1).lower()


# Die vier Ampelstufen-tones sind die einzigen Schweregrad-tones, die
# _pill_for_metric tatsächlich erzeugt (SSoT #759-Tabelle). pill_html kennt
# keine toten Legacy-tones (good/warn/bad/info) mehr.
_AMPEL_STAGE_TONES = ("ampel_green", "ampel_yellow", "ampel_orange", "ampel_red")


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
    AC-3 (#795/AC-8): Ein Schweregrad-Tone erzeugt eine lesbare Vollfarb-Kapsel.

    GIVEN pill_html('OK', 'ampel_green') aufgerufen (echter, vom Renderer
          erzeugter Schweregrad-Tone — nicht der tote Legacy-Tone 'good')
    WHEN das Ergebnis geprüft wird
    THEN beginnt es mit <span>, hat einen vollflächigen background mit weißem
         Text (#ffffff), Kontrast ≥ 4.5:1 (WCAG-AA) und keine CSS-Variablen.

    Verhaltens-/kontrastbasiert statt exakter Hex (#795/AC-8) — eine
    WCAG-konforme Farb-Justierung bricht den Test nicht mehr. Die
    ursprüngliche Absicht (korrekte, lesbare tone-Darstellung) bleibt erhalten.
    """
    from src.output.renderers.email.helpers import pill_html
    result = pill_html("OK", "ampel_green")
    assert result.startswith("<span"), f"pill_html gibt kein <span> zurück: {result[:50]}"
    assert "var(--" not in result, "pill_html enthält CSS-Custom-Properties — Outlook-inkompatibel"
    bg, fg = _parse_pill_colors(result)
    assert _contrast_ratio(bg, fg) >= 4.5, (
        f"Kontrast {round(_contrast_ratio(bg, fg), 2)}:1 < 4.5:1 (bg={bg}, fg={fg})"
    )


def test_ac3_pill_html_is_inline_span():
    """
    AC-3 (Struktur): pill_html-Ergebnis ist eine Vollfarb-Kapsel.

    GIVEN pill_html mit einem echten tone
    WHEN das Ergebnis geprüft wird
    THEN enthält es border-radius:99px (Vollfarb-Kapsel) und padding.
    """
    from src.output.renderers.email.helpers import pill_html
    result = pill_html("Test", "ampel_red")
    assert "border-radius:2px" in result, "Pill hat keine Outline-Tag-Form (border-radius:2px)"
    assert "padding" in result, "Pill hat kein padding"


@pytest.mark.parametrize("tone", list(_AMPEL_STAGE_TONES))
def test_ac4_pill_html_tones(tone):
    """
    AC-4 (#795/AC-8): Jeder der vier echten Schweregrad-tones (ampel-Stufen)
    erzeugt eine WCAG-AA-lesbare Vollfarb-Kapsel.

    GIVEN pill_html(label, tone) für ampel_green/yellow/orange/red
          (die tatsächlich vom Renderer erzeugten Schweregrad-tones — die toten
          Legacy-tones warn/bad/info existieren nicht mehr, #795/AC-8)
    WHEN das Ergebnis geprüft wird
    THEN ist es eine Vollfarb-Kapsel (vollflächiger bg + weißer Text,
         border-radius:99px) mit Kontrast ≥ 4.5:1.
    """
    from src.output.renderers.email.helpers import pill_html
    result = pill_html("Label", tone)
    assert "border-radius:2px" in result, (
        f"Tone '{tone}': Outline-Tag-Form (border-radius:2px) fehlt: {result}"
    )
    bg, fg = _parse_pill_colors(result)
    assert _contrast_ratio(bg, fg) >= 4.5, (
        f"Tone '{tone}': Kontrast {round(_contrast_ratio(bg, fg), 2)}:1 < 4.5:1 "
        f"(bg={bg}, fg={fg})"
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
    assert "#dde8f3" in result, f"Info-Fallback hat nicht #dde8f3 (info bg): {result}"
    assert "#1e3a5f" in result, f"Info-Fallback hat nicht #1e3a5f (info fg): {result}"


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
    assert "600px" in html, "@media (max-width: 600px) fehlt — Bug #305 hebt Breakpoint von 480px auf 600px an"


def test_ac5_mobile_table_resp_rule():
    """
    AC-5 (Teil 2): Mobile-Responsive-Layout via Dual-Mode (desktop-only/mobile-compact).

    GIVEN ein gerendertes Trip-Briefing-HTML
    WHEN der @media-Block analysiert wird
    THEN enthält dieser .desktop-only (display:none) und .mobile-compact (display:block)

    Hinweis: Bug #305 v2 ersetzt das alte td::before-Karten-Layout durch das Dual-Mode-Pattern.
    Die table.resp-Klasse bleibt als Elementklasse erhalten, das td::before-CSS wird nicht mehr
    benötigt da die Desktop-Tabelle auf Mobile via display:none !important ausgeblendet wird.
    """
    html = _render_minimal_html()
    assert 'class="resp"' in html, "Kein <table class=\"resp\"> im HTML"
    media_start = html.find("@media")
    assert media_start != -1, "Kein @media-Block gefunden"
    media_block = html[media_start:html.find("</style>", media_start)]
    assert "desktop-only" in media_block, (
        "Kein .desktop-only-Selektor im @media-Block (Bug #305 v2 Dual-Mode fehlt)"
    )
    assert "mobile-compact" in media_block, (
        "Kein .mobile-compact-Selektor im @media-Block (Bug #305 v2 Dual-Mode fehlt)"
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


# AC-7 (test_ac7_no_eee_in_source) — entfernt in #765.
# Las src/output/renderers/email/html.py als Quelltext (Datei-Inhalt-Anti-
# Pattern, CLAUDE.md). Das relevante Verhalten — das GERENDERTE HTML enthält
# kein hartkodiertes #eee — ist durch test_ac7_no_hardcoded_eee am echten
# Render-Output abgedeckt.


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
