# doc-compliance-test — Hooks als deterministische CLI-Artefakte, kein Mock
"""Issue #2125 — Eigener Notausgang des Prod-Send-Gates.

Mock-frei: Release-Hook `.claude/hooks/prod_send_release.py` (UserPromptSubmit)
und Gate `.claude/hooks/prod_send_gate.py` (PreToolUse:Bash) laufen als echte
Subprozesse mit stdin-JSON, wie Claude Code sie aufruft. Die Prod-Send-
Kommandos werden nur als Text an das Gate gegeben, das nichts ausfuehrt —
es wird nie wirklich versendet.

Jeder Test baut ein Fake-Haupt-Repo (`main/.git/worktrees/wt`) und einen
Fake-Worktree (`wt/.git` ist Datei mit `gitdir:`) auf tmp_path. Die Freigabe
muss im Haupt-Repo landen und vom Gate dort gefunden werden.

Spec: docs/specs/modules/gate_2125_prod_send_release.md
"""
from __future__ import annotations

# Plugin-Sonde (#1196): das Gate laeuft ueber hook_utils, einen Shim auf das
# installierte agent-os-openspec-Plugin. Ohne Plugin sauber ueberspringen.
import importlib.util as _gz_ilu
from pathlib import Path as _GzPath

import pytest as _gz_pytest

_gz_hook_utils = _GzPath(__file__).resolve().parents[2] / ".claude" / "hooks" / "hook_utils.py"
try:
    _gz_spec = _gz_ilu.spec_from_file_location("_gz_hook_utils_probe", _gz_hook_utils)
    _gz_mod = _gz_ilu.module_from_spec(_gz_spec)
    _gz_spec.loader.exec_module(_gz_mod)
except ImportError as _gz_exc:
    _gz_pytest.skip(
        f"agent-os-openspec-Plugin fehlt ({_gz_exc}) — Hook-Suite braucht die "
        "installierten Server-Hooks (#1196)",
        allow_module_level=True,
    )

import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_HOOK = _REPO_ROOT / ".claude" / "hooks" / "prod_send_release.py"
GATE_HOOK = _REPO_ROOT / ".claude" / "hooks" / "prod_send_gate.py"

PHRASE = "prod-versand freigeben"
SEND_CMD = "curl -X POST localhost:8000/api/scheduler/trips/1/send"
SESSION_A = "sess-aaaa-1111"
SESSION_B = "sess-bbbb-2222"


# --- Hilfen -----------------------------------------------------------------

