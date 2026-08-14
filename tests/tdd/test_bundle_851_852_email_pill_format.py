"""
TDD RED tests für Bundle #851/#852 — E-Mail Pill + Antwort-Block Format-Fidelity.

SPEC: docs/specs/modules/bundle_851_852_email_pill_format.md

RED-Zustand (jetzt):
  - pill_html() produziert border-radius:99px (statt 2px) und kein border:1px solid
  - neutral-Tone nutzt #edeae1/#1a1a18 (statt info-Palette #dde8f3/...)
  - Antwort-Kommandos-Block nutzt #dfe7f0-Hintergrund + border-left (statt dunklem Footer-Stil)

AC-4 (Regression) ist bewusst GREEN — beweist dass Ampel-Funktionen unberührt bleiben.
"""
from __future__ import annotations




# ─── Helpers ────────────────────────────────────────────────────────────────

def _render_email_html() -> str:
    """Rendert minimal-valides Briefing-HTML via render_email() → (html, plain)."""
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    from src.output.renderers.email import render_email

    token_line = _make_token_line()
    html, _ = render_email(token_line, **_common_kwargs())
    return html


# ─── AC-1: pill_html() Ampel-Tone enthält Border + eckigen Radius ───────────

class TestAC1PillHtmlAmpelToneBorder:
    """AC-1: pill_html() mit Ampel-Tone muss border:1px solid + border-radius:2px liefern."""

    def test_pill_html_ampel_orange_has_warn_border_color(self):
        """
        GIVEN: tone='ampel_orange'
        WHEN: pill_html() aufgerufen
        THEN: Rückgabe enthält 'border:1px solid #e59248' (warn-Palette,
              Fix #1801 S2 -- alter Wert #f0a060 wich der neuen, staerker
              abgesetzten Palette; ampel_orange hat seit dem vierten Ton
              "caution" weiterhin einen eigenen warn-Rahmen).
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("Regen ab 11:00", "ampel_orange")
        assert "border:1px solid #e59248" in result, (
            f"Erwartet 'border:1px solid #e59248' (warn-Palette), nicht gefunden.\n"
            f"IST: {result}"
        )

    def test_pill_html_has_square_border_radius_not_round(self):
        """
        GIVEN: tone='ampel_orange'
        WHEN: pill_html() aufgerufen
        THEN: Rückgabe enthält 'border-radius:2px' und NICHT 'border-radius:99px'
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("Böen 25 km/h", "ampel_orange")
        assert "border-radius:2px" in result, (
            f"Erwartet 'border-radius:2px' (eckig), nicht gefunden.\nIST: {result}"
        )
        assert "border-radius:99px" not in result, (
            f"'border-radius:99px' (Kapsel-Stil) darf nicht mehr vorkommen.\nIST: {result}"
        )

    def test_pill_html_ampel_green_ok_palette(self):
        """
        GIVEN: tone='ampel_green'
        WHEN: pill_html() aufgerufen
        THEN: Rückgabe enthält ok-Palette: bg=#dcf2e1 + border=#86c89a
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("Kein Gewitter", "ampel_green")
        assert "background:#dcf2e1" in result, (
            f"Erwartet bg=#dcf2e1 (ok-Palette), nicht gefunden.\nIST: {result}"
        )
        assert "border:1px solid #86c89a" in result, (
            f"Erwartet border=#86c89a (ok-Palette), nicht gefunden.\nIST: {result}"
        )

    def test_pill_html_ampel_red_risk_palette(self):
        """
        GIVEN: tone='ampel_red'
        WHEN: pill_html() aufgerufen
        THEN: Rückgabe enthält risk-Palette: bg=#fad3e1 + border=#dd7ba2
              (Fix #1801 S2 -- alte Werte #fadcd6/#e88472 wichen der neuen,
              staerker abgesetzten Palette, Karminrot-Angleich)
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("Gewitter", "ampel_red")
        assert "background:#fad3e1" in result, (
            f"Erwartet bg=#fad3e1 (risk-Palette), nicht gefunden.\nIST: {result}"
        )
        assert "border:1px solid #dd7ba2" in result, (
            f"Erwartet border=#dd7ba2 (risk-Palette), nicht gefunden.\nIST: {result}"
        )

    def test_pill_html_ampel_yellow_caution_palette(self):
        """
        GIVEN: tone='ampel_yellow'
        WHEN: pill_html() aufgerufen
        THEN: Rückgabe enthält den NEUEN eigenstaendigen caution-Ton
              (bg=#fdf2c4 + border=#e0b93c) -- Fix #1801 S2 AC-8: 'ampel_yellow'
              mappt nicht mehr auf 'warn' (das teilt sich 'ampel_orange' jetzt
              exklusiv), sondern auf den vierten Ton 'caution'.
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("Wind mäßig", "ampel_yellow")
        assert "background:#fdf2c4" in result, (
            f"Erwartet bg=#fdf2c4 (caution-Palette), nicht gefunden.\nIST: {result}"
        )
        assert "border:1px solid #e0b93c" in result, (
            f"Erwartet border=#e0b93c (caution-Palette), nicht gefunden.\nIST: {result}"
        )


# ─── AC-2: pill_html() neutral/unbekannte Tones → info-Palette ───────────────

class TestAC2PillHtmlNeutralInfoPalette:
    """AC-2: neutral-Tone muss info-Palette liefern, nicht alte #edeae1-Farben."""

    def test_pill_html_neutral_tone_uses_info_bg(self):
        """
        GIVEN: tone='neutral'
        WHEN: pill_html() aufgerufen
        THEN: Rückgabe enthält bg=#dde8f3 (info-Palette), NICHT altes #edeae1
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("UV mäßig (3.5)", "neutral")
        assert "background:#dde8f3" in result, (
            f"Erwartet bg=#dde8f3 (info-Palette), nicht gefunden.\nIST: {result}"
        )
        assert "#edeae1" not in result, (
            f"Alte Neutral-Farbe #edeae1 darf nicht mehr vorkommen.\nIST: {result}"
        )

    def test_pill_html_neutral_tone_has_info_border(self):
        """
        GIVEN: tone='neutral'
        WHEN: pill_html() aufgerufen
        THEN: Rückgabe enthält border:1px solid #8aacd0 (info-Palette)
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("0°-Linie 2.530 m", "neutral")
        assert "border:1px solid #8aacd0" in result, (
            f"Erwartet border=#8aacd0 (info-Palette), nicht gefunden.\nIST: {result}"
        )

    def test_pill_html_unknown_tone_falls_back_to_info(self):
        """
        GIVEN: tone='unbekannt_xyz' (kein Ampel-Tone, kein 'neutral')
        WHEN: pill_html() aufgerufen
        THEN: Fallback auf info-Palette (bg=#dde8f3), kein Fehler
        """
        from src.output.renderers.email.helpers import pill_html
        result = pill_html("Label", "unbekannt_xyz")
        assert "background:#dde8f3" in result, (
            f"Unbekannter Tone soll info-Fallback nutzen (bg=#dde8f3).\nIST: {result}"
        )


