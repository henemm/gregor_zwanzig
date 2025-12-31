"""
Background Scheduler for Compare Subscriptions.

Automatically sends emails for subscriptions based on their schedule:
- DAILY_MORNING: 07:00
- DAILY_EVENING: 18:00
- WEEKLY: 18:00 on configured weekday
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from app.user import CompareSubscription

logger = logging.getLogger("scheduler")

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

    # Morning subscriptions at 07:00
    _scheduler.add_job(
        run_morning_subscriptions,
        CronTrigger(hour=7, minute=0),
        id="morning_subscriptions",
        name="Morning Subscriptions (07:00)",
    )

    # Evening subscriptions at 18:00
    _scheduler.add_job(
        run_evening_subscriptions,
        CronTrigger(hour=18, minute=0),
        id="evening_subscriptions",
        name="Evening Subscriptions (18:00)",
    )

    _scheduler.start()
    logger.info("Scheduler started with 2 jobs (morning 07:00, evening 18:00)")


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
        subject, body = run_comparison_for_subscription(sub, all_locations)

        # Send email
        email_output = EmailOutput(settings)
        email_output.send(subject, body)

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
