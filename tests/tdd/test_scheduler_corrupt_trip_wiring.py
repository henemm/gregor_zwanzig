"""Test (Issue #1262 Nachbesserung) — record_corrupt_trip_observability wird
vom ECHTEN Scheduler-Lauf (send_reports_for_hour) aufgerufen, nicht nur vom
Unit-Test direkt.

Spec: docs/specs/modules/fix_1262_legacy_flat_metrics.md, AC-4.

Vorher war `record_corrupt_trip_observability` korrekt implementiert, aber
NIRGENDS im echten Sendelauf verdrahtet — der Status-Endpoint und die
MQ-Meldung blieben tot, weil niemand die Funktion je aufrief. Dieser Test
prueft die Verdrahtung ueber eine echte Datei-Zustandsaenderung: nach einem
echten `send_reports_for_hour()`-Lauf mit einem strukturell kaputten Trip im
briefings/-Ordner muss `diagnostics/corrupt_trips.json` mit
`last_skipped_count >= 1` existieren.

MQ-Versand-Sicherheit: `_mq_notify_infra` nutzt den bereits etablierten
Fail-soft-Helper `src.lib.mq_notify.send_mq`, der OHNE gesetztes
`CLAUDE_MQ_SECRET` still ueberspringt (kein echter POST) — in der Testumgebung
ist dieses Secret nicht gesetzt, der reale Versand feuert hier also nicht.
Kein Mock auf Geschaeftslogik: `send_reports_for_hour` laeuft komplett echt,
inkl. dem echten Observability-Aufruf; nur der HTTP-Layer bleibt inaktiv,
weil das Secret fehlt (produktionsidentisches Fail-soft-Verhalten, kein Test-
Stub).

Kern-Schicht, deterministisch: echte Dateien im autouse-isolierten Daten-Root
(`tests/conftest.py::_isolate_data_root`, Issue #1133). `Settings()` bleibt
ohne SMTP-Konfiguration -> `send_reports_for_hour` kehrt frueh mit (0, 0)
zurueck, ABER der Observability-Aufruf steht VOR diesem frühen Return und
laeuft in jedem Fall.
"""
from __future__ import annotations

import json
from pathlib import Path

from app import loader
from app.config import Settings


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


def test_send_reports_for_hour_writes_corrupt_trip_diagnostics():
    """GIVEN eine strukturell kaputte Trip-Datei im briefings/-Ordner / WHEN
    der ECHTE Sendelauf `send_reports_for_hour` laeuft / THEN steht
    `diagnostics/corrupt_trips.json` mit `last_skipped_count >= 1` (AC-4,
    Verdrahtungs-Nachbesserung)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    uid = "corrupt-wiring-user"
    trip_id = "kaputt-wiring-1"
    _write_json(loader.get_briefings_dir(uid) / f"{trip_id}.json", _corrupt_trip(trip_id))

    diag_path = loader.get_data_dir(uid) / "diagnostics" / "corrupt_trips.json"
    assert not diag_path.exists(), "Vorbedingung: Diagnostics-Datei existiert noch nicht"

    settings = Settings()  # keine SMTP-Konfiguration -> can_send_email() False
    scheduler = TripReportSchedulerService(settings=settings, user_id=uid)

    scheduler.send_reports_for_hour(7)

    assert diag_path.exists(), (
        "send_reports_for_hour muss record_corrupt_trip_observability "
        "aufrufen und die Diagnostics-Datei schreiben (AC-4 Wiring)"
    )
    state = json.loads(diag_path.read_text(encoding="utf-8"))
    assert state["last_skipped_count"] >= 1, (
        f"kaputter Trip muss gezaehlt werden, state={state}"
    )
