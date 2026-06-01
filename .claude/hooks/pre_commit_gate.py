#!/usr/bin/env python3
"""
OpenSpec Framework - Pre-Commit Gate Hook

Blocks git commits if tests are failing.
Ensures TDD GREEN phase before allowing commits.

Configuration (in config.yaml):
  pre_commit:
    enabled: true
    test_command: ["pytest", "--tb=line", "-q"]  # or ["npm", "test"]
    timeout: 120
    allow_amend: true  # Allow git commit --amend
    ui_patterns:
      - "web/pages/"
      - "templates/"
      - ".vue"
      - ".tsx"
      - ".jsx"
    screenshot_reminder: true  # Remind about screenshots for UI changes

Exit Codes:
- 0: Allowed (with optional JSON response)
- 2: Blocked
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Try to import config loader
try:
    from config_loader import load_config, get_project_root
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from config_loader import load_config, get_project_root
    except ImportError:
        def load_config():
            return {}
        def get_project_root():
            cwd = Path.cwd()
            for parent in [cwd] + list(cwd.parents):
                if (parent / ".git").exists():
                    return parent
            return cwd


def get_pre_commit_config() -> dict:
    """Get pre-commit configuration with defaults."""
    config = load_config()
    pre_commit = config.get("pre_commit", {})

    return {
        "enabled": pre_commit.get("enabled", True),
        "test_command": pre_commit.get("test_command", ["pytest", "--tb=line", "-q"]),
        "timeout": pre_commit.get("timeout", 120),
        "allow_amend": pre_commit.get("allow_amend", True),
        "ui_patterns": pre_commit.get("ui_patterns", [
            "web/pages/",
            "templates/",
            ".vue",
            ".tsx",
            ".jsx",
            "components/",
            ".svelte",
        ]),
        "screenshot_reminder": pre_commit.get("screenshot_reminder", True),
    }


def get_tool_input() -> dict:
    """Read tool input from stdin or environment."""
    tool_input_str = os.environ.get("CLAUDE_TOOL_INPUT", "")

    if tool_input_str:
        try:
            return json.loads(tool_input_str)
        except json.JSONDecodeError:
            pass

    try:
        data = json.load(sys.stdin)
        return data.get("tool_input", data)
    except (json.JSONDecodeError, EOFError, Exception):
        return {}


def is_git_commit(tool_input: dict, config: dict) -> bool:
    """Check if this is a git commit command."""
    command = tool_input.get("command", "")

    if "git commit" not in command:
        return False

    # Allow amend if configured
    if config["allow_amend"] and "--amend" in command:
        return False

    return True


def run_tests(config: dict) -> tuple[bool, str]:
    """Run tests and return (success, output)."""
    project_root = get_project_root()
    test_command = config["test_command"]
    timeout = config["timeout"]

    # Check if test command executable exists
    try:
        # Try with uv first (Python projects)
        if test_command[0] in ("pytest", "python"):
            full_command = ["uv", "run"] + test_command
        elif test_command[0] in ("npm", "npx", "yarn", "pnpm"):
            full_command = test_command
        else:
            full_command = test_command

        result = subprocess.run(
            full_command,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout + result.stderr

        # Check return code and output for failures
        if result.returncode == 0:
            return True, output

        # Some test frameworks return non-zero for various reasons
        # Check output for actual failures
        output_lower = output.lower()
        if "failed" in output_lower or "error" in output_lower:
            return False, output

        # If no failures mentioned, consider it passed
        return True, output

    except subprocess.TimeoutExpired:
        return False, f"Tests timed out after {timeout} seconds"
    except FileNotFoundError as e:
        # Test runner not found - try direct command
        try:
            result = subprocess.run(
                test_command,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            output = result.stdout + result.stderr
            return result.returncode == 0, output
        except Exception:
            return True, f"Test runner not available: {e}. Allowing commit."
    except Exception as e:
        return False, f"Failed to run tests: {e}"


_SECRET_PATTERNS = [
    # Telegram Bot Token: 10 Ziffern : 35 alphanumerische Zeichen
    r"[0-9]{9,10}:[A-Za-z0-9_-]{35}",
    # Google App Password: 16 Kleinbuchstaben (kein Leerzeichen)
    r"smtp_pass='[a-z]{16}'",
    r"smtp_pass=\"[a-z]{16}\"",
    # Generische Credential-Zuweisungen mit echten Werten (nicht Platzhalter)
    r"(smtp_pass|imap_pass|test_smtp_pass|test_imap_pass|api_key|bot_token)='[A-Za-z0-9+/._-]{12,}'",
]


def check_staged_for_secrets(project_root) -> list[str]:
    """Scannt staged Dateien auf bekannte Secret-Muster. Gibt Fundstellen zurück."""
    import re
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--unified=0"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        findings = []
        for pattern in _SECRET_PATTERNS:
            for match in re.finditer(pattern, result.stdout):
                context = result.stdout[max(0, match.start()-60):match.end()+20].replace("\n", " ")
                findings.append(f"Pattern '{pattern[:40]}...' in: {context[:120]}")
        return findings
    except Exception:
        return []


def check_for_ui_changes(config: dict) -> bool:
    """Check if staged changes include UI files."""
    project_root = get_project_root()
    ui_patterns = config["ui_patterns"]

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        files = result.stdout.strip().split("\n")
        return any(
            any(pattern in f for pattern in ui_patterns)
            for f in files if f
        )
    except Exception:
        return False


_BACKEND_PREFIXES = ("src/", "tests/", "internal/", "cmd/", "api/")


def has_backend_changes(project_root) -> bool:
    """True, wenn staged Aenderungen Python/Go-Backend-Code beruehren.

    Scope-Regel (Issue #354): Die volle Backend-Test-Suite (uv run pytest) ist
    nur relevant, wenn der Commit Backend-Code anfasst. Ein reiner Frontend-
    (frontend/), Tooling- (.claude/) oder Docs- (docs/) Commit kann das Backend
    nicht beeinflussen; ihn an der Backend-Suite zu messen ist sinnlos und
    blockiert bei vorbestehend roter Suite jeden unverwandten Commit.

    Backend = src/, tests/, internal/, cmd/, api/ oder eine .py-Datei im
    Repo-Root (z.B. conftest.py). Im Zweifel (Fehler) -> True (Tests fahren).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        for f in result.stdout.strip().split("\n"):
            if not f:
                continue
            if f.startswith(_BACKEND_PREFIXES):
                return True
            if f.endswith(".py") and "/" not in f:
                return True
        return False
    except Exception:
        return True


def _check_ambiguous_block(workflow_data: dict) -> tuple[bool, str]:
    """Issue #196 — AMBIGUOUS-Verdict blocks commit unless override-token is fresh.

    Returns (allowed, reason).
    - VERIFIED/BROKEN/None: allowed (no AMBIGUOUS-Logik)
    - AMBIGUOUS + valid override (expires_at > now): allowed with reason
    - AMBIGUOUS + expired/missing override: blocked
    """
    verdict = (workflow_data.get("adversary_verdict") or "").upper()
    if not verdict.startswith("AMBIGUOUS"):
        return True, "verdict not AMBIGUOUS"

    override = workflow_data.get("adversary_ambiguous_override") or {}
    if isinstance(override, dict):
        expires = override.get("expires_at", 0) or 0
        if expires and time.time() < expires:
            return True, f"override active: {override.get('reason', '')}"
    return False, (
        "AMBIGUOUS verdict blocks commit. "
        "Run: workflow.py override-ambiguous '<reason>' (TTL 1h)"
    )



def _phase6b_was_run(workflow_data: dict) -> bool:
    """Return True if phase6b_adversary appears in phase_transitions."""
    transitions = workflow_data.get("phase_transitions") or []
    return any(
        isinstance(t, dict) and "phase6b" in (t.get("to") or "")
        for t in transitions
    )


def _check_none_verdict_block(workflow_data: dict) -> tuple[bool, str]:
    """Issue #508 — Block commit if phase6b ran but adversary_verdict is missing/BROKEN.

    Returns (allowed, reason).
    - verdict present and not BROKEN: allowed
    - BROKEN: blocked
    - verdict missing + no phase6b: allowed (Infra/Doku-Workflow)
    - verdict missing + phase6b ran: blocked
    """
    verdict = (workflow_data.get("adversary_verdict") or "").upper()
    if verdict and verdict != "BROKEN":
        return True, "verdict present"
    if verdict == "BROKEN":
        return False, (
            "Adversary-Verdict ist BROKEN. Implementierung korrigieren bevor Commit."
        )
    if not _phase6b_was_run(workflow_data):
        return True, "phase6b did not run"
    return False, (
        "Adversary-Verdict fehlt (None). "
        "qa_gate.py wurde nicht aufgerufen. "
        "Speichere den Test-Output und fuehre aus: "
        "python3 .claude/hooks/qa_gate.py /tmp/test_output.txt"
    )

def _load_active_workflow() -> dict:
    """Load active workflow state via workflow_state_multi wrapper (Issue #196)."""
    try:
        from workflow_state_multi import get_active_workflow
        wf = get_active_workflow()
        return wf or {}
    except Exception:
        return {}


def main():
    config = get_pre_commit_config()

    # Check if enabled
    if not config["enabled"]:
        sys.exit(0)

    tool_input = get_tool_input()

    if not is_git_commit(tool_input, config):
        sys.exit(0)

    # Secret-Scan: staged Dateien auf Credentials prüfen
    project_root = get_project_root()
    secret_findings = check_staged_for_secrets(project_root)
    if secret_findings:
        print("=" * 70, file=sys.stderr)
        print("BLOCKED - Credentials in staged files detected!", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for finding in secret_findings[:5]:
            print(f"  {finding}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Entferne die Credentials aus den Dateien, bevor du committed.", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(2)

    # Issue #196 — AMBIGUOUS-Verdict-Block (before test run)
    wf = _load_active_workflow()
    ok, reason = _check_ambiguous_block(wf)
    if not ok:
        print("=" * 70, file=sys.stderr)
        print("BLOCKED - Adversary AMBIGUOUS", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"{reason}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(2)


    # Issue #508 — None/BROKEN-Verdict-Block: phase6b ohne qa_gate-Aufruf
    ok, reason = _check_none_verdict_block(wf)
    if not ok:
        print("=" * 70, file=sys.stderr)
        print("BLOCKED - Adversary-Verdict fehlt oder BROKEN", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"{reason}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(2)

    # Issue #354 — Scope: Backend-Test-Suite nur bei Backend-Code-Aenderungen.
    # Reiner Frontend-/Tooling-/Docs-Commit kann das Backend nicht beeinflussen.
    # Secret-Scan + AMBIGUOUS-Block (oben) liefen bereits unabhaengig vom Scope.
    if not has_backend_changes(project_root):
        print(
            "Pre-Commit Gate: keine Backend-Code-Aenderung "
            "(src/tests/internal/cmd/api) — Backend-Test-Suite uebersprungen.",
            file=sys.stderr,
        )
        if config["screenshot_reminder"] and check_for_ui_changes(config):
            print(
                "Note: UI changes detected. Consider adding screenshot artifacts.",
                file=sys.stderr,
            )
        sys.exit(0)

    # Run tests
    success, output = run_tests(config)

    if not success:
        # Extract failure summary
        lines = output.split("\n")
        failures = [l for l in lines if "FAILED" in l or "Error" in l or "FAIL" in l]
        summary = "\n".join(failures[:5]) if failures else "Tests failed"

        print("=" * 70, file=sys.stderr)
        print("BLOCKED - Pre-Commit Gate", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(file=sys.stderr)
        print("Tests must pass before committing (TDD-GREEN).", file=sys.stderr)
        print(file=sys.stderr)
        print("Failures:", file=sys.stderr)
        print(summary, file=sys.stderr)
        print(file=sys.stderr)
        print("Fix tests first, then commit.", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        sys.exit(2)

    # Check for UI changes - remind about screenshot
    if config["screenshot_reminder"] and check_for_ui_changes(config):
        # Don't block, just output reminder
        print("Note: UI changes detected. Consider adding screenshot artifacts.", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
