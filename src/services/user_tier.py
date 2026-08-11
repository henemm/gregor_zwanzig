import json
import logging

from app.loader import get_data_dir

logger = logging.getLogger("user_tier")


def sms_allowed(user_id: str) -> bool:
    profile_path = get_data_dir(user_id) / "user.json"
    if not profile_path.exists():
        return False
    try:
        profile = json.loads(profile_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "user.json unreadable/corrupt for %s at %s: %s", user_id, profile_path, exc
        )
        return False
    return profile.get("tier", "free") in ("standard", "premium")


def premium_sms_allowed(user_id: str) -> bool:
    """Issue #1676 S2a (AC-8/D7): Premium-SMS ist ein Premium-Merkmal.

    BEWUSST keine Delegation an `sms_allowed()` — das laesst `standard`
    durch. Der Premium-SMS-Kanal spricht ein Satellitengeraet an, jede
    Nachricht kostet; eine Wiederverwendung waere eine stille
    Rechte-Ausweitung. Fehlendes `tier`-Feld, fehlende oder kaputte
    `user.json` verhalten sich wie `free` — fail-closed.
    """
    profile_path = get_data_dir(user_id) / "user.json"
    if not profile_path.exists():
        return False
    try:
        profile = json.loads(profile_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "user.json unreadable/corrupt for %s at %s: %s", user_id, profile_path, exc
        )
        return False
    return profile.get("tier", "free") == "premium"


def daily_alert_limit(user_id: str) -> int | None:
    """Issue #1070: Tages-Obergrenze proaktiver Alerts nach Nutzerlevel.

    free -> 2, standard -> 4, premium -> None (kein Limit). Fehlende/kaputte
    user.json verhaelt sich wie fehlendes tier-Feld -> free-Default (Limit 2).
    """
    profile_path = get_data_dir(user_id) / "user.json"
    tier = "free"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text())
            tier = profile.get("tier", "free")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "user.json unreadable/corrupt for %s at %s: %s",
                user_id,
                profile_path,
                exc,
            )
            tier = "free"
    return {"free": 2, "standard": 4, "premium": None}.get(tier, 2)
