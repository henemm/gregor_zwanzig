"""Premium-SMS (Garmin inReach) — vierter Versandkanal, Issue #1676 S2a.

ADR-0049 legt den Kanalnamen `premium_sms` und die vier Eigenheiten fest, die
ihn vom normalen SMS-Kanal unterscheiden:

* **Absender fest.** Nur an unsere Dienstnummer kann das Satellitengeraet
  antworten — `sms_from` hat auf diesen Kanal keine Wirkung.
* **Empfaenger ausschliesslich die gelernte Rueckadresse** aus `user.json`
  (S1 lernt sie beim Empfang). `sms_to` wird hier nie gelesen.
* **Fail-closed mit Grund.** Fehlt die Rueckadresse oder ist sie zu alt, geht
  keine Nachricht hinaus. Der Grund verlaesst den Kanal als
  `ChannelBlockedError` — Prosatext fuer den Menschen PLUS Kurzschluessel
  (`reason_code`) fuer den Aufrufer — und landet beim Briefing-Aufrufer in
  `NotificationResult.blocked_channels`; ein stilles Ausbleiben ist bei
  diesem Kanal ausdruecklich verboten (Spec D3/D4).
* **Berechtigung nur `premium`** — das prueft `services.user_tier.
  premium_sms_allowed()` am Aufrufort, nicht dieser Kanal.

Der Nachrichtentext ist unveraendert `report.sms_text` (Spec D5): kein
eigener Renderer, damit SMS und Premium-SMS inhaltlich nicht auseinander
laufen.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.origin_guard import running_origin
from output.channels.base import ChannelBlockedError
from output.channels.seven_io_base import SevenIoChannelBase

#: Unsere feste seven.io-Dienstnummer. Kanal-Eigenschaft, keine Einstellung.
PREMIUM_SMS_SENDER = "4916092172595"

# Kurzschluessel der beiden Sperrfaelle. Sie stehen NEBEN dem Prosatext, nicht
# an seiner Stelle: der Text sagt einem Menschen, was los ist, der
# Kurzschluessel laesst sich buchen und vergleichen. Vokabular und Schreibweise
# wie die bestehenden Gruende in `services/alert_log.py` (`channel_disabled`,
# `delivery_failed`, `below_channel_threshold`), damit der Alarmpfad sie
# unveraendert nach `channels_not_sent` schreiben kann.
BLOCK_REASON_NO_REPLY_ADDRESS = "premium_sms_no_reply_address"
BLOCK_REASON_REPLY_ADDRESS_STALE = "premium_sms_reply_address_stale"

#: Verfallsfrist der gelernten Rueckadresse (Spec D6, PO-Entscheid 2026-08-10).
#: Begruendete Setzung, kein Messwert: zu kurz heisst Briefing-Ausfall mitten
#: auf der Tour, zu lang heisst kostenpflichtige SMS an eine Nummer, die Garmin
#: inzwischen einem fremden Geraet zugeteilt hat — mit HTTP 200 als
#: Scheinerfolg. Widerlegungsbedingungen: Spec „Known Limitations".
PREMIUM_SMS_REPLY_TTL = timedelta(days=30)


class PremiumSmsOutput(SevenIoChannelBase):
    """Sendet das Trip-Briefing als Premium-SMS an das Garmin-Geraet."""

    CHANNEL_NAME = "premium_sms"

    def _origin(self) -> str:
        """Herkunft DIESES Moduls — siehe `SevenIoChannelBase._origin`."""
        return running_origin(Path(__file__))

    def _resolve_sender(self) -> str:
        return PREMIUM_SMS_SENDER

    def _resolve_recipient(self) -> str:
        """Die gelernte Rueckadresse — oder ein benannter Abbruch.

        Beide Faelle sind erst zur Sendezeit final bekannt und deshalb hier
        geprueft, nicht am Aufrufort (Spec D3). Jeder Abbruch traegt seinen
        Kurzschluessel mit, damit ein Aufrufer die zwei Faelle ohne
        Textvergleich unterscheiden kann.
        """
        reply_to = self._settings.premium_sms_reply_to
        reply_at = self._settings.premium_sms_reply_at
        if not reply_to or reply_at is None:
            raise ChannelBlockedError(
                self.name,
                "keine gelernte Rueckadresse vorhanden — das Geraet hat sich "
                "noch nie gemeldet (Rueckkanal, Issue #1676 S1); ohne sie ist "
                "kein Empfaenger bekannt.",
                reason_code=BLOCK_REASON_NO_REPLY_ADDRESS,
            )
        age = _now() - _as_aware(reply_at)
        if age > PREMIUM_SMS_REPLY_TTL:
            raise ChannelBlockedError(
                self.name,
                "gelernte Rueckadresse ist veraltet: zuletzt vor "
                f"{age.days} Tagen gelernt, erlaubt sind "
                f"{PREMIUM_SMS_REPLY_TTL.days} Tage. Garmin kann die Nummer "
                "inzwischen einem fremden Geraet zugeteilt haben — Versand "
                "abgebrochen, bis sich das Geraet wieder meldet.",
                reason_code=BLOCK_REASON_REPLY_ADDRESS_STALE,
            )
        return reply_to


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(stamp: datetime) -> datetime:
    """Zeitstempel ohne Zeitzone gilt als UTC (so legt Go ihn ab).

    Ohne diese Umschreibung wuerde der Fristvergleich mit einem naiven
    Zeitstempel abbrechen, statt zu blocken — ein Absturz statt einer
    Entscheidung.
    """
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
