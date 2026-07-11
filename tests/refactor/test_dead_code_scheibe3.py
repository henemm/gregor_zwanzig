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
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GO_ROUTER = REPO / "internal" / "router" / "router.go"
GO_MAIN = REPO / "cmd" / "server" / "main.go"
PRESET_HANDLER = REPO / "internal" / "handler" / "compare_preset.go"


# ── AC-1: Umzug der Profil-Validierung nach internal/model ──────────────────

def test_activity_profile_moved_to_model():
    """AC-1: internal/model/activity_profile.go existiert und trägt IsValidProfile."""
    target = REPO / "internal" / "model" / "activity_profile.go"
    assert target.exists(), (
        f"{target} fehlt — ActivityProfile/IsValidProfile müssen vor der "
        f"Löschung von internal/compare/ nach model umziehen (AC-1)"
    )
    src = target.read_text(encoding="utf-8")
    for sym in ["ActivityProfile", "IsValidProfile", "ProfileWintersport",
                "ProfileAlpineTour", "ProfileSummerTrekking", "ProfileAllgemein"]:
        assert sym in src, f"{sym} fehlt in internal/model/activity_profile.go (AC-1)"


def test_preset_handler_uses_model_not_compare():
    """AC-1: Der lebende Preset-CRUD-Handler nutzt model statt internal/compare."""
    src = PRESET_HANDLER.read_text(encoding="utf-8")
    assert "internal/compare" not in src, (
        "compare_preset.go importiert noch internal/compare — muss auf "
        "model.IsValidProfile/model.ActivityProfile umgestellt sein (AC-1)"
    )
    assert "IsValidProfile" in src, (
        "compare_preset.go: Profil-Validierung fehlt komplett — Über-Löschung! "
        "IsValidProfile muss weiter aufgerufen werden (AC-1/AC-5)"
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


def test_router_without_compare_run_route():
    """AC-2: router.go ohne /api/compare/run-Route und ohne CompareEngine-Dep."""
    src = GO_ROUTER.read_text(encoding="utf-8")
    assert "compare/run" not in src, "Route /api/compare/run steht noch in router.go (AC-2)"
    assert "CompareEngine" not in src, "Deps-Feld CompareEngine steht noch in router.go (AC-2)"
    assert "internal/compare" not in src, "router.go importiert noch internal/compare (AC-2)"


def test_no_go_file_imports_internal_compare():
    """AC-2: Kein Go-File im Repo importiert internal/compare mehr."""
    hits = [
        str(p.relative_to(REPO))
        for p in REPO.rglob("*.go")
        if ".git" not in p.parts and "internal/compare" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert hits == [], f"internal/compare wird noch referenziert von: {hits} (AC-2)"


# ── AC-4: Schutz — lebende Go-Nachbarn bleiben ──────────────────────────────

def test_main_go_keeps_weather_provider_and_preset_routes():
    """AC-4/AC-10: weatherProvider bleibt in main.go, Preset-CRUD-Routen bleiben."""
    assert "weatherProvider" in GO_MAIN.read_text(encoding="utf-8"), (
        "weatherProvider aus main.go verschwunden — wird vom lebenden "
        "ForecastHandler gebraucht (AC-4, Über-Löschung!)"
    )
    router_src = GO_ROUTER.read_text(encoding="utf-8")
    assert "compare/presets" in router_src, (
        "Preset-CRUD-Routen fehlen in router.go — Über-Löschung! (AC-10)"
    )


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
