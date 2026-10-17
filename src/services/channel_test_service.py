"""Channel test service.

Encapsulates the concrete output-channel imports used by the
/api/notify/test endpoint so that routers do not depend directly on
outputs.* modules.
"""
from __future__ import annotations

import json

from app.config import Settings

_MAIL_GESPERRT = (
    "Die Testmail wurde nicht gesendet: Für dein Konto ist keine bestätigte "
    "E-Mail-Adresse hinterlegt. Bitte bestätige zuerst deine Adresse im Profil."
)


def _sperre_email(user_id: str) -> str | None:
    """Fehlertext, wenn fuer diesen Nutzer keine Testmail gesendet werden darf.

    Issue #2521 S2 / ADR-0091: gesendet wird nur an die bestaetigte
    Profiladresse dieses Nutzers -- nie an "default", nie an die globale
    Betreiber-Adresse (Rueckfall von ``with_user_profile``).
    """
    if not user_id or user_id == "default":
        return _MAIL_GESPERRT
    from app.loader import get_data_dir

    try:
        profil = json.loads((get_data_dir(user_id) / "user.json").read_text())
    except (OSError, ValueError):
        return _MAIL_GESPERRT
    if not isinstance(profil, dict):
        return _MAIL_GESPERRT
    if not profil.get("email_verified_at") or not (profil.get("mail_to") or "").strip():
        return _MAIL_GESPERRT
    return None


def send_test_message(channel: str, user_id: str) -> dict:
    """Send a test message via the requested channel.

    Args:
        channel: "email" or "telegram".
        user_id: Target user identifier.

    Returns:
        A dict with either {"status": "ok"} or {"error": ...}.
    """
    subject = "Gregor 20 — Testmeldung"
    body = "Dein Kanal funktioniert!"

    try:
        if channel == "email":
            from output.channels.email import EmailOutput

            sperre = _sperre_email(user_id)
            if sperre:
                return {"error": sperre}
            # Issue #2521 S2 / ADR-0091 (loest #198 fuer echte Nutzer ab):
            # normale Versandkette an die bestaetigte Profiladresse; Testnutzer
            # und Staging bleiben ueber force_test in with_user_profile auf Stalwart.
            output = EmailOutput(Settings().with_user_profile(user_id))
            output.send(subject, body, html=False)
        elif channel == "telegram":
            from output.channels.recipient import TelegramRecipient
            from output.channels.telegram import TelegramOutput

            # Issue #1412 S4a (M3): an den Profil-Chat ueber den Produktions-Bot,
            # NICHT ueber for_testing() (das zielte auf den Betreiber-Test-Chat).
            settings = Settings().with_user_profile(user_id)
            recipient = TelegramRecipient.for_user(user_id, settings)
            output = TelegramOutput(settings, recipient=recipient)
            output.send(subject, body)
        else:
            return {"error": f"Unbekannter Kanal: {channel}"}
        return {"status": "ok"}
    except Exception as exc:
        return {"error": str(exc)}
