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
    # Issue #198: Channel-Tests sind konzeptionell Tests → IMMER Gmail-Routing,
    # nie über Production-SMTP (Resend). _is_test_user("default") liefert False,
    # daher zwingen wir .for_testing() unabhängig vom user_id.
    settings = Settings().with_user_profile(user_id).for_testing()
    subject = "Gregor 20 — Testmeldung"
    body = "Dein Kanal funktioniert!"

    try:
        if channel == "email":
            from output.channels.email import EmailOutput

            output = EmailOutput(settings)
            output.send(subject, body, html=False)
        elif channel == "telegram":
            from output.channels.telegram import TelegramOutput

            output = TelegramOutput(settings)
            output.send(subject, body)
        else:
            return {"error": f"Unbekannter Kanal: {channel}"}
        return {"status": "ok"}
    except Exception as exc:
        return {"error": str(exc)}
