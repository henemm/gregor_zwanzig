"""TDD RED — Epic #2261, Scheibe A-2 S2: faire Reihenfolge + Zeitgrenze im
Radar-Alarmlauf (Trip-Radar UND Ortsvergleich-Radar).

SPEC: docs/specs/modules/feat_2261_a2s2_radar_takt.md (AC-5, AC-6, AC-7,
AC-8, AC-12, AC-13). Vorlage: ``tests/tdd/test_alert_run_fairness.py`` (S1).

VERTRAG, den diese Tests der Implementierung vorgeben (Developer-Hinweise):

* ``services.trip_alert.RADAR_RUN_DEADLINE_SECONDS`` (45.0) wird zur
  AUFRUFZEIT gelesen, im Funktionsrumpf (``run_started_at + RADAR_RUN_...``),
  NICHT als Default-Argument oder bei Import gebundene Kopie. Die Tests
  verkleinern sie per ``monkeypatch.setattr(trip_alert, ...)``. Importiert
  ``compare_radar_alert`` die Konstante per ``from ... import`` (gebundene
  Kopie), patchen die Tests zusaetzlich ``compare_radar_alert.
  RADAR_RUN_DEADLINE_SECONDS`` (nur wenn das Attribut dort existiert) — es
  funktioniert also beides, Hauptsache der Wert wird je Lauf frisch gelesen.
* ``TripAlertService.check_radar_alerts_run() -> AlertCheckRunResult`` und
  ``CompareRadarAlertService.check_all_compare_presets_run() ->
  AlertCheckRunResult``; ``check_radar_alerts()`` /
  ``check_all_compare_presets()`` bleiben ``int``.
* Der Lauf reicht ``deadline_at=<monotonic-Marke>`` als KEYWORD an
  ``radar_service.get_nowcast(...)`` durch. Die Stub-Dienste der Tests
  nehmen es als ``deadline_at=None`` entgegen.
* ``RadarDeadlineExceeded`` aus ``get_nowcast`` (auch in einem Zonenpunkt
  mitten im Trip) bricht die Einheit ab: keine Teilauswertung, KEIN
  Quellenausfall-/``data_unavailable``-Protokolleintrag, keine Buchung auf
  Sperrzeit/Tageslimit, kein Stempel, ID in ``skipped_ids``. Die Ausnahme
  wird VOR dem breiten ``except Exception`` abgefangen.
* ``AlertCheckStateStore(user_id, filename=...)`` — optionaler Dateiname,
  Default ``alert_last_checked.json``; Lock auf ``<filename>.lock``.
  Dateien: ``alert_last_checked_radar.json`` (Trip),
  ``alert_last_checked_compare_radar.json`` (Ortsvergleich).
  WARNING bei kaputter Datei/Lock-Timeout nennt den ECHTEN Dateinamen.

ACHTUNG fuer bestehende Test-Fakes: sobald der Lauf ``deadline_at=`` an
``get_nowcast`` reicht, scheitern Fakes mit fester Signatur (z.B.
``_GuaranteedWetRadar`` in ``test_952_onset_alert_fidelity.py``) mit
TypeError — der breite ``except Exception`` machte daraus still einen
Quellenausfall. Vor dem Commit alle ``def get_nowcast(`` unter ``tests/``
pruefen und um ``deadline_at=None`` erweitern.

Kein Mock-Theater: echte ``RadarNowcastService``-Unterklasse am DI-Seam,
echte Schlafzeit je Einheit (erste Anfrage je Trip/Ort), echte Trips/
Ortsvergleiche unter dem isolierten Datenbaum, echter FastAPI-Router, echte
Stempel-Dateien. Kein ``AlarmPruefstrecke`` (bindet lokale TCP-Server, unter
``--disable-socket`` blockiert) — E-Mail ist der einzige Kanal, abgegriffen
ueber ``mail_sink``.
"""
from __future__ import annotations

import dataclasses
import fcntl
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.loader import get_data_dir, save_location, save_trip
from app.models import TripReportConfig
from app.user import SavedLocation
from services import alert_daily_limit, trip_alert
from services.radar_cache import RadarNowcastCacheService
from services.radar_service import INTENSITY_DRY, NowcastResult, RadarNowcastService
from services.throttle_store import ThrottleStore
from services.trip_alert import TripAlertService
from utils.timezone import tz_for_coords

# Auf Modulebene (nicht im Testrumpf): api/main.py ruft beim ersten Import
# logging.basicConfig(force=True) auf und entfernt den caplog-Handler eines
# laufenden Tests (Muster test_alert_run_fairness.py).
from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402

from tests.helpers.compare_briefings import write_compare_briefings  # noqa: E402
from tests.tdd.test_952_onset_alert_fidelity import _trip_with_active_segment  # noqa: E402
from tests.tdd.test_compare_radar_alert import (  # noqa: E402
    _data_root_users,
    _radar_preset,
    _settings_email_capable_dummy,
)
from tests.tdd.test_issue_827_radar_throttle_recording import (  # noqa: E402
    _make_settings_with_email,
    _wet_frames,
)

TRIP_STATE = "alert_last_checked_radar.json"
COMPARE_STATE = "alert_last_checked_compare_radar.json"
S1_STATE = "alert_last_checked.json"

# Je Einheit EINE echte Schlafzeit (erste Anfrage), Grenze so, dass sie
# real unterschritten wird, mit grossem Abstand gegen Laufzeit-Rauschen
# (Per-Trip-Overhead auf dem trockenen Pfad liegt bei Zehntelsekunden).
SLEEP_S = 0.4
DEADLINE_S = 0.6

# Trip-Geometrie (Korsika, aus ``_trip_with_active_segment``: Start 42.20/9.10,
# Ziel 42.25/9.15). Trip j liegt um j*TRIP_STEP weiter noerdlich — so ist ueber
# die Breite jeder Anfrage erkennbar, zu WELCHEM Trip sie gehoert.
TRIP_LAT0 = 42.20
TRIP_STEP = 0.15
# Ortsvergleich: je Preset EIN Ort, Breite 46.0 + 0.3*i.
LOC_LAT0 = 46.0
LOC_STEP = 0.3
LOC_LON = 7.75


