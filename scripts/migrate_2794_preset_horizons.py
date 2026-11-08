#!/usr/bin/env python3
"""Migration Issue #2794 S3a: Zeithorizonte eigener Vorlagen auf „alle Tage“ (W5b).

Spec docs/specs/modules/feat_2794_s3a_reiter_wetter.md §6 „Migration“ (AC-26).
Je Nutzer ``<root>/<uid>/metric_presets.json``: aus jedem Metrik-Eintrag jeder
Vorlage wird der Schluessel ``horizons`` entfernt. Fehlend heisst beim Lesen
„alle Tage“ (Go ``store.migrateMetricPreset``, Python-Renderer
``output/renderers/email/helpers.py``). Alle anderen Felder bleiben im Wert
unveraendert (Read-Modify-Write, kein Replace).
Ablauf, Sicherung, Sperre und atomares Schreiben wie
``scripts/migrate_2793_alarm_ab.py`` (``schreiben`` aus migrate_2792).

Exit: 0 fertig, 1 offene Dateien (erneut laufen lassen).

Usage: python3 scripts/migrate_2794_preset_horizons.py --root <data/users> [--backup-dir <p>] [--execute]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from migrate_2792_profil_ampel import schreiben  # noqa: E402  (Sperre, Inhaltsvergleich, atomar)

DATEI = "metric_presets.json"


def _datei_planen(pfad: Path, bericht: list) -> tuple[list, str] | None:
    text = pfad.read_text(encoding="utf-8")
    try:
        presets = json.loads(text)
    except ValueError:
        bericht.append("    unlesbar, übersprungen")
        return None
    if not isinstance(presets, list):
        bericht.append("    kein Vorlagen-Array, übersprungen")
        return None
    neu = copy.deepcopy(presets)
    entfernt = 0
    for p in neu:
        if not isinstance(p, dict) or not isinstance(p.get("metrics"), list):
            continue
        for e in p["metrics"]:
            if isinstance(e, dict) and "horizons" in e:
                bericht.append(f"    {p.get('name', p.get('id', '?'))}: {e.get('metric_id', '?')} "
                               f"horizons {json.dumps(e['horizons'], ensure_ascii=False)} -> alle Tage")
                del e["horizons"]
                entfernt += 1
    if not entfernt:
        bericht.append("    keine Zeithorizonte: unverändert")
        return None
    return neu, text


def planen(root: Path) -> tuple[dict, list[str]]:
    """Phase 1: alle Nutzer planen, nichts schreiben. Nutzer = echte Ordner."""
    plaene, bericht = {}, []
    for udir in sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
        pfad = udir / DATEI
        if not pfad.is_file():
            continue
        bericht.append(f"== Nutzer {udir.name} ==")
        zeilen: list[str] = []
        ergebnis = _datei_planen(pfad, zeilen)
        bericht += [f"  {DATEI}: {'wird geändert' if ergebnis else 'unverändert'}", *zeilen]
        if ergebnis:
            plaene[udir] = [(pfad, *ergebnis)]
    return plaene, bericht


def _sichern(udir: Path, backup_dir: Path, stempel: str) -> Path:
    ziel = backup_dir / f"migrate-2794-{udir.name}-{stempel}.tar.gz"
    with tarfile.open(ziel, "w:gz") as tar:
        tar.add(udir / DATEI, arcname=f"{udir.name}/{DATEI}")
    return ziel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1
    plaene, bericht = planen(root)
    print("\n".join(bericht))
    if not plaene:
        print("Nichts zu tun: alle Dateien bereits migriert.")
    if not args.execute or not plaene:
        print("" if args.execute else "Probelauf: nichts geschrieben (--execute zum Ausführen).")
        return 0
    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for udir in plaene:  # Phase 2: erst alle Sicherungen, dann schreiben
            print(f"Sicherung geschrieben: {_sichern(udir, backup_dir, stempel)}")
    except OSError as exc:
        print(f"Error: Sicherung nach '{backup_dir}' fehlgeschlagen, nichts geschrieben: {exc}", file=sys.stderr)
        return 1
    offen = schreiben(plaene)
    print(f"Migration abgeschlossen: {sum(map(len, plaene.values())) - len(offen)} Datei(en) geschrieben.")
    for zeile in offen:
        print(f"Error: {zeile} -- erneut laufen lassen", file=sys.stderr)
    return 1 if offen else 0


if __name__ == "__main__":
    sys.exit(main())
