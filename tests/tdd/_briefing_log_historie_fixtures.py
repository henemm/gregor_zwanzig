"""Gemeinsamer Aufbau fuer die Versand-Historie-Tests (#2281).

Kein Test-Modul (fuehrender Unterstrich). Geteilt von
``test_briefing_log_vergleich_eintrag.py``, ``test_briefing_log_kaputte_datei.py``
und ``test_briefing_log_nutzer_isolation.py``.

Nur die Netz-Naehte sind ersetzt (Wetter: ``engine_naht`` bzw.
``GZ_TEST_FIXTURE_DIR``; Transport: geteilter Aufzeichner). Kein Fixture
schreibt ``entity_type``/``entity_id`` in den Log -- das muss das Produkt tun.
"""
from __future__ import annotations

import copy
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_data_dir, get_data_root, load_all_trips, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from tests.helpers.transport_mitschrift import (  # noqa: E402
    Kanalmitschrift,
    aufzeichner_installieren,
)
from tests.tdd._compare_kette_fixtures import (  # noqa: E402
    TARGET_DATE,
    alle_orte,
    engine_naht,
    fixture_dict,
    nutzer_anlegen,
    orte_anlegen,
    preset_ablegen,
    preset_laden,
    settings_fuer,
    sms_tageslimit_erschoepfen,
    transport_einrichten,
)
from utils.timezone import tz_for_coords  # noqa: E402

LOG = "briefing_log.json"
INNSBRUCK = (47.2692, 11.4041)


def eintraege(uid: str) -> list[dict]:
    """Eintraege des Nutzer-Logs; fehlende Datei = leere Liste (damit RED als
    Zaehl-Assertion erscheint, nicht als FileNotFoundError)."""
    pfad = get_data_dir(uid) / LOG
    if not pfad.exists():
        return []
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    assert isinstance(daten, dict), f"{pfad} ist kein JSON-Objekt: {daten!r}"
    return list(daten.get("entries", []))


@pytest.fixture
def vergleich(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def vergleich_nutzer() -> tuple[str, str]:
    """Nutzer mit Ortsvergleich: alle vier Kanaele eingeschaltet, SMS-Limit
    erschoepft (SMS + Premium-SMS werden gesperrt)."""
    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    p = copy.deepcopy(fixture_dict("basis"))
    p["id"] = f"vgl-{uuid.uuid4().hex[:8]}"
    p["send_telegram"] = p["send_sms"] = p["send_premium_sms"] = True
    p.setdefault("alert_channels", {"email": True, "telegram": False, "sms": False, "premium_sms": False})
    preset_ablegen(uid, p)
    sms_tageslimit_erschoepfen(uid)
    return uid, p["id"]


def vergleich_senden(uid: str, preset_id: str, *, on_demand: bool, tage_ab_ortstag):
    """Ueber die ECHTE Engstelle. ``tage_ab_ortstag=None`` = die Aufrufform aus
    ``send_compare_preset`` (Handversand ohne Zieltag/Versatz)."""
    from services.scheduler_dispatch_service import send_one_compare_preset

    preset = preset_laden(uid, preset_id)
    if tage_ab_ortstag is None:
        return send_one_compare_preset(
            preset, settings_fuer(uid), uid, str(get_data_root()),
            on_demand=True, weather_failure_as_outcome=True,
        )
    return send_one_compare_preset(
        preset, settings_fuer(uid), uid, str(get_data_root()),
        all_locations_cache=alle_orte(uid),
        target_date=TARGET_DATE + timedelta(days=tage_ab_ortstag),
        tage_ab_ortstag=tage_ab_ortstag, on_demand=on_demand,
    )


# ─────────────── Trip ───────────────


@pytest.fixture
def mitschrift(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def trip_nutzer() -> str:
    uid = f"historie-trip-{uuid.uuid4().hex[:8]}"
    ordner = get_data_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "user.json").write_text(json.dumps({
        "id": uid, "tier": "premium", "mail_to": f"{uid}@example.invalid",
        "email_verified_at": "2026-10-01T08:00:00Z",
    }))
    return uid


def trip_anlegen(user_id: str) -> Trip:
    """Drei Etappen (gestern/heute/morgen) am Fixture-Standort, nur E-Mail."""
    zone = tz_for_coords(*INNSBRUCK)
    heute = datetime.now(timezone.utc).astimezone(zone).date()
    trip_id = f"historie-{uuid.uuid4().hex[:8]}"
    stages = [
        Stage(
            id=f"T{i}", name=f"Etappe {i}", date=heute + timedelta(days=i - 1),
            waypoints=[
                Waypoint(id=f"G{i}a", name="Start",
                         lat=INNSBRUCK[0], lon=INNSBRUCK[1], elevation_m=600),
                Waypoint(id=f"G{i}b", name="Ziel",
                         lat=INNSBRUCK[0] + 0.02, lon=INNSBRUCK[1] + 0.02,
                         elevation_m=900),
            ],
        )
        for i in range(3)
    ]
    trip = Trip(
        id=trip_id, name=f"Historie {trip_id[-4:]}", stages=stages,
        official_alerts_enabled=False,
        report_config=TripReportConfig(
            trip_id=trip_id, send_email=True, send_sms=False,
            send_premium_sms=False, send_telegram=False,
        ),
    )
    save_trip(trip, user_id)
    return next(t for t in load_all_trips(user_id) if t.id == trip_id)
