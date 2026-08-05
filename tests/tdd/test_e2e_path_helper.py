"""
TDD RED: E2E-Pfad-Logik konsolidieren + härten (Issue #665).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen die echten Hooks,
das echte gemeinsame Modul `_e2e_paths`, ein echtes temporäres Git-Repo und echte
Dateien. `REPO_DIR`/`CANONICAL_E2E_PATH` werden per monkeypatch auf das Temp-Repo
umgebogen — das ist KEIN Mock, sondern ein realer Pfad auf ein echtes Git-Repo.

Getestete ACs (siehe docs/specs/modules/issue_665_e2e_path_helper.md):
  AC-1: staging_gate und prod_selftest lösen für denselben HEAD DENSELBEN Pfad auf
        (getaggt / nur-Singleton / keine-Datei)
  AC-2: head_sha() liefert bei git-Fehler "UNKNOWN" (nie ""), in beiden Hooks gleich
  AC-3: commit_e2e_path() mit leerem/None-SHA endet auf UNKNOWN.json, nie auf .json
  AC-5: Pfad-Logik nur noch im gemeinsamen Modul (doc-compliance)

In der RED-Phase fehlt `.claude/hooks/_e2e_paths.py` und die Hooks importieren es
nicht → die Tests scheitern (FileNotFoundError beim Modul-Load, Asymmetrie ""
vs "UNKNOWN", kaputter .json-Name, fehlender Import).
"""

import importlib.util
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
STAGING_GATE = HOOKS_DIR / "staging_gate.py"
PROD_SELFTEST = HOOKS_DIR / "prod_selftest.py"
E2E_PATHS = HOOKS_DIR / "_e2e_paths.py"
# sys.path-Einfügung zentral in tests/tdd/conftest.py — nicht hier.


def _load_module(path: Path, name: str):
    """Lädt ein Modul (echte Funktionen, keine Mocks). Raised wenn Datei fehlt."""
    if not path.exists():
        raise FileNotFoundError(f"{path} existiert nicht (RED erwartet)")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(args, cwd):
    return subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))


