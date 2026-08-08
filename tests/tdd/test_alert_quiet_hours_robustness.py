"""TDD RED — Issue #1479: ein unbrauchbarer Ruhezeit-Wert darf keinen
Alarm-Lauf mehr mitreissen (Wurzel-Haertung in
``DeviationAlertEngine.is_quiet_hours()``).

SPEC: ``docs/specs/modules/fix_1479_ruhezeit_wurzel.md`` (AC-1..AC-11)

Ist-Stand (gemessen, HEAD dieses Worktrees):
``DeviationAlertEngine.is_quiet_hours()`` (``src/services/deviation_alert_engine.py:75-100``)
ruft ungeschuetzt ``time.fromisoformat()`` auf. Ein kaputter String
(``"25:00"``/``"abc"``) wirft ``ValueError``, ein Nicht-String (``int``,
``float``, ``list``, ``bool``, ``dict``) wirft ``TypeError``. An drei der
sechs Aufrufstellen ist das ungefangen und beendet den KOMPLETTEN Alarm-Lauf
des Nutzers:

* ``compare_official_alert.py:107`` (im ``sum()``-Generator ``:72``) — AC-1
* ``compare_radar_alert.py:104`` (Schleife ``:77-79``) — AC-2
* ``trip_alert.py:733`` (Radar-Onset-Schleife ab ``:709``) — AC-3

An zwei weiteren Stellen (``trip_alert.py:205`` in ``check_and_send_alerts``
und ``trip_alert.py:1118`` in ``_send_official_alert_only``) faengt erst das
aeussere ``try/except`` in ``check_all_trips`` (``:427-438``) — der Lauf
laeuft weiter, aber DIESER Trip verliert still seinen Alarm (AC-4/AC-5).

Rot / gruen in dieser Datei — ehrlich gekennzeichnet:

* **ROT heute:** AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-8 sowie der
  Struktur-Waechter AC-11 fuer ``compare_alert.py`` (dort steht noch der
  Behelfs-Schutz aus #1467 S2 AG2, dessen Rueckbau Teil dieser Scheibe ist).
  Fuer die drei anderen Dateien ist AC-11 heute gruen — sie sind bereits
  sauber, der Waechter haelt sie es.
* **GRUEN heute (Regressionsschutz, bewusst NICHT kuenstlich rot gehalten):**
  AC-7 (Leerfall/``None`` laeuft ueber den bestehenden Kurzschluss
  ``if not quiet_from or not quiet_to``) und AC-9 (gueltiges Fenster inkl.
  Mitternachts-Wrap, halb ausgefuelltes Fenster). Beide nageln fest, dass die
  Haertung an diesem Verhalten NICHTS aendert.
* **AC-10 hat bewusst KEINEN Test in dieser Datei.** Der Nachweis ist der
  unveraenderte Lauf des Bestandstests
  ``tests/tdd/test_compare_alert_quiet_hours_precedes_fetch.py::test_f001_broken_quiet_value_does_not_abort_other_presets_same_user``.
  Diese Datei wird nicht angefasst.

Mock-frei (Projektregel): echte Preset-Dateien ueber
``tests/helpers/compare_briefings.py``, echte ``OfficialAlertSource``- und
``frame_source``-Implementierungen als Konfigurations-Nahtstellen (kein
``Mock()``/``patch()``/``MagicMock``), echte Persistenz, Transport
ausschliesslich ueber die vorhandenen ``mail_sink``/``sms_sink``/
``telegram_sink``-Nahtstellen. Kein Netzzugriff.

Kein echter Versand (#1477): ``_settings_email_only()`` setzt Telegram- UND
SMS-Felder AUSDRUECKLICH auf leer/``None`` — ``Settings(...)`` faellt bei
fehlenden Feldern still auf die Prod-``.env`` im Worktree zurueck, und ein
``mail_sink`` allein schuetzt nur den Mail-Kanal.

Pfadregel #1409: Prueflings-Pfade werden relativ zu DIESER Testdatei
aufgeloest (``Path(__file__).resolve().parents[2]``), nie ueber einen festen
Hauptrepo-Pfad — sonst pruefte der Lauf aus dem Worktree die unveraenderte
Hauptrepo-Kopie und meldete falsches Gruen. Einzige bewusste Ausnahme ist die
geteilte Ablage ``COMPARE_DATA_ROOT``: der Compare-Preset-Loader liest
cwd-relativ ueber ``load_compare_presets(data_root="data")``, also ueber das
``cwd`` des Prueflings.
"""
from __future__ import annotations

import ast
import json
import logging
import shutil
import textwrap
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import get_briefings_dir, save_location
from app.user import SavedLocation

from tests.helpers.compare_briefings import write_compare_briefings

_REPO = Path(__file__).resolve().parents[2]
COMPARE_DATA_ROOT = _REPO / "data" / "users"
SERVICES_DIR = _REPO / "src" / "services"

# Island (UTC+0 ganzjaehrig, kein Sommerzeit-Sprung) — haelt die
# Segment-Zeitfenster der Trip-Fixtures frei von DST-Ueberraschungen.
TRIP_LAT, TRIP_LON = 64.0, -22.0

# Getrennte Koordinaten fuer die Ortsvergleich-Fixtures (Deckungs-Toleranz der
# Test-Warnquelle: 0.05).
LAT_BROKEN, LON_BROKEN = 46.62, 13.68
LAT_HEALTHY, LON_HEALTHY = 46.20, 12.10


# ─────────────────────────────── Helfer ─────────────────────────────────────

def _uid(tag: str) -> str:
    return f"tdd-1479-{tag}-{uuid.uuid4().hex[:6]}"


def _clean_compare_user(user_id: str) -> None:
    d = COMPARE_DATA_ROOT / user_id
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def _settings_email_only() -> Settings:
    """``can_send_email() == True``; Telegram UND SMS nachweislich unmoeglich.

    Die leeren Telegram-Felder und ``seven_api_key=None``/``sms_to=None`` sind
    KEIN Beiwerk: ``Settings(...)`` liest jedes nicht gesetzte Feld aus der
    ``.env`` des Arbeitsverzeichnisses — im Worktree ist das die Prod-Datei.
    Genau so gingen am 2026-08-03 echte Telegram-Nachrichten an den
    Produktiv-Chat (#1477). Der ``mail_sink`` ersetzt zusaetzlich den
    SMTP-Versand vollstaendig; die Dummy-Zugangsdaten werden nie gewaehlt.
    """
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.invalid", mail_from="dummy@example.invalid",
        telegram_bot_token="", telegram_chat_id="",
        seven_api_key=None, sms_to=None, sms_from=None,
    )


def _location(loc_id: str, name: str, lat: float, lon: float) -> SavedLocation:
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=1000)


def _compare_preset(
    preset_id: str, name: str, location_ids: list[str], **extra
) -> dict:
    """Compare-Preset-Rohdict (Muster ``test_compare_official_alert.py::_preset``).

    ``schedule="daily"`` = aktiver Ortsvergleich (seit #1233 heisst ``"manual"``
    „deaktiviert" und wuerde den Preset-Lauf vor jeder Ruhezeit-Pruefung
    abbrechen).
    """
    preset: dict = {
        "id": preset_id, "name": name, "user_id": "default",
        "location_ids": location_ids, "schedule": "daily", "weekday": 4,
        "profil": "ALLGEMEIN", "hour_from": 9, "hour_to": 16,
        "empfaenger": ["gregor-test@henemm.com"],
        "created_at": "2026-08-03T00:00:00Z",
    }
    preset.update(extra)
    return preset


def _write_compare_presets(user_id: str, presets: list[dict]) -> None:
    write_compare_briefings(COMPARE_DATA_ROOT / user_id, presets)


class _FakeOfficialAlertSource:
    """Echte Warnquelle (kein Mock): zustaendig fuer EINEN Punkt (0.05
    Toleranz), liefert einen vorab festgelegten, echten ``OfficialAlert``.
    Struktur-Subtyping wie ``test_compare_official_alert.py``."""

    def __init__(self, lat: float, lon: float, alerts: list) -> None:
        self._lat, self._lon, self._alerts = lat, lon, alerts
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "tdd-1479-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float) -> list:
        self.fetch_calls += 1
        return list(self._alerts)


