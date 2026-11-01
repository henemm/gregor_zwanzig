"""Channel test service.

Encapsulates the concrete output-channel imports used by the
/api/notify/test endpoint so that routers do not depend directly on
outputs.* modules.
"""
from __future__ import annotations

import json

from app.config import Settings
from i18n import Lang, resolve_user_lang, t


def _sperre_email(user_id: str, lang: Lang = "de") -> str | None:
    """Fehlertext, wenn fuer diesen Nutzer keine Testmail gesendet werden darf.

    Issue #2521 S2 / ADR-0092: gesendet wird nur an die bestaetigte
    Profiladresse dieses Nutzers -- nie an "default", nie an die globale
    Betreiber-Adresse (Rueckfall von ``with_user_profile``).
    Issue #2671: Sperrtext in ``lang``.
    """
    gesperrt = t("versand.test.mail_gesperrt", lang)
    if not user_id or user_id == "default":
        return gesperrt
    from app.loader import get_data_dir

    try:
        profil = json.loads((get_data_dir(user_id) / "user.json").read_text())
    except (OSError, ValueError):
        return gesperrt
    if not isinstance(profil, dict):
        return gesperrt
    if not profil.get("email_verified_at") or not (profil.get("mail_to") or "").strip():
        return gesperrt
    return None


def send_test_message(channel: str, user_id: str) -> dict:
    """Send a test message via the requested channel.

    Args:
        channel: "email" or "telegram".
        user_id: Target user identifier.

    Returns:
        A dict with either {"status": "ok"} or {"error": ...}.
    """
    lang = resolve_user_lang(user_id)  # Issue #2671: Texte in der Nutzersprache
    subject = t("versand.test.betreff", lang)
    body = t("versand.test.text", lang)

    try:
        if channel == "email":
            from output.channels.email import EmailOutput

            sperre = _sperre_email(user_id, lang)
            if sperre:
                return {"error": sperre}
            # Issue #2521 S2 / ADR-0092 (loest #198 fuer echte Nutzer ab):
            # normale Versandkette an die bestaetigte Profiladresse; Testnutzer
            # und Staging bleiben ueber force_test in with_user_profile auf Stalwart.
            output = EmailOutput(Settings().with_user_profile(user_id))
            output.send(subject, body, html=False, lang=lang)
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
            return {"error": t("versand.test.kanal_unbekannt", lang, kanal=channel)}
        return {"status": "ok"}
    except Exception as exc:
        return {"error": str(exc)}
