"""TDD RED — #2795 S3b Teil 1a: Briefing-Faelligkeit im Viertelstunden-Raster.

Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.1 („Faelligkeit
(Python)“, „Genau ein Versand je Slot und Tag“), AC-5, AC-6, AC-7.

Zielverhalten::

    faellig  <=>  slot_zeit <= ortszeit < slot_zeit + 3 h   (in MINUTEN)
                  UND kein Vermerk fuer (abo, slot, ortstag)

Heute vergleicht die Faelligkeit nur Stunden (``trip_report_scheduler.
_slot_stunde`` -> ``zeit.hour``, ``briefing_slots.fenster_offen(slot_stunde,
ortsstunde)``, ``compare_slot_scheduler.presets_due_for_hour`` ->
``fenster_offen(zeit.hour, hour)``). Ein auf 06:45 gestelltes Briefing ist
damit schon um 06:00 faellig und um 09:45 nicht mehr — der Versand kommt 45
Minuten zu frueh.

Gemessen wird an den ECHTEN Praedikaten und am ECHTEN Sammel-/Versandlauf:
* Trip: ``trip_slot_due`` (freies Praedikat, dieselbe Fensterregel wie der
  Sammellauf) und ``_collect_due_trips`` + ``_dispatch_due_item`` ueber 15-
  Minuten-Ticks; ersetzt ist ausschliesslich die Netz-Naht
  ``_send_trip_report_outcome`` durch eine echte Unterklasse (Muster
  ``tests/tdd/test_briefing_slot_idempotenz.py``).
* Ortsvergleich: ``presets_due_for_hour`` und ``run_briefing_dispatch``; ersetzt
  ist nur ``send_one_compare_preset`` (Netz-Naht, Muster T11 ebenda).
Vermerk-Speicher ist die echte ``briefing_slots.json`` /
``briefing_slots_compare.json`` im isolierten Daten-Root (conftest).

Schnittstellen-Hinweis fuer GREEN: dieser Test bindet sich NICHT an eine neue
Signatur von ``fenster_offen`` (heute Stunden-Ints). Ob es kuenftig Minuten,
``time``-Objekte oder Datetimes nimmt, entscheidet die Implementierung;
geprueft wird die Wirkung an den obigen Praedikaten.

RED-Charakter je Test im Docstring: „Fehlernachweis“ = heute rot wegen des
Stunden-Vergleichs; „Regressionsschutz“ = heute gruen, muss gruen bleiben.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from app.loader import get_briefings_dir, get_data_dir, load_all_trips
from services.briefing_slots import BriefingSlotStore
from tests.tdd.test_briefing_slot_idempotenz import (
    KORSIKA, PARIS, _lauf, _schreibe, _scheduler_mit_festem_ausgang, _trip_json,
)
from utils.timezone import UTC, local_dt

TAGE = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
TAG = date(2026, 8, 20)


def _um(stunde: int, minute: int) -> datetime:
    """UTC-Zeitpunkt zu einer Ortszeit (Europe/Paris) am TAG."""
    return local_dt(datetime(TAG.year, TAG.month, TAG.day, stunde, minute, tzinfo=PARIS), UTC)


def _hhmm(now_utc: datetime) -> str:
    return local_dt(now_utc, PARIS).strftime("%H:%M")


def _ticks(von: tuple[int, int], bis: tuple[int, int]) -> list[datetime]:
    """15-Minuten-Ticks (Ortszeit Paris) von ``von`` bis einschliesslich ``bis``."""
    h, m = von
    out = []
    while (h, m) <= bis:
        out.append(_um(h, m))
        m += 15
        if m == 60:
            h, m = h + 1, 0
    return out


def _trip_mit_slot(user: str, morning: str):
    _schreibe(user, [_trip_json("korsika", *KORSIKA, TAGE, morning=morning)])
    trips = [t for t in load_all_trips(user) if t.id == "korsika"]
    assert len(trips) == 1, "Vorbedingung: Trip muss ladbar sein"
    return trips[0]


# ───────────────────── AC-5: Faelligkeit in Minuten (Trip) ──────────────────

@pytest.mark.parametrize("ortszeit, erwartet", [
    ((6, 0), False),
    ((6, 30), False),
    ((6, 44), False),
    ((6, 45), True),
    ((7, 30), True),
    ((9, 44), True),
    ((9, 46), False),
])
def test_ac5_trip_slot_0645_faellig_genau_ab_0645_bis_0945(ortszeit, erwartet):
    """AC-5 (Trip): Slot 06:45 ist um 06:30 NICHT faellig, um 06:45 faellig,
    um 09:44 noch faellig (3-h-Nachholfenster), um 09:46 nicht mehr.

    RED-Charakter: Fehlernachweis — heute zaehlt nur die Stunde: 06:00/06:30/
    06:44 gelten als faellig, 09:44 nicht mehr.
    """
    from services.trip_report_scheduler import trip_slot_due

    user = "u2795-faellig-trip"
    trip = _trip_mit_slot(user, "06:45:00")
    moment = _um(*ortszeit)
    ist = trip_slot_due(trip, "morning", moment, store=BriefingSlotStore(user))
    assert ist is erwartet, (
        f"AC-5: Morgen-Slot 06:45, Ortszeit {_hhmm(moment)} — faellig={ist}, "
        f"erwartet {erwartet} (Fenster 06:45 bis vor 09:45, in Minuten)"
    )


@pytest.mark.parametrize("ortszeit, erwartet", [
    ((6, 45), False),
    ((6, 59), False),
    ((7, 0), True),
    ((9, 59), True),
    ((10, 0), False),
])
def test_ac7_trip_slot_0700_verhaelt_sich_wie_bisher(ortszeit, erwartet):
    """AC-7 (Trip): Bestandswert 07:00 wird zur selben Zeit faellig wie zuvor
    (07:00 bis vor 10:00).

    RED-Charakter: Regressionsschutz — heute gruen, muss gruen bleiben (rot
    bei Rundung/Versatz der vollen Stunde durch den Umbau).
    """
    from services.trip_report_scheduler import trip_slot_due

    user = "u2795-faellig-0700"
    trip = _trip_mit_slot(user, "07:00:00")
    moment = _um(*ortszeit)
    ist = trip_slot_due(trip, "morning", moment, store=BriefingSlotStore(user))
    assert ist is erwartet, (
        f"AC-7: Slot 07:00, Ortszeit {_hhmm(moment)} — faellig={ist}, erwartet {erwartet}"
    )


# ───────────────── AC-5/AC-6: Sammel- und Versandlauf im 15-Min-Takt (Trip) ──

def test_ac5_ac6_trip_genau_ein_versand_um_0645_ueber_alle_ticks():
    """AC-5 + AC-6 (Trip): Slot 06:45, Scheduler laeuft von 05:00 bis 10:45 im
    15-Minuten-Takt (24 Ticks, davon 12 im Fenster). Ergebnis: GENAU EIN
    Versandversuch fuer den Morgen-Slot, und zwar beim Tick 06:45.

    Echter Sammellauf (``_collect_due_trips``), echte Reservierung und echter
    Vermerk in ``briefing_slots.json``; nur der Versand selbst ist die
    feste-Ausgang-Unterklasse (``sent``).

    RED-Charakter: Fehlernachweis — heute faellt der Versand auf den Tick
    06:00 (Stundenvergleich). Mutations-Waechter danach: Dedupe-Schluessel auf
    Stunde/ohne Vermerk-Filter -> mehrere Versaende im Fenster.
    """
    user = "u2795-ticks-trip"
    _schreibe(user, [_trip_json("korsika", *KORSIKA, TAGE, morning="06:45:00")])
    sched = _scheduler_mit_festem_ausgang(user, "sent")

    treffer = []
    for now in _ticks((5, 0), (10, 45)):
        vorher = len([v for v in sched.versandversuche if v[1] == "morning"])
        _lauf(sched, now)
        if len([v for v in sched.versandversuche if v[1] == "morning"]) > vorher:
            treffer.append(_hhmm(now))

    assert treffer == ["06:45"], (
        "AC-5/AC-6: Slot 06:45 muss ueber alle 15-Minuten-Ticks genau einmal "
        f"versendet werden, beim ersten Tick ab 06:45 — gefunden {treffer}"
    )
    eintraege = json.loads((get_data_dir(user) / "briefing_slots.json").read_text())["entries"]
    morgens = [e for e in eintraege if e["slot"] == "morning" and e["local_day"] == TAG.isoformat()]
    assert [e["outcome"] for e in morgens] == ["sent"], (
        f"AC-6: genau ein Vermerk (korsika, morning, {TAG}) mit Ausgang sent erwartet: {morgens}"
    )


def test_ac6_trip_fehlschlag_wird_im_naechsten_tick_nachgeholt_dann_nie_wieder():
    """AC-6 (Trip): der erste Tick ab 06:45 scheitert ohne Zustellung
    (``channels_unreachable`` -> Reservierung freigegeben), der naechste Tick
    (07:00) holt nach und hat Erfolg; danach im ganzen Fenster kein weiterer
    Versand.

    RED-Charakter: Fehlernachweis — heute liegen die Versuche bei 06:00 und
    06:15 (Stundenvergleich).
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    class _ErstFehlschlagDannErfolg(TripReportSchedulerService):
        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            self.versuche.append((trip.id, report_type))
            return self.ausgaenge.pop(0) if self.ausgaenge else "sent"

    user = "u2795-nachholen-trip"
    _schreibe(user, [_trip_json("korsika", *KORSIKA, TAGE, morning="06:45:00")])
    sched = _ErstFehlschlagDannErfolg(user_id=user)
    sched.versuche = []
    sched.ausgaenge = ["channels_unreachable", "sent"]

    zeiten = []
    for now in _ticks((5, 0), (10, 45)):
        vorher = len(sched.versuche)
        gesammelt = sched._collect_due_trips(now)
        for trip, rt, ortstag in gesammelt:
            if rt == "morning":
                sched._dispatch_due_item(trip, rt, ortstag, now_utc=now)
        if len(sched.versuche) > vorher:
            zeiten.append(_hhmm(now))

    assert zeiten == ["06:45", "07:00"], (
        "AC-6: erster Versuch beim Tick 06:45 (gescheitert), Nachholung beim "
        f"naechsten Tick 07:00, danach nie wieder — gefunden {zeiten}"
    )


