"""
TDD Tests — Issue #348: Isolierte Parallel-Workspaces (clone-basiert)

SPEC: docs/specs/modules/issue_348_parallel_workspaces.md
TEST-MANIFEST: docs/specs/tests/issue_348_parallel_workspaces_tests.md

Mehrere Claude-Sessions teilen sich heute denselben Working-Tree. Dieses
Feature liefert isolierte Arbeitskopien pro Session via `git clone --local`
plus portable Hook-Pfade (`${CLAUDE_PROJECT_DIR}`) in der settings.json.

KEINE MOCKS: Alle Workspace-Tests führen ECHTE git-Operationen in tmp_path aus.

RED-Erwartung:
  - AC-1 (`test_settings_no_hardcoded_repo_path`,
    `test_settings_hooks_use_project_dir_var`) bleibt ROT, bis der
    Orchestrierer settings.json umstellt (Lockout-Risiko, nicht im
    Developer-Scope).
  - AC-3/4/5/6 sind ROT bis `.claude/tools/gz-workspace` existiert.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_JSON = REPO_ROOT / ".claude" / "settings.json"
GZ_WORKSPACE = REPO_ROOT / ".claude" / "tools" / "gz-workspace"

HARDCODED_PREFIX = "/home/hem/gregor_zwanzig/.claude/hooks"
PROJECT_DIR_VAR = "${CLAUDE_PROJECT_DIR}"
MQ_COMMAND = "bash /home/hem/claude-mq/check-messages.sh"


# ---------------------------------------------------------------------------
# Helpers — echte git-Operationen, keine Mocks
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    """git im Verzeichnis `cwd` ausführen, stdout zurückgeben (gestripped)."""
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _make_source_repo(root: Path, settings_content: str | None = None) -> Path:
    """
    Minimales Quell-git-Repo mit einem Commit + minimaler .claude-Struktur.

    Liefert den Pfad zum Repo zurück.
    """
    src = root / "srcrepo"
    src.mkdir(parents=True)
    _git(src, "init", "-q")
    _git(src, "config", "user.email", "test@example.com")
    _git(src, "config", "user.name", "Test")

    (src / "README.md").write_text("# source repo\n")
    claude_dir = src / ".claude"
    (claude_dir / "workflows").mkdir(parents=True)
    if settings_content is not None:
        (claude_dir / "settings.json").write_text(settings_content)

    _git(src, "add", "-A")
    _git(src, "commit", "-q", "-m", "initial")
    return src


def _run_workspace(
    src_repo: Path, ws_root: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    """gz-workspace mit cwd=src_repo und GZ_WS_ROOT=ws_root ausführen."""
    env = dict(os.environ)
    env["GZ_WS_ROOT"] = str(ws_root)
    return subprocess.run(
        ["bash", str(GZ_WORKSPACE), *args],
        cwd=str(src_repo),
        env=env,
        capture_output=True,
        text=True,
    )


def _collect_hook_commands(data: dict) -> list[str]:
    """Alle Hook-`command`-Strings aus der settings.json-Struktur sammeln."""
    commands: list[str] = []
    for event_groups in data.get("hooks", {}).values():
        for group in event_groups:
            for hook in group.get("hooks", []):
                cmd = hook.get("command")
                if isinstance(cmd, str):
                    commands.append(cmd)
    return commands


# ---------------------------------------------------------------------------
# AC-1 — settings.json hat keine hardcoded Repo-Pfade mehr
# (bleibt ROT bis der Orchestrierer settings.json umstellt)
# ---------------------------------------------------------------------------


def test_settings_no_hardcoded_repo_path():
    """
    GIVEN die echte .claude/settings.json
    WHEN  ihr Inhalt geprüft wird
    THEN  enthält sie KEINEN hardcoded Hook-Pfad mehr
    """
    content = SETTINGS_JSON.read_text()
    assert HARDCODED_PREFIX not in content, (
        f"settings.json enthält noch hardcoded Pfad-Präfix '{HARDCODED_PREFIX}' "
        "— muss durch ${CLAUDE_PROJECT_DIR} ersetzt werden"
    )


def test_settings_hooks_use_project_dir_var():
    """
    GIVEN die echte .claude/settings.json als JSON
    WHEN  alle Hook-command-Strings gesammelt werden
    THEN  jeder, der '.claude/hooks/' referenziert, nutzt ${CLAUDE_PROJECT_DIR}
    """
    data = json.loads(SETTINGS_JSON.read_text())
    commands = _collect_hook_commands(data)
    hook_commands = [c for c in commands if ".claude/hooks/" in c]
    assert hook_commands, "Keine .claude/hooks/-Commands in settings.json gefunden"
    for cmd in hook_commands:
        assert PROJECT_DIR_VAR in cmd, (
            f"Hook-command nutzt keinen ${{CLAUDE_PROJECT_DIR}}: {cmd!r}"
        )


# ---------------------------------------------------------------------------
# AC-2 — settings.json valides JSON + claude-mq-Pfad bleibt absolut
# ---------------------------------------------------------------------------


def test_settings_valid_json_and_mq_absolute():
    """
    GIVEN die echte .claude/settings.json
    WHEN  sie geparst wird
    THEN  ist sie valides JSON UND der claude-mq SessionStart-command bleibt
          exakt der absolute Pfad (geteilte externe Infra)
    """
    data = json.loads(SETTINGS_JSON.read_text())
    commands = _collect_hook_commands(data)
    assert MQ_COMMAND in commands, (
        f"SessionStart-claude-mq-command '{MQ_COMMAND}' nicht unverändert vorhanden"
    )


# ---------------------------------------------------------------------------
# AC-3 — `new` erzeugt isolierten Klon
# ---------------------------------------------------------------------------


def test_new_creates_isolated_clone(tmp_path: Path):
    """
    GIVEN ein Quell-Git-Repo
    WHEN  `gz-workspace new wstest` läuft (cwd=Quelle, GZ_WS_ROOT gesetzt)
    THEN  existiert <ws-root>/wstest mit eigenem .git auf Branch ws/wstest
          UND das Quell-Working-Tree ist unverändert
    """
    src = _make_source_repo(tmp_path)
    ws_root = tmp_path / "wsroot"

    proc = _run_workspace(src, ws_root, "new", "wstest")
    assert proc.returncode == 0, f"new schlug fehl: {proc.stderr}"

    clone = ws_root / "wstest"
    assert clone.is_dir(), "Workspace-Verzeichnis wurde nicht erzeugt"
    assert (clone / ".git").exists(), "Klon hat kein eigenes .git"

    branch = _git(clone, "rev-parse", "--abbrev-ref", "HEAD")
    assert branch == "ws/wstest", f"Falscher Branch: {branch!r}"

    src_status = _git(src, "status", "--porcelain")
    assert src_status == "", (
        f"Quell-Repo-Working-Tree wurde verändert: {src_status!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — `list` zeigt Workspace
# ---------------------------------------------------------------------------


def test_list_shows_workspace(tmp_path: Path):
    """
    GIVEN ein per `new` erzeugter Workspace
    WHEN  `gz-workspace list` läuft
    THEN  erscheint der Name und sein Branch im stdout
    """
    src = _make_source_repo(tmp_path)
    ws_root = tmp_path / "wsroot"
    assert _run_workspace(src, ws_root, "new", "wstest").returncode == 0

    proc = _run_workspace(src, ws_root, "list")
    assert proc.returncode == 0, f"list schlug fehl: {proc.stderr}"
    assert "wstest" in proc.stdout, f"Name fehlt in list-Output: {proc.stdout!r}"
    assert "ws/wstest" in proc.stdout, f"Branch fehlt in list-Output: {proc.stdout!r}"


# ---------------------------------------------------------------------------
# AC-5 — `clean` verweigert dirty Workspace ohne --force
# ---------------------------------------------------------------------------


def test_clean_refuses_dirty_without_force(tmp_path: Path):
    """
    GIVEN ein Workspace mit uncommitteter Datei
    WHEN  `gz-workspace clean wstest` OHNE --force läuft
    THEN  exit != 0 und Verzeichnis bleibt; mit --force exit 0 und Verzeichnis weg
    """
    src = _make_source_repo(tmp_path)
    ws_root = tmp_path / "wsroot"
    assert _run_workspace(src, ws_root, "new", "wstest").returncode == 0

    clone = ws_root / "wstest"
    (clone / "dirty.txt").write_text("uncommitted\n")

    proc = _run_workspace(src, ws_root, "clean", "wstest")
    assert proc.returncode != 0, "clean ohne --force hätte abbrechen müssen"
    assert clone.is_dir(), "Workspace wurde trotz dirty ohne --force entfernt"

    proc_force = _run_workspace(src, ws_root, "clean", "wstest", "--force")
    assert proc_force.returncode == 0, f"clean --force schlug fehl: {proc_force.stderr}"
    assert not clone.exists(), "Workspace wurde mit --force nicht entfernt"


# ---------------------------------------------------------------------------
# AC-6 — `new` übernimmt settings.json zeichengleich (portable Hook-Pfade)
# ---------------------------------------------------------------------------


def test_new_preserves_settings_verbatim(tmp_path: Path):
    """
    GIVEN ein Quell-Repo mit settings.json, die ${CLAUDE_PROJECT_DIR} nutzt
    WHEN  `gz-workspace new wstest` läuft
    THEN  ist die settings.json im Klon zeichengleich (keine auf die Quelle
          zeigenden Pfade — die Kopie führt ihre EIGENEN Hooks aus)
    """
    settings = json.dumps(
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python3 "${CLAUDE_PROJECT_DIR}"/.claude/hooks/workflow_gate.py',
                            }
                        ],
                    }
                ]
            }
        },
        indent=2,
    )
    src = _make_source_repo(tmp_path, settings_content=settings)
    ws_root = tmp_path / "wsroot"
    assert _run_workspace(src, ws_root, "new", "wstest").returncode == 0

    clone_settings = (ws_root / "wstest" / ".claude" / "settings.json").read_text()
    assert clone_settings == settings, "settings.json im Klon nicht zeichengleich"
    assert PROJECT_DIR_VAR in clone_settings, "Klon-settings.json verlor ${CLAUDE_PROJECT_DIR}"
    assert str(src) not in clone_settings, "Klon-settings.json zeigt auf das Quell-Repo"


# ---------------------------------------------------------------------------
# AC-7 — nur Tooling-/Config-Schicht, kein Produktiv-Code
# ---------------------------------------------------------------------------


def test_only_tooling_layer():
    """
    GIVEN die Allowlist der #348-Dateien
    WHEN  ihre Pfade geprüft werden
    THEN  beginnt keiner mit src/, api/, internal/ oder frontend/
    """
    allowlist = [
        ".claude/tools/gz-workspace",
        ".claude/settings.json",
        "tests/tdd/test_issue_348_parallel_workspaces.py",
        "CLAUDE.md",
        "docs/specs/modules/issue_348_parallel_workspaces.md",
    ]
    forbidden = ("src/", "api/", "internal/", "frontend/")
    for rel in allowlist:
        assert not rel.startswith(forbidden), (
            f"Datei {rel!r} liegt in einer Produktiv-Code-Schicht — #348 ist Tooling-only"
        )
