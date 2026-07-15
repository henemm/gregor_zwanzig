"""
Idempotentes Setup fuer den rollenden Staging-Test-Trip (#937).

Stellt sicher, dass der Test-User `validator-issue110` einen Trip
`staging-validator-rolling` mit Etappen auf heute+1/heute+2 (Innsbruck) hat
und Mails an gregor-test@henemm.com gehen — Grundlage fuer echte
briefing_mail_validator.py-Laeufe gegen Staging.

Usage:
    uv run python3 scripts/setup_staging_validator_trip.py
    GZ_STAGING_DATA_DIR=/pfad/zu/data uv run python3 scripts/setup_staging_validator_trip.py
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

USER_ID = "validator-issue110"
TRIP_ID = "staging-validator-rolling"
MAIL_TO = "gregor-test@henemm.com"
INNSBRUCK_LAT = 47.2692
INNSBRUCK_LON = 11.4041
# Nordkettenbahn-Talstation — knapp 2km/~250hm entfernter zweiter Punkt in
# Innsbruck, damit Naismith einen von 0 verschiedenen Segment-Weg berechnet
# (identische Start-/Zielkoordinate liefert wp1_start==wp2_start -> Segment
# kollabiert, siehe services/trip_segments.py).
INNSBRUCK_2_LAT = 47.2802
INNSBRUCK_2_LON = 11.3907
INNSBRUCK_2_ELEV = 830


def _staging_data_dir() -> Path:
    return Path(os.environ.get("GZ_STAGING_DATA_DIR", "/home/hem/gregor_zwanzig_staging/data"))


def _ensure_mail_to(data_dir: Path) -> None:
    """Read-Modify-Write: setzt mail_to nur, wenn es fehlt/abweicht — keine anderen Felder anfassen."""
    user_path = data_dir / "users" / USER_ID / "user.json"
    user_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if user_path.exists():
        existing = json.loads(user_path.read_text(encoding="utf-8"))
    if existing.get("mail_to") == MAIL_TO:
        return
    existing["mail_to"] = MAIL_TO
    user_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


def _build_rolling_trip():
    from app.models import TripReportConfig
    from app.trip import Stage, Trip, Waypoint

    today = date.today()

    def _innsbruck_waypoints(prefix: str) -> list:
        # convert_trip_to_segments braucht >=2 Waypoints pro Stage, um ein Segment zu bilden.
        return [
            Waypoint(id=f"{prefix}-1", name="Innsbruck Start", lat=INNSBRUCK_LAT, lon=INNSBRUCK_LON, elevation_m=574),
            Waypoint(id=f"{prefix}-2", name="Innsbruck Nordkettenbahn", lat=INNSBRUCK_2_LAT, lon=INNSBRUCK_2_LON, elevation_m=INNSBRUCK_2_ELEV),
        ]

    stage_1 = Stage(
        id="rolling-stage-1",
        name="Etappe 1",
        date=today + timedelta(days=1),
        waypoints=_innsbruck_waypoints("rolling-wp-1"),
    )
    stage_2 = Stage(
        id="rolling-stage-2",
        name="Etappe 2",
        date=today + timedelta(days=2),
        waypoints=_innsbruck_waypoints("rolling-wp-2"),
    )
    return Trip(
        id=TRIP_ID,
        name="Staging Rolling Validator Trip",
        stages=[stage_1, stage_2],
        report_config=TripReportConfig(trip_id=TRIP_ID, enabled=True, send_email=True),
        # Issue #1258 Fix-Loop F001: bare Trip(...) liefert per Default
        # official_warnings={"enabled": False} (Neuanlage-Semantik, s.
        # app/trip.py). Dieses Skript baut den Trip-Objektgraph aber bei
        # JEDEM Lauf neu (kein Laden von der Platte) — ohne den expliziten
        # None-Override wuerde save_trip()'s RMW-Merge (loader.py
        # _deep_merge_preserve_unknown, "overlay wins") den persistierten
        # official_warnings-Wert bei jedem wiederkehrenden Lauf auf
        # enabled=False zuruecksetzen. None signalisiert "vom Aufrufer nicht
        # gesetzt" -> _trip_to_dict() laesst den Schluessel dann komplett
        # weg, der Merge fasst den bestehenden Wert nicht an (Muster:
        # tests/tdd/test_issue_1088_official_alert_triggers.py _minimal_trip).
        official_warnings=None,
    )


def main() -> None:
    from app.loader import save_trip

    data_dir = _staging_data_dir()
    _ensure_mail_to(data_dir)
    trip = _build_rolling_trip()
    save_trip(trip, user_id=USER_ID, data_dir=data_dir)
    # Marker fuer check-gregor20.sh (henemm-infra) — BetterStack-Quota ist voll
    # (siehe Spec "Known Limitations"), daher Integration in den bestehenden
    # gesammelten "Gregor20 Services"-Heartbeat statt eigenem Heartbeat.
    print(f"OK: {TRIP_ID} aktualisiert ({date.today().isoformat()})")


if __name__ == "__main__":
    main()
