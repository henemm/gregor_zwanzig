"""Issue #811 AC-2 + AC-3 — Renderer-Mail-Gate (un-ueberspringbar).

Mock-frei: echtes Temp-Git-Repo + Subprozess-Aufruf des Gate-Hooks.
Der Hook `.claude/hooks/renderer_mail_gate.py` EXISTIERT in der RED-Phase NOCH NICHT
→ alle Tests erroren/fehlschlagen (gueltiges RED).

Definiert die ERWARTETE Schnittstelle exakt wie in der Spec
(docs/specs/modules/issue_811_mail_quality_gate.md):
  - Hook-Modus: stdin-JSON {"tool_input":{"command":"git commit ..."}} → Exit 0/2.
  - Recorder-Subkommando: `renderer_mail_gate.py record-matrix` schreibt
    state["gates"]["renderer_mail"]["matrix"] = {passed, mail_files_hash}.
  - Nachweis liegt AUSSCHLIESSLICH pro Workflow in .claude/workflows/<name>.json.

Test-Manifest: docs/specs/tests/issue_811_mail_quality_gate_tests.md
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import importlib.util


# Gate-Hook im (Worktree-)Repo. Existiert in RED-Phase NICHT → RED.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_SRC = _REPO_ROOT / ".claude" / "hooks" / "renderer_mail_gate.py"


def _load_gate_module():
    """Importiert renderer_mail_gate als Modul (eine Quelle fuer _is_mail_file)."""
    spec = importlib.util.spec_from_file_location("renderer_mail_gate", _GATE_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_gate = _load_gate_module()

# Eine geschuetzte Mail-Inhalts-Datei (Spec: src/output/renderers/email/.*\.py$).
_MAIL_FILE = "src/output/renderers/email/helpers.py"
_NON_MAIL_FILE = "README.md"

_WF_NAME = "issue-811-mail-quality-gate"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def _setup_repo(tmp_path: Path) -> Path:
    """Standalone Git-Repo mit eigener .claude/-Struktur + Gate-Kopie."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    # .claude/hooks + Gate-Kopie (RED: _GATE_SRC fehlt → FileNotFoundError).
    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy(_GATE_SRC, hooks / "renderer_mail_gate.py")
    # Helfer-Module, die der Gate evtl. importiert, mitkopieren (best-effort).
    for helper in ("config_loader.py", "workflow.py", "workflow_state_multi.py", "hook_utils.py"):
        src = _REPO_ROOT / ".claude" / "hooks" / helper
        if src.exists():
            shutil.copy(src, hooks / helper)

    (repo / ".claude" / "workflows" / "_log").mkdir(parents=True)

    # Mail-Inhalts-Datei anlegen + initial committen (sauberer Baseline).
    mail_path = repo / _MAIL_FILE
    mail_path.parent.mkdir(parents=True, exist_ok=True)
    mail_path.write_text("# initial\n")
    (repo / _NON_MAIL_FILE).write_text("# readme\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _run_gate(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Der Gate resolved den Workflow-Namen ueber hook_utils.get_active_workflow_name()
    # → OPENSPEC_ACTIVE_WORKFLOW (lebender Var-Name). GZ_ACTIVE_WORKFLOW ist Legacy
    # und wird vom Resolver nicht gelesen; explizit setzen macht den Test hermetisch
    # (unabhaengig von der ambienten Session-Env). Siehe #894.
    env["OPENSPEC_ACTIVE_WORKFLOW"] = _WF_NAME
    env["GZ_ACTIVE_WORKFLOW"] = _WF_NAME
    return subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "renderer_mail_gate.py"), *args],
        cwd=repo, input=stdin, capture_output=True, text=True, env=env,
    )


def _commit_stdin() -> str:
    return json.dumps({"tool_input": {"command": "git commit -m wip"}})


def _write_workflow_state(repo: Path, gates: dict | None = None) -> Path:
    state = {"name": _WF_NAME, "phase": "phase6", "issue": 811}
    if gates is not None:
        state["gates"] = gates
    p = repo / ".claude" / "workflows" / f"{_WF_NAME}.json"
    p.write_text(json.dumps(state))
    return p


def _staged_mail_hash(repo: Path) -> str:
    """sha256 der aktuell gestagten Mail-Inhalts-Datei(en) — Spec-Anti-Stale.

    Verwendet _gate._is_mail_file (eine Quelle mit dem Gate — F003).
    Bei Erweiterung auf mehrere Mail-Dateien divergiert der Test-Hash nie vom
    Gate-Hash.
    """
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.split()
    h = hashlib.sha256()
    for name in sorted(out):
        if _gate._is_mail_file(name):
            h.update((repo / name).read_bytes())
    return h.hexdigest()


