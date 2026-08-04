"""Commit-Gates erkennen die git-Aufrufform, nicht nur die Zeichenfolge (#1431).

Die Gates in `.claude/hooks/` entschieden ueber `"git commit" in command`, ob
sie ueberhaupt pruefen. Jede Aufrufform mit etwas zwischen `git` und dem
Unterbefehl (`git -C /pfad commit`, `git -c k=v commit`, `git --no-pager
commit`) umging sie **still**; umgekehrt schlugen sie bei blosser Erwaehnung
(`grep -rn "git commit" …`) an.

Geprueft wird die WIRKUNG am Ort der Zusicherung, nicht nur die Erkennung:

* `renderer_mail_gate` blockt eine gestagte Mail-Inhalts-Datei ohne Nachweis
  auch dann, wenn der Commit als `git -C /pfad commit` geschrieben ist —
  und blockt einen `grep`, der die Zeichenfolge nur nennt, NICHT mehr.
* `auto_restart_server` startet den Dienst bei einem Diagnose-Kommando
  (`git log --oneline | grep -c " commit "`) NICHT mehr neu.

Keine Mocks: echte Hook-Subprozesse, echtes git-Repo, echte Dateien. Der
Server-Neustart wird nicht abgefangen, sondern ueber PATH-Stubs sichtbar und
folgenlos gemacht.
"""

from __future__ import annotations

# Plugin-Sonde (#1196, Vorbild test_issue_811_renderer_gate.py): die Hooks
# dieser Suite laufen ueber hook_utils, einen Shim auf das installierte
# agent-os-openspec-Plugin. Ohne Plugin (CI-Runner, Web-Sessions) sauber
# ueberspringen statt rot — auf dem Server (Plugin vorhanden) laeuft alles.
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
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS = REPO_ROOT / ".claude" / "hooks"


# --------------------------------------------------------------------- #
# Hilfen
# --------------------------------------------------------------------- #

def _plugin_hook_utils() -> Path:
    """Die hook_utils-Fassung, gegen die die Repo-Hooks laufen.

    `.claude/hooks/hook_utils.py` ist nur ein Shim auf die installierte
    Plugin-Fassung. Quelle der Wahrheit ist das Plugin-Repo; der ausgelieferte
    Cache ist eine Kopie davon und wird nur als Rueckfall genutzt.
    """
    candidates = []
    env = os.environ.get("OPENSPEC_PLUGIN_SRC", "").strip()
    if env:
        candidates.append(Path(env) / "core" / "hooks" / "hook_utils.py")
    candidates.append(Path.home() / "agent-os-openspec" / "core" / "hooks" / "hook_utils.py")
    try:
        registry = json.loads(
            (Path.home() / ".claude" / "plugins" / "installed_plugins.json").read_text()
        )
        for key, entries in registry.get("plugins", {}).items():
            if key.startswith("agent-os-openspec@"):
                entry = next((e for e in entries if e.get("scope") == "user"), entries[0])
                if entry.get("installPath"):
                    candidates.append(
                        Path(entry["installPath"]) / "core" / "hooks" / "hook_utils.py"
                    )
    except (OSError, ValueError, KeyError, IndexError):
        pass
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    pytest.fail("Keine hook_utils-Fassung gefunden — Plugin weder als Quelle noch installiert.")


def _hookbin(tmp_path: Path, hook_name: str) -> Path:
    """Isolierte Kopie eines Repo-Hooks samt echter hook_utils-Fassung."""
    binder = tmp_path / "hookbin"
    binder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HOOKS / hook_name, binder / hook_name)
    shutil.copy2(_plugin_hook_utils(), binder / "hook_utils.py")
    return binder / hook_name


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _mail_repo(tmp_path: Path) -> Path:
    """Git-Repo mit gestagter Mail-Inhalts-Datei und aktivem Workflow ohne Nachweis."""
    repo = tmp_path / "repo"
    (repo / "src" / "output" / "renderers" / "email").mkdir(parents=True)
    (repo / ".claude" / "workflows").mkdir(parents=True)
    _git(repo.parent, "init", "-q", str(repo))
    (repo / "src" / "output" / "renderers" / "email" / "compare_html.py").write_text(
        "# Mail-Inhalt\n"
    )
    _git(repo, "add", "src/output/renderers/email/compare_html.py")
    (repo / ".claude" / "active_workflow").write_text("sandboxwf\n")
    (repo / ".claude" / "workflows" / "sandboxwf.json").write_text(
        json.dumps({"name": "sandboxwf", "current_phase": "phase6_implement"})
    )
    return repo


