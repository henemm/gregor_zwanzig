"""Ein Fehlervokabular fuer den Handversand von Trip und Ortsvergleich (#2280).

Spec: docs/specs/modules/feat_2280_handversand_endpoint.md (AC-9)

EINE Zuordnung Code -> (HTTP-Status, Katalogschluessel) und EINE Ableitung des
Versand-Ausgangs aus einem ``NotificationResult`` — geteilt von Trip und
Ortsvergleich, damit beide Flaechen denselben Code mit demselben Text melden.
Issue #2671: der Text kommt in der Nutzersprache aus ``versand.ergebnis.<code>``;
``code`` bleibt der stabile Vertrag mit dem Frontend.
"""
from __future__ import annotations

from i18n import Lang, t

SEND_OUTCOMES: dict[str, tuple[int, str]] = {
    code: (status, f"versand.ergebnis.{code}")
    for code, status in (
        ("kind_required", 400),
        ("not_found", 404),
        ("already_in_progress", 409),
        ("no_stage", 422),
        ("no_weather", 422),
        ("no_channels", 422),
        ("channels_unreachable", 422),
        ("invalid_report_type", 422),
        ("smtp_not_configured", 422),
        # Ortsvergleich nicht versendbar (z.B. alle Orte geloescht, #2216) —
        # der Grund kommt aus dem Versand selbst.
        ("invalid_preset", 422),
        # Unerwarteter Fehler im Versand (Ausnahme, Traceback im Log) — bewusst 500.
        ("send_failed", 500),
    )
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


def error_body(code: str, *, lang: Lang = "de", **values: str) -> tuple[int, dict]:
    """(HTTP-Status, ``{"detail": <Text in lang>, "code": <code>}``) aus dem Vokabular."""
    status, key = SEND_OUTCOMES[code]
    return status, {"detail": t(key, lang, **values), "code": code}
