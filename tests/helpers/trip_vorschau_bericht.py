"""Trip-Vorschau ueber die bleibenden Naehte des ``PreviewService`` (#1743).

Die Kanal-Huellen ``PreviewService.render_email_preview``/
``.render_telegram_preview`` sind mit dem Vorschau-Rueckbau (#1743 AC-31)
entfallen. Ihre Pruefzwecke bleiben: dieser Helfer spielt exakt die Abfolge
der entfallenen Huellen nach — ``_load_trip`` -> ``_resolve_target_date`` ->
``_build_report`` (mit echter ``user_id``) — und liefert den fertigen Report.
"""
from __future__ import annotations

from datetime import datetime, timezone

TELEGRAM_TRENNER = "\n\n---\n\n"


def trip_bericht(service, trip_id: str, *, user_id: str, report_type: str = "morning",
                 target_date: str | None = None, demo: bool = False):
    """Baut den Report wie die entfallenen Huellen (ein Report-Bau, kein Versand)."""
    from services.preview_service import VALID_REPORT_TYPES

    if report_type not in VALID_REPORT_TYPES:
        raise ValueError(f"Ungültiger report_type '{report_type}'")
    trip = service._load_trip(trip_id, user_id=user_id)
    now_utc = datetime.now(timezone.utc)
    target = service._resolve_target_date(trip, target_date, now_utc=now_utc)
    report, _segments, _stage_name, _trip_tz = service._build_report(
        trip, target, report_type, now_utc=now_utc, demo=demo, user_id=user_id,
    )
    return report


def trip_email_html(service, trip_id: str, *, user_id: str, **kwargs) -> str:
    """E-Mail-HTML der Vorschau (vormals ``render_email_preview``)."""
    from services.preview_service import _email_html_of

    return _email_html_of(trip_bericht(service, trip_id, user_id=user_id, **kwargs))


def trip_telegram(service, trip_id: str, *, user_id: str, **kwargs) -> tuple[str, str, list[str]]:
    """(subject, body, bubbles) wie vormals ``render_telegram_preview``."""
    report = trip_bericht(service, trip_id, user_id=user_id, **kwargs)
    bubbles = report.telegram_bubbles or []
    return report.email_subject, TELEGRAM_TRENNER.join(bubbles), bubbles
