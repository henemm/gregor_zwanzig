"""TDD RED — #1725: Briefing-Fälligkeit als Fenster + Idempotenz-Schlüssel.

Spec: docs/specs/modules/fix_1725_faelligkeit_und_idempotenz.md (AC-1..AC-14)
Kontext: docs/context/fix-1725-faelligkeit-idempotenz.md
ADR-0051 (Zeit als Parameter, Zone an den Daten), ADR-0044 (Ortstag, UTC-Vergleich)

Zielverhalten, gegen das hier durchgehend geprüft wird::

    fällig ⟺ konfigurierte_stunde <= ortsstunde < konfigurierte_stunde + 3
             UND kein Vermerk für (trip_id, ortstag, slot)

Vermerk gesetzt bei `sent`, `no_stage`, `no_weather`, `no_channels` — NICHT bei
`channels_unreachable` und nicht bei einer Ausnahme (reserve-then-release).

RED-Ursache vor dem Fix: `_collect_due_trips` vergleicht Stunden auf
GLEICHHEIT (`trip_report_scheduler.py:372,375`). Ein Ortstag hat aber nicht
immer 24 Stunden — am 29.03. fehlt eine Ortsstunde (Briefing entfällt), am
25.10. existiert sie zweimal (Briefing geht zweimal raus). Zusätzlich fehlt
heute jeder Idempotenz-Schutz: ein zweiter Lauf in derselben Stunde
(Neustart, manueller Trigger) sendet ungebremst erneut.

────────────────────────────────────────────────────────────────────────────
🔴 RED-Charakter je Test — Pflichtangabe (Auftrag Team-Lead)
────────────────────────────────────────────────────────────────────────────
Diese Datei schlägt in der RED-Phase VOLLSTÄNDIG fehl (das Modul
`services.briefing_slots` existiert nicht → Collection-Error). Das ist gültiges
RED, aber KEIN Beweis für die Fangkraft der einzelnen Tests. Jeder Test trägt
deshalb in seinem Docstring eine Zeile

    RED-Charakter: <Fehlernachweis|Mutations-Wächter> — rot bei: <Verfälschung>

Fehlernachweis = wäre auch ohne den Fix rot (misst den gemeldeten Defekt).
Mutations-Wächter = wäre heute zufällig grün; sein Wert liegt darin, NACH der
Implementierung rot zu werden, wenn ein Schlüsselglied entfällt, das Fenster
verstellt oder der Filter verschoben wird.

🔴 Die wichtigste Falle: bei funktionierendem Vermerk liefert JEDE
Fensterbreite an einem normalen Tag genau EINEN Treffer. Ein Test, der nur
Treffer zählt, kann die Fensterbreite nicht sehen. **T4 ist der einzige Test,
der beide Fenstergrenzen festnagelt.** Zwei Folgefallen, die hier bewusst
adressiert sind:
  * Die Mutation „Fälligkeit auf `<=` drehen" ergibt unter wirksamem Vermerk
    ebenfalls genau einen Treffer (bei Ortsstunde 00 statt 07). T3 prüft
    deshalb die STUNDE des Treffers, nicht nur deren Anzahl.
  * Die Mutationen „Slot / Trip-ID aus dem Schlüssel entfernen" sind an der
    Sammlung unsichtbar, weil beide Elemente in DERSELBEN Sammlung anfallen —
    der Vermerk entsteht erst beim Versand danach. T5/T7 zählen deshalb
    VERSANDVERSUCHE, nicht gesammelte Zeilen.

────────────────────────────────────────────────────────────────────────────
Schnittstellen-Entscheidungen (die GREEN-Phase richtet sich danach)
────────────────────────────────────────────────────────────────────────────
1. `services.briefing_slots.BriefingSlotStore(user_id: str)`
   * Speicher `get_data_dir(user_id)/briefing_slots.json`, Schema
     `{"entries": [{"trip_id", "slot", "local_day", "recorded_at", "outcome"}]}`,
     `local_day` als ISO-Datum (`YYYY-MM-DD`).
   * Sperr-Sidecar `briefing_slots.json.lock` (Muster `throttle_store`).
   * `LOCK_TIMEOUT_SECONDS` wird als MODUL-ATTRIBUT zur Laufzeit gelesen
     (`briefing_slots.LOCK_TIMEOUT_SECONDS`), damit ein Test die Frist kürzen
     kann; Default = `file_lock.LOCK_TIMEOUT_SECONDS` (2.0 s).
   * `is_recorded(trip_id, slot, local_day: date, zone=None) -> bool` —
     schließt die Rückwärts-Ableitung aus `briefing_log.json` ein (AC-9).
     `zone` (die Ortszone des Trips) entscheidet dabei, ob `sent_at` in
     `local_day` fällt; sie ist optional, weil nur der Scheduler sie kennt.
     Ohne `zone` wird `sent_at` gegen UTC ausgewertet.
   * `reserve(trip_id, slot, local_day, zone=None) -> bool` — True nur bei
     FRISCHER Reservierung. False, wenn bereits ein Vermerk/eine Reservierung
     besteht ODER die Sperre nicht zu bekommen war (fail-closed, AC-13).
   * `record_outcome(trip_id, slot, local_day, outcome: str) -> None`
   * `release(trip_id, slot, local_day) -> None` — nimmt die Reservierung
     zurück.
2. `TripReportSchedulerService._collect_due_trips(now_utc)` liefert
   `list[tuple[Trip, str, date]]`; drittes Element ist der ORTSTAG DES LAUFS
   (`trip_local_today(trip, now_utc)`), ausdrücklich nicht `target_date`.
3. `TripReportSchedulerService._dispatch_due_item(trip, report_type, local_day)`
   `-> str | None`: reserviert, sendet nur bei erfolgreicher Reservierung,
   vermerkt/entlässt je Ausgang, gibt den Ausgang zurück — bzw. `None`, wenn
   gar kein Versandversuch stattfand. Eine Ausnahme aus dem Versand wird nach
   dem `release` WEITERGEREICHT (`dispatch_one` fängt sie wie bisher).
4. `trip_report_scheduler.NACHHOL_FENSTER_STUNDEN = 3`.

────────────────────────────────────────────────────────────────────────────
Test-Politik (CLAUDE.md „Zwei Schichten")
────────────────────────────────────────────────────────────────────────────
Kern-Schicht, deterministisch: kein Netz, kein Postfach. Zeit wird
ausschließlich als PARAMETER hereingereicht (ADR-0051 Regel 3) — nie per Patch
auf die Systemuhr. Einzige Ausnahme ist T12, weil `send_on_demand_report`
konstruktionsbedingt keinen Zeitpunkt annimmt (`:905` liest dort seine eigene
Uhr; das gehört zu #1726 und wird hier nicht angefasst).

Kein Mock-Theater: Speicher, Schlüsselbildung, Fenster und Filter laufen
ECHT. Ersetzt wird an genau einer Stelle die Naht zum Netz — der Versand
selbst (`_send_trip_report_outcome`) — durch eine ECHTE Unterklasse, die einen
der fünf dokumentierten Ausgänge zurückgibt und ihre Aufrufe mitschreibt. Ihr
Rückgabewert ist die EINGABE der geprüften Entscheidung, nicht deren Ergebnis;
behauptet wird nichts, gemessen wird der Zustand des echten Speichers über die
echte Sammlung. Zwei Tests kommen ohne diese Naht aus und bewachen damit, dass
der Vermerk NICHT im Versand sitzt: T12 (On-Demand-Pfad, echter `no_stage`)
und T9 (reine Sammlung).

Ortstage werden von Ortsmitternacht zu Ortsmitternacht abgeschritten und die
Häufigkeit jeder einzelnen Ortsstunde gezählt — nicht Zeilen. ADR-0044-Falle:
zwei zeitzonenbehaftete Zeitpunkte mit demselben `tzinfo` subtrahieren sich auf
nackten Wanduhr-Werten (jeder Tag scheinbar 24,0 h); jeder Vergleich läuft
deshalb über `local_dt(dt, UTC)`, nie über rohes `.astimezone`.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from app.loader import get_briefings_dir, get_data_dir  # noqa: E402
from utils.timezone import UTC, local_dt  # noqa: E402

# Bewusst auf Modulebene: solange `services.briefing_slots` fehlt, ist die
# gesamte Datei ein Collection-Error — das RED ist damit unuebersehbar und
# nicht als Reihe einzelner AttributeErrors zu verwechseln.
from services import briefing_slots  # noqa: E402,F401  (T13 kuerzt die Sperrfrist)
from services.briefing_slots import BriefingSlotStore  # noqa: E402

# Koordinaten je Zone — echte Orte, damit TimezoneFinder sie auflöst.
KORSIKA = (42.30, 8.93)          # Europe/Paris
LORD_HOWE = (-31.5545, 159.0821)  # Australia/Lord_Howe (+10:30/+11:00)
# Adversary-Finding F002: eine Zone, deren ORTSTAG zur Briefing-Stunde vom
# UTC-Tag abweicht — 07:00 Ortszeit am 20.08. ist 2026-08-19T19:00Z.
AUCKLAND = (-36.85, 174.76)      # Pacific/Auckland (+12:00)

PARIS = ZoneInfo("Europe/Paris")
LORD_HOWE_TZ = ZoneInfo("Australia/Lord_Howe")
AUCKLAND_TZ = ZoneInfo("Pacific/Auckland")

# Die vier Ausgänge, die laut Spec einen Vermerk setzen, und der eine, der
# es nicht tut (Spec „Vermerk je Outcome").
VERMERK_AUSGAENGE = ("sent", "no_stage", "no_weather", "no_channels")
OHNE_VERMERK = "channels_unreachable"


# ---------------------------------------------------------------------------
# Aufbau-Helfer (Muster aus tests/tdd/test_briefing_faelligkeit_ortszone.py)
# ---------------------------------------------------------------------------

def _trip_json(trip_id: str, lat: float, lon: float, tage: list[date],
               morning: str | None = "07:00:00",
               evening: str | None = None) -> dict:
    """Trip mit je einer Etappe pro Datum, alle am selben Wegpunkt."""
    report_config: dict = {"enabled": True}
    if morning is not None:
        report_config["morning_time"] = morning
    if evening is not None:
        report_config["evening_time"] = evening
    return {
        "id": trip_id,
        "name": f"Trip {trip_id}",
        "stages": [
            {
                "id": f"{trip_id}-s{i}",
                "name": f"Etappe {i}",
                "date": d.isoformat(),
                "waypoints": [
                    {"id": f"{trip_id}-wp{i}a", "name": "Start",
                     "lat": lat, "lon": lon, "elevation_m": 800},
                    {"id": f"{trip_id}-wp{i}b", "name": "Ziel",
                     "lat": lat + 0.05, "lon": lon + 0.05, "elevation_m": 1200},
                ],
            }
            for i, d in enumerate(tage)
        ],
        "report_config": report_config,
    }


def _schreibe(user_id: str, trips: list[dict]) -> None:
    """Echte Trip-Dateien im isolierten Daten-Root (conftest `_isolate_data_root`).

    Mandantentrennung: jeder Test bekommt eine EIGENE, sprechende `user_id` —
    nie `"default"`.
    """
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    for t in trips:
        (ordner / f"{t['id']}.json").write_text(json.dumps(t), encoding="utf-8")


def _scheduler(user_id: str):
    from services.trip_report_scheduler import TripReportSchedulerService

    return TripReportSchedulerService(user_id=user_id)


def _sammlung(scheduler, now_utc: datetime) -> set[tuple[str, str]]:
    """Nur SAMMELN, nicht versenden — misst den Prüfort `_collect_due_trips`."""
    return {(t.id, rt) for t, rt, _ in scheduler._collect_due_trips(now_utc)}


def _lauf(scheduler, now_utc: datetime) -> list[tuple[str, str]]:
    """Ein vollständiger Sammellauf: sammeln, dann jedes fällige Element über
    den echten Wrapper abarbeiten — genau die Kette, die
    `run_briefing_dispatch` fährt (`collect_due` → Schleife über
    `dispatch_one`), ohne die 2s-Pause und ohne `pre_pass`.

    Rückgabe ist die GESAMMELTE Liste. Wer die Wirkung des Vermerks auf die
    Sammlung misst, prüft damit den Prüfort, den die Spec verlangt (Filter in
    `_collect_due_trips`, nicht erst im Versand).
    """
    gesammelt = list(scheduler._collect_due_trips(now_utc))
    for trip, report_type, ortstag in gesammelt:
        scheduler._dispatch_due_item(trip, report_type, ortstag)
    return [(t.id, rt) for t, rt, _ in gesammelt]


def _ortstag_schritte(zone: ZoneInfo, tag: date) -> Iterator[datetime]:
    """Schreitet den ORTSTAG stündlich von Ortsmitternacht zu Ortsmitternacht ab.

    Die Länge des Tages wird BERECHNET, nicht gesetzt (ADR-0044 `:46-49`):
    beide Ortsmitternachte werden über `local_dt(..., UTC)` nach UTC gebracht,
    erst dort wird verglichen. Ein Vergleich der beiden Wanduhr-Werte mit
    identischem `tzinfo` ergäbe an JEDEM Tag 24,0 h und würde die
    Umstellungstage genau verschlucken.
    """
    start = datetime(tag.year, tag.month, tag.day, 0, 0, tzinfo=zone)
    ende = start + timedelta(days=1)  # Wanduhr-Addition -> nächste Ortsmitternacht
    t = local_dt(start, UTC)
    grenze = local_dt(ende, UTC)
    while t < grenze:
        yield t
        t += timedelta(hours=1)


def _ortsstunde(now_utc: datetime, zone: ZoneInfo) -> int:
    return local_dt(now_utc, zone).hour


def _zeitpunkt(zone: ZoneInfo, tag: date, ortsstunde: int) -> datetime:
    """UTC-Zeitpunkt zu einer eindeutigen Ortsstunde des Ortstags."""
    return local_dt(datetime(tag.year, tag.month, tag.day, ortsstunde, 0, tzinfo=zone), UTC)


def _scheduler_mit_festem_ausgang(user_id: str, ausgang: str = "sent",
                                  ausnahme: BaseException | None = None):
    """Echter `TripReportSchedulerService`, bei dem AUSSCHLIESSLICH die Naht
    zum Netz ersetzt ist.

    Kein Mock: eine echte Unterklasse mit echter Implementierung. Sie gibt
    einen der fünf dokumentierten Ausgangs-Strings zurück (bzw. wirft eine echte
    Ausnahme) und schreibt jeden Aufruf mit. Alles, was geprüft wird — Fenster,
    Schlüsselbildung, Speicher, Filter —, läuft unverändert echt. Der
    Versandversuch selbst ist im deterministischen Kern-Testlauf ohnehin nicht
    ehrlich herstellbar: vier der fünf Ausgänge erfordern einen vollständigen
    Wetterabruf und einen Kanalversuch.
    """
    from services.trip_report_scheduler import TripReportSchedulerService

    class _SchedulerMitFestemAusgang(TripReportSchedulerService):
        versandversuche: list[tuple[str, str]] = []

        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            self.versandversuche.append((trip.id, report_type))
            if self.ausnahme is not None:
                raise self.ausnahme
            return self.ausgang

    scheduler = _SchedulerMitFestemAusgang(user_id=user_id)
    scheduler.versandversuche = []
    scheduler.ausgang = ausgang
    scheduler.ausnahme = ausnahme
    return scheduler


# ---------------------------------------------------------------------------
# AC-1 / T1 — Frühjahrs-Umstellung: der Slot fällt nicht mehr aus
# ---------------------------------------------------------------------------

def test_t1_fruehjahr_slot_faellt_nicht_mehr_aus():
    """Given Trip auf Korsika (Europe/Paris), Morgen-Briefing 02:00, Ortstag
    2026-03-29 (die Ortsstunde 02 existiert an diesem Tag nicht) / When der
    Ortstag von Ortsmitternacht zu Ortsmitternacht abgeschritten wird / Then
    ist der Trip GENAU EINMAL fällig, und zwar bei Ortsstunde 03
    (`3 >= 2 and 3 < 5`).

    RED-Charakter: Fehlernachweis — rot bei: heutiger Stundengleichheit
    (`>=` zurück auf `==`), dann entfällt der Versand ersatzlos (0 Treffer).
    """
    tage = [date(2026, 3, 28), date(2026, 3, 29), date(2026, 3, 30)]
    _schreibe("slot-t1", [_trip_json("korsika", *KORSIKA, tage, morning="02:00:00")])
    scheduler = _scheduler_mit_festem_ausgang("slot-t1")

    treffer = [
        now for now in _ortstag_schritte(PARIS, date(2026, 3, 29))
        if ("korsika", "morning") in _lauf(scheduler, now)
    ]

    assert len(treffer) == 1, (
        "Fruehjahrs-Umstellung: das auf 02:00 gestellte Briefing muss genau "
        f"einmal fallen, gefunden {len(treffer)} "
        f"({[local_dt(t, PARIS).isoformat() for t in treffer]}). 0 heisst: die "
        "nicht existierende Ortsstunde 02 laesst den Slot ersatzlos ausfallen."
    )
    assert _ortsstunde(treffer[0], PARIS) == 3, (
        "Die Ortsstunde 02 existiert am 29.03. nicht — der Nachhol-Treffer "
        f"gehoert auf Ortsstunde 03, gefunden {_ortsstunde(treffer[0], PARIS)}"
    )


# ---------------------------------------------------------------------------
# AC-2 / T2 — Herbst-Umstellung: keine Doppelzustellung
# ---------------------------------------------------------------------------

def test_t2_herbst_doppelstunde_sendet_nur_einmal():
    """Given derselbe Trip am Ortstag 2026-10-25 (die Ortsstunde 02 existiert
    zweimal) / When beide Vorkommen im Lauf durchschritten werden / Then wird
    der Trip GENAU EINMAL gesammelt — das erste Vorkommen setzt den Vermerk,
    das zweite wird durch ihn gefiltert.

    RED-Charakter: Fehlernachweis — rot bei: fehlendem Vermerk-Filter, dann
    geht das Briefing zweimal an echte Empfaenger (heutiger Zustand: 2).
    """
    tage = [date(2026, 10, 24), date(2026, 10, 25), date(2026, 10, 26)]
    _schreibe("slot-t2", [_trip_json("korsika", *KORSIKA, tage, morning="02:00:00")])
    scheduler = _scheduler_mit_festem_ausgang("slot-t2")

    treffer = [
        now for now in _ortstag_schritte(PARIS, date(2026, 10, 25))
        if ("korsika", "morning") in _lauf(scheduler, now)
    ]

    assert len(treffer) == 1, (
        "Herbst-Umstellung: die Ortsstunde 02 kommt zweimal vor — gesammelt "
        f"werden darf der Slot trotzdem nur einmal, gefunden {len(treffer)} "
        f"({[local_dt(t, PARIS).isoformat() for t in treffer]})."
    )
    assert _ortsstunde(treffer[0], PARIS) == 2, (
        f"Erwartet Ortsstunde 02, gefunden {_ortsstunde(treffer[0], PARIS)}"
    )
    # Gemessen wird ausschliesslich der MORGEN-Slot — AC-2 sagt die
    # Doppelstunde dieses Slots zu. `_trip_json(evening=None)` schaltet den
    # Abend-Slot NICHT ab: `loader.py:573` setzt `evening_time` per Default
    # auf 18:00, und dieser Lauf schreitet den vollen Ortstag ab, also faellt
    # der Abend-Slot um 18:00 Ortszeit an. Das ist unveraendertes
    # Bestandsverhalten und gehoert nicht zu dieser Zusicherung — wer hier
    # wieder auf `len(versandversuche)` zurueckbaut, misst den Abend-Slot mit.
    morgens = [v for v in scheduler.versandversuche if v[1] == "morning"]
    assert morgens == [("korsika", "morning")], (
        "Genau ein Versandversuch — der Vermerk muss den zweiten Durchlauf "
        f"der Doppelstunde stoppen, gefunden {scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-3 / T3 — normaler Tag: nur die konfigurierte Stunde trifft
# ---------------------------------------------------------------------------

def test_t3_normaler_tag_trifft_nur_die_konfigurierte_stunde():
    """Given Trip mit Morgen-Briefing 07:00 an einem Tag ohne Zeitumstellung /
    When jede der 24 Ortsstunden einzeln durchlaufen wird / Then trifft genau
    die Ortsstunde 07 und keine der uebrigen 23; und nach dem Versand meldet
    schon die SAMMLUNG den Slot in Ortsstunde 08 nicht mehr.

    Zweite Zusicherung = Pruefort gleich Wirkort: der Filter gehoert in
    `_collect_due_trips`, nicht erst in den Versand — sonst raeumt
    `_process_pending_markers` (`:445-448`) jede Stunde den #1012-Marker weg
    und legt den Nachliefermechanismus lautlos still.

    RED-Charakter: Mutations-Waechter — rot bei: Faelligkeit auf `<=` gedreht
    (dann trifft Ortsstunde 00 statt 07; die blosse ANZAHL bliebe wegen des
    Vermerks 1 und saehe die Verfaelschung nicht) sowie bei einem Filter, der
    erst im Versand statt in der Sammlung sitzt.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe("slot-t3", [_trip_json("korsika", *KORSIKA, tage, morning="07:00:00")])
    scheduler = _scheduler_mit_festem_ausgang("slot-t3")

    treffer = [
        now for now in _ortstag_schritte(PARIS, date(2026, 8, 20))
        if ("korsika", "morning") in _lauf(scheduler, now)
    ]

    assert [_ortsstunde(t, PARIS) for t in treffer] == [7], (
        "An einem normalen Tag muss genau die konfigurierte Ortsstunde 07 "
        f"treffen, gefunden {[_ortsstunde(t, PARIS) for t in treffer]}"
    )

    # Prüfort = Wirkort: der Vermerk wirkt bereits auf die Sammlung.
    acht_uhr = _zeitpunkt(PARIS, date(2026, 8, 20), 8)
    assert ("korsika", "morning") not in _sammlung(scheduler, acht_uhr), (
        "In Ortsstunde 08 liegt der Slot noch im Nachhol-Fenster, ist aber "
        "bereits vermerkt — die SAMMLUNG darf ihn nicht mehr melden. Sitzt der "
        "Filter erst im Versand, raeumt `_process_pending_markers` jede Stunde "
        "den Nachliefer-Marker weg."
    )


