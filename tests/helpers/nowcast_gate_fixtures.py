"""Gemeinsame Bausteine der Nowcast-Freigabe-Tests (Issue #1467 Scheibe S3).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md

Mock-frei: echte Presets/Orte/Trips auf Platte, echte Services, echte
Zustandsdateien (``throttle_state.json``, ``alert_daily_count.json``,
``alert_log.json``). Der Versand laeuft ausschliesslich ueber die vorhandenen
DI-Naehte (``radar_service``/``frame_source``, ``mail_sink``) — kein Netz,
kein ``Mock()``/``patch()``.

``Settings`` wird IMMER vollstaendig konstruiert (auch die Felder, die auf
"aus" stehen sollen): ein weggelassenes Feld faellt bei pydantic still auf die
Prod-``.env`` des Arbeitsverzeichnisses zurueck — genau so gingen am
2026-08-03 echte Telegram-Nachrichten an den Produktiv-Chat des PO (#1477).

Pfadregel #1409: alles wird relativ zu DIESER Datei bzw. ueber
``app.loader.get_data_dir()`` aufgeloest, nie ueber einen festen
Hauptrepo-Pfad. Einzige bewusste Ausnahme ist ``PRESET_ROOT``: der
Vergleichs-Loader liest Presets cwd-relativ
(``load_compare_presets(data_root="data")``) — die in CLAUDE.md ausgenommene
"geteilte Ablage" (Vorbild ``tests/helpers/alert_log_fixtures.py``).
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Settings
from app.loader import get_briefings_dir, get_data_dir
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

# s. Modul-Docstring: cwd-relative Ablage des Vergleichs-Preset-Loaders.
PRESET_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"

VIENNA = ZoneInfo("Europe/Vienna")

LAT, LON = 47.0, 11.0

# Trip-Wegpunkte liegen bewusst in einer Zeitzone MIT UTC-Versatz 0
# (Atlantic/Reykjavik, ganzjaehrig UTC+0). ``convert_trip_to_segments()``
# deutet ``arrival_calculated`` in der ORTSZEIT des Wegpunkts und vergleicht
# das Ergebnis gegen ``datetime.now(timezone.utc)``; mit einem versetzten Ort
# waeren die Tests um den Tageswechsel herum stundenweise instabil.
TRIP_LAT, TRIP_LON = 64.13, -21.90

# Scope-Namen der Sperrzeit-Ablage (Spec (b)).
SCOPE_COMPARE_RADAR = "compare_radar"
SCOPE_TRIP_RADAR = "radar"

LEGACY_COMPARE_RADAR_FILE = "compare_radar_alert_throttle.json"


# ───────────────────────────── Nutzer & Aufraeumen ──────────────────────────


def fresh_uid(prefix: str) -> str:
    return f"tdd-1467s3-{prefix}-{uuid.uuid4().hex[:6]}"


def clean_uid(user_id: str) -> None:
    """Beide Ablagen: die isolierte ``get_data_dir()``-Basis UND das
    cwd-relative Preset-Verzeichnis."""
    for d in (PRESET_ROOT / user_id, get_data_dir(user_id)):
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)


def write_user_tier(user_id: str, tier: str) -> None:
    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": user_id, "tier": tier}))


# ───────────────────────────────── Settings ─────────────────────────────────


def settings_email_only() -> Settings:
    """``can_send_email() == True``; Telegram und SMS ausdruecklich AUS."""
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="", telegram_chat_id="",
        seven_api_key="", sms_to="",
    )


def settings_no_channel_reachable() -> Settings:
    """Kein einziger Kanal erreichbar: ``can_send_email/telegram/sms`` alle
    False. Der Alarm-Pfad laeuft komplett durch, die Zustellung scheitert."""
    return Settings(
        smtp_host="", smtp_user="", smtp_pass="", mail_to="",
        telegram_bot_token="", telegram_chat_id="",
        seven_api_key="", sms_to="",
    )


# ───────────────────────────── Orte & Presets ───────────────────────────────


def location(loc_id: str, name: str, lat: float = LAT, lon: float = LON) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def radar_preset(
    preset_id: str,
    location_ids: list[str],
    *,
    user_id: str = "default",
    cooldown_minutes: int | None = 120,
    quiet_from: str | None = None,
    quiet_to: str | None = None,
) -> dict:
    """Vergleichs-Preset mit scharfem Nowcast-Alarm und aktivem Zeitplan
    (``schedule="daily"`` — sonst greift der Stilllegungs-Riegel aus S2 AG6
    und der Test misst diesen statt der Freigabe-Stufen)."""
    preset: dict = {
        "id": preset_id,
        "name": preset_id,
        "user_id": user_id,
        "location_ids": location_ids,
        "schedule": "daily",
        "weekday": 4,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["dummy@example.invalid"],
        "created_at": "2026-08-08T00:00:00Z",
        "radar_alert_enabled": True,
    }
    if cooldown_minutes is not None:
        preset["alert_cooldown_minutes"] = cooldown_minutes
    if quiet_from is not None:
        preset["alert_quiet_from"] = quiet_from
    if quiet_to is not None:
        preset["alert_quiet_to"] = quiet_to
    return preset


def write_presets(user_id: str, presets: list[dict]) -> Path:
    return write_compare_briefings(PRESET_ROOT / user_id, presets)


# ─────────────────────────────── Radar-Naht ─────────────────────────────────


def wet_frames(onset_minutes: int = 8, *, is_convective: bool = False, rate: float = 0.6) -> list:
    """Ein echter, nasser ``RadarFrame`` ``onset_minutes`` in der Zukunft."""
    from providers.brightsky import RadarFrame

    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=rate, is_convective=is_convective)]


class CountingFrameSource:
    """Echter, aufrufbarer ``frame_source``-Doppelgaenger (kein Mock): liefert
    fuer JEDE Koordinate denselben ausloesenden Frame-Satz und zaehlt die
    tatsaechlichen Abrufe. Die Zaehl-Naht sitzt an der Stelle, an der der
    Nowcast-Abruf real Kosten verursacht."""

    def __init__(self, onset_minutes: int = 8) -> None:
        self._onset = onset_minutes
        self.call_count = 0
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        self.call_count += 1
        self.calls.append((lat, lon))
        return wet_frames(self._onset)


def radar_service(frame_source) -> object:
    from services.radar_service import RadarNowcastService

    return RadarNowcastService(frame_source=frame_source)


def reset_radar_cache() -> None:
    """Der Frame-Cache ist ein Prozess-Singleton (TTL 300 s). Wer INNERHALB
    eines Tests zweimal dieselbe Koordinate abruft und dabei Abrufe zaehlt,
    muss ihn dazwischen leeren — sonst misst der zweite Lauf einen
    Cache-Treffer statt des Freigabe-Verhaltens."""
    from services.radar_cache import reset_shared_radar_cache_for_tests

    reset_shared_radar_cache_for_tests()


# ─────────────────────────── Ruhezeit-Fenster ───────────────────────────────


def quiet_window_now(buffer_minutes: int = 5) -> tuple[str, str]:
    """``(from, to)`` in Europe/Vienna-Lokalzeit, das den JETZIGEN Zeitpunkt
    umschliesst — ``is_quiet_hours()`` vergleicht seit #1312 gegen Wien."""
    now = datetime.now(timezone.utc).astimezone(VIENNA)
    return (
        (now - timedelta(minutes=buffer_minutes)).strftime("%H:%M"),
        (now + timedelta(minutes=buffer_minutes)).strftime("%H:%M"),
    )