# Gestellte Uhr (#2261, Gestellte-Uhr-Ratsche #2242): ``_trip_with_active_segment``
# baut das Segment um die Wanduhr. Abends (Ortszeit nahe Tagesfenster-Ende 19:00)
# schrumpft das Ziel-Segment auf das Mindestfenster, der Trip bekommt nur 1
# Messpunkt und die Fairness-Aussagen (>= 2 Messpunkte je Trip) sind nicht mehr
# pruefbar. Mittags UTC liegt das Segment fuer jede Tageszeit des Laufs gleich.
# ``tick=True``: die Deadline-Tests brauchen weiterlaufende Zeit. ``time.monotonic``
# bleibt ECHT: freezegun ersetzt es je nach Aufrufer-Stack (Threadpool des
# TestClients) mal ja, mal nein — Deadline-Marke und Pruefung sahen dann
# verschiedene Uhren und die Grenze lief sofort ab.
_UHR = "2026-10-01T10:00:00+00:00"


@pytest.fixture(autouse=True)
def _gestellte_uhr():
    echte_monotonic = time.monotonic
    with freeze_time(_UHR, tick=True):
        time.monotonic = echte_monotonic
        yield


def _uid(tag: str) -> str:
    return f"tdd-2261s2-{tag}-{uuid.uuid4().hex[:6]}"


def _state_path(uid: str, filename: str):
    return get_data_dir(uid) / filename


def _read_state(uid: str, filename: str) -> dict[str, datetime]:
    path = _state_path(uid, filename)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {k: datetime.fromisoformat(v) for k, v in raw.items()}


def _write_state(uid: str, filename: str, stamps: dict[str, datetime]) -> None:
    path = _state_path(uid, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: v.isoformat() for k, v in stamps.items()}), encoding="utf-8")


def _patch_deadline(monkeypatch: pytest.MonkeyPatch, seconds: float) -> None:
    """Verkleinert die Radar-Zeitgrenze fuer Trip- UND Ortsvergleich-Lauf."""
    from services import compare_radar_alert

    monkeypatch.setattr(trip_alert, "RADAR_RUN_DEADLINE_SECONDS", seconds)
    if hasattr(compare_radar_alert, "RADAR_RUN_DEADLINE_SECONDS"):
        monkeypatch.setattr(compare_radar_alert, "RADAR_RUN_DEADLINE_SECONDS", seconds)


# ---------------------------------------------------------------------------
# Stub-Radar: echte Unterklasse, echte Schlafzeit, zaehlt Aufrufe je Einheit.
# ---------------------------------------------------------------------------

class _ScriptedRadar(RadarNowcastService):
    """``idx_fn(lat) -> Einheit`` ordnet jede Anfrage einer Einheit (Trip/Ort)
    zu. Je Einheit: Schlafzeit bei der ERSTEN Anfrage, Aufrufzaehler,
    optional eine Ausnahme bei der n-ten Anfrage. ``wet`` liefert ueber den
    echten ``frame_source``-Seam Regen (Beginn in 5 Min), sonst trocken."""

    def __init__(
        self, idx_fn, *, sleep_first_s: float = 0.0, wet: bool = False,
        raise_on: tuple[int, int, BaseException] | None = None,
    ) -> None:
        super().__init__(
            frame_source=_wet_frames if wet else None, cache=RadarNowcastCacheService(),
        )
        self._idx_fn = idx_fn
        self._sleep_first_s = sleep_first_s
        self._wet = wet
        self._raise_on = raise_on  # (einheit, aufruf_nr ab 1, Ausnahme)
        self.first_seen: list[int] = []
        self.calls_per_unit: dict[int, int] = {}

    def get_nowcast(
        self, lat, lon, elevation_m=None, priority="user_briefing", user_id=None,
        deadline_at=None,
    ):
        idx = self._idx_fn(lat)
        n = self.calls_per_unit.get(idx, 0) + 1
        self.calls_per_unit[idx] = n
        if idx not in self.first_seen:
            self.first_seen.append(idx)
            time.sleep(self._sleep_first_s)
        if self._raise_on and self._raise_on[0] == idx and self._raise_on[1] == n:
            raise self._raise_on[2]
        if self._wet:
            return super().get_nowcast(lat, lon, elevation_m, priority, user_id)
        return NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY, source="radar")


