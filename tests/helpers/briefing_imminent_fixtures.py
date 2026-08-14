"""Gemeinsame Bausteine der Vorlauf-Sperre-Tests (Issue #1594).

SPEC: docs/specs/modules/fix_1594_alarm_vorlauf_sperre.md

Mock-frei: echte Trips/Presets/Orte auf Platte, echte Dienste, echte
Zustandsdateien (``throttle_state.json``, ``alert_daily_count.json``,
``alert_log.json``, ``alert_state``, ``briefing_anchor.json``). Ersetzt werden
ausschliesslich die NETZ-Naehte (``_fetch_fresh_weather``,
``_detect_triggered_locations``, ``_detect``) — und zwar durch echte
Unterklassen mit echter Implementierung, die ihre Aufrufe zaehlen. Kein
``Mock()``/``patch()``/``MagicMock``.

**Warum die Zaehl-Naht der richtige Wirkort ist:** die neue Sperre sitzt an
allen drei Einhaengepunkten VOR dem Wetter-/Warnungs-Abruf. „0 Abrufe" heisst
damit „gesperrt", „>=1 Abruf" heisst „durchgelassen" — gemessen an der Stelle,
an der die Sperre wirken SOLL, nicht an der, an der ihr Code steht.

**Keine eingefrorene Systemuhr.** Alle drei Dienstpfade holen ihren Zeitpunkt
selbst ueber ``datetime.now(timezone.utc)``. Statt die Uhr anzuhalten, legen
diese Helfer die BRIEFING-ZEITEN relativ zur echten Uhr — ``stunde_versetzt(1)``
liefert die Ortsstunde in einer Stunde. Der Pruefling muss die Faelligkeit dann
gegen ``now + Vorlauf`` auswerten, um sie zu sehen. Fuer die reine
Gate-Funktion, die ihren Zeitpunkt als PARAMETER bekommt, gilt das Gegenteil:
dort wird ein Zeitpunkt weit weg von der Systemuhr uebergeben, damit ein
Rueckfall auf die Systemuhr sichtbar WUERDE (Regel aus
``reference_freeze_time_macht_parameter_vs_systemuhr_unfalsifizierbar``).

Pfadregel #1409: alles ueber ``app.loader.get_data_dir()``/``get_briefings_dir()``,
nie ueber einen festen Hauptrepo-Pfad.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from app.config import Settings
from app.loader import get_briefings_dir, get_data_dir

from tests.helpers.compare_briefings import write_compare_briefings

# Ortszonen der beiden Koordinaten-Saetze — gemessen, nicht angenommen
# (identisch zu tests/helpers/nowcast_gate_fixtures.py):
#   tz_for_coords(TRIP_LAT, TRIP_LON) -> Atlantic/Reykjavik (ganzjaehrig UTC+0)
#   tz_for_coords(LOC_LAT, LOC_LON)   -> Europe/Vienna
# Der Trip liegt bewusst auf UTC+0: Ortstag und Weltzeittag fallen nie
# auseinander, damit die Etappen-/Slot-Rechnung der Tests nicht um Mitternacht
# kippt.
TRIP_ZONE = ZoneInfo("Atlantic/Reykjavik")
LOCATION_ZONE = ZoneInfo("Europe/Vienna")

TRIP_LAT, TRIP_LON = 64.13, -21.90
LOC_LAT, LOC_LON = 47.0, 11.0

# Ruhezeit-Fenster, das „jetzt" sicher NICHT enthaelt (2–3 h voraus). Gesetzt
# statt weggelassen, damit der Wert real ausgewertet wird, statt in den
# `not quiet_from`-Kurzschluss zu laufen.
def ruhezeit_woanders(*, zone: ZoneInfo = LOCATION_ZONE) -> tuple[str, str]:
    jetzt = datetime.now(timezone.utc).astimezone(zone)
    return (
        (jetzt + timedelta(hours=2)).strftime("%H:%M"),
        (jetzt + timedelta(hours=3)).strftime("%H:%M"),
    )


# ───────────────────────────── Nutzer & Aufraeumen ──────────────────────────


def fresh_uid(prefix: str) -> str:
    return f"tdd-1594-{prefix}-{uuid.uuid4().hex[:6]}"


def clean_uid(user_id: str) -> None:
    d = get_data_dir(user_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def write_user_tier(user_id: str, tier: str = "premium") -> None:
    d = get_data_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": user_id, "tier": tier}))


def settings_email_only() -> Settings:
    """``can_send_email() == True``; Telegram und SMS ausdruecklich AUS.

    ``Settings`` wird IMMER vollstaendig konstruiert: ein weggelassenes Feld
    faellt bei pydantic still auf die Prod-``.env`` zurueck — genau so gingen am
    2026-08-03 echte Telegram-Nachrichten an den Produktiv-Chat des PO (#1477).
    """
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid",
        telegram_bot_token="", telegram_chat_id="",
        seven_api_key="", sms_to="",
    )


# ─────────────────────── Ortsstunden relativ zur echten Uhr ─────────────────


def stunde_versetzt(stunden: int, *, zone: ZoneInfo) -> int:
    """Die Ortsstunde in ``zone``, die in ``stunden`` Stunden gilt."""
    ziel = datetime.now(timezone.utc) + timedelta(hours=stunden)
    return ziel.astimezone(zone).hour


def uhrzeit(stunde: int) -> str:
    """``"HH:00:00"`` — das Format, in dem Trip- und Preset-Slots liegen.

    Go kappt Versandzeiten ohnehin auf die volle Stunde
    (``internal/store/slot_hour_normalization.go``), Minuten waeren hier also
    eine Genauigkeit, die es im Produktivsystem nicht gibt.
    """
    return f"{stunde % 24:02d}:00:00"


def ortstag(zone: ZoneInfo, tage: int = 0) -> date_type:
    return (datetime.now(timezone.utc).astimezone(zone) + timedelta(days=tage)).date()


# ─────────────────────────────── Trips schreiben ────────────────────────────


def _waypoints(lat: float, lon: float, prefix: str) -> list[dict]:
    return [
        {
            "id": f"{prefix}0", "name": "Start", "lat": lat, "lon": lon,
            "elevation_m": 500.0, "arrival_calculated": "00:00",
        },
        {
            "id": f"{prefix}1", "name": "Ende", "lat": lat + 0.1, "lon": lon + 0.1,
            "elevation_m": 600.0, "arrival_calculated": "23:59",
        },
    ]


def write_trip(
    user_id: str,
    trip_id: str,
    *,
    morgen_stunde: int,
    abend_stunde: int,
    enabled: bool = True,
    paused_at: Optional[str] = None,
    paused_until: Optional[datetime] = None,
    skip_next: bool = False,
    etappen_tage: tuple[int, ...] = (0, 1, 2),
    quiet: Optional[tuple[str, str]] = None,
    cooldown_minutes: int = 0,
) -> Path:
    """Schreibt einen Trip als ``briefings/<id>.json`` — das EINZIGE Format,
    aus dem ``load_all_trips()`` seit dem #1250-Cutover liest.

    Bewusst roh geschrieben statt ueber ``app.loader.save_trip()``: jenes
    rechnet ``arrival_calculated`` per Naismith neu (Compute-on-Save, #802) und
    zerstoert damit die ganztaegig aktive Etappe (00:00–23:59), auf die der
    Radar-Pfad angewiesen ist.

    ``etappen_tage`` sind Tagesversaetze zum ORTStag des Trips. Der Default
    ``(0, 1, 2)`` deckt heute, morgen und uebermorgen ab: der Morgen-Slot
    zielt auf den Ortstag, der Abend-Slot auf den Folgetag — und ein Lauf
    kurz vor Mitternacht wertet die Faelligkeit gegen ``now + Vorlauf`` aus,
    also bereits im naechsten Ortstag. Ohne den dritten Tag scheiterte ein
    Abend-Slot-Test in der Randstunde still an der fehlenden Etappe, statt an
    der Sperre.
    """
    stages = [
        {
            "id": f"S{versatz}", "name": f"Tag {versatz}",
            "date": ortstag(TRIP_ZONE, versatz).isoformat(),
            "waypoints": _waypoints(TRIP_LAT, TRIP_LON, f"WP{versatz}"),
        }
        for versatz in etappen_tage
    ]
    data: dict = {
        "id": trip_id,
        "name": f"Trip {trip_id}",
        "kind": "route",
        "alert_cooldown_minutes": cooldown_minutes,
        "alert_quiet_from": (quiet or (None, None))[0],
        "alert_quiet_to": (quiet or (None, None))[1],
        "stages": stages,
        "report_config": {
            "trip_id": trip_id,
            "enabled": enabled,
            "morning_time": uhrzeit(morgen_stunde),
            "evening_time": uhrzeit(abend_stunde),
            "send_email": True,
            "send_telegram": False,
            "alert_on_changes": True,
            "paused_until": paused_until.isoformat() if paused_until else None,
            "skip_next": skip_next,
        },
    }
    if paused_at is not None:
        data["paused_at"] = paused_at

    briefings = get_briefings_dir(user_id)
    briefings.mkdir(parents=True, exist_ok=True)
    path = briefings / f"{trip_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def read_trip_raw(user_id: str, trip_id: str) -> dict:
    """Der PERSISTIERTE Stand — nicht das Objekt im Speicher.

    ``_get_active_trips()`` verbraucht ``skip_next`` per Read-Modify-Write MIT
    ``save_trip()``; ein Test, der nur das uebergebene Objekt prueft, sieht
    diesen Schreibvorgang nicht.
    """
    return json.loads((get_briefings_dir(user_id) / f"{trip_id}.json").read_text())


def load_trip_obj(user_id: str, trip_id: str):
    from app.loader import load_all_trips

    for trip in load_all_trips(user_id=user_id):
        if trip.id == trip_id:
            return trip
    raise AssertionError(f"Trip {trip_id!r} nicht ladbar fuer {user_id!r}")


# ───────────────────────────── Presets schreiben ────────────────────────────


def write_location(user_id: str, loc_id: str = "loc-1594") -> None:
    from app.loader import save_location
    from app.user import SavedLocation

    save_location(
        SavedLocation(
            id=loc_id, name="Testort", lat=LOC_LAT, lon=LOC_LON, elevation_m=1000,
        ),
        user_id=user_id,
    )


def compare_preset(
    preset_id: str,
    *,
    morgen_stunde: Optional[int],
    abend_stunde: Optional[int] = None,
    location_ids: Optional[list[str]] = None,
    schedule: str = "daily",
    paused_at: Optional[str] = None,
    archived_at: Optional[str] = None,
    end_date: Optional[str] = None,
    quiet: Optional[tuple[str, str]] = None,
    cooldown_minutes: int = 0,
) -> dict:
    """Vergleichs-Preset im Bestandsschema.

    ``morgen_stunde``/``abend_stunde`` auf ``None`` schaltet den jeweiligen
    Slot AB (``morning_enabled``/``evening_enabled`` = False) — der Fall
    „Preset ohne geplantes Briefing", ohne dass das Preset stillgelegt waere.
    """
    preset: dict = {
        "id": preset_id,
        "name": f"Vergleich {preset_id}",
        "user_id": "default",
        "location_ids": location_ids or ["loc-1594"],
        "schedule": schedule,
        "weekday": None,
        "profil": "ALLGEMEIN",
        "hour_from": 9,
        "hour_to": 16,
        "empfaenger": ["dummy@example.invalid"],
        "created_at": "2026-08-01T00:00:00Z",
        "morning_enabled": morgen_stunde is not None,
        "morning_time": uhrzeit(morgen_stunde if morgen_stunde is not None else 6),
        "evening_enabled": abend_stunde is not None,
        "evening_time": uhrzeit(abend_stunde if abend_stunde is not None else 18),
        "alert_cooldown_minutes": cooldown_minutes,
    }
    if paused_at is not None:
        preset["paused_at"] = paused_at
    if archived_at is not None:
        preset["archived_at"] = archived_at
    if end_date is not None:
        preset["end_date"] = end_date
    if quiet is not None:
        preset["alert_quiet_from"], preset["alert_quiet_to"] = quiet
    return preset


def write_presets(user_id: str, presets: list[dict]) -> Path:
    return write_compare_briefings(get_data_dir(user_id), presets)


# ══════════════════ Dienstpfade mit ersetzter Netz-Naht ═════════════════════


def trip_change_alert_run(user_id: str, trip_id: str) -> int:
    """Ein echter ``check_and_send_alerts()``-Lauf des Trip-Aenderungsalarms.

    Returns: Anzahl der Wetterabrufe (0 = vor dem Abruf gesperrt).
    """
    from services.trip_alert import TripAlertService

    class _Zaehlend(TripAlertService):
        fetch_aufrufe = 0

        def _fetch_fresh_weather(self, cached_weather):
            type(self).fetch_aufrufe += 1
            return []

    _Zaehlend.fetch_aufrufe = 0
    dienst = _Zaehlend(
        settings=settings_email_only(), throttle_hours=2, user_id=user_id,
    )
    dienst.check_and_send_alerts(load_trip_obj(user_id, trip_id), cached_weather=[])
    return _Zaehlend.fetch_aufrufe


def trip_official_alert_run(user_id: str, trip_id: str) -> tuple[bool, list]:
    """Ein echter ``_send_official_alert_only()``-Lauf (Trip, amtliche Warnung).

    Diese Methode IST die Aufrufstelle ``trip_alert.py:1447``; der oeffentliche
    Einstieg darueber holt die Warnungen ueber das Netz — sie werden hier als
    echte ``OfficialAlert``-Objekte hereingereicht, genau wie der Produktivpfad
    es tut.

    Returns: ``(versendet, mail_sink-Aufrufe)``.
    """
    from services.official_alerts.models import OfficialAlert
    from services.trip_alert import TripAlertService

    gesendet: list = []
    dienst = TripAlertService(
        settings=settings_email_only(), throttle_hours=2, user_id=user_id,
        mail_sink=lambda *a, **kw: gesendet.append((a, kw)),
    )
    warnung = OfficialAlert(
        source="test-1594", hazard="wind", level=3,
        label="Sturmwarnung", region_label="Testregion",
    )
    # Segment-Kennungen sind numerische Strings (`format_segment_reference`).
    versendet = dienst._send_official_alert_only(
        load_trip_obj(user_id, trip_id), [(warnung, ["1"])],
    )
    return bool(versendet), gesendet


def compare_change_alert_run(user_id: str) -> int:
    """Echter ``CompareAlertService.check_all_compare_presets()``-Lauf.

    Gezaehlt wird ``_detect_triggered_locations`` — die Netz-Naht direkt hinter
    der Ruhezeit-Pruefung (``compare_alert.py:183``), also genau dort, wo die
    neue Sperre einsortiert wird.
    """
    from services.compare_alert import CompareAlertService

    class _Zaehlend(CompareAlertService):
        detect_aufrufe = 0

        def _detect_triggered_locations(
            self, preset_id, location_ids, all_locations, config, day_window
        ):
            type(self).detect_aufrufe += 1
            return []

    _Zaehlend.detect_aufrufe = 0
    _Zaehlend(settings=settings_email_only(), user_id=user_id).check_all_compare_presets()
    return _Zaehlend.detect_aufrufe


def compare_official_alert_run(user_id: str) -> int:
    """Echter ``CompareOfficialAlertService.check_all_compare_presets()``-Lauf.

    Gezaehlt wird ``_detect`` — die Netz-Naht direkt hinter der
    Ruhezeit-Pruefung (``compare_official_alert.py:126``).
    """
    from services.compare_official_alert import CompareOfficialAlertService

    class _Zaehlend(CompareOfficialAlertService):
        detect_aufrufe = 0

        def _detect(self, preset_id, locs, sources=None):
            type(self).detect_aufrufe += 1
            return ([], {})

    _Zaehlend.detect_aufrufe = 0
    _Zaehlend(settings=settings_email_only(), user_id=user_id).check_all_compare_presets()
    return _Zaehlend.detect_aufrufe


# ─────────────── Amtliche Warnungen: echte Quelle statt Netz ────────────────


class FakeOfficialAlertSource:
    """Echte ``OfficialAlertSource`` (strukturelles Subtyping, kein Mock):
    zustaendig fuer EINEN Punkt (0.05-Toleranz), liefert steuerbare Warnungen
    und zaehlt ihre Abrufe. Muster aus ``tests/tdd/test_compare_official_alert.py``.
    """

    def __init__(self, lat: float = LOC_LAT, lon: float = LOC_LON, alerts=None):
        self._lat, self._lon = lat, lon
        self._alerts = alerts if alerts is not None else [official_alert()]
        self.fetch_calls = 0

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float, **kwargs):
        self.fetch_calls += 1
        return list(self._alerts)


def official_alert(level: int = 3, hazard: str = "wind", label: str = "Sturmwarnung"):
    """Eine amtliche Warnung, deren Gueltigkeit die echte Uhr umschliesst — der
    Standard-Zeitfenster-Filter ``[now, +inf)`` wuerde sie sonst wegwerfen."""
    from services.official_alerts.models import OfficialAlert

    jetzt = datetime.now(timezone.utc)
    return OfficialAlert(
        source="test-1594", hazard=hazard, level=level, label=label,
        valid_from=jetzt - timedelta(hours=1),
        valid_to=jetzt + timedelta(hours=12),
        region_label="Testregion",
    )


class nur_diese_warnquelle:
    """Ersetzt die global registrierten Warnquellen fuer die Dauer des Blocks.

    Kein Netz: die echten Quellen (GeoSphere, MeteoAlarm, ...) wuerden sonst
    HTTP sprechen. Der Vorzustand wird vollstaendig wiederhergestellt.
    """

    def __init__(self, quelle):
        self._quelle = quelle
        self._backup: list = []

    def __enter__(self):
        import services.official_alerts.base as b

        self._modul = b
        self._backup = list(b._REGISTERED_SOURCES)
        b._REGISTERED_SOURCES.clear()
        b._REGISTERED_SOURCES.append(self._quelle)
        return self._quelle

    def __exit__(self, *exc):
        self._modul._REGISTERED_SOURCES.clear()
        self._modul._REGISTERED_SOURCES.extend(self._backup)
        return False


def compare_official_versand_lauf(user_id: str) -> tuple[int, list]:
    """Echter Lauf des amtlichen Vergleichspfads MIT echter Warnquelle — hier
    entsteht heute ein tatsaechlicher Versand samt Melde-Gedaechtnis,
    Sperrzeit, Tageszaehler und Protokoll-Eintrag.

    Genau diese Buchungen darf die neue Sperre NICHT ausloesen (AC-10/AC-13);
    ein Lauf mit abgeklemmter Erkennung koennte das gar nicht zeigen.

    Returns: ``(Rueckgabewert des Dienstes, mail_sink-Aufrufe)``.
    """
    from services.compare_official_alert import CompareOfficialAlertService

    mails: list = []
    with nur_diese_warnquelle(FakeOfficialAlertSource()):
        sent = CompareOfficialAlertService(
            settings=settings_email_only(), user_id=user_id,
            mail_sink=lambda subject, body: mails.append((subject, body)),
        ).check_all_compare_presets()
    return sent, mails


# ══════════════════ Briefing-Renderer (die Ersetzungs-Probe) ════════════════


def render_trip_briefing_html(official_alerts: list) -> str:
    """Rendert ein echtes Trip-Briefing (HTML-Mail) mit den uebergebenen
    amtlichen Warnungen am Segment — der Pfad, ueber den `seg.official_alerts`
    im Warn-Block landet (`src/output/renderers/email/html.py:1565-1595`).

    Das ist die Probe fuer die tragende Rechtfertigung der ganzen Scheibe: die
    unterdrueckte Meldung wird ERSETZT, nicht verschluckt.
    """
    from app.metric_catalog import build_default_display_config
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    from output.renderers.email.html import render_html

    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=14.5, ascent_m=820.0, descent_m=440.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3,
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
    )
    punkte = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=15.0 + h * 0.3, wind10m_kmh=15.0, precip_1h_mm=0.2,
            cloud_total_pct=50, thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 14)
    ]
    aggregat = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, temp_avg_c=18.0,
        wind_max_kmh=22.0, gust_max_kmh=35.0, precip_sum_mm=0.8,
        cloud_avg_pct=50, humidity_avg_pct=55, thunder_level_max=ThunderLevel.NONE,
    )
    seg_daten = SegmentWeatherData(
        segment=segment, timeseries=NormalizedTimeseries(meta=meta, data=punkte),
        aggregated=aggregat, fetched_at=datetime.now(timezone.utc), provider="demo",
        official_alerts=list(official_alerts),
    )
    return render_html(
        segments=[seg_daten], seg_tables=[[]], trip_name="Vorlauf-Testtour",
        report_type="morning", dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None, stage_name="Etappe 1",
        stage_stats={"distance_km": 14.5, "ascent_m": 820}, multi_day_trend=None,
        compact_summary="Guter Tag.", tz=LOCATION_ZONE, friendly_keys=set(),
    )


# ═════════════════════ Zustands- und Protokoll-Schnappschuss ════════════════


def zustand_schnappschuss(user_id: str, entity_id: str) -> dict:
    """Alles, was ein Alarm-Lauf schreiben KOENNTE — als eine vergleichbare
    Struktur (AC-10 + AC-13).

    Bewusst breit gelesen: Melde-Gedaechtnis, Sperrzeit-Ablage, Tageszaehler
    UND das Alarm-Protokoll (beide Listen). Ein Schnappschuss, der nur eine
    davon abdeckte, liesse genau die Buchung durch, die #1233 verbietet.
    """
    from services.alert_state import AlertStateService

    d = get_data_dir(user_id)

    def _json(name: str, default):
        p = d / name
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text())
        except (OSError, ValueError):
            return default

    protokoll = _json("alert_log.json", {})
    return {
        "melde_gedaechtnis": AlertStateService(user_id=user_id).load(entity_id),
        "sperrzeit": _json("throttle_state.json", {}),
        "tageszaehler": _json("alert_daily_count.json", {}),
        "protokoll_entries": (protokoll or {}).get("entries", []),
        "protokoll_not_delivered": (protokoll or {}).get("not_delivered", []),
    }


def protokoll_eintraege(user_id: str) -> list:
    """Beide Protokoll-Listen zusammen — fuer AC-13 (kein NEUER Eintrag)."""
    schnappschuss = zustand_schnappschuss(user_id, "-")
    return (
        list(schnappschuss["protokoll_entries"])
        + list(schnappschuss["protokoll_not_delivered"])
    )


def briefing_anker_setzen(
    user_id: str, entity_id: str, entity_type: str, *, vor_minuten: float,
) -> datetime:
    """Schreibt den Briefing-Anker ueber den ECHTEN Schreiber
    (``alert_briefing_anchor.record_briefing_sent``) — nicht per Handschrift in
    die Datei. Damit misst der Test das Format, das der Pruefling selbst
    schreibt und liest.
    """
    from services.alert_briefing_anchor import record_briefing_sent

    moment = datetime.now(timezone.utc) - timedelta(minutes=vor_minuten)
    record_briefing_sent(
        user_id=user_id, entity_id=entity_id, entity_type=entity_type, at=moment,
    )
    return moment
