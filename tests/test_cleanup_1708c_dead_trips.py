"""TDD RED — Issue #1708 Scheibe C: tote trips-Ablage archivieren + löschen.

Spec: docs/specs/modules/fix_1708_c_tote_ablage_loeschen.md
Context: docs/context/fix-1708-c-tote-ablage-loeschen.md

Abgedeckte ACs (RED-Phase):
    AC-1: beide Namensmuster (`trips`, `trips.TOT-legacy-1250-nicht-lesen`)
          werden gleichwertig erkannt -- `scripts/cleanup_1708c_dead_trips.py`
          existiert noch nicht -> ImportError.
    AC-2: nur der Trips-Unterordner wird entfernt, `users/<id>/` und
          Geschwister-Unterordner bleiben unangetastet.
    AC-3: Dry-Run schreibt nichts; --execute sichert per tar.gz VOR der
          Löschung.
    AC-4: Sanity-Abbruch (Konten-Check) -- fehlt das erwartete Konto
          `default`, bricht der Lauf ohne Backup/Löschung ab.
    AC-5: Zeit-Warnung ist informativ, blockiert NICHT (siehe Spec-Abschnitt
          "Sanity-Check ... und Zeit-Warnung" -- bewusst kein Abbruch, weil
          die reale Prod-Datei henning/.../5f534011.json eine mtime nach dem
          Referenzdatum trägt und trotzdem gelöscht werden muss).
    AC-6: zweiter --execute-Lauf ist idempotent (0 Aktionen, kein Backup).
    AC-7: Script ist stdlib-only (kein Drittanbieter-/Projekt-Import).

Alle Fixtures liegen ausschließlich in tmp_path. KEINE Berührung von
/home/hem/gregor_zwanzig/data oder produktiven Datenwurzeln.
"""
from __future__ import annotations

import ast
import os
import tarfile
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "cleanup_1708c_dead_trips.py"

CUTOVER = datetime(2026, 7, 15)


def _build_root(tmp_path: Path, *, second_pattern: bool = True) -> Path:
    """Baut einen Fixture-Baum mit beiden Namensmustern, einem echten Konto
    (`default`) und einem Geschwister-Unterordner (`briefings`), der stehen
    bleiben muss."""
    users_root = tmp_path / "users"

    default_dir = users_root / "default"
    (default_dir / "trips").mkdir(parents=True)
    (default_dir / "trips" / "gr221-mallorca.json").write_text("{}")
    (default_dir / "briefings").mkdir(parents=True)
    (default_dir / "briefings" / "5f534011.json").write_text("{}")

    if second_pattern:
        henning_dir = users_root / "henning"
        (henning_dir / "trips.TOT-legacy-1250-nicht-lesen").mkdir(parents=True)
        (henning_dir / "trips.TOT-legacy-1250-nicht-lesen" / "gr221-mallorca.json").write_text("{}")

    return users_root


# ===========================================================================
# AC-1: beide Namensmuster
# ===========================================================================


def test_ac1_dry_run_detects_both_name_patterns(tmp_path):
    """Given ein users_root mit `trips` bei einem User und
    `trips.TOT-legacy-1250-nicht-lesen` bei einem anderen / When das Script
    im Dry-Run läuft / Then werden beide als Löschkandidaten gemeldet, ohne
    eine Einzel-User-Positivliste.

    Heute ROT: `scripts/cleanup_1708c_dead_trips.py` existiert nicht ->
    ImportError.
    """
    from scripts.cleanup_1708c_dead_trips import run_cleanup  # noqa: PLC0415

    users_root = _build_root(tmp_path)
    result = run_cleanup(users_root, tmp_path / "backups", execute=False)

    candidates = result.get("would_remove", [])
    assert any("default" in str(c) and "trips" in str(c) for c in candidates), (
        f"AC-1 verletzt: `trips` bei default nicht als Kandidat erkannt: {result}"
    )
    assert any("henning" in str(c) and "TOT-legacy" in str(c) for c in candidates), (
        f"AC-1 verletzt: `trips.TOT-legacy-...` bei henning nicht erkannt: {result}"
    )
    assert not (tmp_path / "backups").exists(), "Dry-Run darf kein Backup schreiben"


