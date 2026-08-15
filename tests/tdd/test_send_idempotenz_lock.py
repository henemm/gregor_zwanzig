"""TDD RED — #1756: In-Process-Lock gegen doppelten manuellen Trip-Versand.

Spec: docs/specs/modules/fix_1756_send_idempotenz_lock.md (AC-1..AC-6)
Kontext: docs/context/fix-1756-send-timeout-502.md

Zielverhalten: `_try_acquire_send_lock`/`_release_send_lock` (Modulebene in
`services.trip_report_scheduler`) sperren `_send_trip_report_outcome()` pro
Schlüssel `(user_id, trip_id, report_type)`. Ein zweiter Aufruf waehrend ein
erster fuer denselben Schluessel laeuft, liefert den Outcome
`"already_in_progress"` statt einen zweiten echten Versand auszuloesen. Der
Router mappt diesen Outcome auf HTTP 409.

RED heute: `_try_acquire_send_lock`/`_release_send_lock` existieren nicht
(`AttributeError`/`ImportError`) — `send_test_report_outcome()` und
`send_on_demand_report()` rufen `_send_trip_report_outcome()` ungebremst auf,
ein zweiter gleichzeitiger Aufruf laeuft ungehindert durch.

Test-Politik (CLAUDE.md „Zwei Schichten"): Kern-Schicht, deterministisch,
kein Netz. Kein Mock-Theater — ersetzt wird ausschliesslich die Naht zum
Netz (`_send_trip_report_outcome`) durch eine ECHTE Unterklasse (Muster
`tests/tdd/test_briefing_slot_idempotenz.py::_scheduler_mit_festem_ausgang`),
die entweder sofort einen Ausgang zurueckgibt oder — fuer die
„gleichzeitig"-Faelle — kontrolliert auf einem echten `threading.Event`
blockiert, bis der Test das Lock-Verhalten des zweiten Aufrufs geprueft hat.
Kein `sleep`-Timing-Raten: der erste Aufruf meldet ueber ein Event, dass er
die Naht betreten hat (und damit — nach dem Fix — den Lock haelt), bevor der
zweite Aufruf im Hauptthread synchron gestartet wird.

────────────────────────────────────────────────────────────────────────────
RED-Charakter je Test (Konvention aus tests/tdd/test_briefing_slot_idempotenz.py)
────────────────────────────────────────────────────────────────────────────
AC-1/AC-3/AC-4/AC-6 sind Fehlernachweise: sie sind heute rot, weil der Lock
fehlt. AC-2 und AC-5 sind bewusst Mutations-Waechter, die HEUTE SCHON GRUEN
sind — sie pruefen die ABWESENHEIT von Blockade (kein Lock-Konflikt, zwei
verschiedene Nutzer), was ohne jeden Lock trivial erfuellt ist. Ihr Wert
entsteht erst NACH dem Fix: sie muessen auch dann gruen bleiben und faengen
so eine ueberscharfe Lock-Implementierung (z.B. ein Lock ohne user_id im
Schluessel), die faelschlich auch unbeteiligte Aufrufe blockiert.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.loader import get_briefings_dir, load_all_trips  # noqa: E402

KORSIKA = (42.30, 8.93)  # Europe/Paris — echter Ort, TimezoneFinder loest ihn auf.


# ---------------------------------------------------------------------------
# Aufbau-Helfer (Muster: tests/tdd/test_briefing_slot_idempotenz.py::_trip_json)
# ---------------------------------------------------------------------------


def _trip_json(trip_id: str) -> dict:
    heute = date.today()
    return {
        "id": trip_id,
        "name": f"Trip {trip_id}",
        "stages": [{
            "id": f"{trip_id}-s0",
            "name": "Etappe 0",
            "date": heute.isoformat(),
            "waypoints": [
                {"id": f"{trip_id}-wp0a", "name": "Start",
                 "lat": KORSIKA[0], "lon": KORSIKA[1], "elevation_m": 800},
                {"id": f"{trip_id}-wp0b", "name": "Ziel",
                 "lat": KORSIKA[0] + 0.05, "lon": KORSIKA[1] + 0.05, "elevation_m": 1200},
            ],
        }],
        "report_config": {"enabled": True, "evening_time": "18:00:00"},
    }


def _schreibe_trip(user_id: str, trip_id: str) -> None:
    """Mandantentrennung: jeder Test bekommt eine eigene, sprechende user_id."""
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps(_trip_json(trip_id)), encoding="utf-8")


def _lade_trip(user_id: str, trip_id: str):
    trips = load_all_trips(user_id=user_id)
    trip = next(t for t in trips if t.id == trip_id)
    return trip


def _scheduler_mit_festem_ausgang(user_id: str, ausgang: str = "sent"):
    """Echter `TripReportSchedulerService`, bei dem AUSSCHLIESSLICH die Naht
    zum Netz (`_send_trip_report_outcome`) ersetzt ist — sofortige Rueckgabe,
    kein Blockieren. Zaehlt Versandversuche mit."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class _SchedulerMitFestemAusgang(TripReportSchedulerService):
        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            self.versandversuche.append((trip.id, report_type))
            return self.ausgang

    scheduler = _SchedulerMitFestemAusgang(user_id=user_id)
    scheduler.versandversuche = []
    scheduler.ausgang = ausgang
    return scheduler