# ───────────────────── AC-5/AC-7: Ortsvergleich ────────────────────────────

def _orte_korsika(user: str) -> dict:
    from app.loader import load_all_locations

    ordner = get_data_dir(user) / "locations"
    ordner.mkdir(parents=True, exist_ok=True)
    for ort_id in ("ort-a", "ort-b"):
        (ordner / f"{ort_id}.json").write_text(json.dumps({
            "id": ort_id, "name": f"Ort {ort_id}",
            "lat": KORSIKA[0], "lon": KORSIKA[1], "elevation_m": 100,
        }), encoding="utf-8")
    return {loc.id: loc for loc in load_all_locations(user_id=user)}


def _vergleich(user: str, morning: str, *, schreiben: bool = False) -> dict:
    preset = {
        "id": "vgl-2795", "kind": "vergleich", "name": "Korsika-Vergleich",
        "user_id": user, "schedule": "daily", "location_ids": ["ort-a", "ort-b"],
        "empfaenger": ["nutzer@example.com"],
        "morning_enabled": True, "morning_time": morning,
        "evening_enabled": False, "evening_time": "18:00:00",
    }
    if schreiben:
        ordner = get_briefings_dir(user)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "vgl-2795.json").write_text(json.dumps(preset), encoding="utf-8")
    return preset


