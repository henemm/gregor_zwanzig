"""TDD tests for Issue #384 — Hook-Infrastruktur fail-open härten.

Verifiziert, dass JEDER in `.claude/settings.json` registrierte
`${CLAUDE_PROJECT_DIR}`-Hook so eingebunden ist, dass eine **fehlende**
Hook-Datei das Tool ERLAUBT (fail-open), während eine **vorhandene**
Hook-Datei bei echtem Verstoß (Exit 2) weiterhin BLOCKT (fail-closed).

KEINE MOCKS: Die Tests lesen die echten Command-Strings aus settings.json
und führen sie als echte Subprozesse aus. `${CLAUDE_PROJECT_DIR}` wird auf
eine isolierte tmp-Sandbox gezeigt, in der die An-/Abwesenheit der Hook-Datei
gesteuert wird. Stub-Hooks (`sys.exit(0/2)`) ersetzen die echten Gates, damit
keine reale Gate-Logik mitläuft.

Exit-Code-Kontrakt (Claude Code PreToolUse):
- 0 -> Tool erlaubt
- 2 -> Tool blockiert

Spec: docs/specs/modules/issue_384_hook_fail_open.md
Test-Manifest: docs/specs/tests/issue_384_hook_fail_open_tests.md
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"

# Relativer Hook-Pfad innerhalb eines Command-Strings, z. B. ".claude/hooks/secrets_guard.py"
_HOOK_RE = re.compile(r"\.claude/hooks/[A-Za-z0-9_]+\.py")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load_settings() -> dict:
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def _project_dir_commands() -> list[dict]:
    """Alle Hook-Command-Strings, die ${CLAUDE_PROJECT_DIR} referenzieren.

    Das externe `bash /home/hem/claude-mq/check-messages.sh` (absoluter Pfad,
    kein CLAUDE_PROJECT_DIR) wird bewusst NICHT erfasst — es ist nicht die
    Fehlerquelle und nicht Teil des Fixes.
    """
    settings = _load_settings()
    out: list[dict] = []
    for event, groups in settings.get("hooks", {}).items():
        for gi, group in enumerate(groups):
            for hi, hook in enumerate(group.get("hooks", [])):
                cmd = hook.get("command", "")
                if "CLAUDE_PROJECT_DIR" in cmd:
                    out.append({"event": event, "gi": gi, "hi": hi, "cmd": cmd})
    return out


def _hook_relpath(cmd: str) -> str:
    m = _HOOK_RE.search(cmd)
    assert m, f"Kein .claude/hooks/<name>.py im Command gefunden: {cmd!r}"
    return m.group(0)


def _is_fail_open_guarded(cmd: str) -> bool:
    """Fail-open-Muster: `if [ -f … ]; then python3 … ; fi`.

    Die naive Form `python3 … || exit 0` ist VERBOTEN (würde echte Blocks
    aufweichen) und matcht hier bewusst NICHT.
    """
    s = cmd.strip()
    return s.startswith("if [ -f ") and "; then " in s and s.endswith("fi")


def _run(cmd: str, project_dir: Path) -> int:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    proc = subprocess.run(
        cmd, shell=True, env=env, capture_output=True, timeout=30, text=True
    )
    return proc.returncode


def _sandbox(tmp_path: Path, hook_relpath: str, stub_exit: int | None) -> Path:
    """Isolierte CLAUDE_PROJECT_DIR-Sandbox.

    stub_exit is None  -> Hook-Datei FEHLT (leeres .claude/hooks-Verzeichnis).
    stub_exit == 0/2   -> Hook-Datei vorhanden, ein Stub der mit diesem Code endet.
    """
    (tmp_path / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    if stub_exit is not None:
        target = tmp_path / hook_relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"import sys\nsys.exit({stub_exit})\n", encoding="utf-8")
    return tmp_path


# Parametrisierung über alle echten ${CLAUDE_PROJECT_DIR}-Commands der settings.json
_COMMANDS = _project_dir_commands()


def _build_params(mark_unguarded_xfail: bool) -> list:
    """Baut die Parameter-Liste; optional mit xfail(#1307) auf den 5 Hooks
    ohne Fail-open-Wrapping (renderer_mail_gate, prod_send_gate,
    nebenbefund_gate, test_naming_gate, track_token_usage — echter Befund,
    Bundle 2 der Rot-Triage #1211b). Nur fuer die zwei Tests genutzt, die
    genau diese Guard-Eigenschaft pruefen — test_present_blocking_hook_still_blocks
    und test_present_ok_hook_allows bleiben ungemarkt (aktuell gruen)."""
    params = []
    for c in _COMMANDS:
        marks = []
        if mark_unguarded_xfail and not _is_fail_open_guarded(c["cmd"]):
            marks.append(pytest.mark.xfail(
                reason="#1307: Hook ohne Fail-open-Wrapping — fehlende Datei blockiert (Lockout-Falle)",
                strict=False,
            ))
        params.append(pytest.param(
            c["cmd"],
            id=f"{_hook_relpath(c['cmd']).split('/')[-1]}-{c['event']}-{c['gi']}{c['hi']}",
            marks=marks,
        ))
    return params


_PARAMS = _build_params(mark_unguarded_xfail=False)
_PARAMS_GUARD_CHECK = _build_params(mark_unguarded_xfail=True)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_settings_json_is_valid_json():
    """AC-6: settings.json bleibt valides JSON (auch mit eingebettetem if … fi)."""
    data = _load_settings()
    assert isinstance(data, dict)
    assert "hooks" in data


@pytest.mark.parametrize("cmd", _PARAMS_GUARD_CHECK)
def test_every_hook_is_fail_open_guarded(cmd):
    """AC-5: JEDER ${CLAUDE_PROJECT_DIR}-Hook-Command muss fail-open-gewrappt sein.

    GIVEN ein in settings.json registrierter Hook-Command
    WHEN sein Command-String geprüft wird
    THEN entspricht er dem Muster `if [ -f … ]; then python3 … ; fi`
         (Schutz gegen erneutes Aufreißen des Lockout-Lochs).
    """
    assert _is_fail_open_guarded(cmd), (
        "Hook-Command ist NICHT fail-open-gewrappt — fehlende Datei würde das "
        f"Tool blockieren (Lockout): {cmd!r}"
    )


@pytest.mark.parametrize("cmd", _PARAMS_GUARD_CHECK)
def test_missing_hook_file_allows_tool(cmd, tmp_path):
    """AC-1 / AC-3: fehlende Hook-Datei -> Tool erlaubt (Exit 0), kein Lockout.

    GIVEN der echte Command-String aus settings.json
    WHEN er läuft, während die Hook-Datei im Working-Tree FEHLT
    THEN ist der Exit-Code 0 (fail-open) — nicht 2 (block).
    """
    relpath = _hook_relpath(cmd)
    sandbox = _sandbox(tmp_path, relpath, stub_exit=None)  # Datei fehlt
    rc = _run(cmd, sandbox)
    assert rc == 0, (
        f"Fehlende Hook-Datei führte zu Exit {rc} (erwartet 0). Genau dieser "
        f"fail-closed-Pfad löst den Total-Tool-Lockout aus: {cmd!r}"
    )


@pytest.mark.parametrize("cmd", _PARAMS)
def test_present_blocking_hook_still_blocks(cmd, tmp_path):
    """AC-2: vorhandener Hook, der mit Exit 2 blockt -> Block bleibt wirksam.

    GIVEN der echte Command-String aus settings.json
    WHEN die Hook-Datei vorhanden ist und mit Exit 2 blockt
    THEN propagiert Exit 2 (kein Aufweichen durch die fail-open-Logik).
    """
    relpath = _hook_relpath(cmd)
    sandbox = _sandbox(tmp_path, relpath, stub_exit=2)  # Datei da, blockt
    rc = _run(cmd, sandbox)
    assert rc == 2, (
        f"Blockender Hook (Exit 2) ergab Exit {rc} — die fail-open-Logik darf "
        f"echte Blocks NICHT aufweichen: {cmd!r}"
    )


@pytest.mark.parametrize("cmd", _PARAMS)
def test_present_ok_hook_allows(cmd, tmp_path):
    """AC-4: vorhandener Hook mit Exit 0 -> Tool erlaubt, unverändertes Verhalten.

    GIVEN der echte Command-String aus settings.json
    WHEN die Hook-Datei vorhanden ist und mit Exit 0 endet
    THEN ist der Exit-Code 0 (bestehende Gates verhalten sich unverändert).
    """
    relpath = _hook_relpath(cmd)
    sandbox = _sandbox(tmp_path, relpath, stub_exit=0)  # Datei da, erlaubt
    rc = _run(cmd, sandbox)
    assert rc == 0, (
        f"OK-Hook (Exit 0) ergab Exit {rc} — vorhandene Gates müssen unverändert "
        f"durchlassen: {cmd!r}"
    )
