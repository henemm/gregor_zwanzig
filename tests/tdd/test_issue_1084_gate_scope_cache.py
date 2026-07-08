"""TDD RED: Gate-Scope-Cache gegen stale Marker (Issue #1084).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen echte
Temp-Git-Repos + echte Subprozess-Aufrufe der echten Hook-Skripte (fuer
staging_gate.py, das cwd-abhaengig ist) bzw. echte Direktimporte der
Hook-Module (fuer prod_selftest.py, dessen Funktionen einen repo_dir-Parameter
akzeptieren). Die Skripte werden aus dem AKTUELLEN Arbeitsverzeichnis
(Worktree) kopiert, nicht aus dem Hauptrepo hartkodiert.

Getestete ACs (docs/specs/modules/issue_1084_gate_scope_cache.md):
  AC-1: gate_check() lief gerade erfolgreich fuer HEAD (Marker+Scope gesetzt)
        -> prod_selftest-Scope-Erkennung direkt danach liefert den gecachten
        Scope, NICHT docs-only.
  AC-2: Cache-Treffer ist am Verhalten nachweisbar (richtiger Scope trotz
        leerem HEAD..HEAD-Diff).
  AC-3: Altes Marker-Format ohne gate_last_scope-Feld -> Fallback auf
        bestehende Diff-Logik, kein Absturz.
  AC-4: Marker-SHA != HEAD (Multi-Commit-Fall aus #916) -> bestehendes
        Diff-Verhalten bleibt korrekt, gecachter (veralteter) Wert wird NICHT
        verwendet.
  AC-5: gate_check() schreibt sowohl den korrekten SHA als auch den
        passenden gate_last_scope-Wert in den Marker.
  AC-6: write_verdict() honoriert einen uebergebenen --scope-Override.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True, text=True)


def _head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _setup_repo(tmp_path: Path) -> Path:
    """Standalone Git-Repo mit eigener .claude/hooks-Kopie (Worktree-sicher)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("staging_gate.py", "prod_selftest.py", "_e2e_paths.py"):
        shutil.copy(_HOOKS_SRC / name, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _run_staging_gate(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py"), *args],
        cwd=repo, capture_output=True, text=True,
    )


def _write_marker(repo: Path, sha: str, scope: str | None = None) -> Path:
    p = repo / ".claude" / "last_gate_scope.json"
    payload = {"gate_scope_sha": sha}
    if scope is not None:
        payload["gate_last_scope"] = scope
    p.write_text(json.dumps(payload))
    return p


def _read_marker(repo: Path) -> dict | None:
    p = repo / ".claude" / "last_gate_scope.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _write_valid_e2e(repo: Path, sha: str, verdict: str = "VERIFIED: alle ACs gruen") -> Path:
    e2e_path = repo / ".claude" / "e2e_verified.json"
    e2e_path.write_text(json.dumps({
        "verified_commit": sha,
        "staging_verdict": verdict,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "environment": "staging",
        "scope": "backend",
        "findings": [],
    }))
    return e2e_path


def _load_prod_selftest(repo: Path, module_name: str):
    """Laedt die REPO-EIGENE Kopie von prod_selftest.py isoliert (eigener
    Modulname pro Aufruf, damit sys.modules-Caching zwischen Test-Repos nicht
    kollidiert)."""
    hooks_dir = repo / ".claude" / "hooks"
    path = hooks_dir / "prod_selftest.py"
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _frontend_commit(repo: Path) -> str:
    (repo / "frontend").mkdir(exist_ok=True)
    (repo / "frontend" / "Step2Orte.svelte").write_text("<!-- frontend change -->\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "frontend change")
    return _head_sha(repo)


# ---------------------------------------------------------------------------
# AC-1 + AC-2: Cache-Hit direkt nach erfolgreichem gate_check() fuer HEAD
# ---------------------------------------------------------------------------

def test_ac1_prod_selftest_uses_cached_scope_not_docs_only(tmp_path):
    """Nach einem erfolgreichen gate_check()-Lauf fuer HEAD (Marker+Scope
    gesetzt) muss prod_selftest's Scope-Erkennung direkt danach den gecachten
    Scope liefern, NICHT docs-only (Kern-Bugreproduktion #1084)."""
    repo = _setup_repo(tmp_path)
    sha = _frontend_commit(repo)
    _write_valid_e2e(repo, sha)

    check = _run_staging_gate(
        repo, "--check", "--scope", "frontend-only",
        "--e2e-path", str(repo / ".claude" / "e2e_verified.json"),
    )
    assert check.returncode == 0, (
        f"Vorbedingung: gate_check() muss erfolgreich sein. "
        f"rc={check.returncode} stdout={check.stdout!r} stderr={check.stderr!r}"
    )

    selftest = _load_prod_selftest(repo, "ac1_prod_selftest")
    scope = selftest._detect_committed_scope(repo)
    assert scope == "frontend-only", (
        f"prod_selftest muss direkt nach einem erfolgreichen gate_check()-Lauf "
        f"fuer denselben HEAD den gecachten Scope 'frontend-only' liefern, "
        f"nicht neu (fehlerhaft als 'docs-only') herleiten. scope={scope!r}"
    )


def test_ac2_cache_hit_overrides_empty_self_diff(tmp_path):
    """Der Marker-SHA == HEAD UND ein gesetztes gate_last_scope beweisen den
    Cache-Pfad: der reine Diff (HEAD..HEAD) waere leer und wuerde docs-only
    liefern -- der Cache muss das verhindern."""
    repo = _setup_repo(tmp_path)
    sha = _head_sha(repo)
    _write_marker(repo, sha, scope="backend")

    selftest = _load_prod_selftest(repo, "ac2_prod_selftest")
    scope = selftest._detect_committed_scope(repo)
    assert scope == "backend", (
        f"Marker-SHA == HEAD mit gesetztem gate_last_scope='backend' muss "
        f"'backend' liefern (Cache-Pfad), nicht 'docs-only' (der reine, "
        f"selbstreferenzielle HEAD..HEAD-Diff waere leer). scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: Altes Marker-Format ohne gate_last_scope -> Fallback, kein Absturz
# ---------------------------------------------------------------------------

def test_ac3_old_marker_format_falls_back_without_crash(tmp_path):
    """Ein Marker im alten Format (nur gate_scope_sha, kein gate_last_scope)
    mit SHA == HEAD darf nicht abstuerzen und muss auf die bestehende
    Diff-Logik zurueckfallen (Vor-Fix-Ergebnis: docs-only, da Diff leer)."""
    repo = _setup_repo(tmp_path)
    sha = _head_sha(repo)
    _write_marker(repo, sha, scope=None)  # altes Format: nur gate_scope_sha

    marker = _read_marker(repo)
    assert "gate_last_scope" not in marker, "Testvoraussetzung: altes Format"

    selftest = _load_prod_selftest(repo, "ac3_prod_selftest")
    scope = selftest._detect_committed_scope(repo)
    assert scope == "docs-only", (
        f"Altes Marker-Format ohne gate_last_scope muss auf die bestehende "
        f"Diff-Logik zurueckfallen (HEAD..HEAD leer -> docs-only), nicht "
        f"abstuerzen. scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-4: Marker zeigt auf aelteren Commit (#916-Multi-Commit-Fall) -> Cache
# greift NICHT, bestehendes (korrektes) Diff-Verhalten bleibt erhalten
# ---------------------------------------------------------------------------

def test_ac4_stale_cached_scope_not_used_when_marker_not_head(tmp_path):
    """Marker zeigt auf Commit A (mit veraltetem gate_last_scope=docs-only).
    Commit B aendert danach Backend-Code, Commit C ist HEAD und aendert nur
    Docs. Der (falsche, veraltete) gecachte Wert darf NICHT verwendet werden
    -- die bestehende Multi-Commit-Diff-Logik (#916, AC-1) muss weiterhin
    over den gesamten Bereich seit dem Marker urteilen und 'backend'
    liefern."""
    repo = _setup_repo(tmp_path)
    sha_a = _head_sha(repo)
    _write_marker(repo, sha_a, scope="docs-only")

    (repo / "src").mkdir()
    (repo / "src" / "foo.py").write_text("# backend change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "backend change")

    (repo / "docs").mkdir()
    (repo / "docs" / "bar.md").write_text("# docs change\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "docs change")

    selftest = _load_prod_selftest(repo, "ac4_prod_selftest")
    scope = selftest._detect_committed_scope(repo)
    assert scope != "docs-only", (
        f"Der veraltete gecachte Scope ('docs-only') aus dem Marker (der auf "
        f"einen AELTEREN Commit zeigt, nicht HEAD) darf NICHT verwendet "
        f"werden. scope={scope!r}"
    )
    assert scope in ("backend", "full-stack"), (
        f"Erwartete 'backend' oder 'full-stack' (Multi-Commit-Diff seit dem "
        f"Marker), bekam scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-5: gate_check() schreibt SHA + passenden Scope korrekt in den Marker
# ---------------------------------------------------------------------------

def test_ac5_gate_check_writes_sha_and_scope(tmp_path):
    """Nach einem erfolgreichen gate_check()-Lauf mit explizitem Scope
    muss der Marker sowohl den korrekten HEAD-SHA als auch den passenden
    gate_last_scope-Wert enthalten."""
    repo = _setup_repo(tmp_path)
    sha = _frontend_commit(repo)
    _write_valid_e2e(repo, sha)

    res = _run_staging_gate(
        repo, "--check", "--scope", "frontend-only",
        "--e2e-path", str(repo / ".claude" / "e2e_verified.json"),
    )
    assert res.returncode == 0, f"gate_check() muss Exit 0 liefern: {res.stderr!r}"

    marker = _read_marker(repo)
    assert marker is not None, "Marker-Datei muss nach erfolgreichem Lauf existieren."
    assert marker.get("gate_scope_sha") == sha, (
        f"Marker muss den aktuellen HEAD-SHA enthalten. marker={marker!r}"
    )
    assert marker.get("gate_last_scope") == "frontend-only", (
        f"Marker muss den tatsaechlich verwendeten Scope-Wert enthalten. "
        f"marker={marker!r}"
    )


def test_ac5_gate_check_writes_scope_on_docs_only_skip(tmp_path):
    """Auch der docs-only-Skip-Pfad (Zeile 285) muss gate_last_scope='docs-only'
    mitschreiben."""
    repo = _setup_repo(tmp_path)
    sha = _head_sha(repo)

    res = _run_staging_gate(repo, "--check", "--scope", "docs-only")
    assert res.returncode == 0, f"docs-only-Skip muss Exit 0 liefern: {res.stderr!r}"

    marker = _read_marker(repo)
    assert marker is not None
    assert marker.get("gate_scope_sha") == sha
    assert marker.get("gate_last_scope") == "docs-only", (
        f"Marker muss auch im docs-only-Skip-Pfad gate_last_scope enthalten. "
        f"marker={marker!r}"
    )


# ---------------------------------------------------------------------------
# AC-6: write_verdict() honoriert einen expliziten --scope-Override
# ---------------------------------------------------------------------------

def test_ac6_write_verdict_honors_scope_override(tmp_path):
    """Ein per --scope uebergebener Override muss ins scope-Feld der
    Attestation geschrieben werden, nicht das Ergebnis von
    _detect_committed_scope() (das hier 'docs-only' liefern wuerde, da
    keine Datei-Aenderung committet wurde)."""
    repo = _setup_repo(tmp_path)
    findings_path = repo / "findings.json"
    findings_path.write_text("[]")
    e2e_path = repo / ".claude" / "e2e_verified.json"

    res = _run_staging_gate(
        repo, "--write-verdict", "VERIFIED: alle ACs gruen",
        "--findings-json", str(findings_path),
        "--e2e-path", str(e2e_path),
        "--scope", "frontend-only",
    )
    assert res.returncode == 0, f"write_verdict() muss Exit 0 liefern: {res.stderr!r}"

    written = json.loads(e2e_path.read_text())
    assert written.get("scope") == "frontend-only", (
        f"write_verdict() muss den expliziten --scope-Override ('frontend-only') "
        f"honorieren statt _detect_committed_scope() ('docs-only' fuer diesen "
        f"Commit-Zustand ohne Datei-Aenderung) zu verwenden. "
        f"written={written!r}"
    )
