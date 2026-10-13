"""Channel test service.

Encapsulates the concrete output-channel imports used by the
/api/notify/test endpoint so that routers do not depend directly on
outputs.* modules.
"""
from __future__ import annotations

from app.config import Settings


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

            # Issue #198: Mail-Test IMMER ueber den Test-Postausgang, nie Resend.
            output = EmailOutput(Settings().with_user_profile(user_id).for_testing())
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
