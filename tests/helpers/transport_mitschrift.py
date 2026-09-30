"""Geteilter Transport-Aufzeichner fuer die vier Kanal-Ausgaenge (#2422 S1).

Extrahiert aus ``tests/tdd/test_kanaltreue_adhoc_antwort.py:88-225`` (dortiges
``Kanalmitschrift``/``_aufzeichner_installieren``-Muster), erweitert um
``body``/``plain_text_body``/``parse_mode`` -- die urspruengliche Fassung
zeichnete nur ``subject`` auf.

Ersetzt per ``monkeypatch.setattr`` die vier Ausgangs-Klassen in
``services.notification_service`` (``EmailOutput``/``SMSOutput``/
``PremiumSmsOutput``/``TelegramOutput``). Kein ``Mock()``/``patch()``/
``MagicMock`` -- echte Klassen mit den echten ``send()``-Signaturen. Sie
ersetzen NUR die Naht zum Netz, nicht die Entscheidung darueber, wer bedient
wird -- die faellt weiter im Produktivcode.
"""
from __future__ import annotations

#: Versand-Reihenfolge in ``NotificationService.send_trip_report`` -- dieselbe
#: Reihenfolge steht in ``briefing_log.channels``.
ALLE_KANAELE = ("email", "sms", "premium_sms", "telegram")


class Kanalmitschrift:
    """Was tatsaechlich hinausging -- je Kanal eine Liste von Sendungen."""

    def __init__(self) -> None:
        self.je_kanal: dict[str, list[dict]] = {k: [] for k in ALLE_KANAELE}

    @property
    def kanaele(self) -> list[str]:
        """Bediente Kanaele in der Versand-Reihenfolge des Produktivcodes."""
        return [k for k in ALLE_KANAELE if self.je_kanal[k]]

    def empfaenger(self, kanal: str) -> list:
        return [e["empfaenger"] for e in self.je_kanal[kanal]]

    def sendungen(self, kanal: str) -> list[dict]:
        """Alle aufgezeichneten Sendungen dieses Kanals (Reihenfolge = Versand)."""
        return list(self.je_kanal[kanal])

    def leeren(self) -> None:
        self.je_kanal = {k: [] for k in ALLE_KANAELE}

    def __repr__(self) -> str:  # erscheint in jeder Fehlermeldung
        return f"Kanalmitschrift({({k: v for k, v in self.je_kanal.items() if v})})"


def aufzeichner_installieren(monkeypatch) -> Kanalmitschrift:
    """Echte Klassen mit den echten ``send()``-Signaturen ersetzen die vier
    Ausgaenge. Sie ersetzen die Naht zum Netz, NICHT die Entscheidung darueber,
    wer bedient wird -- die faellt weiter im Produktivcode."""
    from services import notification_service as ns

    mit = Kanalmitschrift()

    def _buchen(kanal: str, empfaenger, subject: str, *, body=None,
                plain_text_body=None, parse_mode=None, mail_type=None,
                mail_format=None, compare_hourly_enabled=None) -> None:
        # ``mail_type``/``mail_format`` (nur E-Mail) machen z.B.
        # ``email_format=compact`` an der Naht beobachtbar (#2422 S3):
        # ``mit.sendungen("email")[i]["mail_format"]``.
        mit.je_kanal[kanal].append({
            "empfaenger": empfaenger, "subject": subject, "body": body,
            "plain_text_body": plain_text_body, "parse_mode": parse_mode,
            "mail_type": mail_type, "mail_format": mail_format,
            # #2422 S5 (AC-29): nur die Vergleichs-Mail reicht das Kennzeichen
            # durch (``send_compare_report``); sonst bleibt es ``None``.
            "compare_hourly_enabled": compare_hourly_enabled,
        })

    class _EmailAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, html=True, plain_text_body=None, to=None,
                 mail_type=None, mail_format=None, compare_hourly_enabled=None):
            # Ohne `to=` faellt `EmailOutput` auf `settings.mail_to` zurueck
            # (email.py:647-650) -- genau die Aufloesung, die AC-7 (Kanaltreue)
            # prueft.
            ziel = to if to else self._s.mail_to
            _buchen("email", ziel if isinstance(ziel, str) else list(ziel)[0],
                    subject, body=body, plain_text_body=plain_text_body,
                    mail_type=mail_type, mail_format=mail_format,
                    compare_hourly_enabled=compare_hourly_enabled)

    class _SmsAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body) -> None:
            _buchen("sms", self._s.sms_to, subject, body=body)

    class _PremiumSmsAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body) -> None:
            _buchen("premium_sms", self._s.premium_sms_reply_to, subject, body=body)

    class _TelegramAufzeichner:
        def __init__(self, settings) -> None:
            self._s = settings

        def send(self, subject, body, reply_markup=None, *, parse_mode=None,
                 suppress_subject_line=False) -> int:
            _buchen("telegram", self._s.telegram_chat_id, subject, body=body,
                    parse_mode=parse_mode)
            return 1

    monkeypatch.setattr(ns, "EmailOutput", _EmailAufzeichner)
    # #2422 S5 (Mitschrift-Falle): ``send_compare_report`` importiert
    # ``EmailOutput`` ERST BEIM AUFRUF aus ``output.channels.email``
    # (notification_service.py:1294). Der Patch auf ``ns.EmailOutput`` sieht die
    # Vergleichs-Mail nie -- ohne diese Zeile waeren Tests gegen den Aufzeichner
    # gruen mit null Sendungen. Der Import passiert erst beim Aufruf, deshalb
    # wirkt ``setattr`` auf das Modulattribut.
    import output.channels.email as email_mod

    monkeypatch.setattr(email_mod, "EmailOutput", _EmailAufzeichner)
    monkeypatch.setattr(ns, "SMSOutput", _SmsAufzeichner)
    monkeypatch.setattr(ns, "PremiumSmsOutput", _PremiumSmsAufzeichner)
    monkeypatch.setattr(ns, "TelegramOutput", _TelegramAufzeichner)
    return mit