def _trip_idx(lat: float) -> int:
    return int((lat - TRIP_LAT0 + 0.05) // TRIP_STEP)


def _loc_idx(lat: float) -> int:
    return int(round((lat - LOC_LAT0) / LOC_STEP))


# ---------------------------------------------------------------------------
# Aufbau Trips / Ortsvergleiche
# ---------------------------------------------------------------------------

def _premium(uid: str) -> None:
    """Tier ``premium`` = kein Tageslimit (#1070 AC-3); ohne das deckelt das
    Standard-Tageslimit die Meldungen auf 2 je Tag und verfaelschte die
    Mehr-Einheiten-Tests (AC-13)."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": "premium"}), encoding="utf-8")


def _make_trips(uid: str, ids: list[str]) -> list[str]:
    """Legt je ID einen Trip mit jetzt aktivem Segment an; Trip j (Listen-
    position) liegt um j*TRIP_STEP noerdlicher. Rueckgabe: die IDs in
    Listenposition (idx -> id)."""
    _premium(uid)
    for j, trip_id in enumerate(ids):
        trip = _trip_with_active_segment(
            trip_id, TripReportConfig(trip_id=trip_id, send_email=True, alert_on_changes=True),
        )
        # Waypoint und Stage sind frozen → ersetzen statt mutieren (Trip ist mutabel).
        stage = trip.stages[0]
        trip.stages = [dataclasses.replace(stage, waypoints=[
            dataclasses.replace(wp, lat=round(wp.lat + j * TRIP_STEP, 6))
            for wp in stage.waypoints
        ])]
        save_trip(trip, user_id=uid)
    return ids


def _make_presets(uid: str, ids: list[str]) -> list[str]:
    _premium(uid)
    presets = []
    for i, preset_id in enumerate(ids):
        loc_id = f"loc-{preset_id}"
        save_location(
            SavedLocation(
                id=loc_id, name=f"Ort {preset_id}", lat=LOC_LAT0 + i * LOC_STEP,
                lon=LOC_LON, elevation_m=1000,
            ),
            user_id=uid,
        )
        presets.append(_radar_preset(preset_id, [loc_id], ["gregor-test@henemm.com"]))
    write_compare_briefings(_data_root_users() / uid, presets)
    return ids


def _trip_service(uid: str, radar, mails: list | None = None) -> TripAlertService:
    sink = mails if mails is not None else []
    return TripAlertService(
        settings=_make_settings_with_email(), user_id=uid, radar_service=radar,
        mail_sink=lambda subject, body: sink.append((subject, body)),
    )


def _compare_service(uid: str, radar, mails: list | None = None):
    from services.compare_radar_alert import CompareRadarAlertService

    sink = mails if mails is not None else []
    return CompareRadarAlertService(
        settings=_settings_email_capable_dummy(), user_id=uid, radar_service=radar,
        mail_sink=lambda subject, body: sink.append((subject, body)),
    )


def _ids(order: list[int], mapping: list[str]) -> list[str]:
    return [mapping[i] for i in order]


# ---------------------------------------------------------------------------
# AC-5 — Trip-Radar: zwei Laeufe decken alle Trips ab.
# ---------------------------------------------------------------------------

# Bewusst NICHT in ID-Reihenfolge angelegt (``load_all_trips`` sortiert nicht).
TRIP_IDS = ["t-c", "t-a", "t-d", "t-b"]


def test_trip_radar_zwei_laeufe_decken_alle_trips_ab(monkeypatch):
    """AC-5: Given N=4 Trips mit real zeitverbrauchender Radar-Pruefung und
    eine Grenze, die je Lauf nur k < N zulaesst / When zwei Laeufe von
    ``check_radar_alerts_run`` nacheinander / Then beginnt Lauf 2 mit genau
    den in Lauf 1 uebersprungenen Trips, die Vereinigung ist gleich allen N,
    ``skipped_ids`` nennt die nicht erreichten Trips in Pruefreihenfolge
    (``len == skipped``), ein nicht erreichter Trip erhaelt keinen Stempel.

    Mutation „ID-Reihenfolge statt Stempel" laesst Lauf 2 dieselben Trips
    pruefen ⇒ rot. RED heute: ``check_radar_alerts_run`` existiert nicht."""
    uid = _uid("ac5")
    ids = _make_trips(uid, TRIP_IDS)
    _patch_deadline(monkeypatch, DEADLINE_S)

    radar1 = _ScriptedRadar(_trip_idx, sleep_first_s=SLEEP_S)
    first = _trip_service(uid, radar1).check_radar_alerts_run()
    run1 = _ids(radar1.first_seen, ids)
    # Stempel NACH Lauf 1 festhalten (Lauf 2 stempelt die Restlichen).
    stamped_after_run1 = set(_read_state(uid, TRIP_STATE))

    radar2 = _ScriptedRadar(_trip_idx, sleep_first_s=SLEEP_S)
    second = _trip_service(uid, radar2).check_radar_alerts_run()
    run2 = _ids(radar2.first_seen, ids)

    assert first.hit_deadline, f"Lauf 1 muss an der Grenze abbrechen: {first!r}"
    assert 0 < len(run1) < len(ids), f"k muss zwischen 0 und N liegen: {run1!r}"
    # Lauf 1 ohne Stempel: Fallback-Reihenfolge nach ID, Grenze schneidet hinten ab.
    assert run1 == sorted(ids)[: len(run1)], f"Lauf 1 prueft nach ID: {run1!r}"
    not_reached = [t for t in sorted(ids) if t not in run1]
    assert first.skipped_ids == not_reached, (first.skipped_ids, not_reached)
    assert len(first.skipped_ids) == first.skipped == len(not_reached)
    assert first.checked == len(run1)
    stamped = stamped_after_run1
    assert stamped == set(run1), (
        f"Nur erreichte Trips tragen einen Stempel: Stempel={sorted(stamped)!r}, erreicht={run1!r}"
    )

    assert run2[: len(not_reached)] == not_reached, (
        f"Lauf 2 muss mit den uebersprungenen Trips beginnen: {not_reached!r}, war {run2!r}"
    )
    assert set(run1) | set(run2) == set(ids), (
        f"Vereinigung muss alle Trips abdecken: Lauf 1={run1!r}, Lauf 2={run2!r}"
    )
    assert len(second.skipped_ids) == second.skipped


def test_trip_radar_reihenfolge_kommt_aus_radar_stempeln_nicht_aus_abweichungsdatei():
    """AC-5/AC-6 (eigene Datei je Alarmart): seeded Stempel in
    ``alert_last_checked_radar.json`` bestimmen die Reihenfolge; ein Stempel-
    Satz in der Abweichungs-Datei ``alert_last_checked.json`` (S1) wird
    IGNORIERT. Mutation „gemeinsame Stempeldatei" ⇒ rot.

    RED heute: ``check_radar_alerts_run`` existiert nicht."""
    uid = _uid("ac5order")
    ids = _make_trips(uid, ["t-1", "t-2", "t-3"])
    base = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    # Abweichungsdatei: wuerde Reihenfolge t-3, t-2, t-1 erzwingen.
    _write_state(uid, S1_STATE, {
        "t-1": base + timedelta(hours=3), "t-2": base + timedelta(hours=2),
        "t-3": base + timedelta(hours=1),
    })
    s1_bytes = _state_path(uid, S1_STATE).read_bytes()
    # Radar-Datei: t-2 am aeltesten, t-3 ohne Eintrag (= aeltester ueberhaupt).
    _write_state(uid, TRIP_STATE, {
        "t-1": base + timedelta(hours=9), "t-2": base - timedelta(hours=9),
    })
    radar = _ScriptedRadar(_trip_idx)

    _trip_service(uid, radar).check_radar_alerts_run()

    assert _ids(radar.first_seen, ids) == ["t-3", "t-2", "t-1"], (
        f"Reihenfolge: ohne Stempel, dann aeltester, dann neuester: "
        f"{_ids(radar.first_seen, ids)!r}"
    )
    assert _state_path(uid, S1_STATE).read_bytes() == s1_bytes, (
        "Der Radar-Lauf darf die Abweichungs-Stempeldatei nicht veraendern"
    )


# ---------------------------------------------------------------------------
# AC-6 — Ortsvergleich-Radar: dasselbe, derselbe Store.
# ---------------------------------------------------------------------------

PRESET_IDS = ["p-c", "p-a", "p-d", "p-b"]


def test_compare_radar_zwei_laeufe_decken_alle_presets_ab(monkeypatch):
    """AC-6: wie AC-5 fuer Ortsvergleiche (``check_all_compare_presets_run``);
    ``alert_last_checked.json`` (Abweichungslauf, S1) wird weder angelegt
    noch veraendert. RED heute: ``check_all_compare_presets_run`` fehlt."""
    uid = _uid("ac6")
    ids = _make_presets(uid, PRESET_IDS)
    _patch_deadline(monkeypatch, DEADLINE_S)

    radar1 = _ScriptedRadar(_loc_idx, sleep_first_s=SLEEP_S)
    first = _compare_service(uid, radar1).check_all_compare_presets_run()
    run1 = _ids(radar1.first_seen, ids)
    stamped_after_run1 = set(_read_state(uid, COMPARE_STATE))
    radar2 = _ScriptedRadar(_loc_idx, sleep_first_s=SLEEP_S)
    second = _compare_service(uid, radar2).check_all_compare_presets_run()
    run2 = _ids(radar2.first_seen, ids)

    assert first.hit_deadline, f"Lauf 1 muss an der Grenze abbrechen: {first!r}"
    assert 0 < len(run1) < len(ids), run1
    assert run1 == sorted(ids)[: len(run1)], f"Lauf 1 prueft nach ID: {run1!r}"
    not_reached = [p for p in sorted(ids) if p not in run1]
    assert first.skipped_ids == not_reached, (first.skipped_ids, not_reached)
    assert len(first.skipped_ids) == first.skipped == len(not_reached)
    assert stamped_after_run1 == set(run1), (
        "Nur erreichte Ortsvergleiche tragen einen Stempel"
    )
    assert run2[: len(not_reached)] == not_reached, (not_reached, run2)
    assert set(run1) | set(run2) == set(ids), (run1, run2)
    assert len(second.skipped_ids) == second.skipped
    assert not _state_path(uid, S1_STATE).exists(), (
        "Radar-Laeufe duerfen alert_last_checked.json (Abweichungslauf) nicht anlegen"
    )


def test_compare_radar_haelt_sich_an_den_gemeinsamen_store_und_seine_reihenfolge():
    """AC-6 (Teilungs-Invariante): der Ortsvergleich-Radar liest seine Stempel
    ueber DENSELBEN ``AlertCheckStateStore`` (Parameter ``filename``), mit
    derselben Regel — fehlender Stempel = aeltester, danach aufsteigend,
    ID als Tie-Break. Die S1-Datei bleibt byte-identisch.

    RED heute: ``AlertCheckStateStore`` kennt kein ``filename``."""
    from services.alert_check_state import AlertCheckStateStore

    uid = _uid("ac6store")
    ids = _make_presets(uid, ["p-1", "p-2", "p-3", "p-4", "p-5"])
    base = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    AlertCheckStateStore(uid, filename=COMPARE_STATE).record({
        "p-1": base + timedelta(hours=5), "p-2": base - timedelta(hours=5),
        "p-4": base, "p-5": base,
    }, set(ids))
    _write_state(uid, S1_STATE, {"p-1": base - timedelta(days=1)})
    s1_bytes = _state_path(uid, S1_STATE).read_bytes()
    radar = _ScriptedRadar(_loc_idx)

    _compare_service(uid, radar).check_all_compare_presets_run()

    assert _ids(radar.first_seen, ids) == ["p-3", "p-2", "p-4", "p-5", "p-1"], (
        _ids(radar.first_seen, ids)
    )
    assert _state_path(uid, S1_STATE).read_bytes() == s1_bytes


def test_radar_laeufe_legen_die_abweichungsdatei_nicht_an():
    """AC-6: fehlt ``alert_last_checked.json``, bleibt sie nach Trip- UND
    Ortsvergleich-Radar-Lauf abwesend (zweite Variante neben der
    byte-identisch-Pruefung oben)."""
    uid = _uid("ac6none")
    _make_trips(uid, ["t-x"])
    _make_presets(uid, ["p-x"])

    _trip_service(uid, _ScriptedRadar(_trip_idx)).check_radar_alerts_run()
    _compare_service(uid, _ScriptedRadar(_loc_idx)).check_all_compare_presets_run()

    assert _state_path(uid, TRIP_STATE).exists() and _state_path(uid, COMPARE_STATE).exists()
    assert not _state_path(uid, S1_STATE).exists()


# ---------------------------------------------------------------------------
# AC-7 — Rueckgabe, WARNING und Endpunkt-Antworten (echter FastAPI-Router).
# ---------------------------------------------------------------------------

def test_radar_endpunkte_melden_skipped_ids(monkeypatch, caplog):
    """AC-7: Lauf mit Grenzabbruch und Lauf, der alles schafft / Then
    enthalten Rueckgabe, WARNING und Antwort beider Radar-Endpunkte genau
    die nicht erreichten IDs; ``status`` „partial" + ``reason`` „deadline"
    bzw. „ok" mit leerem ``skipped_ids``; ``check_radar_alerts()`` und
    ``check_all_compare_presets()`` liefern weiter ``int``.

    RED heute: die Antworten tragen nur ``status``/``count``."""
    client = TestClient(app)
    _patch_deadline(monkeypatch, DEADLINE_S)

    # --- Trip-Radar-Endpunkt, Grenzabbruch -------------------------------
    uid = _uid("ac7t")
    trip_ids = _make_trips(uid, ["e-a", "e-b", "e-c", "e-d"])
    radar = _ScriptedRadar(_trip_idx, sleep_first_s=SLEEP_S)
    monkeypatch.setattr(TripAlertService, "_get_radar_service", lambda self: radar)
    with caplog.at_level(logging.WARNING):
        data = client.post(f"/api/scheduler/radar-alert-checks?user_id={uid}").json()
    reached = _ids(radar.first_seen, trip_ids)
    expected = [t for t in sorted(trip_ids) if t not in reached]
    assert data.get("status") == "partial" and data.get("reason") == "deadline", data
    assert data.get("skipped_ids") == expected, (data, expected)
    assert data.get("skipped") == len(expected) and data.get("checked") == len(reached), data
    assert "count" in data and "duration_s" in data, data
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(all(t in w for t in expected) for w in warnings), (
        f"WARNING muss die uebersprungenen IDs {expected!r} nennen: {warnings!r}"
    )

    # --- Trip-Radar-Endpunkt, voller Lauf --------------------------------
    uid_ok = _uid("ac7tok")
    _make_trips(uid_ok, ["f-a", "f-b"])
    monkeypatch.setattr(trip_alert, "RADAR_RUN_DEADLINE_SECONDS", 600.0)
    full_radar = _ScriptedRadar(_trip_idx)
    monkeypatch.setattr(TripAlertService, "_get_radar_service", lambda self: full_radar)
    full = client.post(f"/api/scheduler/radar-alert-checks?user_id={uid_ok}").json()
    assert full.get("status") == "ok" and full.get("skipped_ids") == [], full
    assert "reason" not in full, full

    # --- Rueckgabetyp des Alt-Aufrufs bleibt int -------------------------
    count = TripAlertService(
        settings=_make_settings_with_email(), user_id=uid_ok, radar_service=full_radar,
    ).check_radar_alerts()
    assert type(count) is int, type(count)

    # --- Ortsvergleich-Radar-Endpunkt, Grenzabbruch ----------------------
    from services.compare_radar_alert import CompareRadarAlertService

    _patch_deadline(monkeypatch, DEADLINE_S)
    uid_c = _uid("ac7c")
    preset_ids = _make_presets(uid_c, ["g-a", "g-b", "g-c", "g-d"])
    c_radar = _ScriptedRadar(_loc_idx, sleep_first_s=SLEEP_S)
    monkeypatch.setattr(CompareRadarAlertService, "_get_radar_service", lambda self: c_radar)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        cdata = client.post(f"/api/scheduler/compare-radar-alert-checks?user_id={uid_c}").json()
    c_reached = _ids(c_radar.first_seen, preset_ids)
    c_expected = [p for p in sorted(preset_ids) if p not in c_reached]
    assert cdata.get("status") == "partial" and cdata.get("reason") == "deadline", cdata
    assert cdata.get("skipped_ids") == c_expected, (cdata, c_expected)
    assert cdata.get("skipped") == len(c_expected) and cdata.get("checked") == len(c_reached), cdata
    c_warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(all(p in w for p in c_expected) for w in c_warnings), (c_expected, c_warnings)

    # --- Ortsvergleich-Radar, voller Lauf + int --------------------------
    monkeypatch.setattr(trip_alert, "RADAR_RUN_DEADLINE_SECONDS", 600.0)
    uid_cok = _uid("ac7cok")
    _make_presets(uid_cok, ["h-a", "h-b"])
    c_full_radar = _ScriptedRadar(_loc_idx)
    monkeypatch.setattr(CompareRadarAlertService, "_get_radar_service", lambda self: c_full_radar)
    cfull = client.post(f"/api/scheduler/compare-radar-alert-checks?user_id={uid_cok}").json()
    assert cfull.get("status") == "ok" and cfull.get("skipped_ids") == [], cfull
    ccount = CompareRadarAlertService(
        settings=_settings_email_capable_dummy(), user_id=uid_cok, radar_service=c_full_radar,
    ).check_all_compare_presets()
    assert type(ccount) is int, type(ccount)


# ---------------------------------------------------------------------------
# AC-8 — Grenzabbruch mitten in den Messpunkten ist keine Entwarnung und kein
# Ausfall.
# ---------------------------------------------------------------------------

def _alert_log_text(uid: str) -> str:
    path = get_data_dir(uid) / "alert_log.json"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _alert_log_has_entries(uid: str) -> bool:
    text = _alert_log_text(uid)
    if not text:
        return False
    data = json.loads(text)
    return any(data.get(k) for k in ("entries", "not_delivered", "suppressed"))


def test_deadline_abbruch_ist_keine_entwarnung_und_kein_ausfall():
    """AC-8: Given ein Trip, dessen Quellenkette mitten in den Messpunkten der
    Reststrecke (2. Abruf) mit ``RadarDeadlineExceeded`` abbricht, Punkt 1
    liefert NASSE Daten / Then: kein Alarm, kein Alarmprotokoll-Eintrag
    (weder Quellenausfall noch Daten-nicht-verfuegbar), keine Buchung auf
    Sperrzeit/Tageslimit, kein Stempel, Trip in ``skipped_ids``.

    Gegenproben im selben Test:
    * dasselbe Setup OHNE Abbruch alarmiert genau einmal (Mutation
      „Teildaten auswerten" waere sonst unsichtbar);
    * ein Quellenausfall OHNE Grenzabbruch (RuntimeError) bleibt wie bisher
      protokolliert (``data_unavailable``) — Mutation „Deadline wie normaler
      Fehler behandeln" ⇒ Protokolleintrag erscheint ⇒ rot.

    RED heute: ``check_radar_alerts_run`` existiert nicht."""
    # Am Testanfang aufloesen: ein ImportError ist der RED-Grund, nicht still
    # im Stub verschluckt (trip_alert faengt breit).
    from services.radar_service import RadarDeadlineExceeded

    # Voraussetzung: der Trip liefert mindestens ZWEI Messpunkte (sonst gaebe
    # es keinen Zonenpunkt, an dem man „mittendrin" abbrechen kann).
    probe_uid = _uid("ac8probe")
    _make_trips(probe_uid, ["probe"])
    probe_radar = _ScriptedRadar(_trip_idx)
    _trip_service(probe_uid, probe_radar).check_radar_alerts_run()
    assert probe_radar.calls_per_unit.get(0, 0) >= 2, (
        f"Voraussetzung: Trip braucht >= 2 Messpunkte, hatte {probe_radar.calls_per_unit!r}"
    )

    # Gegenprobe A: ohne Abbruch alarmiert der Aufbau genau einmal.
    ok_uid = _uid("ac8ok")
    _make_trips(ok_uid, ["trip-8"])
    ok_mails: list = []
    ok_result = _trip_service(ok_uid, _ScriptedRadar(_trip_idx, wet=True), ok_mails).check_radar_alerts_run()
    assert ok_result.alerts_sent == 1 and len(ok_mails) == 1, (ok_result, ok_mails)

    # Hauptfall: Abbruch am zweiten Abruf.
    uid = _uid("ac8")
    ids = _make_trips(uid, ["trip-8"])
    mails: list = []
    radar = _ScriptedRadar(
        _trip_idx, wet=True, raise_on=(0, 2, RadarDeadlineExceeded("Zeitgrenze")),
    )
    result = _trip_service(uid, radar, mails).check_radar_alerts_run()

    assert radar.calls_per_unit.get(0, 0) >= 2, "Der Abbruch-Abruf muss stattgefunden haben"
    assert result.alerts_sent == 0 and not mails, (
        f"Teildaten duerfen keinen Alarm ausloesen: {result!r}, {mails!r}"
    )
    assert not _alert_log_has_entries(uid), (
        f"Grenzabbruch darf nichts protokollieren: {_alert_log_text(uid)!r}"
    )
    assert ThrottleStore(uid).last_sent("radar", ids[0]) is None, "Sperrzeit wurde gebucht"
    zone = ZoneInfo(str(tz_for_coords(TRIP_LAT0, 9.10)))
    assert alert_daily_limit.load(uid, datetime.now(timezone.utc), zone) == 0, "Tageslimit gebucht"
    assert ids[0] not in _read_state(uid, TRIP_STATE), "Abgebrochener Trip darf keinen Stempel erhalten"
    assert result.skipped_ids == ids, result

    # Gegenprobe B: Quellenausfall OHNE Grenzabbruch bleibt protokolliert.
    uid_fail = _uid("ac8fail")
    _make_trips(uid_fail, ["trip-8"])
    fail_radar = _ScriptedRadar(_trip_idx, raise_on=(0, 1, RuntimeError("503 Quelle")))
    _trip_service(uid_fail, fail_radar).check_radar_alerts_run()
    assert "data_unavailable" in _alert_log_text(uid_fail), (
        "Quellenausfall ohne Grenzabbruch muss wie bisher als data_unavailable "
        f"protokolliert werden: {_alert_log_text(uid_fail)!r}"
    )


# ---------------------------------------------------------------------------
# AC-12 — Mandantentrennung (Pflicht-Zwei-Nutzer-Test).
# ---------------------------------------------------------------------------

def test_radar_zustand_zwei_nutzer_nie_default():
    """AC-12: Given Nutzer A und B mit je eigenen Trips/Ortsvergleichen
    (GLEICHE IDs) / When ein Radar-Lauf fuer A laeuft / Then werden nur A's
    ``alert_last_checked_radar.json`` und ``..._compare_radar.json``
    geschrieben, B's Dateien bleiben byte-identisch bzw. abwesend, unter
    ``data/users/default/`` entsteht nichts. RED heute: ``*_run`` fehlt."""
    user_a, user_b = _uid("ac12a"), _uid("ac12b")
    for u in (user_a, user_b):
        # Trips und Ortsvergleiche teilen sich briefings/<id>.json: je Nutzer
        # verschiedene IDs, dieselben IDs ueber die Nutzer hinweg.
        _make_trips(u, ["gleich-t"])
        _make_presets(u, ["gleich-p"])
    _write_state(user_b, TRIP_STATE, {"gleich-t": datetime(2026, 1, 1, tzinfo=timezone.utc)})
    b_trip_before = _state_path(user_b, TRIP_STATE).read_bytes()
    default_before = {
        f: (_state_path("default", f).read_bytes() if _state_path("default", f).exists() else None)
        for f in (TRIP_STATE, COMPARE_STATE)
    }

    _trip_service(user_a, _ScriptedRadar(_trip_idx)).check_radar_alerts_run()
    _compare_service(user_a, _ScriptedRadar(_loc_idx)).check_all_compare_presets_run()

    assert "gleich-t" in _read_state(user_a, TRIP_STATE), "A's Trip-Radar-Datei fehlt"
    assert "gleich-p" in _read_state(user_a, COMPARE_STATE), "A's Compare-Radar-Datei fehlt"
    assert _state_path(user_b, TRIP_STATE).read_bytes() == b_trip_before, "B's Datei wurde veraendert"
    assert not _state_path(user_b, COMPARE_STATE).exists(), "B bekam eine Compare-Radar-Datei"
    for f, before in default_before.items():
        after = _state_path("default", f).read_bytes() if _state_path("default", f).exists() else None
        assert after == before, f"{f} unter data/users/default/ veraendert — Cross-User-Leck"


# ---------------------------------------------------------------------------
# AC-13 — fail-open: kaputte Zustandsdatei bzw. nicht erhaeltlicher Lock.
# ---------------------------------------------------------------------------

def _warning_nennt(caplog, filename: str) -> bool:
    return any(
        r.levelno >= logging.WARNING and filename in r.getMessage() for r in caplog.records
    )


def test_radar_zustand_fail_open(monkeypatch, caplog):
    """AC-13 (Trip): (1) ungueltiges JSON, (2) extern gehaltener Lock ⇒ alle
    Trips normal geprueft und Alarme versendet, Reihenfolge faellt auf ID
    zurueck, WARNING nennt ``alert_last_checked_radar.json`` (faengt eine
    Implementierung, die den hartkodierten S1-Namen loggt), keine Exception.

    RED heute: ``check_radar_alerts_run`` fehlt."""
    import services.alert_check_state as state_mod

    monkeypatch.setattr(state_mod, "LOCK_TIMEOUT_SECONDS", 0.1, raising=False)
    # (1) kaputte Datei
    uid = _uid("ac13a")
    ids = _make_trips(uid, ["k-3", "k-1", "k-2"])
    path = _state_path(uid, TRIP_STATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{kaputt", encoding="utf-8")
    radar = _ScriptedRadar(_trip_idx, wet=True)
    mails: list = []

    with caplog.at_level(logging.WARNING):
        result = _trip_service(uid, radar, mails).check_radar_alerts_run()

    assert _ids(radar.first_seen, ids) == ["k-1", "k-2", "k-3"], (
        f"Fallback-Reihenfolge nach ID: {_ids(radar.first_seen, ids)!r}"
    )
    assert result.alerts_sent == 3 and len(mails) == 3, (result, len(mails))
    assert _warning_nennt(caplog, TRIP_STATE), [r.getMessage() for r in caplog.records]

    # (2) Lock extern gehalten
    caplog.clear()
    uid2 = _uid("ac13b")
    _make_trips(uid2, ["l-1", "l-2"])
    lock_path = str(_state_path(uid2, TRIP_STATE)) + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    mails2: list = []
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with caplog.at_level(logging.WARNING):
            result2 = _trip_service(uid2, _ScriptedRadar(_trip_idx, wet=True), mails2).check_radar_alerts_run()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    assert result2.alerts_sent == 2 and len(mails2) == 2, (result2, len(mails2))
    assert _warning_nennt(caplog, TRIP_STATE), [r.getMessage() for r in caplog.records]


def test_compare_radar_zustand_fail_open(monkeypatch, caplog):
    """AC-13 (Ortsvergleich): kaputte Zustandsdatei ⇒ alle Ortsvergleiche
    geprueft und gemeldet (je Preset eine Mail), Reihenfolge nach ID, WARNING
    nennt ``alert_last_checked_compare_radar.json``."""
    uid = _uid("ac13c")
    ids = _make_presets(uid, ["q-3", "q-1", "q-2"])
    path = _state_path(uid, COMPARE_STATE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{kaputt", encoding="utf-8")
    radar = _ScriptedRadar(_loc_idx, wet=True)
    mails: list = []

    with caplog.at_level(logging.WARNING):
        result = _compare_service(uid, radar, mails).check_all_compare_presets_run()

    assert _ids(radar.first_seen, ids) == ["q-1", "q-2", "q-3"], _ids(radar.first_seen, ids)
    assert result.alerts_sent == 3 and len(mails) == 3, (result, len(mails))
    assert _warning_nennt(caplog, COMPARE_STATE), [r.getMessage() for r in caplog.records]


# ---------------------------------------------------------------------------
# Fix-Loop 1 (Adversary F001-F004): die Zeitgrenze WIRKT an der Stelle, an der
# der Alarmlauf `get_nowcast` ruft. Echte `RadarNowcastService`, nur die
# Quellenschritte (Netz-Grenze) schlafen real und zaehlen — der Fake wertet
# `deadline_at` NICHT selbst aus, die echte Kette tut es.
# ---------------------------------------------------------------------------

from tests.tdd.test_radar_alarmlauf_zeitgrenze import (  # noqa: E402
    _erwartete_kettenfolge,
    _service_mit_zeitverbrauchenden_quellen,
)

STEP_S = 0.3


def _make_multi_preset(uid: str, preset_id: str, n_locs: int) -> str:
    """Ein Ortsvergleich mit ``n_locs`` Orten (Breite 46.0 + 0.3*j)."""
    _premium(uid)
    loc_ids = []
    for j in range(n_locs):
        loc_id = f"loc-{preset_id}-{j}"
        save_location(
            SavedLocation(
                id=loc_id, name=f"Ort {preset_id}-{j}", lat=LOC_LAT0 + j * LOC_STEP,
                lon=LOC_LON, elevation_m=1000,
            ),
            user_id=uid,
        )
        loc_ids.append(loc_id)
    write_compare_briefings(
        _data_root_users() / uid, [_radar_preset(preset_id, loc_ids, ["gregor-test@henemm.com"])],
    )
    return preset_id


def _kette(lat: float, lon: float) -> int:
    return len(_erwartete_kettenfolge(lat, lon))


def test_trip_radar_grenze_wirkt_im_ersten_abruf(monkeypatch, caplog):
    """F001/F004: Grenze laeuft MITTEN im ersten Abruf des Trips ab. Die echte
    Kette bricht vor der 2. Quelle ab (genau 1 Quellenschritt), der Trip ist
    nicht erreicht (kein Stempel, in skipped_ids), Endpunkt ``partial``/
    ``deadline`` + WARNING, kein Quellenausfall-Protokoll.

    Mutationen: ``deadline_at`` am ersten Abruf nicht durchreichen ⇒ ganze
    Kette laeuft (calls > 1); Handler entfernen ⇒ data_unavailable-Eintrag;
    ``hit_deadline`` nicht setzen ⇒ Endpunkt „ok"."""
    uid = _uid("f4a")
    ids = _make_trips(uid, ["z-1"])
    svc, _cache, calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=0.6)
    assert _kette(TRIP_LAT0, 9.10) >= 2
    _patch_deadline(monkeypatch, 0.3)
    monkeypatch.setattr(TripAlertService, "_get_radar_service", lambda self: svc)

    with caplog.at_level(logging.WARNING):
        data = TestClient(app).post(f"/api/scheduler/radar-alert-checks?user_id={uid}").json()

    assert len(calls) == 1, f"Nach Ablauf der Grenze darf keine 2. Quelle beginnen: {calls!r}"
    assert data.get("status") == "partial" and data.get("reason") == "deadline", data
    assert data.get("skipped_ids") == ids and data.get("checked") == 0, data
    assert ids[0] not in _read_state(uid, TRIP_STATE)
    assert not _alert_log_has_entries(uid), _alert_log_text(uid)
    assert any(
        ids[0] in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ), [r.getMessage() for r in caplog.records]
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR], (
        "Grenzabbruch ist kein Quellenausfall: kein ERROR-Log "
        f"({[r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]!r})"
    )


