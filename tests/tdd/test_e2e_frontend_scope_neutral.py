"""
TDD RED — Frontend-E2E-Testdateien (`frontend/e2e/**`) neutral klassifizieren (#1197).

Spec: docs/specs/modules/fix_1197_staging_gate_e2e_scope.md (AC-1..AC-6)

Beweist aus Werkzeug-Sicht (echtes Temp-Git-Repo, KEINE subprocess-/git-Mocks):
- Ein Diff, der nur `frontend/e2e/`-Dateien berührt, ist `docs-only` statt
  `frontend-only` (Live-Vorfall 2026-08-15: PR-Stack #1736/#1852/#1881/#1882
  blockierte den Deploy-Gate fälschlich).
- Gemischte Diffs (`frontend/e2e/`+`frontend/src/`, `frontend/e2e/`+Backend,
  `frontend/e2e/`+`docs/`+`tests/`) bleiben korrekt klassifiziert.
- Echter Frontend-Code (`frontend/src/`) ohne `frontend/e2e/`-Anteil bleibt
  unverändert `frontend-only` (Regressionsschutz).
- End-to-End: die Ancestor-Relaxierung in `staging_gate.gate_check` lässt einen
  reinen `frontend/e2e/`-Zuwachs über einem verifizierten Ancestor durch.

Mock-frei: pro Fall ein echtes `git init`-Repo, echte Dateien, echtes
`git add`/`commit`, dann die echte Funktion bzw. der echte Gate gegen dieses
Repo laufen lassen. Direktimport der Hook-Module aus dem AKTUELLEN
Arbeitsverzeichnis (Worktree), nicht aus dem Hauptrepo hartkodiert.
"""
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"

# HOOKS_DIR muss in sys.path[0] liegen, damit staging_gate's internes
# `import _e2e_paths` die Worktree-Version trifft (Konvention aus
# test_scope_tests_neutral.py, Issue #648-Kontaminierungsfalle).
sys.path.insert(0, str(HOOKS_DIR))

_e2e = None
_sg = None


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_modules():
    global _e2e, _sg
    if _e2e is None:
        _e2e = _load_module(HOOKS_DIR / "_e2e_paths.py", "e2e_paths_wt1197_e2e_scope")
    if _sg is None:
        _sg = _load_module(HOOKS_DIR / "staging_gate.py", "staging_gate_wt1197_e2e_scope")


def _git(repo, *args):
    subprocess.run(
        ["git", *args],
        cwd=str(repo), check=True,
        capture_output=True, text=True,
    )


def _init_repo(repo):
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")


def _write(repo, relpath, content="x\n"):
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def _committed_scope(repo, paths):
    """Temp-Repo mit Basis-Commit + Ziel-Commit; ruft die echte
    _detect_scope_from_git_diff() gegen HEAD~1..HEAD auf."""
    _ensure_modules()
    _init_repo(repo)
    _write(repo, "README.md", "base\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-q", "-m", "base")
    for rel in paths:
        _write(repo, rel)
        _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", "change")
    return _e2e._detect_scope_from_git_diff("HEAD~1", "HEAD", repo)


# ---------------------------------------------------------------------------
# AC-1: Diff enthält ausschließlich Dateien unter frontend/e2e/ -> docs-only
# ---------------------------------------------------------------------------

def test_ac1_e2e_only_is_docs_only(tmp_path):
    assert _committed_scope(
        tmp_path,
        ["frontend/e2e/foo.spec.ts", "frontend/e2e/helpers.ts"],
    ) == "docs-only", (
        "Ein Diff, der ausschliesslich frontend/e2e/-Dateien aendert, muss "
        "docs-only liefern (Live-Vorfall 2026-08-15)."
    )


# ---------------------------------------------------------------------------
# AC-2: frontend/e2e/ + frontend/src/ -> weiterhin frontend-only
# ---------------------------------------------------------------------------

def test_ac2_e2e_plus_frontend_src_is_frontend_only(tmp_path):
    assert _committed_scope(
        tmp_path,
        ["frontend/e2e/foo.spec.ts", "frontend/src/routes/+page.svelte"],
    ) == "frontend-only", (
        "Echter Frontend-Code (frontend/src/) darf durch die e2e-Ausnahme "
        "nicht verwaessert werden."
    )


# ---------------------------------------------------------------------------
# AC-3: frontend/e2e/ + Backend-Datei -> weiterhin backend, NICHT full-stack
# ---------------------------------------------------------------------------

