#!/usr/bin/env python3
"""Migration Issue #3196: Trip-Feld ``tempo`` (Fortbewegung + Grundtempo).

Spec docs/specs/modules/feat_3196_trip_tempo_etappen.md (AC-10, ADR-0108 Nr. 5).
Je Nutzer ``<root>/<uid>/briefings/*.json`` (nur Trips, ``kind != vergleich``):

- fehlt ``tempo``, wird es aus dem Altfeld ``activity`` abgeleitet
  (``core.naismith.derive_tempo``: fahrrad_15/20/25 -> rad 15/20/25, alles
  andere -> fuss 4; nie mtb oder ski). Ein vorhandenes ``tempo`` bleibt.
- ``arrival_calculated`` der Wegpunkte wird mit diesem Tempo nach DAV neu
  berechnet (PO 2026-11-20: Gehzeiten aendern sich bewusst einmalig), damit
  die bewerteten Stunden je Wegpunkt sofort den neuen Gehzeiten folgen.

``activity`` und alle anderen Felder bleiben im Wert unveraendert
(Read-Modify-Write, kein Replace, #102). Unveraenderte Dateien werden nicht
geschrieben; ein zweiter Lauf aendert nichts. Ablauf, Sicherung, Sperre und
atomares Schreiben wie ``scripts/migrate_2794_preset_horizons.py``
(``schreiben`` aus migrate_2792). Ausfuehrung nach dem Prod-Deploy.

Exit: 0 fertig, 1 offene Dateien (erneut laufen lassen).

Usage: python3 scripts/migrate_3196_trip_tempo.py --root <data/users> [--backup-dir <p>] [--execute]
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

from app.loader import load_trip_from_dict  # noqa: E402
from core.naismith import compute_stage_arrivals, derive_tempo, tempo_speeds  # noqa: E402
from migrate_2792_profil_ampel import schreiben  # noqa: E402  (Sperre, Inhaltsvergleich, atomar)

ORDNER = "briefings"


def _ankuenfte(neu: dict) -> int:
    """Setzt ``arrival_calculated`` je Wegpunkt nach DAV; liefert die Zahl der Aenderungen.

    Zuordnung ueber Etappen- und Wegpunkt-Kennung; nur Wegpunkte mit Kennung
    werden angefasst, alle anderen Felder bleiben.
    """
    try:
        trip = load_trip_from_dict(copy.deepcopy(neu))
    except Exception:  # noqa: BLE001 -- unlesbarer Trip: Ankuenfte unveraendert lassen
        return 0
    speeds = tempo_speeds(trip)
    berechnet: dict[tuple, str] = {}
    for stage in trip.stages:
        for wp in compute_stage_arrivals(stage, speeds).waypoints:
            if wp.arrival_calculated is not None:
                berechnet[(stage.id, wp.id)] = wp.arrival_calculated
    geaendert = 0
    for st in neu.get("stages") or []:
        if not isinstance(st, dict):
            continue
        for wp in st.get("waypoints") or []:
            if not isinstance(wp, dict):
                continue
            wert = berechnet.get((st.get("id"), wp.get("id")))
            if wert is not None and wp.get("arrival_calculated") != wert:
                wp["arrival_calculated"] = wert
                geaendert += 1
    return geaendert


def _datei_planen(pfad: Path, bericht: list) -> tuple[dict, str] | None:
    text = pfad.read_text(encoding="utf-8")
    try:
        daten = json.loads(text)
    except ValueError:
        bericht.append(f"    {pfad.name}: unlesbar, übersprungen")
        return None
    if not isinstance(daten, dict) or daten.get("kind") == "vergleich":
        return None
    neu = copy.deepcopy(daten)
    zeile = f"    {pfad.name}: activity {daten.get('activity') or '(leer)'!r}"
    if isinstance(neu.get("tempo"), dict):
        zeile += f", tempo bleibt {json.dumps(neu['tempo'], ensure_ascii=False)}"
        tempo_neu = False
    else:
        neu["tempo"] = derive_tempo(neu.get("activity") or "")
        zeile += f" -> tempo {json.dumps(neu['tempo'], ensure_ascii=False)}"
        tempo_neu = True
    ankunft = _ankuenfte(neu)
    if ankunft:
        zeile += f", {ankunft} Ankunftszeit(en) nach DAV"
    if not tempo_neu and not ankunft:
        bericht.append(zeile + ": unverändert")
        return None
    bericht.append(zeile)
    return neu, text


def planen(root: Path) -> tuple[dict, list[str]]:
    """Phase 1: alle Nutzer planen, nichts schreiben. Nutzer = echte Ordner."""
    plaene, bericht = {}, []
    for udir in sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
        bdir = udir / ORDNER
        if not bdir.is_dir():
            continue
        bericht.append(f"== Nutzer {udir.name} ==")
        plan = []
        for pfad in sorted(bdir.glob("*.json")):
            ergebnis = _datei_planen(pfad, bericht)
            if ergebnis:
                plan.append((pfad, *ergebnis))
        if plan:
            plaene[udir] = plan
    return plaene, bericht


def _sichern(udir: Path, plan: list, backup_dir: Path, stempel: str) -> Path:
    ziel = backup_dir / f"migrate-3196-{udir.name}-{stempel}.tar.gz"
    with tarfile.open(ziel, "w:gz") as tar:
        for pfad, _neu, _alt in plan:
            tar.add(pfad, arcname=f"{udir.name}/{ORDNER}/{pfad.name}")
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
        print("Nichts zu tun: alle Trips bereits migriert.")
    if not args.execute or not plaene:
        print("" if args.execute else "Probelauf: nichts geschrieben (--execute zum Ausführen).")
        return 0
    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for udir, plan in plaene.items():  # Phase 2: erst alle Sicherungen, dann schreiben
            print(f"Sicherung geschrieben: {_sichern(udir, plan, backup_dir, stempel)}")
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