# ---------------------------------------------------------------------------
# AC-4 / T4 — Nachhol-Fenster, BEIDE Grenzen zugleich
# ---------------------------------------------------------------------------

def test_t4_nachhol_fenster_faengt_h_plus_1_und_endet_vor_h_plus_3():
    """Given die Slot-Stunde H faellt aus, weil der stuendliche Tick nicht lief
    (Umstellungstag oder gescheiterter HTTP-Post ohne Retry,
    `scheduler.go:547`) / When der naechste Lauf in Ortsstunde H+1 stattfindet
    / Then ist der Trip nachtraeglich faellig; findet er erst in Ortsstunde
    H+3 statt, ist er NICHT mehr faellig.

    🔴 Der EINZIGE Test, der die Fensterbreite in beide Richtungen festnagelt.
    Bei wirksamem Vermerk liefert jede Fensterbreite an einem normalen Tag
    genau einen Treffer — sichtbar wird die Breite nur an einem AUSGELASSENEN
    Lauf. Der Lauf zur Stunde H findet hier deshalb bewusst NICHT statt.

    Adversary-Finding F001: H+1 und H+3 allein nageln die Breite NICHT fest —
    beide Aussagen gelten auch bei Fensterbreite 2, und die Mutation 3 -> 2
    liess die gesamte Suite gruen. Teil 1b prueft deshalb Ortsstunde H+2, den
    einzigen Wert, der 3 von 2 unterscheidet. Der PO hat die drei Stunden
    ausdruecklich freigegeben; ohne diese Messung koennte ein spaeterer Umbau
    sie unbemerkt verengen, und der zweite ausgefallene Tick fiele still aus.

    RED-Charakter: Mutations-Waechter — rot bei: Fenster 3 -> 1 (dann ist H+1
    nicht mehr faellig, erster Teil rot), Fenster 3 -> 2 (dann ist H+2 nicht
    mehr faellig, Teil 1b rot) UND bei Fenster 3 -> „bis Tagesende" (dann ist
    H+3 noch faellig, zweiter Teil rot).
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    tag = date(2026, 8, 20)

    # Teil 1: Stunde 07 ausgelassen, erster Lauf um 08 Ortszeit.
    _schreibe("slot-t4a", [_trip_json("korsika", *KORSIKA, tage, morning="07:00:00")])
    nachzuegler = _scheduler("slot-t4a")
    assert ("korsika", "morning") in _sammlung(
        nachzuegler, _zeitpunkt(PARIS, tag, 8)
    ), (
        "Der Tick zur Ortsstunde 07 ist ausgefallen — in Ortsstunde 08 muss "
        "der Slot nachgeholt werden. Ist er es nicht, ist das Nachhol-Fenster "
        "kleiner als 2 Stunden und faengt den an Umstellungstagen "
        "ausfallenden Cron-Tick nicht."
    )

    # Teil 1b (F001): Stunden 07 UND 08 ausgelassen, erster Lauf um 09
    # Ortszeit. Diese Stunde unterscheidet Fensterbreite 3 von Breite 2 —
    # `7 <= 9 < 10` trifft, `7 <= 9 < 9` nicht.
    _schreibe("slot-t4c", [_trip_json("korsika", *KORSIKA, tage, morning="07:00:00")])
    zweiter_nachzuegler = _scheduler("slot-t4c")
    assert ("korsika", "morning") in _sammlung(
        zweiter_nachzuegler, _zeitpunkt(PARIS, tag, 9)
    ), (
        "Zwei Ticks in Folge ausgefallen (07 und 08) — in Ortsstunde 09 muss "
        "der Slot noch nachgeholt werden. Ist er es nicht, ist das Fenster auf "
        "zwei Stunden verengt und deckt nur EINEN ausgefallenen Tick ab, "
        "obwohl der PO drei Stunden freigegeben hat."
    )

    # Teil 2: Stunden 07, 08, 09 ausgelassen, erster Lauf um 10 Ortszeit.
    _schreibe("slot-t4b", [_trip_json("korsika", *KORSIKA, tage, morning="07:00:00")])
    zu_spaet = _scheduler("slot-t4b")
    assert ("korsika", "morning") not in _sammlung(
        zu_spaet, _zeitpunkt(PARIS, tag, 10)
    ), (
        "Ortsstunde 10 liegt DREI Stunden hinter der konfigurierten 07 und "
        "damit ausserhalb des Fensters (`7 <= 10 < 10` ist falsch). Ein "
        "Morgen-Briefing, das noch bis Tagesende nachgeholt wird, kaeme um "
        "23:00 Ortszeit an und liesse neu angelegte oder aus `paused_until` "
        "zurueckkehrende Trips rueckwirkend feuern."
    )


# ---------------------------------------------------------------------------
# AC-5 / T5 — der Schlüssel braucht den Slot
# ---------------------------------------------------------------------------

def test_t5_schluessel_ohne_slot_wuerde_den_zweiten_slot_verschlucken():
    """Given ein Trip mit Morgen- UND Abend-Briefing, beide auf 07:00 / When
    die Ortsstunde 07 erreicht wird / Then werden BEIDE Slots unabhaengig
    voneinander versendet und unabhaengig vermerkt.

    Gezaehlt werden VERSANDVERSUCHE, nicht gesammelte Zeilen: beide Slots
    fallen in DERSELBEN Sammlung an, der Vermerk des ersten entsteht erst beim
    Versand danach. Eine an der Sammlung gemessene Zusicherung koennte einen
    slotlosen Schluessel nicht sehen.

    RED-Charakter: Mutations-Waechter — rot bei: `slot` aus dem Schluessel
    entfernt; dann scheitert die Reservierung des zweiten Slots am Vermerk des
    ersten und nur einer wird gesendet.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe("slot-t5", [_trip_json(
        "korsika", *KORSIKA, tage, morning="07:00:00", evening="07:00:00",
    )])
    scheduler = _scheduler_mit_festem_ausgang("slot-t5")

    _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 7))

    assert sorted(scheduler.versandversuche) == [
        ("korsika", "evening"), ("korsika", "morning"),
    ], (
        "Morgen- und Abend-Slot sind zwei verschiedene Schluessel und muessen "
        "beide gesendet werden. Gefunden: "
        f"{sorted(scheduler.versandversuche)} — fehlt einer, traegt der "
        "Idempotenz-Schluessel den Slot nicht."
    )