def _official_alert():
    from services.official_alerts.models import OfficialAlert

    now = datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-1479", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=23),
        region_label="Testregion",
    )


class _CoordFrameSource:
    """Echte, aufrufbare ``frame_source``-Naht fuer
    ``RadarNowcastService(frame_source=...)`` — liefert je (lat, lon) einen
    vorab festgelegten, echten ``RadarFrame``-Satz (Muster
    ``test_compare_radar_alert.py::_CoordFrameSource``). Kein Mock: ein reales
    Objekt mit realen Rueckgabewerten, ohne Netz."""

    def __init__(self, by_coord: dict[tuple[float, float], list]) -> None:
        self._by_coord = by_coord
        self.calls: list[tuple[float, float]] = []

    def __call__(self, lat: float, lon: float) -> list:
        self.calls.append((lat, lon))
        return self._by_coord.get((round(lat, 4), round(lon, 4)), [])


def _wet_frames(onset_minutes: int = 8) -> list:
    from providers.brightsky import RadarFrame

    ts = datetime.now(timezone.utc) + timedelta(minutes=onset_minutes)
    return [RadarFrame(timestamp=ts, precip_mm_h=0.9, is_convective=False)]


def _dry_frames() -> list:
    return []


def _save_trip_direct(
    user_id: str, trip_id: str, name: str, quiet: dict,
    lat: float = TRIP_LAT, lon: float = TRIP_LON,
) -> None:
    """Schreibt eine Trip-Datei direkt nach ``briefings/<id>.json`` (Muster
    ``test_issue_883_acute_danger_override.py::_save_trip_direct``) — umgeht
    Naismith-Compute-on-Save und erlaubt Ruhezeit-Rohwerte, die die
    Editor-/Modell-Schicht so nie erzeugen wuerde (genau der Bug: keine
    Schranke davor).

    ``get_briefings_dir()`` folgt dem pytest-isolierten Daten-Wurzelpfad
    (#1133) — demselben Pfad, aus dem ``load_all_trips()`` liest.
    """
    now = datetime.now(timezone.utc)
    briefings = get_briefings_dir(user_id)
    briefings.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": trip_id,
        "name": name,
        "stages": [{
            "id": "S1", "name": "Tag 1", "date": now.date().isoformat(),
            "waypoints": [
                {"id": "WP0", "name": "Start", "lat": lat, "lon": lon,
                 "elevation_m": 100.0,
                 "arrival_calculated": (now - timedelta(hours=1)).strftime("%H:%M")},
                {"id": "WP1", "name": "Ziel", "lat": lat + 0.05,
                 "lon": lon + 0.05, "elevation_m": 200.0,
                 "arrival_calculated": (now + timedelta(hours=2)).strftime("%H:%M")},
            ],
        }],
        "report_config": {
            "trip_id": trip_id, "send_email": True, "send_telegram": False,
        },
    }
    data.update(quiet)
    (briefings / f"{trip_id}.json").write_text(json.dumps(data, indent=2))


# ══════════════════════════════════ AC-1 ═════════════════════════════════════