@pytest.mark.parametrize("morning, ortszeit, erwartet", [
    ("06:45:00", (6, 30), False),
    ("06:45:00", (6, 45), True),
    ("06:45:00", (9, 44), True),
    ("06:45:00", (9, 46), False),
    ("07:00:00", (6, 45), False),   # AC-7 Regressionsschutz
    ("07:00:00", (7, 0), True),     # AC-7 Regressionsschutz
    ("07:00:00", (10, 0), False),   # AC-7 Regressionsschutz
])
def test_ac5_ac7_vergleich_faelligkeit_in_minuten(morning, ortszeit, erwartet):
    """AC-5/AC-7 (Ortsvergleich): ``presets_due_for_hour`` wertet die volle
    Slot-Uhrzeit in Minuten aus (Fenster 3 h). 07:00 verhaelt sich wie bisher.

    RED-Charakter: Fehlernachweis fuer die 06:45-Faelle (heute Stunde 6:
    06:30 faellig, 09:44 nicht); Regressionsschutz fuer die 07:00-Faelle.
    """
    from services.compare_slot_scheduler import presets_due_for_hour

    user = "u2795-faellig-vgl"
    orte = _orte_korsika(user)
    moment = _um(*ortszeit)
    due = presets_due_for_hour([_vergleich(user, morning)], orte, moment)
    ist = any(d.preset.get("id") == "vgl-2795" for d in due)
    assert ist is erwartet, (
        f"Ortsvergleich Slot {morning[:5]}, Ortszeit {_hhmm(moment)}: faellig={ist}, "
        f"erwartet {erwartet}"
    )


def test_ac5_ac6_vergleich_genau_ein_versand_um_0645_ueber_alle_ticks(monkeypatch):
    """AC-5 + AC-6 (Ortsvergleich): Slot 06:45, ``run_briefing_dispatch`` im
    15-Minuten-Takt von 05:00 bis 10:45 — genau EIN Versand, beim Tick 06:45;
    Vermerk in ``briefing_slots_compare.json``.

    Ersetzt ist nur ``send_one_compare_preset`` (Netz-Naht), Sammlung,
    Vermerk und Versandkette laufen echt (Muster T11 aus
    ``tests/tdd/test_briefing_slot_idempotenz.py``).

    RED-Charakter: Fehlernachweis — heute faellt der Versand auf 06:00.
    """
    from app.config import Settings
    from services import dispatch_orchestrator as orchestrator
    import services.scheduler_dispatch_service as sds

    user = "u2795-ticks-vgl"
    _orte_korsika(user)
    _vergleich(user, "06:45:00", schreiben=True)
    protokoll: list = []

    def _versand_ohne_netz(preset, *args, **kwargs):
        protokoll.append(preset.get("id"))
        return "Ort", ["empfaenger@example.invalid"]

    monkeypatch.setattr(sds, "send_one_compare_preset", _versand_ohne_netz)
    monkeypatch.setattr(orchestrator.CompareDispatchStrategy, "inter_mail_delay", 0.0)
    settings = Settings(is_test_mode=True)

    treffer = []
    for now in _ticks((5, 0), (10, 45)):
        vorher = len(protokoll)
        orchestrator.run_briefing_dispatch("vergleich", user, now, settings=settings)
        if len(protokoll) > vorher:
            treffer.append(_hhmm(now))

    assert treffer == ["06:45"], (
        "AC-5/AC-6 (Orte): Slot 06:45 genau einmal, beim ersten Tick ab 06:45 — "
        f"gefunden {treffer}"
    )