def test_trip_radar_grenze_wirkt_am_zonenpunkt(monkeypatch):
    """F001: Der erste Abruf laeuft komplett durch (alle k Quellen), die Grenze
    ist danach abgelaufen — der Zonenpunkt-Abruf beginnt KEINE Quelle.
    Mutation: ``deadline_at`` am Zonenpunkt nicht durchreichen ⇒ 2k Aufrufe."""
    uid = _uid("f1z")
    ids = _make_trips(uid, ["z-1"])
    k = _kette(TRIP_LAT0, 9.10)
    svc, _cache, calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=STEP_S)
    _patch_deadline(monkeypatch, STEP_S * (k - 0.5))

    result = _trip_service(uid, _ScriptedRadarEcht(svc)).check_radar_alerts_run()

    assert len(calls) == k, f"Nur der erste Abruf darf Quellen beginnen ({k}), war {calls!r}"
    assert result.hit_deadline and result.skipped_ids == ids and result.checked == 0, result
    assert ids[0] not in _read_state(uid, TRIP_STATE)
    assert not _alert_log_has_entries(uid), _alert_log_text(uid)


class _ScriptedRadarEcht:
    """Reicht Aufrufe unveraendert an die echte Instanz weiter (Signatur mit
    ``deadline_at``); wertet die Grenze bewusst NICHT selbst aus."""

    def __init__(self, svc) -> None:
        self._svc = svc

    def get_nowcast(self, *args, **kwargs):
        return self._svc.get_nowcast(*args, **kwargs)


