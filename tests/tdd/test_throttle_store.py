"""TDD RED — Issue #1213: Gemeinsamer Cooldown-Speicher (`ThrottleStore`).

SPEC: docs/specs/modules/throttle_store.md

Ersetzt sechs parallel implementierte Cooldown-Prüfungen und drei-plus
getrennte State-Dateien durch EINE `ThrottleStore`-Klasse mit EINEM
State-File pro Nutzer (``throttle_state.json``). Behebt vier latente Bugs:
stiller Totalausfall bei defektem Trip-Eintrag, gegenteilige `null`-Cooldown-
Semantik zwischen Trip- und Compare-Pfad, Lost-Update zwischen API-Prozess
und Scheduler, fehlende Tageslimit-Prüfung im Compare-Pfad.

KEINE Mocks — echte Dateien unter ``tmp_path`` (Store-Unit-Tests, expliziter
``data_dir``-Konstruktor-Override) bzw. unter dem autouse-isolierten
``_DATA_ROOT`` (Aufrufer-Tests via `TripAlertService`/`CompareAlertService`,
Issue #1133 — ``tests/conftest.py::_isolate_data_root``). `now` ist überall
ein expliziter aware-UTC-Parameter, nie `datetime.now()` für Zeitvergleiche.

RED-Ursache (heute, vor der Implementierung):
- `src/services/throttle_store.py` existiert noch nicht → ImportError für
  alle Store-Unit-Tests (1-4, 7, 11, 12).
- `TripAlertService`/`CompareAlertService` kennen den Store noch nicht, lesen
  weiterhin aus ihren eigenen In-Memory-Dicts/Dateien und prüfen im
  Compare-Pfad kein Tageslimit → die Aufrufer-Tests (5, 6, 8, 10) schlagen
  fehl, weil das beobachtete Verhalten NICHT dem Ziel-Design entspricht
  (kein Drosseln bei `None`-Cooldown im Compare-Pfad, kein Tageslimit-Gate,
  `get_time_until_next_alert` kennt noch keinen per-Trip-Cooldown).
- `alert_daily_limit.increment()` schreibt weiterhin über eine hartkodierte
  ``data/users/<uid>/...``-Konstruktion statt über `get_data_dir()` und nicht
  atomar (kein tmp+`os.replace`) → Test 9 schlägt fehl (Verzeichnis unter dem
  isolierten `_DATA_ROOT` existiert gar nicht).
- `TripAlertService._is_throttled` (toter Code) existiert noch → Test 13
  (Regressionsschutz) schlägt jetzt bewusst fehl und wird erst nach dem
  GREEN-Umbau grün.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "users"


# ═══════════════════════════ Gemeinsame Helper ═══════════════════════════════

def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _clean_user(uid: str) -> None:
    """Nur für die Aufrufer-Tests nötig — dort schreiben `compare_alert.py`/
    `alert_state.py`/Presets weiterhin in den echten Baum (hartkodierte
    ``data/users/...``-Pfade, siehe Kontext-Dokument). Store-Unit-Tests
    brauchen dies NICHT (arbeiten unter `tmp_path`)."""
    d = DATA_ROOT / uid
    if d.exists():
        shutil.rmtree(d)


def _location(loc_id: str, name: str, lat: float, lon: float, elevation_m: int = 1000):
    from app.user import SavedLocation
    return SavedLocation(id=loc_id, name=name, lat=lat, lon=lon, elevation_m=elevation_m)


def _point(point_id: str, name: str, lat: float, lon: float, precip_sum_mm: float = 0.0):
    from app.models import SegmentWeatherSummary
    from services.point_weather import PointWeatherData

    return PointWeatherData(
        id=point_id, name=name, lat=lat, lon=lon, timeseries=None,
        aggregated=SegmentWeatherSummary(precip_sum_mm=precip_sum_mm),
        fetched_at=datetime.now(timezone.utc), provider="test-scripted",
    )


class _ScriptedWeatherSource:
    """Deterministischer `LocationWeatherSource`-Impl (Protocol, kein Mock) —
    Vorbild `test_issue_1169_compare_alert_consumer.py::_ScriptedWeatherSource`."""

    def __init__(self, values: dict[str, float]) -> None:
        self._values = dict(values)

    def fetch(self, point_id: str, lat: float, lon: float):
        return _point(point_id, point_id, lat, lon, precip_sum_mm=self._values.get(point_id, 0.0))


def _settings_email_capable_dummy():
    from app.config import Settings
    return Settings(
        smtp_host="dummy.invalid", smtp_user="dummy", smtp_pass="dummy",
        mail_to="dummy@example.com",
    )


def _write_preset_file(user_id: str, presets: list[dict]) -> Path:
    path = DATA_ROOT / user_id / "compare_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(presets, ensure_ascii=False), encoding="utf-8")
    return path


def _make_trip(trip_id: str, alert_cooldown_minutes: int | None):
    from app.trip import Stage, Trip, Waypoint

    wp = Waypoint(id="wp-1", name="Start", lat=42.0, lon=9.0, elevation_m=500)
    stage = Stage(id="s-1", name="Etappe 1", date="2026-06-15", waypoints=[wp])
    trip = Trip(id=trip_id, name="Throttle-Store-Test-Trip", stages=[stage])
    trip.alert_cooldown_minutes = alert_cooldown_minutes
    return trip


# ═══════════════════════ AC-1: Migration aller drei Altquellen ══════════════

def test_migration_pulls_all_three_legacy_sources(tmp_path):
    """AC-1: Fixture mit drei präparierten Altdateien; nach dem ersten
    `ThrottleStore`-Zugriff liefert `last_sent()` alle drei migrierten
    Scopes, `throttle_state.json` existiert, und ein anschließendes
    `record()` ändert NUR diese Datei (Altdateien bleiben unangetastet)."""
    user_dir = tmp_path / "u1"
    user_dir.mkdir()
    trip_id = "trip-a"

    t_trip = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    t_compare = datetime(2026, 7, 2, 11, 0, tzinfo=timezone.utc)
    t_radar = datetime(2026, 7, 3, 12, 0, tzinfo=timezone.utc)

    _write_json(user_dir / "alert_throttle.json", {trip_id: t_trip.isoformat()})
    _write_json(user_dir / "compare_alert_throttle.json", {"preset-a": t_compare.isoformat()})
    _write_json(user_dir / "alert_state" / f"{trip_id}.json", {
        "radar_throttle": {"reported_at": t_radar.isoformat()},
    })

    from services.throttle_store import ThrottleStore

    store = ThrottleStore("u1", data_dir=user_dir)

    assert store.last_sent("trip", trip_id) == t_trip, "AC-1: Trip-Scope nicht migriert"
    assert store.last_sent("compare_preset", "preset-a") == t_compare, (
        "AC-1: Compare-Scope nicht migriert"
    )
    assert store.last_sent("radar", trip_id) == t_radar, "AC-1: Radar-Scope nicht migriert"

    state_path = user_dir / "throttle_state.json"
    assert state_path.exists(), "AC-1: throttle_state.json wurde nach Migration nicht angelegt"

    before_alert_throttle = (user_dir / "alert_throttle.json").read_text()
    before_compare = (user_dir / "compare_alert_throttle.json").read_text()
    before_alert_state = (user_dir / "alert_state" / f"{trip_id}.json").read_text()

    store.record("trip", trip_id, datetime(2026, 7, 5, tzinfo=timezone.utc))

    assert (user_dir / "alert_throttle.json").read_text() == before_alert_throttle, (
        "AC-1: alert_throttle.json wurde nach der Migration noch beschrieben"
    )
    assert (user_dir / "compare_alert_throttle.json").read_text() == before_compare, (
        "AC-1: compare_alert_throttle.json wurde nach der Migration noch beschrieben"
    )
    assert (user_dir / "alert_state" / f"{trip_id}.json").read_text() == before_alert_state, (
        "AC-1: alert_state/<trip_id>.json wurde nach der Migration noch beschrieben"
    )


def test_migration_is_idempotent_on_second_load(tmp_path):
    """AC-1 (Regel-Budget): ein zweiter Load darf einen bereits migrierten und
    per `record()` aktualisierten Wert NICHT durch die (inzwischen geänderte)
    Legacy-Quelle überschreiben."""
    user_dir = tmp_path / "u2"
    user_dir.mkdir()
    trip_id = "trip-a"
    t_trip = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    _write_json(user_dir / "alert_throttle.json", {trip_id: t_trip.isoformat()})

    from services.throttle_store import ThrottleStore

    store1 = ThrottleStore("u2", data_dir=user_dir)
    assert store1.last_sent("trip", trip_id) == t_trip

    updated = datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)
    store1.record("trip", trip_id, updated)

    # Legacy-Quelle nachträglich ändern — ein erneuter Migrationslauf darf
    # diesen (jetzt veralteten) Wert NICHT mehr ziehen.
    _write_json(user_dir / "alert_throttle.json", {
        trip_id: datetime(2099, 1, 1, tzinfo=timezone.utc).isoformat()
    })

    store2 = ThrottleStore("u2", data_dir=user_dir)
    assert store2.last_sent("trip", trip_id) == updated, (
        "AC-1: Zweiter Load hat den bereits migrierten/record()-aktualisierten Wert "
        "durch die geänderte Legacy-Quelle überschrieben — Migration ist nicht idempotent"
    )


# ═══════════════════ AC-2/AC-3: Per-Eintrag-Toleranz bei Korruption ══════════

def test_corrupt_trip_entry_isolates_single_trip(tmp_path):
    """AC-2: ein korrupter Trip-Eintrag darf NUR sich selbst betreffen — der
    gültige Nachbar-Trip bleibt normal drosselbar, kein globaler Ausfall."""
    user_dir = tmp_path / "u3"
    user_dir.mkdir()
    good_ts = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    _write_json(user_dir / "alert_throttle.json", {
        "trip-good": good_ts.isoformat(),
        "trip-bad": "not-a-timestamp",
    })

    from services.throttle_store import ThrottleStore

    store = ThrottleStore("u3", data_dir=user_dir)  # darf nicht crashen

    now = good_ts + timedelta(minutes=30)
    assert store.is_throttled("trip", "trip-good", 60, now) is True, (
        "AC-2: gültiger Trip muss trotz korruptem Nachbar-Eintrag weiterhin "
        "korrekt gedrosselt sein"
    )
    assert store.is_throttled("trip", "trip-bad", 60, now) is False, (
        "AC-2: korrupter Eintrag darf nur sich selbst betreffen (kein Crash, "
        "kein gedrosselter Zustand ohne gültigen Timestamp)"
    )


def test_corrupt_compare_entry_isolates_single_preset(tmp_path):
    """AC-3: analog AC-2, aber für den Compare-Pfad — ein korruptes Preset
    darf nicht alle anderen Presets ausfallen lassen."""
    user_dir = tmp_path / "u4"
    user_dir.mkdir()
    good_ts = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    _write_json(user_dir / "compare_alert_throttle.json", {
        "preset-good": good_ts.isoformat(),
        "preset-bad": "not-a-timestamp",
    })

    from services.throttle_store import ThrottleStore

    store = ThrottleStore("u4", data_dir=user_dir)  # darf nicht crashen

    now = good_ts + timedelta(minutes=30)
    assert store.is_throttled("compare_preset", "preset-good", 60, now) is True, (
        "AC-3: gültiges Preset muss trotz korruptem Nachbar-Eintrag weiterhin "
        "korrekt gedrosselt sein"
    )
    assert store.is_throttled("compare_preset", "preset-bad", 60, now) is False, (
        "AC-3: korrupter Preset-Eintrag darf nur sich selbst betreffen, nicht "
        "alle Presets ausfallen lassen (heutiger Bug: EIN kaputter Eintrag "
        "reisst ALLE Presets mit)"
    )


# ═══════════════════════ AC-4: null-Cooldown-Symmetrie ═══════════════════════

def test_null_cooldown_resolves_to_default_trip_path():
    """AC-4 (Trip-Pfad): `alert_cooldown_minutes=None` muss auf den globalen
    Default (`throttle_hours * 60`) auflösen — 5 Min nach `record()` muss der
    Trip innerhalb des 120-Min-Default-Fensters gedrosselt sein.

    Nutzt den echten `TripAlertService` (isolierter `_DATA_ROOT`, Issue #1133)
    — Vorseeding über einen eigenen `ThrottleStore(uid)` ohne `data_dir`-
    Override, der denselben isolierten `get_data_dir(uid)`-Pfad auflöst wie
    der Store, den der Service intern verwendet.
    """
    from app.config import Settings
    from services.throttle_store import ThrottleStore
    from services.trip_alert import TripAlertService

    uid = f"tdd-throttle-trip-null-{uuid.uuid4().hex[:6]}"
    trip_id = f"trip-{uuid.uuid4().hex[:6]}"
    trip = _make_trip(trip_id, alert_cooldown_minutes=None)

    recorded_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    ThrottleStore(uid).record("trip", trip_id, recorded_at)

    svc = TripAlertService(settings=Settings(), throttle_hours=2, user_id=uid)
    assert svc._is_throttled_with_cooldown(trip) is True, (
        "AC-4: alert_cooldown_minutes=None muss auf den globalen Trip-Default "
        "(throttle_hours*60 = 120 Min) auflösen — 5 Min nach record() muss der "
        "Trip innerhalb dieses Fensters gedrosselt sein"
    )


def test_null_cooldown_resolves_to_default_compare_path():
    """AC-4 (Compare-Pfad): identisches Verhalten wie der Trip-Pfad —
    `alert_cooldown_minutes=None` im Preset darf NICHT (wie heute) 1:1 an
    `is_cooldown_active` durchgereicht werden (dort ist `None` "kein Limit"),
    sondern muss vor dem Store-Aufruf auf den Default (120 Min) auflösen."""
    from app.loader import save_location
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService
    from services.throttle_store import ThrottleStore

    uid = f"tdd-throttle-compare-null-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        loc = _location("loc-x", "Vergleichsort", 47.0, 11.0)
        save_location(loc, user_id=uid)
        preset = {
            "id": preset_id, "name": preset_id, "user_id": uid,
            "location_ids": ["loc-x"], "empfaenger": ["gregor-test@henemm.com"],
            "alert_cooldown_minutes": None,
        }
        _write_preset_file(uid, [preset])

        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-x", _point("loc-x", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        recorded_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        ThrottleStore(uid).record("compare_preset", preset_id, recorded_at)

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _ScriptedWeatherSource({"loc-x": 18.0})  # Δ=16 >= Schwelle 10 -> waere fällig

        svc = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = svc.check_all_compare_presets()

        assert sent == 0, (
            "AC-4: alert_cooldown_minutes=None im Compare-Preset muss auf den "
            "Default (120 Min, identisch zum Trip-Pfad) auflösen — 5 Min nach "
            "record() muss der Cooldown noch aktiv sein und den Versand "
            "unterdrücken (heutiger Bug: None -> kein Limit -> Versand erfolgt)"
        )
        assert sent_subjects == [], "AC-4: mail_sink wurde trotz aktivem Cooldown aufgerufen"
    finally:
        _clean_user(uid)


# ═══════════════════════════ AC-5: Lost-Update-Schutz ════════════════════════

def test_concurrent_record_no_lost_update(tmp_path):
    """AC-5: N Threads (echte Nebenläufigkeit via `threading.Barrier`, jeder
    mit einer eigenen `ThrottleStore`-Instanz auf demselben `user_id`/
    `data_dir` — simuliert API-Prozess + Scheduler mit eigenem
    In-Memory-Zustand) schreiben gleichzeitig je einen anderen `scope/key`;
    eine frische Instanz nach dem Join muss ALLE Einträge sehen (kein Lost
    Update durch eine ungeschützte load-mutate-write-Sequenz)."""
    import threading

    user_dir = tmp_path / "u-concurrent"
    user_dir.mkdir()

    from services.throttle_store import ThrottleStore

    worker_count = 20
    barrier = threading.Barrier(worker_count)
    errors: list[BaseException] = []

    def _worker(i: int) -> None:
        store = ThrottleStore("u-concurrent", data_dir=user_dir)
        now = datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=i)
        try:
            barrier.wait()  # alle Threads starten den Write im selben Zeitfenster
            store.record("trip", f"trip-{i}", now)
        except BaseException as exc:  # pragma: no cover - defensive
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(worker_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"AC-5: Worker-Fehler waehrend nebenlaeufigem record(): {errors}"

    fresh = ThrottleStore("u-concurrent", data_dir=user_dir)
    missing = [
        i for i in range(worker_count)
        if fresh.last_sent("trip", f"trip-{i}") is None
    ]
    assert not missing, (
        f"AC-5: {len(missing)}/{worker_count} Einträge nach nebenläufigem "
        f"record() verloren gegangen (Lost Update durch ungeschützte "
        f"load-mutate-write-Sequenz ohne Lock): fehlende Indizes {missing}"
    )


# ═══════════════════ AC-6: Compare-Tageslimit-Anbindung ══════════════════════

def test_compare_alert_blocked_by_daily_limit():
    """AC-6: Compare-Preset unterhalb des Cooldowns, aber Free-Tageslimit (2)
    bereits erreicht -> Versand wird unterdrückt (analog zum bestehenden
    Trip-Verhalten, Issue #1070).

    `user.json` (Tier) bleibt hartkodiert im echten Baum (nicht Teil dieses
    Issues, `services/user_tier.py`), `alert_daily_count.json` liegt unter dem
    isolierten `get_data_dir(uid)` (Issue #1213 migriert `alert_daily_limit.py`
    darauf)."""
    from app.loader import get_data_dir, save_location
    from services.compare_alert import CompareAlertService
    from services.compare_weather_snapshot import CompareWeatherSnapshotService

    uid = f"tdd-throttle-compare-daily-{uuid.uuid4().hex[:6]}"
    preset_id = f"cp-{uuid.uuid4().hex[:6]}"
    _clean_user(uid)
    try:
        (DATA_ROOT / uid).mkdir(parents=True, exist_ok=True)
        (DATA_ROOT / uid / "user.json").write_text(json.dumps({"id": uid, "tier": "free"}))

        counter_dir = get_data_dir(uid)
        counter_dir.mkdir(parents=True, exist_ok=True)
        today_vienna = datetime.now(timezone.utc).astimezone(ZoneInfo("Europe/Vienna")).date().isoformat()
        (counter_dir / "alert_daily_count.json").write_text(
            json.dumps({"date": today_vienna, "count": 2})
        )

        loc = _location("loc-y", "Tageslimit-Ort", 47.1, 11.1)
        save_location(loc, user_id=uid)
        preset = {
            "id": preset_id, "name": preset_id, "user_id": uid,
            "location_ids": ["loc-y"], "empfaenger": ["gregor-test@henemm.com"],
            "alert_cooldown_minutes": 0,
        }
        _write_preset_file(uid, [preset])
        CompareWeatherSnapshotService(user_id=uid).save(
            preset_id, "loc-y", _point("loc-y", loc.name, loc.lat, loc.lon, precip_sum_mm=2.0)
        )

        settings = _settings_email_capable_dummy()
        sent_subjects: list[str] = []
        ws = _ScriptedWeatherSource({"loc-y": 18.0})  # Δ=16 >= Schwelle 10 -> waere fällig

        svc = CompareAlertService(
            settings=settings, user_id=uid, weather_source=ws,
            mail_sink=lambda subject, body: sent_subjects.append(subject),
        )
        sent = svc.check_all_compare_presets()

        assert sent == 0, (
            "AC-6: Free-Tageslimit (2) bereits erreicht — Compare-Alert-Versand "
            "muss trotz unproblematischem Cooldown unterdrückt werden"
        )
        assert sent_subjects == [], "AC-6: mail_sink wurde trotz ausgeschöpftem Tageslimit aufgerufen"
    finally:
        _clean_user(uid)


# ═══════════════ Atomarer increment()-Write (tmp + os.replace) ══════════════

def test_daily_limit_increment_is_atomic():
    """`alert_daily_limit.increment()` muss über `get_data_dir()` (isolierter
    `_DATA_ROOT`) auflösen und atomar schreiben (tmp-Datei + `os.replace`,
    kein liegen gebliebener `.tmp`-Rest, korrekter Endzustand nach zwei
    Increments)."""
    from app.loader import get_data_dir
    from services import alert_daily_limit

    uid = f"tdd-throttle-atomic-{uuid.uuid4().hex[:6]}"
    now = datetime(2026, 7, 7, 10, 0, tzinfo=timezone.utc)

    alert_daily_limit.increment(uid, now)
    alert_daily_limit.increment(uid, now)

    counter_dir = get_data_dir(uid)
    assert counter_dir.exists(), (
        "increment() hat nicht unter get_data_dir(uid) geschrieben — noch die "
        "hartkodierte data/users/...-Konstruktion statt der isolierten Auflösung"
    )
    names = sorted(p.name for p in counter_dir.iterdir())
    assert "alert_daily_count.json" in names, f"alert_daily_count.json fehlt, gefunden: {names}"
    assert not any(n.endswith(".tmp") or n.startswith("tmp") for n in names), (
        f"Temporärer Schreib-Rest gefunden (kein atomarer tmp+os.replace-Write): {names}"
    )

    data = json.loads((counter_dir / "alert_daily_count.json").read_text())
    assert data["count"] == 2, f"Zähler nach 2 Increments unerwartet: {data}"


# ═══════════════ AC-7: get_time_until_next_alert per-Trip-Cooldown ══════════

def test_get_time_until_next_alert_uses_per_trip_cooldown():
    """AC-7: Trip mit per-Trip-`alert_cooldown_minutes` (30) ungleich der
    globalen `throttle_hours`-Einstellung (5h = 300 Min) — die Restzeit muss
    auf dem per-Trip-Wert basieren, nicht auf der globalen Einstellung.

    Design-Annahme (nicht wörtlich in der Spec fixiert): `get_time_until_next_alert`
    wechselt analog zu `_is_throttled_with_cooldown`/`_is_quiet_hours` von
    `trip_id: str` auf ein `trip`-Objekt als Parameter, um Zugriff auf das
    per-Trip-Cooldown-Feld zu haben.
    """
    from app.config import Settings
    from services.throttle_store import ThrottleStore
    from services.trip_alert import TripAlertService

    uid = f"tdd-throttle-nextalert-{uuid.uuid4().hex[:6]}"
    trip_id = f"trip-{uuid.uuid4().hex[:6]}"

    recorded_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    ThrottleStore(uid).record("trip", trip_id, recorded_at)

    trip = _make_trip(trip_id, alert_cooldown_minutes=30)

    svc = TripAlertService(settings=Settings(), throttle_hours=5, user_id=uid)
    remaining = svc.get_time_until_next_alert(trip)

    assert remaining is not None, (
        "AC-7: 10 Min nach record() bei 30-Min-Cooldown muss noch gedrosselt sein"
    )
    assert remaining <= timedelta(minutes=20), (
        f"AC-7: get_time_until_next_alert muss den per-Trip-Cooldown (30 Min) "
        f"verwenden, nicht die globale throttle_hours-Einstellung (5h = 300 Min); "
        f"erhaltene Restzeit: {remaining}"
    )


# ═══════════════ Radar-Migration: Konflikt & Read-Modify-Write ══════════════

def test_radar_throttle_migration_prefers_newer_timestamp(tmp_path):
    """Konflikt zwischen dem alert_state-Key `radar_throttle` und der Legacy-
    Datei `radar_alert_throttle.json` für denselben Trip: der JÜNGERE
    Timestamp gewinnt — unabhängig davon, welche Quelle ihn liefert."""
    user_dir = tmp_path / "u-radar-conflict"
    user_dir.mkdir()

    from services.throttle_store import ThrottleStore

    # Fall 1: Legacy-Datei ist juenger als der alert_state-Key.
    trip_1 = "trip-legacy-newer"
    older_1 = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    newer_1 = datetime(2026, 7, 5, 9, 0, tzinfo=timezone.utc)
    _write_json(user_dir / "alert_state" / f"{trip_1}.json", {
        "radar_throttle": {"reported_at": older_1.isoformat()},
    })
    _write_json(user_dir / "radar_alert_throttle.json", {trip_1: newer_1.isoformat()})

    store = ThrottleStore("u-radar-conflict", data_dir=user_dir)
    assert store.last_sent("radar", trip_1) == newer_1, (
        "Legacy-Datei war juenger als der alert_state-Key, aber der aeltere "
        "Wert wurde uebernommen"
    )


def test_radar_migration_preserves_other_alert_state_keys(tmp_path):
    """#102 (Datenverlust-Regel): die Radar-Migration darf beim Herausziehen
    des `radar_throttle`-Schlüssels aus `alert_state/<trip_id>.json` KEINE
    anderen Schlüssel dieser Datei löschen oder überschreiben."""
    user_dir = tmp_path / "u-radar-preserve"
    user_dir.mkdir()
    trip_id = "trip-preserve"

    radar_ts = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)
    other_entry = {"last_reported_value": 12.5, "reported_at": "2026-06-01T00:00:00+00:00"}
    _write_json(user_dir / "alert_state" / f"{trip_id}.json", {
        "radar_throttle": {"reported_at": radar_ts.isoformat()},
        "precip_sum_mm:1": other_entry,
    })

    from services.throttle_store import ThrottleStore

    store = ThrottleStore("u-radar-preserve", data_dir=user_dir)
    assert store.last_sent("radar", trip_id) == radar_ts

    remaining = json.loads((user_dir / "alert_state" / f"{trip_id}.json").read_text())
    assert remaining.get("precip_sum_mm:1") == other_entry, (
        "#102: Read-Modify-Write der Radar-Migration hat andere Schlüssel im "
        "alert_state geloescht/ueberschrieben statt nur den radar_throttle-"
        "Schluessel herauszuziehen"
    )


# ═══════════ F002 (Adversary, Runde 2): Migrations-Write vs. record() ════════

def test_migration_write_does_not_clobber_concurrent_record(tmp_path, monkeypatch):
    """F002: Der finale Migrations-Schreibvorgang muss durch dasselbe Lock
    wie `_update()` laufen und darf einen parallelen `record()` für einen
    ANDEREN scope/key nicht verlieren. Erzwingt das Rennfenster real über
    einen `threading.Event`-Hook zwischen Migrations-Lesephase (Legacy-Dateien
    ausgewertet) und -Schreibphase (`self._update(...)`)."""
    import threading

    import services.throttle_store as throttle_store_module
    from services.throttle_store import ThrottleStore

    user_dir = tmp_path / "u-race"
    user_dir.mkdir()
    trip_id = "trip-legacy"
    t_legacy = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    _write_json(user_dir / "alert_throttle.json", {trip_id: t_legacy.isoformat()})

    read_done = threading.Event()
    proceed_to_write = threading.Event()

    original_update = throttle_store_module.ThrottleStore._update

    def _blocking_update(self, mutate):
        # Signalisiert: Legacy-Quellen sind gelesen (Konstruktor-Body vor
        # diesem Aufruf) — jetzt wartet die Migration, bevor sie schreibt.
        read_done.set()
        proceed_to_write.wait(timeout=5)
        return original_update(self, mutate)

    monkeypatch.setattr(throttle_store_module.ThrottleStore, "_update", _blocking_update)

    migration_thread = threading.Thread(
        target=lambda: ThrottleStore("u-race", data_dir=user_dir)
    )
    migration_thread.start()
    assert read_done.wait(timeout=5), "Migrations-Lesephase hat nicht rechtzeitig signalisiert"

    # Konkurrierender record() für einen ANDEREN Key läuft durch den
    # unveränderten `_update()` (echtes Lock) und schreibt VOR der
    # Migrations-Schreibphase.
    concurrent_store = ThrottleStore.__new__(ThrottleStore)
    concurrent_store._user_id = "u-race"
    concurrent_store._dir = user_dir
    concurrent_store._path = user_dir / throttle_store_module._STATE_FILENAME
    original_update(concurrent_store, lambda data: data.setdefault("trip", {}).__setitem__(
        "trip-concurrent", datetime(2026, 7, 9, tzinfo=timezone.utc).isoformat()
    ))

    proceed_to_write.set()
    migration_thread.join(timeout=5)
    assert not migration_thread.is_alive(), "Migrations-Thread ist nicht rechtzeitig fertig geworden"

    fresh = ThrottleStore("u-race", data_dir=user_dir)
    assert fresh.last_sent("trip", trip_id) == t_legacy, (
        "F002: migrierter Legacy-Eintrag ist nach der Race verschwunden"
    )
    assert fresh.last_sent("trip", "trip-concurrent") is not None, (
        "F002: paralleler record()-Eintrag wurde vom ungesperrten "
        "Migrations-Schreibvorgang überschrieben/verloren"
    )


# ═══════════════════ Toter Code — Regressionsschutz ══════════════════════════

def test_dead_code_is_throttled_removed():
    """Regressionsschutz (kein Verhaltenstest, Symbol-Abwesenheit — laut
    Testpolitik-Ausnahme für genau diesen Fall zulaessig): nach dem
    GREEN-Umbau (Issue #1213) darf `TripAlertService._is_throttled` (toter
    Produktivcode, ersetzt durch `_is_throttled_with_cooldown`/Store) nicht
    wieder eingefuehrt werden.

    RED-HINWEIS: In der RED-Phase existiert `_is_throttled` noch (wird erst
    beim GREEN-Umbau entfernt) — dieser Test schlaegt JETZT bewusst mit
    AssertionError fehl und wird nach der Implementierung gruen.
    """
    from services.trip_alert import TripAlertService

    assert not hasattr(TripAlertService, "_is_throttled"), (
        "Toter Code _is_throttled() ist noch vorhanden — muss laut Spec "
        "(docs/specs/modules/throttle_store.md) entfernt werden"
    )