def _scheduler_blockierend(user_id: str, betreten: threading.Event,
                           weiter: threading.Event, ausgang: str = "sent",
                           ausnahme: BaseException | None = None):
    """Echter `TripReportSchedulerService`, dessen Naht zum Netz beim ERSTEN
    Aufruf kontrolliert blockiert: signalisiert per Event, dass sie betreten
    wurde (und — nach dem Fix — den Lock haelt), wartet dann auf Freigabe.
    `ausnahme` (falls gesetzt) wirft NUR beim allerersten Aufruf -- ein
    etwaiger dritter Aufruf (nach Lock-Freigabe) muss normal durchlaufen
    koennen, um die Freigabe ueberhaupt beweisen zu koennen. Kein Mock: echte
    Unterklasse, echte Aufrufmitschrift."""
    from services.trip_report_scheduler import TripReportSchedulerService

    geworfen = {"wert": False}

    class _SchedulerBlockierend(TripReportSchedulerService):
        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            self.versandversuche.append((trip.id, report_type))
            betreten.set()
            weiter.wait(timeout=5)
            if ausnahme is not None and not geworfen["wert"]:
                geworfen["wert"] = True
                raise ausnahme
            return ausgang

    scheduler = _SchedulerBlockierend(user_id=user_id)
    scheduler.versandversuche = []
    return scheduler


# ---------------------------------------------------------------------------
# AC-1 — zweiter gleichzeitiger Testversand-Aufruf liefert already_in_progress
# ---------------------------------------------------------------------------


