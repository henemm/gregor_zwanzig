"""Bestandsmigration laesst Compare-Eintraege unveraendert (#2281, Test 6).

SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md (Test 6, AC-1 Datenerhalt)

Regressionswaechter (heute gruen): ``scripts/migrate_briefing_log_mail_to_mask.py``
(#2157) liest und schreibt ``briefing_log.json`` per Read-Modify-Write. Nach
#2281 stehen dort auch Compare-Eintraege (``entity_type``/``entity_id``, kein
``trip_id``). Das Skript darf sie weder verlieren noch umformen (kein
``trip_id`` ergaenzen, ``entity_*`` nicht streichen).

Damit der Test nicht vakuum-gruen ist, MUSS das Skript die Datei tatsaechlich
neu schreiben: es schreibt nur, wenn es etwas maskiert. Deshalb liegt daneben
ein Trip-Eintrag mit Klartext-``mail_to`` (Kontrolle: wird maskiert, ``.bak``
entsteht). Die Compare-Eintraege tragen kein bzw. ein bereits maskiertes
``mail_to`` -- ein Klartext-``mail_to`` soll auch bei Compare maskiert werden
und ist hier nicht Pruefgegenstand.

Aufruf als Subprozess gegen einen ``tmp_path``-Baum (Vorbild
``tests/unit/test_migrate_briefing_log_mail_to_mask.py``); Pruefling relativ zur
Testdatei aufgeloest.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKRIPT = ROOT / "scripts" / "migrate_briefing_log_mail_to_mask.py"

COMPARE_OHNE_MAIL = {
    "entity_type": "compare", "entity_id": "vgl-alpen", "kind": "morning",
    "sent_at": "2026-10-20T05:00:00+00:00", "channels": ["telegram"], "on_demand": False,
}
COMPARE_MASKIERT = {
    "entity_type": "compare", "entity_id": "vgl-dolomiten", "kind": "evening",
    "sent_at": "2026-10-20T16:00:00+00:00", "channels": ["email"], "on_demand": True,
    "mail_to": "***@example.org",
}
TRIP_KLARTEXT = {
    "trip_id": "trip-gr20", "entity_type": "trip", "entity_id": "trip-gr20",
    "kind": "morning", "sent_at": "2026-10-20T05:00:00+00:00",
    "channels": ["email"], "on_demand": False, "mail_to": "wanderin@beispiel.de",
}


def test_migration_reicht_compare_eintraege_unveraendert_durch(tmp_path):
    """GIVEN ein Log mit zwei Compare-Eintraegen und einem Trip-Eintrag mit
          Klartext-Adresse.
    WHEN  das Migrationsskript laeuft (ohne ``--dry-run``).
    THEN  die Datei wurde neu geschrieben (Kontrolle: Trip-Adresse maskiert,
          ``.bak`` vorhanden), die Compare-Eintraege sind dict-gleich,
          ohne ``trip_id``, Reihenfolge und Anzahl erhalten.
    """
    pfad = tmp_path / "users" / "nutzer-migration" / "briefing_log.json"
    pfad.parent.mkdir(parents=True)
    vorher = [copy.deepcopy(COMPARE_OHNE_MAIL), copy.deepcopy(TRIP_KLARTEXT),
              copy.deepcopy(COMPARE_MASKIERT)]
    pfad.write_text(json.dumps({"entries": vorher}, indent=2), encoding="utf-8")

    lauf = subprocess.run(
        [sys.executable, str(SKRIPT), "--root", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert lauf.returncode == 0, lauf.stderr

    nachher = json.loads(pfad.read_text(encoding="utf-8"))["entries"]
    # Kontrolle: die Datei wurde wirklich umgeschrieben.
    assert pfad.with_name("briefing_log.json.bak").exists(), "Vorbedingung: Skript hat geschrieben"
    assert nachher[1]["mail_to"] != TRIP_KLARTEXT["mail_to"], "Vorbedingung: Trip-Adresse maskiert"

    assert len(nachher) == 3, nachher
    assert nachher[0] == COMPARE_OHNE_MAIL, f"Compare-Eintrag veraendert: {nachher[0]!r}"
    assert nachher[2] == COMPARE_MASKIERT, f"Compare-Eintrag veraendert: {nachher[2]!r}"
    assert "trip_id" not in nachher[0] and "trip_id" not in nachher[2], nachher
    assert {k: v for k, v in nachher[1].items() if k != "mail_to"} == {
        k: v for k, v in TRIP_KLARTEXT.items() if k != "mail_to"
    }, f"Trip-Eintrag ausser mail_to veraendert: {nachher[1]!r}"