def _ausfall_am_kettenende(svc, sleep_s: float) -> None:
    """Letzte Quelle schlaeft und wirft (503) ⇒ Quellenausfall des Orts."""
    def _step(lat, lon, elevation_m=None):
        time.sleep(sleep_s)
        raise RuntimeError("503 Quelle")
    svc._fetch_openmeteo_minutely15 = _step


def test_compare_radar_grenze_mitten_im_ortsvergleich(monkeypatch):
    """F001/F002/F003: Preset mit 2 Orten, Ort 1 laeuft durch und endet in
    einem Quellenausfall, die Grenze ist danach abgelaufen, Ort 2 beginnt keine
    Quelle (echte Kette wertet ``deadline_at`` aus). Das Preset ist nicht
    erreicht: kein Stempel, in skipped_ids, ``checked`` nicht hochgezaehlt,
    ``hit_deadline``, keine Mail und KEIN alert_log-Eintrag — auch nicht der
    Quellenausfall von Ort 1 (F003).

    Gegenprobe: ohne Grenzabbruch wird derselbe Ausfall protokolliert.
    Mutationen: ``raise`` entfernen, Handler entfernen, Stempel behalten,
    ``checked`` nicht dekrementieren, ``hit_deadline`` nicht setzen,
    ``deadline_at`` nicht durchreichen, Ausfall sofort protokollieren."""
    # Gegenprobe (Praemisse): ohne Abbruch steht der Ausfall im Protokoll.
    uid_ok = _uid("f3ok")
    _make_multi_preset(uid_ok, "mp", 2)
    svc_ok, _c, _calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=0.0)
    _ausfall_am_kettenende(svc_ok, 0.0)
    _patch_deadline(monkeypatch, 600.0)
    ok = _compare_service(uid_ok, _ScriptedRadarEcht(svc_ok)).check_all_compare_presets_run()
    assert not ok.hit_deadline and ok.checked == 1, ok
    assert "data_unavailable" in _alert_log_text(uid_ok), "Praemisse: Ausfall wird protokolliert"

    uid = _uid("f3")
    preset = _make_multi_preset(uid, "mp", 2)
    k1 = _kette(LOC_LAT0, LOC_LON)
    svc, _cache, calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=STEP_S)
    _ausfall_am_kettenende(svc, STEP_S)
    _patch_deadline(monkeypatch, STEP_S * (k1 - 0.5))
    mails: list = []

    result = _compare_service(uid, _ScriptedRadarEcht(svc), mails).check_all_compare_presets_run()

    assert len(calls) == k1 - 1, f"Nur Ort 1 darf Quellen beginnen ({k1}), war {calls!r}"
    assert result.hit_deadline and result.checked == 0, result
    assert result.skipped_ids == [preset] and result.skipped == 1, result
    assert result.alerts_sent == 0 and not mails
    assert preset not in _read_state(uid, COMPARE_STATE), "Abgebrochenes Preset gestempelt"
    assert not _alert_log_has_entries(uid), (
        f"Grenzabbruch darf auch den Ausfall von Ort 1 nicht protokollieren: {_alert_log_text(uid)!r}"
    )


