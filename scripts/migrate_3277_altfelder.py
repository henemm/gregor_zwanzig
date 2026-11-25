#!/usr/bin/env python3
"""Datenlauf Issue #3351 (Was steht wo B6b-5): Altfelder aus dem Bestand entfernen.

Spec docs/specs/modules/feat_3351_altfelder_datenlauf.md (AC-1 bis AC-11).
Je Nutzer ``<root>/<uid>/briefings/*.json`` (Trip und Vergleich) und die tote
Altdatei ``<root>/<uid>/compare_presets.json`` (Array): die zehn Altfelder
(``app.loader.ALTFELDER``) werden auf oberster Ebene, in ``display_config`` und
in ``report_config`` entfernt (``altfelder_entfernen``); alles andere bleibt
(Read-Modify-Write mit Merge, ADR-0101). Fail-closed: ein Abo mit Altfeldern,
aber ohne vollstaendige Tabelle ``display_config.placements`` (``rows`` und
``outlook_reports`` als Liste) ist BLOCKIERT (ADR-0124); unlesbare Dateien
ebenso. Ablauf, Sicherung, Sperre und atomares Schreiben wie
``scripts/migrate_2794_preset_horizons.py`` (``schreiben`` aus migrate_2792).

Exit: 0 fertig oder nichts zu tun, 1 offene Dateien, Fehler oder Altfeld
uebrig (``--nachzaehlen``), 2 blockiert (fail-closed, nichts geschrieben).

Usage: python3 scripts/migrate_3277_altfelder.py --root <data/users> [--backup-dir <p>]
       [--ausfuehren] [--blockierte-auslassen] [--nachzaehlen]
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

from app.loader import ALTFELDER, altfelder_entfernen  # noqa: E402  (Namen nie als Literal, #3277)
from migrate_2792_profil_ampel import schreiben  # noqa: E402  (Sperre, Inhaltsvergleich, atomar)

PRESETS = "compare_presets.json"
EBENEN = (("oberste", None), ("display_config", "display_config"), ("report_config", "report_config"))


def _funde(abo: dict) -> list[tuple[str, str]]:
    """(Ebene, Feld) je Altfeld auf den drei Ebenen."""
    funde = []
    for label, schluessel in EBENEN:
        teil = abo if schluessel is None else abo.get(schluessel)
        if isinstance(teil, dict):
            funde += [(label, name) for name in ALTFELDER if name in teil]
    return funde


def _art(abo: dict, ist_presets: bool) -> str:
    return "vergleich" if ist_presets or abo.get("kind") == "vergleich" or "location_ids" in abo else "trip"


def _tabelle_ok(abo: dict) -> bool:
    dc = abo.get("display_config")
    pl = dc.get("placements") if isinstance(dc, dict) else None
    return isinstance(pl, dict) and isinstance(pl.get("rows"), list) and isinstance(pl.get("outlook_reports"), list)


def _nutzer(root: Path) -> list[Path]:
    return sorted(d for d in root.iterdir() if d.is_dir() and not d.name.startswith((".", "_")))


def zaehlen(root: Path) -> list[dict]:
    """Liest alle Dateien (rein lesend). Je Datei mit Altfeldern oder Lesefehler
    ein Eintrag: udir, pfad, rel, text, daten, funde [(uid, art, ebene, feld)], blockiert."""
    eintraege = []
    for udir in _nutzer(root):
        dateien = [(p, False) for p in sorted((udir / "briefings").glob("*.json"))]
        if (udir / PRESETS).is_file():
            dateien.append((udir / PRESETS, True))
        for pfad, ist_presets in dateien:
            rel = f"{udir.name}/{pfad.relative_to(udir)}"
            e = {"udir": udir, "pfad": pfad, "rel": rel, "text": None, "daten": None,
                 "funde": [], "blockiert": None}
            try:
                e["text"] = pfad.read_text(encoding="utf-8")
                e["daten"] = json.loads(e["text"])
            except (OSError, ValueError) as exc:
                e["blockiert"] = f"unlesbar ({exc.__class__.__name__})"
                eintraege.append(e)
                continue
            daten = e["daten"]
            if not isinstance(daten, list if ist_presets else dict):
                e["blockiert"] = "unerwartete Struktur"
                eintraege.append(e)
                continue
            for abo in (daten if ist_presets else [daten]):
                if isinstance(abo, dict):
                    art = _art(abo, ist_presets)
                    e["funde"] += [(udir.name, art, ebene, feld) for ebene, feld in _funde(abo)]
            if not e["funde"]:
                continue
            if not ist_presets and not _tabelle_ok(daten):  # fail-closed nur fuer Abos (AC-5/AC-9)
                e["blockiert"] = f"Abo {daten.get('id', pfad.stem)}: Altfelder, aber Tabelle placements unvollständig"
            eintraege.append(e)
    return eintraege


def planen(root: Path) -> tuple[dict, list[dict], list[dict]]:
    """Plaene je Nutzer (pfad, neu, alt_text), bereinigbare und blockierte Eintraege."""
    eintraege = zaehlen(root)
    offen = [e for e in eintraege if not e["blockiert"]]
    blockiert = [e for e in eintraege if e["blockiert"]]
    plaene: dict = {}
    for e in offen:
        daten = e["daten"]
        neu = ([altfelder_entfernen(copy.deepcopy(a)) if isinstance(a, dict) else a for a in daten]
               if isinstance(daten, list) else altfelder_entfernen(copy.deepcopy(daten)))
        if neu != daten:
            plaene.setdefault(e["udir"], []).append((e["pfad"], neu, e["text"]))
    return plaene, offen, blockiert


def _bericht(offen: list[dict], blockiert: list[dict], titel: str) -> list[str]:
    funde = [f for e in offen for f in e["funde"]]
    zeilen = [f"{titel}: {len(funde)} Altfeld(er) in {len(offen)} Datei(en), "
              f"{len({f[0] for f in funde})} Nutzer"]
    for name in ALTFELDER:
        auswahl = [f for f in funde if f[3] == name]
        if not auswahl:
            continue
        ebenen = Counter(f[2] for f in auswahl)
        arten = Counter(f[1] for f in auswahl)
        zeilen.append(f"  {name}: " + ", ".join(f"{lbl} {ebenen[lbl]}" for lbl, _ in EBENEN if ebenen[lbl])
                      + " | " + ", ".join(f"{a} {n}" for a, n in sorted(arten.items()))
                      + f" | {len({f[0] for f in auswahl})} Nutzer")
    for e in blockiert:
        zeilen.append(f"  BLOCKIERT: {e['rel']}: {e['blockiert']} ({len(e['funde'])} Altfeld(er))")
    if blockiert:
        zeilen.append(f"BLOCKIERT gesamt: {len(blockiert)} Datei(en) (getrennt ausgewiesen)")
    return zeilen


def _sichern(udir: Path, backup_dir: Path, stempel: str) -> Path:
    ziel = backup_dir / f"migrate-3277-{udir.name}-{stempel}.tar.gz"
    with tarfile.open(ziel, "w:gz") as tar:
        for teil in ("briefings", PRESETS):
            if (udir / teil).exists():
                tar.add(udir / teil, arcname=f"{udir.name}/{teil}")
    return ziel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--ausfuehren", action="store_true")
    parser.add_argument("--blockierte-auslassen", action="store_true")
    parser.add_argument("--nachzaehlen", action="store_true")
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {root}", file=sys.stderr)
        return 1
    if args.nachzaehlen:
        eintraege = zaehlen(root)
        offen = [e for e in eintraege if not e["blockiert"]]
        blockiert = [e for e in eintraege if e["blockiert"]]
        print("\n".join(_bericht(offen, blockiert, "Nachzählung")))
        return 1 if eintraege else 0
    plaene, offen, blockiert = planen(root)
    print("\n".join(_bericht(offen, blockiert, "Altfelder im Bestand")))
    if blockiert and not args.blockierte_auslassen:
        print("Abbruch (fail-closed): blockierte Abos, nichts geschrieben "
              "(--blockierte-auslassen, um sie unverändert zu lassen).", file=sys.stderr)
        return 2
    if blockiert:
        print(f"Ausgelassen: {len(blockiert)} blockierte Datei(en) bleiben unverändert.")
    if not plaene:
        print("Nichts zu tun: keine bereinigbaren Altfelder.")
        return 0
    if not args.ausfuehren:
        print("Probelauf: nichts geschrieben (--ausfuehren zum Ausführen).")
        return 0
    backup_dir = (args.backup_dir or (root.parent / ".backups")).resolve()
    stempel = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        for udir in plaene:  # erst alle Sicherungen, dann schreiben
            print(f"Sicherung geschrieben: {_sichern(udir, backup_dir, stempel)}")
    except OSError as exc:
        print(f"Error: Sicherung nach '{backup_dir}' fehlgeschlagen, nichts geschrieben: {exc}", file=sys.stderr)
        return 1
    offen_dateien = schreiben(plaene)
    print(f"Bereinigung abgeschlossen: {sum(map(len, plaene.values())) - len(offen_dateien)} Datei(en) geschrieben.")
    for zeile in offen_dateien:
        print(f"Error: {zeile} -- erneut laufen lassen", file=sys.stderr)
    return 1 if offen_dateien else 0


if __name__ == "__main__":
    sys.exit(main())