def _run_hook(hook: Path, command: str, cwd: Path, extra_env: dict | None = None):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(cwd)
    env["CLAUDE_TOOL_INPUT"] = json.dumps({"command": command})
    env.pop("GZ_HOOK_TOOL_INPUT", None)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(hook)],
        cwd=str(cwd),
        env=env,
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        timeout=90,
    )


# --------------------------------------------------------------------- #
# renderer_mail_gate — Wirkung am Ort der Zusicherung
# --------------------------------------------------------------------- #

def test_mail_gate_blockt_alternative_aufrufform(tmp_path):
    """`git -C /pfad commit` mit gestagter Mail-Datei und ohne Nachweis -> Block.

    Vorher lief genau diese Form ungeprueft durch — das ist der Vorfall aus
    #1431 (zwei Mail-Renderer-Dateien committet, Gate lief nie).
    """
    repo = _mail_repo(tmp_path)
    hook = _hookbin(tmp_path, "renderer_mail_gate.py")
    proc = _run_hook(hook, f'git -C {repo} commit -m "wip"', repo)
    assert proc.returncode == 2, (
        "Mail-Nachweispflicht bleibt ueber die Aufrufform umgehbar: "
        f"rc={proc.returncode} err={proc.stderr!r}"
    )


def test_mail_gate_blockt_weiterhin_kanonische_form(tmp_path):
    repo = _mail_repo(tmp_path)
    hook = _hookbin(tmp_path, "renderer_mail_gate.py")
    proc = _run_hook(hook, 'git commit -m "wip"', repo)
    assert proc.returncode == 2, proc.stderr


@pytest.mark.parametrize("template", [
    # Adversary F002: Trenner ohne umgebende Leerzeichen
    'cd /tmp&&git -C {repo} commit -m "wip"',
    # Adversary F001: Zeilenumbruch als Trenner
    'cd /tmp\ngit -C {repo} commit -m "wip"',
])
def test_mail_gate_blockt_verkettete_aufrufform(tmp_path, template):
    """Auch verkettete Schreibweisen muessen die Nachweispflicht ausloesen."""
    repo = _mail_repo(tmp_path)
    hook = _hookbin(tmp_path, "renderer_mail_gate.py")
    proc = _run_hook(hook, template.format(repo=repo), repo)
    assert proc.returncode == 2, (
        "Verkettete Aufrufform umgeht die Mail-Nachweispflicht: "
        f"rc={proc.returncode} err={proc.stderr!r}"
    )


def test_mail_gate_blockt_keine_blosse_erwaehnung(tmp_path):
    """Ein `grep` nach der Zeichenfolge ist kein Commit und darf nicht blocken."""
    repo = _mail_repo(tmp_path)
    hook = _hookbin(tmp_path, "renderer_mail_gate.py")
    proc = _run_hook(hook, 'grep -rn "git commit" .claude/hooks/', repo)
    assert proc.returncode == 0, (
        f"Erwaehnung blockiert weiterhin: rc={proc.returncode} err={proc.stderr!r}"
    )


# --------------------------------------------------------------------- #
# pendant_gate — Pendant-Sperre (#1481 B), gleiche Aufrufform-Zusicherung
# --------------------------------------------------------------------- #

def _pendant_repo(tmp_path: Path) -> Path:
    """Git-Repo mit gestagter NEUER Datei im einseitigen Bereich, ohne Begruendung."""
    repo = tmp_path / "pendantrepo"
    einseitig = repo / "frontend" / "src" / "lib" / "components" / "compare"
    einseitig.mkdir(parents=True)
    _git(repo.parent, "init", "-q", str(repo))
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("Ausgangsstand\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Ausgangsstand")
    (einseitig / "Ortsliste.svelte").write_text('<script lang="ts">\n</script>\n')
    _git(repo, "add", "-A")
    return repo


@pytest.mark.parametrize("template", [
    # Vorspann-Programm — frueher liess `sudo` die Erkennung noch zu, `timeout` nicht
    'sudo git commit -m "wip"',
    'timeout 30 git commit -m "wip"',
    # Adversary F001 aus #1431: Zeilenumbruch als Trenner
    'echo start\ngit commit -m "wip"',
    # Adversary F002 aus #1431: Trenner ohne umgebende Leerzeichen
    'echo start&&git commit -m "wip"',
])
def test_pendant_gate_greift_bei_alternativer_aufrufform(tmp_path, template):
    """Die Pendant-Sperre erkennt den Commit an der Aufrufform, nicht am Wortlaut (AC-11).

    Ein Waechter, der auf `"git commit" in befehl` prueft, laesst sich ueber die
    Schreibweise still umgehen — genau der Vorfall aus #1431.

    Die Vorlagen nannten hier bis 2026-08-04 `git -C <pfad>`. Seit dem Rueckbau (F010)
    ist ein `-C` das ausdrueckliche Zeichen dafuer, dass anderswo committet wird — der
    Waechter laesst solche Aufrufe bewusst durch und sagt es. Fuer die Zusicherung dieses
    Tests — greift die Sperre unabhaengig von der Schreibweise? — braucht es deshalb
    Formen, bei denen der Commit HIER stattfindet. Die Zusicherung ist dieselbe
    geblieben, nur die Beispiele passen jetzt zum Entwurf.
    """
    repo = _pendant_repo(tmp_path)
    hook = _hookbin(tmp_path, "pendant_gate.py")
    proc = _run_hook(hook, template, repo)
    assert proc.returncode == 2, (
        "Die Pendant-Sperre bleibt ueber die Aufrufform umgehbar: "
        f"rc={proc.returncode} err={proc.stderr!r}"
    )
    assert "Ortsliste.svelte" in proc.stderr, (
        "Exit 2 allein beweist nichts (ein fehlender Waechter liefert denselben Code) — "
        f"die Meldung muss die gestagte Datei nennen: {proc.stderr!r}"
    )


