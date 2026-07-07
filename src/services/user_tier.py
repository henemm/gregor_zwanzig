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


def daily_alert_limit(user_id: str) -> int | None:
    """Issue #1070: Tages-Obergrenze proaktiver Alerts nach Nutzerlevel.

    free -> 2, standard -> 4, premium -> None (kein Limit). Fehlende/kaputte
    user.json verhaelt sich wie fehlendes tier-Feld -> free-Default (Limit 2).
    """
    profile_path = Path(f"data/users/{user_id}/user.json")
    tier = "free"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text())
            tier = profile.get("tier", "free")
        except (json.JSONDecodeError, OSError):
            tier = "free"
    return {"free": 2, "standard": 4, "premium": None}.get(tier, 2)