def test_ac1_broken_quiet_value_does_not_abort_official_compare_run():
    """AC-1 (ROT heute) GIVEN zwei amtliche Ortsvergleiche DESSELBEN Nutzers —
    der erste mit kaputtem ``alert_quiet_from="25:00"`` (Stunde 25 existiert
    nicht), der zweite gesund und mit einer echten, neuen amtlichen Warnung an
    seinem Ort.

    WHEN ``CompareOfficialAlertService.check_all_compare_presets()`` laeuft.

    THEN bricht der Lauf NICHT ab und der gesunde Ortsvergleich stellt seinen
    Alarm zu — nachgewiesen an der echten Zustellung am ``mail_sink``, nicht
    bloss am Ausbleiben einer Ausnahme.

    Verarbeitungs-REIHENFOLGE (kaputt VOR gesund) ist hier deterministisch:
    ``load_compare_presets()`` liest ``sorted(briefings.glob("*.json"))``
    (``loader.py:322``), die Reihenfolge ist also die des Dateinamens =
    ``<preset_id>.json``. Die Kennungen sind deshalb bewusst ``...-a-kaputt``
    und ``...-z-gesund`` gewaehlt. Ohne diese Reihenfolge wuerde der Test
    nichts beweisen: waere der gesunde zuerst dran, koennte er auch bei
    intaktem Absturz-Verhalten schon zugestellt haben.

    ROT-Grund heute: ``compare_official_alert.py:107`` ruft
    ``DeviationAlertEngine.is_quiet_hours()`` ungeschuetzt aus dem
    Generator-Ausdruck von ``sum(...)`` (``:72``) — der ``ValueError`` schlaegt
    aus ``check_all_compare_presets()`` nach oben durch, der zweite
    Ortsvergleich wird nie erreicht.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    from services.official_alerts import register_official_alert_source
    import services.official_alerts.base as oa_base

    uid = _uid("ac1")
    pid_broken = f"cp-1479-ac1-a-kaputt-{uuid.uuid4().hex[:4]}"
    pid_healthy = f"cp-1479-ac1-z-gesund-{uuid.uuid4().hex[:4]}"
    _clean_compare_user(uid)
    sources_backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        save_location(_location("loc-kaputt", "KaputtOrt", LAT_BROKEN, LON_BROKEN), user_id=uid)
        save_location(_location("loc-gesund", "GesundOrt1479", LAT_HEALTHY, LON_HEALTHY), user_id=uid)
        _write_compare_presets(uid, [
            _compare_preset(
                pid_broken, "Kaputt-Vergleich", ["loc-kaputt"],
                alert_quiet_from="25:00", alert_quiet_to="23:00",
            ),
            _compare_preset(pid_healthy, "Gesund-Vergleich", ["loc-gesund"]),
        ])
        # NUR der gesunde Ort hat eine Warnquelle -> jede Zustellung ist
        # eindeutig ihm zuzuordnen.
        register_official_alert_source(
            _FakeOfficialAlertSource(LAT_HEALTHY, LON_HEALTHY, [_official_alert()])
        )

        mail_calls: list[tuple[str, str]] = []
        sms_calls: list = []
        telegram_calls: list = []
        svc = CompareOfficialAlertService(
            settings=_settings_email_only(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
            sms_sink=lambda text: sms_calls.append(text),
            telegram_sink=lambda text: telegram_calls.append(text),
        )
        sent = svc.check_all_compare_presets()

        assert len(mail_calls) == 1, (
            f"Der gesunde Ortsvergleich {pid_healthy!r} MUSS zustellen, obwohl der "
            f"vorher verarbeitete Ortsvergleich {pid_broken!r} einen unbrauchbaren "
            f"Ruhezeit-Wert ('25:00') traegt — erwartet genau 1 Zustellung am "
            f"mail_sink, erhalten: {len(mail_calls)} (AC-1)"
        )
        subject, body = mail_calls[0]
        assert "GesundOrt1479" in (subject + body), (
            "Die zugestellte Meldung gehoert nicht zum gesunden Ortsvergleich: "
            f"Betreff={subject!r} (AC-1)"
        )
        assert sent >= 1, (
            f"check_all_compare_presets() muss mindestens den gesunden "
            f"Ortsvergleich als versendet zaehlen, erhalten: {sent} (AC-1)"
        )
        assert sms_calls == [] and telegram_calls == [], (
            "Weder SMS noch Telegram waren fuer diesen Ortsvergleich freigeschaltet."
        )
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(sources_backup)
        _clean_compare_user(uid)


# ══════════════════════════════════ AC-2 ═════════════════════════════════════

def test_ac2_broken_quiet_value_does_not_abort_nowcast_compare_run():
    """AC-2 (ROT heute) GIVEN zwei Nowcast-Ortsvergleiche DESSELBEN Nutzers —
    der erste mit einem Nicht-String als ``alert_quiet_to`` (``2200`` statt
    ``"22:00"``), der zweite gesund; BEIDE haben einen echten Regen-Beginn in
    8 Minuten (also innerhalb der 20-Minuten-Schwelle).

    WHEN ``CompareRadarAlertService.check_all_compare_presets()`` laeuft.

    THEN bricht der Lauf NICHT ab und der gesunde Ortsvergleich stellt seinen
    Alarm zu (Nachweis am ``mail_sink``).

    Warum BEIDE einen Regen-Beginn brauchen: in diesem Pfad steht die
    Ruhezeit-Pruefung NACH der Erkennung (``compare_radar_alert.py:99-110``,
    AC-5 der Ursprungs-Spec). Ohne ausloesenden Regen-Beginn wuerde der
    kaputte Ortsvergleich die Ruhezeit-Pruefung nie erreichen und der Test
    waere schon heute gruen, ohne irgendetwas zu beweisen.

    Verarbeitungs-REIHENFOLGE (kaputt VOR gesund): wie bei AC-1 ueber die
    Dateinamen (``...-a-kaputt`` vor ``...-z-gesund``), weil
    ``load_compare_presets()`` ``sorted(...)`` verwendet.

    ROT-Grund heute: ``compare_radar_alert.py:104`` ruft ``is_quiet_hours()``
    ungeschuetzt in der Preset-Schleife (``:77-79``) — der ``TypeError``
    beendet den gesamten Nowcast-Lauf des Nutzers.
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = _uid("ac2")
    pid_broken = f"cp-1479-ac2-a-kaputt-{uuid.uuid4().hex[:4]}"
    pid_healthy = f"cp-1479-ac2-z-gesund-{uuid.uuid4().hex[:4]}"
    _clean_compare_user(uid)
    try:
        save_location(_location("loc-kaputt2", "KaputtOrt2", LAT_BROKEN, LON_BROKEN), user_id=uid)
        save_location(_location("loc-gesund2", "GesundOrt1479b", LAT_HEALTHY, LON_HEALTHY), user_id=uid)
        _write_compare_presets(uid, [
            _compare_preset(
                pid_broken, "Kaputt-Nowcast", ["loc-kaputt2"],
                radar_alert_enabled=True,
                alert_quiet_from="22:00", alert_quiet_to=2200,
            ),
            _compare_preset(
                pid_healthy, "Gesund-Nowcast", ["loc-gesund2"],
                radar_alert_enabled=True,
            ),
        ])

        frame_source = _CoordFrameSource({
            (LAT_BROKEN, LON_BROKEN): _wet_frames(8),
            (LAT_HEALTHY, LON_HEALTHY): _wet_frames(8),
        })
        mail_calls: list[tuple[str, str]] = []
        svc = CompareRadarAlertService(
            settings=_settings_email_only(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        sent = svc.check_all_compare_presets()

        delivered = [s + b for s, b in mail_calls]
        assert any("GesundOrt1479b" in text for text in delivered), (
            f"Der gesunde Nowcast-Ortsvergleich {pid_healthy!r} MUSS zustellen, "
            f"obwohl der vorher verarbeitete Ortsvergleich {pid_broken!r} einen "
            f"Nicht-String als Ruhezeit-Wert (2200) traegt — erhalten: "
            f"{len(mail_calls)} Zustellung(en), Betreffs={[s for s, _ in mail_calls]!r}, "
            f"sent={sent} (AC-2)"
        )
    finally:
        _clean_compare_user(uid)


# ══════════════════════════════════ AC-3 ═════════════════════════════════════

def test_ac3_broken_quiet_value_does_not_abort_trip_radar_run():
    """AC-3 (ROT heute) GIVEN zwei Trips DESSELBEN Nutzers — einer mit
    kaputtem ``alert_quiet_from="abc"`` (und trockenem Nowcast, damit die
    Zustellung eindeutig zuzuordnen bleibt), einer gesund mit erfuelltem
    Regen-Beginn in 8 Minuten.

    WHEN ``TripAlertService.check_radar_alerts()`` ueber alle Trips laeuft.

    THEN bricht der Lauf NICHT ab und der gesunde Trip stellt seinen Alarm zu
    (Nachweis am ``mail_sink``, nicht bloss „keine Ausnahme").

    Zur REIHENFOLGE — hier bewusst ANDERS geloest als bei AC-1/AC-2:
    ``load_all_trips()`` liest ``briefings_dir.glob("*.json")`` OHNE
    ``sorted(...)`` (``loader.py:1327``), die Reihenfolge ist also die des
    Dateisystems und nicht steuerbar. Der Test ist deshalb bewusst
    reihenfolge-UNABHAENGIG gebaut und ist in BEIDEN Reihenfolgen heute rot:
    kommt der kaputte Trip zuerst, wird der gesunde nie erreicht (0
    Zustellungen); kommt der gesunde zuerst, schlaegt der ``ValueError`` des
    kaputten Trips trotzdem aus ``check_radar_alerts()`` nach oben durch (der
    Aufruf selbst wirft, der Test bricht mit Fehler ab). Die tatsaechlich
    beobachtete Reihenfolge steht zur Diagnose in der Fehlermeldung.

    ROT-Grund heute: ``trip_alert.py:733`` ruft ``self._is_quiet_hours(...)``
    in der Trip-Schleife ab ``:709``; das erste ``try`` dieser Schleife steht
    erst bei ``:755`` (Nowcast-Abruf) — die Ausnahme reisst den gesamten
    Radar-Onset-Lauf mit.
    """
    from app.loader import load_all_trips
    from services.radar_service import RadarNowcastService
    from services.trip_alert import TripAlertService

    uid = _uid("ac3")
    tid_broken = f"trip-1479-ac3-kaputt-{uuid.uuid4().hex[:4]}"
    tid_healthy = f"trip-1479-ac3-gesund-{uuid.uuid4().hex[:4]}"

    # Der kaputte Trip startet an einer ANDEREN Koordinate und bekommt dort
    # einen trockenen Nowcast -> nach der Haertung stellt NUR der gesunde Trip
    # zu, die Zustellung ist also eindeutig zuzuordnen. Der kaputte Trip
    # erreicht die Ruhezeit-Pruefung trotzdem: sie steht in diesem Pfad VOR
    # dem Nowcast-Abruf (`trip_alert.py:733` vs. `:759`).
    _save_trip_direct(uid, tid_broken, "Kaputt-Trip",
                      {"alert_quiet_from": "abc", "alert_quiet_to": "23:00"},
                      lat=TRIP_LAT + 1.0, lon=TRIP_LON + 1.0)
    _save_trip_direct(uid, tid_healthy, "Gesund-Trip-1479", {})

    observed_order = [t.id for t in load_all_trips(user_id=uid)]

    frame_source = _CoordFrameSource({
        (TRIP_LAT, TRIP_LON): _wet_frames(8),
        (round(TRIP_LAT + 1.0, 4), round(TRIP_LON + 1.0, 4)): _dry_frames(),
    })

    mail_calls: list[tuple[str, str]] = []
    svc = TripAlertService(
        settings=_settings_email_only(), user_id=uid, throttle_hours=0,
        radar_service=RadarNowcastService(frame_source=frame_source),
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
    )
    sent = svc.check_radar_alerts()

    assert sent >= 1 and mail_calls, (
        f"Der gesunde Trip {tid_healthy!r} MUSS seinen Regen-Beginn-Alarm "
        f"zustellen, obwohl {tid_broken!r} einen unbrauchbaren Ruhezeit-Wert "
        f"('abc') traegt — erhalten: sent={sent}, "
        f"{len(mail_calls)} Zustellung(en). Beobachtete Trip-Reihenfolge: "
        f"{observed_order!r} (AC-3)"
    )


# ══════════════════════════════════ AC-4 ═════════════════════════════════════

def test_ac4_broken_quiet_value_does_not_swallow_this_trips_weather_alert():
    """AC-4 (ROT heute) GIVEN einen Trip mit kaputtem Ruhezeit-Wert
    (``alert_quiet_from="25:00"``) und einer echten, ausloesenden
    Boeen-Aenderung (20 -> 60 km/h, Standard-Empfindlichkeit).

    WHEN ``TripAlertService.check_and_send_alerts()`` fuer genau diesen Trip
    laeuft.

    THEN wird der Alarm fuer DIESEN Trip trotzdem zugestellt.

    Wie sich der Fehler heute AUSSERT: der Direktaufruf wirft den
    ``ValueError`` aus ``trip_alert.py:205`` nach oben (dieser Test bricht
    also mit Fehler ab). Im Betrieb steckt derselbe Aufruf im aeusseren
    ``try/except Exception`` von ``check_all_trips`` (``:427-438``) — dort
    wird daraus GENAU der stille Einzelverlust: der Lauf geht weiter, dieser
    Trip bekommt 0 Zustellungen, nur eine ``logger.error``-Zeile bleibt.
    """
    from tests.helpers.alert_log_fixtures import gust_alert_trip, weather
    from services.trip_alert import TripAlertService

    uid = _uid("ac4")
    trip = gust_alert_trip(f"trip-1479-ac4-{uuid.uuid4().hex[:4]}")
    trip.alert_quiet_from = "25:00"   # Stunde 25 existiert nicht -> ValueError
    trip.alert_quiet_to = "23:00"

    mail_calls: list[tuple[str, str]] = []
    svc = TripAlertService(
        settings=_settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
    )
    sent = svc.check_and_send_alerts(
        trip, [weather(1, gust_max_kmh=20.0)],
        fresh_weather=[weather(1, gust_max_kmh=60.0)],
    )

    assert sent is True, (
        f"Ein unbrauchbarer Ruhezeit-Wert darf den Alarm dieses Trips nicht "
        f"verschlucken — erwartet True, erhalten: {sent!r} (AC-4)"
    )
    assert len(mail_calls) == 1, (
        f"Erwartet genau 1 Zustellung am mail_sink, erhalten: "
        f"{len(mail_calls)} (AC-4)"
    )


# ══════════════════════════════════ AC-5 ═════════════════════════════════════

def test_ac5_broken_quiet_value_does_not_swallow_this_trips_official_alert():
    """AC-5 (ROT heute) GIVEN einen Trip mit einem Nicht-String als
    Ruhezeit-Wert (``alert_quiet_from=2200``) und einer neuen amtlichen
    Warnung.

    WHEN ``TripAlertService._send_official_alert_only()`` fuer diesen Trip
    laeuft.

    THEN wird die amtliche Warnung trotzdem zugestellt.

    Heute: ``trip_alert.py:1118`` ruft ``self._is_quiet_hours(...)`` als
    ERSTES Gate — der ``TypeError`` faellt in dasselbe aeussere
    ``try/except`` von ``check_all_trips`` und der Trip verliert seine
    amtliche Warnung still (0 Zustellungen).
    """
    from tests.helpers.alert_log_fixtures import gust_alert_trip
    from services.trip_alert import TripAlertService

    uid = _uid("ac5")
    trip = gust_alert_trip(f"trip-1479-ac5-{uuid.uuid4().hex[:4]}")
    trip.alert_quiet_from = 2200      # int statt "HH:MM" -> TypeError
    trip.alert_quiet_to = "23:00"

    mail_calls: list[tuple[str, str]] = []
    svc = TripAlertService(
        settings=_settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
    )
    sent = svc._send_official_alert_only(trip, [(_official_alert(), ["1"])])

    assert sent is True, (
        f"Ein unbrauchbarer Ruhezeit-Wert darf die amtliche Warnung dieses "
        f"Trips nicht verschlucken — erwartet True, erhalten: {sent!r} (AC-5)"
    )
    assert len(mail_calls) == 1, (
        f"Erwartet genau 1 Zustellung am mail_sink, erhalten: "
        f"{len(mail_calls)} (AC-5)"
    )


# ══════════════════════════════════ AC-6 ═════════════════════════════════════

_UNUSABLE_QUIET_VALUES = [
    pytest.param("25:00", id="kaputter-string-25-00"),
    pytest.param("abc", id="kaputter-string-abc"),
    pytest.param(2200, id="int-2200"),
    pytest.param(22.5, id="float-22-5"),
    pytest.param(["22:00"], id="liste"),
    pytest.param(True, id="bool-true"),
    pytest.param({"h": 22}, id="dict"),
]


@pytest.mark.parametrize("unusable", _UNUSABLE_QUIET_VALUES)
def test_ac6_unusable_quiet_value_returns_false_without_raising(unusable):
    """AC-6 (ROT heute) GIVEN einen unbrauchbaren Ruhezeit-Wert — zwei kaputte
    Strings (``"25:00"``, ``"abc"``) und fuenf Nicht-String-Typen (``int``,
    ``float``, ``list``, ``bool``, ``dict``).

    WHEN ``DeviationAlertEngine.is_quiet_hours()`` direkt aufgerufen wird —
    der Wert einmal als Beginn und einmal als Ende der Ruhezeit, die jeweils
    andere Haelfte gueltig.

    THEN liefert die Funktion in JEDEM dieser Faelle ``False`` („keine
    Ruhezeit gesetzt") und laesst KEINE Ausnahme nach aussen.

    Alle sieben Werte sind ``truthy`` und passieren damit den bestehenden
    Kurzschluss ``if not quiet_from or not quiet_to`` (``:91-92``) — sie
    landen also wirklich in ``time.fromisoformat()``. Das ist der Unterschied
    zu AC-7.

    ROT-Grund heute: ``time.fromisoformat()`` (``:95-96``) wirft ungefangen
    ``ValueError`` (kaputte Strings) bzw. ``TypeError`` (Nicht-Strings).
    """
    from services.deviation_alert_engine import DeviationAlertEngine

    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)

    as_from = DeviationAlertEngine.is_quiet_hours(now, unusable, "23:00")
    assert as_from is False, (
        f"Unbrauchbarer Beginn {unusable!r} muss als 'keine Ruhezeit gesetzt' "
        f"gelten — erwartet False, erhalten: {as_from!r} (AC-6)"
    )

    as_to = DeviationAlertEngine.is_quiet_hours(now, "22:00", unusable)
    assert as_to is False, (
        f"Unbrauchbares Ende {unusable!r} muss als 'keine Ruhezeit gesetzt' "
        f"gelten — erwartet False, erhalten: {as_to!r} (AC-6)"
    )


# ══════════════════════════════════ AC-7 ═════════════════════════════════════

@pytest.mark.parametrize("empty", [pytest.param("", id="leerer-string"),
                                   pytest.param(None, id="fehlt")])
def test_ac7_empty_quiet_value_returns_false_and_writes_no_warning(caplog, empty):
    """AC-7 (GRUEN heute, Regressionsschutz — NICHT kuenstlich rot gehalten)
    GIVEN einen leeren (``""``) bzw. fehlenden (``None``) Ruhezeit-Wert.

    WHEN ``DeviationAlertEngine.is_quiet_hours()`` aufgerufen wird.

    THEN liefert sie unveraendert ``False`` UND es wird KEINE Warnzeile
    geschrieben.

    Beide Haelften sind noetig: der Rueckgabewert allein wuerde den regulaeren
    Leerfall nicht von einer gefangenen Ausnahme unterscheiden. Der Leerfall
    laeuft ueber den bestehenden Kurzschluss ``if not quiet_from or not
    quiet_to`` (``:91-92``) und darf den neuen ``try/except`` NIE erreichen —
    sonst rauschte jedes unkonfigurierte Konto das Betriebsprotokoll voll.

    Warum heute gruen: der Kurzschluss existiert bereits; die Haertung darf
    daran nichts aendern.
    """
    from services.deviation_alert_engine import DeviationAlertEngine

    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)

    with caplog.at_level(logging.WARNING):
        as_from = DeviationAlertEngine.is_quiet_hours(now, empty, "23:00")
        as_to = DeviationAlertEngine.is_quiet_hours(now, "22:00", empty)

    assert as_from is False and as_to is False, (
        f"Leerer/fehlender Ruhezeit-Wert {empty!r} muss False liefern — "
        f"erhalten: Beginn={as_from!r}, Ende={as_to!r} (AC-7)"
    )
    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings == [], (
        f"Der regulaere Leerfall {empty!r} darf KEINE Warnzeile erzeugen "
        f"(sonst ist er nicht mehr von einer gefangenen Ausnahme zu "
        f"unterscheiden) — erhalten: {warnings!r} (AC-7)"
    )


