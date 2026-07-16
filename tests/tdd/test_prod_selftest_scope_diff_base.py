"""TDD RED: prod_selftest.py's Diff-Basis ignoriert `previous_commit` im
Deploy-Marker -- ein reiner Doku-Commit obenauf auf einem Code-Commit wird
faelschlich als docs-only uebersprungen (Issue #1283, Fix-Workflow
fix-1282-1283-gate-honesty).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen echte
Temp-Git-Repos + echte Direktimporte der REPO-EIGENEN Kopie von
prod_selftest.py (dessen Funktionen einen repo_dir-Parameter akzeptieren).
Vorbild fast 1:1: tests/tdd/test_issue_1084_gate_scope_cache.py.

Getestete ACs (docs/specs/modules/gate_honesty_mail_selftest.md):
  AC-7: last_prod_deploy.json enthaelt previous_commit, ist != HEAD und via
        `git cat-file -e` aufloesbar -> _scope_diff_base nutzt previous_commit
        mit HOECHSTER Prioritaet als Diff-Basis.
  AC-8: Regressionsmatrix ueber 5 Szenarien: (a) stacked-docs-on-code,
        (b) normaler Ein-Code-Commit, (c) echter docs-only-Deploy,
        (d) No-op-Re-Deploy (previous_commit==HEAD), (e) Erst-Deploy ohne
        Marker/ohne previous_commit-Feld.
  AC-9: previous_commit abwesend oder unaufloesbar -> NIEMALS faelschlich
        docs-only; die bestehende Fail-closed-Fallback-Kette (#1121) bleibt
        unveraendert intakt.

Aktuell (rot, Szenario a): last_prod_deploy.json hat nur `deployed_commit`
(== HEAD, da der Marker unmittelbar nach DIESEM Deploy geschrieben wurde) --
`_scope_diff_base` ueberspringt ihn deshalb (deployed_commit == head-Guard)
und faellt auf `HEAD~1` zurueck. Liegt zwischen dem letzten Deploy und HEAD
mehr als ein Commit (Code-Commit + obenauf ein Doku-Commit), sieht `HEAD~1`
nur noch den letzten (Doku-)Commit -> faelschlich "docs-only" statt des
tatsaechlich seit dem letzten Deploy ausgerollten Bereichs.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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
    for name in ("prod_selftest.py", "_e2e_paths.py"):
        shutil.copy(_HOOKS_SRC / name, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _commit_file(repo: Path, relpath: str, content: str, message: str) -> str:
    p = repo / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _head_sha(repo)


def _write_prod_deploy_marker(repo: Path, *, deployed_commit: str | None = None,
                               previous_commit: str | None = None) -> Path:
    payload: dict = {}
    if deployed_commit is not None:
        payload["deployed_commit"] = deployed_commit
    if previous_commit is not None:
        payload["previous_commit"] = previous_commit
    p = repo / ".claude" / "last_prod_deploy.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload))
    return p


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


# ---------------------------------------------------------------------------
# AC-7 + AC-8(a): stacked-docs-on-code -- der Kern-Bugreproduktionsfall
# ---------------------------------------------------------------------------

def test_scenario_a_stacked_docs_on_code_uses_previous_commit_as_diff_base(tmp_path):
    """AC-7: previous_commit ist != HEAD und aufloesbar -> muss mit hoechster
    Prioritaet als Diff-Basis genutzt werden, auch wenn obenauf ein reiner
    Doku-Commit liegt. Scope-Ergebnis darf NICHT docs-only sein."""
    repo = _setup_repo(tmp_path)
    commit0 = _head_sha(repo)  # Stand vor diesem Deploy (previous_commit)
    _commit_file(repo, "src/foo.py", "# code change\n", "code change")
    commit_c = _commit_file(repo, "docs/bar.md", "# docs change\n", "docs change")

    _write_prod_deploy_marker(repo, deployed_commit=commit_c, previous_commit=commit0)

    selftest = _load_prod_selftest(repo, "scenario_a")
    base = selftest._scope_diff_base(repo)
    assert base == commit0, (
        f"AC-7: _scope_diff_base muss previous_commit ({commit0!r}) als "
        f"Diff-Basis liefern (hoechste Prioritaet). Aktuell (rot) liefert es "
        f"HEAD~1 (den unmittelbaren Vorgaenger-Commit, der nur den Doku-"
        f"Commit sieht). base={base!r}"
    )

    scope = selftest._detect_committed_scope(repo)
    assert scope != "docs-only", (
        f"AC-7: der gesamte seit dem letzten Prod-Deploy ausgerollte Bereich "
        f"(Code-Commit + Doku-Commit) muss erkannt werden, nicht nur der "
        f"oberste (Doku-)Commit. Aktuell (rot) liefert dies faelschlich "
        f"'docs-only'. scope={scope!r}"
    )
    assert scope in ("backend", "full-stack"), (
        f"Erwartete 'backend' oder 'full-stack' (src/foo.py ist Backend-Code), "
        f"bekam scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-8(b): normaler Ein-Code-Commit -> Selftest laeuft (nicht docs-only)
# ---------------------------------------------------------------------------

def test_scenario_b_normal_single_code_commit_scope_is_backend(tmp_path):
    repo = _setup_repo(tmp_path)
    commit0 = _head_sha(repo)
    commit_b = _commit_file(repo, "src/foo.py", "# code change\n", "code change")

    _write_prod_deploy_marker(repo, deployed_commit=commit_b, previous_commit=commit0)

    selftest = _load_prod_selftest(repo, "scenario_b")
    scope = selftest._detect_committed_scope(repo)
    assert scope == "backend", (
        f"AC-8(b): ein normaler Ein-Code-Commit-Deploy muss 'backend' "
        f"liefern (Selftest laeuft). scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-8(c): echter docs-only-Deploy -> uebersprungen
# ---------------------------------------------------------------------------

def test_scenario_c_real_docs_only_deploy_scope_is_docs_only(tmp_path):
    repo = _setup_repo(tmp_path)
    commit0 = _head_sha(repo)
    commit_b = _commit_file(repo, "docs/bar.md", "# docs change\n", "docs change")

    _write_prod_deploy_marker(repo, deployed_commit=commit_b, previous_commit=commit0)

    selftest = _load_prod_selftest(repo, "scenario_c")
    scope = selftest._detect_committed_scope(repo)
    assert scope == "docs-only", (
        f"AC-8(c): ein echter docs-only-Deploy (nur docs/-Aenderung seit dem "
        f"letzten Deploy) muss weiterhin 'docs-only' liefern (Selftest "
        f"uebersprungen). scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-8(d): No-op-Re-Deploy (previous_commit == HEAD) -> faellt sicher durch
# ---------------------------------------------------------------------------

def test_scenario_d_noop_redeploy_previous_commit_equals_head_falls_through_safely(tmp_path):
    """previous_commit == HEAD (Re-Deploy ohne neue Commits, LOCAL==NEW) darf
    NIEMALS als Diff-Basis benutzt werden (selbstreferenzieller leerer
    HEAD..HEAD-Diff waere faelschlich docs-only). Muss stattdessen sicher
    auf die bestehende Kette zurueckfallen (hier: Ein-Commit-Repo, HEAD~1
    nicht aufloesbar -> fail-closed 'backend', #1121)."""
    repo = _setup_repo(tmp_path)
    head = _head_sha(repo)
    _write_prod_deploy_marker(repo, deployed_commit=head, previous_commit=head)

    selftest = _load_prod_selftest(repo, "scenario_d")
    base = selftest._scope_diff_base(repo)
    assert base != head, (
        f"AC-8(d): previous_commit==HEAD darf NICHT als Diff-Basis verwendet "
        f"werden (waere ein leerer Selbst-Diff). base={base!r} head={head!r}"
    )

    scope = selftest._detect_committed_scope(repo)
    assert scope == "backend", (
        f"AC-8(d): No-op-Re-Deploy muss fail-closed 'backend' liefern (Ein-"
        f"Commit-Repo, HEAD~1 nicht aufloesbar), NIEMALS faelschlich "
        f"'docs-only' durch einen leeren Selbst-Diff. scope={scope!r}"
    )


# ---------------------------------------------------------------------------
# AC-8(e) + AC-9: Erst-Deploy ohne Marker -> Rueckwaertskompatibler Fallback
# ---------------------------------------------------------------------------

def test_scenario_e_first_deploy_no_marker_falls_back_to_head_tilde1(tmp_path):
    """Kein last_prod_deploy.json vorhanden (Erst-Deploy) -> bestehender
    HEAD~1-Fallback greift unveraendert."""
    repo = _setup_repo(tmp_path)
    _commit_file(repo, "src/foo.py", "# code change\n", "code change")
    # bewusst KEIN last_prod_deploy.json geschrieben.

    selftest = _load_prod_selftest(repo, "scenario_e_no_marker")
    base = selftest._scope_diff_base(repo)
    assert base == "HEAD~1", (
        f"AC-9: fehlt der Marker komplett (Erst-Deploy), muss der bestehende "
        f"HEAD~1-Fallback unveraendert greifen (Rueckwaertskompatibilitaet). "
        f"base={base!r}"
    )
    scope = selftest._detect_committed_scope(repo)
    assert scope == "backend"


def test_scenario_e_old_marker_without_previous_commit_field_falls_back(tmp_path):
    """AC-9: altes Marker-Format (nur deployed_commit, kein previous_commit-
    Feld) -> identisches Verhalten wie vor diesem Fix (Rueckwaertskompatibel).
    """
    repo = _setup_repo(tmp_path)
    _commit_file(repo, "src/foo.py", "# code change\n", "code change")
    head = _head_sha(repo)
    _write_prod_deploy_marker(repo, deployed_commit=head)  # kein previous_commit

    marker = json.loads((repo / ".claude" / "last_prod_deploy.json").read_text())
    assert "previous_commit" not in marker, "Testvoraussetzung: altes Marker-Format"

    selftest = _load_prod_selftest(repo, "scenario_e_old_marker")
    scope = selftest._detect_committed_scope(repo)
    assert scope == "backend", (
        f"AC-9: altes Marker-Format ohne previous_commit-Feld darf sich "
        f"nicht anders verhalten als vor diesem Fix -- bestehende "
        f"Fallback-Kette (deployed_commit==HEAD -> Gate-Marker -> HEAD~1) "
        f"bleibt intakt. scope={scope!r}"
    )


def test_scenario_e_previous_commit_unresolvable_falls_back_fail_closed(tmp_path):
    """AC-9: previous_commit zeigt auf einen NICHT existierenden SHA -> darf
    NIE als Diff-Basis verwendet werden (git cat-file -e schlaegt fehl).
    Fallback greift (Ein-Commit-Repo -> HEAD~1 unaufloesbar -> fail-closed
    'backend', niemals faelschlich 'docs-only')."""
    repo = _setup_repo(tmp_path)
    head = _head_sha(repo)
    garbage_sha = "0" * 40
    _write_prod_deploy_marker(repo, deployed_commit=head, previous_commit=garbage_sha)

    selftest = _load_prod_selftest(repo, "scenario_e_unresolvable")
    scope = selftest._detect_committed_scope(repo)
    assert scope == "backend", (
        f"AC-9: ein unaufloesbarer previous_commit darf NICHT verwendet "
        f"werden; Fallback muss fail-closed 'backend' liefern. scope={scope!r}"
    )
