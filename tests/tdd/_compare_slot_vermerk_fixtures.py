"""Gemeinsamer Aufbau fuer Faelligkeitsfenster + Idempotenz-Vermerk des
Ortsvergleichs (Issue #1777).

Kein Test-Modul (fuehrender Unterstrich). Geteilt von
``test_compare_briefing_vermerk.py`` (Vermerk, Ausgangs-Abbildung, Rollout,
fail-closed, Nachholer, Handversand) und ``test_compare_faelligkeit_fenster.py``
(Fenster, Umstellungstage, Zonen, Alarm-Sperre, Anzeige).

SPEC: docs/specs/modules/fix_1777_compare_faelligkeit_und_idempotenz.md
Vorbild (Trip): tests/tdd/test_briefing_slot_idempotenz.py (#1725).

Test-Politik (CLAUDE.md „Zwei Schichten"): kein Mock-Theater. Speicher,
Schluesselbildung, Fenster, Sammelphase, Nachholer und Orchestrator laufen
ECHT ueber ``run_briefing_dispatch("vergleich", ...)``. Ersetzt wird an genau
einer Stelle die Naht zum Netz -- der Versand ``send_one_compare_preset`` --
durch eine echte Funktion, die einen der dokumentierten Ausgaenge liefert
(Rueckkehr = ``sent``, ``SendOutcomeError(code)``, sonstige Ausnahme) und jeden
Aufruf mitschreibt. Ihr Ausgang ist die EINGABE der gepruefen Entscheidung,
nicht deren Ergebnis -- Muster ``_scheduler_mit_festem_ausgang`` der
Trip-Tests. Wo der Nachhol-Vermerk (``pending_briefings.json``) aus dem echten
Versandweg stammen muss, laufen die Tests ueber die volle Kette
(``kette``-Fixture: Wetter-Naht + Transport-Aufzeichner wie in
``test_compare_briefing_nachholen.py``).

Zeit: ausschliesslich als ``now_utc``-Parameter (ADR-0051 Regel 3); Ortstage
werden ueber ``local_dt(..., UTC)`` abgeschritten (ADR-0044-Falle, s. Trip).

Speicher werden ROH gelesen und geschrieben (Schema laut Spec, Variante B):
``data/users/<uid>/briefing_slots_compare.json`` =
``{"entries": [{"preset_id", "slot", "local_day", "recorded_at", "outcome"}]}``.
So sind die Tests an fehlendem VERHALTEN rot, nicht an einer fehlenden
Konstruktor-Signatur.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo

import pytest

from app.loader import get_data_dir, get_data_root, save_location
from app.user import SavedLocation
from utils.timezone import UTC, local_dt

# Pfadregel #1409: Pruefling relativ zur Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: Datei des Compare-Vermerks (Spec „Design", Variante B).
COMPARE_SLOTS = "briefing_slots_compare.json"
TRIP_SLOTS = "briefing_slots.json"

# Koordinaten je Zone -- echte Orte, damit TimezoneFinder sie aufloest.
KORSIKA = (42.30, 8.93)          # Europe/Paris
NEW_YORK = (40.71, -74.01)       # America/New_York
INNSBRUCK = (47.27, 11.39)       # Europe/Vienna

PARIS = ZoneInfo("Europe/Paris")
NY = ZoneInfo("America/New_York")
WIEN = ZoneInfo("Europe/Vienna")

#: Ausgaenge, die laut Spec einen Vermerk setzen (geteilte VERMERK_AUSGAENGE
#: ohne ``no_stage``, das es im Vergleich nicht gibt).
VERMERK_AUSGAENGE = ("sent", "no_channels", "no_weather")


# ---------------------------------------------------------------------------
# Zeit
# ---------------------------------------------------------------------------


def utc_zu(zone: ZoneInfo, tag: date, stunde: int, minute: int = 0) -> datetime:
    """UTC-Zeitpunkt einer eindeutigen Ortsstunde des Ortstags."""
    return local_dt(datetime(tag.year, tag.month, tag.day, stunde, minute, tzinfo=zone), UTC)


def ortsstunde(now_utc: datetime, zone: ZoneInfo) -> int:
    return local_dt(now_utc, zone).hour


def ortstag_schritte(zone: ZoneInfo, tag: date) -> Iterator[datetime]:
    """Schreitet den ORTSTAG stuendlich von Ortsmitternacht zu Ortsmitternacht
    ab; die Tageslaenge wird berechnet (23/24/25 h), nicht gesetzt."""
    start = datetime(tag.year, tag.month, tag.day, 0, 0, tzinfo=zone)
    ende = start + timedelta(days=1)
    t = local_dt(start, UTC)
    grenze = local_dt(ende, UTC)
    while t < grenze:
        yield t
        t += timedelta(hours=1)


# ---------------------------------------------------------------------------
# Nutzer, Orte, Vergleiche
# ---------------------------------------------------------------------------


def nutzer() -> str:
    """Frisches Profil (eigene Kennung, eigene Empfaenger, nie ``default``)."""
    from tests.tdd._compare_kette_fixtures import nutzer_anlegen

    return nutzer_anlegen()


def ort_anlegen(uid: str, lid: str, koord: tuple[float, float], name: str | None = None) -> str:
    save_location(SavedLocation(
        id=lid, name=name or lid, lat=koord[0], lon=koord[1], elevation_m=800,
    ), user_id=uid)
    return lid


def vergleich_ablegen(uid: str, pid: str, *, orte: list[str],
                      morgen: str | None = "07:00:00", abend: str | None = None,
                      schedule: str = "daily", weekday: int | None = None,
                      telegram: bool = False, **extra) -> str:
    """Echtes Preset im Persistenzformat des Editors (``briefings/<id>.json``,
    ``kind="vergleich"``), Basis = Fixture ``compare_kette/basis.json``."""
    from tests.tdd._compare_kette_fixtures import fixture_dict, preset_ablegen

    roh = fixture_dict("basis")
    roh["id"] = pid
    roh["name"] = f"Vergleich {pid}"
    roh["location_ids"] = list(orte)
    roh["schedule"] = schedule
    roh["weekday"] = weekday
    roh["morning_enabled"] = morgen is not None
    roh["morning_time"] = morgen or "07:00:00"
    roh["evening_enabled"] = abend is not None
    roh["evening_time"] = abend or "18:00:00"
    roh["send_telegram"] = telegram
    roh.update(extra)
    preset_ablegen(uid, roh)
    return pid


def lauf(uid: str, now_utc: datetime) -> tuple[int, int]:
    """Der echte stuendliche Compare-Lauf (Go-Cron -> ``run_briefing_dispatch``:
    ``collect_due`` -> ``pre_pass`` -> ``dispatch_one`` je faelligem Preset)."""
    from services.dispatch_orchestrator import run_briefing_dispatch

    return run_briefing_dispatch("vergleich", uid, now_utc, data_root=str(get_data_root()))


# ---------------------------------------------------------------------------
# Rohe Speicher (Schema laut Spec)
# ---------------------------------------------------------------------------


def _json_lesen(pfad: Path) -> dict:
    if not pfad.exists():
        return {}
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    return daten if isinstance(daten, dict) else {}


def compare_vermerke(uid: str) -> list[dict]:
    return list(_json_lesen(get_data_dir(uid) / COMPARE_SLOTS).get("entries", []))


def compare_vermerk_schluessel(uid: str) -> set[tuple]:
    """``{(preset_id, slot, local_day, outcome)}`` der Compare-Vermerk-Datei."""
    return {
        (e.get("preset_id"), e.get("slot"), e.get("local_day"), e.get("outcome"))
        for e in compare_vermerke(uid)
    }


def abgeschlossene_vermerke(uid: str) -> set[tuple]:
    """Nur Vermerke MIT Ausgang -- ``(preset_id, slot, local_day, outcome)``."""
    return {k for k in compare_vermerk_schluessel(uid) if k[3] is not None}


def compare_vermerk_schreiben(uid: str, eintraege: list[dict]) -> Path:
    pfad = get_data_dir(uid) / COMPARE_SLOTS
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": eintraege}, indent=2), encoding="utf-8")
    return pfad


def compare_vermerk(pid: str, slot: str, tag: date, outcome: str | None,
                    recorded_at: datetime | None = None) -> dict:
    return {
        "preset_id": pid, "slot": slot, "local_day": tag.isoformat(),
        "recorded_at": (recorded_at or datetime(2026, 1, 1, tzinfo=timezone.utc)).isoformat(),
        "outcome": outcome,
    }


def briefing_log_schreiben(uid: str, eintraege: list[dict]) -> None:
    """``briefing_log.json`` im Format von ``briefing_log.append_briefing_log``
    (``briefing_log.py:56-66``)."""
    pfad = get_data_dir(uid) / "briefing_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": eintraege}, indent=2), encoding="utf-8")


def compare_log_eintrag(pid: str, kind: str, sent_at: datetime, *, on_demand: bool = False,
                        entity_type: str | None = "compare") -> dict:
    eintrag: dict = {}
    if entity_type == "trip" or entity_type is None:
        eintrag["trip_id"] = pid
    eintrag.update({
        "entity_id": pid, "kind": kind, "sent_at": sent_at.isoformat(),
        "channels": ["email"], "on_demand": on_demand,
    })
    if entity_type is not None:
        eintrag["entity_type"] = entity_type
    return eintrag


def nachhol_vermerke(uid: str) -> list[dict]:
    """Ortsvergleich-Eintraege in ``pending_briefings.json`` (#2587)."""
    daten = _json_lesen(get_data_dir(uid) / "pending_briefings.json")
    return [e for e in daten.get("entries", []) if e.get("kind") == "vergleich"]


def nachhol_vermerk_schreiben(uid: str, pid: str, slot: str, tag: date, slot_hour: int) -> None:
    pfad = get_data_dir(uid) / "pending_briefings.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [{
        "kind": "vergleich", "preset_id": pid, "report_type": slot,
        "date": tag.isoformat(), "slot_hour": slot_hour, "reason": "dispatch_error",
        "failed_segment_ids": [], "attempts": 0,
        "created_at": "2026-01-01T00:00:00+00:00",
    }]}, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Versand-Naht (nur die Naht zum Netz)
