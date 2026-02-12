#!/usr/bin/env python3
"""Play a notification sound when Claude Code stops."""
import subprocess
subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
