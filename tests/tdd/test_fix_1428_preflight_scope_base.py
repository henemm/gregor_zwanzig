"""
Regressionstest — Preflight-Diff-Basis statt Scope-Cache (henemm-infra#148 / #1428).

Root-Cause (Diagnose+Fix-Design: infra-Instanz, henemm-infra):
`staging_gate.py` beantwortete dieselbe Scope-Frage fuer denselben Ziel-Commit
im Preflight (VOR `git reset --hard`, Diff-Basis = alter, noch live laufender
Commit) und im regulaeren --check danach (Diff-Basis = alter Gate-Marker) je
nach Situation unterschiedlich. Traf der Marker auf einen aelteren Stand als
den zuletzt live gegangenen Commit (z.B. weil eine vorangegangene Deploy-Runde
den Marker nicht vorrueckte -- Retry-Szenario), diffte der reguläre Check ueber
den Backend-Commit hinweg und sah faelschlich "backend" statt "docs-only",
obwohl der Preflight fuer denselben Ziel-Commit "docs-only" ermittelt und den
Deploy freigegeben hatte. Das fuehrte zu henemm-infra#148 (Produktionsausfall).

Der urspruengliche Fix-Vorschlag ("Scope unter der Ziel-SHA cachen") haette
NICHT funktioniert: cached_scope_for_sha() verwirft einen gecachten
"docs-only"-Wert grundsaetzlich (Schutzregel F001) -- und genau "docs-only"
war der Preflight-Wert im gemeldeten Vorfall. Der tatsaechliche Fix hinterlegt
daher die Diff-BASIS (den alten, noch live laufenden Commit), nicht den
Scope-WERT. Der Scope wird weiterhin immer frisch aus dem echten `git diff`
berechnet -- F001 bleibt unberuehrt.

KEINE Mocks der Git-Logik. Jeder Test baut ein ECHTES temporaeres Git-Repo und
ruft das ECHTE staging_gate.gate_check()/_scope_diff_base() in-process dagegen
auf. Muster/Location-Seam wie tests/tdd/test_staging_gate_ancestor_scope.py
(Vorbild fuer Setup/Fixtures/hermetisches Temp-Repo, Issue #1096).

Pfadregel #1409: Pruefling wird relativ zur Testdatei aufgeloest
(parents[2] == Repo-Root dieses Worktrees), NIE ueber einen hartkodierten
Hauptrepo-Pfad -- sonst pruefte dieser Test aus einem Worktree die
unveraenderte Hauptrepo-Kopie.
"""

import importlib.util
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGING_GATE = REPO_ROOT / ".claude" / "hooks" / "staging_gate.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load_module(STAGING_GATE, "staging_gate_fix_1428")


def _git(args, cwd):
    return subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))


def _init_repo(root: Path) -> None:
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)


def _commit(root: Path, files: dict, msg: str) -> str:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", msg], root)
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


def _point(monkeypatch, shared: Path, verified: Path | None = None) -> None:
    verified = verified if verified is not None else shared
    monkeypatch.setattr(GATE, "_shared_repo_dir", lambda: shared)
    monkeypatch.setattr(GATE, "_verified_repo_dir", lambda: verified)


# ---------------------------------------------------------------------------
# Vorfall-Reproduktion: Marker M ist veraltet (Retry-Szenario), Backend-Commit
# B ist bereits live gecheckt out, Ziel-Commit D ist ein reiner docs-only-
# Aufsatz auf B. Preflight liefert fuer D "docs-only"; der reguläre Check nach
# dem Reset MUSS zum selben Ergebnis kommen.
# ---------------------------------------------------------------------------
def test_regular_check_after_reset_agrees_with_preflight_docs_only(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    m = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "M: initial product")
    # Marker zeigt (veraltet) auf M -- wurde bei B's Deploy nie vorgerueckt
    # (Retry-Szenario, siehe Docstring).
    _point(monkeypatch, tmp_path)
    GATE._e2e_paths.write_last_gate_scope(tmp_path, m)

    b = _commit(tmp_path, {"src/handler.py": "y = 2\n"}, "B: backend change (bereits live)")
    d = _commit(tmp_path, {"docs/notes.md": "# notes\n"}, "D: docs-only Aufsatz auf B")
    assert m != b != d

    # Preflight fuer D laeuft, waehrend B noch ausgecheckt ist (der reale
    # Ablauf VOR git reset --hard).
    _git(["checkout", "-q", b], tmp_path)
    rc_preflight = GATE.gate_check(None, None, expected_commit=d)
    assert rc_preflight == 0, "Preflight muss D als docs-only freigeben (Diff B..D)"

    # Deploy fuehrt git reset --hard auf D aus.
    _git(["checkout", "-q", d], tmp_path)

    # Regulaerer Check nach dem Reset (kein expected_commit -- prueft HEAD=D).
    rc_check = GATE.gate_check(None, None, expected_commit=None)
    assert rc_check == 0, (
        "Regulaerer Check nach dem Reset muss dieselbe docs-only-Antwort wie "
        "der Preflight liefern (Diff B..D), nicht ueber den veralteten Marker "
        "M hinweg gegen den Backend-Commit B diffen (das war henemm-infra#148)"
    )


