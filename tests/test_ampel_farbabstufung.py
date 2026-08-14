"""TDD RED — Bug #1801: Farbabstand + Konsolidierung der Ampel-Palette.

Scheibe S1 (Konsolidierung, AC-1/AC-2): `html.py` und `outlook.py` fuehren
heute eigene Kopien der (bg, fg)-Ampelfarben statt `design_tokens.tone_css()`
zu rufen. Ein reines Struktur-Refactoring hat keinen roten Test -- der Beweis
setzt deshalb an der WIRKUNG an (kein Dateiinhalt-Check, CLAUDE.md-Verbot):
`design_tokens._TONE_CSS` wird zur Laufzeit auf einen Erkennungswert
gepatcht; erst wenn `html.py`/`outlook.py` tatsaechlich `tone_css()` rufen,
erscheint der Erkennungswert in der gerenderten Ausgabe. Heute (zwei
unabhaengige Kopien) tut er das nicht -- RED.

Scheibe S2 (AC-3/AC-4): neue Ampel-Palette mit groesserem Farbabstand
orange<->rot (ΔE76 im Lab-Farbraum) + WCAG-AA-Fix des gruenen Zelltexts.
ΔE76 und der WCAG-Kontrast werden hier selbst berechnet (keine externe
Bibliothek, CLAUDE.md-Testpolitik).

SPEC: docs/specs/modules/fix_1801_warnstufen_abstufung.md AC-1..AC-4
Mock-frei: `monkeypatch` (pytest-Bordmittel) ist keine Mock-Bibliothek im
Sinne des Projektverbots (kein `Mock()`/`patch()`/`MagicMock`) -- es ist die
Sonde, die die Kopplung an die zentrale Quelle misst, keine Ersatzlogik.
"""
from __future__ import annotations

import math
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")


# ---------------------------------------------------------------------------
# Farb-Mathematik (lokal, keine externe Bibliothek — CLAUDE.md-Testpolitik)
# ---------------------------------------------------------------------------

def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb_to_xyz(r: int, g: int, b: int) -> tuple[float, float, float]:
    R, G, B = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    X = R * 0.4124564 + G * 0.3575761 + B * 0.1804375
    Y = R * 0.2126729 + G * 0.7151522 + B * 0.0721750
    Z = R * 0.0193339 + G * 0.1191920 + B * 0.9503041
    return X * 100, Y * 100, Z * 100


def _lab_f(t: float) -> float:
    return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)


def _hex_to_lab(h: str) -> tuple[float, float, float]:
    X, Y, Z = _rgb_to_xyz(*_hex_to_rgb(h))
    Xn, Yn, Zn = 95.0489, 100.0, 108.8840
    fx, fy, fz = _lab_f(X / Xn), _lab_f(Y / Yn), _lab_f(Z / Zn)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b = 200 * (fy - fz)
    return L, a, b


def _delta_e76(h1: str, h2: str) -> float:
    """CIE76-Farbabstand zweier Hex-Farben (hoeher = besser unterscheidbar)."""
    L1, a1, b1 = _hex_to_lab(h1)
    L2, a2, b2 = _hex_to_lab(h2)
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


def _relative_luminance(h: str) -> float:
    r, g, b = _hex_to_rgb(h)
    R, G, B = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    return 0.2126 * R + 0.7152 * G + 0.0722 * B