# ---------------------------------------------------------------------------


class Versandnaht:
    """Ersetzt ``scheduler_dispatch_service.send_one_compare_preset``.

    ``ausgang[pid]`` (Default ``standard``): ``"sent"`` = Rueckkehr ohne
    Ausnahme; ein anderer String = ``SendOutcomeError(code)``; eine Ausnahme-
    Instanz wird geworfen. ``versuche`` schreibt JEDEN Aufruf mit -- auch die
    des Nachholers (#2587), erkennbar an ``nachhol=True`` (der Nachholer
    reicht ``catchup_hint`` durch, der regulaere Versand nie).
    """

    def __init__(self) -> None:
        self.standard: object = "sent"
        self.ausgang: dict[str, object] = {}
        self.versuche: list[dict] = []

    def __call__(self, preset, settings, user_id, data_root, all_locations_cache=None,
                 target_date=None, tage_ab_ortstag=None, *args, **kwargs):
        from services.send_outcomes import SendOutcomeError

        pid = preset.get("id")
        nachhol = kwargs.get("catchup_hint") is not None
        slot = kwargs.get("report_type") or ("evening" if tage_ab_ortstag else "morning")
        self.versuche.append({
            "uid": user_id, "pid": pid, "slot": slot, "target_date": target_date,
            "nachhol": nachhol, "on_demand": bool(kwargs.get("on_demand")),
        })
        wert = self.ausgang.get(pid, self.standard)
        if isinstance(wert, BaseException):
            raise wert
        if wert != "sent":
            raise SendOutcomeError(str(wert))
        return "Ort", ["empfaenger@example.invalid"]

    def regulaer(self, pid: str | None = None, uid: str | None = None) -> list[tuple]:
        return [
            (v["pid"], v["slot"]) for v in self.versuche
            if not v["nachhol"] and (pid is None or v["pid"] == pid)
            and (uid is None or v["uid"] == uid)
        ]

    def nachgeholt(self, pid: str | None = None) -> list[tuple]:
        return [
            (v["pid"], v["slot"]) for v in self.versuche
            if v["nachhol"] and (pid is None or v["pid"] == pid)
        ]


