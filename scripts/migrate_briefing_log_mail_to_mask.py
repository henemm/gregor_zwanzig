#!/usr/bin/env python3
"""Einmalige Bestandsmigration (#2157): maskiert Klartext-``mail_to`` in
``<root>/users/<user_id>/briefing_log.json`` per ``mask_addr_for_pii_log()``.

Read-Modify-Write: nur ``entries[].mail_to`` wird ersetzt, vor dem Schreiben
liegt ``briefing_log.json.bak`` mit den Originalbytes daneben. ``--dry-run``
zaehlt nur und schreibt nichts.

    python scripts/migrate_briefing_log_mail_to_mask.py --root <datenwurzel> [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from output.channels.email import mask_addr_for_pii_log  # noqa: E402


def _migriere_datei(pfad: Path, dry_run: bool) -> tuple[int, int]:
    original = pfad.read_bytes()
    daten = json.loads(original)
    maskiert = unveraendert = 0
    for eintrag in daten.get("entries", []):
        alt = eintrag.get("mail_to")
        neu = mask_addr_for_pii_log(alt) if alt else alt
        if neu == alt:
            unveraendert += 1
            continue
        eintrag["mail_to"] = neu
        maskiert += 1
    if maskiert and not dry_run:
        pfad.with_name(pfad.name + ".bak").write_bytes(original)
        pfad.write_text(json.dumps(daten, indent=2, ensure_ascii=False), encoding="utf-8")
    return maskiert, unveraendert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    summe_maskiert = summe_unveraendert = 0
    for pfad in sorted((args.root / "users").glob("*/briefing_log.json")):
        maskiert, unveraendert = _migriere_datei(pfad, args.dry_run)
        print(f"{pfad}: {maskiert} maskiert, {unveraendert} unverändert")
        summe_maskiert += maskiert
        summe_unveraendert += unveraendert

    modus = " (Dry-Run, nichts geschrieben)" if args.dry_run else ""
    print(f"{summe_maskiert} Einträge maskiert, {summe_unveraendert} unverändert{modus}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
