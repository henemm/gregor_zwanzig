"""Plugin path bootstrap for project-specific hooks.

Import this before importing any framework modules:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    import _bootstrap  # noqa: F401
"""
import os
import sys
from pathlib import Path


def _find_plugin_hooks() -> Path:
    pr = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip().rstrip("/")
    if pr:
        candidate = Path(pr) / "core" / "hooks"
        if candidate.exists():
            return candidate
    for known in [Path("/home/hem/agent-os-openspec/core/hooks")]:
        if known.exists():
            return known
    return Path(__file__).resolve().parent


_local = str(Path(__file__).resolve().parent)
_plugin = str(_find_plugin_hooks())
for _p in [_local, _plugin]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
