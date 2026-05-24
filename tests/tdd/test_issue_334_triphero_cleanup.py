"""
TDD RED: Issue #334 — Cleanup: TripHero.svelte (toter Code entfernen)

Verifiziert, dass die seit dem Trip-Detail-Redesign (#302) nicht mehr
gerenderte Komponente ``TripHero`` samt Begleit-Code entfernt ist — und
dass der noch aktiv von ``TripHeader.svelte`` genutzte Code (Util-Funktionen
``getDaysLabel`` + ``formatDateRange``) NICHT mit-entfernt wurde.

Wichtige Namens-Unterscheidung (case-sensitiv!):
- ``TripHero``  = die zu entfernende Svelte-Komponente (großes T, großes H, ...o)
- ``tripHero``  = das überlebende Util-Modul ``$lib/utils/tripHero`` (kleines t)
  → wird von ``TripHeader.svelte`` importiert und MUSS bleiben.

Spec: docs/specs/modules/issue_334_triphero_cleanup.md
Test-Manifest: docs/specs/tests/issue_334_triphero_cleanup_tests.md
"""
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]

TRIPHERO_SVELTE = ROOT / "frontend/src/lib/components/trip-detail/TripHero.svelte"
BARREL_INDEX = ROOT / "frontend/src/lib/components/trip-detail/index.ts"
HERO_E2E_SPEC = ROOT / "frontend/e2e/trip-detail-hero.spec.ts"
TRIPHERO_UTILS = ROOT / "frontend/src/lib/utils/tripHero.ts"
TRIPHERO_UTILS_TEST = ROOT / "frontend/src/lib/utils/tripHero.test.ts"

FRONTEND_SRC = ROOT / "frontend/src"
FRONTEND_E2E = ROOT / "frontend/e2e"

# Komponenten-Bezeichner case-sensitiv mit Wortgrenze. Matcht "TripHero"
# (Komponente) aber NICHT "tripHero" (Util-Pfad) und NICHT "TripHeader".
COMPONENT_RE = re.compile(r"\bTripHero\b")

ORPHAN_FUNCS_RE = re.compile(r"\b(getActiveStageDisplay|getNextBriefing|parseHHMM|compareHHMM)\b")


def _grep_dir(base: Path, pattern: re.Pattern, exts=(".ts", ".svelte", ".js")) -> list[str]:
    """Sucht ``pattern`` in allen Quelldateien unter ``base`` (ohne node_modules)."""
    hits: list[str] = []
    if not base.exists():
        return hits
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix not in exts:
            continue
        if "node_modules" in path.parts:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                rel = path.relative_to(ROOT)
                hits.append(f"{rel}:{i}: {line.strip()}")
    return hits


# --- AC-1: tote Komponenten-Datei entfernt -------------------------------

def test_ac1_triphero_svelte_file_removed():
    """
    GIVEN: das Repository nach dem Cleanup
    WHEN:  auf TripHero.svelte geprüft wird
    THEN:  die Datei existiert nicht mehr
    """
    assert not TRIPHERO_SVELTE.exists(), (
        f"TripHero.svelte existiert noch: {TRIPHERO_SVELTE.relative_to(ROOT)}"
    )


# --- AC-2: Barrel-Re-Export entfernt -------------------------------------

def test_ac2_barrel_reexport_removed():
    """
    GIVEN: index.ts des trip-detail-Barrels
    WHEN:  nach dem Komponenten-Bezeichner TripHero gegrept wird
    THEN:  0 Treffer (Re-Export entfernt)
    """
    hits = [
        f"Z.{i}: {line.strip()}"
        for i, line in enumerate(BARREL_INDEX.read_text(encoding="utf-8").splitlines(), 1)
        if COMPONENT_RE.search(line)
    ]
    assert hits == [], "TripHero wird in index.ts noch re-exportiert:\n" + "\n".join(hits)


# --- AC-3: kein Import/Tag/Re-Export irgendwo im Frontend ----------------

