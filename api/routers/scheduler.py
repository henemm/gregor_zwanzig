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
    send_compare_preset,
)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])
logger = logging.getLogger("scheduler.trigger")

_telegram_reader = None


@router.post("/trip-reports")
def trigger_trip_reports(hour: Optional[int] = None, user_id: str = Query(...)):
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
def trigger_alert_checks(user_id: str = Query(...)):
    """Trigger weather change alert checks."""
    from services.trip_alert import TripAlertService

    service = TripAlertService(user_id=user_id)
    count = service.check_all_trips()
    return {"status": "ok", "count": count}


@router.post("/compare-alert-checks")
def trigger_compare_alert_checks(user_id: str = Query(...)):
    """Trigger Compare-Preset Deviation-Alert-Checks (Issue #1169, Epic #1095)."""
    from services.compare_alert import CompareAlertService

    service = CompareAlertService(user_id=user_id)
    count = service.check_all_compare_presets()
    return {"status": "ok", "count": count}


@router.post("/radar-alert-checks")
def trigger_radar_alert_checks(user_id: str):
    """Trigger radar/thunderstorm nowcast alert checks (proaktiv)."""
    from services.trip_alert import TripAlertService

    service = TripAlertService(user_id=user_id)
    count = service.check_radar_alerts()
    return {"status": "ok", "count": count}


@router.post("/compare-radar-alert-checks")
def trigger_compare_radar_alert_checks(user_id: str):
    """Trigger Compare-Preset Radar-Onset-Alert-Checks (Issue #1041 Slice 1b, Epic #1095)."""
    from services.compare_radar_alert import CompareRadarAlertService

    service = CompareRadarAlertService(user_id=user_id)
    count = service.check_all_compare_presets()
    return {"status": "ok", "count": count}


@router.post("/compare-official-alert-checks")
def trigger_compare_official_alert_checks(user_id: str = Query(...)):
    """Trigger Compare-Preset Official-Alert-Standalone-Checks (Issue #1216 Slice 2a)."""
    from services.compare_official_alert import CompareOfficialAlertService

    service = CompareOfficialAlertService(user_id=user_id)
    count = service.check_all_compare_presets()
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
def trigger_compare_presets_daily(hour: Optional[int] = None, user_id: str = Query(...)):
    """Trigger compare preset dispatch for the current or specified hour.

    #1232 Scheibe 2a: Go-Cron ruft diesen Endpoint stuendlich auf (statt
    einmal taeglich um 06:00); Slot-Faelligkeit wird in
    `run_compare_presets_daily` gegen die Stunde geprueft.

    Issue #1290 (E1): (sent, failed) -- bei Teilfehlern status="partial"
    zurueckgeben, identisches Schema zu /trip-reports (#766), damit das
    externe Monitoring einen 100%-Ausfall (Prod-Journal 2026-07-16:
    133/133) von einem leeren Lauf unterscheiden kann.
    """
    sent, failed = run_compare_presets_daily(user_id, hour=hour)
    status = "partial" if failed > 0 else "ok"
    return {"status": status, "count": sent, "failed": failed}


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
