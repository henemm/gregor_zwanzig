"""
Staging-only debug endpoints — Issue #830.

Nur aktiv wenn GZ_ENV=staging. Erlaubt das manuelle Ausloesen des
Radar-Alert-Pfads fuer IMAP-basierte Validator-Tests.

Exit fuer alle anderen Umgebungen: HTTP 404.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/debug", tags=["debug"])
logger = logging.getLogger(__name__)


@router.post("/trigger-radar-alert")
def trigger_radar_alert(user_id: str = "default"):
    """Staging-only: loest echten Radar-Alert-Pfad aus, sendet an gregor-test@henemm.com.

    Ablauf (analog check_radar_alerts(), ohne Throttle-Check):
    1. Staging-Guard (GZ_ENV=staging) -> sonst 404.
    2. Trips fuer user_id laden.
    3. Ersten Trip + Segment ableiten.
    4. Nowcast abrufen (echter Call, kein Mock).
    5. Mail an gregor-test@henemm.com senden (mail_type=radar-alert).
    6. Kein radar_alert_due()-Check, kein Throttle-Eintrag (Test-Seam).
    """
    import sys
    from pathlib import Path
    from datetime import date as date_type, datetime, timezone
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
    from services.trip_segments import convert_trip_to_segments
    from services.radar_service import RadarNowcastService
    from outputs.radar_alert import build_radar_alert_body, build_radar_alert_subject
    from outputs.email import EmailOutput
    from utils.timezone import tz_for_coords

    trips = list(load_all_trips(user_id=user_id))
    if not trips:
        return JSONResponse({"status": "no_trips"})

    trip = trips[0]
    today = date_type.today()
    now_utc = datetime.now(timezone.utc)
    segments = convert_trip_to_segments(trip, today)
    # Fallback: Trip-Etappen liegen evtl. in der Vergangenheit (Staging-Testdaten).
    # Debug-Seam nutzt einfach die erste Etappe des Trips, egal welches Datum.
    if not segments:
        for stage in getattr(trip, "stages", []):
            stage_date = getattr(stage, "date", None)
            if stage_date:
                segments = convert_trip_to_segments(trip, stage_date)
                if segments:
                    break
    if not segments:
        return JSONResponse({"status": "no_segment"})

    # Aktives oder erstes Segment
    active = None
    for seg in segments:
        if seg.start_time <= now_utc <= seg.end_time:
            active = seg
            break
    if active is None:
        active = segments[0]

    lat = active.start_point.lat
    lon = active.start_point.lon
    tz = tz_for_coords(lat, lon)

    radar_svc = RadarNowcastService()
    try:
        result = radar_svc.get_nowcast(lat, lon)
    except Exception as exc:
        logger.warning("Radar nowcast failed in trigger endpoint: %s", exc)
        # Sende trotzdem Test-Mail mit Platzhalter-Werten
        result = SimpleNamespace(
            is_convective=False,
            source="test",
            onset_minutes=5,
        )

    # Cooldown-Anzeige (Fallback 2 Stunden)
    cooldown_min = getattr(trip, "alert_cooldown_minutes", None) or 120
    if cooldown_min % 60 == 0:
        n = cooldown_min // 60
        cooldown_display = f"{n} Stunde" if n == 1 else f"{n} Stunden"
    else:
        cooldown_display = f"{cooldown_min} Minuten"

    # Segment-Label (einfach: Segment-ID oder Index)
    seg_id = getattr(active, "segment_id", None)
    segment_label = str(seg_id) if seg_id is not None else "Etappe 1"

    onset_text = radar_svc.format_now_text(result, tz=tz, include_source=False)
    source_label = radar_svc.source_label(getattr(result, "source", "test"))

    subject = build_radar_alert_subject(trip.name, result, segment_label)
    body = build_radar_alert_body(
        onset_text=onset_text,
        segment_label=segment_label,
        cooldown_display=cooldown_display,
        source=source_label,
    )

    # Empfaenger-Override: immer an gregor-test@henemm.com
    test_settings = settings.model_copy(update={"mail_to": "gregor-test@henemm.com"})
    try:
        EmailOutput(test_settings).send(
            subject=subject,
            body=body,
            plain_text_body=body,
            mail_type="radar-alert",
        )
    except Exception as exc:
        logger.error("Trigger-Endpoint Mail-Versand fehlgeschlagen: %s", exc)
        raise HTTPException(status_code=500, detail=f"Mail-Versand fehlgeschlagen: {exc}")

    logger.info("Trigger-Endpoint: Radar-Alert-Mail gesendet fuer trip=%s, segment=%s", trip.id, segment_label)
    return JSONResponse({"status": "sent", "trip_id": str(trip.id), "segment": segment_label})
