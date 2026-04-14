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

import httpx
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

# BetterStack Heartbeat URLs (pinged after successful report runs)
# Note: Go scheduler also pings these. During parallel phase, both ping.
HEARTBEAT_MORNING = "https://uptime.betterstack.com/api/v1/heartbeat/f4GBDxFQHxuu73FdRt5wjGsQ"
HEARTBEAT_EVENING = "https://uptime.betterstack.com/api/v1/heartbeat/5Cc4vmiEDgrSr7qsBa2k2av4"

# Global scheduler instance
_scheduler: BackgroundScheduler | None = None

# Tracks last run result per job: {job_id: {"time": iso_str, "status": "ok"|"error", "error": str|None}}
_job_results: dict[str, dict] = {}


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

    # Alert Checks - Every 30 minutes for weather change alerts (Feature 3.4)
    _scheduler.add_job(
        run_alert_checks,
        CronTrigger(minute="0,30", timezone=TIMEZONE),
        id="alert_checks",
        name="Alert Checks (every 30 min)",
    )

    # Inbound Command Poll - Every 5 minutes for email commands (Feature 6)
    _scheduler.add_job(
        run_inbound_command_poll,
        CronTrigger(minute="*/5", timezone=TIMEZONE),
        id="inbound_command_poll",
        name="Inbound Command Poll (every 5min)",
    )

    _scheduler.start()
    logger.info(f"Scheduler started: Subscriptions 07:00/18:00, Trip Reports hourly, Alert Checks every 30min, Inbound Commands every 5min ({TIMEZONE})")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler shutdown complete")


def _record_run(job_id: str, func, *args, **kwargs) -> None:
    """Run a job function and record its result (time, status, error)."""
    try:
        func(*args, **kwargs)
        _job_results[job_id] = {
            "time": datetime.now(TIMEZONE).isoformat(),
            "status": "ok",
            "error": None,
        }
    except Exception as e:
        _job_results[job_id] = {
            "time": datetime.now(TIMEZONE).isoformat(),
            "status": "error",
            "error": str(e),
        }
        raise


def run_morning_subscriptions() -> None:
    """Run all DAILY_MORNING subscriptions."""
    def _do():
        from app.user import Schedule
        logger.info("Running morning subscriptions...")
        _run_subscriptions_by_schedule(Schedule.DAILY_MORNING)
    _record_run("morning_subscriptions", _do)
    _ping_heartbeat(HEARTBEAT_MORNING)


def run_evening_subscriptions() -> None:
    """Run DAILY_EVENING and matching WEEKLY subscriptions."""
    def _do():
        from app.user import Schedule
        logger.info("Running evening subscriptions...")
        _run_subscriptions_by_schedule(Schedule.DAILY_EVENING)
        _run_weekly_subscriptions()
    _record_run("evening_subscriptions", _do)
    _ping_heartbeat(HEARTBEAT_EVENING)


def run_alert_checks() -> None:
    """Check all active trips for weather changes (Feature 3.4)."""
    def _do():
        from services.trip_alert import TripAlertService
        service = TripAlertService()
        count = service.check_all_trips()
        if count > 0:
            logger.info(f"Alert checks: {count} alerts sent")
    _record_run("alert_checks", _do)


def run_trip_reports_check() -> None:
    """Check which trips need reports at this hour (Feature 3.3 + 3.5)."""
    def _do():
        from services.trip_report_scheduler import TripReportSchedulerService
        now = datetime.now(TIMEZONE)
        current_hour = now.hour
        service = TripReportSchedulerService()
        count = service.send_reports_for_hour(current_hour)
        if count > 0:
            logger.info(f"Trip reports at {current_hour:02d}:00: {count} sent")
    _record_run("trip_reports_hourly", _do)


def run_inbound_command_poll() -> None:
    """Poll inbound channels for trip commands (Feature 6)."""
    def _do():
        from app.config import Settings
        from services.inbound_email_reader import InboundEmailReader
        settings = Settings()
        imap_user = settings.imap_user or settings.smtp_user
        imap_pass = settings.imap_pass or settings.smtp_pass
        if not imap_user or not imap_pass:
            return
        reader = InboundEmailReader()
        count = reader.poll_and_process(settings)
        if count > 0:
            logger.info(f"Inbound commands processed: {count}")
    _record_run("inbound_command_poll", _do)


def _ping_heartbeat(url: str) -> None:
    """Ping BetterStack heartbeat URL. Fire-and-forget with logging."""
    try:
        response = httpx.get(url, timeout=5)
        response.raise_for_status()
        logger.info(f"Heartbeat ping OK: {url[-8:]}")
    except Exception as e:
        logger.warning(f"Heartbeat ping failed: {e}")


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
    """Execute a single subscription and send via selected channels."""
    from app.config import Settings
    from app.loader import load_all_locations
    from services.compare_subscription import run_comparison_for_subscription

    logger.info(f"Executing subscription: {sub.name}")

    try:
        settings = Settings()
        all_locations = load_all_locations()

        subject, html_body, text_body = run_comparison_for_subscription(sub, all_locations)

        if not sub.send_email and not sub.send_signal:
            logger.warning(f"No channels configured for subscription: {sub.name}")
            return

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

    except Exception as e:
        logger.error(f"Failed to execute subscription {sub.name}: {e}")


def get_scheduler_status() -> dict:
    """Get current scheduler status for UI display."""
    if _scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    for job in _scheduler.get_jobs():
        last_run = _job_results.get(job.id)
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "last_run": last_run,
        })

    return {
        "running": _scheduler.running,
        "jobs": jobs,
    }
