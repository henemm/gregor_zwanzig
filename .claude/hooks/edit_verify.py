"""
PostToolUse hook: edit_verify.py — Bug #569

Verifies that an Edit or Write tool call actually landed on disk.
On success: no output, exit 0.
On failure: warning message to stdout, exit 0 (visibility, not blocking).
Fail-open on any error.
"""
import json
import sys


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)

    try:
        tool_input = payload.get("tool_input", {})
        if not isinstance(tool_input, dict):
            sys.exit(0)

        file_path = tool_input.get("file_path")
        if not file_path:
            sys.exit(0)

        # Determine what string to look for
        tool_name = payload.get("tool_name", "")
        if tool_name == "Write":
            content = tool_input.get("content")
            if not content:
                sys.exit(0)
            search_string = content[:200]
        else:
            # Edit tool
            search_string = tool_input.get("new_string")
            if not search_string:
                sys.exit(0)

        # Read the file using the absolute path directly (AC-5: no path re-resolution)
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                file_content = fh.read()
        except (OSError, UnicodeDecodeError):
            # AC-4: fail-open for unreadable or binary files
            sys.exit(0)

        # Check if expected string is present
        if search_string in file_content:
            # AC-1/AC-3: success, no output
            sys.exit(0)

        # AC-2: silent failure detected — output warning to stdout
        print(
            f"WARNING: Edit-Verify failed — new_string/content NOT FOUND in {file_path}\n"
            f"Expected to find: {repr(search_string[:80])}"
        )
        sys.exit(0)

    except Exception:
        # Fail-open for any unexpected error
        sys.exit(0)


if __name__ == "__main__":
    main()
