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


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    # Only act on Bash tool calls
    tool_name = hook_input.get("tool_name", "")
    if tool_name != "Bash":
        return

    # Check if command was a git commit
    # Handle both "git commit" and "git -C /path commit" patterns
    command = hook_input.get("tool_input", {}).get("command", "")
    has_git = "git " in command or "git\n" in command
    has_commit = " commit " in command or " commit\n" in command or command.endswith(" commit")
    if not (has_git and has_commit):
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