# ---------------------------------------------------------------------------
# AC-6 / T6 — der Schlüssel braucht den Ortstag
# ---------------------------------------------------------------------------

def test_t6_schluessel_ohne_ortstag_wuerde_den_folgetag_verstummen_lassen():
    """Given ein Trip, dessen Morgen-Briefing an zwei aufeinanderfolgenden
    Ortstagen faellig wird / When der Lauf an beiden Tagen ausgefuehrt wird /
    Then ist er an beiden Tagen faellig — der Vermerk vom Vortag blockiert den
    neuen Tag nicht.

    RED-Charakter: Mutations-Waechter — rot bei: `local_day` aus dem
    Schluessel entfernt; dann bleibt Tag 2 stumm und der Nutzer bekommt nach
    dem ersten Briefing nie wieder eines.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21), date(2026, 8, 22)]
    _schreibe("slot-t6", [_trip_json("korsika", *KORSIKA, tage, morning="07:00:00")])
    scheduler = _scheduler_mit_festem_ausgang("slot-t6")

    tag1 = _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 7))
    tag2 = _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 21), 7))

    assert ("korsika", "morning") in tag1, "Tag 1 muss faellig sein"
    assert ("korsika", "morning") in tag2, (
        "Tag 2 muss ebenfalls faellig sein — der Vermerk vom Vortag darf den "
        "neuen Ortstag nicht blockieren. Fehlt der Ortstag im Schluessel, "
        "verstummt das Briefing nach dem ersten Versand dauerhaft."
    )
    assert len(scheduler.versandversuche) == 2, (
        f"Zwei Ortstage, zwei Versandversuche — gefunden {scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-7 / T7 — der Schlüssel braucht die Trip-ID
# ---------------------------------------------------------------------------

def test_t7_schluessel_ohne_trip_id_wuerde_den_zweiten_trip_verschlucken():
    """Given zwei verschiedene Trips desselben Nutzers in derselben Zone mit
    identischer Briefing-Stunde / When diese Ortsstunde erreicht wird / Then
    werden BEIDE gesendet und unabhaengig vermerkt.

    Auch hier werden VERSANDVERSUCHE gezaehlt: beide Trips fallen in derselben
    Sammlung an, der Vermerk entsteht erst danach.

    RED-Charakter: Mutations-Waechter — rot bei: `trip_id` aus dem Schluessel
    entfernt; dann nimmt der erste Trip dem zweiten sein Briefing weg.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe("slot-t7", [
        _trip_json("korsika-nord", *KORSIKA, tage, morning="07:00:00"),
        _trip_json("korsika-sued", *KORSIKA, tage, morning="07:00:00"),
    ])
    scheduler = _scheduler_mit_festem_ausgang("slot-t7")

    _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 7))

    assert sorted(scheduler.versandversuche) == [
        ("korsika-nord", "morning"), ("korsika-sued", "morning"),
    ], (
        "Zwei Trips zur selben Stunde sind zwei verschiedene Schluessel. "
        f"Gefunden: {sorted(scheduler.versandversuche)} — fehlt einer, traegt "
        "der Idempotenz-Schluessel die Trip-Kennung nicht."
    )


