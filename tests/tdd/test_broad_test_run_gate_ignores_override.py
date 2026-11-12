"""Waechter fuer #2227: ``override`` oeffnet das Testlauf-Gate nicht mehr.

SPEC: docs/specs/modules/fix_2227_override_zwei_gates.md (AC-1 bis AC-4)

Das Freigabe-Wort ``override`` erzeugt im Plugin ein Token, das an den
Workflow-Namen gebunden ist, nicht an eine Sperre. Bisher oeffnete es damit auch
``broad_test_run_gate.py`` fuer beliebig viele breite pytest-Laeufe (1 h) --
genau so lief am 2026-08-10 (#1660 B) ein pytest ohne Socket-Sperre, der Weg des
Produktiv-Versands aus #1477. Seit #1755 gibt es den sicheren Offline-Volllauf;
der Override-Ausgang entfaellt ersatzlos.

Kein Mock-Theater: der echte Hook laeuft als Subprozess mit JSON-Payload auf
stdin. Das Token erzeugt der ECHTE Plugin-Erzeuger (``override_token.create_token``)
unter einem temporaeren Projekt-Root, der aktive Workflow steht dort in
``.claude/active_workflow`` -- dieselbe Aufloesung, die der Hook ueber
``hook_utils`` benutzt. ``test_anordnung_token_ist_fuer_das_plugin_gueltig``
belegt, dass das Token in genau dieser Anordnung gueltig und dem aktiven
Workflow zugeordnet ist; ein Exit 2 der Blockfaelle ist also kein Zufallstreffer
eines nicht gefundenen Tokens.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
HOOK = ROOT / ".claude" / "hooks" / "broad_test_run_gate.py"
HOOKS_DIR = ROOT / ".claude" / "hooks"

sys.path.insert(0, str(HOOKS_DIR))
gate = pytest.importorskip("broad_test_run_gate")

WORKFLOW = "fix-2227-testlauf-gate-probe"


def _plugin_hooks_dir() -> Path:
    registry = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    data = json.loads(registry.read_text())
    for key, entries in data.get("plugins", {}).items():
        if key.startswith("agent-os-openspec@"):
            entry = next((e for e in entries if e.get("scope") == "user"), entries[0])
            return Path(entry["installPath"]) / "core" / "hooks"
    raise RuntimeError("agent-os-openspec nicht installiert")


def _env(root: Path) -> dict:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env.pop("OPENSPEC_ACTIVE_WORKFLOW", None)
    env.pop("GZ_ACTIVE_WORKFLOW", None)
    # Wie auf dem Server (UTC). Das Plugin schreibt ``created`` als naive
    # Ortszeit, der bisherige Leser im Gate deutete naive Zeiten als UTC. Unter
    # der Test-TZ aus conftest.py (America/St_Johns, UTC-3:30) galt das Token
    # dort deshalb als abgelaufen -- ein Exit 2 waere ein Zufallstreffer.
    env["TZ"] = "UTC"
    return env


def _make_root(tmp_path: Path, *, with_token: bool) -> Path:
    """Temp-Projekt-Root (Haupt-Repo-Form: ``.git`` ist ein Verzeichnis) mit
    aktivem Workflow; auf Wunsch mit frischem Token vom echten Plugin-Erzeuger."""
    root = tmp_path / "proj"
    (root / ".git").mkdir(parents=True)
    (root / ".claude" / "workflows").mkdir(parents=True)
    (root / ".claude" / "active_workflow").write_text(WORKFLOW + "\n")
    (root / ".claude" / "workflows" / f"{WORKFLOW}.json").write_text("{}")
    if with_token:
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "import override_token; override_token.create_token(sys.argv[2])"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code, str(_plugin_hooks_dir()), WORKFLOW],
            cwd=str(root), env=_env(root), capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        assert (root / ".claude" / "user_override_token.json").exists()
    return root


def _run_gate(root: Path, command: str) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload, capture_output=True, text=True,
        cwd=str(root), env=_env(root), timeout=30,
    )


@pytest.fixture
def token_root(tmp_path):
    return _make_root(tmp_path, with_token=True)


@pytest.fixture
def plain_root(tmp_path):
    return _make_root(tmp_path, with_token=False)


# ---------------------------------------------------------------------------
# Anordnung: das Token waere in genau dieser Umgebung gueltig
# ---------------------------------------------------------------------------

def test_anordnung_token_ist_fuer_das_plugin_gueltig(token_root):
    """Kontrollfall: in derselben Umgebung loest ``hook_utils`` den Workflow
    auf, und das Plugin haelt das Token fuer gueltig. Ohne diesen Nachweis
    waere ein Exit 2 unten auch mit nicht gefundenem Token erklaerbar."""
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2]);"
        "import hook_utils, override_token;"
        "n = hook_utils.get_active_workflow_name();"
        "print(n, override_token.has_valid_token(n), hook_utils.find_project_root())"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, str(HOOKS_DIR), str(_plugin_hooks_dir())],
        cwd=str(token_root), env=_env(token_root), capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    name, valid, found_root = proc.stdout.split()
    assert name == WORKFLOW
    assert valid == "True"
    assert Path(found_root).resolve() == token_root.resolve()

    # Auch in der Lesart des bisherigen Gate-Lesers (naive Zeit = UTC, TTL 1 h)
    # ist das Token frisch.
    from datetime import datetime, timedelta, timezone
    data = json.loads((token_root / ".claude" / "user_override_token.json").read_text())
    created = datetime.fromisoformat(data["tokens"][WORKFLOW]["created"])
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    assert abs(datetime.now(timezone.utc) - created) <= timedelta(minutes=5)


# ---------------------------------------------------------------------------
# AC-1: normaler (zerlegbarer) Pfad blockt trotz gueltigem Token
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    ["uv run pytest", "uv run pytest tests/", "uv run pytest -q tests/tdd/"],
    ids=["volllauf", "verzeichnis", "unterverzeichnis"],
)
def test_ac1_breiter_lauf_blockt_trotz_override(token_root, command):
    proc = _run_gate(token_root, command)
    assert proc.returncode == 2, (
        f"Override-Token oeffnet das Testlauf-Gate noch (Exit {proc.returncode})"
    )
    assert "BLOCKED" in proc.stderr


# ---------------------------------------------------------------------------
# AC-2: Roh-Scan-Pfad (sh -c / eval) blockt trotz gueltigem Token
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "command",
    ['sh -c "uv run pytest"', 'bash -c "uv run pytest tests/"', 'eval "uv run pytest"'],
    ids=["sh-c", "bash-c-verzeichnis", "eval"],
)
def test_ac2_roh_scan_blockt_trotz_override(token_root, command):
    proc = _run_gate(token_root, command)
    assert proc.returncode == 2, (
        f"Override-Token oeffnet den Roh-Scan-Pfad noch (Exit {proc.returncode})"
    )
    assert "BLOCKED" in proc.stderr


# ---------------------------------------------------------------------------
# AC-3: erlaubte Wege bleiben frei, mit und ohne Token
# ---------------------------------------------------------------------------

ALLOWED = [
    gate.OFFLINE_CALL,
    gate.OFFLINE_CALL + " > /tmp/x.txt 2>&1",
    "uv run pytest tests/tdd/x.py",
    "uv run pytest --collect-only",
    "uv run pytest --co tests/",
]


@pytest.mark.parametrize("command", ALLOWED, ids=["offline", "offline-umleitung", "datei", "collect-only", "co"])
@pytest.mark.parametrize("with_token", [True, False], ids=["mit-token", "ohne-token"])
def test_ac3_erlaubte_wege_bleiben_frei(tmp_path, command, with_token):
    root = _make_root(tmp_path, with_token=with_token)
    proc = _run_gate(root, command)
    assert proc.returncode == 0, proc.stderr


# ---------------------------------------------------------------------------
# AC-4: Hinweistext nennt keinen Freigabe-/override-Ausgang mehr
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command", ["uv run pytest", 'sh -c "uv run pytest"'], ids=["normal", "roh-scan"])
def test_ac4_hinweis_ohne_override_ausgang(plain_root, command):
    proc = _run_gate(plain_root, command)
    assert proc.returncode == 2
    text = proc.stderr
    assert gate.OFFLINE_CALL in text
    assert "--collect-only" in text
    assert "override" not in text.lower()
    assert "Freigabe des Users" not in text
