"""TDD RED — Issue #2286 AC-6: Korrupt-Zaehlung nach Art (trip / vergleich / unbekannt).

SPEC: docs/specs/modules/fix_2286_compare_betrieb_health.md (Implementierungsdetail 4, AC-6)

Heute meldet der Scanner `record_corrupt_trip_observability` JEDE unlesbare
Datei in `briefings/` als "Kaputter Trip" -- auch einen Vergleich -- und
ueberspringt lesbare Vergleichs-Presets ungeprueft (ein strukturell kaputtes
Preset wird nie gezaehlt).

Soll (ein Scanner, ein Dedup-Stand `diagnostics/corrupt_trips.json`):
  (a) unlesbar + Rohtext `"kind": "vergleich"`        -> vergleich
  (b) unlesbar ohne erkennbare Art                     -> unbekannt
  (c) lesbares Vergleichs-Preset, `compare_preset_from_dict` scheitert -> vergleich
  (d) kaputter Trip                                    -> trip
`by_kind` zusaetzlich zu den Altfeldern `notified`/`last_skipped_count`/
`last_run`; MQ-Betreff je Art; Dedup je Dateiname, je Nutzer.

Naht: der ECHTE Produktions-Notifier `_mq_notify_infra` wird uebergeben, nur
die Netzgrenze `lib.mq_notify.send_mq` zeichnet auf (Boundary-Sink, wie der
smtplib-Sink) -- der Betreff entsteht so im Produktcode, nicht im Test.
Daten-Root: autouse `tests/conftest.py::_isolate_data_root`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import loader

FALL_A = "a-vergleich-unlesbar.json"
FALL_B = "b-unbekannt-unlesbar.json"
FALL_C = "c-vergleich-struktur.json"
FALL_D = "d-trip-kaputt.json"

#: Betreff-Anfang je Art (Spec Implementierungsdetail 4).
BETREFF = {
    FALL_A: "Kaputter Vergleich",
    FALL_B: "Kaputte Briefing-Datei",
    FALL_C: "Kaputter Vergleich",
    FALL_D: "Kaputter Trip",
}


def _vergleich_struktur_kaputt() -> dict:
    """Lesbares JSON, `kind: vergleich`, aber `location_ids` ist keine Liste
    -> `compare_preset_from_dict` scheitert (`list(42)`)."""
    return {
        "id": "c-vergleich-struktur", "name": "Struktur kaputt", "kind": "vergleich",
        "location_ids": 42, "schedule": "daily", "created_at": "2026-07-01T00:00:00Z",
    }


def _trip_kaputt() -> dict:
    """Strukturell defekter Trip (Muster test_scheduler_corrupt_trip_observability)."""
    return {
        "id": "d-trip-kaputt", "name": "Kaputte-Trip", "kind": "route",
        "stages": [{"id": "e1", "name": "Etappe 1", "date": "kaputt", "waypoints": []}],
    }


def _write_four_cases(uid: str) -> Path:
    bdir = loader.get_briefings_dir(uid)
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / FALL_A).write_text(
        '{"id": "a-vergleich-unlesbar", "kind": "vergleich", "name": "abgeschnitten', encoding="utf-8",
    )
    (bdir / FALL_B).write_text("{not valid json", encoding="utf-8")
    (bdir / FALL_C).write_text(json.dumps(_vergleich_struktur_kaputt()), encoding="utf-8")
    (bdir / FALL_D).write_text(json.dumps(_trip_kaputt()), encoding="utf-8")
    return bdir


@pytest.fixture
def mq_sink(monkeypatch):
    """Boundary-Sink auf `lib.mq_notify.send_mq` (Netzgrenze zum claude-mq)."""
    import lib.mq_notify as mq_mod

    sent: list[dict] = []

    def _record(sender, recipient, priority, subject, body):
        sent.append({"sender": sender, "recipient": recipient, "priority": priority,
                     "subject": subject, "body": body})

    monkeypatch.setattr(mq_mod, "send_mq", _record)
    return sent


def _state(uid: str) -> dict:
    path = loader.get_data_dir(uid) / "diagnostics" / "corrupt_trips.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _scan(uid: str):
    from services.trip_report_scheduler import _mq_notify_infra, record_corrupt_trip_observability

    return record_corrupt_trip_observability(uid, notify=_mq_notify_infra)


def test_premise_case_c_fails_compare_structure_check():
    """Praemisse fuer Fall (c): das Fixture scheitert wirklich am echten
    Vergleichs-Struktur-Parser (sonst misst der Test nichts)."""
    from app.loader import compare_preset_from_dict

    with pytest.raises(Exception):
        compare_preset_from_dict(_vergleich_struktur_kaputt())


def test_by_kind_counts_each_case(mq_sink):
    """Given je eine Datei der Faelle (a)-(d) / When der Scanner laeuft / Then
    `by_kind` == {vergleich: 2, unbekannt: 1, trip: 1}; die Altfelder
    `notified`, `last_skipped_count`, `last_run` bleiben erhalten.

    RED: `by_kind` fehlt, (c) wird gar nicht gezaehlt."""
    uid = "tdd-2286-bykind"
    _write_four_cases(uid)

    _scan(uid)
    state = _state(uid)

    by_kind = state.get("by_kind") or {}
    got = {k: by_kind.get(k, 0) for k in ("trip", "vergleich", "unbekannt")}
    assert got == {"trip": 1, "vergleich": 2, "unbekannt": 1}, (
        f"AC-6: (a)+(c) -> vergleich, (b) -> unbekannt, (d) -> trip; kam {state!r}"
    )
    for feld in ("notified", "last_skipped_count", "last_run"):
        assert feld in state, f"AC-6: Altfeld {feld!r} muss erhalten bleiben, kam {state!r}"
    assert sorted(state["notified"]) == sorted([FALL_A, FALL_B, FALL_C, FALL_D])


def test_mq_subject_per_kind(mq_sink):
    """AC-6: je kaputter Datei genau EINE MQ-Meldung an `infra` (Prioritaet
    `high`); der Betreff traegt die Art ("Kaputter Vergleich" / "Kaputte
    Briefing-Datei" / "Kaputter Trip") und den Dateinamen.

    RED: heute heisst jede Meldung "Kaputter Trip", (c) fehlt ganz."""
    uid = "tdd-2286-betreff"
    _write_four_cases(uid)

    _scan(uid)

    by_file: dict[str, list[dict]] = {}
    for msg in mq_sink:
        for fname in BETREFF:
            if fname in msg["subject"]:
                by_file.setdefault(fname, []).append(msg)
    assert sorted(by_file) == sorted(BETREFF), (
        f"AC-6: jede der vier Dateien braucht eine Meldung, kam {[m['subject'] for m in mq_sink]!r}"
    )
    for fname, erwartet in BETREFF.items():
        msgs = by_file[fname]
        assert len(msgs) == 1, f"AC-6: {fname} genau einmal melden, kam {len(msgs)}"
        msg = msgs[0]
        assert msg["subject"].startswith(erwartet), (
            f"AC-6: {fname} muss mit {erwartet!r} beginnen, kam {msg['subject']!r}"
        )
        assert (msg["recipient"], msg["priority"]) == ("infra", "high")


def test_dedup_second_run_sends_nothing_new(mq_sink):
    """AC-6 Dedup: zweiter Scanner-Lauf (zweiter Sub-Job bzw. naechster Lauf)
    ueber dieselben Dateien loest KEINE neue Meldung aus; `by_kind` bleibt
    korrekt (die Dateien sind weiterhin kaputt)."""
    uid = "tdd-2286-dedup"
    _write_four_cases(uid)

    _scan(uid)
    nach_lauf_1 = len(mq_sink)
    _scan(uid)

    assert nach_lauf_1 == 4, f"AC-6: Lauf 1 meldet alle vier Dateien, kam {nach_lauf_1}"
    assert len(mq_sink) == nach_lauf_1, (
        "AC-6: Lauf 2 darf keine Datei erneut melden, neu: "
        f"{[m['subject'] for m in mq_sink[nach_lauf_1:]]!r}"
    )
    by_kind = _state(uid).get("by_kind") or {}
    assert {k: by_kind.get(k, 0) for k in ("trip", "vergleich", "unbekannt")} == {
        "trip": 1, "vergleich": 2, "unbekannt": 1,
    }


def test_state_is_per_user_same_filename(mq_sink):
    """AC-6 Mandantentrennung: Nutzer A und B haben eine kaputte Datei mit
    DEMSELBEN Namen. A's Dedup-Stand darf B's Meldung nicht unterdruecken,
    und B's `by_kind` enthaelt nur B's Datei."""
    uid_a, uid_b = "tdd-2286-iso-a", "tdd-2286-iso-b"
    _write_four_cases(uid_a)
    bdir_b = loader.get_briefings_dir(uid_b)
    bdir_b.mkdir(parents=True, exist_ok=True)
    (bdir_b / FALL_D).write_text(json.dumps(_trip_kaputt()), encoding="utf-8")

    _scan(uid_a)
    vor_b = len(mq_sink)
    _scan(uid_b)
    neu_b = mq_sink[vor_b:]

    assert len(neu_b) == 1 and FALL_D in neu_b[0]["subject"], (
        f"AC-6: B muss seine gleichnamige Datei selbst gemeldet bekommen, kam {neu_b!r}"
    )
    state_b = _state(uid_b)
    by_kind_b = state_b.get("by_kind") or {}
    assert {k: by_kind_b.get(k, 0) for k in ("trip", "vergleich", "unbekannt")} == {
        "trip": 1, "vergleich": 0, "unbekannt": 0,
    }, f"AC-6: B's Stand darf A's Dateien nicht enthalten, kam {state_b!r}"
    assert state_b["notified"] == [FALL_D]


def test_both_subjobs_report_each_file_once_without_crash(mq_sink):
    """AC-6 Dedup ueber die ECHTEN Sub-Jobs (`briefingDispatch()` ruft Trip- und
    Vergleichs-Versand nacheinander): nach `send_due_reports` (Trip) und
    `run_compare_presets_daily` (Vergleich) ist jede der vier Dateien genau
    einmal gemeldet. Zugleich darf das strukturell kaputte Preset (c) den
    Vergleichs-Lauf nicht abstuerzen lassen (toleranter Lader, AC-5)."""
    from datetime import datetime, timezone

    from services.scheduler_dispatch_service import run_compare_presets_daily
    from services.trip_report_scheduler import TripReportSchedulerService

    uid = "tdd-2286-subjobs"
    _write_four_cases(uid)

    TripReportSchedulerService(user_id=uid).send_due_reports(datetime.now(timezone.utc))
    result = run_compare_presets_daily(uid, data_root=str(loader.get_data_root()), hour=6)

    assert result == (0, 0), f"kein gueltiger Vergleich vorhanden, kam {result!r}"
    gemeldet = sorted(f for f in BETREFF for m in mq_sink if f in m["subject"])
    assert gemeldet == sorted(BETREFF), (
        "AC-6: jede Datei ueber beide Sub-Jobs genau einmal gemeldet, kam "
        f"{[m['subject'] for m in mq_sink]!r}"
    )


def test_rewrite_keeps_unknown_fields_of_previous_state(mq_sink):
    """Adversary F001 (Read-Modify-Write, CLAUDE.md "Daten-Schema-Reworks"):
    GIVEN ein vorhandenes `diagnostics/corrupt_trips.json` mit Altfeldern UND
    einem dem Scanner unbekannten Zusatzfeld (`future_field`) / WHEN der
    Scanner laeuft / THEN bleibt das Zusatzfeld erhalten, die Altfelder sind
    da (aktualisiert), `by_kind` ist geschrieben.

    Waechter gegen das Entfernen des `**previous`-Merges ist ALLEIN die
    `future_field`-Zusicherung: `notified` baut der Scanner ohnehin aus dem
    Vorgaenger-Stand neu auf und bliebe auch ohne Merge erhalten."""
    uid = "tdd-2286-merge"
    _write_four_cases(uid)
    diag = loader.get_data_dir(uid) / "diagnostics"
    diag.mkdir(parents=True, exist_ok=True)
    (diag / "corrupt_trips.json").write_text(json.dumps({
        "notified": ["alt-datei.json"],
        "last_skipped_count": 99,
        "last_run": "2026-01-01T00:00:00+00:00",
        "future_field": 42,
    }), encoding="utf-8")

    _scan(uid)
    state = _state(uid)

    assert state.get("future_field") == 42, (
        f"Read-Modify-Write: unbekanntes Feld muss erhalten bleiben, kam {state!r}"
    )
    assert sorted(state["notified"]) == sorted(["alt-datei.json", FALL_A, FALL_B, FALL_C, FALL_D])
    assert state["last_skipped_count"] == 4
    assert state["last_run"] != "2026-01-01T00:00:00+00:00"
    assert {k: state["by_kind"].get(k, 0) for k in ("trip", "vergleich", "unbekannt")} == {
        "trip": 1, "vergleich": 2, "unbekannt": 1,
    }
