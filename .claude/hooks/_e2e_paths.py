"""
Gemeinsame E2E-Pfad-Helfer (Issue #665).

Pure Funktionen — keine Modul-Konstanten. Wird von staging_gate.py und
prod_selftest.py als dünner Shim-Layer verwendet.
"""

import subprocess
from pathlib import Path


def head_sha(repo_dir) -> str:
    """Gibt den aktuellen Git-HEAD-SHA zurück oder 'UNKNOWN' bei Fehler."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(repo_dir),
    )
    if result.returncode != 0:
        return "UNKNOWN"
    return result.stdout.strip() or "UNKNOWN"


def commit_e2e_path(repo_dir, sha) -> Path:
    """Commit-getaggter Attestation-Pfad: .claude/e2e_verified/<sha>.json

    Defensiv: leerer oder None-SHA → 'UNKNOWN' (kein kaputter Dateiname).
    """
    sha = sha or "UNKNOWN"
    return Path(repo_dir) / ".claude" / "e2e_verified" / f"{sha}.json"


def default_e2e_path(repo_dir, canonical_path, sha) -> Path:
    """Default-Pfad-Auflösung: commit-getaggt (Vorrang), sonst Singleton-Fallback.

    Existiert die commit-getaggte Datei → diese.
    Existiert nur der Singleton-Pfad → Fallback (Migration).
    Sonst die (nicht existente) getaggte Datei → wird als 'fehlt' behandelt.
    """
    tagged = commit_e2e_path(repo_dir, sha)
    if tagged.exists():
        return tagged
    if Path(canonical_path).exists():
        return Path(canonical_path)
    return tagged
