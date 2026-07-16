"""TDD RED — Issue #1265: Prod-Testdaten-Altlasten aufräumen + Wächter.

Spec: docs/specs/modules/issue_1265_prod_testdata_cleanup.md
Context: docs/context/fix-1265-prod-testdata-cleanup.md

Abgedeckte ACs (RED-Phase):
    AC-1: Bereinigungs-Script (Positivliste, Backup, echte Konten unangetastet,
          idempotent) — `scripts/cleanup_1265_prod_testdata.py` existiert noch
          nicht -> ImportError.
    AC-2: `compare_presets.json` des default-Users wird per Read-Modify-Write
          auf eine leere, valide Liste geleert -> ImportError (selbes Script).
    AC-4: Wächter-Selbsttest — ein Kern-Test ohne real_data_root/live-Marker,
          der unter <repo>/data/users/ schreiben will, muss künftig FAILEN.
          Heute (Wächter existiert noch nicht) läuft das Snippet grün durch
          -> dieser Test schlägt mit AssertionError fehl.

AC-3 (Go, Scheduler-Härtung) ist in der TDD-RED-Phase durch den edit_gate
gesperrt (keine *_test.go-Neuanlage außerhalb __tests__/) und kommt in
Phase 6 (Implementierung) mit.

Alle Fixtures dieser Datei liegen ausschließlich in tmp_path — mit einer
einzigen dokumentierten Ausnahme in AC-4 (s. dortiger Docstring), die sich
selbst restlos aufräumt. KEINE Berührung von /home/hem/gregor_zwanzig/data
(Produktionsdaten, TABU) oder des sonstigen Repo-Bestands.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Die vier echten Test-Presets aus der PO-bestätigten Positivliste (Spec
# Sektion "Implementation Details" A2).
_TEST_PRESET_IDS = [
    "cp-923d0c80712de2f1",
    "cp-c7c3a2ba83996ac0",
    "cp-956455a97aa5cb22",
    "cp-4c9284f8a22eb3d6",
]

# Drei der 36 gelisteten Positivlisten-Verzeichnisse (Ausschnitt genügt für
# den Kern-Test — die vollständige, wörtliche Liste lebt im Script selbst).
_SAMPLE_POSITIVLIST_DIRS = ["tdd-1012-ac1", "tdd-1007-ac1", "tdd-638-ac1"]


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_fixture_tree(users_root: Path) -> None:
    """Mini-Abbild des Prod-Baums: 3 von 36 Positivlisten-Kandidaten, die
    echten Konten default/henning/steffi/admin (inkl. compare_presets.json
    mit den vier Test-Presets) und der Klärungsfall validator-issue110
    (bleibt in dieser Runde unangetastet, Known Limitation der Spec).
    steffi/admin sind (F001, Adversary Fix-Loop 1) minimal vertreten -- die
    Sanity-Check-Prüfung auf "alle vier echten Konten vorhanden" muss auch
    im Fixture-Baum erfüllt sein, sonst verweigert das Script jeden
    --execute-Lauf."""
    # A1 — Positivlisten-Ausschnitt
    _write_json(
        users_root / "tdd-1012-ac1" / "user.json",
        {"mail_to": "gregor-test@henemm.com"},
    )
    (users_root / "tdd-1007-ac1").mkdir(parents=True, exist_ok=True)
    _write_json(
        users_root / "tdd-638-ac1" / "alert_log.json",
        [{"ts": "2026-07-01T00:00:00Z", "msg": "test-alert"}],
    )

    # Echte Konten — NIE löschen (AC-1)
    _write_json(
        users_root / "default" / "user.json",
        {"mail_to": "henning@henemm.com"},
    )
    _write_json(
        users_root / "default" / "trips" / "gr221-mallorca.json",
        {"id": "gr221-mallorca", "name": "GR221 Mallorca"},
    )
    # A2 — die vier Test-Presets, die per RMW geleert werden (AC-2)
    _write_json(
        users_root / "default" / "compare_presets.json",
        [
            {"id": pid, "name": f"Test-Preset {pid}", "empfaenger": ["test@example.com"]}
            for pid in _TEST_PRESET_IDS
        ],
    )
    _write_json(
        users_root / "henning" / "user.json",
        {"mail_to": "henning@henemm.com"},
    )
    _write_json(
        users_root / "henning" / "trips" / "real-trip.json",
        {"id": "real-trip", "name": "Echter Trip"},
    )
    _write_json(users_root / "steffi" / "user.json", {"mail_to": "steffi@example.com"})
    _write_json(users_root / "admin" / "user.json", {"mail_to": "admin@example.com"})

    # Klärungsfall — bleibt in dieser Runde stehen (Known Limitation)
    _write_json(
        users_root / "validator-issue110" / "trips" / "v1.json",
        {"id": "v1", "name": "Validator Trip"},
    )


def _real_account_snapshot(users_root: Path) -> dict[str, str]:
    """SHA-256 aller Dateien der drei "byte-identisch unangetastet"-Konten
    aus AC-1, OHNE compare_presets.json (das wird von AC-2 bewusst geändert)."""
    snapshot: dict[str, str] = {}
    for f in sorted((users_root / "default").rglob("*")):
        if f.is_file() and f.name != "compare_presets.json":
            snapshot[str(f.relative_to(users_root))] = _sha256(f)
    for f in sorted((users_root / "henning").rglob("*")):
        if f.is_file():
            snapshot[str(f.relative_to(users_root))] = _sha256(f)
    for f in sorted((users_root / "validator-issue110").rglob("*")):
        if f.is_file():
            snapshot[str(f.relative_to(users_root))] = _sha256(f)
    return snapshot


# ===========================================================================
# AC-1: Bereinigungs-Script — Positivliste, Backup, echte Konten unangetastet
# ===========================================================================


def test_ac1_dry_run_lists_candidates_and_deletes_nothing(tmp_path):
    """AC-1 dry-run: Given der Fixture-Baum mit 3 Positivlisten-Kandidaten
    und den echten Konten / When `run_cleanup(execute=False)` läuft / Then
    wird NICHTS gelöscht, kein Backup geschrieben, aber die drei Kandidaten
    werden als Kandidaten gemeldet.

    Heute ROT: `scripts/cleanup_1265_prod_testdata.py` existiert nicht ->
    ImportError.
    """
    from scripts.cleanup_1265_prod_testdata import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)

    before = _real_account_snapshot(users_root)

    result = run_cleanup(users_root, backup_dir, execute=False)

    for name in _SAMPLE_POSITIVLIST_DIRS:
        assert (users_root / name).exists(), (
            f"Dry-Run darf {name} nicht löschen"
        )
    assert set(_SAMPLE_POSITIVLIST_DIRS).issubset(
        set(result.get("would_remove_dirs", []))
    ), f"Dry-Run-Kandidatenliste unvollständig: {result}"
    assert not backup_dir.exists() or not any(backup_dir.iterdir()), (
        "Dry-Run darf kein Backup schreiben"
    )
    assert _real_account_snapshot(users_root) == before, (
        "Dry-Run darf echte Konten nicht verändern"
    )


def test_ac1_execute_backs_up_removes_positivliste_and_is_idempotent(tmp_path):
    """AC-1 execute: Given derselbe Fixture-Baum / When `run_cleanup(execute=True)`
    läuft / Then existiert vorher ein tar.gz-Backup, danach sind exakt die
    Positivlisten-Kandidaten entfernt, `default`/`henning`/`validator-issue110`
    sind (außer compare_presets.json, s. AC-2) byte-identisch unangetastet,
    und ein zweiter Lauf macht 0 Aktionen (Idempotenz).

    Heute ROT: Script existiert nicht -> ImportError.
    """
    from scripts.cleanup_1265_prod_testdata import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)

    before = _real_account_snapshot(users_root)

    first = run_cleanup(users_root, backup_dir, execute=True)

    backups = list(backup_dir.glob("*.tar.gz")) if backup_dir.exists() else []
    assert backups, "AC-1 verletzt: kein tar.gz-Backup vor der Löschung geschrieben"

    for name in _SAMPLE_POSITIVLIST_DIRS:
        assert not (users_root / name).exists(), (
            f"AC-1 verletzt: {name} (Positivliste) wurde nicht entfernt"
        )
    for name in ("default", "henning", "validator-issue110"):
        assert (users_root / name).exists(), (
            f"AC-1 verletzt: echtes Konto {name} wurde entfernt"
        )
    assert _real_account_snapshot(users_root) == before, (
        "AC-1 verletzt: echte Konten sind nicht byte-identisch unangetastet "
        "geblieben"
    )
    assert first.get("actions", 0) >= len(_SAMPLE_POSITIVLIST_DIRS), (
        f"Erwartet mindestens {len(_SAMPLE_POSITIVLIST_DIRS)} Aktionen, "
        f"bekam: {first}"
    )

    second = run_cleanup(users_root, backup_dir, execute=True)
    assert second.get("actions", -1) == 0, (
        f"AC-1 verletzt: zweiter --execute-Lauf ist nicht idempotent, "
        f"Rückgabe: {second}"
    )
    assert second.get("removed_dirs", []) == [], (
        f"AC-1 verletzt: zweiter Lauf hat erneut Verzeichnisse entfernt: {second}"
    )


def test_ac1_sanity_check_refuses_execute_without_real_accounts(tmp_path):
    """F001 (Adversary Fix-Loop 1, HIGH): Given ein users_root OHNE jedes der
    vier echten Konten (default/henning/steffi/admin) -- z.B. weil --root
    versehentlich auf ein falsches Verzeichnis zeigt -- / When run_cleanup
    mit execute=True aufgerufen wird / Then verweigert das Script die
    Ausführung (kein Backup, keine Löschung) und meldet die fehlenden Konten
    im Ergebnis."""
    from scripts.cleanup_1265_prod_testdata import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    (users_root / "tdd-638-ac1").mkdir(parents=True)  # nur ein Kandidat, KEIN echtes Konto

    result = run_cleanup(users_root, backup_dir, execute=True)

    assert (users_root / "tdd-638-ac1").exists(), (
        "F001 verletzt: trotz fehlender echter Konten wurde gelöscht"
    )
    assert not backup_dir.exists() or not any(backup_dir.iterdir()), (
        "F001 verletzt: Backup trotz fehlgeschlagenem Sanity-Check geschrieben"
    )
    assert result.get("error"), f"F001 verletzt: kein Fehlerhinweis im Ergebnis: {result}"
    assert set(result.get("missing_real_accounts", [])) == {
        "default", "henning", "steffi", "admin",
    }, result


def test_ac1_never_delete_positivlist_overlap_check_raises_on_conflict():
    """F004 (Adversary Fix-Loop 1, LOW): Given ein hypothetischer Konflikt
    zwischen Positivliste und NEVER_DELETE / When der Start-Check läuft /
    Then wirft er laut (AssertionError) statt lautlos zu maskieren -- und
    für die reale, konfliktfreie Konfiguration bleibt er still."""
    from scripts.cleanup_1265_prod_testdata import (  # noqa: PLC0415
        NEVER_DELETE,
        POSITIVLIST_DIRS,
        _assert_no_positivlist_never_delete_overlap,
    )

    with pytest.raises(AssertionError):
        _assert_no_positivlist_never_delete_overlap(["default", "tdd-x"], {"default"})

    _assert_no_positivlist_never_delete_overlap(["tdd-x"], {"default"})  # kein Raise

    # Reale Konfiguration ist tatsächlich konfliktfrei (Modul-Import-Zeit-
    # Assertion in scripts/cleanup_1265_prod_testdata.py wäre sonst bereits
    # beim Import dieses Tests fehlgeschlagen).
    _assert_no_positivlist_never_delete_overlap(POSITIVLIST_DIRS, NEVER_DELETE)


# ===========================================================================
# AC-2: default-User compare_presets.json — RMW auf leere, valide Liste
# ===========================================================================


def test_ac2_compare_presets_emptied_to_valid_empty_list(tmp_path):
    """AC-2: Given `compare_presets.json` des default-Users mit den vier
    Test-Presets / When das Script mit `--execute` (via run_cleanup) läuft /
    Then enthält die Datei danach eine leere, valide JSON-Liste — die Datei
    selbst bleibt bestehen (kein Löschen der Datei, nur RMW des Inhalts).

    Heute ROT: Script existiert nicht -> ImportError.
    """
    from scripts.cleanup_1265_prod_testdata import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    backup_dir = tmp_path / "backups"
    _build_fixture_tree(users_root)
    presets_path = users_root / "default" / "compare_presets.json"

    result = run_cleanup(users_root, backup_dir, execute=True)

    assert presets_path.exists(), (
        "AC-2 verletzt: compare_presets.json darf nicht gelöscht werden, "
        "nur geleert"
    )
    presets = json.loads(presets_path.read_text(encoding="utf-8"))
    assert presets == [], (
        f"AC-2 verletzt: compare_presets.json sollte nach dem Lauf eine "
        f"leere Liste sein, ist aber: {presets}"
    )
    assert set(result.get("preset_ids_removed", [])) == set(_TEST_PRESET_IDS), (
        f"AC-2 verletzt: erwartete Entfernung der vier Test-Preset-IDs, "
        f"Rückgabe: {result}"
    )


# ===========================================================================
# AC-4: pytest-Wächter — Schreibversuch unter <repo>/data/users/ ohne Marker
# ===========================================================================


def test_ac4_kern_test_writing_into_repo_data_users_without_marker_is_blocked():
    """AC-4 (Wächter-Selbsttest): Ein Kern-Test ohne `real_data_root`/`live`-
    Marker, der versucht unter `<repo>/data/users/` zu schreiben, muss von
    der gehärteten `_isolate_data_root`-Fixture (tests/conftest.py, Teil C
    der Spec) mit FAIL + Klartext-Hinweis gestoppt werden.

    Heute (Wächter existiert noch nicht) läuft das Snippet grün durch (Exit
    0) -> dieser Test ist ROT (AssertionError statt der erwarteten
    fehlgeschlagenen Subprocess-Ausführung). Nach Teil C wird er grün.

    Testdaten-Hygiene: das Snippet wird bewusst *innerhalb* des Repos unter
    tests/tdd/ angelegt (nicht in tmp_path) — pytest lädt conftest.py nur
    für Testdateien, die im Verzeichnisbaum unterhalb des Repo-Roots liegen;
    eine Datei in tmp_path würde die zu prüfende Fixture gar nicht laden und
    den Wächter damit gar nicht testen. Snippet-Datei UND jede Leak-Datei
    unter data/users/ werden im finally-Block dieses Tests restlos entfernt
    — unabhängig vom Testausgang bleibt keine Spur im echten Baum zurück.
    """
    snippet_path = REPO_ROOT / "tests" / "tdd" / f"_guard_selftest_{uuid.uuid4().hex}.py"
    leak_dir = REPO_ROOT / "data" / "users" / "tdd-guard-selftest"

    snippet_path.write_text(
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def test_leak_into_repo_data_users():\n"
        "    target = Path('data') / 'users' / 'tdd-guard-selftest'\n"
        "    target.mkdir(parents=True, exist_ok=True)\n"
        "    (target / 'leak.txt').write_text('leak')\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", str(snippet_path), "-p", "no:cacheprovider", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode != 0, (
            "AC-4 verletzt: der gehärtete Wächter (Teil C) sollte dieses "
            "Kern-Test-Snippet ohne real_data_root/live-Marker fehlschlagen "
            "lassen, weil es unter <repo>/data/users/ schreibt. Heute "
            "(Wächter fehlt noch) läuft es grün durch (Exit "
            f"{result.returncode}).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    finally:
        snippet_path.unlink(missing_ok=True)
        if leak_dir.exists():
            shutil.rmtree(leak_dir, ignore_errors=True)


def test_ac4_guard_detects_in_place_content_mutation_of_existing_file():
    """F003 (Adversary Fix-Loop 1, HIGH): der Wächter-Snapshot muss auch
    reine Inhalts-Überschreibungen einer BEREITS BESTEHENDEN Datei
    erkennen, nicht nur neue/entfernte Top-Level-Einträge (Adversary-Repro:
    Verzeichnis-mtime ändert sich nicht bei ``write_text`` auf eine
    bestehende Datei). Nutzt eine echte, bereits vorhandene, git-ignorierte
    Datei unter ``data/users/default/`` (s. .gitignore) -- Original-Bytes
    UND -mtime werden im finally-Block exakt restauriert (inkl.
    ``os.utime``), es bleibt KEINE Spur im echten Baum zurück."""
    target = REPO_ROOT / "data" / "users" / "default" / "alert_daily_count.json"
    if not target.exists():
        pytest.skip(
            "Fixture-Datei data/users/default/alert_daily_count.json fehlt "
            "in dieser Umgebung"
        )

    original_bytes = target.read_bytes()
    original_stat = target.stat()

    snippet_path = REPO_ROOT / "tests" / "tdd" / f"_guard_selftest_mutate_{uuid.uuid4().hex}.py"
    snippet_path.write_text(
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def test_mutate_existing_file_in_place():\n"
        "    target = Path('data') / 'users' / 'default' / 'alert_daily_count.json'\n"
        "    target.write_text('{\"date\": \"1265-leak\", \"count\": 999}')\n",
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", str(snippet_path), "-p", "no:cacheprovider", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode != 0, (
            "F003 verletzt: der gehärtete Wächter sollte In-Place-Content-"
            "Mutation einer bestehenden Datei erkennen und den Test FAILEN "
            f"lassen. Exit-Code war {result.returncode}.\nstdout:\n"
            f"{result.stdout}\nstderr:\n{result.stderr}"
        )
    finally:
        snippet_path.unlink(missing_ok=True)
        target.write_bytes(original_bytes)
        os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
