"""
Tests für Issue #254 — Email-Template Vorarbeit (EPIC 9 Prerequisite).

SPEC: docs/specs/modules/issue_254_email_template_vorarbeit.md

RED-Zustand (jetzt):
  - design_system.md hat noch keinen §12-Abschnitt → Assertion-Fails
  - scripts/preview_email.py existiert NICHT → FileNotFoundError / subprocess.CalledProcessError
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_SYSTEM_MD = REPO_ROOT / "docs" / "reference" / "design_system.md"
TOKENS_CSS = REPO_ROOT / "docs" / "reference" / "design_system_tokens.css"
PREVIEW_SCRIPT = REPO_ROOT / "scripts" / "preview_email.py"


# ---------------------------------------------------------------------------
# AC-1: design_system.md enthält §12 mit app.css als verbindlicher Quelle
# ---------------------------------------------------------------------------

def test_ac1_design_system_md_has_mail_tokens_section():
    """AC-1: §12 enthält einen Mail-Tokens-Unterabschnitt (nicht nur Begleit-Dateien)."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    # §12 existiert bereits als "Begleit-Dateien" — gesucht wird ein spezifischer
    # Mail-Tokens-Abschnitt innerhalb von §12 oder als §13.
    lower = content.lower()
    assert "mail-token" in lower or "mail token" in lower or "## 12 · mail" in lower or "### mail" in lower, (
        "design_system.md braucht einen Abschnitt speziell für Mail-Tokens "
        "(z.B. '### Mail-Tokens: Single Source of Truth' in §12)"
    )


def test_ac1_design_system_md_names_app_css_as_source():
    """AC-1: §12 benennt app.css explizit als verbindliche Source for Mail-Templates."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    # Die Verbindlichkeit muss im Mail-Kontext stehen (nicht nur generisch "im Zweifel")
    lower = content.lower()
    assert "mail" in lower and "app.css" in content and (
        "verbindlich" in lower or "single source" in lower
    ), (
        "§12 muss app.css als verbindliche Mail-Token-Quelle nennen "
        "(app.css + 'verbindlich'/'Single Source' im Mail-Kontext)"
    )


def test_ac1_design_system_md_lists_naming_deviations():
    """AC-1: §12 dokumentiert alten → neuen Token-Namen-Mapping als Tabelle."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    # Suche nach der konkreten Mapping-Tabelle (--g-good → --g-success)
    assert "--g-good" in content, (
        "§12 muss das Mapping-Paar --g-good → --g-success dokumentieren "
        "(als Tabelle mit altem und neuem Namen)"
    )
    assert "--g-bad" in content, (
        "§12 muss das Mapping-Paar --g-bad → --g-danger dokumentieren"
    )


def test_ac1_design_system_md_references_thunder_bug():
    """AC-1: §12 verweist auf den --g-weather-thunder-Farbkonflikt mit Issue-Nummer."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    # Muss eine Issue-Referenz für den Thunder-Bug enthalten (nicht nur thunder im Icon-Set)
    # Der bestehende `--g-wx-thunder` in der Farbtabelle reicht nicht — es muss ein
    # spezifischer Bug-Hinweis sein.
    assert ("weather-thunder" in content or "g-weather-thunder" in content) and (
        "Bug" in content or "bug" in content or "#" in content
    ), (
        "§12 muss auf den --g-weather-thunder Farbkonflikt MIT Bug-Issue-Referenz hinweisen "
        "(nicht nur den Token in der Farbtabelle)"
    )


def test_ac1_tokens_css_comment_references_decision():
    """AC-1: design_system_tokens.css Kommentar-Header verweist explizit auf §12."""
    content = TOKENS_CSS.read_text(encoding="utf-8")
    # Aktueller Stand: "Im Zweifel gilt app.css. Stand-Sync via Issue #213"
    # Gesucht: expliziter Verweis auf §12 oder "Mail-Tokens" oder "verbindlich"
    assert "§12" in content or ("mail" in content.lower() and "verbindlich" in content.lower()), (
        "design_system_tokens.css Kommentar-Header muss explizit auf §12 in design_system.md verweisen "
        "(aktuell steht nur 'Im Zweifel gilt app.css' — nicht spezifisch genug)"
    )


# ---------------------------------------------------------------------------
# AC-2: html.py-Inventar vollständig dokumentiert in §12
# ---------------------------------------------------------------------------

def test_ac2_inventory_dark_footer_assessed():
    """AC-2: Dunkel-Footer-Baustein ist als FEHLT bewertet in §12."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    assert "Dunkel" in content or "dunkel" in content or "dark footer" in content.lower(), (
        "§12 muss Dunkel-Footer als FEHLT dokumentieren"
    )