def test_ac3_e2e_plus_backend_is_backend_not_full_stack(tmp_path):
    assert _committed_scope(
        tmp_path,
        ["frontend/e2e/foo.spec.ts", "src/app/cli.py"],
    ) == "backend", (
        "frontend/e2e/ + Backend-Code darf NICHT full-stack ergeben, weil "
        "frontend/e2e/ nicht als has_frontend zaehlt."
    )


# ---------------------------------------------------------------------------
# AC-4: frontend/e2e/ + docs/ + tests/ -> docs-only
# ---------------------------------------------------------------------------

def test_ac4_e2e_plus_docs_plus_tests_is_docs_only(tmp_path):
    assert _committed_scope(
        tmp_path,
        ["frontend/e2e/foo.spec.ts", "docs/README.md", "tests/tdd/test_bar.py"],
    ) == "docs-only", (
        "frontend/e2e/ zusammen mit anderen bereits neutralen Pfadklassen "
        "(docs/, tests/) muss docs-only bleiben."
    )


# ---------------------------------------------------------------------------
# AC-6: nur echter Frontend-Code, KEINE frontend/e2e/-Datei -> weiterhin
# frontend-only (Regressionsschutz, Bestandsverhalten unveraendert).
# ---------------------------------------------------------------------------

def test_ac6_frontend_src_only_still_frontend_only_no_regression(tmp_path):
    assert _committed_scope(
        tmp_path,
        ["frontend/src/lib/foo.ts"],
    ) == "frontend-only", (
        "Regressionsschutz: echter Frontend-Code ohne frontend/e2e/-Anteil "
        "muss unveraendert frontend-only bleiben."
    )


# ---------------------------------------------------------------------------
# AC-5: End-to-End -- staging_gate.gate_check Ancestor-Relaxierung laesst
# einen reinen frontend/e2e/-Zuwachs ueber einem verifizierten Ancestor durch.
#
# Reproduziert den Live-Vorfall vom 2026-08-15 im Kleinformat: ein Ancestor-
# Commit ist VERIFIED attestiert, der Zuwachs zum HEAD aendert ausschliesslich
# eine Datei unter frontend/e2e/. Vor dem Fix klassifiziert die Ancestor-Logik
# diesen Zuwachs als frontend-only (Bug) -> kein Relax -> Exit 1. Nach dem Fix
# liefert dieselbe Berechnung docs-only -> Relax -> Exit 0.
#
# Pattern uebernommen aus test_staging_gate_ancestor_scope.py (#1197 Vorgaenger-
# Fix): ehrlicher Location-Seam (_shared_repo_dir/_verified_repo_dir per
# monkeypatch auf das echte tmp-Repo umgebogen), keine Mocks der Git-Logik.
# scope_override="frontend-only" simuliert den (vor diesem Fix) falsch
# berechneten Gesamt-Scope des Deploys, damit der fruehe docs-only-Skip in
# gate_check NICHT vorzeitig greift und der Kontrollfluss verlaesslich in die
# Ancestor-Attestations-Aufloesung fuehrt, deren Zuwachs-Scope (C..HEAD)
# unabhaengig davon real per git berechnet wird.
# ---------------------------------------------------------------------------

def _iso(hours_ago: float = 0.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _write_attestation(shared: Path, sha: str, *, scope: str = "frontend-only") -> None:
    out = shared / ".claude" / "e2e_verified" / f"{sha}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "verified_commit": sha,
                "staging_verdict": "VERIFIED: alles gut",
                "findings": [],
                "verified_at": _iso(),
                "scope": scope,
                "environment": "staging",
            }
        )
    )


def test_ac5_gate_check_ancestor_relaxation_with_e2e_only_increment(tmp_path, monkeypatch):
    _ensure_modules()
    _init_repo(tmp_path)
    _write(tmp_path, "src/app.py", "x = 1\n")
    _write(tmp_path, "frontend/src/main.ts", "// app\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "product (attested)")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(tmp_path),
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    _write(tmp_path, "frontend/e2e/trip-preview-renamed.staging.spec.ts", "// e2e\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "e2e-only increment (renamed spec)")

    _write_attestation(tmp_path, base, scope="frontend-only")
    monkeypatch.setattr(_sg, "_shared_repo_dir", lambda: tmp_path)
    monkeypatch.setattr(_sg, "_verified_repo_dir", lambda: tmp_path)
    monkeypatch.delenv("GZ_SKIP_E2E_GATE", raising=False)

    rc = _sg.gate_check(None, "frontend-only", expected_commit=None)
    assert rc == 0, (
        "Ein reiner frontend/e2e/-Zuwachs ueber einem verifizierten Ancestor "
        "muss die Ancestor-Relaxierung durchlassen (Exit 0) -- reproduziert "
        "den Live-Vorfall vom 2026-08-15."
    )
