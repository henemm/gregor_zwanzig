"""Test (Issue #1262 Adversary-Fix F001) — atomarer Schreib der
Dedup-Zustandsdatei `diagnostics/corrupt_trips.json`.

Spec: docs/specs/modules/fix_1262_legacy_flat_metrics.md, AC-4.

F001 (HIGH): `record_corrupt_trip_observability` schrieb die Zustandsdatei
frueher per `state_path.write_text(...)` — nicht atomar. Ein Absturz mitten
im Schreiben (systemd-Restart/Deploy/OOM = Routine im Produktionsbetrieb)
haette die Datei halb geschrieben zurueckgelassen; die Lese-Seite faengt
kaputtes JSON zwar fail-soft ab, faellt dabei aber still auf ein LEERES
Dedup-Gedaechtnis zurueck (`already = set()`) — der naechste Scheduler-Tick
haette dann ALLE zuvor gemeldeten kaputten Trips erneut per MQ gemeldet,
genau die Tick-Flut, die AC-4-Dedup verhindern soll.

Fix: Zustandsdatei wird jetzt ueber den im selben Modul bereits vorhandenen
atomaren Schreib-Helper `_write_pending_data` (tmp-Datei + `os.replace`)
geschrieben. Analog zum etablierten Praezedenz-Test
`tests/tdd/test_throttle_store.py::test_daily_limit_increment_is_atomic`
(kein `.tmp`-Rest nach dem Schreiben).

Kern-Schicht, deterministisch: echte Dateien im autouse-isolierten Daten-Root
(`tests/conftest.py::_isolate_data_root`, Issue #1133). `notify` ist ein
echter, aufrufsprotokollierender Callback (Test-Spy, kein `Mock()` auf
Geschaeftslogik).
"""
from __future__ import annotations

import json
from pathlib import Path

from app import loader


def _corrupt_trip(trip_id: str) -> dict:
    """Strukturell defekter Trip: Etappe mit ungueltigem `date`."""
    return {
        "id": trip_id,
        "name": "Kaputte-Tour",
        "kind": "route",
        "stages": [
            {
                "id": f"{trip_id}-etappe-1",
                "name": "Etappe 1",
                "date": "kaputt",
                "waypoints": [],
            }
        ],
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_dedup_state_write_leaves_no_tmp_residue_and_dedup_holds_across_runs():
    """GIVEN eine strukturell defekte Trip-Datei / WHEN
    `record_corrupt_trip_observability` zweimal laeuft / THEN bleibt nach
    JEDEM Lauf kein `.tmp`-Schreib-Rest im `diagnostics/`-Ordner liegen
    (atomarer tmp+os.replace-Write, F001), UND das Dedup-Gedaechtnis
    ueberlebt intakt vom ersten zum zweiten Lauf (genau EINE MQ-Meldung
    total, nicht bei jedem Lauf neu)."""
    from services.trip_report_scheduler import record_corrupt_trip_observability

    uid = "corrupt-atomic-write-user"
    trip_id = "kaputt-atomic-1"
    _write_json(loader.get_briefings_dir(uid) / f"{trip_id}.json", _corrupt_trip(trip_id))

    notified: list[str] = []

    def _notify(filename: str, detail: str) -> None:
        notified.append(filename)

    diag_dir = loader.get_data_dir(uid) / "diagnostics"

    result1 = record_corrupt_trip_observability(user_id=uid, notify=_notify)
    assert result1.skipped_count > 0
    names_after_run1 = sorted(p.name for p in diag_dir.iterdir())
    assert "corrupt_trips.json" in names_after_run1, (
        f"Zustandsdatei fehlt nach Lauf 1: {names_after_run1}"
    )
    assert not any(n.endswith(".tmp") or n.startswith("tmp") for n in names_after_run1), (
        f"Temporaerer Schreib-Rest nach Lauf 1 gefunden (kein atomarer "
        f"tmp+os.replace-Write, F001): {names_after_run1}"
    )

    result2 = record_corrupt_trip_observability(user_id=uid, notify=_notify)
    assert result2.skipped_count > 0
    names_after_run2 = sorted(p.name for p in diag_dir.iterdir())
    assert not any(n.endswith(".tmp") or n.startswith("tmp") for n in names_after_run2), (
        f"Temporaerer Schreib-Rest nach Lauf 2 gefunden (kein atomarer "
        f"tmp+os.replace-Write, F001): {names_after_run2}"
    )

    assert len(notified) == 1, (
        f"Dedup-Gedaechtnis muss den zweiten Lauf ueberleben — genau EINE "
        f"MQ-Meldung insgesamt erwartet, bekam {notified}"
    )

    state = json.loads((diag_dir / "corrupt_trips.json").read_text(encoding="utf-8"))
    assert state["notified"] == [f"{trip_id}.json"], (
        f"Dedup-Zustand nach Lauf 2 unerwartet: {state}"
    )
