"""
Scheduler Trigger Endpoints — called by Go Cron-Scheduler.

Each endpoint triggers a Python service synchronously and returns the result.
These run on localhost:8000 (internal only, not exposed by Nginx).

SPEC: docs/specs/modules/go_scheduler.md v1.0 (Step 2)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
logger = logging.getLogger("scheduler.trigger")


@router.post("/morning-subscriptions")
def trigger_morning():
    """Trigger morning subscription reports."""
    from app.loader import load_all_locations, load_compare_subscriptions
    from app.user import Schedule
    from services.compare_subscription import run_comparison_for_subscription

    count = _run_subscriptions_by_schedule(Schedule.DAILY_MORNING)
    return {"status": "ok", "count": count}


@router.post("/evening-subscriptions")
def trigger_evening():
    """Trigger evening + weekly subscription reports."""
    from datetime import datetime

    from app.loader import load_compare_subscriptions
    from app.user import Schedule

    count = _run_subscriptions_by_schedule(Schedule.DAILY_EVENING)
    count += _run_weekly_subscriptions()
    return {"status": "ok", "count": count}


@router.post("/trip-reports")
def trigger_trip_reports(hour: Optional[int] = None):
    """Trigger trip reports for current or specified hour."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from services.trip_report_scheduler import TripReportSchedulerService

    tz = ZoneInfo("Europe/Vienna")
    current_hour = hour if hour is not None else datetime.now(tz).hour

    service = TripReportSchedulerService()
    count = service.send_reports_for_hour(current_hour)
    return {"status": "ok", "count": count}


@router.post("/alert-checks")
def trigger_alert_checks():
    """Trigger weather change alert checks."""
    from services.trip_alert import TripAlertService

    service = TripAlertService()
    count = service.check_all_trips()
    return {"status": "ok", "count": count}


@router.post("/inbound-commands")
def trigger_inbound():
    """Trigger inbound email command polling."""
    from app.config import Settings
    from services.inbound_email_reader import InboundEmailReader

    settings = Settings()
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        return {"status": "skipped", "reason": "imap_not_configured"}

    reader = InboundEmailReader()
    count = reader.poll_and_process(settings)
    return {"status": "ok", "count": count}


def _run_subscriptions_by_schedule(schedule) -> int:
    """Run all subscriptions matching the given schedule. Returns count."""
    from app.config import Settings
    from app.loader import load_all_locations, load_compare_subscriptions
    from services.compare_subscription import run_comparison_for_subscription

    count = 0
    settings = Settings()
    all_locations = load_all_locations()

    for sub in load_compare_subscriptions():
        if sub.enabled and sub.schedule == schedule:
            try:
                subject, html_body, text_body = run_comparison_for_subscription(
                    sub, all_locations
                )
                _send_subscription(sub, subject, html_body, text_body, settings)
                count += 1
            except Exception as e:
                logger.error(f"Failed subscription {sub.name}: {e}")

    return count


def _run_weekly_subscriptions() -> int:
    """Run WEEKLY subscriptions if today matches the weekday. Returns count."""
    from datetime import datetime

    from app.config import Settings
    from app.loader import load_all_locations, load_compare_subscriptions
    from app.user import Schedule
    from services.compare_subscription import run_comparison_for_subscription

    current_weekday = datetime.now().weekday()
    count = 0
    settings = Settings()
    all_locations = load_all_locations()

    for sub in load_compare_subscriptions():
        if sub.enabled and sub.schedule == Schedule.WEEKLY:
            if sub.weekday == current_weekday:
                try:
                    subject, html_body, text_body = run_comparison_for_subscription(
                        sub, all_locations
                    )
                    _send_subscription(sub, subject, html_body, text_body, settings)
                    count += 1
                except Exception as e:
                    logger.error(f"Failed weekly subscription {sub.name}: {e}")

    return count


def _send_subscription(sub, subject: str, html_body: str, text_body: str, settings) -> None:
    """Send subscription result via configured channels."""
    if sub.send_email:
        if settings.can_send_email():
            from outputs.email import EmailOutput

            EmailOutput(settings).send(subject, html_body, plain_text_body=text_body)
            logger.info(f"Email sent for: {sub.name}")
        else:
            logger.error(f"Email requested but SMTP not configured: {sub.name}")

    if sub.send_signal:
        if settings.can_send_signal():
            try:
                from outputs.signal import SignalOutput

                SignalOutput(settings).send(subject, text_body)
                logger.info(f"Signal sent for: {sub.name}")
            except Exception as e:
                logger.error(f"Signal failed for {sub.name}: {e}")
        else:
            logger.warning(f"Signal requested but not configured: {sub.name}")