def test_ac3_no_triphero_reference_anywhere_in_frontend():
    """
    GIVEN: das gesamte frontend/src + frontend/e2e
    WHEN:  nach dem Komponenten-Bezeichner TripHero (case-sensitiv) gegrept wird
    THEN:  0 Treffer (kein Import, kein <TripHero>-Tag, kein Re-Export)
    """
    hits = _grep_dir(FRONTEND_SRC, COMPONENT_RE) + _grep_dir(FRONTEND_E2E, COMPONENT_RE)
    assert hits == [], (
        f"Noch {len(hits)} TripHero-Referenz(en) im Frontend:\n" + "\n".join(hits)
    )


# --- AC-4: toter E2E-Test entfernt ---------------------------------------

def test_ac4_dead_e2e_spec_removed():
    """
    GIVEN: das Repository nach dem Cleanup
    WHEN:  auf trip-detail-hero.spec.ts geprüft wird
    THEN:  die Datei existiert nicht mehr (testete nicht mehr existente trip-hero-TestIDs)
    """
    assert not HERO_E2E_SPEC.exists(), (
        f"Toter E2E-Test existiert noch: {HERO_E2E_SPEC.relative_to(ROOT)}"
    )


# --- AC-5: verwaiste Util-Funktionen entfernt ----------------------------

def test_ac5_orphan_util_functions_removed():
    """
    GIVEN: tripHero.ts nach dem Cleanup
    WHEN:  nach getActiveStageDisplay / getNextBriefing / parseHHMM / compareHHMM gegrept wird
    THEN:  0 Treffer (nur von der entfernten Komponente genutzte Funktionen + private Helfer weg)
    """
    hits = [
        f"Z.{i}: {line.strip()}"
        for i, line in enumerate(TRIPHERO_UTILS.read_text(encoding="utf-8").splitlines(), 1)
        if ORPHAN_FUNCS_RE.search(line)
    ]
    assert hits == [], "Verwaiste Funktionen noch in tripHero.ts:\n" + "\n".join(hits)


# --- AC-6: überlebende Util-Funktionen unangetastet (Über-Lösch-Guard) ---

def test_ac6_surviving_util_functions_intact():
    """
    GIVEN: tripHero.ts nach dem Cleanup
    WHEN:  nach den von TripHeader.svelte genutzten Exporten gegrept wird
    THEN:  getDaysLabel und formatDateRange existieren weiterhin (je genau 1 export)
    """
    content = TRIPHERO_UTILS.read_text(encoding="utf-8")
    assert len(re.findall(r"export function getDaysLabel\b", content)) == 1, (
        "getDaysLabel fehlt oder ist mehrfach — wird von TripHeader.svelte gebraucht!"
    )
    assert len(re.findall(r"export function formatDateRange\b", content)) == 1, (
        "formatDateRange fehlt oder ist mehrfach — wird von TripHeader.svelte gebraucht!"
    )


# --- AC-7: tote Tests entfernt, überlebende Tests intakt -----------------

def test_ac7_orphan_tests_removed_survivors_intact():
    """
    GIVEN: tripHero.test.ts nach dem Cleanup
    WHEN:  nach Referenzen auf die verwaisten Funktionen gegrept wird
    THEN:  0 Treffer; getDaysLabel- und formatDateRange-Tests sind weiterhin vorhanden
    """
    content = TRIPHERO_UTILS_TEST.read_text(encoding="utf-8")
    orphan_hits = [
        f"Z.{i}: {line.strip()}"
        for i, line in enumerate(content.splitlines(), 1)
        if re.search(r"\b(getActiveStageDisplay|getNextBriefing)\b", line)
    ]
    assert orphan_hits == [], (
        "tripHero.test.ts referenziert noch verwaiste Funktionen:\n" + "\n".join(orphan_hits)
    )
    assert "getDaysLabel" in content, "getDaysLabel-Tests fehlen — überlebende Tests dürfen NICHT entfernt werden!"
    assert "formatDateRange" in content, "formatDateRange-Tests fehlen — überlebende Tests dürfen NICHT entfernt werden!"