# ══════════════════════════════════ AC-8 ═════════════════════════════════════

def test_ac8_caught_exception_is_logged_with_type_values_and_label(caplog):
    """AC-8 (ROT heute) GIVEN einen unbrauchbaren Ruhezeit-Wert und eine
    gesetzte Kennung (``context_label``).

    WHEN ``is_quiet_hours()`` die Ausnahme faengt.

    THEN traegt die geschriebene Warnzeile ALLE VIER Bestandteile: den
    Ausnahmetyp (``TypeError``), beide Rohwerte und die Kennung.

    Der Ausnahmetyp ist Pflicht, nicht Zierrat: das ``except`` faengt
    absichtlich breit auf ``Exception`` (der Wert stammt aus einer
    Nutzerdatei). Ohne den Typ in der Zeile ginge ein echter Programmfehler
    dort als „kaputter Nutzerwert" durch.

    ROT-Grund heute: ``is_quiet_hours()`` kennt den Parameter
    ``context_label`` nicht (``TypeError: unexpected keyword argument``) und
    schreibt ueberhaupt keine Warnzeile.
    """
    from services.deviation_alert_engine import DeviationAlertEngine

    now = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    label = f"cp-1479-ac8-{uuid.uuid4().hex[:6]}"

    with caplog.at_level(logging.WARNING):
        result = DeviationAlertEngine.is_quiet_hours(
            now, 2200, "23:00", context_label=label,
        )

    assert result is False, f"Erwartet False, erhalten: {result!r} (AC-8)"

    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    hits = [
        text for text in warnings
        if "TypeError" in text and repr(2200) in text
        and repr("23:00") in text and label in text
    ]
    assert hits, (
        "Erwartet EINE Warnzeile mit Ausnahmetyp ('TypeError'), beiden "
        f"Rohwerten ({2200!r}, {'23:00'!r}) und der Kennung {label!r} — "
        f"erhalten: {warnings!r} (AC-8)"
    )