# ---------------------------------------------------------------------------
# AC-8 / T8 — die Outcome-Matrix entscheidet über den Vermerk
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ausgang", VERMERK_AUSGAENGE)
def test_t8_vier_ausgaenge_setzen_den_vermerk(ausgang: str):
    """Given ein Versandversuch endet mit `sent`, `no_stage`, `no_weather`
    oder `no_channels` / When die naechste Stunde INNERHALB des Nachhol-
    Fensters laeuft / Then wird der Slot nicht erneut verarbeitet.

    RED-Charakter: Mutations-Waechter — rot bei: einem der vier Ausgaenge aus
    der Vermerk-Menge entfernt; dann laeuft der Slot in den verbleibenden
    Fensterstunden erneut (bei `no_weather`: stuendliche „keine Daten"-Mail +
    stuendlicher voller Wetterabruf gegen das Kontingent #1329, und der
    #1012-Nachliefer-Marker wird jede Stunde weggeraeumt).
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    user = f"slot-t8-{ausgang}"
    _schreibe(user, [_trip_json("korsika", *KORSIKA, tage, morning="07:00:00")])
    scheduler = _scheduler_mit_festem_ausgang(user, ausgang=ausgang)

    erste = _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 7))
    zweite = _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 8))

    assert ("korsika", "morning") in erste, "Stunde 07 muss faellig sein"
    assert ("korsika", "morning") not in zweite, (
        f"Ausgang '{ausgang}' setzt laut Spec einen Vermerk — in Stunde 08 "
        "(noch im Nachhol-Fenster) darf der Slot nicht erneut verarbeitet werden."
    )
    assert len(scheduler.versandversuche) == 1, (
        f"Genau ein Versandversuch bei Ausgang '{ausgang}', gefunden "
        f"{scheduler.versandversuche}"
    )


def test_t8_channels_unreachable_haelt_den_slot_offen():
    """Given ein Versandversuch endet mit `channels_unreachable` / When die
    naechste Stunde innerhalb des Nachhol-Fensters laeuft / Then unternimmt
    der Lauf einen weiteren Versuch — per Definition
    (`sent = bool(sent_channels)`) hat niemand etwas bekommen.

    RED-Charakter: Mutations-Waechter — rot bei: `channels_unreachable` in die
    Vermerk-Menge geschoben; dann bleibt der einzige beabsichtigte Nachholfall
    still.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe("slot-t8-offen", [
        _trip_json("korsika", *KORSIKA, tage, morning="07:00:00"),
    ])
    scheduler = _scheduler_mit_festem_ausgang("slot-t8-offen", ausgang=OHNE_VERMERK)

    _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 7))
    zweite = _lauf(scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 8))

    assert ("korsika", "morning") in zweite, (
        "Bei 'channels_unreachable' hat niemand etwas bekommen — der naechste "
        "Lauf im Fenster muss es erneut versuchen."
    )
    assert len(scheduler.versandversuche) == 2, (
        f"Zwei Versuche erwartet, gefunden {scheduler.versandversuche}"
    )


