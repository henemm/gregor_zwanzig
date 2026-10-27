"""Ein Fehlervokabular fuer den Handversand von Trip und Ortsvergleich (#2280).

Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-9)

EINE Zuordnung Code -> (HTTP-Status, deutscher Text) und EINE Ableitung des
Versand-Ausgangs aus einem ``NotificationResult`` — geteilt von Trip und
Ortsvergleich, damit beide Flaechen denselben Code mit demselben Text melden.
Texte mit Platzhaltern werden mit ``str.format`` gefuellt.
"""
from __future__ import annotations

SEND_OUTCOMES: dict[str, tuple[int, str]] = {
    "kind_required": (400, "Briefing-Art fehlt oder ist ungültig (erlaubt: route, vergleich)"),
    "not_found": (404, "Briefing {entity_id} nicht gefunden"),
    "already_in_progress": (409, "Versand läuft bereits — bitte warten"),
    "no_stage": (
        422, "Kein Briefing für {report_type} — keine Etappendaten für das aktuelle Datum",
    ),
    "no_weather": (422, "Kein Briefing versendet — keine Wetterdaten verfügbar"),
    "no_channels": (
        422,
        "Kein Briefing versendet — kein Versandweg aktiv "
        "(E-Mail, Telegram und SMS sind alle deaktiviert)",
    ),
    "channels_unreachable": (
        422,
        "Kein Briefing versendet — Versandweg konfiguriert, aber nicht "
        "einsatzbereit (Kanal technisch nicht erreichbar)",
    ),
    "invalid_report_type": (
        422, "Ungültiger Berichtstyp {report_type} (erlaubt: morning, evening)",
    ),
    "smtp_not_configured": (422, "E-Mail-Versand (SMTP) ist für diesen Nutzer nicht eingerichtet"),
    # Ortsvergleich nicht versendbar (z.B. alle Orte geloescht, #2216) — der
    # Grund kommt aus dem Versand selbst.
    "invalid_preset": (422, "Ortsvergleich nicht versendbar: {reason}"),
    # Unerwarteter Fehler im Versand (Ausnahme, Traceback im Log) — bewusst 500.
    "send_failed": (500, "Versand fehlgeschlagen — interner Fehler, bitte später erneut versuchen"),
}


class SendOutcomeError(ValueError):
    """Versand ohne Zustellung mit einem Code aus ``SEND_OUTCOMES``.

    Unterklasse von ``ValueError``: der fehler-isolierende Cron-Wrapper
    (``_dispatch_due_preset``) verbucht den Lauf dadurch unveraendert als
    "nicht versendet", ohne abzubrechen (AC-8)."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or f"Versand ohne Zustellung: {code}")
        self.code = code


def outcome_from_result(result) -> str:
    """``NotificationResult`` -> ``"no_channels"`` | ``"channels_unreachable"`` | ``"sent"``."""
    if result.no_channel_configured:
        return "no_channels"
    if not result.sent:
        return "channels_unreachable"
    return "sent"


def error_body(code: str, **values: str) -> tuple[int, dict]:
    """(HTTP-Status, ``{"detail": <Text>, "code": <code>}``) aus dem Vokabular."""
    status, template = SEND_OUTCOMES[code]
    return status, {"detail": template.format(**values), "code": code}
