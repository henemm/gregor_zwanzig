"""Staging-only debug endpoints — Issue #830.

Nur aktiv wenn GZ_ENV=staging. Erlaubt das manuelle Ausloesen des
Radar-Alert-Pfads fuer IMAP-basierte Validator-Tests.

Exit fuer alle anderen Umgebungen: HTTP 404.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/debug", tags=["debug"])
logger = logging.getLogger(__name__)


def _pick_debug_segment(trip, now_utc, today):
    """Segmentwahl der Debug-Route (Issue #2985).

    1. `resolve_current_segment` liefert ein Segment -> genau dieses.
    2. Sonst Test-Seam-Rueckfall (nur Debug): erstes Segment von `today`,
       sonst erstes Segment des ersten Etappendatums mit Segmenten.
    3. Sonst None.
    """
    # Lazy import (Zirkularimport-Schutz beim Prod-Startup)
    from services.trip_segments import convert_trip_to_segments, resolve_current_segment

    resolved = resolve_current_segment(trip, now_utc, today)
    if resolved is not None:
        return resolved[0]

    segments = convert_trip_to_segments(trip, today)
    if segments:
        return segments[0]
    for stage in getattr(trip, "stages", None) or []:
        stage_date = getattr(stage, "date", None)
        if stage_date:
            segments = convert_trip_to_segments(trip, stage_date)
            if segments:
                return segments[0]
    return None


@router.post("/trigger-radar-alert")
def trigger_radar_alert(user_id: str = Query(...)):
    """Staging-only: loest echten Radar-Alert-Pfad aus, sendet an gregor-test@henemm.com.

    Ablauf (analog check_radar_alerts(), ohne Throttle-Check):
    1. Staging-Guard (GZ_ENV=staging) -> sonst 404.
    2. Trips fuer user_id laden.
    3. Ersten Trip + Segment ableiten ueber `_pick_debug_segment`: zuerst der
       gemeinsame Baustein `resolve_current_segment` (wie
       `TripAlertService.check_radar_alerts()`, inkl. Vortags-Rueckgriff bei
       Ankunft nach Mitternacht, Issue #2985). Nur wenn der nichts liefert,
       greift ein Test-Seam-Rueckfall (Staging-Testdaten liegen oft in der
       Vergangenheit): erstes Segment von heute, sonst erstes Segment des
       ersten Etappendatums mit Segmenten; sonst `no_segment`.
    4. Nowcast-Ergebnis als deterministisches Fixture injizieren (source="test") —
       KEIN echter Quellen-Abruf (#1190): geprueft wird nur die Alarm-Mechanik
       (Throttle/Mail-Format/Cooldown), nicht die Provider-Kette. Fuer
       Provider-/Source-Chain-Verifikation ungeeignet.
    5. Mail an gregor-test@henemm.com senden (mail_type=radar-alert).
    6. Kein radar_alert_due()-Check, kein Throttle-Eintrag (Test-Seam).
    """
    import sys
    from datetime import datetime, timezone
    from pathlib import Path
    from types import SimpleNamespace

    src_dir = Path(__file__).resolve().parents[2] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from app.config import Settings

    settings = Settings()
    if settings.env != "staging":
        raise HTTPException(status_code=404, detail="Not found")

    # Lazy imports (Zirkularimport-Schutz beim Prod-Startup)
    from app.loader import load_all_trips
    from services.radar_alert_service import build_debug_onset_alert_message, send_radar_alert_email
    from services.radar_service import RadarNowcastService
    from services.trip_day import trip_local_today

    trips = list(load_all_trips(user_id=user_id))
    if not trips:
        return JSONResponse({"status": "no_trips"})

    trip = trips[0]
    now_utc = datetime.now(timezone.utc)
    today = trip_local_today(trip, now_utc)
    active = _pick_debug_segment(trip, now_utc, today)
    if active is None:
        return JSONResponse({"status": "no_segment"})

    radar_svc = RadarNowcastService()
    # Synthethisches Ergebnis: kein echter Nowcast (Wetter variabel), sondern fester
    # Leichter-Regen-Szenario damit der Validator P-1/P-2/P-3/P-4 sicher pruefen kann.
    result = SimpleNamespace(
        is_convective=False,
        source="test",
        onset_minutes=5,
        intensity_label="Leichter Regen",
    )

    source_label = radar_svc.source_label(getattr(result, "source", "test"))
    segment_label = f"Etappe {getattr(active, 'segment_id', 1)}"

    # Issue #2982: Beginnzeit, Tagesbezug und Event kommen aus dem EINEN
    # Baustein (`onset_event_from_nowcast`) statt einer eigenen Ableitung hier.
    msg = build_debug_onset_alert_message(trip, active, result, source_label)

    # Empfaenger-Override: immer an gregor-test@henemm.com, SMTP immer über Stalwart.
    # for_testing() leitet smtp_host → mail.henemm.com weg von Resend (Issue #924).
    test_settings = settings.for_testing()
    try:
        send_radar_alert_email(
            test_settings,
            msg,
            to="gregor-test@henemm.com",
        )
    except Exception as exc:
        logger.error("Trigger-Endpoint Mail-Versand fehlgeschlagen: %s", exc)  # i18n-log
        raise HTTPException(status_code=500, detail=f"Mail-Versand fehlgeschlagen: {exc}")  # i18n-log (Debug-Router, nur Betreiber)

    logger.info("Trigger-Endpoint: Radar-Alert-Mail gesendet fuer trip=%s, segment=%s", trip.id, segment_label)
    return JSONResponse({"status": "sent", "trip_id": str(trip.id), "segment": segment_label})
