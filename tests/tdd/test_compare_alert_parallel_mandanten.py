"""TDD RED -- Feature #1539 (S6): Mandantentrennung beim parallelen Ortsvergleich-Alarm.

SPEC: docs/specs/modules/feat_1539_s6_compare_parallel.md (AC-9)

Zwei verschiedene Nutzer, je ein Compare-Preset auf Orten mit GLEICHEN Koordinaten,
laufen gleichzeitig durch Aenderungs-Alarm und Warn-Alarm. Jeder Abruf traegt die
``user_id`` seines Nutzers (nie ``"default"``/``None``); Treffer, Mails, ``raw`` und
``queries_by_loc`` des einen Nutzers tauchen nie beim anderen auf.

Heute laufen die Abrufe im aufrufenden Faden (nicht im Worker des Bausteins) -- die
Worker-Pruefung ist der rote Treiber; die Trennungs-Zusicherungen schuetzen die
Umstellung.
"""
from __future__ import annotations

# ruff: noqa: F811
import threading
from datetime import datetime, timezone

from app.user import SavedLocation
from services.compare_alert import CompareAlertService
from services.compare_official_alert import CompareOfficialAlertService
from tests.tdd._compare_alert_parallel_fixtures import (  # noqa: F401
    WarnRand,
    WetterRand,
    anker_setzen,
    dateien_schreiben,
    ist_worker,
    neue_breite,
    neue_kennung,
    neue_orte,
    preset_dict,
    pruefling_aus_worktree,
    settings_dummy,
    slots_setzen,
    thread_fehler,
    umgebung,
    warnquelle_registriert,
)

pruefling_aus_worktree()


def _parallel(*ziele) -> list[BaseException]:
    fehler: list[BaseException] = []

    def lauf(ziel):
        try:
            ziel()
        except BaseException as exc:  # noqa: BLE001 -- Thread-Fehler selbst einsammeln
            fehler.append(exc)

    faeden = [threading.Thread(target=lauf, args=(z,)) for z in ziele]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join(timeout=20.0)
    return fehler


def test_ac9_aenderungs_alarm_zwei_nutzer_gleiche_koordinaten(umgebung, thread_fehler, monkeypatch):
    slots_setzen(monkeypatch, "open_meteo", 3)
    koordinaten = (neue_breite(), 11.0)
    nutzer = {}
    for tag in ("a", "b"):
        uid = neue_kennung(f"ac9{tag}")
        orte = neue_orte(2, f"{tag}{uid[-6:]}", gleiche_koordinaten=koordinaten)
        preset = preset_dict("p-ac9", [o.id for o in orte])
        for o in orte:
            anker_setzen(uid, preset["id"], o)
        dateien_schreiben(uid, preset, orte)
        nutzer[uid] = {"orte": orte, "mails": []}

    rand = WetterRand(verzoegerung={"loc-1": 0.2, "loc-2": 0.2})
    dienste = {
        uid: CompareAlertService(
            settings=settings_dummy(), user_id=uid, weather_source=rand,
            mail_sink=lambda _m=daten["mails"], **kw: _m.append(str(kw)))
        for uid, daten in nutzer.items()
    }

    fehler = _parallel(*[d.check_all_compare_presets for d in dienste.values()])

    assert not fehler, f"Thread-Fehler: {fehler!r}"
    assert {a["user_id"] for a in rand.aufrufe} == set(nutzer), (
        "jeder Abruf traegt die user_id seines Nutzers (nie default/None)")
    for uid in nutzer:
        assert sum(1 for a in rand.aufrufe if a["user_id"] == uid) == 2
    for uid, daten in nutzer.items():
        fremd = [n for u, d in nutzer.items() if u != uid for o in d["orte"] for n in [o.name]]
        assert daten["mails"], f"Setup: {uid} erhaelt einen Alarm"
        for text in daten["mails"]:
            assert any(o.name in text for o in daten["orte"])
            assert not any(n in text for n in fremd), "Alarm eines Nutzers enthaelt Orte des anderen"
    assert all(ist_worker(a["thread"]) for a in rand.aufrufe), (
        "Abrufe muessen im Worker des Bausteins laufen")
    assert rand.max_gleichzeitig >= 2


def test_ac9_warn_alarm_zwei_nutzer_gleiche_koordinaten(umgebung, thread_fehler, monkeypatch):
    slots_setzen(monkeypatch, "official_alerts", 3)
    lat, lon = neue_breite(), 11.0
    nutzer = {}
    for tag in ("a", "b"):
        uid = neue_kennung(f"ac9w{tag}")
        orte = [SavedLocation(id=f"{tag}-loc-{i}", name=f"Ort-{tag}-{i}", lat=lat, lon=lon,
                              elevation_m=1000) for i in (1, 2)]
        nutzer[uid] = {"orte": orte, "ergebnis": None}

    quelle = WarnRand(verzoegerung={lat: 0.2})
    jetzt = datetime.now(timezone.utc)

    def lauf(uid):
        dienst = CompareOfficialAlertService(settings=settings_dummy(), user_id=uid)
        nutzer[uid]["ergebnis"] = dienst._fetch_locations("p-ac9", nutzer[uid]["orte"], jetzt)

    with warnquelle_registriert(quelle):
        fehler = _parallel(*[lambda u=uid: lauf(u) for uid in nutzer])

    assert not fehler, f"Thread-Fehler: {fehler!r}"
    for uid, daten in nutzer.items():
        raw, queries = daten["ergebnis"]
        eigene = [o.id for o in daten["orte"]]
        assert [ids for _, ids in raw] == [[i] for i in eigene], "raw nur mit eigenen Orten"
        assert list(queries) == eigene, "queries_by_loc nur mit eigenen Orten"
        for ort_id, qs in queries.items():
            assert all(q.scope == ort_id and q.scope_ids == (ort_id,) for q in qs)
    assert all(ist_worker(a["thread"]) for a in quelle.aufrufe), (
        "Warn-Abrufe muessen im Worker des Bausteins laufen")
    assert quelle.max_gleichzeitig >= 2
