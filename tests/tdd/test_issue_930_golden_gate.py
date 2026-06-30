"""
TDD RED Phase — Issue #930: Golden-Email-Gate

Drei Tests die ALLE JETZT FEHLSCHLAGEN, weil:
- renderer_mail_gate.py hat noch keinen golden_ok-Check (AC-1)
- tests/golden/email/regenerate.py existiert noch nicht (AC-2)
- settings.json hat noch keinen PreToolUse:Bash-Hook (AC-3)

Spec: docs/specs/modules/issue_930_golden_gate.md
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).parents[2]


def test_renderer_mail_gate_has_golden_check():
    """AC-1: renderer_mail_gate._do_hook() muss einen golden_ok-Check haben.

    Das Gate muss bei korrupten/veralteten Golden-Snapshots mit Exit 2 +
    Hinweis auf regenerate.py blockieren. Aktuell fehlt dieser Check
    vollstaendig — das Gate gibt bei korruptem Golden Exit 0 (no-op).
    """
    gate_path = REPO_ROOT / ".claude" / "hooks" / "renderer_mail_gate.py"
    source = gate_path.read_text()
    assert "golden_ok" in source, (
        "renderer_mail_gate.py hat noch keinen golden_ok-Check. "
        "AC-1 erfordert: pytest tests/golden/email/ als Gate-Bedingung, "
        "mit Exit 2 + Hinweis auf tests/golden/email/regenerate.py."
    )


def test_regenerate_script_exists():
    """AC-2: tests/golden/email/regenerate.py muss existieren.

    Das Skript wird im Block-Message des Gates als Abhilfe referenziert.
    Ohne das Skript waere die Fehlermeldung irreführend — Nutzer koennen
    nicht regenerieren was nicht existiert.
    """
    regen_path = REPO_ROOT / "tests" / "golden" / "email" / "regenerate.py"
    assert regen_path.exists(), (
        "tests/golden/email/regenerate.py fehlt. "
        "Wird vom renderer_mail_gate.py als Abhilfe im Block-Message referenziert. "
        "Muss Golden-Snapshots neu generieren koennen."
    )


# doc-compliance-test
def test_settings_json_has_preToolUse_renderer_gate():
    """AC-3: settings.json hat einen PreToolUse:Bash-Hook fuer renderer_mail_gate.py.

    Seit Commit ede10a2d ist das Gate aus settings.json entfernt worden und
    wird NIE aufgerufen. Jede Renderer-Aenderung kann ungesichert committed
    werden — das Gate existiert nur noch auf dem Papier.
    """
    settings_path = REPO_ROOT / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text())
    pretooluse_blocks = settings.get("hooks", {}).get("PreToolUse", [])
    has_renderer_gate = any(
        "renderer_mail_gate" in json.dumps(block)
        for block in pretooluse_blocks
    )
    assert has_renderer_gate, (
        "settings.json hat keinen PreToolUse:Bash-Hook fuer renderer_mail_gate.py. "
        "Das Gate wird nie aufgerufen! "
        "Ein PreToolUse-Block mit matcher='Bash' und command='...renderer_mail_gate.py' "
        "muss in .claude/settings.json eingetragen sein."
    )
