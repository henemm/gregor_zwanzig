"""#2157 AC-g: einmalige Bestandsmigration maskiert Klartext-``mail_to`` in
``briefing_log.json`` -- Dry-Run-Zaehler == echter Lauf, ``.bak`` vorher,
alle anderen Felder unveraendert.

Spec: docs/specs/modules/pii_log_masking.md ("Migration von
briefing_log.json-Bestandsdaten", AC-g)

Aufrufvertrag (in dieser RED-Phase festgelegt, Vorbild
``tests/test_migrate_1250_briefings.py``: Subprozess gegen einen
``tmp_path``-Baum):

    python scripts/migrate_briefing_log_mail_to_mask.py --root <datenwurzel> [--dry-run]

* ``<datenwurzel>`` enthaelt ``users/<user_id>/briefing_log.json``.
* Ohne ``--dry-run`` wird geschrieben (Spec: Flag ``--dry-run``), vorher
  ``briefing_log.json.bak`` mit den Originalbytes daneben.
* Letzte Ausgabezeile enthaelt ``<N> Einträge maskiert, <M> unverändert``.

RED heute: das Skript existiert nicht -> returncode != 0.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKRIPT = REPO_ROOT / "scripts" / "migrate_briefing_log_mail_to_mask.py"

_ZAEHLER = re.compile(r"(\d+) Einträge maskiert, (\d+) unverändert")


def _eintrag(trip_id: str, **extra) -> dict:
    base = {
        "trip_id": trip_id,
        "kind": "morning",
        "sent_at": "2026-09-01T05:00:00+00:00",
        "channels": ["email"],
        "on_demand": False,
    }
    base.update(extra)
    return base


def _baum_anlegen(root: Path) -> dict[str, Path]:
    logs = {
        "nutzer-a": [
            _eintrag("t-ops", mail_to="gregor-test@henemm.com"),
            _eintrag("t-fremd", mail_to="finder@example.org", extra_feld="bleibt"),
            _eintrag("t-tg", channels=["telegram"]),
        ],
        "nutzer-b": [
            _eintrag("t-b", mail_to="Wanderin <wanderin@beispiel.de>"),
            _eintrag("t-staging", mail_to="gregor-staging@henemm.com"),
        ],
    }
    pfade = {}
    for uid, eintraege in logs.items():
        pfad = root / "users" / uid / "briefing_log.json"
        pfad.parent.mkdir(parents=True)
        pfad.write_text(json.dumps({"entries": eintraege}, indent=2), encoding="utf-8")
        pfade[uid] = pfad
    return pfade


def _lauf(root: Path, *extra: str) -> tuple[int, int]:
    ergebnis = subprocess.run(
        [sys.executable, str(SKRIPT), "--root", str(root), *extra],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert ergebnis.returncode == 0, (
        f"Migrationsskript scheiterte (rc={ergebnis.returncode}):\n"
        f"stdout: {ergebnis.stdout}\nstderr: {ergebnis.stderr}"
    )
    treffer = _ZAEHLER.findall(ergebnis.stdout)
    assert treffer, f"Zaehlerzeile fehlt in der Ausgabe:\n{ergebnis.stdout}"
    maskiert, unveraendert = treffer[-1]
    return int(maskiert), int(unveraendert)


def test_ac_g_dry_run_zaehlt_wie_echter_lauf_und_aendert_nur_mail_to(tmp_path):
    pfade = _baum_anlegen(tmp_path)
    original = {uid: p.read_bytes() for uid, p in pfade.items()}

    trocken = _lauf(tmp_path, "--dry-run")

    for uid, pfad in pfade.items():
        assert pfad.read_bytes() == original[uid], f"Dry-Run hat {uid} veraendert"
        assert not pfad.with_name("briefing_log.json.bak").exists(), (
            f"Dry-Run darf kein .bak anlegen ({uid})"
        )
    assert trocken == (2, 3), f"Dry-Run-Zaehler (maskiert, unveraendert): {trocken}"

    echt = _lauf(tmp_path)

    assert echt == trocken, f"Echter Lauf {echt} != Dry-Run {trocken}"
    for uid, pfad in pfade.items():
        bak = pfad.with_name("briefing_log.json.bak")
        assert bak.exists(), f".bak fehlt fuer {uid}"
        assert bak.read_bytes() == original[uid], f".bak ist nicht das Original ({uid})"

    vorher = {uid: json.loads(b)["entries"] for uid, b in original.items()}
    nachher = {uid: json.loads(p.read_text())["entries"] for uid, p in pfade.items()}
    erwartet_mail_to = {
        ("nutzer-a", "t-ops"): "gregor-test@henemm.com",
        ("nutzer-a", "t-fremd"): "***@example.org",
        ("nutzer-a", "t-tg"): None,
        ("nutzer-b", "t-b"): "***@beispiel.de",
        ("nutzer-b", "t-staging"): "gregor-staging@henemm.com",
    }
    for uid in pfade:
        assert len(nachher[uid]) == len(vorher[uid]), f"Eintragszahl geaendert ({uid})"
        for alt, neu in zip(vorher[uid], nachher[uid]):
            assert neu.get("mail_to") == erwartet_mail_to[(uid, alt["trip_id"])], (
                f"mail_to falsch fuer {uid}/{alt['trip_id']}: {neu}"
            )
            ohne_alt = {k: v for k, v in alt.items() if k != "mail_to"}
            ohne_neu = {k: v for k, v in neu.items() if k != "mail_to"}
            assert ohne_neu == ohne_alt, f"Felder ausser mail_to veraendert: {alt} -> {neu}"
            assert ("mail_to" in neu) == ("mail_to" in alt), (
                f"mail_to-Schluessel hinzugefuegt/entfernt: {alt} -> {neu}"
            )