def _wcag_contrast(h1: str, h2: str) -> float:
    """WCAG-2.0-Kontrastverhaeltnis (relative Luminanz), >= 4.5 = AA fuer Fliesstext."""
    l1, l2 = _relative_luminance(h1), _relative_luminance(h2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ===========================================================================
# S1 — Wirkungstest: tone_css() muss die gerenderte HTML-Ausgabe steuern
# ===========================================================================

class TestS1ToneCssIsSingleSourceOfTruth:

    def test_html_table_orange_cell_bg_follows_tone_css(self, monkeypatch):
        """GIVEN `html.py` faerbt orange Ampel-Zellen heute aus einer eigenen
        lokalen Kopie statt `design_tokens.tone_css()` / WHEN die zentrale
        Quelle zur Laufzeit auf einen Erkennungswert gepatcht wird / THEN
        traegt die gerenderte Stundentabelle genau diesen Erkennungswert.

        Heute (zwei unabhaengige Kopien) hat der Patch keine Wirkung -- RED.
        """
        from output.renderers.email import design_tokens
        from output.renderers.email.html import _render_html_table

        sentinel_bg = "#123456"
        monkeypatch.setitem(design_tokens._TONE_CSS, "orange", (sentinel_bg, "#000000"))

        # Wind 55 km/h liegt zwischen den Katalog-Schwellen orange (50) und
        # rot (70) -> orange Zell-Toenung (severity_for("wind", 55) == "orange").
        rows = [{"time": "08", "wind": 55.0}]
        html_out = _render_html_table(rows, friendly_keys=set(), indicator_keys={"wind"})

        assert sentinel_bg in html_out, (
            "html.py._render_html_table faerbt die orange Ampel-Zelle nicht "
            "ueber design_tokens.tone_css() -- S1-Konsolidierung fehlt "
            "(zwei unabhaengige Farbkopien)."
        )

    def test_outlook_table_wind_cell_bg_follows_tone_css(self, monkeypatch):
        """GIVEN `outlook.py._outlook_cell_bg` faerbt Schwellen-Zellen (Wind,
        Boeen, Regen, Regenwahrsch.) heute aus einer eigenen lokalen Kopie /
        WHEN `design_tokens._TONE_CSS["orange"]` gepatcht wird / THEN
        traegt die gerenderte Ausblick-Zeile den Erkennungswert."""
        from output.renderers.email import design_tokens
        from output.renderers.email.outlook import render_outlook_table

        sentinel_bg = "#234567"
        monkeypatch.setitem(design_tokens._TONE_CSS, "orange", (sentinel_bg, "#000000"))

        rows = [{"weekday": "Mo", "wind_kmh": 55.0}]
        table_html = render_outlook_table(rows)

        assert sentinel_bg in table_html, (
            "outlook.py.render_outlook_table faerbt die orange Wind-Zelle "
            "nicht ueber design_tokens.tone_css() -- S1-Konsolidierung fehlt "
            "(_outlook_cell_bg hat eine eigene lokale Kopie)."
        )

    def test_outlook_table_thunder_cell_bg_follows_tone_css(self, monkeypatch):
        """GIVEN `outlook.py._THUNDER_LEVEL_BG` faerbt die Gewitter-Spalte
        heute aus einer ZWEITEN eigenen lokalen Kopie / WHEN
        `design_tokens._TONE_CSS["orange"]` gepatcht wird / THEN traegt die
        gerenderte Gewitter-Zelle (Stufe MED) den Erkennungswert."""
        from output.renderers.email import design_tokens
        from output.renderers.email.outlook import render_outlook_table

        sentinel_bg = "#345678"
        monkeypatch.setitem(design_tokens._TONE_CSS, "orange", (sentinel_bg, "#000000"))

        rows = [{"weekday": "Mo", "thunder": "MED"}]
        table_html = render_outlook_table(rows)

        assert sentinel_bg in table_html, (
            "outlook.py.render_outlook_table faerbt die Gewitter-Zelle bei "
            "Stufe MED nicht ueber design_tokens.tone_css() -- S1-"
            "Konsolidierung fehlt (_THUNDER_LEVEL_BG hat eine eigene "
            "lokale Kopie)."
        )


# ===========================================================================
# AC-3 — Punktabstand orange<->rot mindestens ΔE76 50 (heute rund 16,4)
# ===========================================================================

class TestAC3OrangeRedDistance:

    def test_ampel_dot_colors_match_target_palette(self):
        """GIVEN die neue Punktfarben-Zielwerte-Tabelle der Spec / WHEN
        `_AMPEL_DOT_COLORS` gelesen wird / THEN stimmen orange und rot exakt
        mit den Zielwerten `#d4530a`/`#a8104a` ueberein (heute `#c2410c`/
        `#b91c1c`)."""
        from output.renderers.email.helpers import _AMPEL_DOT_COLORS

        assert _AMPEL_DOT_COLORS["orange"][0] == "#d4530a", (
            f"Ampel-Punktfarbe orange war {_AMPEL_DOT_COLORS['orange'][0]!r}, "
            f"erwartet '#d4530a' (Spec-Zielwert)"
        )
        assert _AMPEL_DOT_COLORS["red"][0] == "#a8104a", (
            f"Ampel-Punktfarbe rot war {_AMPEL_DOT_COLORS['red'][0]!r}, "
            f"erwartet '#a8104a' (Spec-Zielwert)"
        )

    def test_ampel_dot_orange_red_delta_e76_at_least_50(self):
        """GIVEN der heutige Punktabstand orange<->rot betraegt nur ΔE76 ~16,4
        (kleinster Sprung der gesamten Skala) / WHEN die neue Palette
        eingesetzt wird / THEN betraegt der ΔE76-Abstand mindestens 50."""
        from output.renderers.email.helpers import _AMPEL_DOT_COLORS

        orange_hex = _AMPEL_DOT_COLORS["orange"][0]
        red_hex = _AMPEL_DOT_COLORS["red"][0]
        distance = _delta_e76(orange_hex, red_hex)

        assert distance >= 50, (
            f"ΔE76(orange={orange_hex!r}, rot={red_hex!r}) = {distance:.1f}, "
            f"erwartet >= 50 (heute rund 16,4 -- Beschwerde #1801)"
        )

    def test_tone_css_area_colors_match_target_palette(self):
        """GIVEN dieselbe Zielwerte-Tabelle fuer Flaechenfarben / WHEN
        `design_tokens._TONE_CSS` gelesen wird / THEN stimmen orange und rot
        exakt mit den Zielwerten `#fbe3cc`/`#f7d3e2` ueberein (heute
        `#fad6b8`/`#f6c5bf`)."""
        from output.renderers.email.design_tokens import tone_css

        orange_bg, _ = tone_css("orange")
        red_bg, _ = tone_css("red")

        assert orange_bg == "#fbe3cc", (
            f"Ampel-Flaechenfarbe orange war {orange_bg!r}, erwartet '#fbe3cc'"
        )
        assert red_bg == "#f7d3e2", (
            f"Ampel-Flaechenfarbe rot war {red_bg!r}, erwartet '#f7d3e2'"
        )


# ===========================================================================
# AC-4 — Gruener Zelltext erreicht WCAG-AA (>=4,5:1), G_SUCCESS bleibt gleich
# ===========================================================================

class TestAC4GreenTextWcagContrast:

    def test_green_cell_text_reaches_wcag_aa(self):
        """GIVEN der gruene Zelltext unterschreitet heute WCAG-AA (4,01:1
        auf `#dbeadd`, Grenze 4,5:1) / WHEN der Text auf die neue Konstante
        `G_AMPEL_TEXT_GREEN` (`#2f6b39`) umgestellt wird / THEN betraegt der
        Kontrast mindestens 4,5:1 UND `G_SUCCESS` bleibt fuer die amtliche
        Warnpalette/den Korridor-Marker unveraendert `#3a7d44` (AC-10-
        Voraussetzung, im selben Test statt separatem Test, weil diese
        zweite Assertion allein NICHT rot waere -- sie prueft nur, dass ein
        Bestandswert unangetastet bleibt)."""
        from output.renderers.email.design_tokens import G_SUCCESS, tone_css

        green_bg, green_fg = tone_css("green")
        contrast = _wcag_contrast(green_fg, green_bg)

        assert green_fg == "#2f6b39", (
            f"Gruener Ampel-Zelltext war {green_fg!r}, erwartet neue "
            f"Konstante G_AMPEL_TEXT_GREEN '#2f6b39'"
        )
        assert contrast >= 4.5, (
            f"Kontrast gruener Zelltext/Hintergrund = {contrast:.2f}:1, "
            f"erwartet >= 4.5:1 (WCAG-AA, ADR-0008)"
        )
        assert G_SUCCESS == "#3a7d44"
