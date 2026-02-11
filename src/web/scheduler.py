"""
Background Scheduler for Compare Subscriptions and Trip Reports.

Automatically sends emails for subscriptions and trip reports based on schedule:
- DAILY_MORNING: 07:00 Europe/Vienna
- DAILY_EVENING: 18:00 Europe/Vienna
- WEEKLY: 18:00 on configured weekday

SPEC: docs/specs/modules/scheduler.md v1.1
SPEC: docs/specs/modules/trip_report_scheduler.md v1.0 (Feature 3.3)
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from app.user import CompareSubscription

# Configure logging to stdout for visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("scheduler")

# Explicit timezone for all cron triggers (v1.1 fix)
TIMEZONE = ZoneInfo("Europe/Vienna")

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None


def init_scheduler() -> None:
    """
    Initialize and start the background scheduler.

    Called on NiceGUI server startup via app.on_startup().
    """
    global _scheduler

    # Avoid double initialization
    if _scheduler is not None:
        logger.warning("Scheduler already initialized, skipping")
        return

    _scheduler = BackgroundScheduler()

    # Morning subscriptions at 07:00 Europe/Vienna
    _scheduler.add_job(
        run_morning_subscriptions,
        CronTrigger(hour=7, minute=0, timezone=TIMEZONE),
        id="morning_subscriptions",
        name="Morning Subscriptions (07:00)",
    )

    # Evening subscriptions at 18:00 Europe/Vienna
    _scheduler.add_job(
        run_evening_subscriptions,
        CronTrigger(hour=18, minute=0, timezone=TIMEZONE),
        id="evening_subscriptions",
        name="Evening Subscriptions (18:00)",
    )

    # Trip Reports - Hourly check for per-trip configured times (Feature 3.3 + 3.5)
    _scheduler.add_job(
        run_trip_reports_check,
        CronTrigger(minute=0, timezone=TIMEZONE),
        id="trip_reports_hourly",
        name="Trip Reports (hourly check)",
    )

    _scheduler.start()
    logger.info(f"Scheduler started: Subscriptions at 07:00/18:00, Trip Reports hourly ({TIMEZONE})")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler shutdown complete")


def run_morning_subscriptions() -> None:
    """Run all DAILY_MORNING subscriptions."""
    from app.user import Schedule

    logger.info("Running morning subscriptions...")
    _run_subscriptions_by_schedule(Schedule.DAILY_MORNING)


def run_evening_subscriptions() -> None:
    """Run DAILY_EVENING and matching WEEKLY subscriptions."""
    from app.user import Schedule

    logger.info("Running evening subscriptions...")
    _run_subscriptions_by_schedule(Schedule.DAILY_EVENING)
    _run_weekly_subscriptions()


def run_trip_reports_check() -> None:
    """Check which trips need reports at this hour (Feature 3.3 + 3.5)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    now = datetime.now(TIMEZONE)
    current_hour = now.hour

    service = TripReportSchedulerService()
    count = service.send_reports_for_hour(current_hour)
    if count > 0:
        logger.info(f"Trip reports at {current_hour:02d}:00: {count} sent")


def _run_weekly_subscriptions() -> None:
    """Run WEEKLY subscriptions if today matches the weekday."""
    from app.loader import load_compare_subscriptions
    from app.user import Schedule

    current_weekday = datetime.now().weekday()
    logger.info(f"Checking weekly subscriptions for weekday {current_weekday}")

    for sub in load_compare_subscriptions():
        if sub.enabled and sub.schedule == Schedule.WEEKLY:
            if sub.weekday == current_weekday:
                logger.info(f"Weekly subscription matches: {sub.name}")
                _execute_subscription(sub)


def _run_subscriptions_by_schedule(schedule: "Schedule") -> None:
    """Run all subscriptions matching the given schedule."""
    from app.loader import load_compare_subscriptions

    for sub in load_compare_subscriptions():
        if sub.enabled and sub.schedule == schedule:
            _execute_subscription(sub)


def _execute_subscription(sub: "CompareSubscription") -> None:
    """Execute a single subscription and send email."""
    from app.config import Settings
    from app.loader import load_all_locations
    from outputs.email import EmailOutput
    from web.pages.compare import run_comparison_for_subscription

    logger.info(f"Executing subscription: {sub.name}")

    try:
        settings = Settings()

        if not settings.can_send_email():
            logger.error(f"SMTP not configured, cannot send email for: {sub.name}")
            return

        # Load locations
        all_locations = load_all_locations()

        # Generate email content
        # SPEC: docs/specs/compare_email.md v4.2 - Multipart Email
        subject, html_body, text_body = run_comparison_for_subscription(sub, all_locations)

        # Send email with both HTML and Plain-Text
        email_output = EmailOutput(settings)
        email_output.send(subject, html_body, plain_text_body=text_body)

        logger.info(f"Email sent successfully for: {sub.name}")

    except Exception as e:
        logger.error(f"Failed to execute subscription {sub.name}: {e}")


def get_scheduler_status() -> dict:
    """Get current scheduler status for UI display."""
    if _scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "running": _scheduler.running,
        "jobs": jobs,
    }
