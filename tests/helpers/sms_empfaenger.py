"""Gemeinsamer Test-Helper fuer den Empfaengervertrag SMS / Premium-SMS
(Issue #1412 S4b, Vorbild ``tests/helpers/telegram_empfaenger.py``).

Der seven.io-Transport sendet nur noch an belegte Empfaenger:

* SMS ``user_profile`` -- bestaetigte Nummer aus ``user.json``
  (``profil_sms`` schreibt sie unter der per-Test isolierten Datenwurzel,
  ``sms_ausgang`` liefert den passenden ``SMSOutput``);
* SMS ``verification`` -- Bestaetigungscode an die ausstehende Nummer
  (``pending_sms_to`` bzw. ``sms_to``), ``verifikations_ausgang``;
* Premium-SMS ``user_profile`` -- gelernte Rueckadresse samt Zeitstempel
  (``profil_rueckadresse`` / ``premium_ausgang``).

Kein Stub des Prueflings: es werden die echten Fabriken benutzt. Die neuen
Namen (``SmsRecipient``, ``PremiumSmsRecipient``, ``recipient=``) werden nur
INNERHALB der Funktionen importiert -- ein Test, der diesen Helper importiert,
stirbt so nicht schon beim Sammeln.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.loader import get_data_dir


def _profil_rmw(user_id: str, felder: dict) -> None:
    """Read-Modify-Write auf ``user.json``: bestehende Felder bleiben erhalten.
    Tarif ``premium`` als Vorgabe (SMS 10, Premium-SMS 15 je Tag) -- sonst
    sperrte das Tageslimit (#2412) den Versand aus dem falschen Grund."""
    ordner = get_data_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / "user.json"
    try:
        profil = json.loads(datei.read_text())
    except (OSError, ValueError):
        profil = {}
    if not isinstance(profil, dict):
        profil = {}
    profil.setdefault("id", user_id)
    profil.setdefault("tier", "premium")
    profil.update(felder)
    datei.write_text(json.dumps(profil))


def zeitstempel(stamp: datetime) -> str:
    """Zeitstempel in der Form, in der Go ihn ablegt (RFC3339, ``Z``)."""
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def profil_sms(user_id: str, nummer: Optional[str], *, bestaetigt: bool = True, **felder) -> None:
    """Traegt ``sms_to`` (und bei ``bestaetigt`` dieselbe Nummer als
    ``sms_verified_number``) ins Profil ein. Weitere Felder (z. B.
    ``pending_sms_to``) per Schluesselwort."""
    werte = {"sms_to": nummer or "", "sms_verified_number": (nummer or "") if bestaetigt else ""}
    werte.update(felder)
    _profil_rmw(user_id, werte)


def profil_rueckadresse(
    user_id: str, nummer: Optional[str], *,
    gelernt_vor: Optional[timedelta] = timedelta(minutes=5),
    gelernt_am: Optional[datetime] = None, **felder,
) -> None:
    """Traegt die gelernte Premium-SMS-Rueckadresse ein. ``gelernt_am`` hat
    Vorrang vor ``gelernt_vor``; ``gelernt_vor=None`` ohne ``gelernt_am``
    laesst den Zeitstempel weg."""
    werte: dict = {"premium_sms_reply_to": nummer or ""}
    if gelernt_am is not None:
        werte["premium_sms_reply_at"] = zeitstempel(gelernt_am)
    elif gelernt_vor is not None:
        werte["premium_sms_reply_at"] = zeitstempel(datetime.now(timezone.utc) - gelernt_vor)
    werte.update(felder)
    _profil_rmw(user_id, werte)


def mit_profil_sms(user_id: str, settings) -> str:
    """Migrationshilfe #1412 S4b: traegt die Nummer, die ein Test bisher nur in
    ``settings.sms_to`` setzte, als BESTAETIGTE Nummer ins Profil ein (dort
    liest sie ``SmsRecipient.for_user``) und gibt ``user_id`` zurueck."""
    nummer = getattr(settings, "sms_to", None)
    if nummer:
        profil_sms(user_id, nummer)
    return user_id


def mit_profil_rueckadresse(user_id: str, settings) -> str:
    """Migrationshilfe #1412 S4b: uebertraegt ``premium_sms_reply_to/_at`` aus
    den Settings ins Profil (dort liest sie ``PremiumSmsRecipient.for_user``)."""
    nummer = getattr(settings, "premium_sms_reply_to", None)
    if nummer:
        gelernt = getattr(settings, "premium_sms_reply_at", None)
        if gelernt is not None:
            profil_rueckadresse(user_id, nummer, gelernt_am=gelernt)
        else:
            profil_rueckadresse(user_id, nummer, gelernt_vor=None)
    return user_id


def mit_profil_kanaele(user_id: str, settings) -> str:
    """Migrationshilfe #1412 S4a+S4b in einem: Telegram-Chat, SMS-Nummer und
    Premium-Rueckadresse, die ein Test bisher nur in den Settings setzte,
    wandern ins Profil (dort lesen die Empfaenger-Fabriken). Gibt ``user_id``
    zurueck -- Ersatz fuer ``mit_profil_chat(uid, settings)``."""
    from tests.helpers.telegram_empfaenger import mit_profil_chat

    mit_profil_chat(user_id, settings)
    mit_profil_sms(user_id, settings)
    return mit_profil_rueckadresse(user_id, settings)


def sms_ausgang(settings, user_id: str, nummer: Optional[str] = None):
    """``SMSOutput`` mit Empfaenger ``SmsRecipient.for_user``; ``nummer`` wird
    vorher als bestaetigte Nummer ins Profil geschrieben (``None``: Profil
    bleibt, wie es ist)."""
    from output.channels.recipient import SmsRecipient
    from output.channels.sms import SMSOutput

    if nummer is not None:
        profil_sms(user_id, nummer)
    return SMSOutput(settings, recipient=SmsRecipient.for_user(user_id, settings))


def verifikations_ausgang(settings, user_id: str, nummer: str):
    """``SMSOutput`` mit Empfaenger ``SmsRecipient.verification`` -- nur fuer
    die an das Profil gebundene ausstehende Nummer zulaessig."""
    from output.channels.recipient import SmsRecipient
    from output.channels.sms import SMSOutput

    return SMSOutput(settings, recipient=SmsRecipient.verification(user_id, nummer))


def premium_ausgang(
    settings, user_id: str, nummer: Optional[str] = None, *,
    gelernt_vor: timedelta = timedelta(minutes=5),
):
    """``PremiumSmsOutput`` mit Empfaenger ``PremiumSmsRecipient.for_user``;
    ``nummer`` wird vorher als frisch gelernte Rueckadresse eingetragen."""
    from output.channels.premium_sms import PremiumSmsOutput
    from output.channels.recipient import PremiumSmsRecipient

    if nummer is not None:
        profil_rueckadresse(user_id, nummer, gelernt_vor=gelernt_vor)
    return PremiumSmsOutput(settings, recipient=PremiumSmsRecipient.for_user(user_id, settings))