def test_t8_ausnahme_nimmt_die_reservierung_zurueck():
    """Given der Versand wirft eine Ausnahme / When die naechste Stunde
    innerhalb des Fensters laeuft / Then ist der Slot erneut faellig — die
    Reservierung wird durch reserve-then-release zurueckgenommen, und die
    Ausnahme erreicht unveraendert den Aufrufer (`dispatch_one` faengt sie).

    RED-Charakter: Mutations-Waechter — rot bei: `release` im Ausnahmepfad
    entfernt (dann bleibt der Slot als vermerkt stehen, obwohl nichts
    passiert ist) oder bei einem Wrapper, der die Ausnahme schluckt und damit
    die Fehlerzaehlung in `dispatch_one` still auf Erfolg dreht.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe("slot-t8-ausnahme", [
        _trip_json("korsika", *KORSIKA, tage, morning="07:00:00"),
    ])
    scheduler = _scheduler_mit_festem_ausgang(
        "slot-t8-ausnahme", ausnahme=RuntimeError("Kanal wirft"),
    )

    trip, report_type, ortstag = scheduler._collect_due_trips(
        _zeitpunkt(PARIS, date(2026, 8, 20), 7)
    )[0]
    with pytest.raises(RuntimeError):
        scheduler._dispatch_due_item(trip, report_type, ortstag)

    assert ("korsika", "morning") in _sammlung(
        scheduler, _zeitpunkt(PARIS, date(2026, 8, 20), 8)
    ), (
        "Nach einer Ausnahme darf kein Vermerk zurueckbleiben — der Slot muss "
        "im Nachhol-Fenster erneut faellig sein."
    )


# ---------------------------------------------------------------------------
# AC-9 / T9 — Rollout ohne Doppelversand beim Deploy
# ---------------------------------------------------------------------------

def test_t9_rueckwaerts_ableitung_aus_dem_briefing_log():
    """Given `briefing_slots.json` existiert noch nicht (frischer Rollout),
    aber `briefing_log.json` traegt fuer den Trip einen Eintrag mit passender
    Slot-Art, dessen `sent_at` in den aktuellen Ortstag faellt / When die
    Faelligkeit geprueft wird / Then gilt der Slot als erledigt.

    Gegenprobe im selben Test: liegt derselbe Eintrag am VORTAG, ist der Slot
    faellig. Ohne diese Gegenprobe koennte „nicht faellig" auch aus einem
    kaputten Aufbau stammen.

    Der Speicher wird hier bewusst NICHT ueber die Sammlung befuellt: geprueft
    wird die Rueckwaerts-Ableitung selbst, also der Zustand direkt nach einem
    Deploy mitten im Nachhol-Fenster.

    Teil c (Adversary-Finding F002) prueft, dass die Ableitung `sent_at` im
    ORTSTAG des Trips auswertet und nicht in UTC: In `Europe/Paris` liegen
    Ortstag und UTC-Tag zur Stunde 07 auf demselben Datum, die Zone ist am
    Ergebnis also gar nicht ablesbar — beide Verfaelschungen (Zone nicht
    durchgereicht, `zone or UTC` hart auf UTC) blieben mit den Teilen a/b
    gruen. In `Pacific/Auckland` faellt 07:00 Ortszeit am 20.08. auf
    `2026-08-19T19:00Z`, also einen ANDEREN UTC-Tag.

    RED-Charakter: Mutations-Waechter — rot bei: Rueckwaerts-Ableitung
    entfernt (dann bekommt jeder Nutzer, dessen Briefing kurz vor dem Deploy
    rausging, es im Fenster ein zweites Mal) und, fuer Teil c, bei fehlender
    Zonen-Durchreichung bzw. UTC-Auswertung von `sent_at`.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    tag = date(2026, 8, 20)
    sieben_uhr = _zeitpunkt(PARIS, tag, 7)

    def _mit_log(user: str, sent_at: datetime,
                 koordinaten: tuple[float, float] = KORSIKA) -> None:
        _schreibe(user, [_trip_json("korsika", *koordinaten, tage, morning="07:00:00")])
        pfad = get_data_dir(user) / "briefing_log.json"
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(json.dumps({"entries": [{
            "trip_id": "korsika",
            "kind": "morning",
            "sent_at": sent_at.isoformat(),
            "channels": ["email"],
        }]}), encoding="utf-8")

    # a) Eintrag aus DIESEM Ortstag -> Slot gilt als erledigt.
    _mit_log("slot-t9-heute", _zeitpunkt(PARIS, tag, 7))
    assert not (get_data_dir("slot-t9-heute") / "briefing_slots.json").exists(), (
        "Testaufbau prueft nichts: der eigene Speicher darf hier noch nicht "
        "existieren, sonst greift die Rueckwaerts-Ableitung gar nicht."
    )
    assert ("korsika", "morning") not in _sammlung(
        _scheduler("slot-t9-heute"), sieben_uhr
    ), (
        "briefing_log.json weist den Versand dieses Ortstags bereits nach — "
        "ohne eigenen Vermerk muss die Rueckwaerts-Ableitung greifen, sonst "
        "sendet der erste Lauf nach dem Deploy ein zweites Mal."
    )

    # b) Gegenprobe: derselbe Eintrag vom Vortag blockiert nicht.
    _mit_log("slot-t9-gestern", _zeitpunkt(PARIS, tag - timedelta(days=1), 7))
    assert ("korsika", "morning") in _sammlung(
        _scheduler("slot-t9-gestern"), sieben_uhr
    ), (
        "Ein Eintrag vom VORTAG darf den heutigen Slot nicht blockieren — "
        "sonst faellt das Briefing nach dem ersten Tag dauerhaft aus."
    )

    # c) F002: Zone, deren Ortstag zur Briefing-Stunde vom UTC-Tag abweicht.
    #    07:00 Ortszeit am 20.08. in Auckland ist 2026-08-19T19:00Z — wer
    #    `sent_at` gegen UTC statt gegen den Ortstag auswertet, findet den
    #    Eintrag nicht und sendet nach dem Deploy ein zweites Mal.
    auckland_sieben_uhr = _zeitpunkt(AUCKLAND_TZ, tag, 7)
    assert local_dt(auckland_sieben_uhr, UTC).date() != tag, (
        "Testaufbau prueft nichts: UTC-Tag und Ortstag muessen hier "
        f"auseinanderfallen, gefunden {local_dt(auckland_sieben_uhr, UTC).date()}"
    )
    _mit_log("slot-t9-auckland", auckland_sieben_uhr, koordinaten=AUCKLAND)
    assert ("korsika", "morning") not in _sammlung(
        _scheduler("slot-t9-auckland"), auckland_sieben_uhr
    ), (
        "Der Log-Eintrag liegt im ORTSTAG des Trips (20.08. Auckland), auch "
        "wenn sein UTC-Tag der 19.08. ist. Wird `sent_at` gegen UTC statt "
        "gegen den Ortstag ausgewertet — oder die Zone gar nicht erst "
        "durchgereicht —, greift die Rueckwaerts-Ableitung fuer jeden Trip "
        "oestlich von etwa UTC+8 und westlich von etwa UTC-5 nicht mehr."
    )


# ---------------------------------------------------------------------------
# AC-10 / T10 — kein rückwirkendes Feuern bei neuen/reaktivierten Trips
# ---------------------------------------------------------------------------

def test_t10_neuer_trip_feuert_nicht_rueckwirkend():
    """Given ein Trip wird neu angelegt (oder kehrt aus `paused_until`
    zurueck), seine erste Etappe liegt heute, die konfigurierte Morgen-Stunde
    liegt aber mehr als 3 Stunden zurueck / When der erste Sammellauf danach
    stattfindet / Then ist er NICHT faellig.

    `_get_active_trips` (`:656-657`) prueft nur die Etappe, nicht das
    Anlagedatum — das Nachhol-Fenster ist der einzige Mechanismus, der diesen
    Fall ausschliesst.

    RED-Charakter: Mutations-Waechter — rot bei: Fenster auf „bis Tagesende"
    geoeffnet; dann bekommt jeder frisch angelegte Trip sofort ein Briefing,
    das auf eine laengst vergangene Uhrzeit datiert ist.
    """
    tag = date(2026, 8, 20)
    _schreibe("slot-t10", [_trip_json(
        "frisch", *KORSIKA, [tag, tag + timedelta(days=1)], morning="07:00:00",
    )])
    scheduler = _scheduler("slot-t10")

    assert ("frisch", "morning") not in _sammlung(
        scheduler, _zeitpunkt(PARIS, tag, 20)
    ), (
        "Ortsstunde 20 liegt 13 Stunden hinter der konfigurierten 07 — ein "
        "gerade erst angelegter Trip darf sein Morgen-Briefing nicht "
        "rueckwirkend bekommen."
    )


