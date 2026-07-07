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

from app.config import Settings
from services.scheduler_dispatch_service import (
    run_compare_presets_daily,
    save_subscription_status,
    send_compare_preset,
    send_subscription_email,
    send_subscription_telegram,
)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
logger = logging.getLogger("scheduler.trigger")

_telegram_reader = None


@router.post("/trip-reports")
def trigger_trip_reports(hour: Optional[int] = None, user_id: str = "default"):
    """Trigger trip reports for current or specified hour."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from services.trip_report_scheduler import TripReportSchedulerService

    tz = ZoneInfo("Europe/Vienna")
    current_hour = hour if hour is not None else datetime.now(tz).hour

    service = TripReportSchedulerService(user_id=user_id)
    # Issue #766: (sent, failed) — bei Teilfehlern status="partial" zurückgeben,
    # damit das externe Monitoring 452-Rate-Limit-Ausfälle erkennen kann.
    sent, failed = service.send_reports_for_hour(current_hour)
    status = "partial" if failed > 0 else "ok"
    return {"status": status, "count": sent, "failed": failed}


@router.post("/alert-checks")
def trigger_alert_checks(user_id: str = "default"):
    """Trigger weather change alert checks."""
    from services.trip_alert import TripAlertService

    service = TripAlertService(user_id=user_id)
    count = service.check_all_trips()
    return {"status": "ok", "count": count}


@router.post("/radar-alert-checks")
def trigger_radar_alert_checks(user_id: str):
    """Trigger radar/thunderstorm nowcast alert checks (proaktiv)."""
    from services.trip_alert import TripAlertService

    service = TripAlertService(user_id=user_id)
    count = service.check_radar_alerts()
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


@router.post("/inbound-telegram")
def trigger_inbound_telegram():
    """Trigger Telegram Bot polling."""
    global _telegram_reader
    from services.inbound_telegram_reader import InboundTelegramReader

    settings = Settings()
    if not settings.can_send_telegram():
        return {"status": "skipped", "reason": "telegram not configured"}
    if _telegram_reader is None:
        _telegram_reader = InboundTelegramReader()
    count = _telegram_reader.poll_and_process(settings)
    return {"status": "ok", "processed": count}


@router.post("/compare-presets-daily")
def trigger_compare_presets_daily(user_id: str = "default"):
    """Trigger daily compare preset dispatch (called by Go scheduler at 06:00)."""
    count = run_compare_presets_daily(user_id)
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
        if sub.send_email and settings.can_send_email():
            send_subscription_email(sub, subject, html_body, text_body, settings)
        elif sub.send_email:
            logger.error(f"Email requested but SMTP not configured: {sub.name}")
        if sub.send_telegram and settings.can_send_telegram():
            try:
                send_subscription_telegram(sub, subject, text_body, settings)
            except Exception as e:
                logger.error(f"Telegram failed for {sub.name}: {e}")
        elif sub.send_telegram:
            logger.warning(f"Telegram requested but not configured: {sub.name}")
        sub.last_run = datetime.utcnow().isoformat() + "Z"
        sub.last_status = "ok"
        sub.top_ort_letzter_versand = winner_name
        save_subscription_status(user_id, sub)
        return {"status": "ok", "winner": winner_name or ""}
    except HTTPException:
        raise
    except Exception as e:
        sub.last_run = datetime.utcnow().isoformat() + "Z"
        sub.last_status = "error"
        try:
            save_subscription_status(user_id, sub)
        except Exception as save_err:
            logger.error(f"Failed to persist error-status for {sub.name}: {save_err}")
        raise HTTPException(status_code=500, detail=str(e))

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


@router.post("/trips/{trip_id}/send")
def send_test_trip_report(trip_id: str, user_id: str = "default", report_type: str = "evening"):
    """Test-Versand für einen spezifischen Trip. Issue #695."""
    from app.config import Settings
    from app.loader import load_all_trips
    from services.trip_report_scheduler import TripReportSchedulerService

    # AC-5: Trip-Existenz zuerst prüfen — vor SMTP-Check (F002-Fix)
    all_trips = load_all_trips(user_id=user_id)
    trip = next((t for t in all_trips if t.id == trip_id), None)
    if trip is None:
        raise HTTPException(status_code=404, detail=f"Trip {trip_id} not found")

    # Issue #904: Trip ohne Etappen muss 422 liefern, bevor der SMTP-Check
    # eine irreführende "SMTP not configured"-Meldung zurückgibt.
    if not trip.stages:
        raise HTTPException(
            status_code=422,
            detail=f"Kein Briefing für {report_type} — keine Etappen",
        )

    # AC-6: SMTP-Check nach Trip-Lookup
    settings = Settings().with_user_profile(user_id)
    if not settings.can_send_email():
        raise HTTPException(status_code=422, detail="SMTP not configured for this user")

    service = TripReportSchedulerService(user_id=user_id)
    try:
        sent = service.send_test_report(trip, report_type)
    except ValueError as e:
        # F003-Fix: Ungültiger report_type → 422 statt 500
        raise HTTPException(status_code=422, detail=str(e))
    if not sent:
        raise HTTPException(
            status_code=422,
            detail=f"Kein Briefing für {report_type} — keine Etappendaten für das aktuelle Datum",
        )
    return {"status": "ok", "trip_id": trip_id, "report_type": report_type, "sent": True}


@router.post("/compare-presets/{preset_id}/send")
def manual_send_compare_preset(preset_id: str, user_id: str = Query("default")):
    """Einzelversand-Trigger fuer ein Compare-Preset. Issue #627.

    Ignoriert schedule — sendet sofort, egal ob daily/weekly/manual.
    """
    try:
        return send_compare_preset(user_id, preset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