def test_pendant_gate_blockt_keine_blosse_erwaehnung(tmp_path):
    """Gegenprobe: ein `grep` nach der Zeichenfolge ist kein Commit und darf nicht blocken."""
    repo = _pendant_repo(tmp_path)
    hook = _hookbin(tmp_path, "pendant_gate.py")
    proc = _run_hook(hook, 'grep -rn "git commit" .claude/hooks/', repo)
    assert proc.returncode == 0, (
        f"Blosse Erwaehnung blockiert: rc={proc.returncode} err={proc.stderr!r}"
    )


# --------------------------------------------------------------------- #
# auto_restart_server — kein Neustart bei Diagnose-Kommandos
# --------------------------------------------------------------------- #

def _stub_path(tmp_path: Path) -> tuple[Path, Path]:
    """PATH-Verzeichnis mit protokollierenden Stubs statt echter Systembefehle."""
    stub_dir = tmp_path / "stubbin"
    stub_dir.mkdir(parents=True, exist_ok=True)
    log = tmp_path / "restart_calls.log"
    for name in ("sudo", "systemctl", "fuser", "uv"):
        script = stub_dir / name
        script.write_text(f'#!/bin/sh\necho "$0 $@" >> "{log}"\nexit 1\n')
        script.chmod(0o755)
    return stub_dir, log


def _run_restart_hook(tmp_path: Path, command: str) -> str:
    hook = _hookbin(tmp_path, "auto_restart_server.py")
    stub_dir, log = _stub_path(tmp_path)
    env = {"PATH": f"{stub_dir}:{os.environ.get('PATH', '')}"}
    _run_hook(hook, command, tmp_path, extra_env=env)
    return log.read_text() if log.exists() else ""


@pytest.mark.parametrize("command", [
    'git log --oneline | grep -c " commit "',
    'grep -rn "git commit" .claude/hooks/',
])
def test_diagnose_kommando_startet_keinen_dienst_neu(tmp_path, command):
    """Ein Lesebefehl darf keinen `sudo systemctl restart` des Dienstes ausloesen."""
    calls = _run_restart_hook(tmp_path, command)
    assert calls == "", (
        f"Diagnose-Kommando loeste einen Dienst-Neustart aus: {calls!r}"
    )


def test_echter_commit_startet_weiterhin_neu(tmp_path):
    """Gegenprobe: der Hook wird nicht einfach funktionslos."""
    calls = _run_restart_hook(tmp_path, 'git -C /tmp/x commit -m "wip"')
    assert calls.strip(), "Hook reagiert auf einen echten Commit gar nicht mehr"


# --------------------------------------------------------------------- #
# e2e_commit_gate — Klassifikationshelfer (inert, aber gleiche Bauart)
# --------------------------------------------------------------------- #

def _load_e2e_gate(tmp_path: Path):
    """Hook-Kopie samt echter hook_utils-Fassung laden (nicht ueber den Shim)."""
    import importlib.util

    hook = _hookbin(tmp_path, "e2e_commit_gate.py")
    sys.modules.pop("hook_utils", None)
    sys.path.insert(0, str(hook.parent))
    try:
        spec = importlib.util.spec_from_file_location("e2e_commit_gate_under_test", hook)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(hook.parent))
        sys.modules.pop("hook_utils", None)
    return module


def test_e2e_gate_erkennt_aufrufform_und_ignoriert_erwaehnung(tmp_path):
    gate = _load_e2e_gate(tmp_path)
    assert gate.is_git_commit({"command": 'git -C /repo commit -m "x"'}) is True
    assert gate.is_git_commit({"command": 'grep -rn "git commit" .'}) is False
    assert gate.is_git_commit({"command": 'git -C /repo commit --amend'}) is False