def quiet_window_elsewhere() -> tuple[str, str]:
    """Ein GESETZTES Ruhezeit-Fenster, das „jetzt" NICHT enthaelt (2–3 h
    voraus). Schaerfer als „gar keine Ruhezeit", weil der Wert damit real
    ausgewertet wird statt in den ``not quiet_from``-Kurzschluss zu laufen."""
    now = datetime.now(timezone.utc).astimezone(VIENNA)
    return (
        (now + timedelta(hours=2)).strftime("%H:%M"),
        (now + timedelta(hours=3)).strftime("%H:%M"),
    )


# ───────────────────────── Zustandsdateien lesen/setzen ─────────────────────


def daily_counter_path(user_id: str) -> Path:
    return get_data_dir(user_id) / "alert_daily_count.json"


def vienna_today() -> str:
    return datetime.now(timezone.utc).astimezone(VIENNA).date().isoformat()


def seed_daily_counter(user_id: str, count: int) -> None:
    path = daily_counter_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": vienna_today(), "count": count}))


def read_daily_counter(user_id: str) -> int:
    path = daily_counter_path(user_id)
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    if data.get("date") != vienna_today():
        return 0
    return int(data.get("count", 0))


def throttle_state_path(user_id: str) -> Path:
    return get_data_dir(user_id) / "throttle_state.json"


def read_throttle_state(user_id: str) -> dict:
    path = throttle_state_path(user_id)
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data if isinstance(data, dict) else {}


def record_throttle(user_id: str, scope: str, key: str, when: datetime | None = None) -> None:
    """Sperrzeit-Eintrag ueber den ECHTEN ``ThrottleStore`` setzen (nicht per
    Handschrift in die Datei) — damit misst der Test das Format, das der
    Pruefling selbst schreibt."""
    from services.throttle_store import ThrottleStore

    ThrottleStore(user_id).record(scope, key, when or datetime.now(timezone.utc))


def write_legacy_compare_throttle(user_id: str, preset_id: str, when: datetime) -> Path:
    """Die ABGELOESTE Alt-Datei mit frischem Eintrag vorbelegen (AC-3)."""
    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / LEGACY_COMPARE_RADAR_FILE
    path.write_text(json.dumps({preset_id: when.isoformat()}, indent=2))
    return path


