"""TDD-Tests fuer Issue #316 — docs/reference Cleanup.

Reine Datei-/Inhalts-Verifikation (kein Mock, keine API): die Tests lesen die
echten Dateien im Repo und pruefen die 5 Akzeptanzkriterien aus
`docs/specs/modules/issue_316_docs_reference_cleanup.md`.

RED-Phase: Alle Tests MUESSEN aktuell fehlschlagen, weil das Cleanup noch nicht
durchgefuehrt ist (nicegui-Doc existiert, frontend_components.md veraltet).
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = REPO_ROOT / "docs" / "reference"
FRONTEND_COMPONENTS = REFERENCE_DIR / "frontend_components.md"
NICEGUI_DOC = REFERENCE_DIR / "nicegui_best_practices.md"
COMPONENTS_DIR = REPO_ROOT / "frontend" / "src" / "lib" / "components"

LIVE_TOOLING = [
    REPO_ROOT / ".claude" / "agents" / "feature-planner.md",
    REPO_ROOT / ".claude" / "standards" / "safari_compatibility.md",
]

# Nicht mehr existierende Cockpit-Komponenten (durch _home-Kacheln ersetzt).
PHANTOM_COCKPIT = ["StagePill", "StageStrip", "ActiveTripCard", "BriefingsTimeline", "AlertFeed", "BottomRow"]

# In Issue #316 namentlich genannte, bisher undokumentierte Komponenten.
NAMED_COMPONENTS = [
    "MapCanvas",
    "WaypointPin",
    "PauseStageView",
    "ProfileEditor",
    "StageCard",
    "WaypointCard",
    "LocationPreviewMap",
    "NewLocationWizard",
    "AlertRulesEditor",
    "AlertRuleRow",
    "ModeCard",
    "Wordmark",
]


def _doc_text() -> str:
    return FRONTEND_COMPONENTS.read_text(encoding="utf-8")


def _component_category_dirs() -> list[str]:
    """Direkte Unterverzeichnisse von frontend/src/lib/components/ (Kategorien)."""
    return sorted(
        p.name
        for p in COMPONENTS_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("__")
    )


# --- AC-1: jede Komponente/Kategorie ist im Doc auffindbar -------------------

def test_ac1_all_component_category_dirs_documented():
    """AC-1: Jedes Unterverzeichnis von lib/components/ wird im Doc erwaehnt."""
    text = _doc_text()
    categories = _component_category_dirs()
    assert categories, "Keine Komponenten-Kategorien gefunden — Pfad falsch?"
    missing = [cat for cat in categories if cat not in text]
    assert not missing, f"Undokumentierte Komponenten-Kategorien: {missing}"


def test_ac1_named_components_documented():
    """AC-1: Alle in #316 namentlich genannten Komponenten stehen im Doc."""
    text = _doc_text()
    missing = [name for name in NAMED_COMPONENTS if name not in text]
    assert not missing, f"Im Doc fehlende Komponenten: {missing}"


# --- AC-2: kein NiceGUI-Bezug mehr in docs/reference ------------------------

def test_ac2_no_nicegui_reference_in_docs_reference():
    """AC-2: Keine .md-Datei in docs/reference/ erwaehnt 'nicegui'."""
    offenders = []
    for md in sorted(REFERENCE_DIR.glob("*.md")):
        if "nicegui" in md.read_text(encoding="utf-8").lower():
            offenders.append(md.name)
    assert not offenders, f"NiceGUI-Bezug in docs/reference/ gefunden: {offenders}"


# --- AC-3: nicegui-Doc geloescht --------------------------------------------

def test_ac3_nicegui_doc_deleted():
    """AC-3: docs/reference/nicegui_best_practices.md existiert nicht mehr."""
    assert not NICEGUI_DOC.exists(), (
        "nicegui_best_practices.md existiert noch — sollte geloescht sein."
    )


# --- AC-4: kein toter Link in lebendigem Tooling ----------------------------

@pytest.mark.parametrize("tooling_file", LIVE_TOOLING, ids=lambda p: p.name)
def test_ac4_no_dangling_nicegui_link_in_live_tooling(tooling_file: Path):
    """AC-4: Aktives .claude/-Tooling verweist nicht mehr auf das geloeschte Doc."""
    assert tooling_file.exists(), f"Tooling-Datei fehlt: {tooling_file}"
    text = tooling_file.read_text(encoding="utf-8")
    assert "nicegui_best_practices.md" not in text, (
        f"Toter NiceGUI-Link in {tooling_file.name}"
    )


# --- AC-5: Stand-Datum + Wordmark-Props -------------------------------------

def test_ac5_updated_date_bumped():
    """AC-5: Header traegt das aktuelle Stand-Datum 2026-05-25."""
    text = _doc_text()
    assert "**Updated:** 2026-05-25" in text, (
        "Stand-Datum nicht auf 2026-05-25 aktualisiert."
    )


def test_ac5_wordmark_props_documented():
    """AC-5: Wordmark ist mit einem Props-Interface dokumentiert."""
    text = _doc_text()
    assert "WordmarkProps" in text, (
        "Wordmark-Props-Interface (WordmarkProps) nicht im Doc dokumentiert."
    )


# --- Guard: keine Phantom-Cockpit-Komponenten ------------------------------

def test_no_phantom_cockpit_components():
    """Guard (F002): Doc listet keine nicht mehr existierenden _cockpit-Komponenten."""
    text = _doc_text()
    assert "_cockpit" not in text, "Verweis auf nicht-existentes routes/_cockpit/ im Doc"
    present = [c for c in PHANTOM_COCKPIT if c in text]
    assert not present, f"Nicht mehr existierende Cockpit-Komponenten im Doc: {present}"