# ═══════════════ AC-8 Wirkung an den ECHTEN Aufrufstellen ════════════════════
#
# Fix-Loop F001 (Adversary, MEDIUM): der Test oben prueft AC-8 nur am direkten
# Engine-Aufruf mit einer VON HAND uebergebenen Kennung. Entfernte man
# `context_label=preset_id` bzw. `context_label=trip.id` an den drei echten
# Aufrufstellen (`compare_official_alert.py:107-113`,
# `compare_radar_alert.py:101-109`, `trip_alert.py:510-512`), blieben alle
# Tests gruen — die eigentliche Zusicherung ("im Protokoll steht, WELCHER
# Ortsvergleich/Trip betroffen ist") waere unbewacht. Die drei folgenden Tests
# laufen deshalb ueber den echten Dienstpfad und pruefen die Kennung als
# konkreten, im Test erzeugten Wert (uuid-Suffix) — nicht gegen ein Muster,
# das auch bei leerer Kennung passte.


def _engine_quiet_warnings(caplog) -> list[str]:
    """Nur die Warnzeilen, die die Engine SELBST geschrieben hat (Logger
    ``services.deviation_alert_engine``).

    Der Filter laeuft ueber den Logger-Namen und nicht ueber den Meldungstext:
    die aufrufenden Dienste (``compare_official_alert``, ``compare_radar_alert``,
    ``trip_alert``) schreiben die Kennung ohnehin in ihre eigenen Debug-Zeilen —
    wuerde man die mitzaehlen, waere der Test auch dann gruen, wenn die Engine
    die Kennung gar nicht bekommt. Genau das ist F001.
    """
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.WARNING
        and record.name.endswith("deviation_alert_engine")
    ]


def test_ac8_effect_official_compare_run_names_the_affected_preset(caplog):
    """AC-8 Wirkung (Fix-Loop F001) GIVEN EINEN amtlichen Ortsvergleich mit
    kaputtem ``alert_quiet_from="25:00"`` und einer eindeutigen, im Test
    erzeugten Preset-Kennung.

    WHEN der ECHTE Dienstpfad ``CompareOfficialAlertService.check_all_compare_presets()``
    laeuft (nicht der direkte Engine-Aufruf).

    THEN nennt die Warnzeile der Engine genau diese Preset-Kennung — im Betrieb
    ist damit ablesbar, WELCHER Ortsvergleich den unbrauchbaren Wert traegt.

    Ohne ``context_label=preset_id`` an ``compare_official_alert.py:107-113``
    schreibt die Engine ihre Zeile ohne Kennung und dieser Test wird rot.
    """
    from services.compare_official_alert import CompareOfficialAlertService
    import services.official_alerts.base as oa_base

    uid = _uid("ac8-official")
    pid_broken = f"cp-1479-ac8eff-{uuid.uuid4().hex[:8]}"
    _clean_compare_user(uid)
    # Kein Netz: die global registrierten echten Warnquellen werden fuer die
    # Dauer des Tests geleert (Muster AC-1). Der Ruhezeit-Check steht ohnehin
    # VOR dem Abruf — nach der Haertung laeuft der Preset aber weiter bis zum
    # Abruf durch.
    sources_backup = list(oa_base._REGISTERED_SOURCES)
    oa_base._REGISTERED_SOURCES.clear()
    try:
        save_location(
            _location("loc-kaputt-ac8", "KaputtOrtAc8", LAT_BROKEN, LON_BROKEN),
            user_id=uid,
        )
        _write_compare_presets(uid, [
            _compare_preset(
                pid_broken, "Kaputt-Vergleich-AC8", ["loc-kaputt-ac8"],
                alert_quiet_from="25:00", alert_quiet_to="23:00",
            ),
        ])
        mail_calls: list[tuple[str, str]] = []
        sms_calls: list = []
        telegram_calls: list = []
        svc = CompareOfficialAlertService(
            settings=_settings_email_only(), user_id=uid,
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
            sms_sink=lambda text: sms_calls.append(text),
            telegram_sink=lambda text: telegram_calls.append(text),
        )
        with caplog.at_level(logging.WARNING):
            svc.check_all_compare_presets()

        engine_warnings = _engine_quiet_warnings(caplog)
        assert engine_warnings, (
            "Die Engine hat beim echten Preset-Lauf ueberhaupt keine Warnzeile "
            f"geschrieben — der Lauf hat den Ruhezeit-Check fuer {pid_broken!r} "
            "nicht erreicht, der Test bewacht dann nichts (AC-8 Wirkung)"
        )
        assert any(pid_broken in text for text in engine_warnings), (
            f"Die Warnzeile der Engine nennt die betroffene Preset-Kennung "
            f"{pid_broken!r} NICHT — im Betrieb waere nicht ablesbar, welcher "
            f"Ortsvergleich den unbrauchbaren Ruhezeit-Wert traegt. Fehlt "
            f"`context_label=preset_id` in compare_official_alert.py? "
            f"Erhalten: {engine_warnings!r} (AC-8 Wirkung)"
        )
        assert sms_calls == [] and telegram_calls == []
    finally:
        oa_base._REGISTERED_SOURCES.clear()
        oa_base._REGISTERED_SOURCES.extend(sources_backup)
        _clean_compare_user(uid)


