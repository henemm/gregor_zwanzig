#!/usr/bin/env python3
"""Migration Issue #3157 (B6): Bestands-Abos ins Tabellenformat ``placements``.

Spec docs/specs/modules/feat_3157_migration_placements.md (AC-1..AC-10),
Mutter-Spec docs/specs/modules/feat_3122_was_steht_wo.md (Teil A Nr. 8), ADR-0124.
Je Nutzer ``<root>/<uid>/briefings/*.json`` (Trips und Orts-Vergleiche):

- Abos mit lesbarem ``display_config.placements`` bleiben unangetastet
  (``services.placements.read_placements``).
- Sonst rechnet allein ``services.placements.placements_from_legacy`` die
  Tabelle aus den Altfelden um (Abo geladen wie in der Tabellen-Ansicht).
  Geschrieben wird nur ``display_config.placements`` und bei
  ``show_stability_off`` zusaetzlich ``report_config.show_stability=false``;
  alle anderen Felder (auch die Altfelder) bleiben inhaltsgleich (Roh-JSON,
  Read-Modify-Write, #102). Keine eigene Umrechnungslogik.
- Fail-closed: Aenderungsart ``unerklaert`` oder Lade-/Umrechnungsfehler ->
  Abo unangetastet, ``Fehler`` mit Grund im Bericht, Exit 1; andere Abos weiter.

Bericht je Abo eine Zeile: Nutzer, Abo-Id, Flaeche (Trip|Orte), Status
(``hat schon placements`` | ``wird umgerechnet`` | ``Fehler``), ``<art>=<anzahl>``.
Mit ``--execute`` je Nutzer zuerst ``migrate-3157-<uid>-<timestamp>.tar.gz``;
scheitert sie, wird fuer diesen Nutzer nichts geschrieben. Sperre, Inhaltsvergleich
und atomares Schreiben: ``schreiben`` aus migrate_2792. Idempotent.

Exit: 0 fertig, 1 Fehler-Abos, gescheiterte Sicherung oder offene Dateien.

Usage: python3 scripts/migrate_3157_placements.py --root <data/users> [--backup-dir <p>] [--execute]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from app.loader import compare_preset_to_dict, load_compare_presets, load_trip, user_dir  # noqa: E402
from app.models import slot_aktiv  # noqa: E402
from services.compare_slot_scheduler import resolve_preset_slots  # noqa: E402
from services.placements import placements_from_legacy, read_placements  # noqa: E402
from migrate_2792_profil_ampel import schreiben  # noqa: E402  (Sperre, Inhaltsvergleich, atomar)

ORDNER = "briefings"
UNERKLAERT = "unerklaert"
HAT_SCHON, WIRD, FEHLER = "hat schon placements", "wird umgerechnet", "Fehler"


class AboFehler(Exception):
    """Abo nicht ladbar oder nicht umrechenbar (fail-closed)."""


def _umrechnung_orte(pfad: Path, abo_id: str):
    """Orte-Abo ueber den Lade-Weg der Tabellen-Ansicht umrechnen."""
    udir = pfad.parent.parent
    data_root = udir.parent.parent
    if user_dir(data_root, udir.name).resolve() != udir.resolve():
        raise AboFehler("Nutzerverzeichnis liegt nicht unter <data>/users")
    treffer = [p for p in load_compare_presets(user_id=udir.name, data_root=data_root)
               if p.id == abo_id]
    if len(treffer) != 1:
        raise AboFehler("Orts-Vergleich nicht ladbar")
    preset = compare_preset_to_dict(treffer[0])
    slots = resolve_preset_slots(preset)
    return placements_from_legacy(
        preset.get("display_config") or {}, "compare",
        enabled_reports=tuple(rt for rt, an in (("morning", slots.morning_enabled),
                                                ("evening", slots.evening_enabled)) if an),
        outlook_enabled=preset.get("outlook_enabled"))


def _umrechnung_trip(pfad: Path):
    """Trip ueber den Lade-Weg der Tabellen-Ansicht umrechnen."""
    trip = load_trip(str(pfad))
    if trip is None:
        raise AboFehler("Trip nicht ladbar")
    rc = trip.report_config
    return placements_from_legacy(
        trip.display_config, "trip", report_config=rc,
        enabled_reports=tuple(rt for rt in ("morning", "evening") if slot_aktiv(rc, rt)))


def _neu(daten: dict, umgerechnet) -> dict:
    """Roh-JSON plus ``placements`` (und ggf. ``show_stability=false``)."""
    neu = copy.deepcopy(daten)
    if neu.get("display_config") is None:  # Altabo ohne display_config: nur placements neu
        neu["display_config"] = {}
    neu["display_config"]["placements"] = umgerechnet.placements
    if umgerechnet.show_stability_off:
        rc = neu.get("report_config")
        if not isinstance(rc, dict):
            raise AboFehler("report_config fehlt, show_stability nicht setzbar")
        rc["show_stability"] = False
    return neu


def _abo_planen(pfad: Path) -> dict:
    """Ein Abo planen; liefert Bericht-Bausteine und ggf. den Schreibplan."""
    info = {"id": pfad.stem, "flaeche": "Trip", "arten": Counter(), "plan": None, "grund": ""}
    try:
        text = pfad.read_text(encoding="utf-8")
        daten = json.loads(text)
        if not isinstance(daten, dict):
            raise AboFehler("kein Objekt")
        # Fehlendes/null display_config ist kein Ladefehler (Modell-Default, #3157 AC-11).
        dc = daten.get("display_config")
        dc = {} if dc is None else dc
        if not isinstance(dc, dict):
            raise AboFehler("display_config ist kein Objekt")
        info["id"] = str(daten.get("id") or pfad.stem)
        orte = daten.get("kind") == "vergleich"
        info["flaeche"] = "Orte" if orte else "Trip"
        if read_placements(dc.get("placements")) is not None:
            info["status"] = HAT_SCHON
            return info
        umgerechnet = _umrechnung_orte(pfad, info["id"]) if orte else _umrechnung_trip(pfad)
        info["arten"] = Counter(c.kind for c in umgerechnet.changes)
        if info["arten"][UNERKLAERT]:
            raise AboFehler(f"Änderungsart {UNERKLAERT}, nichts geschrieben")
        info["plan"] = (pfad, _neu(daten, umgerechnet), text)
        info["status"] = WIRD
    except Exception as exc:  # noqa: BLE001 -- fail-closed: jedes Problem -> Abo unangetastet
        grund = str(exc) if isinstance(exc, AboFehler) else f"nicht ladbar oder umrechenbar ({type(exc).__name__}: {exc})"
        info.update(status=FEHLER, grund=grund, plan=None)
    return info


def _zeile(uid: str, info: dict) -> str:
    zeile = f"  {uid} {info['id']} {info['flaeche']}: {info['status']}"
    if info["grund"]:
        zeile += f" ({info['grund']})"
    arten = " ".join(f"{art}={n}" for art, n in sorted(info["arten"].items()))
    return zeile + (f" {arten}" if arten else "")


def planen(root: Path) -> tuple[dict, list[str], Counter, Counter]:
    """Phase 1: alle Nutzer planen, nichts schreiben. Nutzer = echte Ordner."""
    plaene, bericht, status, arten = {}, [], Counter(), Counter()
    for udir in sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
        bdir = udir / ORDNER
        if not bdir.is_dir():
            continue
        bericht.append(f"== Nutzer {udir.name} ==")
        plan = []
        for pfad in sorted(bdir.glob("*.json")):
            info = _abo_planen(pfad)
            bericht.append(_zeile(udir.name, info))
            status[info["status"]] += 1
            arten.update(info["arten"])
            if info["plan"]:
                plan.append(info["plan"])
        if plan:
            plaene[udir] = plan
    return plaene, bericht, status, arten


def _summen(status: Counter, arten: Counter) -> list[str]:
    zeilen = ["Summe je Status: " + (", ".join(f"{s}={n}" for s, n in sorted(status.items())) or "keine Abos")]
    if arten:
        zeilen.append("Summe je Änderungsart: " + ", ".join(f"{a}={n}" for a, n in sorted(arten.items())))
    return zeilen


def _sichern(udir: Path, plan: list, backup_dir: Path, stempel: str) -> Path:
    ziel = backup_dir / f"migrate-3157-{udir.name}-{stempel}.tar.gz"
    try:
        with tarfile.open(ziel, "w:gz") as tar:
            for pfad, _neu, _alt in plan:
                tar.add(pfad, arcname=f"{udir.name}/{ORDNER}/{pfad.name}")
    except BaseException:
        ziel.unlink(missing_ok=True)
        raise
    return ziel


def ausfuehren(plaene: dict, backup_dir: Path) -> int:
    """Phase 2: je Nutzer erst Sicherung, dann schreiben. Liefert Zahl der Probleme."""
    stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    probleme, geschrieben = 0, 0
    for udir, plan in plaene.items():
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            print(f"Sicherung geschrieben: {_sichern(udir, plan, backup_dir, stempel)}")
        except OSError as exc:
            print(f"Error: Sicherung für Nutzer {udir.name} nach '{backup_dir}' fehlgeschlagen, "
                  f"für diesen Nutzer nichts geschrieben: {exc}", file=sys.stderr)
            probleme += 1
            continue
        offen = schreiben({udir: plan})
        geschrieben += len(plan) - len(offen)
        for zeile in offen:
            print(f"Error: {zeile} -- erneut laufen lassen", file=sys.stderr)
        probleme += len(offen)
    print(f"Migration abgeschlossen: {geschrieben} Datei(en) geschrieben.")
    return probleme


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
    plaene, bericht, status, arten = planen(root)
    print("\n".join(bericht + _summen(status, arten)))
    fehler = status[FEHLER]
    if fehler:
        print(f"Error: {fehler} Abo(s) mit Fehler, unangetastet (siehe Bericht).", file=sys.stderr)
    if not plaene:
        print("Nichts umzurechnen.")
    if not args.execute:
        print("Probelauf: nichts geschrieben (--execute zum Ausführen).")
        return 1 if fehler else 0
    if not plaene:
        return 1 if fehler else 0
    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    probleme = ausfuehren(plaene, backup_dir)
    return 1 if fehler or probleme else 0


if __name__ == "__main__":
    sys.exit(main())