def test_ac2_inventory_daylight_svg_assessed():
    """AC-2: Daylight-Bar (SVG) ist als FEHLT bewertet in §12."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    assert "Daylight" in content or "daylight" in content, (
        "§12 muss Daylight-Bar (SVG) als FEHLT dokumentieren"
    )


def test_ac2_inventory_tag_system_assessed():
    """AC-2: Tag-System ok/warn/risk/info ist bewertet in §12."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    lower = content.lower()
    assert "tag-system" in lower or "ok/warn" in content or "tag system" in lower, (
        "§12 muss Tag-System ok/warn/risk/info bewerten"
    )


def test_ac2_inventory_all_six_components_present():
    """AC-2: Alle 6 Bausteine erwähnt — ActivityProfile, Inline-CSS, Fonts."""
    content = DESIGN_SYSTEM_MD.read_text(encoding="utf-8")
    lower = content.lower()
    assert "activityprofile" in lower or "activity_profile" in lower, (
        "§12 muss ActivityProfile-Status dokumentieren"
    )
    assert "inline" in lower, (
        "§12 muss Inline-CSS-Only-Status dokumentieren"
    )
    assert "inter tight" in lower or "jetbrains" in lower, (
        "§12 muss Font-Stack-Status dokumentieren"
    )


# ---------------------------------------------------------------------------
# AC-3: scripts/preview_email.py existiert und läuft fehlerfrei
# ---------------------------------------------------------------------------

def test_ac3_preview_script_exists():
    """AC-3: scripts/preview_email.py existiert."""
    assert PREVIEW_SCRIPT.exists(), (
        f"scripts/preview_email.py nicht gefunden unter {PREVIEW_SCRIPT}"
    )


def test_ac3_preview_script_runs_without_error(tmp_path):
    """AC-3: Skript läuft ohne Fehler und erzeugt HTML-Datei."""
    out_file = tmp_path / "email_preview.html"
    result = subprocess.run(
        [sys.executable, str(PREVIEW_SCRIPT), "--out", str(out_file)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Script beendet mit Exit {result.returncode}\n"
        f"STDOUT: {result.stdout}\n"
        f"STDERR: {result.stderr}"
    )
    assert out_file.exists(), "HTML-Datei wurde nicht erzeugt"


def test_ac3_preview_output_is_valid_html(tmp_path):
    """AC-3: Erzeugtes HTML hat valide Grundstruktur mit DOCTYPE und Tabelle."""
    out_file = tmp_path / "email_preview.html"
    subprocess.run(
        [sys.executable, str(PREVIEW_SCRIPT), "--out", str(out_file)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        timeout=30,
    )
    if not out_file.exists():
        pytest.skip("Datei nicht erzeugt — AC-3 Existenz-Test greift zuerst")
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content, "Kein DOCTYPE im Output"
    assert "<table" in content, "Kein <table>-Element im Output (Wettertabelle erwartet)"


def test_ac3_preview_script_no_network_calls():
    """AC-3: Skript importiert keine Netzwerk-Bibliotheken im Direkt-Aufruf."""
    if not PREVIEW_SCRIPT.exists():
        pytest.skip("Script existiert nicht — AC-3 Existenz-Test greift zuerst")
    import ast
    content = PREVIEW_SCRIPT.read_text(encoding="utf-8")
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        pytest.fail(f"Syntaxfehler in preview_email.py: {e}")
    network_modules = {"requests", "httpx", "aiohttp", "urllib"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                root = name.split(".")[0]
                assert root not in network_modules, (
                    f"Netzwerk-Bibliothek '{root}' im Preview-Script — AC-3 verlangt keine API-Calls"
                )