def _init_repo(root: Path) -> str:
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(parents=True, exist_ok=True)
    (root / "src" / "x.py").write_text("a = 1\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "c1"], root)
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    head = _init_repo(root)
    return root, head


def _patch_paths(monkeypatch, mod, root: Path):
    monkeypatch.setattr(mod, "REPO_DIR", root)
    # Fix #1382: CANONICAL_E2E_PATH entfällt aus beiden Hooks (kein Rückfall
    # auf die alte Sammeldatei mehr). raising=False haelt diesen Patch als
    # reines Sicherheitsnetz weiterhin gueltig, auch wenn das Attribut nicht
    # mehr existiert (kein AttributeError in der GREEN-Phase).
    monkeypatch.setattr(
        mod, "CANONICAL_E2E_PATH", root / ".claude" / "e2e_verified.json", raising=False
    )


def _both_hooks():
    return (
        _load_module(STAGING_GATE, "staging_gate"),
        _load_module(PROD_SELFTEST, "prod_selftest"),
    )


# ---------------------------------------------------------------------------
# AC-1: Beide Hooks lösen denselben Default-Pfad auf
# ---------------------------------------------------------------------------
class TestCrossHookConsistency:
    def _resolve_both(self, monkeypatch, root):
        sg, ps = _both_hooks()
        _patch_paths(monkeypatch, sg, root)
        _patch_paths(monkeypatch, ps, root)
        return sg._commit_e2e_path(), ps._commit_e2e_path()

    def test_tagged_file_exists_same_path(self, monkeypatch, repo):
        root, head = repo
        tagged = root / ".claude" / "e2e_verified" / f"{head}.json"
        tagged.parent.mkdir(parents=True, exist_ok=True)
        tagged.write_text("{}")
        a, b = self._resolve_both(monkeypatch, root)
        assert a == b == tagged

    def test_singleton_only_evidence_is_ignored_uses_tagged_path(self, monkeypatch, repo):
        """Fix #1382: der Rückfall auf die alte Sammeldatei entfällt ersatzlos.
        Existiert NUR die Singleton-Datei (kein commit-getaggter Nachweis),
        lösen beide Hooks weiterhin denselben, aber NICHT-EXISTENTEN
        commit-getaggten Pfad auf — die Singleton-Datei wird nie mehr
        gelesen (vorher: test_only_singleton_same_path, erwartete den
        Fallback auf singleton)."""
        root, head = repo
        singleton = root / ".claude" / "e2e_verified.json"
        singleton.write_text("{}")
        a, b = self._resolve_both(monkeypatch, root)
        tagged = root / ".claude" / "e2e_verified" / f"{head}.json"
        assert a == b == tagged
        assert a != singleton

    def test_no_file_same_path(self, monkeypatch, repo):
        root, head = repo
        a, b = self._resolve_both(monkeypatch, root)
        # Beide fallen auf den (nicht existenten) getaggten Pfad zurück — identisch.
        assert a == b == root / ".claude" / "e2e_verified" / f"{head}.json"


# ---------------------------------------------------------------------------
# AC-2: head_sha() bei git-Fehler → "UNKNOWN", in beiden Hooks gleich
# ---------------------------------------------------------------------------
class TestHeadShaHardening:
    def test_module_returns_unknown_without_git(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        nogit = tmp_path / "nogit"
        nogit.mkdir()
        assert mod.head_sha(nogit) == "UNKNOWN"

    def test_both_hooks_symmetric_unknown(self, monkeypatch, tmp_path):
        nogit = tmp_path / "nogit"
        nogit.mkdir()
        sg, ps = _both_hooks()
        monkeypatch.setattr(sg, "REPO_DIR", nogit)
        monkeypatch.setattr(ps, "REPO_DIR", nogit)
        # Kern des #665-Befunds: KEINE Asymmetrie "" vs "UNKNOWN" mehr.
        assert sg._head_sha() == ps._head_sha() == "UNKNOWN"


# ---------------------------------------------------------------------------
# AC-3: commit_e2e_path() gegen leeren/None-SHA gehärtet
# ---------------------------------------------------------------------------
class TestCommitPathHardening:
    def test_empty_sha_yields_unknown_json(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        p = mod.commit_e2e_path(tmp_path, "")
        assert p.name == "UNKNOWN.json"

    def test_none_sha_yields_unknown_json(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        p = mod.commit_e2e_path(tmp_path, None)
        assert p.name == "UNKNOWN.json"

    def test_valid_sha_preserved(self, tmp_path):
        mod = _load_module(E2E_PATHS, "_e2e_paths")
        p = mod.commit_e2e_path(tmp_path, "abc123")
        assert p.name == "abc123.json"


# ---------------------------------------------------------------------------
# AC-5 / AC-7 (#1307 Scheibe B): Delegation wird an ihrer WIRKUNG geprüft.
#
# Der frühere Test dieser Klasse suchte per `assert "rev-parse" not in src` im
# Quelltext beider Hooks. Das war eine Formprüfung: durch `"rev-" + "parse"`
# trivial umgehbar, blind für vier weitere direkte git-Aufrufe und zugleich
# ein Fehlalarm auf `staging_gate.py:400` (eine legitime, bewusst
# eigenständige Zeile). Ersetzt durch einen Delegations-Zähler gegen ein
# echtes Temp-Repo.
#
# Messprinzip (kein Mock): ein echtes `git`-Ersatzskript im Suchpfad zählt die
# tatsächlich ausgeführten Subprozesse; parallel zählt ein Wrapper um die
# gemeinsame Funktion, wie viele davon INNERHALB eines Aufrufs dieser Funktion
# passierten. Die echte Funktion läuft dabei unverändert weiter. Was übrig
# bleibt (`outside`), lief an der gemeinsamen Stelle vorbei.
# ---------------------------------------------------------------------------

_SHIM = """#!/usr/bin/env bash
if [ "$1" = "cat-file" ] && [ "$2" = "-e" ]; then printf x >> "{catfile}"; fi
if [ "$1" = "diff" ] && [ "$2" = "--name-only" ]; then printf x >> "{diff}"; fi
if [ "$1" = "merge-base" ] && [ "$2" = "--is-ancestor" ]; then printf x >> "{mergebase}"; fi
if [ "$1" = "rev-parse" ] && [ "$2" = "--verify" ]; then printf x >> "{revverify}"; fi
exec "{real_git}" "$@"
"""


def _count(path: Path) -> int:
    return len(path.read_text()) if path.exists() else 0


class _GitProbe:
    """Zählt echte git-Subprozesse (PATH-Shim) je Kommando-Art."""

    def __init__(self, tmp_path: Path, monkeypatch):
        self.catfile = tmp_path / "n_catfile"
        self.diff = tmp_path / "n_diff"
        self.mergebase = tmp_path / "n_mergebase"
        self.revverify = tmp_path / "n_revverify"
        real_git = shutil.which("git")
        assert real_git, "echtes git nicht auf PATH"
        shim_dir = tmp_path / "bin"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "git"
        shim.write_text(
            _SHIM.format(
                catfile=self.catfile, diff=self.diff, mergebase=self.mergebase,
                revverify=self.revverify, real_git=real_git,
            )
        )
        shim.chmod(0o755)
        monkeypatch.setenv("PATH", f"{shim_dir}:{os.environ['PATH']}")

    def reset(self) -> None:
        for p in (self.catfile, self.diff, self.mergebase, self.revverify):
            p.unlink(missing_ok=True)


class _Delegation:
    """Wrapper um eine gemeinsame Funktion: zählt Aufrufe UND die dabei
    ausgelösten Subprozesse. Die echte Funktion bleibt aktiv (kein Mock,
    kein verändertes Verhalten)."""

    def __init__(self, counter: Path):
        self.counter = counter
        self.calls = 0
        self.inside = 0

    def wrap(self, module, attr: str) -> None:
        orig = getattr(module, attr)

        def wrapped(*args, **kwargs):
            before = _count(self.counter)
            try:
                return orig(*args, **kwargs)
            finally:
                self.calls += 1
                self.inside += _count(self.counter) - before

        setattr(module, attr, wrapped)

    @property
    def outside(self) -> int:
        return _count(self.counter) - self.inside


def _init_repo_two_commits(root: Path) -> "tuple[str, str]":
    """Echtes Repo mit zwei Commits — HEAD~1 muss auflösbar sein."""
    _init_repo(root)
    (root / "src" / "y.py").write_text("b = 2\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "c2"], root)
    head = _git(["rev-parse", "HEAD"], root).stdout.strip()
    prev = _git(["rev-parse", "HEAD~1"], root).stdout.strip()
    return head, prev


class TestSharedGitDelegation:
    def test_commit_existence_checks_go_through_shared_module(self, monkeypatch, tmp_path):
        """AC-5: Jede Prüfung 'existiert dieser Commit?' in staging_gate UND
        prod_selftest läuft über `_e2e_paths.commit_exists()`.

        RED heute: die gemeinsame Funktion existiert noch nicht; beide Hooks
        setzen fünfmal ein eigenes `git cat-file -e` ab.
        """
        root = tmp_path / "repo"
        root.mkdir()
        head, prev = _init_repo_two_commits(root)

        sg, ps = _both_hooks()
        _patch_paths(monkeypatch, sg, root)
        _patch_paths(monkeypatch, ps, root)
        monkeypatch.setattr(ps, "REPO_DIR", root)

        for mod, name in ((sg, "staging_gate"), (ps, "prod_selftest")):
            assert hasattr(mod._e2e_paths, "commit_exists"), (
                f"{name}: die gemeinsame Stelle _e2e_paths.commit_exists(sha, repo_dir) "
                "fehlt — Commit-Existenzprüfungen sind noch je Hook dupliziert "
                "(staging_gate.py:139/:148, prod_selftest.py:620/:629/:638)"
            )

        probe = _GitProbe(tmp_path, monkeypatch)
        deleg = _Delegation(probe.catfile)
        deleg.wrap(sg._e2e_paths, "commit_exists")
        deleg.wrap(ps._e2e_paths, "commit_exists")

        marker = root / ".claude" / "last_gate_scope.json"
        preflight = root / ".claude" / "last_preflight_base.json"
        prod_deploy = root / ".claude" / "last_prod_deploy.json"

        # (1) staging_gate: hinterlegte Preflight-Basis
        sg._e2e_paths.write_preflight_base(root, head, prev)
        sg._scope_diff_base()
        preflight.unlink(missing_ok=True)

        # (2) staging_gate: Gate-Marker
        sg._e2e_paths.write_last_gate_scope(root, prev)
        sg._scope_diff_base()

        # (3) prod_selftest: previous_commit aus last_prod_deploy.json
        prod_deploy.write_text(json.dumps({"previous_commit": prev}))
        ps._scope_diff_base(root)

        # (4) prod_selftest: deployed_commit
        prod_deploy.write_text(json.dumps({"deployed_commit": prev}))
        ps._scope_diff_base(root)

        # (5) prod_selftest: Gate-Marker
        prod_deploy.unlink(missing_ok=True)
        ps._scope_diff_base(root)

        assert marker.exists(), "Marker-Datei muss für (2)/(5) wirksam sein"
        assert deleg.calls >= 5, (
            f"Nur {deleg.calls} Aufruf(e) der gemeinsamen Stelle beobachtet — der "
            "Ablauf hat gar nicht geprüft, ob ein Commit existiert (der Test misst nichts)"
        )
        assert deleg.outside == 0, (
            f"{deleg.outside} Commit-Existenzprüfung(en) liefen als direkter "
            "git-Subprozess an _e2e_paths.commit_exists() vorbei"
        )

    def test_file_diff_lookups_go_through_shared_module(self, monkeypatch, tmp_path):
        """AC-5: Jede Ermittlung 'welche Dateien haben sich geändert?' läuft
        über `_e2e_paths._git_diff_names()`.

        RED heute: `staging_gate._telegram_live_gate()` (:226-229) setzt ein
        eigenes `git diff --name-only HEAD~1 HEAD` ab.
        """
        root = tmp_path / "repo"
        root.mkdir()
        _init_repo_two_commits(root)

        sg, ps = _both_hooks()
        _patch_paths(monkeypatch, sg, root)
        _patch_paths(monkeypatch, ps, root)
        monkeypatch.setattr(ps, "REPO_DIR", root)

        probe = _GitProbe(tmp_path, monkeypatch)
        deleg = _Delegation(probe.diff)
        deleg.wrap(sg._e2e_paths, "_git_diff_names")
        deleg.wrap(ps._e2e_paths, "_git_diff_names")

        sg._telegram_live_gate()
        sg._detect_committed_scope()
        ps._detect_committed_scope(root)

        assert deleg.calls > 0, (
            "Kein Aufruf der gemeinsamen Stelle beobachtet — der Ablauf hat gar "
            "keinen Datei-Diff ermittelt (der Test misst nichts)"
        )
        assert deleg.outside == 0, (
            f"{deleg.outside} Datei-Diff(s) liefen als direkter git-Subprozess an "
            "_e2e_paths._git_diff_names() vorbei"
        )

    def test_merge_base_and_rev_parse_verify_stay_outside_this_check(
        self, monkeypatch, tmp_path
    ):
        """AC-7: `git merge-base --is-ancestor` (staging_gate.py:465) und
        `git rev-parse --verify <ref>^{commit}` (:400) bleiben BEWUSST
        eigenständig — für beide gibt es kein Gegenstück im gemeinsamen Modul
        (`rev-parse --verify` liefert zusätzlich die volle SHA auf stdout, was
        eine reine Existenzprüfung nicht kann; die Ancestor-Prüfung ist die
        einzige Fundstelle im Hook-Baum). Der Delegations-Zähler darf deshalb
        NICHT anschlagen, obwohl beide Kommandos hier nachweislich laufen.
        """
        root = tmp_path / "repo"
        root.mkdir()
        head, prev = _init_repo_two_commits(root)

        sg, _ps = _both_hooks()
        _patch_paths(monkeypatch, sg, root)

        # VERIFIED-Nachweis für den Vorgänger → die Ancestor-Auflösung greift
        # und löst `merge-base --is-ancestor` aus.
        att = root / ".claude" / "e2e_verified" / f"{prev}.json"
        att.parent.mkdir(parents=True, exist_ok=True)
        att.write_text(json.dumps({
            "verified_commit": prev,
            "staging_verdict": "VERIFIED: ok",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "backend",
        }))

        probe = _GitProbe(tmp_path, monkeypatch)
        catfile = _Delegation(probe.catfile)
        diffs = _Delegation(probe.diff)
        if hasattr(sg._e2e_paths, "commit_exists"):
            catfile.wrap(sg._e2e_paths, "commit_exists")
        diffs.wrap(sg._e2e_paths, "_git_diff_names")

        sg.gate_check(None, "backend", expected_commit=head)

        assert _count(probe.revverify) > 0, (
            "rev-parse --verify lief gar nicht — der Test belegt nichts"
        )
        assert _count(probe.mergebase) > 0, (
            "merge-base --is-ancestor lief gar nicht — der Test belegt nichts"
        )
        assert catfile.outside == 0, (
            "Der Delegations-Zähler hat auf einen der beiden bewusst "
            "eigenständigen Aufrufe angeschlagen (cat-file-Zähler)"
        )
        assert diffs.outside == 0, (
            "Der Delegations-Zähler hat auf einen der beiden bewusst "
            "eigenständigen Aufrufe angeschlagen (diff-Zähler)"
        )
