"""
TDD RED — Bug #569: PostToolUse Edit-Verifikation

Tests für .claude/hooks/edit_verify.py
Alle Tests MÜSSEN fehlschlagen, weil die Datei noch nicht existiert.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_PATH = Path(__file__).parents[2] / ".claude" / "hooks" / "edit_verify.py"


def run_hook(payload: dict) -> subprocess.CompletedProcess:
    """Führt edit_verify.py mit dem gegebenen Payload aus."""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestAC1EditSuccess:
    """AC-1: Edit erfolgreich → new_string in Datei → kein Output, exit 0."""

    def test_edit_success_no_output(self, tmp_path):
        target = tmp_path / "test.md"
        target.write_text("# Old Title\nSome content here\n")

        # Simulate: Edit already applied the change (new_string IS in file)
        target.write_text("# New Title\nSome content here\n")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "# Old Title",
                "new_string": "# New Title",
            },
            "tool_response": {"type": "text", "text": "File updated successfully."},
        }
        result = run_hook(payload)
        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""

    def test_edit_success_new_string_present(self, tmp_path):
        target = tmp_path / "6-validate.md"
        target.write_text("Staging aktuell machen\nmore content\n")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "old text",
                "new_string": "Staging aktuell machen",
            },
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0
        assert "ERROR" not in result.stdout
        assert "FEHLER" not in result.stdout


class TestAC2EditSilentFailure:
    """AC-2: new_string NICHT in Datei → klare Fehlermeldung im stdout."""

    def test_edit_silent_failure_outputs_warning(self, tmp_path):
        target = tmp_path / "6-validate.md"
        # File has OLD content (edit silently failed)
        target.write_text("# Old content unchanged\n")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "# Old content unchanged",
                "new_string": "# New content that should be here",
            },
            "tool_response": {"type": "text", "text": "File updated successfully."},
        }
        result = run_hook(payload)
        assert result.returncode == 0  # never blocks
        # stdout must contain a warning/error visible to Claude
        assert len(result.stdout) > 0
        assert any(
            word in result.stdout.upper()
            for word in ["WARNUNG", "WARNING", "FEHLER", "ERROR", "FAILED", "NOT FOUND"]
        )

    def test_edit_silent_failure_mentions_file(self, tmp_path):
        target = tmp_path / "7-deploy.md"
        target.write_text("original content\n")

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "original content",
                "new_string": "EXPECTED NEW CONTENT XYZ",
            },
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0
        assert len(result.stdout) > 0
        assert "EXPECTED NEW CONTENT XYZ" in result.stdout or str(target) in result.stdout


class TestAC3WriteToolVerification:
    """AC-3: Write-Tool → prüft ersten 200 Zeichen von `content`."""

    def test_write_success_no_output(self, tmp_path):
        target = tmp_path / "output.md"
        content = "# Fresh content\nThis was written by Write tool.\n"
        target.write_text(content)

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": content,
            },
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_write_failure_outputs_warning(self, tmp_path):
        target = tmp_path / "output.md"
        target.write_text("completely different content\n")

        expected_content = "# Expected content that was not written\n" + "x" * 50

        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(target),
                "content": expected_content,
            },
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0
        assert len(result.stdout) > 0


class TestAC4FailOpen:
    """AC-4: Datei nicht lesbar → fail-open, exit 0, kein Output."""

    def test_nonexistent_file_no_error(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/tmp/file_that_does_not_exist_xyz123.md",
                "old_string": "anything",
                "new_string": "anything else",
            },
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0
        # fail-open: no warning for files that don't exist (could be new file creation)
        # OR: minimal non-blocking output at most

    def test_binary_file_no_crash(self, tmp_path):
        target = tmp_path / "binary.bin"
        target.write_bytes(bytes(range(256)))

        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(target),
                "old_string": "anything",
                "new_string": "something",
            },
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0  # never crashes


class TestAC5AbsolutePaths:
    """AC-5: Immer absoluter Pfad aus tool_input.file_path, keine Pfad-Neuauflösung."""

    def test_uses_given_absolute_path_directly(self, tmp_path):
        # Two files with same relative name but at different absolute paths
        worktree_file = tmp_path / "worktree" / ".claude" / "commands" / "6-validate.md"
        main_file = tmp_path / "main" / ".claude" / "commands" / "6-validate.md"

        worktree_file.parent.mkdir(parents=True)
        main_file.parent.mkdir(parents=True)

        new_string = "UNIQUE_NEW_STRING_IN_WORKTREE_ONLY"
        worktree_file.write_text(new_string + "\nrest of content\n")
        main_file.write_text("original content without new string\n")

        # Hook receives absolute path to WORKTREE file — should use that
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(worktree_file),
                "old_string": "original",
                "new_string": new_string,
            },
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0
        # Should NOT report error, because the worktree file HAS the new_string
        assert "ERROR" not in result.stdout.upper()
        assert "FEHLER" not in result.stdout.upper()
        assert "FAILED" not in result.stdout.upper()


class TestAC6EmptyPayload:
    """AC-6: Kein file_path / new_string / content → sofort exit 0."""

    def test_empty_payload_exit_0(self):
        result = run_hook({})
        assert result.returncode == 0

    def test_no_file_path_exit_0(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {"old_string": "x", "new_string": "y"},
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0

    def test_no_new_string_no_content_exit_0(self):
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/tmp/any.md"},
            "tool_response": {"type": "text", "text": "ok"},
        }
        result = run_hook(payload)
        assert result.returncode == 0

    def test_invalid_json_exit_0(self):
        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input="not valid json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
