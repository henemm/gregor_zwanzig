"""TDD RED — Epic #2261, Scheibe A-2 S1: faire Reihenfolge im Alarmlauf.

SPEC: docs/specs/modules/fix_2261_a2s1_alarmlauf_reihenfolge.md

``TripAlertService.check_all_trips()`` bricht bei langsamen Laeufen an der
Zeitgrenze ab. Heute ist die Reihenfolge fest nach Trip-ID — dieselben
ID-hinteren Trips fallen bei JEDEM langsamen Lauf weg. Die Spec verlangt:
Reihenfolge nach „zuletzt erreicht" (aelteste zuerst, persistiert je Nutzer
in ``data/users/<user_id>/alert_last_checked.json``), übersprungene IDs
sichtbar (``skipped_ids``), Grenze 180 s.

Kein Mock-Theater: echte Schlafzeit je Trip (Muster ``_setup_slow_trips``
aus ``test_alert_run_deadline.py``), echte Trips im isolierten Datenbaum
(``conftest._redirect_data_root_session``), echter Store, echter FastAPI-
Router. Ersetzt wird nur ``check_and_send_alerts`` durch eine Funktion, die
die Aufruf-Reihenfolge aufzeichnet — das ist die Messstelle, an der die
Reihenfolge WIRKT.

Store-Vertrag, den diese Tests festlegen (``services/alert_check_state.py``):
- ``AlertCheckStateStore(user_id)`` — Pfad ueber ``get_data_dir(user_id)``
- ``.load(known_trip_ids) -> dict[str, datetime]`` (fail-open, leer bei Fehler)
- ``.record(reached: dict[str, datetime], known_trip_ids)`` — Max-Merge,
  Prune, atomar, Lock auf ``alert_last_checked.json.lock`` (Muster
  ``throttle_store.py``), fail-open bei Lock-Timeout
- Dateiformat ``{trip_id: ISO-8601-UTC}``

RED-Ursachen (heute):
- ``services.alert_check_state`` existiert nicht (AC-3..AC-7 Import-Fehler).
- ``check_all_trips()`` sortiert nach Trip-ID (AC-1, AC-2 rot).
- ``AlertCheckRunResult`` hat kein ``skipped_ids``; Endpoint/WARNING nennen
  keine IDs (AC-8, AC-10 rot).
- ``ALERT_RUN_DEADLINE_SECONDS`` ist 90 statt 180 (AC-9 rot).
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from app.loader import delete_trip, get_data_dir, save_trip
from app.models import TripReportConfig
from app.trip import Stage, Trip, Waypoint
from services import trip_alert
from services.trip_alert import TripAlertService

# Helfer + autouse-Fixture (Registry amtlicher Quellen leeren) aus dem
# Schwester-Test der Zeitgrenze (#1447 S1) — dieselben Bausteine, keine Kopie.
from tests.tdd.test_alert_run_deadline import (  # noqa: F401
    LAT,
    LON,
    _active_trip,
    _isolated_official_alert_sources,
    _save_cached,
    _settings,
    _weather_data,
)

STATE_FILENAME = "alert_last_checked.json"

# Schlafzeit je Trip und Grenze so gewaehlt, dass die Grenze real
# unterschritten wird: Pruefung vor Trip 1 (t=0), Trip 2 (t~0.2), Trip 3
# (t~0.4 > 0.3) ⇒ genau k=2 Trips je Lauf, mit ~0.1 s Abstand zur Grenze
# auf beiden Seiten (Toleranz gegen Laufzeit-Rauschen).
SLEEP_S = 0.2
DEADLINE_S = 0.3
REACHED_PER_RUN = 2


def _fresh_user(prefix: str) -> str:
    return f"tdd-2261-{prefix}-{uuid.uuid4().hex[:6]}"


def _service(user_id: str) -> TripAlertService:
    return TripAlertService(settings=_settings(), user_id=user_id, mail_sink=lambda *_: None)


def _state_path(user_id: str):
    return get_data_dir(user_id) / STATE_FILENAME


def _read_state(user_id: str) -> dict[str, datetime]:
    raw = json.loads(_state_path(user_id).read_text(encoding="utf-8"))
    return {k: datetime.fromisoformat(v) for k, v in raw.items()}


def _write_state(user_id: str, stamps: dict[str, datetime]) -> None:
    path = _state_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({k: v.isoformat() for k, v in stamps.items()}), encoding="utf-8",
    )


def _save_active(user_id: str, trip_id: str) -> Trip:
    trip = _active_trip(trip_id)
    save_trip(trip, user_id=user_id)
    _save_cached(user_id, trip.id, [_weather_data(1, precip_sum_mm=2.0)])
    return trip


def _record_calls(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sleep_s: float = 0.0,
    deadline_s: float = 600.0,
    returns: bool = False,
    raise_for: frozenset[str] = frozenset(),
) -> list[str]:
    """Ersetzt ``check_and_send_alerts`` durch eine Aufzeichnung der
    Aufruf-Reihenfolge (+ echte Schlafzeit) und setzt die Laufgrenze."""
    calls: list[str] = []

    def _recording(self, trip, cached, fresh_weather=None, official_notices=None):
        calls.append(trip.id)
        time.sleep(sleep_s)
        if trip.id in raise_for:
            raise RuntimeError(f"Giftfall {trip.id}")
        return returns

    monkeypatch.setattr(TripAlertService, "check_and_send_alerts", _recording)
    monkeypatch.setattr(trip_alert, "ALERT_RUN_DEADLINE_SECONDS", deadline_s)
    return calls


# ---------------------------------------------------------------------------
# AC-1 — zwei langsame Laeufe decken zusammen alle Trips ab.
# ---------------------------------------------------------------------------

def test_zwei_langsame_laeufe_decken_alle_trips_ab(monkeypatch):
    """AC-1: Given N=4 Trips, Grenze laesst je Lauf nur k=2 zu / When zwei
    Laeufe nacheinander / Then Vereinigung = alle 4 Trips, und Lauf 2 beginnt
    mit genau den in Lauf 1 uebersprungenen Trips.

    RED (heute): ``sorted(key=id)`` ⇒ Lauf 2 prueft wieder trip-0, trip-1.
    """
    user_id = _fresh_user("ac1")
    all_ids = [_save_active(user_id, f"trip-{i}").id for i in range(4)]
    calls = _record_calls(monkeypatch, sleep_s=SLEEP_S, deadline_s=DEADLINE_S)

    first = _service(user_id).check_all_trips()
    run1 = list(calls)
    calls.clear()
    second = _service(user_id).check_all_trips()
    run2 = list(calls)

    assert first.hit_deadline and second.hit_deadline
    assert len(run1) == REACHED_PER_RUN, f"Lauf 1 sollte k=2 erreichen, war {run1!r}"
    skipped_in_run1 = [t for t in all_ids if t not in run1]
    assert run2[: len(skipped_in_run1)] == skipped_in_run1, (
        f"Lauf 2 muss mit den in Lauf 1 uebersprungenen Trips beginnen: "
        f"erwartet {skipped_in_run1!r}, Lauf 1={run1!r}, Lauf 2={run2!r}"
    )
    assert set(run1) | set(run2) == set(all_ids), (
        f"Zwei Laeufe muessen alle Trips abdecken: Lauf 1={run1!r}, Lauf 2={run2!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — vorbelegte Stempel bestimmen die Reihenfolge, ID ist Tie-Break.
# ---------------------------------------------------------------------------

def test_vorbelegte_stempel_bestimmen_reihenfolge_id_ist_tiebreak(monkeypatch):
    """AC-2: Given Stempel: t1-neu (neuester), t2-alt (aeltester), t3-ohne
    (kein Eintrag), t4-mitte/t5-mitte (identischer Stempel) / When ein Lauf /
    Then Reihenfolge t3-ohne, t2-alt, t4-mitte, t5-mitte, t1-neu.

    Die IDs sind so gewaehlt, dass die ID-Reihenfolge (t1..t5) von der
    erwarteten abweicht. RED (heute): ID-Sortierung.
    """
    user_id = _fresh_user("ac2")
    for tid in ("t1-neu", "t2-alt", "t3-ohne", "t4-mitte", "t5-mitte"):
        _save_active(user_id, tid)
    base = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    _write_state(user_id, {
        "t1-neu": base + timedelta(hours=5),
        "t2-alt": base - timedelta(hours=5),
        "t4-mitte": base,
        "t5-mitte": base,
    })
    calls = _record_calls(monkeypatch)

    _service(user_id).check_all_trips()

    assert calls == ["t3-ohne", "t2-alt", "t4-mitte", "t5-mitte", "t1-neu"], (
        f"Reihenfolge muss ohne Stempel → aeltester → neuester sein, "
        f"ID als Tie-Break; tatsaechlich {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — geloeschter Trip verschwindet aus der Zustandsdatei.
# ---------------------------------------------------------------------------

def test_geloeschter_trip_verschwindet_aus_zustandsdatei(monkeypatch):
    """AC-3: Given ein Stempel fuer einen inzwischen geloeschten Trip / When
    der naechste Lauf schreibt / Then fehlt dessen Eintrag, die vorhandenen
    Trips stehen in der Datei."""
    user_id = _fresh_user("ac3")
    _save_active(user_id, "bleibt-a")
    _save_active(user_id, "bleibt-b")
    _save_active(user_id, "weg")
    old = datetime(2026, 9, 1, tzinfo=timezone.utc)
    _write_state(user_id, {"bleibt-a": old, "bleibt-b": old, "weg": old})
    delete_trip("weg", user_id=user_id)
    _record_calls(monkeypatch)

    _service(user_id).check_all_trips()

    state = _read_state(user_id)
    assert "weg" not in state, f"Geloeschter Trip muss geprunt werden: {state!r}"
    assert {"bleibt-a", "bleibt-b"} <= set(state), f"Vorhandene Trips fehlen: {state!r}"
    assert all(state[t] > old for t in ("bleibt-a", "bleibt-b")), (
        f"Erreichte Trips muessen einen neuen Stempel tragen: {state!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Stempel auch fuer Giftfall, regellosen und abgelaufenen Trip; kein
# Stempel fuer nicht erreichte Trips.
# ---------------------------------------------------------------------------

def _regellos_trip(trip_id: str) -> Trip:
    """Weder Alarmregel noch Aenderungsalarm noch amtlicher Trigger ⇒
    ``check_all_trips`` verlaesst ihn per ``continue``."""
    trip = _active_trip(trip_id)
    trip.official_warnings = {"enabled": False}
    trip.report_config = TripReportConfig(trip_id=trip_id, alert_on_changes=False)
    return trip


def _abgelaufener_trip(trip_id: str) -> Trip:
    past = date.today() - timedelta(days=10)
    stage = Stage(
        id="T1", name="Tag 1", date=past,
        waypoints=[Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0)],
    )
    trip = Trip(id=trip_id, name="Abgelaufen", stages=[stage])
    trip.report_config = TripReportConfig(trip_id=trip_id, send_email=True)
    return trip


def test_stempel_auch_bei_exception_regellos_und_abgelaufen(monkeypatch):
    """AC-4: Given (a) Exception, (b) regellos, (c) abgelaufen, (d) normal —
    alle vor der Grenze erreicht / When der Lauf endet / Then trägt jeder
    einen Stempel und (d) wurde normal geprueft. Zusaetzlich: ein Lauf mit
    Grenzabbruch vergibt dem nicht erreichten Trip KEINEN Stempel.

    Die Mutation „Stempel nur im Erfolgspfad" laesst (a)-(c) ohne Eintrag.
    """
    user_id = _fresh_user("ac4")
    _save_active(user_id, "a-gift")
    save_trip(_regellos_trip("b-regellos"), user_id=user_id)
    save_trip(_abgelaufener_trip("c-abgelaufen"), user_id=user_id)
    _save_active(user_id, "d-normal")
    calls = _record_calls(monkeypatch, raise_for=frozenset({"a-gift"}))
    before = datetime.now(timezone.utc)

    result = _service(user_id).check_all_trips()

    assert "d-normal" in calls, f"Nach dem Giftfall muss der Lauf weitergehen: {calls!r}"
    assert result.checked == 4 and result.skipped == 0
    state = _read_state(user_id)
    for tid in ("a-gift", "b-regellos", "c-abgelaufen", "d-normal"):
        assert tid in state and state[tid] >= before, (
            f"Erreichter Trip {tid} braucht einen frischen Stempel: {state!r}"
        )

    # Teil 2: nicht erreichter Trip bekommt keinen Stempel.
    user2 = _fresh_user("ac4b")
    for i in range(3):
        _save_active(user2, f"slow-{i}")
    calls2 = _record_calls(monkeypatch, sleep_s=SLEEP_S, deadline_s=DEADLINE_S)
    result2 = _service(user2).check_all_trips()

    assert result2.hit_deadline and len(calls2) == REACHED_PER_RUN, calls2
    state2 = _read_state(user2)
    unreached = {f"slow-{i}" for i in range(3)} - set(calls2)
    assert set(state2) == set(calls2), (
        f"Nur erreichte Trips duerfen einen Stempel tragen: Stempel={sorted(state2)!r}, "
        f"erreicht={calls2!r}, nicht erreicht={sorted(unreached)!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 — zwei Schreiber mergen mit Maximum.
# ---------------------------------------------------------------------------

def test_zwei_schreiber_mergen_mit_maximum():
    """AC-5: Given zwei ueberlappende Laeufe schreiben sich kreuzende Werte,
    der zweite mit aelterem Wert fuer einen gemeinsamen Trip / When beide
    speichern / Then je Trip das Maximum, kein Eintrag verloren."""
    from services.alert_check_state import AlertCheckStateStore

    user_id = _fresh_user("ac5")
    known = {"x", "y", "z"}
    t1 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    t2 = t1 + timedelta(minutes=15)
    t3 = t1 + timedelta(minutes=30)

    AlertCheckStateStore(user_id).record({"x": t2, "y": t1}, known)
    AlertCheckStateStore(user_id).record({"x": t1, "z": t3}, known)

    state = _read_state(user_id)
    assert state == {"x": t2, "y": t1, "z": t3}, f"Max-Merge verletzt: {state!r}"
    assert AlertCheckStateStore(user_id).load(known) == state


# ---------------------------------------------------------------------------
# AC-6 — Mandantentrennung (Pflicht-Zwei-Nutzer-Test).
# ---------------------------------------------------------------------------

def test_zwei_nutzer_isolation_nie_default(monkeypatch):
    """AC-6: Given Nutzer A und B, beide mit Trip-ID „gleich" / When ein Lauf
    fuer A / Then nur A's Datei geschrieben, B's Datei byte-identisch, keine
    Datei unter ``data/users/default/``."""
    user_a = _fresh_user("ac6a")
    user_b = _fresh_user("ac6b")
    _save_active(user_a, "gleich")
    _save_active(user_b, "gleich")
    _write_state(user_b, {"gleich": datetime(2026, 1, 1, tzinfo=timezone.utc)})
    b_before = _state_path(user_b).read_bytes()
    default_path = _state_path("default")
    default_existed = default_path.exists()
    _record_calls(monkeypatch)

    _service(user_a).check_all_trips()

    assert "gleich" in _read_state(user_a), "Lauf fuer A muss A's Zustandsdatei schreiben"
    assert _state_path(user_b).read_bytes() == b_before, "B's Zustandsdatei wurde veraendert"
    assert default_existed or not default_path.exists(), (
        "Zustand landete unter data/users/default/ — Cross-User-Leck"
    )


# ---------------------------------------------------------------------------
# AC-7 — kaputte Zustandsdatei und Lock-Timeout sind fail-open.
# ---------------------------------------------------------------------------

def test_kaputte_zustandsdatei_und_lock_timeout_sind_fail_open(monkeypatch, caplog):
    """AC-7: Given (1) ungueltiges JSON in der Zustandsdatei bzw. (2) ein
    extern gehaltener Lock / When ``check_all_trips`` laeuft / Then alle
    Trips geprueft und Alarme gezaehlt, Reihenfolge nach Trip-ID, WARNING
    im Log, keine Exception."""
    import services.alert_check_state as state_mod

    # Lock-Wartezeit kurz halten — getestet wird das Verhalten nach Timeout.
    monkeypatch.setattr(state_mod, "LOCK_TIMEOUT_SECONDS", 0.1, raising=False)

    # (1) kaputte Datei
    user_id = _fresh_user("ac7a")
    for tid in ("k-3", "k-1", "k-2"):
        _save_active(user_id, tid)
    path = _state_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{kaputt", encoding="utf-8")
    calls = _record_calls(monkeypatch, returns=True)

    with caplog.at_level(logging.WARNING):
        result = _service(user_id).check_all_trips()

    assert calls == ["k-1", "k-2", "k-3"], f"Fallback-Reihenfolge nach ID erwartet: {calls!r}"
    assert result.alerts_sent == 3, f"Versand darf nicht ausbleiben: {result!r}"
    assert any(
        r.levelno >= logging.WARNING and STATE_FILENAME in r.getMessage() for r in caplog.records
    ), f"WARNING zur kaputten Zustandsdatei fehlt: {[r.getMessage() for r in caplog.records]!r}"

    # (2) Lock extern gehalten
    caplog.clear()
    user2 = _fresh_user("ac7b")
    for tid in ("l-1", "l-2"):
        _save_active(user2, tid)
    lock_path = str(_state_path(user2)) + ".lock"
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        calls2 = _record_calls(monkeypatch, returns=True)
        with caplog.at_level(logging.WARNING):
            result2 = _service(user2).check_all_trips()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    assert calls2 == ["l-1", "l-2"] and result2.alerts_sent == 2, (calls2, result2)
    assert any(
        r.levelno >= logging.WARNING and STATE_FILENAME in r.getMessage() for r in caplog.records
    ), f"WARNING zum Lock-Timeout fehlt: {[r.getMessage() for r in caplog.records]!r}"


# ---------------------------------------------------------------------------
# AC-8 — skipped_ids in Ergebnis, WARNING und Endpoint.
# ---------------------------------------------------------------------------

def test_skipped_ids_in_ergebnis_warning_und_endpoint(monkeypatch, caplog):
    """AC-8: Given ein Lauf mit Grenzabbruch und ein voller Lauf / Then
    ``skipped_ids`` (Ergebnis, WARNING, Endpoint) nennt genau die nicht
    erreichten Trips, ``len(skipped_ids) == skipped``; voller Lauf ⇒ leer."""
    from fastapi.testclient import TestClient

    from api.main import app

    user_id = _fresh_user("ac8")
    all_ids = [_save_active(user_id, f"s-{i}").id for i in range(4)]
    calls = _record_calls(monkeypatch, sleep_s=SLEEP_S, deadline_s=DEADLINE_S)

    with caplog.at_level(logging.WARNING):
        result = _service(user_id).check_all_trips()

    expected = [t for t in all_ids if t not in calls]
    assert result.skipped_ids == expected, (result.skipped_ids, calls)
    assert len(result.skipped_ids) == result.skipped
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any(all(t in w for t in expected) for w in warnings), (
        f"WARNING muss die uebersprungenen IDs {expected!r} nennen: {warnings!r}"
    )

    # Endpoint, eigener Nutzer (Stempel des Laufs oben veraendern sonst die Reihenfolge).
    user_ep = _fresh_user("ac8ep")
    ep_ids = [_save_active(user_ep, f"e-{i}").id for i in range(4)]
    calls.clear()
    data = TestClient(app).post(f"/api/scheduler/alert-checks?user_id={user_ep}").json()
    assert data.get("skipped_ids") == [t for t in ep_ids if t not in calls], (data, calls)
    assert len(data["skipped_ids"]) == data["skipped"]

    # Voller Lauf.
    monkeypatch.setattr(trip_alert, "ALERT_RUN_DEADLINE_SECONDS", 600.0)
    monkeypatch.setattr(
        TripAlertService, "check_and_send_alerts", lambda *a, **k: False,
    )
    full = _service(user_id).check_all_trips()
    assert full.skipped_ids == [] and full.skipped == 0 and not full.hit_deadline


# ---------------------------------------------------------------------------
# AC-9 — Laufgrenze 180 s, unter dem Go-Wartebudget von 300 s.
# ---------------------------------------------------------------------------

GO_ALERT_WAIT_BUDGET_S = 300  # internal/scheduler/scheduler.go: alertWaitBudget


def test_laufgrenze_180_unter_go_wartebudget():
    """AC-9: ``ALERT_RUN_DEADLINE_SECONDS`` == 180 und < 300 (Go-Wartebudget).
    Invariante: Grenze + beobachteter Einzel-Trip-Ueberhang (~64 s) ≤ 300 s."""
    assert trip_alert.ALERT_RUN_DEADLINE_SECONDS == 180.0
    assert trip_alert.ALERT_RUN_DEADLINE_SECONDS < GO_ALERT_WAIT_BUDGET_S


# ---------------------------------------------------------------------------
# AC-10 — Statusableitung unveraendert, Antwort traegt skipped_ids.
# ---------------------------------------------------------------------------

def test_status_partial_nur_bei_hit_deadline(monkeypatch):
    """AC-10 (Python-Seite): ``status`` ist ``partial`` nur bei Grenzabbruch,
    sonst ``ok``; die Antwort traegt in beiden Faellen ``skipped_ids``. Die
    Go-Seite bleibt unveraendert (``go test ./internal/scheduler/...``)."""
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)

    user_ok = _fresh_user("ac10ok")
    _save_active(user_ok, "ok-1")
    _record_calls(monkeypatch)
    ok = client.post(f"/api/scheduler/alert-checks?user_id={user_ok}").json()
    assert ok.get("status") == "ok" and ok.get("skipped_ids") == [], ok

    user_p = _fresh_user("ac10p")
    for i in range(3):
        _save_active(user_p, f"p-{i}")
    _record_calls(monkeypatch, sleep_s=SLEEP_S, deadline_s=DEADLINE_S)
    partial = client.post(f"/api/scheduler/alert-checks?user_id={user_p}").json()
    assert partial.get("status") == "partial" and partial.get("reason") == "deadline", partial
    assert partial.get("skipped_ids") and len(partial["skipped_ids"]) == partial["skipped"], partial
