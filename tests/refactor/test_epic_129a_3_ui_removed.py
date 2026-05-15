"""
RED-Tests fuer Epic #129 Phase A.3 - NiceGUI ersatzlos loeschen + Service abklemmen.
Spec: docs/specs/epic_129a_3_ui_removal.md
Test-Manifest: docs/specs/tests/epic_129a_3_ui_removed_tests.md

Diese Tests pruefen den Ziel-Zustand nach der Loesch-Aktion:
  - test_ac1_src_web_directory_empty (AC-1) -> src/web/ enthaelt keine .py-Dateien mehr
  - test_ac2_no_imports_from_web    (AC-2) -> kein externer Import auf web.* / src.web.*
  - test_ac3_seven_test_files_deleted (AC-3) -> 7 spezifische Test-Files sind weg
  - test_ac4_pyproject_no_nicegui_apscheduler (AC-4) -> Dependencies entfernt
  - test_ac5_no_web_main_in_hooks   (AC-5) -> .claude/validate.py + e2e-verify.md sauber
  - test_ac7_collection_clean       (AC-7) -> pytest collect-only ohne Errors

AC-6 (systemctl is-active gregor_zwanzig.service -> inactive) ist ein Live-Smoke-Check
nach Prod-Deploy und kein pytest-Test (siehe Spec, Verification-Sektion).

Vor der GREEN-Phase muessen mindestens AC-1, AC-2, AC-3, AC-4 und AC-5 FAIL sein.

Test-Namen verwenden Bezeichner aus der Spec, damit der spec-enforcement-Hook
sie der zentralen Spec zuordnen kann.
"""
from pathlib import Path
import subprocess

import pytest  # noqa: F401  (Konvention: pytest in Refactor-Tests immer importiert)

REPO = Path(__file__).resolve().parents[2]


def test_ac1_src_web_directory_empty():
    """AC-1: src/web/ darf keine .py-Dateien mehr enthalten.

    Akzeptiert: Verzeichnis komplett geloescht ODER existiert noch ohne .py-Dateien
    (z. B. nur leere __pycache__/-Reste, die wir ignorieren).
    """
    web = REPO / "src" / "web"
    if not web.exists():
        return  # geloescht — perfekt
    py_files = [
        p for p in web.rglob("*.py") if "__pycache__" not in str(p)
    ]
    assert py_files == [], (
        f"src/web/ hat noch Python-Dateien: {py_files}"
    )


def test_ac2_no_imports_from_web():
    """AC-2: Niemand importiert mehr aus web.* oder src.web.*.

    Pruefbereich: src/, api/, tests/, .claude/. Diese Test-Datei selbst wird
    aus der Trefferliste gefiltert (sie enthaelt die Such-Pattern als String-
    Konstanten in der Doku, nicht als echte Imports).
    """
    result = subprocess.run(
        [
            "grep",
            "-rn",
            "--include=*.py",
            "--exclude-dir=.git",
            "--exclude-dir=worktrees",
            "--exclude-dir=__pycache__",
            "--exclude-dir=.venv",
            "--exclude-dir=node_modules",
            "--exclude-dir=htmlcov",
            "-E",
            r"from web\.|^import web\.|^import src\.web|from src\.web",
            "src/",
            "api/",
            "tests/",
            ".claude/",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    lines = [
        line
        for line in result.stdout.splitlines()
        if "test_epic_129a_3_ui_removed.py" not in line
    ]
    assert lines == [], (
        "Verbleibende web.* Imports:\n" + "\n".join(lines)
    )


def test_ac3_seven_test_files_deleted():
    """AC-3: Genau diese 7 Test-Dateien sind ersatzlos geloescht."""
    deleted = [
        "tests/tdd/test_weather_config_api_ui.py",
        "tests/tdd/test_safari_cache_fix.py",
        "tests/tdd/test_betterstack_heartbeat.py",
        "tests/e2e/test_weather_config.py",
        "tests/integration/test_trip_report_scheduler.py",
        "tests/unit/test_settings_protection.py",
        "tests/unit/test_weather_config_strategy.py",
    ]
    still_there = [f for f in deleted if (REPO / f).exists()]
    assert still_there == [], (
        f"Diese Test-Files sind noch nicht geloescht: {still_there}"
    )


def test_ac4_pyproject_no_nicegui_apscheduler():
    """AC-4: pyproject.toml referenziert nicegui + apscheduler nicht mehr.

    Substring-Check ueber die ganze Datei (Dependencies + Ruff-Exceptions).
    """
    content = (REPO / "pyproject.toml").read_text()
    forbidden = ["nicegui", "apscheduler"]
    found = [s for s in forbidden if s in content]
    assert found == [], (
        f"pyproject.toml referenziert noch: {found}"
    )


def test_ac5_no_web_main_in_hooks():
    """AC-5: .claude/validate.py + .claude/commands/e2e-verify.md haben keine
    String-Eval-Imports mehr auf web.main / web.scheduler / -m src.web.main.
    """
    forbidden = [
        "from web.main",
        "from web.scheduler",
        "-m src.web.main",
        "-m web.main",
    ]
    offenders = []
    for path in [".claude/validate.py", ".claude/commands/e2e-verify.md"]:
        full = REPO / path
        if not full.exists():
            continue
        content = full.read_text()
        for s in forbidden:
            if s in content:
                offenders.append(f"{path}: '{s}'")
    assert offenders == [], (
        "Verbleibende Hook-/Command-Referenzen auf NiceGUI-Entrypoints:\n  - "
        + "\n  - ".join(offenders)
    )


def test_ac7_collection_clean():
    """AC-7: pytest --collect-only laeuft ohne Collection-Errors.

    Wir pruefen nicht die genaue Test-Anzahl (Spec sagt "mind. 50 Tests
    weniger"), sondern dass keine Imports auf gestrichene Module crashen.
    """
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "tests/",
            "--collect-only",
            "-q",
            "--no-header",
        ],
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    combined = (result.stdout + result.stderr).lower()
    # pytest meldet Collection-Probleme als "error during collection" (Singular)
    # oder "errors during collection" (Plural). Wir matchen den gemeinsamen
    # Substring "error during collection", der beide Varianten abdeckt.
    assert "error during collection" not in combined, (
        f"Collection errors:\n{combined[-2500:]}"
    )
    # Defensiv zusaetzlich: pytest-Exit-Code 0 (= keine Errors).
    assert result.returncode == 0, (
        f"pytest --collect-only returncode={result.returncode}:\n{combined[-2500:]}"
    )