# ---------------------------------------------------------------------------
# AC-11 / T11 — der Ortsvergleich bleibt bit-identisch
# ---------------------------------------------------------------------------

def _compare_preset_schreiben(user_id: str, stunde: int) -> None:
    """Echtes Vergleichs-Preset in `briefings/` (Cutover-Lesepfad #1250 S7b)."""
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "vgl-1.json").write_text(json.dumps({
        "id": "vgl-1",
        "kind": "vergleich",
        "name": "Alpen vs Voralpen",
        "user_id": user_id,
        "schedule": "daily",
        "location_ids": ["ort-a", "ort-b"],
        "empfaenger": ["nutzer@example.com"],
        "morning_enabled": True,
        "morning_time": f"{stunde:02d}:00:00",
        "evening_enabled": False,
        "evening_time": "18:00:00",
    }), encoding="utf-8")


def test_t11_ortsvergleich_kennt_keinen_vermerk(monkeypatch):
    """Given der Ortsvergleichs-Pfad mit unveraenderter Konfiguration / When
    derselbe Versandlauf ueber 24 Stunden ausgefuehrt wird / Then feuert das
    Preset genau zur konfigurierten Stunde der festen Vergleichs-Zone — und
    ein ZWEITER Lauf in derselben Stunde feuert erneut.

    Der zweite Lauf ist der eigentliche Waechter: der Idempotenz-Schutz darf
    ausschliesslich im Trip-Pfad wirken. Gemessen wird ueber das GETEILTE
    Skelett `run_briefing_dispatch`, nicht nur ueber `collect_due` — ein Hook
    im Skelett (etwa `already_sent(item)` vor `dispatch_one`) waere an
    `collect_due` allein unsichtbar. Ersetzt ist nur `dispatch_one` (die Naht
    zum echten Vergleichs-Versand), `collect_due` und `pre_pass` laufen echt.

    RED-Charakter: Mutations-Waechter — rot bei: Vermerk-Filter ins geteilte
    Skelett `run_briefing_dispatch` verschoben oder in eine gemeinsame
    Basisklasse beider Strategien gezogen; dann verstummt der zweite Lauf und
    der Ortsvergleich hat vor #1726 still seine Faelligkeit geaendert.
    """
    from app.config import Settings
    from services import dispatch_orchestrator as orchestrator

    _compare_preset_schreiben("slot-t11", 9)
    protokoll: list = []

    class _MitgeschriebenerVergleich(orchestrator.CompareDispatchStrategy):
        def dispatch_one(self, item) -> None:
            protokoll.append(item[0].get("id"))

    monkeypatch.setitem(orchestrator._STRATEGY, "vergleich", _MitgeschriebenerVergleich)
    zone = ZoneInfo(orchestrator.CompareDispatchStrategy.NOCH_NICHT_ORTSZEIT_SIEHE_1726)
    settings = Settings(is_test_mode=True)

    stunden_mit_versand = []
    for now in _ortstag_schritte(zone, date(2026, 8, 20)):
        vorher = len(protokoll)
        orchestrator.run_briefing_dispatch("vergleich", "slot-t11", now, settings=settings)
        if len(protokoll) > vorher:
            stunden_mit_versand.append(_ortsstunde(now, zone))

    assert stunden_mit_versand == [9], (
        "Der Ortsvergleich muss unveraendert genau zur konfigurierten Stunde "
        f"seiner festen Zone feuern, gefunden {stunden_mit_versand}"
    )

    # Zweiter Lauf in derselben Stunde: Compare kennt keinen Vermerk.
    vorher = len(protokoll)
    orchestrator.run_briefing_dispatch(
        "vergleich", "slot-t11", _zeitpunkt(zone, date(2026, 8, 20), 9), settings=settings,
    )
    assert len(protokoll) == vorher + 1, (
        "Ein zweiter Lauf in derselben Stunde muss den Vergleich erneut "
        "versenden — der Idempotenz-Schutz aus #1725 gehoert ausschliesslich "
        "in den Trip-Pfad, nicht ins geteilte Skelett (#1726, AC-8 aus #1724)."
    )


# ---------------------------------------------------------------------------
# AC-12 / T12 — On-Demand-Versand ist vom Vermerk unabhängig
# ---------------------------------------------------------------------------

def test_t12_on_demand_schreibt_keinen_vermerk_und_liest_keinen(caplog):
    """Given ein Nutzer fordert per SMS-Kommando ein Briefing ausserhalb des
    regulaeren Slots an / When dieser On-Demand-Versand laeuft / Then setzt er
    KEINEN Vermerk fuer den regulaeren Slot und liest auch KEINEN.

    🔴 Dieser Test kommt bewusst OHNE die Versand-Naht aus: `send_on_demand_
    report` laeuft in den ECHTEN `_send_trip_report_outcome` und erreicht dort
    ehrlich den Ausgang `no_stage` (frueher Return vor jedem Wetterabruf, kein
    Netz). Genau dadurch faengt er die Verfaelschung, die eine Unterklasse
    verdecken wuerde.

    Zeit: `send_on_demand_report` nimmt konstruktionsbedingt keinen Zeitpunkt
    an (`:905` liest dort seine eigene Uhr — bekannte Drift, gehoert zu #1726).
    Der Ortstag wird deshalb ueber dieselbe Ableitung wie im Produktivcode
    (`trip_local_today`) aus der aktuellen Uhr bestimmt.

    RED-Charakter: Mutations-Waechter — rot bei: Vermerk in
    `_send_trip_report_outcome` statt im Wrapper `_dispatch_due_item` gesetzt
    (dann nimmt eine SMS-Anfrage dem Nutzer sein regulaeres Briefing weg) und
    rot bei einem On-Demand-Pfad, der den Vermerk LIEST (dann ist der
    Test-Knopf nach dem regulaeren Versand tot).
    """
    from app.loader import load_all_trips
    from services.trip_day import trip_local_today

    jetzt = datetime.now(timezone.utc)
    _schreibe("slot-t12", [_trip_json(
        "korsika", *KORSIKA, [local_dt(jetzt, PARIS).date() - timedelta(days=1)],
        morning="07:00:00", evening="18:00:00",
    )])
    trip = load_all_trips(user_id="slot-t12")[0]
    ortstag = trip_local_today(trip, jetzt)
    scheduler = _scheduler("slot-t12")
    store = BriefingSlotStore("slot-t12")

    # a) Der On-Demand-Versand endet ehrlich mit `no_stage` — einem Ausgang,
    #    der im REGULAEREN Pfad einen Vermerk setzt.
    assert scheduler.send_on_demand_report(trip, "evening") == "no_stage", (
        "Testaufbau prueft nichts: der On-Demand-Versand muss hier ohne Netz "
        "im Ausgang 'no_stage' enden."
    )
    assert not store.is_recorded("korsika", "evening", ortstag), (
        "Ein per SMS angefordertes Briefing darf dem Nutzer sein regulaeres "
        "nicht wegnehmen — der On-Demand-Pfad setzt keinen Vermerk. Steht hier "
        "einer, sitzt er in `_send_trip_report_outcome` statt im Wrapper."
    )

    # b) Ein bestehender Vermerk macht den Test-Knopf nicht tot.
    assert store.reserve("korsika", "evening", ortstag), (
        "Testaufbau prueft nichts: die Reservierung muss frisch gelingen."
    )
    store.record_outcome("korsika", "evening", ortstag, "sent")
    assert store.is_recorded("korsika", "evening", ortstag), (
        "Testaufbau prueft nichts: der Vermerk muss nach `record_outcome` stehen."
    )

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="trip_report_scheduler"):
        ergebnis = scheduler.send_on_demand_report(trip, "evening")

    assert ergebnis == "no_stage", (
        "Der On-Demand-Versand muss trotz bestehendem Vermerk denselben "
        f"ehrlichen Ausgang liefern, gefunden {ergebnis!r}"
    )
    assert any("Generating evening report" in eintrag.getMessage()
               for eintrag in caplog.records), (
        "Der On-Demand-Pfad ist gar nicht erst in den Versand eingetreten — "
        "er liest offenbar den Vermerk. Damit waere der Test-Versand-Knopf "
        "nach dem regulaeren Briefing des Tages tot (#695)."
    )