def read_log(user_id: str) -> dict:
    path = get_data_dir(user_id) / "alert_log.json"
    if not path.exists():
        return {"entries": [], "not_delivered": []}
    data = json.loads(path.read_text())
    data.setdefault("entries", [])
    data.setdefault("not_delivered", [])
    return data


def suppression_reasons(entry: dict) -> set[str]:
    """Alle Unterdrueckungs-Gruende, die dieser Protokoll-Eintrag traegt.

    Gelesen wird BEWUSST breit (Kanal-Aufschluesselung UND moegliche
    Kopffelder): die Spec legt die beobachtbare Wirkung fest ("ein Eintrag mit
    dem Unterdrueckungs-Grund"), die Traegerform ist Implementierungsdetail.
    Der Eintrags-``reason`` (= Ausloeser, z.B. ``nowcast``) zaehlt nur mit,
    wenn er einer der drei Gate-Gruende ist.
    """
    from services import alert_log

    gate = {
        alert_log.REASON_QUIET_HOURS,
        alert_log.REASON_COOLDOWN,
        alert_log.REASON_DAILY_LIMIT,
    }
    found: set[str] = set()
    not_sent = entry.get("channels_not_sent")
    if isinstance(not_sent, dict):
        found.update(not_sent.values())
    else:
        for item in not_sent or []:
            if isinstance(item, dict):
                found.add(item.get("reason"))
    for key in ("reason", "suppressed_reason", "gate_reason", "suppression_reason"):
        found.add(entry.get(key))
    return {r for r in found if r in gate}


def entries_for(user_id: str, entity_id: str, *, bucket: str) -> list[dict]:
    return [
        e for e in read_log(user_id).get(bucket, [])
        if isinstance(e, dict) and e.get("entity_id") == entity_id
    ]


# ─────────────────────────────── Trip-Bausteine ─────────────────────────────


def make_trip(
    trip_id: str,
    *,
    cooldown_minutes: int = 120,
    quiet_from: str | None = None,
    quiet_to: str | None = None,
) -> Trip:
    """Trip mit einer heute aktiven Etappe (Segment-Auswahl in
    ``check_radar_alerts()`` braucht ``arrival_calculated``).

    Die Etappe spannt bewusst den GANZEN Tag (00:00–23:59 Ortszeit = UTC, s.
    ``TRIP_LAT``): so ist zu jeder Tageszeit ein Segment aktiv und der Test
    misst die Freigabe-Stufen, nicht die Segment-Auswahl.
    """
    wp0 = Waypoint(
        id="WP0", name="Start", lat=TRIP_LAT, lon=TRIP_LON, elevation_m=500.0,
        arrival_calculated="00:00",
    )
    wp1 = Waypoint(
        id="WP1", name="Ende", lat=TRIP_LAT + 0.1, lon=TRIP_LON + 0.1, elevation_m=600.0,
        arrival_calculated="23:59",
    )
    stage = Stage(id="S1", name="Tag 1", date=date_type.today(), waypoints=[wp0, wp1])
    trip = Trip(id=trip_id, name="S3 Nowcast-Trip", stages=[stage])
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False,
    )
    trip.alert_cooldown_minutes = cooldown_minutes
    trip.alert_quiet_from = quiet_from
    trip.alert_quiet_to = quiet_to
    return trip


def save_trip(trip: Trip, user_id: str) -> None:
    trips_dir = get_briefings_dir(user_id)
    trips_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": trip.id,
        "name": trip.name,
        "alert_cooldown_minutes": trip.alert_cooldown_minutes,
        "alert_quiet_from": trip.alert_quiet_from,
        "alert_quiet_to": trip.alert_quiet_to,
        "stages": [
            {
                "id": s.id, "name": s.name, "date": s.date.isoformat(),
                "waypoints": [
                    {
                        "id": w.id, "name": w.name, "lat": w.lat, "lon": w.lon,
                        "elevation_m": w.elevation_m,
                        "arrival_calculated": w.arrival_calculated,
                    }
                    for w in s.waypoints
                ],
            }
            for s in trip.stages
        ],
        "report_config": {
            "trip_id": trip.report_config.trip_id,
            "send_email": trip.report_config.send_email,
            "send_telegram": trip.report_config.send_telegram,
        },
    }
    (trips_dir / f"{trip.id}.json").write_text(json.dumps(data))


def trip_alert_service(user_id: str, settings: Settings, frame_source, mail_sink):
    from services.trip_alert import TripAlertService

    return TripAlertService(
        settings=settings, throttle_hours=2, user_id=user_id,
        radar_service=radar_service(frame_source), mail_sink=mail_sink,
    )


def compare_radar_service(user_id: str, settings: Settings, frame_source, mail_sink):
    from services.compare_radar_alert import CompareRadarAlertService

    return CompareRadarAlertService(
        settings=settings, user_id=user_id,
        radar_service=radar_service(frame_source), mail_sink=mail_sink,
    )
