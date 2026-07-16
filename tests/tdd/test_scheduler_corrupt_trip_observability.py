"""RED-Test (Issue #1262) — Beobachtbarkeit uebersprungener/kaputter Trips.

Spec: docs/specs/modules/fix_1262_legacy_flat_metrics.md, AC-4.

Heute verschwindet ein beim Laden crashender Trip still aus `load_all_trips`
(nur `logger.error` + `continue`). Der Briefing-Scheduler soll pro Lauf
sichtbar machen, WIE VIELE Trips uebersprungen wurden, und pro kaputter
Trip-Datei genau EINE deduplizierte MQ-Meldung (Prioritaet `high`) an Instanz
`infra` senden — dedupliziert pro Dateiname, damit nicht jeder stuendliche
Tick erneut pingt.

Erwartete, noch zu bauende Observability-API (RED, weil sie fehlt):

    from services.trip_report_scheduler import record_corrupt_trip_observability

    result = record_corrupt_trip_observability(user_id=<uid>, notify=<callable>)

    - Scannt `get_briefings_dir(user_id)`, laedt jede Datei ueber den echten
      Loader-Pfad und zaehlt die, die nicht ladbar sind.
    - `result.skipped_count` (int) > 0, wenn mindestens ein Trip kaputt ist.
    - `notify` ist ein optionaler Callback `notify(filename: str, detail: str)`,
      der pro NEU entdeckter kaputter Datei GENAU EINMAL aufgerufen wird
      (Dedup-Schluessel = Dateiname, ueber Laeufe hinweg persistiert). Ein
      zweiter Lauf ueber dieselbe kaputte Datei ruft `notify` NICHT erneut auf.

`notify` ist hier ein echter, aufrufsprotokollierender Callback (Test-Spy,
kein `Mock()` auf Geschaeftslogik) — das ist der von der Spec vorgesehene
Injektions-Seam fuer den MQ-Versand.

Kern-Schicht, deterministisch: echte Dateien im autouse-isolierten Daten-Root
(`tests/conftest.py::_isolate_data_root`, Issue #1133). Die kaputte Datei
traegt eine strukturell defekte Etappe (ungueltiges `date`) — unabhaengig vom
Flach-Metrics-Fix, damit sie auch nach dem Loader-Heal-Fix kaputt bleibt.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import loader


def _corrupt_trip(trip_id: str) -> dict:
    """Strukturell defekter Trip: Etappe mit ungueltigem `date` -> der Loader
    crasht beim Parsen (`date.fromisoformat('kaputt')` -> ValueError)."""
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


def test_corrupt_trip_counted_and_mq_deduped_per_file():
    """GIVEN eine strukturell defekte Trip-Datei im briefings/-Ordner / WHEN
    der Scheduler-Beobachtbarkeits-Pfad zweimal laeuft / THEN ist der Zaehler
    uebersprungener Trips > 0 nach Lauf 1, UND die MQ-Meldung an `infra`
    erfolgt beim ZWEITEN Lauf fuer dieselbe Datei NICHT erneut (Dedup pro
    Dateiname, AC-4)."""
    from services.trip_report_scheduler import record_corrupt_trip_observability

    uid = "corrupt-obs-user"
    trip_id = "kaputt-1"
    _write_json(loader.get_briefings_dir(uid) / f"{trip_id}.json", _corrupt_trip(trip_id))

    notified: list[str] = []

    def _notify(filename: str, detail: str) -> None:
        notified.append(filename)

    # --- Lauf 1: kaputte Datei wird gezaehlt UND einmalig gemeldet ---
    result1 = record_corrupt_trip_observability(user_id=uid, notify=_notify)
    assert result1.skipped_count > 0, (
        "Lauf 1 muss die kaputte Trip-Datei als uebersprungen zaehlen (AC-4)"
    )
    assert len(notified) == 1, (
        f"Lauf 1 muss genau EINE MQ-Meldung pro kaputter Datei ausloesen, "
        f"bekam {notified}"
    )
    assert notified[0].startswith(trip_id), (
        "die MQ-Meldung ist pro Dateiname dedupliziert — der Dateiname muss "
        "im notify-Aufruf auftauchen (AC-4)"
    )

    # --- Lauf 2: gleiche Datei, KEINE erneute Meldung (Dedup persistiert) ---
    result2 = record_corrupt_trip_observability(user_id=uid, notify=_notify)
    assert result2.skipped_count > 0, (
        "Die Datei ist weiterhin kaputt — Lauf 2 zaehlt sie erneut (AC-4)"
    )
    assert len(notified) == 1, (
        f"Lauf 2 darf fuer dieselbe kaputte Datei NICHT erneut melden "
        f"(Dedup pro Dateiname, kein Ping bei jedem Tick), bekam {notified}"
    )