def test_compare_radar_endpunkt_meldet_abbruch_mitten_im_preset(monkeypatch, caplog):
    """F002: Endpunkt ``partial``/``deadline`` + WARNING mit der Preset-ID, wenn
    die Grenze mitten im Ortsvergleich (Ort 2) greift. Mutation:
    ``hit_deadline`` bei Abbruch nicht setzen ⇒ status „ok"."""
    from services.compare_radar_alert import CompareRadarAlertService

    uid = _uid("f2ep")
    preset = _make_multi_preset(uid, "mp", 2)
    k1 = _kette(LOC_LAT0, LOC_LON)
    svc, _cache, _calls = _service_mit_zeitverbrauchenden_quellen(monkeypatch, sleep_s=STEP_S)
    _patch_deadline(monkeypatch, STEP_S * (k1 - 0.5))
    monkeypatch.setattr(
        CompareRadarAlertService, "_get_radar_service", lambda self: _ScriptedRadarEcht(svc),
    )
    with caplog.at_level(logging.WARNING):
        data = TestClient(app).post(
            f"/api/scheduler/compare-radar-alert-checks?user_id={uid}"
        ).json()
    assert data.get("status") == "partial" and data.get("reason") == "deadline", data
    assert data.get("skipped_ids") == [preset] and data.get("checked") == 0, data
    assert any(
        preset in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING
    ), [r.getMessage() for r in caplog.records]