def _write_validation_log(
    repo: Path, *, passed: bool = True, validated_at: datetime | None = None,
) -> Path:
    """Schreibt ein briefing_validation.yaml-Log.

    validated_at: explizit setzbar fuer Freshness-Tests. Default: jetzt.
    """
    now = validated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    log_dir = repo / ".claude" / "workflows" / "_log"
    ts = now.strftime("%Y%m%d_%H%M%S")
    p = log_dir / f"{ts}_{_WF_NAME}_briefing_validation.yaml"
    p.write_text(
        "validator: briefing_mail_validator\n"
        f"validated_at: '{now.isoformat()}'\n"
        f"workflow_id: {_WF_NAME}\n"
        f"passed: {str(passed).lower()}\n"
        "error_count: 0\n"
    )
    return p


# ---------------------------------------------------------------------------
# AC-2: Block ohne Nachweis
# ---------------------------------------------------------------------------

def test_block_when_no_evidence(tmp_path):
    """Mail-Datei gestaged, kein Nachweis im Workflow → Exit 2."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo, gates=None)
    (repo / _MAIL_FILE).write_text("# changed\n")
    _git(repo, "add", _MAIL_FILE)

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 2, (
        f"Ohne Nachweis muss der Gate blockieren (Exit 2). "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: Pass mit beiden Nachweisen
# ---------------------------------------------------------------------------

def test_pass_with_both_evidences(tmp_path):
    """Matrix-Nachweis (Hash passend) + Validator-Log passed (frisch) → Exit 0."""
    repo = _setup_repo(tmp_path)
    mail_path = repo / _MAIL_FILE
    mail_path.write_text("# changed\n")
    _git(repo, "add", _MAIL_FILE)

    # validated_at explizit NACH mail-mtime setzen (robust gegen 1s-Granularitaet).
    mail_mtime = mail_path.stat().st_mtime
    fresh_vat = datetime.fromtimestamp(mail_mtime + 2.0, tz=timezone.utc)

    mail_hash = _staged_mail_hash(repo)
    _write_workflow_state(repo, gates={
        "renderer_mail": {"matrix": {"passed": True, "mail_files_hash": mail_hash}},
    })
    _write_validation_log(repo, passed=True, validated_at=fresh_vat)

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 0, (
        f"Mit beiden frischen Nachweisen muss der Gate passieren (Exit 0). "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: No-op ohne Mail-Datei (kein False-Positive)
# ---------------------------------------------------------------------------

def test_noop_when_no_mail_file(tmp_path):
    """Commit beruehrt KEINE Mail-Inhalts-Datei → Exit 0 (no-op)."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo, gates=None)
    (repo / _NON_MAIL_FILE).write_text("# touched\n")
    _git(repo, "add", _NON_MAIL_FILE)

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 0, (
        f"Ohne Mail-Datei darf der Gate NICHT blockieren (Exit 0). "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: Recorder schreibt den Hash in den Workflow-State
# ---------------------------------------------------------------------------

def test_record_matrix_writes_hash(tmp_path):
    """`record-matrix` schreibt state.gates.renderer_mail.matrix mit sha256."""
    repo = _setup_repo(tmp_path)
    state_path = _write_workflow_state(repo, gates=None)
    (repo / _MAIL_FILE).write_text("# changed\n")
    _git(repo, "add", _MAIL_FILE)
    expected = _staged_mail_hash(repo)

    res = _run_gate(repo, "record-matrix")
    assert res.returncode == 0, f"record-matrix sollte Exit 0 liefern: {res.stderr!r}"

    state = json.loads(state_path.read_text())
    matrix = state.get("gates", {}).get("renderer_mail", {}).get("matrix", {})
    assert matrix.get("passed") is True, f"matrix.passed fehlt: {matrix!r}"
    assert matrix.get("mail_files_hash") == expected, (
        f"matrix.mail_files_hash muss dem sha256 der Mail-Dateien entsprechen: {matrix!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: Validator-Log aelter als Mail-Datei → Gate blockt (F001 Freshness)
# ---------------------------------------------------------------------------

def test_block_when_validator_log_older_than_mail_file(tmp_path):
    """Validator-Log aelter als Mail-Datei-mtime → Exit 2 (F001 Freshness).

    Beweist AC-2(b): der Validator-Nachweis muss NACH der letzten Renderer-Aenderung
    entstanden sein. Alter Log (validated_at < mail mtime) → stale → blockiert.

    mtime wird via os.utime explizit gesetzt (robust gegen 1s-Granularitaet von
    Dateisystemen, die nanosekunden-Präzision nicht garantieren).
    """
    import os
    repo = _setup_repo(tmp_path)

    # T0: Log-Zeitstempel (validated_at = jetzt).
    t0 = datetime.now(timezone.utc)
    _write_validation_log(repo, passed=True)

    # Mail-Datei schreiben und mtime explizit auf T0 + 2s setzen (deutlich nach Log).
    mail_path = repo / _MAIL_FILE
    mail_path.write_text("# changed after stale log\n")
    future_mtime = t0.timestamp() + 2.0
    os.utime(mail_path, (future_mtime, future_mtime))

    _git(repo, "add", _MAIL_FILE)
    mail_hash = _staged_mail_hash(repo)

    _write_workflow_state(repo, gates={
        "renderer_mail": {"matrix": {"passed": True, "mail_files_hash": mail_hash}},
    })

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 2, (
        f"Validator-Log aelter als Mail-Datei muss blockieren (Exit 2, F001 Freshness). "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: Stale-Nachweis nach Renderer-Aenderung → erneut blockiert
# ---------------------------------------------------------------------------

def test_stale_evidence_reblocked_after_change(tmp_path):
    """Nachweis hinterlegt → Mail-Datei erneut geaendert → Exit 2 (Hash-Mismatch)."""
    repo = _setup_repo(tmp_path)
    mail_path = repo / _MAIL_FILE
    mail_path.write_text("# changed v1\n")
    _git(repo, "add", _MAIL_FILE)
    old_hash = _staged_mail_hash(repo)
    # validated_at frisch relativ zu v1 (robust gegen 1s-Granularitaet).
    v1_mtime = mail_path.stat().st_mtime
    fresh_vat = datetime.fromtimestamp(v1_mtime + 2.0, tz=timezone.utc)
    _write_workflow_state(repo, gates={
        "renderer_mail": {"matrix": {"passed": True, "mail_files_hash": old_hash}},
    })
    _write_validation_log(repo, passed=True, validated_at=fresh_vat)

    # Spaetere Renderer-Aenderung invalidiert den Nachweis (Hash-Mismatch).
    mail_path.write_text("# changed v2 — andere Bytes\n")
    _git(repo, "add", _MAIL_FILE)

    res = _run_gate(repo, stdin=_commit_stdin())
    assert res.returncode == 2, (
        f"Veralteter (Hash-fremder) Nachweis muss erneut blockieren (Exit 2). "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: Kein globaler/ENV-Bypass
# ---------------------------------------------------------------------------

def test_no_env_global_bypass(tmp_path):
    """Kein ENV-Flag/globaler Schalter erzeugt einen gueltigen Nachweis."""
    repo = _setup_repo(tmp_path)
    _write_workflow_state(repo, gates=None)
    (repo / _MAIL_FILE).write_text("# changed\n")
    _git(repo, "add", _MAIL_FILE)

    env = dict(os.environ)
    # Der Gate resolved den Workflow-Namen ueber hook_utils.get_active_workflow_name()
    # → OPENSPEC_ACTIVE_WORKFLOW (lebender Var-Name). GZ_ACTIVE_WORKFLOW ist Legacy
    # und wird vom Resolver nicht gelesen; explizit setzen macht den Test hermetisch
    # (unabhaengig von der ambienten Session-Env). Siehe #894.
    env["OPENSPEC_ACTIVE_WORKFLOW"] = _WF_NAME
    env["GZ_ACTIVE_WORKFLOW"] = _WF_NAME
    # Plausible Bypass-Versuche, die NICHT funktionieren duerfen.
    for bypass in ("RENDERER_MAIL_GATE_SKIP", "GZ_SKIP_GATES",
                   "SKIP_MAIL_GATE", "GZ_RENDERER_MAIL_OK"):
        env[bypass] = "1"
    res = subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "renderer_mail_gate.py")],
        cwd=repo, input=_commit_stdin(), capture_output=True, text=True, env=env,
    )
    assert res.returncode == 2, (
        f"Kein ENV/globaler Bypass darf den Gate aushebeln (Exit 2 erwartet). "
        f"rc={res.returncode} stderr={res.stderr!r}"
    )
