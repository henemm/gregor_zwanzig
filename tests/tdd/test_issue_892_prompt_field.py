"""Issue #892 — UserPromptSubmit-Hook muss das echte Payload-Feld `prompt` lesen.

Claude Code übergibt den User-Prompt im UserPromptSubmit-Payload im Feld
`prompt`. Der Hook `phase_listener.py` (via `hook_utils.get_user_message`) las
bislang ausschließlich `user_message` → immer leerer String → kein Steuerwort
(approved/go/stop/override/...) wurde je erkannt.

Diese Tests beweisen Verhalten END-TO-END: sie rufen `phase_listener.py` als
echten Subprozess mit realem Payload auf und prüfen den tatsächlichen
Seiteneffekt (Override-Token-Datei), KEIN Datei-Inhalts-Check des Hook-Codes.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude" / "hooks" / "phase_listener.py"


def _run_hook(payload: dict):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(ROOT)}
    # Kein aktiver Workflow nötig: Override-Token-Pfad arbeitet global (__global__).
    env.pop("OPENSPEC_ACTIVE_WORKFLOW", None)
    env.pop("GZ_ACTIVE_WORKFLOW", None)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


@pytest.fixture
def clean_token_file():
    token_file = ROOT / ".claude" / "user_override_token.json"
    backup = token_file.read_text() if token_file.exists() else None
    if token_file.exists():
        token_file.unlink()
    try:
        yield token_file
    finally:
        if backup is not None:
            token_file.write_text(backup)
        elif token_file.exists():
            token_file.unlink()


def _token_count(token_file: Path) -> int:
    if not token_file.exists():
        return 0
    return len(json.loads(token_file.read_text()).get("tokens", {}))


def test_prompt_field_triggers_override(clean_token_file):
    """Echtes CC-Payload-Feld `prompt` mit 'override' → Override-Token entsteht."""
    result = _run_hook({"prompt": "override"})
    assert result.returncode == 0, f"Hook darf nie blocken: {result.stderr!r}"
    assert _token_count(clean_token_file) > 0, (
        f"Kein Override-Token nach prompt='override' erstellt. "
        f"stderr={result.stderr!r}"
    )


def test_legacy_user_message_still_works(clean_token_file):
    """Rückwärtskompatibilität: altes Feld `user_message` funktioniert weiter."""
    result = _run_hook({"user_message": "override"})
    assert result.returncode == 0, f"Hook darf nie blocken: {result.stderr!r}"
    assert _token_count(clean_token_file) > 0, (
        f"Kein Override-Token nach user_message='override'. stderr={result.stderr!r}"
    )


def test_unrelated_prompt_creates_no_token(clean_token_file):
    """Kontroll-Test: harmloser Prompt löst KEIN Token aus (kein False-Positive)."""
    result = _run_hook({"prompt": "bitte etwas ganz anderes machen"})
    assert result.returncode == 0, f"Hook darf nie blocken: {result.stderr!r}"
    assert _token_count(clean_token_file) == 0, (
        "Harmloser Prompt darf kein Override-Token erzeugen."
    )