@pytest.fixture
def naht(monkeypatch) -> Versandnaht:
    """Versand-Naht + unbrauchbare Transportfelder (#1477) + keine 2s-Pause."""
    import services.dispatch_orchestrator as orch_mod
    import services.scheduler_dispatch_service as sds
    from tests.tdd._compare_kette_fixtures import transport_einrichten

    transport_einrichten(monkeypatch)
    monkeypatch.setattr(orch_mod.CompareDispatchStrategy, "inter_mail_delay", 0.0)
    n = Versandnaht()
    monkeypatch.setattr(sds, "send_one_compare_preset", n)
    return n


# ---------------------------------------------------------------------------
# Volle Kette (Nachhol-Vermerk aus dem echten Versandweg)
# ---------------------------------------------------------------------------


class Kette:
    """Was hinausging (``mit``), schaltbarer Wetter- und Telegram-Ausfall."""

    def __init__(self, mit) -> None:
        self.mit = mit
        self.wetter_aus = False
        self.telegram_aus = False
        self.telegram_versuche = 0

    def mails(self) -> list[dict]:
        return self.mit.sendungen("email")

    def telegramme(self) -> list[dict]:
        return self.mit.sendungen("telegram")


#: Wortlaut des Nachhol-Hinweises (#2587 AC-5) -- Kennzeichen des Nachholers.
NACHHOL_HINWEIS = "Nachgeliefert"


