"""TDD GREEN — Fix #1219 Scheibe 1: Migrationsscript
`scripts/migrate_1219_email_verified.py`.

Spec: docs/specs/modules/fix_1219_email_verify.md (AC-8)
Struktureller Vorbild: tests/tdd/test_issue_1133_testdata_cleanup.py
(subprocess-Aufruf des echten Scripts gegen eine Fixture-Baum-Kopie, NO MOCKS).

Daten-Isolation (PFLICHT): jeder Test baut seinen eigenen `tmp_path`-Baum mit
`henning`/`steffi`-Fixture-Profilen — die echten `data/users/` werden nie
angefasst (kein `--root`-Default im Script erzwingt das).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1219_email_verified.py"


def _write_profile(root: Path, user_id: str, **fields) -> Path:
    user_dir = root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / "user.json"
    path.write_text(json.dumps(fields), encoding="utf-8")
    return path


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_migrate_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=60, cwd=REPO_ROOT)


def test_ac8_dry_run_writes_nothing(tmp_path):
    """AC-8 (Dry-Run): GIVEN henning/steffi ohne email_verified_at / WHEN
    das Script OHNE --execute läuft / THEN wird kein user.json verändert,
    aber der Plan nennt beide Konten."""
    root = tmp_path / "users"
    henning_path = _write_profile(root, "henning", id="henning", mail_to="henning@henemm.com")
    steffi_path = _write_profile(root, "steffi", id="steffi", mail_to="steffi@henemm.com", sms_to="+491511234567")
    before = {henning_path: henning_path.read_text(), steffi_path: steffi_path.read_text()}

    result = _run_migrate(root)

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert henning_path.read_text() == before[henning_path], "Dry-Run darf henning/user.json nicht ändern"
    assert steffi_path.read_text() == before[steffi_path], "Dry-Run darf steffi/user.json nicht ändern"
    assert "henning" in result.stdout and "steffi" in result.stdout


def test_ac8_execute_sets_verified_at_and_preserves_other_fields(tmp_path):
    """AC-8: GIVEN henning/steffi ohne email_verified_at, mit sonstigen
    Feldern (mail_to, password_hash, passkey_credentials) / WHEN --execute
    läuft / THEN ist email_verified_at bei beiden gesetzt, alle anderen
    Felder sind byteidentisch erhalten (Read-Modify-Write-Merge)."""
    root = tmp_path / "users"
    henning_path = _write_profile(
        root, "henning", id="henning", mail_to="henning@henemm.com",
        password_hash="bcrypt$fixture", passkey_credentials=[{"id": "abc"}],
    )
    steffi_path = _write_profile(root, "steffi", id="steffi", mail_to="steffi@henemm.com")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    henning_after = json.loads(henning_path.read_text())
    steffi_after = json.loads(steffi_path.read_text())

    assert henning_after.get("email_verified_at"), "henning muss nach --execute email_verified_at haben"
    assert steffi_after.get("email_verified_at"), "steffi muss nach --execute email_verified_at haben"
    assert henning_after["mail_to"] == "henning@henemm.com"
    assert henning_after["password_hash"] == "bcrypt$fixture"
    assert henning_after["passkey_credentials"] == [{"id": "abc"}]
    assert steffi_after["mail_to"] == "steffi@henemm.com"

    backups = list((root.parent / ".backups").glob("*.tar.gz"))
    assert backups, "AC-8: --execute muss ein tar.gz-Backup vor dem Schreiben anlegen"


def test_ac8_second_execute_is_idempotent(tmp_path):
    """AC-8 (Idempotenz): GIVEN ein erster --execute-Lauf hat
    email_verified_at bereits gesetzt / WHEN ein zweiter --execute-Lauf
    folgt / THEN bleibt der ursprüngliche Zeitstempel unverändert (kein
    Überschreiben ohne --force)."""
    root = tmp_path / "users"
    henning_path = _write_profile(root, "henning", id="henning", mail_to="henning@henemm.com")
    _write_profile(root, "steffi", id="steffi", mail_to="steffi@henemm.com")

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, first.stderr
    first_verified_at = json.loads(henning_path.read_text())["email_verified_at"]

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, second.stderr
    second_verified_at = json.loads(henning_path.read_text())["email_verified_at"]

    assert first_verified_at == second_verified_at, (
        "AC-8: ein zweiter --execute-Lauf darf einen bereits gesetzten "
        f"email_verified_at-Zeitstempel nicht überschreiben (ohne --force): "
        f"{first_verified_at!r} != {second_verified_at!r}"
    )
