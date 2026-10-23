"""
Scheduler Trigger Endpoints — called by Go Cron-Scheduler.

Each endpoint triggers a Python service synchronously and returns the result.
These run on localhost:8000 (internal only, not exposed by Nginx).

SPEC: docs/specs/modules/go_scheduler.md v1.0 (Step 2)
"""
from __future__ import annotations

import fcntl
import logging
import time
from contextlib import contextmanager
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import Settings
from api.routers.briefings_send import send_briefing
from services.scheduler_dispatch_service import run_compare_presets_daily

logger = logging.getLogger("scheduler")

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@contextmanager
def _poll_lock(name: str):
    """Nicht-blockierender flock je Poll-Kanal (Issue #2439, ADR-0088).

    Cron, Push-Weckruf und Admin-Proxy laufen alle durch diesen Lock, damit
    ``last_seen_id`` bzw. IMAP-``UNSEEN`` nie doppelt abgearbeitet werden.
    Liefert True, wenn der Lock gehalten wird, False bei Belegung.
    """
    from app.loader import get_data_root

    directory = get_data_root() / "diagnostics"
    directory.mkdir(parents=True, exist_ok=True)
    fd = open(directory / name, "a+")
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        fd.close()

@router.post("/trip-reports")
def trigger_trip_reports(at: Optional[str] = None, user_id: str = Query(...)):
    """Trigger trip reports for the current (or a given) point in time.

    Issue #1724: nahm bis dahin eine Stunde entgegen und deutete sie in
    `Europe/Vienna` -- einer Konstante ohne fachliche Herleitung. Ein Trip in
    Auckland wurde dadurch faellig, wenn es in Wien 07:00 war (dort 17:00).
    Uebergeben wird jetzt ein ZEITPUNKT; welche Stunde das ist, entscheidet
    jeder Trip in seiner eigenen Zone (ADR-0051 Regel 2).

    `at` ist optional und dient dem manuellen Ausloesen (ISO-8601). Ohne
    Zeitzonen-Angabe gilt UTC -- Hausnorm #1345, nicht die Prozess-Zeitzone.
    """
    from datetime import datetime, timezone

    from services.trip_report_scheduler import TripReportSchedulerService

    if at is None:
        now_utc = datetime.now(timezone.utc)
    else:
        try:
            now_utc = datetime.fromisoformat(at)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unlesbarer Zeitpunkt: {at!r}")
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

    service = TripReportSchedulerService(user_id=user_id)
    # Issue #766: (sent, failed) — bei Teilfehlern status="partial" zurückgeben,
    # damit das externe Monitoring 452-Rate-Limit-Ausfälle erkennen kann.
    started_at = time.monotonic()
    sent, failed = service.send_due_reports(now_utc)
    duration_s = round(time.monotonic() - started_at, 3)
    logger.info(
        f"trip_reports: Lauf beendet nach {duration_s:.3f}s fuer "
        f"user_id={user_id} (sent={sent} failed={failed})"
    )
    status = "partial" if failed > 0 else "ok"
    return {"status": status, "count": sent, "failed": failed, "duration_s": duration_s}


@router.post("/alert-checks")
def trigger_alert_checks(user_id: str = Query(...)):
    """Trigger weather change alert checks.

    Issue #1447 (S1): ``check_all_trips()`` liefert seit dieser Scheibe ein
    ``AlertCheckRunResult`` statt eines blossen ``int`` — bei Abbruch durch
    die Zeitobergrenze meldet die Antwort ``status: "partial"`` inkl.
    ``checked``/``skipped``/``reason``, ansonsten unveraendert ``status: "ok"``.
    """
    from services.trip_alert import TripAlertService

    service = TripAlertService(user_id=user_id)
    result = service.check_all_trips()
    response = {
        "status": "partial" if result.hit_deadline else "ok",
        "count": result.alerts_sent,
        "checked": result.checked,
        "skipped": result.skipped,
        "skipped_ids": result.skipped_ids,
        "duration_s": result.duration_s,
        "failed": result.failed,
    }
    if result.hit_deadline:
        response["reason"] = "deadline"
    return response


