import json
from pathlib import Path


def sms_allowed(user_id: str) -> bool:
    profile_path = Path(f"data/users/{user_id}/user.json")
    if not profile_path.exists():
        return False
    try:
        profile = json.loads(profile_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    return profile.get("tier", "free") in ("standard", "premium")
