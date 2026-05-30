"""
Scheduler Trigger Endpoints — called by Go Cron-Scheduler.

Each endpoint triggers a Python service synchronously and returns the result.
These run on localhost:8000 (internal only, not exposed by Nginx).

SPEC: docs/specs/modules/go_scheduler.md v1.0 (Step 2)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
logger = logging.getLogger("scheduler.trigger")


@router.post("/morning-subscriptions")
def trigger_morning(user_id: str = "default"):
    """Trigger morning subscription reports."""
    from app.user import Schedule

    count = _run_subscriptions_by_schedule(Schedule.DAILY_MORNING, user_id)
    return {"status": "ok", "count": count}


@router.post("/evening-subscriptions")
def trigger_evening(user_id: str = "default"):
    """Trigger evening + weekly subscription reports."""
    from app.user import Schedule

    count = _run_subscriptions_by_schedule(Schedule.DAILY_EVENING, user_id)
    count += _run_weekly_subscriptions(user_id)
    return {"status": "ok", "count": count}


@router.post("/trip-reports")
def trigger_trip_reports(hour: Optional[int] = None, user_id: str = "default"):
    """Trigger trip reports for current or specified hour."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from services.trip_report_scheduler import TripReportSchedulerService

    tz = ZoneInfo("Europe/Vienna")
    current_hour = hour if hour is not None else datetime.now(tz).hour

    service = TripReportSchedulerService(user_id=user_id)
    count = service.send_reports_for_hour(current_hour)
    return {"status": "ok", "count": count}


@router.post("/alert-checks")
def trigger_alert_checks(user_id: str = "default"):
    """Trigger weather change alert checks."""
    from services.trip_alert import TripAlertService

    service = TripAlertService(user_id=user_id)
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


@router.post("/subscriptions/{subscription_id}/send")
def manual_send_subscription(subscription_id: str, user_id: str = Query("default")):
    """Manueller Versand-Trigger fuer eine einzelne Subscription. Issue #456."""
    from datetime import datetime

    from app.config import Settings
    from app.loader import load_all_locations, load_compare_subscriptions
    from services.compare_subscription import run_comparison_for_subscription

    all_subs = load_compare_subscriptions(user_id=user_id)
    sub = next((s for s in all_subs if s.id == subscription_id), None)
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    all_locations = load_all_locations(user_id=user_id)
    settings = Settings().with_user_profile(user_id)
    try:
        subject, html_body, text_body, winner_name = run_comparison_for_subscription(
            sub, all_locations
        )
        _send_subscription(sub, subject, html_body, text_body, settings)
        sub.last_run = datetime.utcnow().isoformat() + "Z"
        sub.last_status = "ok"
        sub.top_ort_letzter_versand = winner_name
        _save_subscription(user_id, sub)
        return {"status": "ok", "winner": winner_name or ""}
    except HTTPException:
        raise
    except Exception as e:
        sub.last_run = datetime.utcnow().isoformat() + "Z"
        sub.last_status = "error"
        try:
            _save_subscription(user_id, sub)
        except Exception as save_err:
            logger.error(f"Failed to persist error-status for {sub.name}: {save_err}")
        raise HTTPException(status_code=500, detail=str(e))


def _run_subscriptions_by_schedule(schedule, user_id: str = "default") -> int:
    """Run all subscriptions matching the given schedule. Returns count."""
    from datetime import datetime

    from app.config import Settings
    from app.loader import load_all_locations, load_compare_subscriptions
    from services.compare_subscription import run_comparison_for_subscription

    count = 0
    success_count = 0
    settings = Settings().with_user_profile(user_id)
    all_locations = load_all_locations(user_id=user_id)

    for sub in load_compare_subscriptions(user_id=user_id):
        if sub.enabled and sub.schedule == schedule:
            try:
                subject, html_body, text_body, winner_name = run_comparison_for_subscription(
                    sub, all_locations
                )
                _send_subscription(sub, subject, html_body, text_body, settings)
                count += 1
                success_count += 1
                # Issue #252 — Lauf-Status nach Erfolg zurueckschreiben
                sub.last_run = datetime.utcnow().isoformat() + "Z"
                sub.last_status = "ok"
                # Issue #456 — Top-Ort persistieren (None ueberschreibt nicht)
                sub.top_ort_letzter_versand = winner_name
                try:
                    _save_subscription(user_id, sub)
                except Exception as save_err:
                    logger.error(f"Failed to persist run-status for {sub.name}: {save_err}")
            except Exception as e:
                logger.error(f"Failed subscription {sub.name}: {e}")
                # Issue #252 — auch Fehler-Status zurueckschreiben
                sub.last_run = datetime.utcnow().isoformat() + "Z"
                sub.last_status = "error"
                try:
                    _save_subscription(user_id, sub)
                except Exception as save_err:
                    logger.error(f"Failed to persist error-status for {sub.name}: {save_err}")

    if success_count > 0:
        _ping_heartbeat_compare()

    return count


