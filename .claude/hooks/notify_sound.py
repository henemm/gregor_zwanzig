#!/usr/bin/env python3
"""Play a notification sound when Claude Code stops."""
import shutil
import subprocess
import sys

if shutil.which("afplay"):
    # macOS: play system sound
    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
else:
    # SSH/iTerm: terminal bell
    sys.stdout.write("\a")
    sys.stdout.flush()