def test_ac1_zweiter_gleichzeitiger_testversand_liefert_already_in_progress():
    """Given ein Testversand fuer Trip A (User X, evening) laeuft bereits /
    When waehrend dieser Laufzeit ein zweiter `send_test_report_outcome()`-
    Aufruf fuer denselben Schluessel erfolgt / Then liefert der zweite Aufruf
    `"already_in_progress"`, OHNE dass ein zweiter echter Versand ausgeloest
    wird (Versand-Mitschrift zaehlt nur EINEN Eintrag).

    Bug-Nachweis: rot vor Fix (der zweite Aufruf laeuft heute ungehindert
    durch und ruft die Naht ein zweites Mal auf), gruen nach Fix.

    RED-Charakter: Fehlernachweis — rot bei fehlendem Lock (heutiger Zustand).
    """
    user_id = "send-lock-ac1"
    trip_id = "korsika"
    _schreibe_trip(user_id, trip_id)
    trip = _lade_trip(user_id, trip_id)

    betreten = threading.Event()
    weiter = threading.Event()
    scheduler = _scheduler_blockierend(user_id, betreten, weiter)

    ergebnisse: list[str] = []
    thread = threading.Thread(
        target=lambda: ergebnisse.append(scheduler.send_test_report_outcome(trip, "evening")),
    )
    thread.start()
    assert betreten.wait(timeout=5), "Erster Aufruf hat die Netz-Naht nicht betreten"

    zweiter_ausgang = scheduler.send_test_report_outcome(trip, "evening")

    weiter.set()
    thread.join(timeout=5)

    assert zweiter_ausgang == "already_in_progress", (
        f"Erwartet 'already_in_progress' waehrend ein Versand fuer denselben "
        f"Schluessel laeuft, bekommen {zweiter_ausgang!r}"
    )
    assert ergebnisse == ["sent"], f"Erster Aufruf muss unveraendert durchlaufen: {ergebnisse}"
    assert scheduler.versandversuche == [(trip_id, "evening")], (
        "Die Netz-Naht darf nur EINMAL betreten worden sein — ein zweiter "
        f"echter Versandversuch waere ein Doppelversand: {scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-2 — ohne Lock-Kollision laeuft der Versand unveraendert durch
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ausgang", ["sent", "no_stage", "no_weather", "no_channels", "channels_unreachable"])
def test_ac2_ohne_kollision_liefert_unveraenderten_outcome(ausgang: str):
    """Given kein Versand fuer den Schluessel laeuft gerade / When
    `send_test_report_outcome()` aufgerufen wird / Then bleibt der Outcome
    unveraendert (keine Regression an #695/#1325), UND der Lock ist danach
    wieder frei (ein direkt folgender Aufruf blockiert nicht).

    RED-Charakter: Mutations-Waechter — heute bereits gruen (kein Lock, also
    auch keine faelschliche Blockade). Wert entsteht NACH dem Fix: faengt
    einen Lock, der versehentlich nicht freigegeben wird oder den Outcome
    verfaelscht."""
    user_id = f"send-lock-ac2-{ausgang}"
    trip_id = "korsika"
    _schreibe_trip(user_id, trip_id)
    trip = _lade_trip(user_id, trip_id)
    scheduler = _scheduler_mit_festem_ausgang(user_id, ausgang=ausgang)

    outcome = scheduler.send_test_report_outcome(trip, "evening")
    assert outcome == ausgang, f"Erwartet unveraenderten Outcome {ausgang!r}, bekommen {outcome!r}"

    # Lock-Freigabe: ein zweiter, direkt folgender Aufruf darf NICHT
    # 'already_in_progress' liefern -- der erste ist bereits abgeschlossen.
    zweiter = scheduler.send_test_report_outcome(trip, "evening")
    assert zweiter != "already_in_progress", (
        "Der Lock muss nach Abschluss des ersten Aufrufs wieder frei sein, "
        f"bekommen {zweiter!r} beim direkt folgenden Aufruf"
    )
    assert len(scheduler.versandversuche) == 2, (
        f"Beide Aufrufe muessen die Naht betreten, gefunden {scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Router mappt already_in_progress auf HTTP 409
# ---------------------------------------------------------------------------


def test_ac3_router_mappt_already_in_progress_auf_409(monkeypatch):
    """Given der Router-Endpunkt `POST /api/scheduler/trips/{trip_id}/send`
    erhaelt den Outcome `"already_in_progress"` / When die Antwort gebaut
    wird / Then ist der Statuscode 409 mit einem nicht-leeren `detail`-Feld,
    unterscheidbar von den bestehenden 422-Fehlerzweigen.

    RED-Charakter: Fehlernachweis — rot, weil der Router den Outcome
    'already_in_progress' heute nicht kennt und in den 200-Erfolgspfad
    faellt (`{"status": "ok", ..., "sent": True}`) statt 409 zu liefern."""
    from fastapi.testclient import TestClient
    from api.main import app

    user_id = "send-lock-ac3"
    trip_id = "korsika"
    _schreibe_trip(user_id, trip_id)

    monkeypatch.setattr("app.config.Settings.can_send_email", lambda self: True)
    monkeypatch.setattr(
        "services.trip_report_scheduler.TripReportSchedulerService.send_test_report_outcome",
        lambda self, trip, report_type: "already_in_progress",
    )

    resp = TestClient(app).post(
        f"/api/scheduler/trips/{trip_id}/send",
        params={"user_id": user_id, "report_type": "evening"},
    )

    assert resp.status_code == 409, (
        f"Erwartet 409 bei Outcome 'already_in_progress', bekommen "
        f"{resp.status_code}. Body: {resp.text}"
    )
    body = resp.json()
    assert body.get("detail"), f"Kein nicht-leeres 'detail'-Feld in der 409-Antwort: {body}"
    assert body["detail"] != "SMTP not configured for this user", (
        "Die 409-Meldung darf nicht mit dem bestehenden 422-Zweig verwechselt werden"
    )


# ---------------------------------------------------------------------------
# AC-4 — Lock wird nach Exception per finally wieder freigegeben
# ---------------------------------------------------------------------------


def test_ac4_lock_wird_nach_exception_wieder_freigegeben():
    """Given ein Versandversuch wirft eine Exception, WAEHREND er laeuft
    haelt er (nach dem Fix) den Lock / When ein zweiter Aufruf waehrend
    dieser Laufzeit eintrifft, DANACH ein dritter / Then wird der zweite
    Aufruf mit 'already_in_progress' abgewiesen (Lock war belegt), der
    dritte Aufruf (nach Abschluss inkl. Exception) darf die Naht dagegen
    erneut betreten — beweist Freigabe per `finally`, nicht nur im
    Erfolgspfad.

    Zwei Teile in einem Test, weil beide zusammen erst beweiskraeftig sind:
    Teil 1 (waehrend die Exception noch aussteht) ist der Fehlernachweis.
    Teil 2 (nach Abschluss) waere ohne Teil 1 ein Mutations-Waechter, der
    schon ohne jeden Lock gruen ist (ohne Lock blockiert ohnehin nichts).

    RED-Charakter: Fehlernachweis (Teil 1) — rot, weil der Lock heute nicht
    existiert: der zweite Aufruf blockiert nicht auf 'already_in_progress',
    sondern betritt die Naht ebenfalls und wirft dieselbe Exception.
    """
    user_id = "send-lock-ac4"
    trip_id = "korsika"
    _schreibe_trip(user_id, trip_id)
    trip = _lade_trip(user_id, trip_id)

    betreten = threading.Event()
    weiter = threading.Event()
    scheduler = _scheduler_blockierend(
        user_id, betreten, weiter, ausnahme=RuntimeError("Versandpfad wirft (simuliert)"),
    )

    fehler: list[BaseException] = []

    def _erster_aufruf() -> None:
        try:
            scheduler.send_test_report_outcome(trip, "evening")
        except RuntimeError as exc:
            fehler.append(exc)

    thread = threading.Thread(target=_erster_aufruf)
    thread.start()
    assert betreten.wait(timeout=5), "Erster Aufruf hat die Netz-Naht nicht betreten"

    # Teil 1: waehrend der erste Aufruf noch (kurz vor der Exception) laeuft,
    # muss der Lock ihn als belegt ausweisen.
    zweiter_waehrend_laufzeit = scheduler.send_test_report_outcome(trip, "evening")
    assert zweiter_waehrend_laufzeit == "already_in_progress", (
        "Waehrend der erste Aufruf laeuft (kurz vor seiner Exception) muss "
        f"ein zweiter Aufruf blockiert werden, bekommen {zweiter_waehrend_laufzeit!r}"
    )

    weiter.set()
    thread.join(timeout=5)
    assert fehler and isinstance(fehler[0], RuntimeError), (
        "Der erste Aufruf muss die Exception unveraendert weiterreichen"
    )

    # Teil 2: NACH der Exception muss der Lock frei sein.
    dritter_nach_exception = scheduler.send_test_report_outcome(trip, "evening")
    assert dritter_nach_exception != "already_in_progress", (
        "Nach einer Exception im ersten Aufruf muss der Lock frei sein "
        f"(finally-Freigabe), bekommen {dritter_nach_exception!r}"
    )
    assert len(scheduler.versandversuche) == 2, (
        f"Nur der 1. und 3. Aufruf duerfen die Naht betreten haben — der 2. Aufruf "
        f"wird per Lock abgewiesen, bevor er sie erreicht (Teil 1 oben): "
        f"{scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Mandantentrennung: zwei Nutzer blockieren sich nicht gegenseitig
# ---------------------------------------------------------------------------


def test_ac5_zwei_nutzer_blockieren_sich_nicht_bei_identischer_trip_id():
    """Given zwei verschiedene Nutzer (User X, User Y) loesen gleichzeitig
    einen Testversand fuer ihren jeweils eigenen Trip mit identischer
    `trip_id` und identischem `report_type` aus / When beide Aufrufe
    zeitgleich laufen / Then blockiert keiner der beiden den anderen — beide
    erhalten ihren eigenen Outcome, keiner 'already_in_progress'.

    Pflicht-Zwei-Nutzer-Test gemaess CLAUDE.md-Mandantenfaehigkeits-Vorgabe.
    """
    trip_id = "gleicher-slug"
    _schreibe_trip("send-lock-ac5-x", trip_id)
    _schreibe_trip("send-lock-ac5-y", trip_id)
    trip_x = _lade_trip("send-lock-ac5-x", trip_id)
    trip_y = _lade_trip("send-lock-ac5-y", trip_id)

    betreten_x = threading.Event()
    weiter_x = threading.Event()
    scheduler_x = _scheduler_blockierend("send-lock-ac5-x", betreten_x, weiter_x)
    scheduler_y = _scheduler_mit_festem_ausgang("send-lock-ac5-y", ausgang="sent")

    ergebnisse: list[str] = []
    thread = threading.Thread(
        target=lambda: ergebnisse.append(scheduler_x.send_test_report_outcome(trip_x, "evening")),
    )
    thread.start()
    assert betreten_x.wait(timeout=5), "User X hat die Netz-Naht nicht betreten"

    ausgang_y = scheduler_y.send_test_report_outcome(trip_y, "evening")

    weiter_x.set()
    thread.join(timeout=5)

    assert ausgang_y != "already_in_progress", (
        f"User Y darf durch User X' laufenden Versand nicht blockiert werden "
        f"(identische trip_id/report_type, verschiedene user_id), bekommen {ausgang_y!r}"
    )
    assert ergebnisse == ["sent"], f"User X' Versand muss unveraendert durchlaufen: {ergebnisse}"


# ---------------------------------------------------------------------------
# AC-6 — send_on_demand_report() teilt denselben Lock-Key-Raum
# ---------------------------------------------------------------------------


def test_ac6_on_demand_zweiter_aufruf_liefert_already_in_progress():
    """Given `send_on_demand_report()` nutzt denselben `_send_trip_report_
    outcome()`-Kern / When waehrend eines laufenden On-Demand-Versands ein
    zweiter On-Demand-Aufruf fuer denselben Schluessel eintrifft / Then
    liefert `send_on_demand_report()` ein `OnDemandErgebnis` mit
    `outcome="already_in_progress"`, ohne einen zweiten echten Versand."""
    user_id = "send-lock-ac6"
    trip_id = "korsika"
    _schreibe_trip(user_id, trip_id)
    trip = _lade_trip(user_id, trip_id)

    betreten = threading.Event()
    weiter = threading.Event()
    scheduler = _scheduler_blockierend(user_id, betreten, weiter)

    ergebnisse = []
    thread = threading.Thread(
        target=lambda: ergebnisse.append(scheduler.send_on_demand_report(trip, "evening")),
    )
    thread.start()
    assert betreten.wait(timeout=5), "Erster On-Demand-Aufruf hat die Netz-Naht nicht betreten"

    zweites_ergebnis = scheduler.send_on_demand_report(trip, "evening")

    weiter.set()
    thread.join(timeout=5)

    assert zweites_ergebnis.outcome == "already_in_progress", (
        f"Erwartet 'already_in_progress' beim zweiten On-Demand-Aufruf, "
        f"bekommen {zweites_ergebnis.outcome!r}"
    )
    assert zweites_ergebnis.zieltag is not None, (
        "Der Platzhalter-Zieltag muss auch im Kollisionsfall gesetzt sein "
        "(vor dem Lock-Versuch berechnet)"
    )
    assert ergebnisse and ergebnisse[0].outcome == "sent", (
        f"Erster On-Demand-Aufruf muss unveraendert durchlaufen: {ergebnisse}"
    )
    assert scheduler.versandversuche == [(trip_id, "evening")], (
        f"Die Netz-Naht darf nur EINMAL betreten worden sein: {scheduler.versandversuche}"
    )


def test_ac6_geteilter_lock_key_raum_testversand_blockiert_on_demand():
    """Given ein laufender Testversand (`send_test_report_outcome`) fuer Trip
    A, User X, evening / When waehrend dieser Laufzeit ein On-Demand-Aufruf
    (`send_on_demand_report`) fuer DENSELBEN Schluessel eintrifft / Then wird
    auch dieser mit `outcome='already_in_progress'` abgewiesen — geteilter
    Lock-Key-Raum, nicht zwei getrennte Register."""
    user_id = "send-lock-ac6-geteilt"
    trip_id = "korsika"
    _schreibe_trip(user_id, trip_id)
    trip = _lade_trip(user_id, trip_id)

    betreten = threading.Event()
    weiter = threading.Event()
    scheduler = _scheduler_blockierend(user_id, betreten, weiter)

    ergebnisse: list[str] = []
    thread = threading.Thread(
        target=lambda: ergebnisse.append(scheduler.send_test_report_outcome(trip, "evening")),
    )
    thread.start()
    assert betreten.wait(timeout=5), "Testversand hat die Netz-Naht nicht betreten"

    on_demand_ergebnis = scheduler.send_on_demand_report(trip, "evening")

    weiter.set()
    thread.join(timeout=5)

    assert on_demand_ergebnis.outcome == "already_in_progress", (
        "Ein laufender Testversand muss einen gleichzeitigen On-Demand-Aufruf "
        f"fuer denselben Schluessel blockieren, bekommen {on_demand_ergebnis.outcome!r} "
        "-- getrennte Lock-Register waeren ein Konstruktionsfehler, kein Idempotenz-Schutz."
    )
    assert ergebnisse == ["sent"], f"Testversand muss unveraendert durchlaufen: {ergebnisse}"