def _run_weekly_subscriptions(user_id: str = "default") -> int:
    """Run WEEKLY subscriptions if today matches the weekday. Returns count."""
    from datetime import datetime

    from app.config import Settings
    from app.loader import load_all_locations, load_compare_subscriptions
    from app.user import Schedule
    from services.compare_subscription import run_comparison_for_subscription

    current_weekday = datetime.now().weekday()
    count = 0
    success_count = 0
    settings = Settings()
    all_locations = load_all_locations(user_id=user_id)

    for sub in load_compare_subscriptions(user_id=user_id):
        if sub.enabled and sub.schedule == Schedule.WEEKLY:
            if sub.weekday == current_weekday:
                try:
                    subject, html_body, text_body, winner_name = run_comparison_for_subscription(
                        sub, all_locations
                    )
                    _send_subscription(sub, subject, html_body, text_body, settings)
                    count += 1
                    success_count += 1
                    sub.last_run = datetime.utcnow().isoformat() + "Z"
                    sub.last_status = "ok"
                    # Issue #456 — Top-Ort persistieren (None ueberschreibt nicht)
                    sub.top_ort_letzter_versand = winner_name
                    try:
                        _save_subscription(user_id, sub)
                    except Exception as save_err:
                        logger.error(f"Failed to persist weekly run-status for {sub.name}: {save_err}")
                except Exception as e:
                    logger.error(f"Failed weekly subscription {sub.name}: {e}")
                    sub.last_run = datetime.utcnow().isoformat() + "Z"
                    sub.last_status = "error"
                    try:
                        _save_subscription(user_id, sub)
                    except Exception as save_err:
                        logger.error(f"Failed to persist weekly error-status for {sub.name}: {save_err}")

    if success_count > 0:
        _ping_heartbeat_compare()

    return count


def _send_subscription(sub, subject: str, html_body: str, text_body: str, settings) -> None:
    """Send subscription result via configured channels."""
    if sub.send_email:
        if settings.can_send_email():
            from outputs.email import EmailOutput

            # Issue #252: per-Subscription recipients override settings.mail_to
            to_list = list(sub.recipients) if getattr(sub, "recipients", None) else None
            EmailOutput(settings).send(
                subject,
                html_body,
                plain_text_body=text_body,
                to=to_list,
            )
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

    if sub.send_telegram:
        if settings.can_send_telegram():
            try:
                from outputs.telegram import TelegramOutput

                TelegramOutput(settings).send(subject, text_body)
                logger.info(f"Telegram sent for: {sub.name}")
            except Exception as e:
                logger.error(f"Telegram failed for {sub.name}: {e}")
        else:
            logger.warning(f"Telegram requested but not configured: {sub.name}")


def _save_subscription(user_id: str, sub, data_root: str | None = None) -> None:
    """Read-modify-write last_run/last_status for a single subscription.

    Issue #252 — Scheduler persists run-status directly in the JSON store
    (no HTTP call to the Go API, because the Go endpoint requires cookie-auth
    that the scheduler doesn't have).

    Only `last_run` and `last_status` are overwritten; every other field of the
    existing JSON entry is preserved (Read-Modify-Write per
    BUG-DATALOSS-GR221 / data_schema_backup contract).

    Args:
        user_id: User identifier (subscription file is per-user).
        sub: CompareSubscription whose last_run / last_status will be written.
        data_root: Optional override of the data root for tests
            (`{data_root}/users/{user_id}/compare_subscriptions.json`).
            Default `None` resolves to `data/users/{user_id}/...`.
    """
    import json as _json
    import os as _os

    base = data_root if data_root else "data"
    path = _os.path.join(base, "users", user_id, "compare_subscriptions.json")
    if not _os.path.exists(path):
        logger.warning("Subscription file not found, cannot persist status: %s", path)
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = _json.load(f)
    except (OSError, _json.JSONDecodeError) as e:
        logger.error("Failed to read subscription file %s: %s", path, e)
        return

    subs = payload.get("subscriptions", [])
    updated = False
    for entry in subs:
        if entry.get("id") == sub.id:
            if sub.last_run is not None:
                entry["last_run"] = sub.last_run
            if sub.last_status is not None:
                entry["last_status"] = sub.last_status
            # Issue #456 — Top-Ort nur schreiben, wenn nicht None (None loescht NICHT)
            top_ort = getattr(sub, "top_ort_letzter_versand", None)
            if top_ort is not None:
                entry["top_ort_letzter_versand"] = top_ort
            updated = True
            break

    if not updated:
        logger.warning("Subscription id %r not found in %s", sub.id, path)
        return

    try:
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Failed to write subscription file %s: %s", path, e)


def _ping_heartbeat_compare() -> None:
    """Fail-soft: Heartbeat-Ping wenn GZ_HEARTBEAT_COMPARE gesetzt.

    Wird ausschliesslich aufgerufen wenn mindestens ein Compare-Versand
    erfolgreich war (Readiness statt Liveness, siehe globale Heartbeat-Regel).

    SPEC: docs/specs/modules/issue_253_compare_email.md §3
    """
    import os

    url = os.getenv("GZ_HEARTBEAT_COMPARE", "")
    if not url:
        logger.debug("GZ_HEARTBEAT_COMPARE nicht gesetzt — kein Heartbeat-Ping")
        return
    try:
        import httpx

        httpx.get(url, timeout=5)
        logger.info("Heartbeat-Ping Compare OK")
    except Exception as e:
        logger.warning("Heartbeat-Ping Compare fehlgeschlagen: %s", e)