@router.post("/compare-alert-checks")
def trigger_compare_alert_checks(user_id: str = Query(...)):
    """Trigger Compare-Preset Deviation-Alert-Checks (Issue #1169, Epic #1095)
    UND amtliche Warnungen (vormals eigener Endpoint
    ``/compare-official-alert-checks``, Issue #1216 Slice 2a).

    Fix #2286 (AC-9): Muster Trip -- dort laufen amtliche Warnungen im
    ``alert-checks``-Lauf mit. Beide Teile laufen nacheinander, JEDER in
    eigenem try-Block (Fehlerisolation): wirft einer, laeuft der andere
    trotzdem, und der Fehler zaehlt als ``failed``. ``count``/``failed``/
    ``duration_s`` werden summiert; ``checked`` ist die Zahl gepruefter
    Presets (beide Teile pruefen dieselben Presets -> Maximum, nicht Summe).
    """
    from services.compare_alert import CompareAlertService
    from services.compare_official_alert import CompareOfficialAlertService

    count = failed = checked = 0
    duration_s = 0.0
    for name, service_cls in (
        ("compare_alert", CompareAlertService),
        ("compare_official_alert", CompareOfficialAlertService),
    ):
        try:
            service = service_cls(user_id=user_id)
            count += service.check_all_compare_presets()
            failed += service.last_failed_count
            checked = max(checked, service.last_checked_count)
            duration_s += service.last_duration_s
        except Exception:
            logger.exception(f"{name}: Lauf fuer user_id={user_id} abgebrochen")
            failed += 1
    return {
        "status": "ok",
        "count": count,
        "failed": failed,
        "checked": checked,
        "duration_s": round(duration_s, 3),
    }


def _radar_run_response(result, dienst: str, user_id: str) -> dict:
    """Antwort der Radar-Laeufe (Epic #2261 A-2 S2): bisherige Felder plus
    checked/skipped/skipped_ids/duration_s; Grenzabbruch = partial/deadline."""
    logger.info(
        f"{dienst}: Lauf beendet nach {result.duration_s:.3f}s fuer "
        f"user_id={user_id} (checked={result.checked} skipped={result.skipped})"
    )
    body = {
        "status": "partial" if result.hit_deadline else "ok",
        "count": result.alerts_sent,
        "checked": result.checked,
        "skipped": result.skipped,
        "skipped_ids": result.skipped_ids,
        "duration_s": round(result.duration_s, 3),
        "failed": result.failed,
    }
    if result.hit_deadline:
        body["reason"] = "deadline"
    return body


@router.post("/radar-alert-checks")
def trigger_radar_alert_checks(user_id: str):
    """Trigger radar/thunderstorm nowcast alert checks (proaktiv)."""
    from services.trip_alert import TripAlertService

    return _radar_run_response(
        TripAlertService(user_id=user_id).check_radar_alerts_run(), "radar_alert", user_id
    )


@router.post("/compare-radar-alert-checks")
def trigger_compare_radar_alert_checks(user_id: str):
    """Trigger Compare-Preset Radar-Onset-Alert-Checks (Issue #1041 Slice 1b, Epic #1095)."""
    from services.compare_radar_alert import CompareRadarAlertService

    return _radar_run_response(
        CompareRadarAlertService(user_id=user_id).check_all_compare_presets_run(),
        "compare_radar_alert",
        user_id,
    )


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

    with _poll_lock("inbound_command_poll.lock") as frei:
        if not frei:
            return {"status": "busy"}
        reader = InboundEmailReader()
        count = reader.poll_and_process(settings)
    # Issue #2439: "processed" steuert den Nachversuch des Push-Weckrufs in Go.
    return {"status": "ok", "count": count, "processed": count}


