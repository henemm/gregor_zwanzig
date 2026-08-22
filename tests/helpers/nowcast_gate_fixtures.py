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
Hauptrepo-Pfad.

Issue #1595: die frueher hier dokumentierte Ausnahme ``PRESET_ROOT`` (fester
Hauptrepo-Pfad, begruendet mit ``load_compare_presets(data_root="data")``)
ist ENTFALLEN. Der Vergleichs-Loader liest die Datenwurzel jetzt ueber
``get_data_root()``, also ueber dieselbe Basis wie ``get_data_dir()``. Ein
fester Pfad schriebe seither dorthin, wo der Pruefling NICHT liest. Deshalb
``preset_root()`` als Funktion: der Wert faellt beim Aufruf, nach der
#1133-Fixture, nicht beim Import davor.
"""
from __future__ import annotations

import json
import shutil
import uuid
from contextlib import contextmanager
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Settings
from app.loader import get_briefings_dir, get_data_dir
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from app.user import SavedLocation

from tests.helpers.briefing_zeiten import briefing_zeiten_fuer_trip
from tests.helpers.compare_briefings import write_compare_briefings

def preset_root() -> Path:
    """Nutzer-Wurzel der Vergleichs-Preset-Ablage, s. Modul-Docstring.

    Funktion statt Konstante (#1595): ``get_data_root()`` liefert erst zur
    Laufzeit die von der #1133-Fixture gesetzte Basis.
    """
    from app.loader import get_data_root

    return get_data_root() / "users"

# Issue #1726: Ruhezeit und Tageszaehler laufen nicht mehr auf der Wiener Uhr,
# sondern auf der ORTSZONE des jeweiligen Gegenstands. Die Helfer unten nehmen
# sie deshalb als Parameter. Die beiden Konstanten sind die Zonen der
# DEFAULT-Koordinaten dieser Datei — gemessen, nicht angenommen:
#   tz_for_coords(LAT, LON)           -> Europe/Vienna
#   tz_for_coords(TRIP_LAT, TRIP_LON) -> Atlantic/Reykjavik
# Wer einen Vergleich aus `location()` baut, braucht LOCATION_ZONE; wer einen
# Trip aus `make_trip()` baut, TRIP_ZONE. Ein gemeinsamer Default waere fuer
# eine der beiden Seiten still falsch (Versatz 1-2 h) und der Test dann gruen
# aus dem falschen Grund.
LOCATION_ZONE = ZoneInfo("Europe/Vienna")
TRIP_ZONE = ZoneInfo("Atlantic/Reykjavik")

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
    for d in (preset_root() / user_id, get_data_dir(user_id)):
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
    return write_compare_briefings(preset_root() / user_id, presets)


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


def quiet_window_now(
    buffer_minutes: int = 5, *, zone: ZoneInfo = LOCATION_ZONE,
) -> tuple[str, str]:
    """``(from, to)`` in der Ortszeit von ``zone``, das den JETZIGEN Zeitpunkt
    umschliesst. Seit #1726 wertet ``is_quiet_hours()`` in der Zone des
    Gegenstands aus — das Fenster muss in DERSELBEN Zone gebildet werden."""
    now = datetime.now(timezone.utc).astimezone(zone)
    return (
        (now - timedelta(minutes=buffer_minutes)).strftime("%H:%M"),
        (now + timedelta(minutes=buffer_minutes)).strftime("%H:%M"),
    )


def quiet_window_elsewhere(*, zone: ZoneInfo = LOCATION_ZONE) -> tuple[str, str]:
    """Ein GESETZTES Ruhezeit-Fenster, das „jetzt" NICHT enthaelt (2–3 h
    voraus). Schaerfer als „gar keine Ruhezeit", weil der Wert damit real
    ausgewertet wird statt in den ``not quiet_from``-Kurzschluss zu laufen."""
    now = datetime.now(timezone.utc).astimezone(zone)
    return (
        (now + timedelta(hours=2)).strftime("%H:%M"),
        (now + timedelta(hours=3)).strftime("%H:%M"),
    )


# ───────────────────────── Zustandsdateien lesen/setzen ─────────────────────


def daily_counter_path(user_id: str) -> Path:
    return get_data_dir(user_id) / "alert_daily_count.json"


def local_today(zone: ZoneInfo = LOCATION_ZONE) -> str:
    return datetime.now(timezone.utc).astimezone(zone).date().isoformat()


def seed_daily_counter(
    user_id: str, count: int, *, zone: ZoneInfo = LOCATION_ZONE,
) -> None:
    """Zaehlerstand vorbelegen — im Schema, das der Pruefling seit #1726
    SCHREIBT (``{"zones": {"<zone>": {...}}}``). Bewusst nicht im Alt-Schema:
    der Helfer soll den Normalfall herstellen, nicht die Migration testen (die
    hat ihren eigenen Nachweis in AC-8)."""
    path = daily_counter_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"zones": {str(zone): {"date": local_today(zone), "count": count}}}
    ))


def read_daily_counter(user_id: str, *, zone: ZoneInfo = LOCATION_ZONE) -> int:
    path = daily_counter_path(user_id)
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    entry = (data.get("zones") or {}).get(str(zone))
    if not isinstance(entry, dict) or entry.get("date") != local_today(zone):
        return 0
    return int(entry.get("count", 0))


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


def trip_stage(
    stage_id: str, day: date_type, lat: float, lon: float,
    *, arrival_start: str = "00:00", arrival_end: str = "23:59",
    wp_prefix: str = "WP",
) -> Stage:
    """Zwei-Wegpunkt-Etappe (Start/Ende) — der Baustein, aus dem
    :func:`make_trip` seine Etappe baut. Additiv exportiert (Issue #1697),
    damit Aufrufer, die eine ZWEITE Etappe (z.B. Folgetag) brauchen, sie
    NICHT selbst aus ``Stage``/``Waypoint`` zusammensetzen — Teilungsregel
    statt Nachbau.
    """
    wp0 = Waypoint(
        id=f"{wp_prefix}0", name="Start", lat=lat, lon=lon, elevation_m=500.0,
        arrival_calculated=arrival_start,
    )
    wp1 = Waypoint(
        id=f"{wp_prefix}1", name="Ende", lat=lat + 0.1, lon=lon + 0.1, elevation_m=600.0,
        arrival_calculated=arrival_end,
    )
    return Stage(id=stage_id, name="Tag 1", date=day, waypoints=[wp0, wp1])


def make_trip(
    trip_id: str,
    *,
    cooldown_minutes: int = 120,
    quiet_from: str | None = None,
    quiet_to: str | None = None,
    stage_date: date_type | None = None,
    lat: float = TRIP_LAT,
    lon: float = TRIP_LON,
    arrival_start: str = "00:00",
    arrival_end: str = "23:59",
    extra_stages: list[Stage] | None = None,
) -> Trip:
    """Trip mit einer heute aktiven Etappe (Segment-Auswahl in
    ``check_radar_alerts()`` braucht ``arrival_calculated``).

    Die Etappe spannt standardmaessig den GANZEN Tag (00:00–23:59 Ortszeit =
    UTC, s. ``TRIP_LAT``): so ist zu jeder Tageszeit ein Segment aktiv und
    der Test misst die Freigabe-Stufen, nicht die Segment-Auswahl.

    Issue #1697: ``stage_date``/``lat``/``lon``/``arrival_start``/
    ``arrival_end``/``extra_stages`` sind ADDITIV — alle Defaults sind
    bit-identisch zum bisherigen Verhalten (``date.today()``,
    ``TRIP_LAT``/``TRIP_LON``, 00:00–23:59, keine zweite Etappe). Bestehende
    Aufrufer (``test_nowcast_suppression_logging.py``,
    ``test_trip_radar_nowcast_gate_migration.py``) bleiben unveraendert
    gruen (belegt per Testlauf, s. Commit-Historie). Die neuen Parameter
    dienen Faellen, die eine ANDERE Etappe/einen zweiten Tag brauchen (z.B.
    #1697 AC-1/AC-3/AC-5: Ortsdatum weicht vom Serverdatum ab).
    """
    day = stage_date if stage_date is not None else date_type.today()
    stage = trip_stage(
        "S1", day, lat, lon, arrival_start=arrival_start, arrival_end=arrival_end,
    )
    stages = [stage] + list(extra_stages or [])
    trip = Trip(id=trip_id, name="S3 Nowcast-Trip", stages=stages)
    # Issue #1594: ohne gesetzte Zeiten erbt `TripReportConfig` 07:00/18:00
    # Ortszeit. Der Trip waere damit taeglich zweimal 60 Minuten lang
    # "Briefing steht bevor", und die Vorlauf-Sperre unterdrueckte den Alarm
    # aus einem ZWEITEN Grund — die Freigabe-Stufe, die diese Tests messen,
    # waere dann nicht mehr die gemessene. Reine Vorbedingung; die Zone kommt
    # aus derselben Aufloesung wie in der Sperre selbst (`anchor_tz`).
    morgen, abend = briefing_zeiten_fuer_trip(trip)
    trip.report_config = TripReportConfig(
        trip_id=trip_id, send_email=True, send_telegram=False,
        morning_time=morgen, evening_time=abend,
    )
    trip.alert_cooldown_minutes = cooldown_minutes
    trip.alert_quiet_from = quiet_from
    trip.alert_quiet_to = quiet_to
    return trip


@contextmanager
def frozen_active_window(hour_utc: int = 12):
    """Gestellte Uhr, nicht Wanduhr (#2050, Vorbild #2017 Scheibe B in
    ``test_issue_822_radar_nowcast_segment.py``): fuer Aufrufer, die einen
    ``make_trip()``-Trip ueber das PRODUKTIVE ``app.loader.save_trip()``
    speichern — nicht den verkuerzten ``save_trip()`` dieser Datei.

    ``app.loader.save_trip()`` fuehrt Compute-on-Save aus (Issue #802):
    ``arrival_start``/``arrival_end`` aus ``make_trip()`` werden dabei
    VERWORFEN und ``compute_stage_arrivals()`` rechnet WP0/WP1 stattdessen ab
    einem Default-Start 08:00 Ortszeit per Naismith neu. Bei den
    Default-Koordinaten dieser Datei (``TRIP_LAT``/``TRIP_LON``, Reykjavik,
    ganzjaehrig UTC+0) ergibt das 08:00-11:22. Das anschliessende
    Ziel-Segment (``src/services/trip_segments.py``) verlaengert die
    Abdeckung bis zum Ende des Default-Tagesfensters (Stunde 19 inklusive ->
    20:00 Ortszeit exklusiv), eine Vorschau deckt alles VOR 08:00 ab —
    luecklos aktiv ist damit NUR ``[08:00, 20:00)`` Ortszeit. Ausserhalb
    davon (20:00-24:00) liefert ``resolve_current_segment()`` ``None`` und
    ``check_radar_alerts()`` bricht vor dem Nowcast-Abruf ab — abhaengig
    davon, wann die Testsuite laeuft (gemessen 2026-08-21, #2050: CI-Lauf um
    19:38 UTC gruen, derselbe Testfall um 20:40 UTC rot).

    Dieser Helfer stellt die Uhr auf ``hour_utc:00`` UTC HEUTE — der Default
    (12 Uhr) liegt mittig im garantiert aktiven Fenster, unabhaengig von der
    tatsaechlichen Wanduhr beim Testlauf. Wie in der Vorbild-Datei wird NICHT
    aus der Wanduhr gerechnet (das waere genau das Anti-Muster, das
    ``test_fixture_wallclock_ratchet.py`` bewacht) — der Ankerpunkt ist ein
    fester, weit von beiden Fensterkanten entfernter Wert.
    """
    from freezegun import freeze_time

    anker = datetime.combine(
        date_type.today(), datetime.min.time(), tzinfo=TRIP_ZONE,
    ) + timedelta(hours=hour_utc)
    with freeze_time(anker):
        yield anker


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
            # Issue #1594: die Zeiten MUESSEN mitgeschrieben werden. Fehlen
            # sie in der Datei, setzt der Loader beim Zurueckladen wieder die
            # Modell-Vorgaben 07:00/18:00 ein — der am Objekt gesetzte Wert
            # aus `make_trip()` waere dann wirkungslos, und zwar still.
            "morning_time": trip.report_config.morning_time.isoformat(),
            "evening_time": trip.report_config.evening_time.isoformat(),
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