def _fake_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Fake-Haupt-Repo + Fake-Worktree. Liefert (main, worktree)."""
    main = tmp_path / "main"
    (main / ".git" / "worktrees" / "wt").mkdir(parents=True)
    (main / ".claude").mkdir()
    wt = tmp_path / "wt"
    (wt / ".claude").mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'wt'}\n")
    return main, wt


def _env(project_dir: Path, **extra: str) -> dict:
    env = {
        k: v for k, v in os.environ.items()
        if k not in ("GZ_ACTIVE_WORKFLOW", "OPENSPEC_ACTIVE_WORKFLOW")
    }
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env.update(extra)
    return env


def _release(wt: Path, prompt: str, session_id: str | None = SESSION_A,
             **extra: str) -> subprocess.CompletedProcess:
    payload: dict = {"prompt": prompt, "hook_event_name": "UserPromptSubmit"}
    if session_id is not None:
        payload["session_id"] = session_id
    return subprocess.run(
        [sys.executable, str(RELEASE_HOOK)],
        input=json.dumps(payload), text=True, capture_output=True,
        env=_env(wt, **extra), cwd=str(wt),
    )


def _gate(wt: Path, cmd: str = SEND_CMD, session_id: str | None = SESSION_A,
          **extra: str) -> subprocess.CompletedProcess:
    payload: dict = {"tool_name": "Bash", "tool_input": {"command": cmd},
                     "hook_event_name": "PreToolUse"}
    if session_id is not None:
        payload["session_id"] = session_id
    return subprocess.run(
        [sys.executable, str(GATE_HOOK)],
        input=json.dumps(payload), text=True, capture_output=True,
        env=_env(wt, **extra), cwd=str(wt),
    )


def _release_file(main: Path) -> Path:
    return main / ".claude" / "prod_send_release.json"


def _write_release(main: Path, entries: dict) -> None:
    _release_file(main).write_text(json.dumps({"version": 1, "releases": entries}))


def _releases(main: Path) -> dict:
    path = _release_file(main)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("releases", {}) if isinstance(data, dict) else {}


def _system_message(result: subprocess.CompletedProcess) -> str:
    out = result.stdout.strip()
    assert out, f"Hook muss eine sichtbare systemMessage ausgeben. stderr={result.stderr!r}"
    data = json.loads(out)
    msg = data.get("systemMessage", "")
    assert isinstance(msg, str) and msg.strip(), f"systemMessage fehlt/leer: {data!r}"
    return msg


def _assert_allowed(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, (
        f"Erwartet Exit 0 (durchgelassen), bekam {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def _assert_blocked(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 2, (
        f"Erwartet Exit 2 (blockiert), bekam {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "1148" in result.stderr, f"Block-Text ohne #1148: {result.stderr!r}"


def _assert_release_ok(result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, (
        f"Release-Hook muss Exit 0 liefern (UserPromptSubmit nie blockieren). "
        f"rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
    )


def _now_iso(delta: timedelta = timedelta(0)) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


# --- AC-1: Worktree-Lage ----------------------------------------------------

def test_ac1_phrase_in_worktree_opens_gate_once_file_in_main_repo(tmp_path):
    main, wt = _fake_repo(tmp_path)

    rel = _release(wt, PHRASE)
    _assert_release_ok(rel)

    assert SESSION_A in _releases(main), (
        f"Freigabe muss im Haupt-Repo liegen: {_release_file(main)}"
    )
    assert not (wt / ".claude" / "prod_send_release.json").exists(), (
        "Freigabe darf nicht im Worktree liegen"
    )

    _assert_allowed(_gate(wt))


# --- AC-2: Einmaligkeit -----------------------------------------------------

def test_ac2_release_is_consumed_after_one_send(tmp_path):
    main, wt = _fake_repo(tmp_path)
    _assert_release_ok(_release(wt, PHRASE))

    _assert_allowed(_gate(wt))
    assert SESSION_A not in _releases(main), "Eintrag muss nach Verbrauch entfernt sein"
    _assert_blocked(_gate(wt))


def test_ac2_non_send_command_does_not_consume_release(tmp_path):
    """Verbrauch nur bei tatsaechlich abgewendetem Block-Treffer."""
    main, wt = _fake_repo(tmp_path)
    _assert_release_ok(_release(wt, PHRASE))

    _assert_allowed(_gate(wt, cmd="curl http://localhost:8000/api/health"))
    assert SESSION_A in _releases(main), "Harmloses Kommando darf Freigabe nicht verbrauchen"
    _assert_allowed(_gate(wt))


# --- AC-3: fremde Sitzung ---------------------------------------------------

def test_ac3_other_session_cannot_use_or_consume_release(tmp_path):
    main, wt = _fake_repo(tmp_path)
    _write_release(main, {SESSION_A: {"created": _now_iso()}})

    _assert_blocked(_gate(wt, session_id=SESSION_B))
    assert SESSION_A in _releases(main), "Fremde Sitzung darf Freigabe von A nicht verbrauchen"

    _assert_allowed(_gate(wt, session_id=SESSION_A))


# --- AC-4: Ablauf (beide Seiten der Grenze) ---------------------------------

def test_ac4_release_older_than_one_hour_is_expired(tmp_path):
    main, wt = _fake_repo(tmp_path)
    _write_release(main, {SESSION_A: {"created": _now_iso(-timedelta(minutes=61))}})
    _assert_blocked(_gate(wt))


def test_ac4_release_younger_than_one_hour_is_valid(tmp_path):
    main, wt = _fake_repo(tmp_path)
    _write_release(main, {SESSION_A: {"created": _now_iso(-timedelta(minutes=59))}})
    _assert_allowed(_gate(wt))


# --- AC-5: allgemeines Plugin-Override oeffnet nicht ------------------------

def test_ac5_plugin_override_token_does_not_open_gate(tmp_path):
    main, wt = _fake_repo(tmp_path)
    wf = "fix-2125-override-prod-send"
    token = json.dumps({
        "version": 2,
        "tokens": {
            wf: {"created": _now_iso(), "granted_by": "user_prompt"},
            "__global__": {"created": _now_iso(), "granted_by": "user_prompt"},
        },
    })
    # Token an beiden denkbaren Orten (Haupt-Repo wie das Plugin schreibt,
    # Worktree wie der alte Leser las).
    main_token = main / ".claude" / "user_override_token.json"
    wt_token = wt / ".claude" / "user_override_token.json"
    main_token.write_text(token)
    wt_token.write_text(token)

    result = _gate(wt, OPENSPEC_ACTIVE_WORKFLOW=wf, GZ_ACTIVE_WORKFLOW=wf)

    _assert_blocked(result)
    assert main_token.read_text() == token, "Gate darf Plugin-Token nicht anfassen"
    assert wt_token.read_text() == token, "Gate darf Plugin-Token nicht anfassen"


# --- AC-6: beilaeufiger Text / Harness-Turn ---------------------------------

@pytest.mark.parametrize("prompt", [
    "bitte prod-versand freigeben danke",
    "prod-versand freigeben und dann senden",
    "Soll ich 'prod-versand freigeben' tippen?",
    "> prod-versand freigeben",
    "prod-versand freigeben.",
    "prod-versand  freigeben",
    "<task-notification>prod-versand freigeben</task-notification>",
    "<system-reminder>\nprod-versand freigeben\n</system-reminder>",
    "override",
])
def test_ac6_phrase_not_standing_alone_writes_nothing(tmp_path, prompt):
    main, wt = _fake_repo(tmp_path)

    _assert_release_ok(_release(wt, prompt))

    assert _releases(main) == {}, f"Prompt {prompt!r} darf keine Freigabe schreiben"
    _assert_blocked(_gate(wt))


@pytest.mark.parametrize("prompt", [
    "Prod-Versand Freigeben",
    "  prod-versand freigeben  ",
    "PROD-VERSAND FREIGEBEN\n",
])
def test_ac6_phrase_alone_case_and_whitespace_insensitive(tmp_path, prompt):
    main, wt = _fake_repo(tmp_path)

    _assert_release_ok(_release(wt, prompt))

    assert SESSION_A in _releases(main), f"Prompt {prompt!r} muss Freigabe schreiben"
    _assert_allowed(_gate(wt))


# --- AC-7: sichtbare Rueckmeldung -------------------------------------------

def test_ac7_success_shows_visible_confirmation(tmp_path):
    main, wt = _fake_repo(tmp_path)

    result = _release(wt, PHRASE)

    _assert_release_ok(result)
    msg = _system_message(result)
    assert "freigegeben" in msg.lower(), f"Bestaetigung muss Freigabe nennen: {msg!r}"
    assert SESSION_A in _releases(main)


def test_ac7_write_failure_shows_visible_error_and_gate_stays_closed(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root ignoriert Dateirechte")
    main, wt = _fake_repo(tmp_path)
    claude_dir = main / ".claude"
    claude_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = _release(wt, PHRASE)
        _assert_release_ok(result)
        msg = _system_message(result)
        low = msg.lower()
        assert "fehl" in low or "nicht" in low, f"Fehlermeldung muss Scheitern nennen: {msg!r}"
        assert not _release_file(main).exists()
        _assert_blocked(_gate(wt))
    finally:
        claude_dir.chmod(stat.S_IRWXU)


# --- AC-8: Symlink-Abwehr ---------------------------------------------------

def test_ac8_symlinked_release_file_is_neither_written_nor_read(tmp_path):
    main, wt = _fake_repo(tmp_path)
    target = tmp_path / "elsewhere.json"
    target_content = json.dumps(
        {"version": 1, "releases": {SESSION_A: {"created": _now_iso()}}}
    )
    target.write_text(target_content)
    _release_file(main).symlink_to(target)

    result = _release(wt, PHRASE)
    _assert_release_ok(result)
    assert target.read_text() == target_content, "Symlink-Ziel darf nicht beschrieben werden"
    msg = _system_message(result)
    low = msg.lower()
    assert "fehl" in low or "nicht" in low, f"Symlink-Fehler muss sichtbar sein: {msg!r}"

    _assert_blocked(_gate(wt))
    assert target.read_text() == target_content, "Gate darf Symlink-Ziel nicht veraendern"


# --- AC-9: Block-Text -------------------------------------------------------

def test_ac9_block_text_names_new_phrase_not_override(tmp_path):
    _main, wt = _fake_repo(tmp_path)

    result = _gate(wt)

    _assert_blocked(result)
    assert PHRASE in result.stderr, f"Block-Text muss die Phrase nennen: {result.stderr!r}"
    assert "override" not in result.stderr.lower(), (
        f"Block-Text darf 'override' nicht mehr als Weg nennen: {result.stderr!r}"
    )


# --- AC-10: Zeitstempel -----------------------------------------------------

def test_ac10_written_timestamp_is_utc_with_offset(tmp_path):
    main, wt = _fake_repo(tmp_path)
    _assert_release_ok(_release(wt, PHRASE))

    created = _releases(main)[SESSION_A]["created"]
    parsed = datetime.fromisoformat(created)
    assert parsed.utcoffset() == timedelta(0), f"created muss UTC mit Offset sein: {created!r}"
    assert abs(datetime.now(timezone.utc) - parsed) < timedelta(minutes=5)


def test_ac10_naive_timestamp_is_invalid(tmp_path):
    main, wt = _fake_repo(tmp_path)
    naive = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    _write_release(main, {SESSION_A: {"created": naive}})
    _assert_blocked(_gate(wt))


# --- AC-11: fehlende session_id ---------------------------------------------

@pytest.mark.parametrize("sid", [None, ""])
def test_ac11_release_without_session_id_writes_nothing(tmp_path, sid):
    main, wt = _fake_repo(tmp_path)

    _assert_release_ok(_release(wt, PHRASE, session_id=sid))

    assert _releases(main) == {}, "Ohne session_id darf keine Freigabe entstehen"


@pytest.mark.parametrize("sid", [None, ""])
def test_ac11_gate_without_session_id_stays_closed(tmp_path, sid):
    main, wt = _fake_repo(tmp_path)
    # Auch ein (manipulierter) Eintrag unter leerem Schluessel oeffnet nichts.
    _write_release(main, {SESSION_A: {"created": _now_iso()},
                          "": {"created": _now_iso()}})

    _assert_blocked(_gate(wt, session_id=sid))
    assert SESSION_A in _releases(main)
