#!/usr/bin/env python3
"""
PostToolUse hook: Auto-restart server after git commit.

Detects git commit in Bash commands and restarts the NiceGUI web server
so the running process always has the latest code.

CORRECT command: python3 -m src.web.main (NOT src.app.cli!)
Port 8080 is hardcoded in src/web/main.py.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Issue #1431: gemeinsame, tokenbasierte git-Aufrufform-Erkennung aus hook_utils.
#
# UEBERGANGS-RUECKFALL — NACH AUSLIEFERUNG DES PLUGINS ENTFERNEN (Issue #1431).
# Der except-Zweig ist eine ZWEITFASSUNG GENAU DES DEFEKTS, den #1431 beseitigt:
# er erkennt `git -C /pfad commit` nicht. Er existiert nur, solange eine
# Plugin-Fassung OHNE `is_git_subcommand` installiert sein kann (der Shim
# .claude/hooks/hook_utils.py laedt die ausgelieferte Cache-Fassung). Sobald die
# neue Fassung ausgeliefert ist: try/except loeschen, Import direkt stellen.
# Der Rueckfall ist hier bewusst ENGER als die frueheren Teilstring-Bedingungen
# — er startet im Zweifel NICHT neu, statt faelschlich neu zu starten.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from hook_utils import is_git_subcommand
except Exception:  # noqa: BLE001 — Plugin fehlt/veraltet: konservativ, kein Neustart
    def is_git_subcommand(command: str, subcommand: str) -> bool:
        return f"git {subcommand}" in command


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Only act on Bash tool calls
    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        return

    # Issue #1431: Die frueheren zwei Teilstring-Bedingungen hatten keinen
    # Positionsbezug — `git log --oneline | grep -c " commit "` erfuellte beide
    # und loeste `sudo systemctl restart` des LIVE-Dienstes aus.
    command = hook_input.get("tool_input", {}).get("command", "")
    if not is_git_subcommand(command, "commit"):
        return

    # Check if commit clearly failed — restart is the default
    # tool_response structure varies, so extract stdout robustly
    tool_response = hook_input.get("tool_response", {})
    response_text = ""
    if isinstance(tool_response, str):
        response_text = tool_response
    elif isinstance(tool_response, dict):
        response_text = tool_response.get("stdout", "") or tool_response.get("content", "") or str(tool_response)
    if "nothing to commit" in response_text:
        return

    # --- Server restart ---
    # Check if systemd service is managing the server
    systemd_active = False
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", "gregor_zwanzig.service"],
            capture_output=True, timeout=5,
        )
        systemd_active = result.returncode == 0
    except Exception:
        pass

    if systemd_active:
        # systemd owns the server — let it handle the restart
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "restart", "gregor_zwanzig.service"],
                capture_output=True, timeout=15,
            )
            if result.returncode == 0:
                print("SERVER AUTO-RESTARTED via systemctl after commit", file=sys.stderr)
            else:
                print(f"WARNING: systemctl restart failed: {result.stderr.decode().strip()}", file=sys.stderr)
        except Exception as e:
            print(f"WARNING: systemctl restart failed: {e}", file=sys.stderr)
        return

    # No systemd service — manual restart (interactive dev session)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "/opt/gregor_zwanziger")

    # Kill existing server on port 8080
    try:
        result = subprocess.run(
            ["fuser", "-k", "8080/tcp"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass

    time.sleep(2)

    # Start new server with CORRECT entry point
    log_path = "/tmp/gregor_server.log"
    try:
        proc = subprocess.Popen(
            ["uv", "run", "python3", "-m", "src.web.main"],
            cwd=project_dir,
            stdout=open(log_path, "w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception as e:
        print(f"SERVER RESTART FAILED: {e}", file=sys.stderr)
        return

    # Wait for server to be ready
    time.sleep(3)

    # Verify server is running
    try:
        result = subprocess.run(
            ["fuser", "8080/tcp"],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            pid = result.stdout.decode().strip()
            print(f"SERVER AUTO-RESTARTED after commit (PID {pid}, port 8080)", file=sys.stderr)
        else:
            print("WARNING: Server restart may have failed — check /tmp/gregor_server.log", file=sys.stderr)
    except Exception:
        print("WARNING: Could not verify server restart", file=sys.stderr)


if __name__ == "__main__":
    main()