@router.post("/inbound-sms")
def trigger_inbound_sms():
    """Trigger Premium-SMS-Rueckkanal-Polling (Issue #1676 Scheibe S1).

    Fix F001 (Adversary-Fund): der Status wird aus dem tatsaechlichen
    Fehlschlag-Zaehler abgeleitet (Hausnorm run_briefing_dispatch(),
    dispatch_orchestrator.py:157), nicht mehr bedingungslos "ok" gemeldet --
    sonst bleibt ein wiederholter Lernfehler (z.B. Go-API-Neustart waehrend
    des Polls) unsichtbar, obwohl die Garmin-Rueckadresse verloren geht.

    HTTP bleibt bei 200 -- Hausnorm der Nachbar-Endpunkte
    `trigger_trip_reports` (Issue #766) und `trigger_compare_presets_daily`
    (Issue #1290), beide melden `status: "partial"` ebenfalls mit HTTP 200:
    die Anfrage wurde ordentlich bearbeitet, ein 503 waere eine falsche
    Aussage ueber die HTTP-Ebene. Die Sichtbarkeit fuer den Zeitplaner
    entsteht stattdessen ueber den Antwortkoerper -- ausgewertet in
    `internal/scheduler/scheduler.go::premiumSmsPoll()` (Fix F002).
    """
    from services.inbound_sms_reader import InboundSmsReader

    settings = Settings()
    reader = InboundSmsReader()
    with _poll_lock("inbound_sms_poll.lock") as frei:
        if not frei:
            return {"status": "busy"}
        count = reader.poll_and_process(settings)
    failed = reader.last_failed_count
    # Issue #2154 AC-11: eine bewusste Ablehnung (409 fehlender/ungueltiger
    # Verknuepfungs-Code, 429 Ratebremse) ist KEIN Netz-/5xx-Fehler und darf
    # `failed` nicht erhoehen -- als "ok" durchgehen darf sie aber auch nicht,
    # sonst bleibt ein dauerhaft ausgesperrter Nutzer unsichtbar. Denselben
    # Wert "partial" wertet internal/scheduler/scheduler.go::
    # triggerPremiumSmsPollEndpoint bereits zu einem sichtbaren
    # partialRunError aus -- kein neues Go-Statusfeld noetig.
    rejected = getattr(reader, "last_rejected_count", 0)
    status = "partial" if failed > 0 or rejected > 0 else "ok"
    # Issue #2439: "processed" = in diesem Lauf gefundene/verarbeitete Befehle.
    return {
        "status": status, "count": count, "failed": failed,
        "rejected": rejected, "processed": count,
    }


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
    # Fix #2286 (AC-8): gleiche Feldmenge wie /trip-reports inkl. duration_s.
    started_at = time.monotonic()
    sent, failed = run_compare_presets_daily(user_id, hour=hour)
    duration_s = round(time.monotonic() - started_at, 3)
    status = "partial" if failed > 0 else "ok"
    return {"status": status, "count": sent, "failed": failed, "duration_s": duration_s}


@router.post("/trips/{trip_id}/send")
def send_test_trip_report(trip_id: str, user_id: str = Query(...), report_type: str = "evening"):
    """Test-Versand für einen spezifischen Trip. Issue #695.

    Issue #2280 (AC-13): Delegate auf den geteilten Helfer des Endpoints
    ``POST /api/briefings/{id}/send`` — gleiche Antwort- und Fehlerform; die
    Alt-Route behaelt den Default ``report_type=evening``.
    """
    return send_briefing("route", trip_id, user_id, report_type)


@router.post("/compare-presets/{preset_id}/send")
def manual_send_compare_preset(preset_id: str, user_id: str = Query(...)):
    """Einzelversand-Trigger fuer ein Compare-Preset. Issue #627.

    Ignoriert schedule — sendet sofort. Issue #2280 (AC-13): Delegate auf den
    geteilten Helfer des Endpoints ``POST /api/briefings/{id}/send``.
    """
    return send_briefing("vergleich", preset_id, user_id, "morning")
