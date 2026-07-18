"""
Tests für Dead-Code-Abbau Scheibe 3 (Issue #1215, letzte Scheibe).
Spec: docs/specs/modules/rework_1215_dead_code_scheibe3.md

Struktur-Beweise für die Entfernung der produktions-toten Go-Compare-Engine
(Access-Log-Vorprüfung 2026-07-11: 0 Aufrufe von /api/compare/run, je) und
des zugehörigen Frontend-Triggers. Datei-Existenz-/Inhalts-Prüfungen folgen
dem etablierten Muster der Scheibe-1/2-Struktur-Tests; die Go-Verhaltensebene
(go build/vet/test) läuft in der Implementierungs-Phase, weil edit_gate
_test.go-Dateien in der RED-Phase blockiert (bekannte Regel).

TDD RED: Vor der Implementierung schlagen die *_removed/*_moved-Tests fehl.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# `go` liegt auf manchen Entwicklungs-Hosts nicht auf PATH (z.B. nur unter
# /usr/local/go/bin installiert) — robust auflösen statt hart "go" anzunehmen.
_GO_FALLBACKS = ("/usr/local/go/bin/go", "/usr/lib/go/bin/go")


def _go_binary() -> str | None:
    found = shutil.which("go")
    if found:
        return found
    return next((p for p in _GO_FALLBACKS if Path(p).exists()), None)


# ── AC-1/AC-2: Umzug der Profil-Validierung + Go-Kompilat als Verhaltensnachweis
#
# #765: Kein read_text()/grep auf Produkt-Go-Quelltext mehr als Verhaltensnachweis.
# Statt einzelne Symbole/Strings aus internal/model/activity_profile.go,
# internal/handler/compare_preset.go und internal/router/router.go zu lesen,
# beweist ein echter `go build ./...` dieselben strukturellen Fakten: existierte
# `IsValidProfile`/`ActivityProfile` nicht in internal/model, oder importierte
# ein Go-File noch das geloeschte internal/compare-Paket, schlaegt der Build
# hart fehl (undefined symbol / package does not exist).

def test_go_module_builds_after_dead_code_removal():
    """AC-1/AC-2: Repo kompiliert nach dem Umzug/der Loeschung fehlerfrei.

    Deckt implizit ab: internal/model/activity_profile.go traegt die
    Profil-Symbole (sonst wuerden internal/handler/compare_preset.go und
    internal/router/router.go, die sie referenzieren, nicht kompilieren),
    und kein Go-File importiert das geloeschte internal/compare mehr (sonst
    'package ... is not in std' / 'no required module').
    """
    go_bin = _go_binary()
    if not go_bin:
        pytest.skip("go-Toolchain nicht gefunden (weder PATH noch bekannte Fallback-Pfade)")
    result = subprocess.run(
        [go_bin, "build", "./..."], capture_output=True, text=True, cwd=str(REPO),
    )
    assert result.returncode == 0, (
        f"go build schlaegt fehl (AC-1/AC-2 verletzt):\n{result.stdout}\n{result.stderr}"
    )


# ── AC-2: Go-Löschgut ────────────────────────────────────────────────────────

def test_internal_compare_removed():
    """AC-2: internal/compare/ existiert nicht mehr."""
    assert not (REPO / "internal" / "compare").exists(), (
        "internal/compare/ existiert noch — produktions-tote Engine (#1215 Scheibe 3)"
    )


def test_compare_run_handler_removed():
    """AC-2: compare_run.go + compare_run_test.go sind gelöscht."""
    leftover = [
        f for f in ["compare_run.go", "compare_run_test.go"]
        if (REPO / "internal" / "handler" / f).exists()
    ]
    assert leftover == [], f"Toter Handler noch vorhanden: {leftover} (AC-2)"


# router.go ohne /api/compare/run-Route, ohne CompareEngine-Dep, ohne
# internal/compare-Import (#765: kein Source-Read mehr) sowie der Über-
# Löschungs-Schutz für weatherProvider/compare/presets (AC-4/AC-10) sind beide
# durch test_go_module_builds_after_dead_code_removal (go build) UND die
# umfangreiche e2e-Playwright-Abdeckung von /api/compare/presets abgedeckt
# (u.a. frontend/e2e/compare-editor-slice3.spec.ts, compare-hub-*.spec.ts) —
# "anderswo gedeckt" (#765 DoD).


# ── AC-6/7/8/9: Frontend ────────────────────────────────────────────────────

def test_preset_header_removed():
    """AC-6: PresetHeader.svelte existiert nicht mehr (0 Importer, toter Trigger)."""
    assert not (REPO / "frontend" / "src" / "lib" / "components" / "compare" / "PresetHeader.svelte").exists(), (
        "PresetHeader.svelte existiert noch — einziger UI-Trigger der toten Route (AC-6)"
    )


def test_compare_main_stage_spec_removed():
    """AC-7: compare-main-stage.spec.ts (testet toten Run-Flow) ist gelöscht."""
    assert not (REPO / "frontend" / "e2e" / "compare-main-stage.spec.ts").exists(), (
        "compare-main-stage.spec.ts existiert noch — testet ausschließlich den toten Run-Button-Flow (AC-7)"
    )


def test_content_tests_adjusted():
    """AC-8/AC-9: Dateiinhalt-Tests referenzieren PresetHeader nicht mehr bzw. invertiert."""
    t390 = (REPO / "frontend" / "src" / "lib" / "issue_390_compare_atomic_migration.test.ts")
    assert "PresetHeader" not in t390.read_text(encoding="utf-8"), (
        "issue_390-Test liest noch PresetHeader.svelte (AC-8)"
    )
    t462 = (REPO / "frontend" / "src" / "lib" / "components" / "compare" / "issue_462.test.ts")
    assert "PresetHeader" not in t462.read_text(encoding="utf-8"), (
        "issue_462.test.ts: PresetHeader-Eintrag muss raus (AC-8)"
    )
    guard = (REPO / "frontend" / "src" / "lib" / "components" / "shared" / "__tests__" / "legacy_wizard_removed.test.ts")
    src = guard.read_text(encoding="utf-8")
    assert "PresetHeader-Eintrag entfernt — der gehört zu Scheibe 3!" not in src, (
        "legacy_wizard_removed.test.ts: Scheibe-2-Assertion 'PresetHeader bleibt' "
        "muss mit Scheibe 3 umgedreht sein, sonst bricht der lebende Test (AC-9)"
    )