def test_ac8_effect_nowcast_compare_run_names_the_affected_preset(caplog):
    """AC-8 Wirkung (Fix-Loop F001) GIVEN EINEN Nowcast-Ortsvergleich mit einem
    Nicht-String als ``alert_quiet_to`` (``2200``), eindeutiger Preset-Kennung
    und einem echten Regen-Beginn in 8 Minuten.

    WHEN ``CompareRadarAlertService.check_all_compare_presets()`` laeuft.

    THEN nennt die Warnzeile der Engine genau diese Preset-Kennung.

    Der Regen-Beginn ist Pflicht: in diesem Pfad steht der Ruhezeit-Check NACH
    der Erkennung (``compare_radar_alert.py:99-109``). Ohne Ausloeser wuerde der
    Check nie erreicht und der Test waere gruen, ohne etwas zu beweisen —
    deshalb faengt die erste Zusicherung genau diesen Fall ab.
    """
    from services.compare_radar_alert import CompareRadarAlertService
    from services.radar_service import RadarNowcastService

    uid = _uid("ac8-nowcast")
    pid_broken = f"cp-1479-ac8effr-{uuid.uuid4().hex[:8]}"
    _clean_compare_user(uid)
    try:
        save_location(
            _location("loc-kaputt-ac8r", "KaputtOrtAc8r", LAT_BROKEN, LON_BROKEN),
            user_id=uid,
        )
        _write_compare_presets(uid, [
            _compare_preset(
                pid_broken, "Kaputt-Nowcast-AC8", ["loc-kaputt-ac8r"],
                radar_alert_enabled=True,
                alert_quiet_from="22:00", alert_quiet_to=2200,
            ),
        ])
        frame_source = _CoordFrameSource({(LAT_BROKEN, LON_BROKEN): _wet_frames(8)})
        mail_calls: list[tuple[str, str]] = []
        svc = CompareRadarAlertService(
            settings=_settings_email_only(), user_id=uid,
            radar_service=RadarNowcastService(frame_source=frame_source),
            mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        )
        with caplog.at_level(logging.WARNING):
            svc.check_all_compare_presets()

        engine_warnings = _engine_quiet_warnings(caplog)
        assert engine_warnings, (
            "Die Engine hat beim echten Nowcast-Lauf keine Warnzeile "
            f"geschrieben — der Ruhezeit-Check fuer {pid_broken!r} wurde nicht "
            f"erreicht (Regen-Beginn erkannt? frame_source-Aufrufe: "
            f"{frame_source.calls!r}), der Test bewacht dann nichts "
            "(AC-8 Wirkung)"
        )
        assert any(pid_broken in text for text in engine_warnings), (
            f"Die Warnzeile der Engine nennt die betroffene Preset-Kennung "
            f"{pid_broken!r} NICHT. Fehlt `context_label=preset_id` in "
            f"compare_radar_alert.py? Erhalten: {engine_warnings!r} "
            "(AC-8 Wirkung)"
        )
    finally:
        _clean_compare_user(uid)


def test_ac8_effect_trip_run_names_the_affected_trip(caplog):
    """AC-8 Wirkung (Fix-Loop F001) GIVEN einen Trip mit kaputtem
    ``alert_quiet_from="25:00"``, eindeutiger Trip-Kennung und einer echten,
    ausloesenden Boeen-Aenderung (20 -> 60 km/h).

    WHEN der echte Aufrufer ``TripAlertService.check_and_send_alerts()`` laeuft
    — er ruft ``_is_quiet_hours()`` (``trip_alert.py:510-512``) als erstes Gate.

    THEN nennt die Warnzeile der Engine genau diese Trip-Kennung.

    Ohne ``context_label=trip.id`` in ``TripAlertService._is_quiet_hours()``
    wird dieser Test rot.
    """
    from tests.helpers.alert_log_fixtures import gust_alert_trip, weather
    from services.trip_alert import TripAlertService

    uid = _uid("ac8-trip")
    trip_id = f"trip-1479-ac8eff-{uuid.uuid4().hex[:8]}"
    trip = gust_alert_trip(trip_id)
    trip.alert_quiet_from = "25:00"
    trip.alert_quiet_to = "23:00"

    mail_calls: list[tuple[str, str]] = []
    svc = TripAlertService(
        settings=_settings_email_only(), user_id=uid, throttle_hours=0,
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
    )
    with caplog.at_level(logging.WARNING):
        svc.check_and_send_alerts(
            trip, [weather(1, gust_max_kmh=20.0)],
            fresh_weather=[weather(1, gust_max_kmh=60.0)],
        )

    engine_warnings = _engine_quiet_warnings(caplog)
    assert engine_warnings, (
        "Die Engine hat beim echten Trip-Lauf keine Warnzeile geschrieben — "
        f"der Ruhezeit-Check fuer {trip_id!r} wurde nicht erreicht, der Test "
        "bewacht dann nichts (AC-8 Wirkung)"
    )
    assert any(trip_id in text for text in engine_warnings), (
        f"Die Warnzeile der Engine nennt die betroffene Trip-Kennung "
        f"{trip_id!r} NICHT — im Betrieb waere nicht ablesbar, welcher Trip "
        f"den unbrauchbaren Ruhezeit-Wert traegt. Fehlt `context_label=trip.id` "
        f"in TripAlertService._is_quiet_hours()? Erhalten: "
        f"{engine_warnings!r} (AC-8 Wirkung)"
    )


# ══════════════════════════════════ AC-9 ═════════════════════════════════════

def test_ac9_valid_quiet_window_still_suppresses_including_midnight_wrap():
    """AC-9 (GRUEN heute, Regressionsschutz — NICHT kuenstlich rot gehalten)
    GIVEN eine gueltige, vollstaendige Ruhezeit ``22:00-07:00``
    (Mitternachts-Wrap) und ein halb ausgefuelltes Fenster (nur Beginn).

    WHEN ``is_quiet_hours()`` mit den Faellen aus #181 aufgerufen wird.

    THEN bleibt das Verhalten gegenueber dem Stand vor dieser Scheibe
    unveraendert: innerhalb des Fensters wird unterdrueckt, ausserhalb nicht,
    die obere Grenze ist ausschliessend (``< to``), und das halbe Fenster
    unterdrueckt NIE (Known Limitation aus #181).

    Alle Zeitpunkte sind bewusst in Europe/Vienna angegeben: ``is_quiet_hours``
    rechnet seit #1312 D1 nach Vienna um; ein UTC-Zeitpunkt haette je nach
    Sommer-/Winterzeit eine andere Ortszeit und der Test wuerde am
    Zeitumstellungstag etwas anderes pruefen als behauptet.
    """
    from services.deviation_alert_engine import VIENNA, DeviationAlertEngine

    def at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
        return datetime(2026, month, day, hour, minute, tzinfo=VIENNA)

    assert DeviationAlertEngine.is_quiet_hours(at(6, 15, 23, 30), "22:00", "07:00") is True, (
        "23:30 Ortszeit liegt im Fenster 22:00-07:00 (Mitternachts-Wrap) (AC-9)"
    )
    assert DeviationAlertEngine.is_quiet_hours(at(6, 16, 3, 0), "22:00", "07:00") is True, (
        "03:00 Ortszeit liegt nach Mitternacht noch im Fenster 22:00-07:00 (AC-9)"
    )
    assert DeviationAlertEngine.is_quiet_hours(at(6, 16, 7, 0), "22:00", "07:00") is False, (
        "07:00 exakt ist das ENDE des Fensters und wird nicht mehr unterdrueckt (AC-9)"
    )
    assert DeviationAlertEngine.is_quiet_hours(at(6, 16, 12, 0), "22:00", "07:00") is False, (
        "12:00 Ortszeit liegt ausserhalb des Fensters 22:00-07:00 (AC-9)"
    )
    assert DeviationAlertEngine.is_quiet_hours(at(1, 15, 23, 30), "22:00", "07:00") is True, (
        "Auch in der Winterzeit gilt dasselbe Fenster in Ortszeit (AC-9)"
    )
    assert DeviationAlertEngine.is_quiet_hours(at(6, 15, 15, 0), "08:00", "22:00") is True, (
        "15:00 Ortszeit liegt im normalen (nicht wrappenden) Fenster 08:00-22:00 (AC-9)"
    )
    assert DeviationAlertEngine.is_quiet_hours(at(6, 15, 23, 0), "22:00", None) is False, (
        "Halb ausgefuelltes Fenster (Beginn ohne Ende) darf NIE unterdruecken "
        "— Known Limitation aus #181 (AC-9)"
    )
    assert DeviationAlertEngine.is_quiet_hours(at(6, 15, 23, 0), None, "07:00") is False, (
        "Halb ausgefuelltes Fenster (Ende ohne Beginn) darf NIE unterdruecken (AC-9)"
    )