# Alle Transport-Felder ausdruecklich unbrauchbar: `Settings()` faellt bei
# fehlenden Feldern still auf die Prod-`.env` im Worktree zurueck (#1477).
# SMTP ist vollstaendig, aber auf einen nicht existierenden Host gesetzt — der
# Transportrand selbst wird unten durch eine aufzeichnende Funktion ersetzt.
_TOTE_TRANSPORT_FELDER: dict = {
    "smtp_host": "dummy.invalid", "smtp_user": "dummy", "smtp_pass": "dummy",
    "mail_to": "dummy@example.com",
    "telegram_bot_token": "", "telegram_chat_id": "",
    "telegram_test_bot_token": "", "telegram_test_chat_id": "",
    "sms_gateway_url": "", "seven_api_key": "", "sms_to": "",
}


def _zustellbare_settings():
    """Echte `Settings`: E-Mail sendefaehig, Telegram/SMS nachweislich nicht."""
    from app.config import Settings

    settings = Settings(**_TOTE_TRANSPORT_FELDER)
    assert settings.can_send_email() is True, (
        "Vorbedingung: ohne sendefaehigen Kanal endet der Versand in "
        "'no_channels' und erreicht den briefing_log-Eintrag nie."
    )
    # Sicherung (#1477): kein Kanal, der echte Nachrichten ausloesen koennte.
    assert settings.can_send_telegram() is False
    assert settings.can_send_sms() is False
    return settings


def _scheduler_mit_fixture_wetter(user_id: str, settings):
    """Echter Scheduler, bei dem NUR der Wetterabruf aus einer Fixture kommt —
    Haus-Muster `_FixtureScheduler` aus
    `tests/tdd/test_briefing_anchor_survives_dispatch_failure.py:226`.

    Kein Mock: eine echte Unterklasse, die `_fetch_weather` durch echte
    `SegmentWeatherData`-Objekte beantwortet. Alles danach — Rendering,
    Kanalauswahl, `_append_briefing_log` — laeuft unveraendert echt.
    """
    from app.models import (
        ForecastMeta,
        NormalizedTimeseries,
        Provider,
        SegmentWeatherData,
        SegmentWeatherSummary,
    )
    from services.trip_report_scheduler import TripReportSchedulerService

    class _MitFixtureWetter(TripReportSchedulerService):
        def _fetch_weather(self, segments, provider=None):
            return [
                SegmentWeatherData(
                    segment=s,
                    timeseries=NormalizedTimeseries(
                        meta=ForecastMeta(
                            provider=Provider.OPENMETEO, model="test", grid_res_km=1.0,
                        ),
                        data=[],
                    ),
                    aggregated=SegmentWeatherSummary(),
                    fetched_at=datetime.now(timezone.utc),
                    provider="openmeteo",
                )
                for s in segments
            ]

    return _MitFixtureWetter(settings=settings, user_id=user_id)


def _aufzeichnender_mailversand(monkeypatch) -> list:
    """Ersetzt den Transportrand `EmailOutput.send` durch eine echte,
    aufzeichnende Funktion (Haus-Muster) — kein Netz, kein Mock-Objekt."""
    from output.channels.email import EmailOutput

    zugestellt: list = []

    def _record(self, *, subject, body, **kwargs):
        zugestellt.append({"subject": subject, "body": body})

    monkeypatch.setattr(EmailOutput, "send", _record)
    return zugestellt


def test_t12b_zugestellter_on_demand_versand_laesst_den_regulaeren_slot_faellig(
    monkeypatch,
):
    """Given ein per SMS angefordertes „heute" wird TATSAECHLICH zugestellt
    (Ausgang `sent`) / When der regulaere Sammellauf zur konfigurierten Stunde
    laeuft / Then ist der Slot weiterhin faellig.

    🔴 Adversary-Finding F004 — die Luecke, die T12 nicht sehen kann: T12 prueft
    einen On-Demand-Versand, der ehrlich in `no_stage` endet, und kehrt damit
    zurueck, BEVOR `_append_briefing_log` (`trip_report_scheduler.py:1337`)
    erreicht ist. Genau dieser Log-Eintrag ist aber die Spur, ueber die ein
    angefordertes Briefing dem Nutzer sein regulaeres wegnahm: die
    Rueckwaerts-Ableitung (AC-9) liest `trip_id`, `kind` und `sent_at`, solange
    `briefing_slots.json` noch nicht existiert — also genau in dem Zeitfenster
    nach einem Deploy, in dem typischerweise der Test-Versand gedrueckt wird.

    Ersetzt sind ausschliesslich die zwei Naehte zum Netz: der Wetterabruf
    (Fixture-Unterklasse) und der Mail-Transportrand (aufzeichnende Funktion).
    `_send_trip_report_outcome`, der Log-Schreiber, der Speicher und die
    Sammlung laufen echt.

    RED-Charakter: Mutations-Waechter — rot bei: `on_demand` nicht im
    Log-Eintrag festgehalten oder in `_log_bezeugt_versand` nicht uebersprungen.
    Dann faellt das regulaere Briefing dieses Ortstags still aus — ohne
    Protokollzeile, ohne Fehlerzaehler.
    """
    from app.loader import get_data_dir, load_all_trips
    from services.trip_day import trip_local_today

    jetzt = datetime.now(timezone.utc)
    heute_ort = local_dt(jetzt, PARIS).date()
    _schreibe("slot-t12b", [_trip_json(
        "korsika", *KORSIKA,
        [heute_ort - timedelta(days=1), heute_ort, heute_ort + timedelta(days=1)],
        morning="07:00:00",
    )])
    trip = load_all_trips(user_id="slot-t12b")[0]
    ortstag = trip_local_today(trip, jetzt)
    settings = _zustellbare_settings()
    zugestellt = _aufzeichnender_mailversand(monkeypatch)
    scheduler = _scheduler_mit_fixture_wetter("slot-t12b", settings)

    # a) Der On-Demand-Versand geht wirklich raus.
    assert scheduler.send_on_demand_report(trip, "morning") == "sent", (
        "Testaufbau prueft nichts: nur ein zugestellter On-Demand-Versand "
        "erreicht `_append_briefing_log` — genau darum geht es hier."
    )
    assert len(zugestellt) == 1, (
        f"Genau eine zugestellte Nachricht erwartet, gefunden {len(zugestellt)}"
    )
    log_eintraege = json.loads(
        (get_data_dir("slot-t12b") / "briefing_log.json").read_text(encoding="utf-8")
    )["entries"]
    assert [e["kind"] for e in log_eintraege] == ["morning"], (
        "Testaufbau prueft nichts: der Log-Eintrag, um den es geht, muss "
        f"entstanden sein. Gefunden: {log_eintraege}"
    )

    # b) Die eigentliche Zusicherung (AC-12): der regulaere Slot bleibt faellig.
    assert not (get_data_dir("slot-t12b") / "briefing_slots.json").exists(), (
        "Testaufbau prueft nichts: ohne eigenen Speicher greift die "
        "Rueckwaerts-Ableitung gar nicht, und der Fall waere unerreichbar."
    )
    assert not BriefingSlotStore("slot-t12b").is_recorded(
        "korsika", "morning", ortstag, zone=PARIS,
    ), (
        "Ein angefordertes Briefing darf den regulaeren Slot nicht als "
        "erledigt erscheinen lassen."
    )
    assert ("korsika", "morning") in _sammlung(
        _scheduler("slot-t12b"), _zeitpunkt(PARIS, ortstag, 7),
    ), (
        "Der regulaere 07:00-Slot muss weiterhin faellig sein (AC-12). Ist er "
        "es nicht, hat die Rueckwaerts-Ableitung den On-Demand-Eintrag aus "
        "briefing_log.json gelesen — der Nutzer verliert sein regulaeres "
        "Briefing dieses Ortstags stillschweigend."
    )


# ---------------------------------------------------------------------------
# AC-13 / T13 — Sperre nicht erhältlich → kein Versand (fail-closed)
# ---------------------------------------------------------------------------