# ===========================================================================
# AC-2: nur der Unterordner, nie users/<id>/ selbst
# ===========================================================================


def test_ac2_execute_removes_only_trips_subdir_leaves_siblings_and_user_dir(tmp_path):
    """Given `default/` enthält `trips/` UND `briefings/` / When --execute
    läuft / Then existiert `default/` danach weiterhin, `briefings/` ist
    unverändert, nur `trips/` ist verschwunden."""
    from scripts.cleanup_1708c_dead_trips import run_cleanup  # noqa: PLC0415

    users_root = _build_root(tmp_path, second_pattern=False)
    run_cleanup(users_root, tmp_path / "backups", execute=True)

    assert (users_root / "default").is_dir(), (
        "AC-2 verletzt: users/default/ selbst wurde entfernt"
    )
    assert not (users_root / "default" / "trips").exists(), (
        "AC-2 verletzt: trips/ wurde nicht entfernt"
    )
    assert (users_root / "default" / "briefings" / "5f534011.json").exists(), (
        "AC-2 verletzt: Geschwister-Unterordner briefings/ wurde angetastet"
    )


# ===========================================================================
# AC-3: Dry-Run schreibt nichts, Execute sichert VOR dem Löschen
# ===========================================================================


def test_ac3_dry_run_writes_nothing_execute_backs_up_before_delete(tmp_path):
    """Given ein Root mit einem Löschkandidaten / When Dry-Run läuft / Then
    bleibt alles unverändert. When danach --execute läuft / Then existiert
    ein lesbares tar.gz-Backup, das den Zielordner enthält, bevor er entfernt
    wurde."""
    from scripts.cleanup_1708c_dead_trips import run_cleanup  # noqa: PLC0415

    users_root = _build_root(tmp_path, second_pattern=False)
    backup_dir = tmp_path / "backups"

    run_cleanup(users_root, backup_dir, execute=False)
    assert (users_root / "default" / "trips").exists(), "Dry-Run darf nicht löschen"
    assert not backup_dir.exists() or not any(backup_dir.iterdir()), (
        "Dry-Run darf kein Backup schreiben"
    )

    result = run_cleanup(users_root, backup_dir, execute=True)
    backups = list(backup_dir.glob("*.tar.gz"))
    assert backups, f"AC-3 verletzt: kein tar.gz-Backup geschrieben: {result}"
    with tarfile.open(backups[0]) as tar:
        names = tar.getnames()
    assert any("gr221-mallorca.json" in n for n in names), (
        f"AC-3 verletzt: Backup enthält nicht die Trip-Datei: {names}"
    )
    assert not (users_root / "default" / "trips").exists(), (
        "AC-3 verletzt: nach --execute muss der Zielordner entfernt sein"
    )


# ===========================================================================
# AC-4: Sanity-Abbruch (Konten-Check)
# ===========================================================================


def test_ac4_missing_required_account_aborts_without_backup_or_delete(tmp_path):
    """Given unter --root fehlt das erwartete Konto `default` / When
    --execute läuft / Then bricht der Lauf ohne Backup und ohne Löschung ab,
    Exit-relevanter Fehler wird im Ergebnis gemeldet."""
    from scripts.cleanup_1708c_dead_trips import run_cleanup  # noqa: PLC0415

    users_root = tmp_path / "users"
    (users_root / "irgendwer" / "trips").mkdir(parents=True)  # kein "default"
    backup_dir = tmp_path / "backups"

    result = run_cleanup(users_root, backup_dir, execute=True)

    assert result.get("error"), f"AC-4 verletzt: kein Fehler gemeldet: {result}"
    assert (users_root / "irgendwer" / "trips").exists(), (
        "AC-4 verletzt: trotz fehlendem Konto wurde gelöscht"
    )
    assert not backup_dir.exists() or not any(backup_dir.iterdir()), (
        "AC-4 verletzt: trotz fehlendem Konto wurde ein Backup geschrieben"
    )


