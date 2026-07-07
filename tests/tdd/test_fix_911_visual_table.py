"""
VISUELLE TDD-Tests für #911 — Desktop-Stundentabelle gegen Design-Vorlage.

SOLL: docs/design-requests/issue_911_mail_vorschau/screen-output-preview.jsx
(EmailDataTable + sevCellStyle).

WARUM VISUELL: Die vorherige Runde war mit String-Presence-Tests grün, während
ALLE Bugs live bestanden blieben. Diese Tests rendern die echte Mail, laden sie
in einem headless-Browser bei DESKTOP-Breite (≥601px) und lesen die BERECHNETEN
Stile echter Zellen aus — das ist der tatsächliche Anzeige-Zustand, kein String.

KEINE Mocks. KEINE Dateiinhalt-Checks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402


# ---------------------------------------------------------------------------
# Design-SOLL-Werte (aus screen-output-preview.jsx)
# ---------------------------------------------------------------------------
LINE_COLOR_RGB = "rgb(240, 236, 225)"     # #f0ece1 — alle Zell-Linien
RISK_CELL = {
    "caution": "rgb(251, 238, 184)",       # #fbeeb8
    "warn":    "rgb(250, 214, 184)",       # #fad6b8
    "danger":  "rgb(246, 197, 191)",       # #f6c5bf
}
WHITE_OR_TRANSPARENT = {"rgba(0, 0, 0, 0)", "rgb(255, 255, 255)", "transparent"}


# ---------------------------------------------------------------------------
# Echte Render-Pipeline (Produktionspfad render_html), reiner Zahlen-Modus
# ---------------------------------------------------------------------------
def _numeric_dc():
    """Display-Config im reinen Zahlen-Modus mit ALLEN Metriken aktiviert —
    spiegelt den Trip des Nutzers (Rain%, Visib, CAPE etc. sichtbar)."""
    from app.metric_catalog import build_default_display_config
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = True
        # Roh-/Zahlen-Modus erzwingen (wie der Trip des Nutzers): build_html_indicator_keys
        # liest use_friendly_format DIREKT — Attribut ggf. neu setzen, sonst bleibt es True
        # (Default) → Ampel-Emojis statt Zahlen.
        try:
            object.__setattr__(mc, "use_friendly_format", False)
        except Exception:
            mc.use_friendly_format = False
        try:
            object.__setattr__(mc, "format_mode", "raw")
        except Exception:
            pass
    return dc


def _warn_row():
    """Eine Stundenzeile, deren Werte je Metrik die WARN-Schwelle überschreiten
    (Design-Schwellen: wind>30, gust>45, precip>4, pop>70, visibility<1 km)."""
    from app.models import ForecastDataPoint, ThunderLevel
    from output.renderers.email.helpers import dp_to_row
    dp = ForecastDataPoint(
        ts=datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc),
        t2m_c=17.2,
        wind10m_kmh=35.0,     # > 30 → warn
        gust_kmh=50.0,        # > 45 → warn
        precip_1h_mm=5.0,     # > 4  → warn
        cloud_total_pct=100,
        thunder_level=ThunderLevel.NONE,
        wind_chill_c=17.0,
        snowfall_limit_m=None,
        humidity_pct=80,
    )
    # dp-Felder für die zusätzlichen Spalten (dp_to_row liest getattr(dp, dp_field)):
    dp.pop_pct = 80           # > 70 → warn  (Rain%)
    dp.visibility_m = 800     # 0.8 km → < 1 → warn (Visib)
    dp.cape_jkg = 1500        # CAPE (CAPE)
    row = dp_to_row(dp, _numeric_dc(), tz=ZoneInfo("Europe/Berlin"))
    row["risk"] = "warn"
    return row


def _render_full_html(rows):
    """Volle Briefing-Mail über den ECHTEN Produktions-Einstiegspunkt render_email().

    WICHTIG: render_email() baut format_modes + indicator_keys SELBST aus der
    display_config (build_html_indicator_keys). Nur so trifft der Test den
    realen Zahlen-Modus des Nutzers — render_html() direkt aufzurufen (ohne
    indicator_keys) würde fälschlich Ampel-Emojis erzeugen.
    """
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    from output.renderers.email import render_email
    kw = _common_kwargs()
    kw["display_config"] = _numeric_dc()
    kw["seg_tables"] = [rows]
    kw["tz"] = ZoneInfo("Europe/Berlin")
    kw["multi_day_trend"] = None
    html, _plain = render_email(_make_token_line(), **kw)
    return html


# ---------------------------------------------------------------------------
# Playwright-Harness: Desktop-Breite, berechnete Stile auslesen
# ---------------------------------------------------------------------------
DESKTOP_TABLE = "div.desktop-only table[data-table='resp'], div.desktop-only table.resp"


def _with_desktop_page(html, fn):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1000, "height": 1400})
        page.set_content(html, wait_until="load")
        try:
            return fn(page)
        finally:
            browser.close()


def _cell_styles(page):
    """Liste der berechneten Stile aller Datenzellen der Desktop-Tabelle."""
    return page.evaluate(
        """(sel)=>{
            const tbl = document.querySelector(sel);
            if(!tbl) return null;
            const tds = Array.from(tbl.querySelectorAll('tbody td'));
            return tds.map(td=>{
                const inner = td.firstElementChild;
                // Hintergrund kann auf <td> oder auf innerem <span> liegen:
                const bgTd = getComputedStyle(td).backgroundColor;
                const bgInner = inner ? getComputedStyle(inner).backgroundColor : 'rgba(0, 0, 0, 0)';
                return {
                    label: td.getAttribute('data-label'),
                    text: td.innerText.trim(),
                    borderRight: getComputedStyle(td).borderRightColor,
                    borderBottom: getComputedStyle(td).borderBottomColor,
                    bgTd, bgInner,
                    fontFamily: getComputedStyle(td).fontFamily,
                };
            });
        }""",
        DESKTOP_TABLE,
    )


# ===========================================================================
# AC-1 — Linienfarbe durchgängig #f0ece1
# ===========================================================================
class TestAC1LineColor:
    def test_all_cell_borders_are_design_line_color(self):
        html = _render_full_html([_warn_row()])
        cells = _with_desktop_page(html, _cell_styles)
        assert cells, "Desktop-Tabelle nicht gefunden / leer"
        wrong = [
            (c["label"], c["borderRight"], c["borderBottom"])
            for c in cells
            if c["borderRight"] != LINE_COLOR_RGB or c["borderBottom"] != LINE_COLOR_RGB
        ]
        assert not wrong, (
            "Zell-Linien NICHT durchgängig #f0ece1 (rgb(240,236,225)).\n"
            "Abweichende Zellen (label, border-right, border-bottom):\n  "
            + "\n  ".join(str(w) for w in wrong)
        )


# ===========================================================================
# AC-2 — Risk-Hintergrund je Schweregrad (getönte Zelle, nicht weiß)
# ===========================================================================
class TestAC2RiskBackground:
    @pytest.mark.parametrize("label", ["Wind", "Gust", "Rain", "Rain%", "Visib"])
    def test_warn_cell_has_tinted_background(self, label):
        html = _render_full_html([_warn_row()])
        cells = _with_desktop_page(html, _cell_styles)
        assert cells, "Desktop-Tabelle nicht gefunden / leer"
        match = [c for c in cells if c["label"] == label]
        assert match, f"Spalte {label!r} nicht in Tabelle (labels: {[c['label'] for c in cells]})"
        c = match[0]
        bg = c["bgTd"] if c["bgTd"] not in WHITE_OR_TRANSPARENT else c["bgInner"]
        assert bg == RISK_CELL["warn"], (
            f"Zelle {label!r} (Wert {c['text']!r}) muss WARN-Tönung "
            f"{RISK_CELL['warn']} (#fad6b8) tragen, hat aber {bg!r}. "
            "Vorlage sevCellStyle → RISK_CELL.warn.bg."
        )


# ===========================================================================
# AC-3 — Tabelleninhalt Monospace (nicht Body-Font Inter/sans)
# ===========================================================================
class TestAC3Monospace:
    def test_data_cell_font_is_monospace(self):
        html = _render_full_html([_warn_row()])
        cells = _with_desktop_page(html, _cell_styles)
        assert cells, "Desktop-Tabelle nicht gefunden / leer"
        c = cells[0]
        ff = c["fontFamily"].lower()
        assert ("jetbrains mono" in ff) or ("monospace" in ff), (
            f"Tabelleninhalt-Font ist {c['fontFamily']!r} — erwartet JetBrains-Mono/"
            "monospace. Die Tabelle erbt den serifenlosen Body-Font (Inter)."
        )

    def test_table_renders_with_true_monospace_metrics(self):
        """Echte Monospace-Prüfung: 'WWWW' und 'iiii' in der Tabellen-Schrift
        müssen gleich breit sein (variable Fonts wie Inter wären unterschiedlich)."""
        html = _render_full_html([_warn_row()])

        def measure(page):
            return page.evaluate(
                """(sel)=>{
                    const tbl = document.querySelector(sel);
                    if(!tbl) return null;
                    const ff = getComputedStyle(tbl.querySelector('tbody td')).fontFamily;
                    const mk = (t)=>{const s=document.createElement('span');
                        s.style.fontFamily=ff; s.style.fontSize='13px';
                        s.style.position='absolute'; s.style.whiteSpace='pre';
                        s.textContent=t; document.body.appendChild(s);
                        const w=s.getBoundingClientRect().width; s.remove(); return w;};
                    return {w: mk('WWWW'), i: mk('iiii')};
                }""",
                DESKTOP_TABLE,
            )

        res = _with_desktop_page(html, measure)
        assert res, "Desktop-Tabelle nicht gefunden / leer"
        assert abs(res["w"] - res["i"]) < 0.5, (
            f"Tabellen-Font ist NICHT monospace: Breite 'WWWW'={res['w']}px vs "
            f"'iiii'={res['i']}px. Bei echtem Monospace identisch."
        )


# ===========================================================================
# AC-4/AC-5 (#995 Gruppe B) — Zell-Hintergrund direkt auf <td>, kein Span-Trick
# ===========================================================================
class TestAC4AC5CellBackgroundInline:
    """AC-4 (Geometrie td vs. Hintergrund-Element) lässt sich mit reinem
    Chromium-Rendering NICHT zuverlässig als RED zeigen: Chromium löst den
    aktuellen `margin:-6px -6px` / `padding:6px 6px`-Span-Trick gegen das
    globale `td{padding:6px}` aus dem <style>-Block korrekt auf (html.py:1471),
    die gemessene Lücke kann daher bereits jetzt ~0px sein. Das reale Problem
    tritt nur in Mail-Clients auf, die den <style>-Block strippen/anders
    auflösen (Outlook, teils Apple Mail) — die finale Bestätigung für AC-4 ist
    deshalb NICHT dieser Test, sondern der echte Testversand via
    briefing_mail_validator.py gegen das Staging-Testpostfach (AC-6, kein
    pytest, siehe CLAUDE.md Mail-Validatoren).

    AC-5 (strukturelle Abwesenheit des Span-Wrappers) ist dagegen JETZT
    zuverlässig RED: der Span mit negativem Margin existiert im generierten
    DOM für jede getönte Zelle.
    """

    def test_ac5_no_negative_margin_span_in_data_cells(self):
        html = _render_full_html([_warn_row()])
        count = _with_desktop_page(html, lambda page: page.evaluate(
            """() => {
                const tds = Array.from(document.querySelectorAll('tbody td[data-label]'));
                return tds.filter(td => td.querySelector('span[style*="margin:-6"]') !== null).length;
            }"""
        ))
        assert count == 0, (
            f"{count} getönte Zelle(n) verwenden noch den Span/Negativ-Margin-"
            "Wrapper (margin:-6px) statt Hintergrund+Padding direkt inline auf "
            "<td> (Vorbild _otd()-Muster html.py:1106-1117). Nach dem Fix muss "
            "die Zählung 0 sein."
        )

    def test_ac4_tinted_background_geometry_matches_td(self):
        """Geometrie-Nachweis (best-effort, siehe Klassendocstring): das
        Hintergrund-tragende Element (Span jetzt, <td> nach dem Fix) muss die
        <td>-Fläche randlos abdecken (Lücke ≤ 1px)."""
        html = _render_full_html([_warn_row()])
        geom = _with_desktop_page(html, lambda page: page.evaluate(
            """() => {
                const tds = Array.from(document.querySelectorAll('tbody td[data-label]'));
                for (const td of tds) {
                    const tdBg = getComputedStyle(td).backgroundColor;
                    let bgEl = null;
                    if (tdBg && tdBg !== 'rgba(0, 0, 0, 0)' && tdBg !== 'transparent') {
                        bgEl = td;
                    } else {
                        const span = td.querySelector('span');
                        const spanBg = span ? getComputedStyle(span).backgroundColor : null;
                        if (spanBg && spanBg !== 'rgba(0, 0, 0, 0)' && spanBg !== 'transparent') {
                            bgEl = span;
                        }
                    }
                    if (bgEl) {
                        const tdBox = td.getBoundingClientRect();
                        const bgBox = bgEl.getBoundingClientRect();
                        return {
                            found: true,
                            leftGap: bgBox.left - tdBox.left,
                            rightGap: tdBox.right - bgBox.right,
                            topGap: bgBox.top - tdBox.top,
                            bottomGap: tdBox.bottom - bgBox.bottom,
                        };
                    }
                }
                return {found: false};
            }"""
        ))
        assert geom["found"], "Getönte Zelle mit Hintergrund-Element nicht gefunden"
        max_gap = max(abs(geom["leftGap"]), abs(geom["rightGap"]),
                      abs(geom["topGap"]), abs(geom["bottomGap"]))
        assert max_gap <= 1.0, f"Geometrie-Lücke > 1px zwischen Hintergrund und <td>: {geom}"