# ═════════════════════════════ AC-11 (Struktur) ══════════════════════════════
#
# AC-10 hat bewusst KEINEN Test hier — s. Modul-Docstring.

_QUIET_CALL_NAMES = {"is_quiet_hours", "_is_quiet_hours"}

# `compare_alert.py` ist bewusst MIT in der Liste, obwohl AC-11 im Wortlaut
# nur die drei anderen Dateien nennt und den dortigen Behelf aus #1467 S2 AG2
# "ausnimmt". Grund: der Rueckbau genau dieses Behelfs ist laut Spec Teil
# DIESER Scheibe ("Rueckbau: compare_alert.py:161-181"). Ein Eintrag mit
# Ausnahme-Zweig waere heute gruen und muesste nach dem Rueckbau von Hand
# nachgezogen werden; so ist er heute rot, wird durch den Rueckbau gruen und
# bewacht die Datei danach OHNE jede Aenderung an dieser Testdatei mit —
# genau die geforderte Selbst-Erledigung. Ein spaeterer Rueckfall in die vom
# PO verworfene Kopier-Loesung (eigenes try/except je Aufrufstelle) faellt
# dann in allen vier Dateien auf.
#
# Issue #1467 S3: `compare_radar_alert.py` ist hier durch `alert_gate.py`
# ERSETZT, nicht gestrichen — die Ruhezeit-Aufrufstelle des Vergleichs-Nowcast
# ist mit dieser Scheibe in den geteilten Freigabe-Baustein umgezogen (dort
# liegt sie jetzt fuer BEIDE Nowcast-Pfade). Der Waechter zieht mit dem Aufruf
# um; bliebe der alte Eintrag stehen, liefe er in einer Datei ohne Aufruf ins
# Leere und die Sicherung 1 unten (mindestens eine Aufrufstelle gefunden)
# wuerde ihn zu Recht als Testfehler melden. `trip_alert.py` bleibt in der
# Liste: dort rufen der Aenderungs- und der amtliche Pfad weiterhin selbst.
_GUARDED_FILES = [
    "compare_official_alert.py",
    "alert_gate.py",
    "trip_alert.py",
    "compare_alert.py",
]

# Selbstpruefung des Suchmechanismus (Pflicht): ein Waechter, der nichts
# findet, ist immer gruen und damit wertlos. Diese beiden Bausteine sind
# KEIN Produktivcode, sondern der Pruefstein fuer den Pruefer selbst.
_SELF_CHECK_VIOLATION = textwrap.dedent(
    """
    def check(now, a, b):
        try:
            active = DeviationAlertEngine.is_quiet_hours(now, a, b)
        except Exception:
            active = False
        return active
    """
)

# Fix-Loop F002 (Adversary, LOW): `with contextlib.suppress(Exception):` ist
# semantisch dasselbe Wiederaufbauen des Schutzes an der Aufrufstelle wie ein
# eigenes try/except — nur eine andere Schreibweise. Beide Import-Formen
# ("contextlib.suppress" und das direkt importierte "suppress") gehoeren
# geprueft, sonst genuegt ein anderer Import, um am Waechter vorbeizukommen.
_SELF_CHECK_SUPPRESS_VIOLATION = textwrap.dedent(
    """
    import contextlib

    def check(now, a, b):
        active = False
        with contextlib.suppress(Exception):
            active = DeviationAlertEngine.is_quiet_hours(now, a, b)
        return active
    """
)
_SELF_CHECK_BARE_SUPPRESS_VIOLATION = textwrap.dedent(
    """
    from contextlib import suppress

    def check(now, a, b):
        active = False
        with suppress(ValueError, TypeError):
            active = DeviationAlertEngine.is_quiet_hours(now, a, b)
        return active
    """
)
_SELF_CHECK_CLEAN = textwrap.dedent(
    """
    def check(now, a, b):
        active = DeviationAlertEngine.is_quiet_hours(now, a, b, context_label="x")
        if active:
            return False
        return True
    """
)
# Gegenbaustein zur zweiten Ausfallart des erweiterten Waechters ("meldet
# alles"): ein `with`-Block, der NICHTS unterdrueckt, ist kein Verstoss.
_SELF_CHECK_CLEAN_WITH = textwrap.dedent(
    """
    def check(now, a, b, lock):
        with lock:
            return DeviationAlertEngine.is_quiet_hours(now, a, b, context_label="x")
    """
)


def _called_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _quiet_call_lines(source: str) -> list[int]:
    """Zeilennummern aller ECHTEN Aufrufe von ``is_quiet_hours``/
    ``_is_quiet_hours``. Ueber den Syntaxbaum statt per Textsuche: Kommentare
    und Doku-Texte, in denen der Name nur ERWAEHNT wird (davon gibt es in
    ``trip_alert.py`` und ``compare_alert.py`` mehrere), sind sonst
    Falschtreffer."""
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and _called_name(node) in _QUIET_CALL_NAMES
    )


def _quiet_calls_inside_own_try(source: str) -> list[int]:
    """Zeilennummern der Aufrufe, die in einem EIGENEN ``try``-Block der Datei
    stehen (``try``-Rumpf, gleich wie tief verschachtelt) — genau das
    Kopier-Muster, das AC-11 ausschliesst."""
    hits: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Try):
            continue
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Call) and _called_name(sub) in _QUIET_CALL_NAMES:
                    hits.add(sub.lineno)
    return sorted(hits)


def _quiet_calls_inside_suppress(source: str) -> list[int]:
    """Zeilennummern der Aufrufe, die in einem ``with contextlib.suppress(...)``-
    Block stehen (Fix-Loop F002).

    ``contextlib.suppress`` verschluckt die Ausnahme genauso wie ein eigenes
    ``try/except`` — es ist dieselbe, vom PO verworfene Kopier-Loesung in
    anderer Schreibweise. Erkannt werden beide Import-Formen: der qualifizierte
    Aufruf (``contextlib.suppress(...)``, ``ast.Attribute``) und der direkt
    importierte (``suppress(...)``, ``ast.Name``). Andere ``with``-Blocks
    (Locks, geoeffnete Dateien) sind ausdruecklich KEIN Verstoss.
    """
    hits: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.With, ast.AsyncWith)):
            continue
        suppresses = any(
            isinstance(item.context_expr, ast.Call)
            and _called_name(item.context_expr) == "suppress"
            for item in node.items
        )
        if not suppresses:
            continue
        for stmt in node.body:
            for sub in ast.walk(stmt):
                if isinstance(sub, ast.Call) and _called_name(sub) in _QUIET_CALL_NAMES:
                    hits.add(sub.lineno)
    return sorted(hits)


def _quiet_calls_inside_own_guard(source: str) -> list[int]:
    """Alle Formen des an der Aufrufstelle wiederaufgebauten Schutzes:
    eigenes ``try``/``except`` ODER ``with contextlib.suppress(...)``."""
    return sorted(
        set(_quiet_calls_inside_own_try(source)) | set(_quiet_calls_inside_suppress(source))
    )