# ===========================================================================
# AC-5: Zeit-Warnung ist informativ, blockiert NICHT
# ===========================================================================


def test_ac5_newer_mtime_logs_warning_but_does_not_block_execute(tmp_path):
    """Given eine Datei im Zielordner trägt eine mtime NACH dem
    Referenzdatum 2026-07-15 (wie real `henning/.../5f534011.json`,
    mtime 2026-08-10 -- zweimal fehlgeleitet beschrieben, siehe Spec) / When
    --execute läuft / Then wird eine Warnung gemeldet, aber Backup UND
    Löschung laufen trotzdem regulär durch (kein Abbruch)."""
    from scripts.cleanup_1708c_dead_trips import run_cleanup  # noqa: PLC0415

    users_root = _build_root(tmp_path, second_pattern=False)
    newer_file = users_root / "default" / "trips" / "gr221-mallorca.json"
    newer_ts = (CUTOVER + timedelta(days=26)).timestamp()  # 2026-08-10
    os.utime(newer_file, (newer_ts, newer_ts))

    result = run_cleanup(users_root, tmp_path / "backups", execute=True)

    assert result.get("time_warnings"), (
        f"AC-5 verletzt: keine Zeit-Warnung trotz neuerer mtime gemeldet: {result}"
    )
    assert not (users_root / "default" / "trips").exists(), (
        "AC-5 verletzt: Zeit-Warnung hat die Löschung blockiert -- das ist "
        "explizit NICHT gewollt (Spec-Begründung: reale Prod-Datei würde "
        "sonst nie gelöscht)"
    )
    assert not result.get("error"), (
        f"AC-5 verletzt: Zeit-Warnung darf keinen Abbruch-Fehler erzeugen: {result}"
    )


# ===========================================================================
# AC-6: Idempotenz
# ===========================================================================


def test_ac6_second_run_is_idempotent_zero_actions(tmp_path):
    """Given ein erster --execute-Lauf hat den Zielordner entfernt / When das
    Script ein zweites Mal mit denselben Argumenten läuft / Then werden 0
    Aktionen gemeldet, kein neues Backup, kein Fehler."""
    from scripts.cleanup_1708c_dead_trips import run_cleanup  # noqa: PLC0415

    users_root = _build_root(tmp_path, second_pattern=False)
    backup_dir = tmp_path / "backups"

    run_cleanup(users_root, backup_dir, execute=True)
    backups_after_first = set(backup_dir.glob("*.tar.gz"))

    second = run_cleanup(users_root, backup_dir, execute=True)

    assert second.get("actions", -1) == 0, (
        f"AC-6 verletzt: zweiter Lauf ist nicht idempotent: {second}"
    )
    assert set(backup_dir.glob("*.tar.gz")) == backups_after_first, (
        "AC-6 verletzt: zweiter Lauf hat ein neues Backup geschrieben"
    )
    assert not second.get("error"), f"AC-6 verletzt: zweiter Lauf meldet Fehler: {second}"


# ===========================================================================
# AC-7: stdlib-only
# ===========================================================================


_ALLOWED_STDLIB = {
    "__future__", "argparse", "ast", "dataclasses", "datetime", "json",
    "os", "pathlib", "shutil", "sys", "tarfile", "typing",
}


def test_ac7_script_imports_only_stdlib():
    """Given das Cleanup-Script muss ohne `uv run`/venv per
    `sudo -n python3 ...` lauffähig sein / When seine Top-Level-Imports
    statisch geprüft werden / Then referenziert keiner ein
    Drittanbieter- oder Projekt-internes Paket.

    Heute ROT: SCRIPT_PATH existiert nicht -> FileNotFoundError.
    """
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SCRIPT_PATH))

    top_level_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_modules.add(node.module.split(".")[0])

    disallowed = top_level_modules - _ALLOWED_STDLIB
    assert not disallowed, (
        f"AC-7 verletzt: Nicht-stdlib-Imports gefunden: {disallowed}"
    )