def test_t13_ohne_sperre_wird_nicht_gesendet(monkeypatch):
    """Given die Schreibsperre auf `briefing_slots.json` ist nicht zu bekommen
    / When ein Trip zum Versand ansteht / Then wird NICHT gesendet, statt ohne
    wirksamen Vermerk zu senden.

    Mockfreier Aufbau: die Sperre wird mit einem ECHTEN, im selben Prozess
    gehaltenen `flock`-Filedeskriptor auf der echten Sidecar-Datei belegt.
    `flock` haengt an der Open-File-Description, nicht am Prozess — ein
    zweiter `os.open` derselben Datei kollidiert also real (nachgemessen).
    Die Zeitgrenze wird ueber das Modul-Attribut gekuerzt, damit der Test
    nicht 2 Sekunden wartet.

    RED-Charakter: Mutations-Waechter — rot bei: fail-open wie
    `throttle_store:139-150` (Warnung loggen und trotzdem weitermachen). Dort
    kostet ein verpasster Schreibvorgang einen doppelten Hinweis; hier
    bedeutet er einen echten Doppelversand inklusive kostenpflichtiger
    Premium-SMS.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    _schreibe("slot-t13", [_trip_json("korsika", *KORSIKA, tage, morning="07:00:00")])
    scheduler = _scheduler_mit_festem_ausgang("slot-t13")

    monkeypatch.setattr(briefing_slots, "LOCK_TIMEOUT_SECONDS", 0.05, raising=False)

    trip, report_type, ortstag = scheduler._collect_due_trips(
        _zeitpunkt(PARIS, date(2026, 8, 20), 7)
    )[0]

    verzeichnis = get_data_dir("slot-t13")
    verzeichnis.mkdir(parents=True, exist_ok=True)
    sperrdatei = str(verzeichnis / "briefing_slots.json.lock")
    fd = os.open(sperrdatei, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        ergebnis = scheduler._dispatch_due_item(trip, report_type, ortstag)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    assert scheduler.versandversuche == [], (
        "Die Reservierung war nicht zu bekommen — dann darf NICHT gesendet "
        "werden. Ein Versand ohne wirksamen Vermerk ist ein Doppelversand in "
        f"der naechsten Stunde. Gefunden: {scheduler.versandversuche}"
    )
    assert ergebnis is None, (
        "Ohne Versandversuch gibt es keinen Ausgang zu melden — erwartet None, "
        f"gefunden {ergebnis!r}"
    )


# ---------------------------------------------------------------------------
# AC-14 / T14 — Australia/Lord_Howe (Halbstunden-Versatz, 24,5-Stunden-Tag)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tag,stunde", [
    # 2026-04-05: Ende der Sommerzeit, Ortstag 24,5 h lang. Die Ortsstunde 01
    # kommt ZWEIMAL vor (01:00 und 01:30) -- Doppelstunde im Halbstunden-Raster.
    (date(2026, 4, 5), 1),
    (date(2026, 4, 5), 7),
    # 2026-10-04: Beginn der Sommerzeit, Ortstag 23,5 h lang (01:00 -> 02:30).
    (date(2026, 10, 4), 2),
    (date(2026, 10, 4), 7),
])
def test_t14_lord_howe_halbstundenversatz_bleibt_unauffaellig(tag: date, stunde: int):
    """Given ein Trip in `Australia/Lord_Howe` (Halbstunden-Versatz, an den
    eigenen Umstellungstagen 24,5 bzw. 23,5 Stunden lang) / When der
    Sammellauf ueber den vollstaendigen Ortstag laeuft / Then wird der Trip
    genau einmal faellig, ohne Luecke und ohne Dopplung.

    Der Fall existierte im Repo bisher nur als Text in ADRs und einem
    Docstring — kein einziger Test hat ihn je gemessen.

    RED-Charakter: fuer (05.04., 01:00) Fehlernachweis — die Ortsstunde 01
    kommt an diesem Tag zweimal vor, die heutige Stundengleichheit liefert
    dort ZWEI Treffer. Fuer die uebrigen Faelle Mutations-Waechter — rot bei:
    einer Faelligkeitsrechnung, die den Halbstunden-Versatz auf volle Stunden
    rundet oder den Ortstag mit fest gesetzten 24 Stunden abschreitet.
    """
    tage = [tag - timedelta(days=1), tag, tag + timedelta(days=1)]
    user = f"slot-t14-{tag.isoformat()}-{stunde}"
    _schreibe(user, [_trip_json(
        "lordhowe", *LORD_HOWE, tage, morning=f"{stunde:02d}:00:00",
    )])
    scheduler = _scheduler_mit_festem_ausgang(user)

    treffer = [
        now for now in _ortstag_schritte(LORD_HOWE_TZ, tag)
        if ("lordhowe", "morning") in _lauf(scheduler, now)
    ]

    assert len(treffer) == 1, (
        f"{tag} / konfiguriert {stunde:02d}:00 — erwartet genau ein Treffer, "
        f"gefunden {len(treffer)}: "
        f"{[local_dt(t, LORD_HOWE_TZ).isoformat() for t in treffer]}"
    )
    assert _ortsstunde(treffer[0], LORD_HOWE_TZ) == stunde, (
        f"Treffer liegt auf Ortsstunde "
        f"{_ortsstunde(treffer[0], LORD_HOWE_TZ)}, konfiguriert war {stunde}"
    )


# ---------------------------------------------------------------------------
# T15 (Adversary-Finding F003) — der Schlüssel trägt den ORTSTAG, nicht den
# UTC-Tag: das Fenster darf über die UTC-Tagesgrenze nicht auseinanderfallen
# ---------------------------------------------------------------------------

def test_t15_fenster_ueber_der_utc_tagesgrenze_sendet_nur_einmal():
    """Given ein Trip in `Europe/Paris` mit Morgen-Briefing 01:00 — die drei
    Fensterstunden 01/02/03 Ortszeit liegen auf ZWEI verschiedenen UTC-Tagen
    (23:00 des Vortags, 00:00 und 01:00) / When der volle Ortstag abgeschritten
    wird / Then geht genau EIN Morgen-Briefing raus.

    🔴 Warum dieser Fall fehlte: `_collect_due_trips` bildet den Ortstag mit
    `vor_ort.date()`. Ersetzt man das durch `now_utc.date()`, blieb die gesamte
    Suite gruen (Adversary Z3) — kein Test verliess den Bereich, in dem Ortstag
    und UTC-Tag ohnehin gleich sind. `test_ac4_korsika_unveraendert` klammert
    die Konfigurationsstunden 0 und 1 per `parametrize` ausdruecklich aus, also
    genau diesen Bereich.

    Der Schaden waere ein DOPPELVERSAND an echte Empfaenger inklusive
    kostenpflichtiger Premium-SMS: Der in Ortsstunde 01 geschriebene Vermerk
    truege den UTC-Tag des Vortages, die Pruefung in Ortsstunde 02 fragte nach
    dem heutigen — kein Treffer, zweiter Versand.

    Gezaehlt werden VERSANDVERSUCHE des Morgen-Slots. Der Abend-Slot bleibt
    unbeachtet: `_trip_json(evening=None)` schaltet ihn nicht ab, `loader.py`
    setzt ihn per Default auf 18:00 (s. T2).

    RED-Charakter: Mutations-Waechter — rot bei: `ortstag = now_utc.date()`
    statt `vor_ort.date()`, also einem Schluessel, der den UTC-Tag statt des
    Ortstags traegt.
    """
    tage = [date(2026, 8, 19), date(2026, 8, 20), date(2026, 8, 21)]
    tag = date(2026, 8, 20)
    _schreibe("slot-t15", [_trip_json("korsika", *KORSIKA, tage, morning="01:00:00")])
    scheduler = _scheduler_mit_festem_ausgang("slot-t15")

    # Vorbedingung: die Fensterstunden liegen tatsaechlich auf zwei UTC-Tagen.
    utc_tage = {
        local_dt(_zeitpunkt(PARIS, tag, h), UTC).date() for h in (1, 2, 3)
    }
    assert len(utc_tage) == 2, (
        "Testaufbau prueft nichts: die drei Fensterstunden muessen ueber die "
        f"UTC-Tagesgrenze reichen, gefunden {sorted(utc_tage)}"
    )

    treffer = [
        now for now in _ortstag_schritte(PARIS, tag)
        if ("korsika", "morning") in _lauf(scheduler, now)
    ]

    assert [_ortsstunde(t, PARIS) for t in treffer] == [1], (
        "Erwartet genau ein Treffer auf Ortsstunde 01, gefunden "
        f"{[_ortsstunde(t, PARIS) for t in treffer]}"
    )
    morgens = [v for v in scheduler.versandversuche if v[1] == "morning"]
    assert morgens == [("korsika", "morning")], (
        "Genau EIN Morgen-Versand ueber das ganze Fenster. Mehr heisst: der "
        "Vermerk aus Ortsstunde 01 wurde in Ortsstunde 02 nicht gefunden, weil "
        f"der Schluessel den UTC-Tag traegt statt den Ortstag. Gefunden: {morgens}"
    )