@pytest.fixture
def kette(monkeypatch) -> Kette:
    """Echter ``send_one_compare_preset``; Naehte nur zum Netz:
    Wetter (``engine_naht``, Orte ``loc-ibk``/``loc-bz``), Transport
    (geteilter Aufzeichner), Δ-Anker-Schreiber still."""
    import services.comparison_engine as ce_mod
    import services.dispatch_orchestrator as orch_mod
    from app.user import ComparisonResult, LocationResult
    from services import notification_service as ns
    from tests.helpers.transport_mitschrift import aufzeichner_installieren
    from tests.tdd._compare_kette_fixtures import engine_naht, transport_einrichten

    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    mit = aufzeichner_installieren(monkeypatch)
    k = Kette(mit)
    monkeypatch.setattr(orch_mod.CompareDispatchStrategy, "inter_mail_delay", 0.0)

    engine = ce_mod.ComparisonEngine

    class _SchaltbareEngine(engine):  # echte Unterklasse, kein Mock
        @staticmethod
        def run(*args, **kwargs):
            if not k.wetter_aus:
                return engine.run(*args, **kwargs)
            locations = kwargs.get("locations")
            if locations is None and args:
                locations = args[0]
            return ComparisonResult(
                locations=[
                    LocationResult(location=loc, error="Open-Meteo: HTTP 503 (keine Daten)")
                    for loc in list(locations or [])
                ],
                time_window=kwargs.get("time_window", (9, 16)),
                target_date=kwargs.get("target_date"),
                created_at=datetime(2026, 7, 8, 4, 0),
            )

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _SchaltbareEngine)

    telegram_aufzeichner = ns.TelegramOutput

    class _Telegram(telegram_aufzeichner):
        def send(self, *args, **kwargs):
            k.telegram_versuche += 1
            if k.telegram_aus:
                raise RuntimeError("Telegram-Gateway nicht erreichbar (simulierter Ausfall)")
            return super().send(*args, **kwargs)

    monkeypatch.setattr(ns, "TelegramOutput", _Telegram)
    return k


def kette_nutzer() -> str:
    """Nutzer mit den beiden Kettenorten (``loc-ibk`` Innsbruck = Europe/Vienna
    zuerst, ``loc-bz``) -- nur diese Kennungen kennt die Wetter-Naht."""
    from tests.tdd._compare_kette_fixtures import nutzer_anlegen, orte_anlegen

    uid = nutzer_anlegen()
    orte_anlegen(uid)
    return uid


def ohne_mail_to(uid: str) -> None:
    from tests.tdd import _handversand_fixtures as hv

    hv.profil_ohne_mail_to(uid)
