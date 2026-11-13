#!/usr/bin/env python3
"""Migration Issue #2795 S3b Teil 1a: „Kanäle je Wettergröße“ entfällt.

Spec docs/specs/modules/feat_2795_s3b_teil1_zustellung.md §4.3 (AC-28).
Je Nutzer ``<root>/<uid>/briefings/*.json`` (Trip und Ortsvergleich): nur der
oberste Schluessel ``alert_metric_channels`` wird entfernt (Read-Modify-Write,
alle anderen Felder wertgleich). Der Alarmversand ignoriert den Schluessel
bereits; die Migration raeumt den Altbestand auf und protokolliert je Nutzer
jedes betroffene Abo mit der bisherigen Sonderregel je Metrik.

Ablauf wie ``scripts/migrate_2793_alarm_ab.py``: erst planen (Probelauf ohne
``--execute`` schreibt nichts, auch keine Sicherung), dann je betroffenem
Nutzer eine Sicherung, dann atomar schreiben ueber
``migrate_2792_profil_ampel.schreiben`` (Sperre, Inhaltsvergleich). Idempotent:
ein zweiter Lauf findet nichts mehr.

Exit: 0 fertig, 1 offene Dateien oder Fehler (erneut laufen lassen).

Usage: python3 scripts/migrate_2795_alert_metric_channels.py --root <data/users> [--backup-dir <p>] [--execute]
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

SCHLUESSEL = "alert_metric_channels"
_KANAELE = ("email", "telegram", "sms", "premium_sms")


def _kanaele(eintrag: object) -> str:
    """Eingeschaltete Kanaele eines Eintrags (``{kanal: bool}`` oder Liste)."""
    if isinstance(eintrag, dict):
        an = [k for k in _KANAELE if eintrag.get(k)]
    elif isinstance(eintrag, (list, tuple)):
        an = [k for k in _KANAELE if k in eintrag]
    else:
        an = []
    return ", ".join(an) if an else "(keiner)"


def _regel_kanaele_protokollieren(obj: dict, pfad: Path, bericht: list) -> None:
    """F003: alte ``alert_rules[].channels`` wirken seit 1a nicht mehr. Nur
    protokollieren (Verlust nachvollziehbar), die Regeln bleiben unveraendert."""
    regeln = obj.get("alert_rules")
    alt = [r for r in regeln if isinstance(r, dict) and r.get("channels")] if isinstance(regeln, list) else []
    if not alt:
        return
    abo = obj.get("id") or pfad.stem
    bericht.append(f"    Abo {abo} ({obj.get('kind') or 'unbekannt'}): alte Regel-Kanäle "
                   "wirken nicht mehr (nur protokolliert)")
    for r in alt:
        bericht.append(f"      Regel {r.get('id') or '?'} ({r.get('metric') or '?'}): {_kanaele(r['channels'])}")


def _datei_planen(pfad: Path, bericht: list) -> tuple[dict, str] | None:
    text = pfad.read_text(encoding="utf-8")
    try:
        obj = json.loads(text)
    except ValueError:
        bericht.append("    unlesbar, übersprungen")
        return None
    if not isinstance(obj, dict):
        return None
    _regel_kanaele_protokollieren(obj, pfad, bericht)
    if SCHLUESSEL not in obj:
        return None
    regel = obj[SCHLUESSEL]
    abo = obj.get("id") or pfad.stem
    bericht.append(f"    Abo {abo} ({obj.get('kind') or 'unbekannt'}): bisherige Sonderregel")
    if isinstance(regel, dict) and regel:
        for metrik, eintrag in sorted(regel.items()):
            bericht.append(f"      {metrik}: {_kanaele(eintrag)}")
    else:
        bericht.append(f"      (leer: {json.dumps(regel, ensure_ascii=False)})")
    neu = copy.deepcopy(obj)
    del neu[SCHLUESSEL]
    return neu, text


def _nutzer_planen(udir: Path) -> tuple[list, list[str]]:
    plan, bericht = [], [f"== Nutzer {udir.name} =="]
    for pfad in sorted((udir / "briefings").glob("*.json")):
        zeilen: list[str] = []
        ergebnis = _datei_planen(pfad, zeilen)
        if ergebnis is None and not zeilen:
            continue
        bericht += [f"  {pfad.relative_to(udir)}: {'wird geändert' if ergebnis else 'unverändert'}", *zeilen]
        if ergebnis:
            plan.append((pfad, *ergebnis))
    if not plan:
        bericht.append("  keine Sonderregeln")
    return plan, bericht


def planen(root: Path) -> tuple[dict, list[str]]:
    """Phase 1: alle Nutzer planen, nichts schreiben. Nutzer = echte Ordner."""
    plaene, bericht = {}, []
    for udir in sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
        plan, zeilen = _nutzer_planen(udir)
        bericht += zeilen
        if plan:
            plaene[udir] = plan
    return plaene, bericht


def _sichern(udir: Path, backup_dir: Path, stempel: str) -> Path:
    ziel = backup_dir / f"migrate-2795-{udir.name}-{stempel}.tar.gz"
    with tarfile.open(ziel, "w:gz") as tar:
        tar.add(udir / "briefings", arcname=f"{udir.name}/briefings")
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
        print("Nichts zu tun: kein Abo trägt noch alert_metric_channels.")
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