def test_ac11_search_mechanism_actually_detects_a_violation():
    """AC-11 Selbstpruefung (heute GRUEN, und das ist der Punkt): beweist,
    dass der Suchmechanismus ueberhaupt greift.

    Ein Waechter, der nie etwas findet, besteht immer — und bewacht nichts.
    Deshalb laeuft hier DERSELBE Mechanismus, den der eigentliche
    Struktur-Test benutzt, gegen zwei kuenstliche Textbausteine:

    * ein Baustein MIT eigenem ``try/except`` um den Aufruf -> MUSS als
      Verstoss erkannt werden,
    * ein Baustein OHNE -> darf KEINEN Verstoss melden, aber der Aufruf selbst
      muss trotzdem gefunden werden.

    Beide Haelften zusammen schliessen die zwei Ausfallarten aus: „findet
    immer nichts" und „findet immer alles".
    """
    assert len(_quiet_call_lines(_SELF_CHECK_VIOLATION)) == 1, (
        "Selbstpruefung: der Aufruf-Finder erkennt den Aufruf im "
        "Verstoss-Baustein nicht — der Waechter waere blind."
    )
    assert len(_quiet_calls_inside_own_try(_SELF_CHECK_VIOLATION)) == 1, (
        "Selbstpruefung FEHLGESCHLAGEN: der Mechanismus meldet den "
        "offensichtlichen Verstoss (try/except um den Aufruf) NICHT. Ein "
        "Waechter, der nichts findet, ist immer gruen und damit wertlos."
    )
    assert len(_quiet_call_lines(_SELF_CHECK_CLEAN)) == 1, (
        "Selbstpruefung: der Aufruf-Finder erkennt den Aufruf im sauberen "
        "Baustein nicht."
    )
    assert _quiet_calls_inside_own_try(_SELF_CHECK_CLEAN) == [], (
        "Selbstpruefung FEHLGESCHLAGEN: der Mechanismus meldet einen Verstoss "
        "im sauberen Baustein — er wuerde alles melden und waere ebenso wertlos."
    )


def test_ac11_search_mechanism_also_detects_contextlib_suppress():
    """AC-11 Selbstpruefung, zweite Umgehungsform (Fix-Loop F002).

    ``with contextlib.suppress(Exception):`` um den Aufruf verschluckt die
    Ausnahme genauso wie ein eigenes ``try/except`` — der urspruengliche
    Waechter sah nur ``ast.Try`` und war fuer diese Schreibweise blind.

    Geprueft werden hier dieselben zwei Ausfallarten wie oben, jetzt fuer den
    erweiterten Mechanismus:

    * ein Baustein MIT ``contextlib.suppress`` -> genau EIN Verstoss,
    * derselbe Baustein mit direkt importiertem ``suppress`` -> genau EIN
      Verstoss (ein anderer Import darf nicht am Waechter vorbeifuehren),
    * ein Baustein OHNE Unterdrueckung -> NULL Verstoesse; ein gewoehnlicher
      ``with``-Block (Lock) ebenfalls NULL, sonst meldete der Waechter alles.
    """
    assert len(_quiet_call_lines(_SELF_CHECK_SUPPRESS_VIOLATION)) == 1, (
        "Selbstpruefung: der Aufruf-Finder erkennt den Aufruf im "
        "contextlib.suppress-Baustein nicht — der Waechter waere blind."
    )
    assert len(_quiet_calls_inside_own_guard(_SELF_CHECK_SUPPRESS_VIOLATION)) == 1, (
        "Selbstpruefung FEHLGESCHLAGEN: `with contextlib.suppress(Exception):` "
        "um den is_quiet_hours()-Aufruf wird NICHT als Verstoss gemeldet. Das "
        "ist dieselbe Kopier-Loesung wie try/except, nur anders geschrieben "
        "(Fix-Loop F002)."
    )
    assert len(_quiet_calls_inside_own_guard(_SELF_CHECK_BARE_SUPPRESS_VIOLATION)) == 1, (
        "Selbstpruefung FEHLGESCHLAGEN: das direkt importierte "
        "`from contextlib import suppress` wird NICHT erkannt — ein anderer "
        "Import genuegte dann, um am Waechter vorbeizukommen (Fix-Loop F002)."
    )
    assert _quiet_calls_inside_own_guard(_SELF_CHECK_CLEAN) == [], (
        "Selbstpruefung FEHLGESCHLAGEN: der erweiterte Mechanismus meldet "
        "einen Verstoss im sauberen Baustein — er wuerde alles melden."
    )
    assert len(_quiet_call_lines(_SELF_CHECK_CLEAN_WITH)) == 1, (
        "Selbstpruefung: der Aufruf-Finder erkennt den Aufruf im "
        "gewoehnlichen with-Baustein nicht."
    )
    assert _quiet_calls_inside_own_guard(_SELF_CHECK_CLEAN_WITH) == [], (
        "Selbstpruefung FEHLGESCHLAGEN: ein gewoehnlicher `with`-Block (Lock, "
        "geoeffnete Datei) unterdrueckt keine Ausnahme und ist KEIN Verstoss."
    )


@pytest.mark.parametrize("filename", _GUARDED_FILES)
def test_ac11_no_own_try_except_around_quiet_hours_callsite(filename):
    """AC-11 GIVEN den Code-Stand nach dieser Scheibe.

    WHEN die Aufrufstellen in ``compare_official_alert.py``,
    ``compare_radar_alert.py``, ``trip_alert.py`` (und nach dem Rueckbau auch
    ``compare_alert.py``) auf einen EIGENEN, an der Aufrufstelle
    wiederaufgebauten Schutz um den ``is_quiet_hours()``-Aufruf durchsucht
    werden — ``try``/``except`` ODER ``with contextlib.suppress(...)``
    (Fix-Loop F002: beides verschluckt die Ausnahme, es ist dieselbe
    Kopier-Loesung in zwei Schreibweisen).

    THEN findet sich dort keines — der Schutz lebt ausschliesslich in
    ``DeviationAlertEngine.is_quiet_hours()``. Ein Rueckfall in die vom PO
    ausdruecklich verworfene Kopier-Loesung bricht diesen Test.

    Zwei eingebaute Sicherungen gegen einen wertlosen Waechter:

    1. Der Test verlangt, dass in JEDER geprueften Datei mindestens eine
       echte Aufrufstelle GEFUNDEN wird. Findet die Suche keine, ist das ein
       Testfehler, kein Erfolg (z.B. weil eine Datei umbenannt wurde oder der
       Aufruf ueber einen neuen Namen laeuft).
    2. Der Mechanismus selbst wird in
       ``test_ac11_search_mechanism_actually_detects_a_violation`` gegen einen
       kuenstlichen Verstoss und einen sauberen Gegenbaustein geprueft.

    Zu ``compare_alert.py``: heute ROT (der Behelfs-Schutz aus #1467 S2 AG2
    steht dort noch), nach dem in dieser Scheibe vorgesehenen Rueckbau gruen —
    und danach ohne jede Aenderung an dieser Testdatei dauerhaft mitbewacht.
    S. Kommentar bei ``_GUARDED_FILES``.
    """
    path = SERVICES_DIR / filename
    assert path.is_file(), (
        f"Geprueftes Modul {path} existiert nicht — der Waechter wuerde ins "
        "Leere laufen (AC-11)"
    )
    source = path.read_text(encoding="utf-8")

    call_lines = _quiet_call_lines(source)
    assert call_lines, (
        f"In {filename} wurde KEIN Aufruf von is_quiet_hours()/_is_quiet_hours() "
        "gefunden. Das ist ein Testfehler, kein Erfolg: der Waechter bewacht "
        "dann nichts (AC-11)"
    )

    violations = _quiet_calls_inside_own_guard(source)
    assert violations == [], (
        f"{filename} umgibt den is_quiet_hours()-Aufruf mit einem EIGENEN "
        f"try/except oder contextlib.suppress (Zeile(n) {violations}). Der "
        "Schutz gehoert in die "
        "geteilte Engine (ADR-0021), nicht in eine weitere Kopie an der "
        "Aufrufstelle — genau diese Loesung hat der PO am 2026-08-03 "
        "verworfen (AC-11). Bei compare_alert.py ist das heute erwartet: "
        "dort steht noch der Behelfs-Schutz aus #1467 S2 AG2, dessen Rueckbau "
        "Teil dieser Scheibe ist."
    )