# ─── AC-3: Antwort-Kommandos-Block im render_email() HTML-Output ─────────────

class TestAC3AntwortKommandosBlockStyle:
    """AC-3: Antwort-Kommandos-Block hat hellen Stil (#fbfaf6) laut #884-Design."""

    def test_antwort_block_has_dark_background(self):
        """
        GIVEN: render_email() mit Minimal-Daten
        WHEN: HTML gerendert
        THEN: Antwort-Kommandos-Block enthält background:#fbfaf6 (G_HEADER_BG, #884 design)

        Note: #884 changed the Antwort-Kommandos-Block from dark (#1d1c1a) to light
        (#fbfaf6, G_HEADER_BG). The dark background (#1d1c1a) moved to the footer.
        """
        html = _render_email_html()
        idx = html.find("Antwort-Kommandos")
        assert idx != -1, "Antwort-Kommandos nicht im HTML gefunden"
        block_context = html[max(0, idx - 300):idx + 300]
        assert "background:#fbfaf6" in block_context, (
            f"Erwartet background:#fbfaf6 im Antwort-Block (#884 design, G_HEADER_BG), nicht gefunden.\n"
            f"Kontext: {block_context}"
        )

    def test_antwort_block_has_no_info_box_background(self):
        """
        GIVEN: render_email() mit Minimal-Daten
        WHEN: HTML gerendert
        THEN: G_BOX_INFO_BG (#dfe7f0) kommt im Antwort-Kommandos-Block NICHT vor
        """
        html = _render_email_html()
        idx = html.find("Antwort-Kommandos")
        assert idx != -1, "Antwort-Kommandos nicht im HTML gefunden"
        block_context = html[max(0, idx - 300):idx + 300]
        assert "#dfe7f0" not in block_context, (
            f"G_BOX_INFO_BG (#dfe7f0) darf im Antwort-Block nicht vorkommen.\n"
            f"Kontext: {block_context}"
        )

    def test_antwort_block_has_no_border_left(self):
        """
        GIVEN: render_email() mit Minimal-Daten
        WHEN: HTML gerendert
        THEN: 'border-left:4px solid' kommt im Antwort-Block NICHT vor
        """
        html = _render_email_html()
        idx = html.find("Antwort-Kommandos")
        assert idx != -1, "Antwort-Kommandos nicht im HTML gefunden"
        block_context = html[max(0, idx - 300):idx + 600]
        assert "border-left:4px solid" not in block_context, (
            f"'border-left:4px solid' darf im Antwort-Block nicht vorkommen.\n"
            f"Kontext: {block_context}"
        )


# ─── AC-4: Regression — tone_symbol() + ampel_stage_tone() unverändert ──────

class TestAC4RegressionAmpelFunctions:
    """
    AC-4: _AMPEL_STAGE_COLORS und Hilfsfunktionen bleiben nach dem Rewrite unverändert.
    Diese Tests sind bewusst GREEN (Regression-Schutz, kein Implementierungs-Bedarf).

    Issue #1222: tone_symbol() liefert seither IMMER "" — Kreis-Emojis wurden
    aus dem Plain-Text ersatzlos entfernt (AC-4 der #1222-Spec).
    """

    def test_tone_symbol_green(self):
        from src.output.renderers.email.helpers import tone_symbol
        assert tone_symbol("ampel_green") == ""

    def test_tone_symbol_yellow(self):
        from src.output.renderers.email.helpers import tone_symbol
        assert tone_symbol("ampel_yellow") == ""

    def test_tone_symbol_orange(self):
        from src.output.renderers.email.helpers import tone_symbol
        assert tone_symbol("ampel_orange") == ""

    def test_tone_symbol_red(self):
        from src.output.renderers.email.helpers import tone_symbol
        assert tone_symbol("ampel_red") == ""