# ---------------------------------------------------------------------------
# Unit-Test (a): Vorrang des Hints -- die Preflight-Basis wird genutzt, wenn
# fuer den aktuellen HEAD vorhanden.
# ---------------------------------------------------------------------------
def test_scope_diff_base_prefers_preflight_hint_over_marker(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    base_commit = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "base")
    other_marker_commit = _commit(tmp_path, {"src/other.py": "z = 1\n"}, "other (marker)")
    target = _commit(tmp_path, {"docs/notes.md": "# notes\n"}, "target")
    _point(monkeypatch, tmp_path)

    # Marker zeigt auf einen ANDEREN Commit als die Preflight-Basis.
    GATE._e2e_paths.write_last_gate_scope(tmp_path, other_marker_commit)
    GATE._e2e_paths.write_preflight_base(tmp_path, target, base_commit)

    _git(["checkout", "-q", target], tmp_path)
    assert GATE._scope_diff_base() == base_commit, (
        "Bei vorhandenem, aufloesbarem Preflight-Hint fuer den aktuellen HEAD "
        "muss dieser Vorrang vor dem Gate-Marker haben"
    )


# ---------------------------------------------------------------------------
# Unit-Test (b): Hint fuer einen FALSCHEN Ziel-Commit wird ignoriert --
# Fallback auf die bestehende Marker-Logik.
# ---------------------------------------------------------------------------
def test_scope_diff_base_ignores_hint_for_wrong_target(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    marker_commit = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "marker basis")
    stale_hint_target = _commit(tmp_path, {"src/other.py": "z = 1\n"}, "anderer alter Ziel-Commit")
    actual_head = _commit(tmp_path, {"docs/notes.md": "# notes\n"}, "tatsaechlicher HEAD")
    _point(monkeypatch, tmp_path)

    GATE._e2e_paths.write_last_gate_scope(tmp_path, marker_commit)
    # Hint wurde fuer einen ANDEREN (aelteren) Ziel-Commit hinterlegt, nicht
    # fuer den jetzt aktuellen HEAD.
    GATE._e2e_paths.write_preflight_base(tmp_path, stale_hint_target, marker_commit)

    _git(["checkout", "-q", actual_head], tmp_path)
    assert GATE._scope_diff_base() == marker_commit, (
        "Ein Hint fuer einen fremden Ziel-Commit darf nicht greifen -- Fallback "
        "auf die bestehende Marker-Logik"
    )


# ---------------------------------------------------------------------------
# Unit-Test (c): Selbstreferenz -- Fix #1776. Preflight-Basis == Ziel-Commit
# selbst (kann bei einem Merge kurz nach dem Preflight entstehen). Ein
# HEAD..HEAD-Diff waere immer leer und faelschlich "docs-only" (henemm-infra
# Live-Vorfaelle #1725, #1803). _scope_diff_base() darf die Selbstreferenz
# nicht zurueckgeben, sondern muss auf die bestehende Marker/HEAD~1-Fallback-
# Kette ausweichen -- dasselbe Muster, das der marker_sha-Zweig (Zeile
# 164: "if marker_sha and marker_sha != head") bereits hat.
# ---------------------------------------------------------------------------
def test_scope_diff_base_rejects_preflight_hint_self_reference(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    target = _commit(tmp_path, {"src/app.py": "x = 1\n"}, "target (Preflight-Basis == Ziel-Commit)")
    _point(monkeypatch, tmp_path)

    # Selbstreferenz: Preflight-Basis zeigt auf den Ziel-Commit selbst.
    GATE._e2e_paths.write_preflight_base(tmp_path, target, target)

    _git(["checkout", "-q", target], tmp_path)
    result = GATE._scope_diff_base(head=target)
    assert result != target, (
        "Bei Selbstreferenz (preflight_base == head) darf _scope_diff_base() "
        "nicht den Ziel-Commit selbst zurueckgeben (HEAD..HEAD-Diff waere "
        "immer leer und faelschlich docs-only, #1776) -- Fallback auf "
        "Marker/HEAD~1 erwartet"
    )
