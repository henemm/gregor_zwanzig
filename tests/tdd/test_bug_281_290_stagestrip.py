"""
TDD Tests — Bug #290 + #281: StageStrip & g-accent Fallback

SPEC: docs/specs/modules/bug_281_290_stagestrip.md

Hintergrund:
  #290: StageDetailRow.svelte hatte var(--g-accent, #3b82f6) —
        blauer Hex-Fallback widerspricht Issue-#277-Konvention (gefixt).
  #281: Stage-Pills im Cockpit-StageStrip umbrachen bei langen Namen.

Sanierung Issue #355:
  Die Pill-/Strip-Komponenten lebten unter frontend/src/routes/_cockpit/
  (StagePill.svelte, StageStrip.svelte). Dieser Cockpit-Code wurde im
  SvelteKit-Rework entfernt — die zugehoerigen AC-2..AC-5-Tests sind obsolet
  und wurden geloescht. AC-1 (StageDetailRow blauer Fallback) und der
  globale app.css-Pill-Block existieren weiterhin und bleiben getestet.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

STAGE_DETAIL_ROW = FRONTEND_SRC / "lib" / "components" / "trip-detail" / "StageDetailRow.svelte"
APP_CSS = FRONTEND_SRC / "app.css"


# ---------------------------------------------------------------------------
# AC-1 — Kein falscher blauer Hex-Fallback
# ---------------------------------------------------------------------------


def test_no_blue_accent_fallback_in_stage_detail_row():
    """
    GIVEN:  StageDetailRow.svelte (Bug #290)
    WHEN:   Quelltext nach 'var(--g-accent, #3b82f6)' durchsucht wird
    THEN:   0 Treffer — Token löst sich stets zu #c45a2a auf, Fallback ist falsch

    RED: var(--g-accent, #3b82f6) existiert noch in Z.230
    """
    assert STAGE_DETAIL_ROW.exists(), f"Datei nicht gefunden: {STAGE_DETAIL_ROW}"

    content = STAGE_DETAIL_ROW.read_text()
    count = content.count("var(--g-accent, #3b82f6)")
    assert count == 0, (
        f"Gefunden: {count} Vorkommen von 'var(--g-accent, #3b82f6)' in "
        f"{STAGE_DETAIL_ROW.relative_to(REPO_ROOT)}. "
        "Fix: Fallback entfernen → var(--g-accent)"
    )


# ---------------------------------------------------------------------------
# AC-2 — Einzeilige Pills mit Truncation (globaler app.css-Block)
# ---------------------------------------------------------------------------


def test_pill_global_css_has_whitespace_nowrap():
    """
    GIVEN:  app.css [data-slot='pill']-Block (Bug #281)
    WHEN:   Quelltext nach 'white-space: nowrap' im Pill-Block durchsucht wird
    THEN:   Vorhanden — verhindert Zeilenumbruch in allen Pill-Instanzen

    RED: white-space: nowrap fehlt im globalen Pill-Block
    """
    assert APP_CSS.exists(), f"Datei nicht gefunden: {APP_CSS}"

    content = APP_CSS.read_text()
    pill_start = content.find('[data-slot="pill"]')
    assert pill_start != -1, "Kein [data-slot='pill'] Block in app.css gefunden"

    pill_section = content[pill_start : pill_start + 300]
    assert "white-space: nowrap" in pill_section, (
        "'white-space: nowrap' fehlt im [data-slot='pill']-Block in app.css. "
        "Fix: white-space: nowrap; zum Pill-Block hinzufügen"
    )


# ---------------------------------------------------------------------------
# AC-3..AC-5 (StagePill/StageStrip unter routes/_cockpit/) — geloescht in #355.
# Der Cockpit-Code wurde im SvelteKit-Rework entfernt; die Tests referenzierten
# nicht mehr existente Pfade und sind obsolet (siehe Modul-Docstring).
# ---------------------------------------------------------------------------
