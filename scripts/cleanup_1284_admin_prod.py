#!/usr/bin/env python3
"""Bereinigungs-Script für Issue #1284 — entfernt den kompletten
`admin`-Testdaten-Sammelbecken-Baum aus dem Produktiv-Datenbaum.

Spec: docs/specs/modules/fix_1284_admin_prod_testdata.md, Sektion
"Implementation Details" AC-1. Vorbild: `scripts/cleanup_1265_prod_testdata.py`
(Dry-Run-Default, --execute, tar.gz-Backup, Fail-Fast, Idempotenz).

WICHTIG (ADR-0028, PO-Entscheid 2026-07-16): Dieses Script hebt bewusst den
`NEVER_DELETE`-Schutz für `admin` auf, den `scripts/cleanup_1265_prod_testdata.py:65`
verankert. Das ist KEIN Versehen -- `admin` hat sich seit #1265 zum reinen
E2E-Testleichen-Sammelbecken entwickelt (153 Vergleichs-Abos, siehe Spec
Purpose) und wird hier vollständig entfernt statt (wie #1265) selektiv
bereinigt. Anders als das 1265er-Script erweitert dieses Script NICHT
dessen Positivliste -- ein eigenständiges Script verhindert, dass die
NEVER_DELETE-Semantik für alle Aufrufer des 1265er-Scripts verwässert wird.

Hartkodiertes Ziel: `<users_root>/admin` -- KEIN generischer `--user`-
Parameter (Fehlbedienungs-Schutz).

Usage:
    python3 scripts/cleanup_1284_admin_prod.py --root data/users \\
        [--backup-dir <path>] [--execute]

Läuft auf dem Prod-Host als `claude-gregor` gegen den absoluten Pfad
`/home/hem/gregor_zwanzig/data/users` -- reiner Host-Schritt, kein Teil des
Code-Deploys.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

# Die vier echten Konten, die als Sanity-Check vor jeder Löschung tatsächlich
# unter users_root vorhanden sein müssen (analog #1265 REAL_ACCOUNTS, aber
# OHNE admin -- admin ist hier das Löschziel, kein zu schützendes Konto).
REAL_ACCOUNTS = ("default", "henning", "steffi", "validator-issue110")


def _missing_real_accounts(users_root: Path) -> list[str]:
    """Fail-Fast-Schutz: welche der vier echten Konten fehlen unter
    users_root als Verzeichnis -- falls ja, zeigt --root vermutlich auf den
    falschen Baum."""
    return [name for name in REAL_ACCOUNTS if not (users_root / name).is_dir()]


def _make_backup(admin_dir: Path, backup_dir: Path) -> Path:
    """Atomar (F002/F003, Adversary Fix-Loop 1): schreibt zunächst in eine
    temporäre Datei im selben Zielverzeichnis und benennt sie erst nach
    erfolgreichem Tar-Lauf auf den finalen Namen um. Bricht der Lauf
    mittendrin ab (z.B. Permission-Fehler beim Lesen einer Datei unter
    `admin_dir`), bleibt kein unvollständiges `.tar.gz` liegen -- die
    Teildatei wird entfernt und der Fehler weitergereicht."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_path = backup_dir / f"cleanup-1284-{timestamp}.tar.gz"
    tmp_path = backup_dir / f".cleanup-1284-{timestamp}.tar.gz.tmp"
    try:
        with tarfile.open(tmp_path, "w:gz") as tar:
            tar.add(admin_dir, arcname=admin_dir.name)
    except (OSError, tarfile.TarError):
        tmp_path.unlink(missing_ok=True)
        raise
    tmp_path.rename(final_path)
    return final_path


def run_cleanup(users_root: Path, backup_dir: Path, execute: bool = False) -> dict:
    """Kern-Funktion (Test-Vertrag): dry-run meldet, ob `admin/` existiert
    und ob echte Konten fehlen, ohne zu schreiben; execute sichert `admin/`
    per tar.gz-Backup und entfernt den gesamten Baum danach vollständig.
    Fail-Fast, wenn eines der vier echten Konten fehlt (falscher --root) --
    dieser Check läuft unbedingt, auch im Dry-Run (F001, Adversary
    Fix-Loop 1). Bricht ab, ohne zu sichern oder zu löschen, wenn `admin/`
    ein Symlink statt eines echten Verzeichnisses ist (F002). Idempotent
    (admin/ bereits weg: 0 Aktionen, kein Backup)."""
    users_root = Path(users_root)
    backup_dir = Path(backup_dir)
    admin_dir = users_root / "admin"

    # F001: unbedingt berechnen, auch im Dry-Run -- sonst verschweigt der
    # Dry-Run genau die Warnung, für die er da ist.
    missing_real_accounts = _missing_real_accounts(users_root)

    result: dict = {
        "admin_exists": admin_dir.exists(),
        "actions": 0,
        "backup_path": None,
        "missing_real_accounts": missing_real_accounts,
        "error": None,
    }

    if not admin_dir.exists():
        # Idempotenz: nichts zu tun, kein Backup.
        return result

    if not execute:
        return result

    if admin_dir.is_symlink():
        # F002: Symlink statt echtem Verzeichnis -- ein tar-Backup davon
        # enthielte nur den Symlink-Eintrag, kein echtes Backup. Sauber
        # abbrechen statt eine Sicherung vorzutäuschen, die es nicht gibt.
        result["error"] = (
            f"Abbruch: {admin_dir} ist ein Symlink statt eines echten "
            "Verzeichnisses -- wird nicht gesichert und nicht gelöscht."
        )
        return result

    if missing_real_accounts:
        result["error"] = (
            f"Abbruch: {users_root} enthält nicht alle vier echten Konten "
            f"({', '.join(missing_real_accounts)} fehlen) — falsches "
            "Verzeichnis? Kein Backup geschrieben, admin/ nicht gelöscht."
        )
        return result

    try:
        backup_path = _make_backup(admin_dir, backup_dir)
    except (OSError, tarfile.TarError) as exc:
        result["error"] = (
            f"Abbruch: Backup von {admin_dir} fehlgeschlagen ({exc}) -- "
            "admin/ nicht gelöscht."
        )
        return result

    # F003: Erfolgs-Print erst NACH verifiziertem (per Rename atomar
    # abgeschlossenem) Backup -- vorher wäre die Meldung eine Behauptung
    # ohne Deckung.
    result["backup_path"] = str(backup_path)
    print(f"Backup geschrieben: {backup_path} (Restore: tar xzf {backup_path} -C <ziel>)")

    shutil.rmtree(admin_dir)
    result["actions"] = 1

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/users"))
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    users_root = args.root.resolve()
    if not users_root.exists() or not users_root.is_dir():
        print(f"Error: --root existiert nicht oder ist kein Verzeichnis: {users_root}", file=sys.stderr)
        return 1
    backup_dir = (args.backup_dir or (users_root.parent / ".backups")).resolve()

    result = run_cleanup(users_root, backup_dir, execute=args.execute)

    print(f"Root: {users_root}")
    print(f"admin/ vorhanden: {result['admin_exists']}")
    if result.get("missing_real_accounts"):
        print(
            f"WARNUNG: fehlende echte Konten unter {users_root}: "
            f"{result['missing_real_accounts']} — falsches Verzeichnis?",
            file=sys.stderr,
        )

    if not args.execute:
        print("Dry-run: nichts geschrieben (--execute zum Ausführen).")
        return 0

    if result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        return 1

    if result["backup_path"]:
        print(f"Backup: {result['backup_path']}")
    print(f"Aktionen: {result['actions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
