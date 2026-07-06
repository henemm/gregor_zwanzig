"""
TDD Tests für Issue #829: Token-Verbrauch pro Workflow protokollieren

SPIKE-ERGEBNIS: Machbar — Session-Transcripts (.jsonl) enthalten usage-Felder.

Testet:
- AC-1: Stop-Hook schreibt token_usage in Workflow-State
- AC-2: Kumulation über mehrere Sessions
- AC-3: Kein aktiver Workflow → exit 0, keine State-Änderung
- AC-4: write-log schreibt token_usage ins YAML-Execution-Log
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
HOOK_SCRIPT = HOOKS_DIR / "track_token_usage.py"
WORKFLOW_PY = HOOKS_DIR / "workflow.py"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _make_transcript(turns: list[dict], path: Path) -> None:
    """Erzeugt eine minimale .jsonl-Transcript-Datei mit usage-Daten."""
    with open(path, "w") as f:
        for turn in turns:
            f.write(json.dumps(turn) + "\n")


def _make_assistant_turn(
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_creation: int = 0,
    cache_read: int = 0,
) -> dict:
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": cache_creation,
                "cache_read_input_tokens": cache_read,
            },
        },
    }


def _run_hook(transcript_path: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    """Führt den Stop-Hook mit dem gegebenen Transcript aus."""
    payload = json.dumps({
        "session_id": "test-session-829",
        "transcript_path": str(transcript_path),
        "cwd": str(PROJECT_ROOT),
        "hook_event_name": "Stop",
        "reason": "test",
    })
    hook_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        env=hook_env,
    )


# ─── AC-1: Stop-Hook schreibt token_usage in Workflow-State ──────────────────

class TestAC1StopHookWritesTokenUsage:
    """
    GIVEN: Aktiver Workflow + Session-Transcript mit bekannten usage-Daten
    WHEN: Stop-Hook (track_token_usage.py) wird aufgerufen
    THEN: Workflow-State enthält token_usage mit allen vier Zählern > 0
    """

    def test_hook_script_exists(self):
        """track_token_usage.py muss existieren."""
        assert HOOK_SCRIPT.exists(), (
            f"{HOOK_SCRIPT} nicht gefunden — Implementierung fehlt noch"
        )

    def test_stop_hook_writes_token_usage_to_state(self, tmp_path):
        with tempfile.TemporaryDirectory() as wf_dir:
            # Minimale Workflow-State-Datei anlegen
            wf_file = Path(wf_dir) / "829-token-spike.json"
            wf_file.write_text(json.dumps({
                "name": "829-token-spike",
                "current_phase": "phase5_tdd_red",
            }))

            # Transcript mit 2 Turns
            transcript = tmp_path / "session.jsonl"
            _make_transcript([
                _make_assistant_turn(input_tokens=200, output_tokens=80,
                                     cache_creation=5000, cache_read=10000),
                _make_assistant_turn(input_tokens=10, output_tokens=30,
                                     cache_creation=0, cache_read=20000),
            ], transcript)

            result = _run_hook(transcript, env={
                "GZ_ACTIVE_WORKFLOW": "829-token-spike",
                "GZ_WORKFLOW_ROOT": wf_dir,
            })

            assert result.returncode == 0, (
                f"Stop-Hook schlug fehl (exit {result.returncode}):\n{result.stderr}"
            )

            state = json.loads(wf_file.read_text())
            assert "token_usage" in state, (
                f"token_usage fehlt im State. State-Inhalt: {state}"
            )
            usage = state["token_usage"]
            assert usage.get("input_tokens") == 210, f"input_tokens falsch: {usage}"
            assert usage.get("output_tokens") == 110, f"output_tokens falsch: {usage}"
            assert usage.get("cache_creation_tokens") == 5000, f"cache_creation falsch: {usage}"
            assert usage.get("cache_read_tokens") == 30000, f"cache_read falsch: {usage}"


# ─── AC-2: Kumulation über mehrere Sessions ──────────────────────────────────

class TestAC2Accumulation:
    """
    GIVEN: Workflow-State hat bereits token_usage aus Vorgänger-Session
    WHEN: Stop-Hook einer zweiten Session wird aufgerufen
    THEN: Zähler werden kumuliert, nicht überschrieben
    """

    def test_token_usage_accumulates_across_sessions(self, tmp_path):
        with tempfile.TemporaryDirectory() as wf_dir:
            wf_file = Path(wf_dir) / "829-token-spike.json"
            wf_file.write_text(json.dumps({
                "name": "829-token-spike",
                "current_phase": "phase5_tdd_red",
                # Vorheriger Session-Wert
                "token_usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_tokens": 20000,
                    "cache_read_tokens": 80000,
                },
            }))

            transcript = tmp_path / "session2.jsonl"
            _make_transcript([
                _make_assistant_turn(input_tokens=100, output_tokens=50,
                                     cache_creation=1000, cache_read=5000),
            ], transcript)

            result = _run_hook(transcript, env={
                "GZ_ACTIVE_WORKFLOW": "829-token-spike",
                "GZ_WORKFLOW_ROOT": wf_dir,
            })
            assert result.returncode == 0

            state = json.loads(wf_file.read_text())
            usage = state["token_usage"]
            assert usage["input_tokens"] == 1100, f"Kumulation input falsch: {usage}"
            assert usage["output_tokens"] == 550, f"Kumulation output falsch: {usage}"
            assert usage["cache_creation_tokens"] == 21000, f"Kumulation cache_creation falsch: {usage}"
            assert usage["cache_read_tokens"] == 85000, f"Kumulation cache_read falsch: {usage}"


# ─── AC-3: Kein aktiver Workflow → exit 0, keine State-Änderung ──────────────

class TestAC3NoActiveWorkflow:
    """
    GIVEN: GZ_ACTIVE_WORKFLOW ist nicht gesetzt
    WHEN: Stop-Hook wird aufgerufen
    THEN: exit 0, keine Datei wird verändert
    """

    def test_no_active_workflow_exits_cleanly(self, tmp_path):
        transcript = tmp_path / "session.jsonl"
        _make_transcript([
            _make_assistant_turn(input_tokens=500, output_tokens=200),
        ], transcript)

        env_without_workflow = {k: v for k, v in os.environ.items()
                                if k != "GZ_ACTIVE_WORKFLOW"}

        result = _run_hook(transcript, env=env_without_workflow)

        assert result.returncode == 0, (
            f"Hook bei fehlendem GZ_ACTIVE_WORKFLOW schlug fehl:\n{result.stderr}"
        )

    def test_no_workflow_does_not_create_state_files(self, tmp_path):
        with tempfile.TemporaryDirectory() as wf_dir:
            transcript = tmp_path / "session.jsonl"
            _make_transcript([
                _make_assistant_turn(input_tokens=100, output_tokens=50),
            ], transcript)

            before_files = set(Path(wf_dir).iterdir())
            env_without_workflow = {k: v for k, v in os.environ.items()
                                    if k != "GZ_ACTIVE_WORKFLOW"}
            env_without_workflow["GZ_WORKFLOW_ROOT"] = wf_dir

            _run_hook(transcript, env=env_without_workflow)

            after_files = set(Path(wf_dir).iterdir())
            assert after_files == before_files, (
                f"Unerwartete neue Dateien: {after_files - before_files}"
            )


# ─── AC-4: write-log schreibt token_usage ins YAML-Log ──────────────────────

class TestAC4WriteLogIncludesTokenUsage:
    """
    GIVEN: Workflow-State enthält token_usage
    WHEN: workflow.py write-log success wird aufgerufen
    THEN: YAML-Execution-Log enthält token_usage-Block mit allen vier Zählern
    """

    def test_write_log_includes_token_usage(self, tmp_path):
        with tempfile.TemporaryDirectory() as wf_dir:
            log_dir = Path(wf_dir) / "_log"
            log_dir.mkdir()

            wf_file = Path(wf_dir) / "829-token-spike.json"
            wf_file.write_text(json.dumps({
                "name": "829-token-spike",
                "current_phase": "phase5_tdd_red",
                "phase_transitions": [],
                "token_usage": {
                    "input_tokens": 5000,
                    "output_tokens": 2000,
                    "cache_creation_tokens": 100000,
                    "cache_read_tokens": 500000,
                },
            }))

            result = subprocess.run(
                [sys.executable, str(WORKFLOW_PY), "write-log", "success"],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "GZ_ACTIVE_WORKFLOW": "829-token-spike",
                    "GZ_WORKFLOW_ROOT": wf_dir,
                },
                cwd=str(PROJECT_ROOT),
            )

            assert result.returncode == 0, (
                f"write-log schlug fehl:\n{result.stderr}"
            )

            log_files = list(log_dir.glob("*.yaml"))
            assert log_files, "Kein YAML-Log geschrieben"

            log_data = yaml.safe_load(log_files[0].read_text())
            assert "token_usage" in log_data, (
                f"token_usage fehlt im YAML-Log. Felder: {list(log_data.keys())}"
            )
            usage = log_data["token_usage"]
            assert usage.get("input_tokens") == 5000
            assert usage.get("output_tokens") == 2000
            assert usage.get("cache_creation_tokens") == 100000
            assert usage.get("cache_read_tokens") == 500000
