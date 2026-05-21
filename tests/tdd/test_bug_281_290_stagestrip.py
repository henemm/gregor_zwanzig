"""
TDD RED Tests — Bug #290 + #281: StageStrip & g-accent Fallback

SPEC: docs/specs/modules/bug_281_290_stagestrip.md

Hintergrund:
  #290: StageDetailRow.svelte Z.230 hat var(--g-accent, #3b82f6) —
        blauer Hex-Fallback widerspricht Issue-#277-Konvention.
  #281: Stage-Pills im Cockpit-StageStrip umbrechen bei langen Namen
        auf mehrere Zeilen. Design-Intent: einzeilige Chips mit Truncation.

RED-Zustand (jetzt):
  - var(--g-accent, #3b82f6) noch in StageDetailRow.svelte → AC-1 FAIL
  - stage-pill__label fehlt in StagePill.svelte → AC-2 FAIL
  - title={label} fehlt in StagePill.svelte → AC-3 FAIL
  - font-weight für .active fehlt in StagePill.svelte → AC-4 FAIL
  - strip-fade-right fehlt in StageStrip.svelte → AC-5 FAIL
  - white-space: nowrap fehlt im Pill-Block von app.css → AC-2 FAIL
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"

STAGE_DETAIL_ROW = FRONTEND_SRC / "lib" / "components" / "trip-detail" / "StageDetailRow.svelte"
STAGE_PILL = REPO_ROOT / "frontend" / "src" / "routes" / "_cockpit" / "StagePill.svelte"
STAGE_STRIP = REPO_ROOT / "frontend" / "src" / "routes" / "_cockpit" / "StageStrip.svelte"
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
# AC-2 — Einzeilige Pills mit Truncation
# ---------------------------------------------------------------------------


def test_stage_pill_has_label_wrapper_class():
    """
    GIVEN:  StagePill.svelte (Bug #281)
    WHEN:   Quelltext nach 'stage-pill__label' durchsucht wird
    THEN:   Mindestens 1 Treffer — Label-Wrapper für text-overflow: ellipsis

    RED: stage-pill__label fehlt → kein Truncation-Wrapper
    """
    assert STAGE_PILL.exists(), f"Datei nicht gefunden: {STAGE_PILL}"

    content = STAGE_PILL.read_text()
    assert "stage-pill__label" in content, (
        "Klasse 'stage-pill__label' fehlt in StagePill.svelte. "
        "Fix: Label in <span class='stage-pill__label'> wrappen mit "
        "overflow:hidden; text-overflow:ellipsis; white-space:nowrap"
    )


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
# AC-3 — Nativer Tooltip mit vollem Label
# ---------------------------------------------------------------------------


def test_stage_pill_has_title_binding():
    """
    GIVEN:  StagePill.svelte (Bug #281)
    WHEN:   Quelltext nach 'title={label}' durchsucht wird
    THEN:   Vorhanden — Browser zeigt vollständigen Stage-Namen beim Hover

    RED: title={label} fehlt → kein nativer Tooltip
    """
    assert STAGE_PILL.exists(), f"Datei nicht gefunden: {STAGE_PILL}"

    content = STAGE_PILL.read_text()
    assert "title={label}" in content, (
        "'title={label}' fehlt in StagePill.svelte. "
        "Fix: title={label} auf den äußeren <span> setzen"
    )


# ---------------------------------------------------------------------------
# AC-4 — Aktive Pill visuell hervorgehoben
# ---------------------------------------------------------------------------


def test_stage_pill_active_has_bold_style():
    """
    GIVEN:  StagePill.svelte (Bug #281)
    WHEN:   Quelltext nach font-weight + active-Kombination durchsucht wird
    THEN:   Beide vorhanden — aktive Stage-Pill zeigt Label in font-weight: 600

    RED: StagePill hat keinen .active-spezifischen font-weight-Style
    """
    assert STAGE_PILL.exists(), f"Datei nicht gefunden: {STAGE_PILL}"

    content = STAGE_PILL.read_text()
    assert ".stage-pill.active .stage-pill__label" in content and "font-weight: 600" in content, (
        "Kein spezifischer '.stage-pill.active .stage-pill__label { font-weight: 600 }' in StagePill.svelte. "
        "Fix: .stage-pill.active .stage-pill__label { font-weight: 600; }"
    )


# ---------------------------------------------------------------------------
# AC-5 — Scroll-Affordance: rechte Fade-Maske
# ---------------------------------------------------------------------------


def test_stage_strip_has_fade_mask():
    """
    GIVEN:  StageStrip.svelte (Bug #281)
    WHEN:   Quelltext nach 'strip-fade-right' durchsucht wird
    THEN:   Vorhanden — gradient-Maske signalisiert weiteren Scroll-Content

    RED: strip-fade-right fehlt in StageStrip.svelte
    """
    assert STAGE_STRIP.exists(), f"Datei nicht gefunden: {STAGE_STRIP}"

    content = STAGE_STRIP.read_text()
    assert "strip-fade-right" in content, (
        "'strip-fade-right' fehlt in StageStrip.svelte. "
        "Fix: <div class='strip-fade-right' aria-hidden='true'> mit "
        "gradient: transparent → var(--g-paper) einbauen"
    )