# ---------------------------------------------------------------------------
# Fix-Loop 2 (Adversary F008/F009): gesammelte Quellenausfaelle gehen ausser
# bei einem Grenzabbruch nie verloren.
# ---------------------------------------------------------------------------

def test_compare_radar_ausfall_ort1_und_alarm_ort2_beides_wirksam():
    """F008: Preset mit 2 Orten, Ort 1 Quellenausfall, Ort 2 loest aus ⇒ der
    Alarm geht raus UND der Ausfall von Ort 1 steht im Protokoll.
    Mutation „Ausfaelle nur protokollieren, wenn nichts ausloest" ⇒ rot."""
    uid = _uid("f8")
    _make_multi_preset(uid, "mp", 2)
    mails: list = []
    radar = _ScriptedRadar(_loc_idx, wet=True, raise_on=(0, 1, RuntimeError("503 Quelle")))

    result = _compare_service(uid, radar, mails).check_all_compare_presets_run()

    assert result.alerts_sent == 1 and len(mails) == 1, (result, len(mails))
    assert "data_unavailable" in _alert_log_text(uid), (
        f"Ausfall von Ort 1 fehlt im Protokoll: {_alert_log_text(uid)!r}"
    )


def test_compare_radar_ausfall_ort1_bleibt_bei_unerwartetem_fehler_an_ort2():
    """F009: Ort 1 Quellenausfall, danach wirft die Auswertung von Ort 2 eine
    unerwartete Exception (Dienst liefert ein unbrauchbares Ergebnis) ⇒ die
    Exception erreicht den Aufrufer wie bisher, der Ausfall von Ort 1 steht
    trotzdem im Protokoll (nur ein Grenzabbruch verwirft ihn).
    Mutation „Protokollierung nur am Normalende (kein finally)" ⇒ rot."""
    class _KaputtBeiOrt2(_ScriptedRadar):
        def get_nowcast(self, lat, lon, *a, **kw):
            if _loc_idx(lat) == 1:
                return object()  # AttributeError bei der Auswertung
            return super().get_nowcast(lat, lon, *a, **kw)

    uid = _uid("f9")
    _make_multi_preset(uid, "mp", 2)
    radar = _KaputtBeiOrt2(_loc_idx, raise_on=(0, 1, RuntimeError("503 Quelle")))

    with pytest.raises(AttributeError):
        _compare_service(uid, radar).check_all_compare_presets_run()

    assert "data_unavailable" in _alert_log_text(uid), (
        f"Ausfall von Ort 1 ging verloren: {_alert_log_text(uid)!r}"
    )
