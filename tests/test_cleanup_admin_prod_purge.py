"""TDD RED — Issue #1284: `admin`-Testdaten-Sammelbecken im Prod-Baum entfernen.

Spec: docs/specs/modules/fix_1284_admin_prod_testdata.md, Sektion "Test Plan"
      Test 1-3.
Context: docs/context/fix-1284-e2e-leichen-prod.md

Abgedeckte Tests (RED-Phase):
    Test 1: kompletter admin-Baum weg, tar.gz-Backup vorher, die vier echten
            Konten (default/henning/steffi/validator-issue110) byte-identisch
            unangetastet.
    Test 2: Fail-Fast bei fehlendem echten Konto (z.B. steffi) -- kein
            Backup, keine Löschung, admin/ bleibt bestehen.
    Test 3: Idempotenz -- bereits bereinigter Baum (kein admin/ mehr),
            zweiter --execute-Lauf: 0 Aktionen, kein neues Backup.

Heute ROT: `scripts/cleanup_1284_admin_prod.py` existiert noch nicht ->
ImportError bei jedem Test.

Alle Fixtures liegen ausschließlich in tmp_path -- KEINE Berührung von
<repo>/data/users (Wächter aus tests/conftest.py:67 würde sonst zuschlagen)
oder gar des echten Prod-Baums.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path

# Die vier echten Konten, die laut Spec (AC-1) byte-identisch unangetastet
# bleiben müssen -- NICHT admin, das ist das Sammelbecken.
REAL_ACCOUNTS = ("default", "henning", "steffi", "validator-issue110")


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_fixture_tree(users_root: Path) -> None:
    """Mini-Abbild des Prod-Baums: `admin/` (Sammelbecken, inkl. user.json +
    briefings/*.json, davon ein sofort abbrechendes Preset ohne Orte und
    eines mit Ort) und die vier echten Konten mit je mindestens einer
    Nutzdatei."""
    _write_json(
        users_root / "admin" / "user.json",
        {"mail_to": "admin@example.com"},
    )
    _write_json(
        users_root / "admin" / "briefings" / "cp-b64ae1f2da2fc922.json",
        {"id": "cp-b64ae1f2da2fc922", "kind": "vergleich", "location_ids": []},
    )
    _write_json(
        users_root / "admin" / "briefings" / "cp-ski-tirol.json",
        {"id": "cp-ski-tirol", "kind": "vergleich", "location_ids": ["loc-1"]},
    )

    _write_json(
        users_root / "default" / "user.json",
        {"mail_to": "henning@henemm.com"},
    )
    _write_json(
        users_root / "default" / "trips" / "gr221-mallorca.json",
        {"id": "gr221-mallorca", "name": "GR221 Mallorca"},
    )
    _write_json(
        users_root / "henning" / "user.json",
        {"mail_to": "henning@henemm.com"},
    )
    _write_json(
        users_root / "henning" / "briefings" / "real-preset.json",
        {"id": "real-preset", "kind": "vergleich"},
    )
    _write_json(
        users_root / "steffi" / "user.json",
        {"mail_to": "steffi.emmrich@gmail.com"},
    )
    _write_json(
        users_root / "validator-issue110" / "user.json",
        {"mail_to": "validator@example.com"},
    )
    _write_json(
        users_root / "validator-issue110" / "trips" / "v1.json",
        {"id": "v1"},
    )


def _real_accounts_snapshot(users_root: Path) -> dict[str, str]:
    """SHA-256 aller Dateien der vier echten Konten -- Nachweis
    "byte-identisch unangetastet" (Test 1), nicht bloß Existenz-Check."""
    snapshot: dict[str, str] = {}
    for name in REAL_ACCOUNTS:
        root = users_root / name
        if not root.exists():
            continue
        for f in sorted(root.rglob("*")):
            if f.is_file():
                snapshot[str(f.relative_to(users_root))] = _sha256(f)
    return snapshot


def test_execute_removes_admin_tree_with_backup_and_real_accounts_untouched(tmp_path):
    """Test 1 (Spec Test Plan): Given tmp-Baum mit `admin/` (user.json +
    briefings/*.json) und den vier echten Konten `default`/`henning`/
    `steffi`/`validator-issue110` / When `run_cleanup(..., execute=True)`
    läuft / Then existiert vorher ein tar.gz-Backup von `admin/`, danach ist
    `admin/` vollständig entfernt, und die vier echten Konten sind
    byte-identisch unverändert.

    Heute ROT: `scripts/cleanup_1284_admin_prod` existiert nicht ->
    ImportError.
    """
    from scripts.cleanup_1284_admin_prod import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)

    before = _real_accounts_snapshot(users_root)
    assert (users_root / "admin").exists(), "Fixture-Fehler: admin/ fehlt vor dem Lauf"

    result = run_cleanup(users_root, backup_dir, execute=True)

    backups = list(backup_dir.glob("*.tar.gz")) if backup_dir.exists() else []
    assert backups, f"Test 1 verletzt: kein tar.gz-Backup geschrieben, Ergebnis: {result}"

    assert not (users_root / "admin").exists(), (
        "Test 1 verletzt: data/users/admin/ wurde nicht vollständig entfernt"
    )
    for name in REAL_ACCOUNTS:
        assert (users_root / name).exists(), (
            f"Test 1 verletzt: echtes Konto {name} wurde entfernt"
        )
    after = _real_accounts_snapshot(users_root)
    assert after == before, (
        "Test 1 verletzt: echte Konten sind nicht byte-identisch unangetastet "
        f"geblieben. Vorher: {before}, nachher: {after}"
    )
    assert result.get("actions", 0) >= 1, f"Erwartet >=1 Aktion, bekam: {result}"


def test_execute_refuses_when_a_real_account_is_missing(tmp_path):
    """Test 2 (Spec Test Plan): Given tmp-Baum, in dem `steffi` fehlt / When
    das Skript mit `--execute` läuft / Then bricht es ohne Backup und ohne
    Löschung ab (Fail-Fast-Schutz gegen falschen `--root`).

    Heute ROT: `scripts/cleanup_1284_admin_prod` existiert nicht ->
    ImportError.
    """
    from scripts.cleanup_1284_admin_prod import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)
    shutil.rmtree(users_root / "steffi")

    result = run_cleanup(users_root, backup_dir, execute=True)

    assert (users_root / "admin").exists(), (
        "Test 2 verletzt: trotz fehlendem echten Konto (steffi) wurde admin/ gelöscht"
    )
    assert not backup_dir.exists() or not any(backup_dir.iterdir()), (
        "Test 2 verletzt: Backup trotz fehlgeschlagenem Sanity-Check geschrieben"
    )
    assert result.get("error"), f"Test 2 verletzt: kein Fehlerhinweis im Ergebnis: {result}"
    assert "steffi" in result.get("missing_real_accounts", []), result


def test_execute_is_idempotent_on_already_cleaned_tree(tmp_path):
    """Test 3 (Spec Test Plan): Given ein bereits bereinigter tmp-Baum (kein
    `admin/` mehr vorhanden) / When das Skript ein zweites Mal mit
    `--execute` läuft / Then werden 0 Aktionen ausgeführt und kein neues
    Backup geschrieben (Idempotenz).

    Heute ROT: `scripts/cleanup_1284_admin_prod` existiert nicht ->
    ImportError.
    """
    from scripts.cleanup_1284_admin_prod import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)

    first = run_cleanup(users_root, backup_dir, execute=True)
    assert not (users_root / "admin").exists(), (
        f"Fixture-Vorbereitung fehlgeschlagen: admin/ nach erstem Lauf noch da: {first}"
    )
    backups_after_first = list(backup_dir.glob("*.tar.gz")) if backup_dir.exists() else []
    assert len(backups_after_first) == 1, (
        "Fixture-Vorbereitung: erwartet genau 1 Backup nach erstem Lauf, "
        f"gefunden: {backups_after_first}"
    )

    second = run_cleanup(users_root, backup_dir, execute=True)

    assert second.get("actions", -1) == 0, (
        f"Test 3 verletzt: zweiter --execute-Lauf ist nicht idempotent: {second}"
    )
    backups_after_second = list(backup_dir.glob("*.tar.gz"))
    assert len(backups_after_second) == len(backups_after_first), (
        "Test 3 verletzt: zweiter Lauf hat ein neues Backup geschrieben. "
        f"Vorher: {backups_after_first}, nachher: {backups_after_second}"
    )


def test_dry_run_reports_missing_real_accounts(tmp_path):
    """F001 (Adversary Fix-Loop 1, MEDIUM): Given ein tmp-Baum, in dem
    `steffi` fehlt / When `run_cleanup(..., execute=False)` (Dry-Run) läuft
    / Then meldet das Ergebnis `missing_real_accounts` nicht-leer -- der
    Dry-Run darf die Warnung, für die er da ist, nicht verschweigen. Vor dem
    Fix lief der Check nur im `--execute`-Zweig, Dry-Run meldete immer `[]`.
    """
    from scripts.cleanup_1284_admin_prod import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)
    shutil.rmtree(users_root / "steffi")

    result = run_cleanup(users_root, backup_dir, execute=False)

    assert "steffi" in result.get("missing_real_accounts", []), (
        f"F001 verletzt: Dry-Run verschweigt fehlendes echtes Konto: {result}"
    )
    assert result.get("actions", -1) == 0, "Dry-Run darf nicht löschen"
    assert (users_root / "admin").exists(), "Dry-Run darf admin/ nicht löschen"
    assert not backup_dir.exists() or not any(backup_dir.iterdir()), (
        "Dry-Run darf kein Backup schreiben"
    )


def test_execute_refuses_when_admin_is_a_symlink(tmp_path):
    """F002 (Adversary Fix-Loop 1, LOW): Given `admin` ist ein Symlink statt
    eines echten Verzeichnisses / When `run_cleanup(..., execute=True)`
    läuft / Then bricht der Lauf sauber ab -- kein Backup (ein tar-Backup
    eines Symlinks enthielte nur den Symlink-Eintrag, keine echte
    Sicherung), keine Löschung, klarer Fehlerhinweis im Ergebnis.
    """
    from scripts.cleanup_1284_admin_prod import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)

    admin_dir = users_root / "admin"
    real_target = tmp_path / "somewhere-else"
    real_target.mkdir()
    shutil.rmtree(admin_dir)
    admin_dir.symlink_to(real_target, target_is_directory=True)

    result = run_cleanup(users_root, backup_dir, execute=True)

    assert result.get("error"), f"F002 verletzt: kein Fehlerhinweis bei Symlink-admin: {result}"
    assert admin_dir.is_symlink() and admin_dir.exists(), (
        "F002 verletzt: Symlink-admin wurde entfernt"
    )
    assert not backup_dir.exists() or not any(backup_dir.iterdir()), (
        "F002 verletzt: Backup trotz Symlink-admin geschrieben"
    )


def test_backup_leaves_no_partial_file_on_failure(tmp_path):
    """F003 (Adversary Fix-Loop 1, LOW): Given der tar-Lauf bricht mittendrin
    ab (hier: unlesbare Datei unter `admin/` durch Permission-Entzug) / When
    `run_cleanup(..., execute=True)` läuft / Then bleibt keine
    unvollständige `.tar.gz`- oder `.tmp`-Datei im Backup-Verzeichnis liegen,
    admin/ bleibt unangetastet, und das Ergebnis trägt einen Fehlerhinweis.
    """
    from scripts.cleanup_1284_admin_prod import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)

    unreadable = users_root / "admin" / "briefings" / "cp-ski-tirol.json"
    unreadable.chmod(0o000)
    try:
        if os.access(unreadable, os.R_OK):
            import pytest

            pytest.skip("Läuft als root oder mit CAP_DAC_OVERRIDE -- chmod 000 wirkt nicht")

        result = run_cleanup(users_root, backup_dir, execute=True)

        leftovers = list(backup_dir.glob("*")) if backup_dir.exists() else []
        assert not leftovers, (
            f"F003 verletzt: Teildatei(en) nach fehlgeschlagenem Backup liegen geblieben: {leftovers}"
        )
        assert (users_root / "admin").exists(), (
            "F003 verletzt: admin/ wurde trotz fehlgeschlagenem Backup gelöscht"
        )
        assert result.get("error"), f"F003 verletzt: kein Fehlerhinweis: {result}"
    finally:
        unreadable.chmod(0o644)
