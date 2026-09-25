import json
import logging

from app.loader import get_data_dir

logger = logging.getLogger("user_tier")

# Issue #2412 S4a (Spec sms_daily_limit.md, PO-Entscheidung E3/E4, 2026-09-24):
# taegliche Kosten-Obergrenzen je Kanal, getrennt von `daily_alert_limit`
# (Alarm-FREQUENZ). Reserve = wie viel vom Grundlimit fuer Alarme reserviert
# bleibt, wenn Briefings das Kontingent zuerst beanspruchen.
SMS_ALARM_RESERVE = 2
PREMIUM_SMS_ALARM_RESERVE = 3
PREMIUM_SMS_REPLY_OVERSHOOT = 3

_DAILY_SMS_LIMIT = {"free": 0, "standard": 10, "premium": 10}
_DAILY_PREMIUM_SMS_LIMIT = {"free": 0, "standard": 0, "premium": 15}
_KNOWN_TIERS = ("free", "standard", "premium")


def _load_profile(user_id: str) -> dict:
    """Adversary F001b (CRITICAL): robustes Laden von `user.json` -- fehlende
    Datei, kaputtes JSON ODER gueltiges JSON, das KEIN Objekt ist (Liste,
    Zahl, String, ...) liefern alle ein leeres Profil (WARNING bei
    tatsaechlichem Inhaltsproblem), NIE ein `AttributeError` aus einem
    `.get()` auf einem Nicht-Dict. Jeder Aufrufer in diesem Modul faellt
    damit einheitlich auf sein eigenes free-Default zurueck."""
    profile_path = get_data_dir(user_id) / "user.json"
    if not profile_path.exists():
        return {}
    try:
        profile = json.loads(profile_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "user.json unreadable/corrupt for %s at %s: %s", user_id, profile_path, exc
        )
        return {}
    if not isinstance(profile, dict):
        logger.warning(
            "user.json for %s at %s is not a JSON object (%s) -- treated as "
            "empty profile",
            user_id, profile_path, type(profile).__name__,
        )
        return {}
    return profile


def _tier(user_id: str) -> str:
    """Adversary F009 (CRITICAL): liefert AUSSCHLIESSLICH einen bekannten
    Tier-String (`free`/`standard`/`premium`). Jeder andere Wert -- kein
    String (z.B. eine Liste) ODER ein unbekannter String (z.B. `"gold"`) --
    faellt WARNING-geloggt auf `"free"` zurueck. Ohne diese Pruefung wuerde
    ein fremder Wert ungeprueft in `_DAILY_SMS_LIMIT.get(...)` landen --
    eine Liste ist dort `unhashable` (`TypeError`), ein unbekannter String
    still auf 0 gemappt (kein Wurf, aber ein stiller Vertragsbruch). Dies
    ist die EINE Auswertungsstelle fuer alle vier Aufrufer in diesem Modul."""
    roh = _load_profile(user_id).get("tier", "free")
    if isinstance(roh, str) and roh in _KNOWN_TIERS:
        return roh
    logger.warning(
        "user.json tier value %r for %s is not a known tier -- treated as "
        "'free'",
        roh, user_id,
    )
    return "free"


def daily_sms_limit(user_id: str) -> int:
    """Issue #2412 S4a: Tages-Kostendeckel fuer den Kanal SMS je Tier."""
    return _DAILY_SMS_LIMIT.get(_tier(user_id), 0)


def daily_premium_sms_limit(user_id: str) -> int:
    """Issue #2412 S4a: Tages-Kostendeckel fuer den Kanal Premium-SMS je Tier."""
    return _DAILY_PREMIUM_SMS_LIMIT.get(_tier(user_id), 0)


def sms_allowed(user_id: str) -> bool:
    return _tier(user_id) in ("standard", "premium")


def premium_sms_allowed(user_id: str) -> bool:
    """Issue #1676 S2a (AC-8/D7): Premium-SMS ist ein Premium-Merkmal.

    BEWUSST keine Delegation an `sms_allowed()` — das laesst `standard`
    durch. Der Premium-SMS-Kanal spricht ein Satellitengeraet an, jede
    Nachricht kostet; eine Wiederverwendung waere eine stille
    Rechte-Ausweitung. Fehlendes `tier`-Feld, fehlende oder kaputte
    `user.json` verhalten sich wie `free` — fail-closed.
    """
    return _tier(user_id) == "premium"


def daily_alert_limit(user_id: str) -> int | None:
    """Issue #1070: Tages-Obergrenze proaktiver Alerts nach Nutzerlevel.

    free -> 2, standard -> 4, premium -> None (kein Limit). Fehlende/kaputte
    user.json verhaelt sich wie fehlendes tier-Feld -> free-Default (Limit 2).
    """
    return {"free": 2, "standard": 4, "premium": None}.get(_tier(user_id), 2)
