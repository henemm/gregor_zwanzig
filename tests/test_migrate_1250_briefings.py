"""TDD RED — Issue #1250 Scheibe 5 (AC-16 bis AC-19): Datei-Migration
Trip + ComparePreset -> BriefingSubscription (`briefings/<id>.json`).

Spec: docs/specs/modules/issue_1250_briefing_subscription.md, Sektion
"Scheibe 5 — kind + gemeinsames Modell/Store + Datei-Migration"
(AC-16..AC-19). Kontext: docs/context/feat-1250-s5-kind-migration.md.

Hintergrund: `scripts/migrate_1250_briefings.py` liest pro User
`<root>/*/trips/*.json` (je 1 Trip) und `<root>/*/compare_presets.json`
(Array) als rohe Dicts, setzt additiv `kind` (Trip -> "route", Preset ->
"vergleich") und schreibt verlustfrei nach
`<root>/<uid>/briefings/<id>.json` (id = Trip-Dateiname bzw. `preset["id"]`).
Dry-Run-Default (C4), tar.gz-Backup vor `--execute`, Idempotenz über
Ziel-Existenz + gesetztes `kind` (AC-18), strikte Pro-User-Isolation (AC-19).

RED heute: `scripts/migrate_1250_briefings.py` existiert NOCH NICHT ->
`subprocess`-Aufruf endet mit returncode != 0 -> alle Tests schlagen fehl.
Nach der Implementierung (GREEN) laufen sie grün.

Struktureller Vorbild: tests/tdd/test_corridor_migration.py (subprocess-
Aufruf des echten Skripts gegen einen tmp_path-Fixture-Baum, --root/
--execute, Idempotenz, Dry-Run-Default). NO MOCKS, echte Dateien, echte
Prozesse.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _migrate_script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_1250_briefings.py"


def _trip(trip_id: str, **extra) -> dict:
    base = {
        "id": trip_id,
        "name": trip_id,
        "stages": [],
        "activity": "hiking",
        "some_unknown_field": "keep-me",
    }
    base.update(extra)
    return base


def _preset(preset_id: str, **extra) -> dict:
    base = {
        "id": preset_id,
        "name": preset_id,
        "user_id": "default",
        "location_ids": ["loc-a"],
        "schedule": "manual",
        "empfaenger": ["gregor-test@henemm.com"],
        "some_unknown_field": "keep-me",
    }
    base.update(extra)
    return base


def _write_trip(root: Path, user_id: str, trip: dict) -> Path:
    trips_dir = root / user_id / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)
    path = trips_dir / f"{trip['id']}.json"
    path.write_text(json.dumps(trip, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_presets(root: Path, user_id: str, presets: list[dict]) -> Path:
    user_dir = root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / "compare_presets.json"
    path.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_migrate_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=90, cwd=REPO_ROOT)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _snapshot(root: Path) -> dict[str, str]:
    """Relativer Pfad -> Inhalt für JEDE Datei unter root (Existenz UND
    Byte-Inhalt in einer Prüfung)."""
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _build_two_user_fixture(root: Path) -> dict[str, tuple[Path, dict]]:
    """2 User (user-a/user-b), je 1 Trip (trips/<id>.json) + 1 Compare-Preset
    (compare_presets.json[0]), je mit einem unmodellierten Zusatzfeld
    (`some_unknown_field`) zur Verlustfreiheits-Prüfung."""
    trip_a = _trip("trip-a")
    trip_b = _trip("trip-b")
    preset_a = _preset("cp-a")
    preset_b = _preset("cp-b")
    return {
        "trip_a": (_write_trip(root, "user-a", trip_a), trip_a),
        "trip_b": (_write_trip(root, "user-b", trip_b), trip_b),
        "preset_a": (_write_presets(root, "user-a", [preset_a]), preset_a),
        "preset_b": (_write_presets(root, "user-b", [preset_b]), preset_b),
    }


# ═══════════════════════════════ AC-16 ═══════════════════════════════════════

def test_ac16_execute_migrates_lossless_with_kind(tmp_path):
    """AC-16 GIVEN einen Trip und ein ComparePreset je User (2 User) ohne
    `kind`-Feld, je mit einem unmodellierten Zusatzfeld / WHEN
    `migrate_1250_briefings.py --execute` läuft / THEN existiert für jeden
    Trip UND jedes Preset eine `data/users/<uid>/briefings/<id>.json`, die
    ALLE Quellfelder (inkl. `some_unknown_field`) enthält UND `kind` ==
    "route" (Trip) bzw. "vergleich" (Preset) trägt; der Report nennt jede
    migrierte Entität.

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    fixture = _build_two_user_fixture(root)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    checks = [
        (root / "user-a" / "briefings" / "trip-a.json", fixture["trip_a"][1], "route"),
        (root / "user-b" / "briefings" / "trip-b.json", fixture["trip_b"][1], "route"),
        (root / "user-a" / "briefings" / "cp-a.json", fixture["preset_a"][1], "vergleich"),
        (root / "user-b" / "briefings" / "cp-b.json", fixture["preset_b"][1], "vergleich"),
    ]
    for path, source, expected_kind in checks:
        assert path.exists(), f"Ziel-Datei fehlt: {path}"
        data = _load(path)
        for key, value in source.items():
            assert data.get(key) == value, (
                f"{path}: Quellfeld '{key}' verloren oder verändert -- "
                f"erwartet {value!r}, erhalten {data.get(key)!r}"
            )
        assert data.get("some_unknown_field") == "keep-me", (
            f"{path}: unmodelliertes Zusatzfeld nicht verlustfrei migriert (RMW-Verstoß)"
        )
        assert data.get("kind") == expected_kind, (
            f"{path}: erwartet kind={expected_kind!r}, erhalten {data.get('kind')!r}"
        )

    for entity_id in ("trip-a", "trip-b", "cp-a", "cp-b"):
        assert entity_id in result.stdout, (
            f"Report muss migrierte Entität '{entity_id}' nennen:\n{result.stdout}"
        )


# ═══════════════════════════════ AC-17 ═══════════════════════════════════════

def test_ac17_dry_run_writes_nothing_but_reports(tmp_path):
    """AC-17 GIVEN Trip + Preset je User ohne `kind` / WHEN das Skript OHNE
    `--execute` läuft / THEN wird KEIN `briefings/`-Verzeichnis/keine Datei
    angelegt (Dateisystem-Zustand vor/nach identisch, Existenz UND Inhalt),
    aber der Report ist NICHT leer (Feld-Diff/Plan) — Dry-Run-Default (C4).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    _build_two_user_fixture(root)
    before = _snapshot(root)

    result = _run_migrate(root)  # kein --execute -> Dry-Run-Default

    assert result.returncode == 0, (
        f"Dry-Run darf nicht fehlschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    after = _snapshot(root)
    assert after == before, (
        "Dry-Run darf das Dateisystem NICHT verändern (Existenz+Inhalt identisch)"
    )
    assert not (root / "user-a" / "briefings").exists(), (
        "Dry-Run darf kein briefings/-Verzeichnis für User A anlegen"
    )
    assert not (root / "user-b" / "briefings").exists(), (
        "Dry-Run darf kein briefings/-Verzeichnis für User B anlegen"
    )
    assert result.stdout.strip() != "", "Dry-Run muss einen nicht-leeren Report ausgeben"


# ═══════════════════════════════ AC-18 ═══════════════════════════════════════

def test_ac18_second_execute_is_idempotent_no_rewrite(tmp_path):
    """AC-18 GIVEN ein bereits migrierter Bestand (erster `--execute`-Lauf
    ist gelaufen, Ziel existiert + `kind` gesetzt) / WHEN ein zweiter
    `--execute`-Lauf folgt / THEN bleibt die mtime der Zieldateien
    UNVERÄNDERT (keine erneute Schreiboperation) und der Report enthält
    eine SKIP-Zeile.

    RED heute: Skript existiert nicht -> bereits der erste Lauf
    returncode != 0.
    """
    root = tmp_path / "users"
    _build_two_user_fixture(root)

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, (
        f"1. Lauf fehlgeschlagen:\nstdout:\n{first.stdout}\nstderr:\n{first.stderr}"
    )

    briefing_paths = [
        root / "user-a" / "briefings" / "trip-a.json",
        root / "user-b" / "briefings" / "trip-b.json",
        root / "user-a" / "briefings" / "cp-a.json",
        root / "user-b" / "briefings" / "cp-b.json",
    ]
    for path in briefing_paths:
        assert path.exists(), f"Nach 1. Lauf fehlt Zieldatei: {path}"
    mtimes_before = {path: path.stat().st_mtime_ns for path in briefing_paths}

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode == 0, (
        f"2. Lauf fehlgeschlagen:\nstdout:\n{second.stdout}\nstderr:\n{second.stderr}"
    )

    for path in briefing_paths:
        assert path.stat().st_mtime_ns == mtimes_before[path], (
            f"Zweiter --execute-Lauf hat Zieldatei erneut geschrieben "
            f"(kein Idempotenz-Skip): {path}"
        )
    assert "SKIP" in second.stdout, (
        f"Report des zweiten Laufs muss eine SKIP-Zeile enthalten:\n{second.stdout}"
    )


# ═══════════════════════════════ AC-19 ═══════════════════════════════════════

def test_ac19_user_isolation_no_cross_user_paths(tmp_path):
    """AC-19 GIVEN zwei User (user-a/user-b) mit je eigenem Trip + Preset /
    WHEN `--execute` läuft / THEN liegen die migrierten Dateien STRIKT
    unter dem jeweils eigenen `data/users/<uid>/briefings/`; User-A-`id`
    taucht NICHT unter User-B-Pfad auf und umgekehrt (kein Cross-User-
    Datenzugriff).

    RED heute: Skript existiert nicht -> returncode != 0.
    """
    root = tmp_path / "users"
    _build_two_user_fixture(root)

    result = _run_migrate(root, extra_args=["--execute"])
    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    user_a_dir = root / "user-a" / "briefings"
    user_b_dir = root / "user-b" / "briefings"
    assert user_a_dir.exists(), f"User-A-briefings/ fehlt: {user_a_dir}"
    assert user_b_dir.exists(), f"User-B-briefings/ fehlt: {user_b_dir}"

    user_a_ids = {p.stem for p in user_a_dir.glob("*.json")}
    user_b_ids = {p.stem for p in user_b_dir.glob("*.json")}

    assert user_a_ids == {"trip-a", "cp-a"}, f"User A briefings unerwartet: {user_a_ids}"
    assert user_b_ids == {"trip-b", "cp-b"}, f"User B briefings unerwartet: {user_b_ids}"
    assert user_a_ids.isdisjoint(user_b_ids), "Cross-User-ID-Kollision zwischen A und B"

    for foreign_id in user_b_ids:
        assert not (user_a_dir / f"{foreign_id}.json").exists(), (
            f"User-B-Entität '{foreign_id}' unter User-A-Pfad gefunden -- Cross-User-Leck"
        )
    for foreign_id in user_a_ids:
        assert not (user_b_dir / f"{foreign_id}.json").exists(), (
            f"User-A-Entität '{foreign_id}' unter User-B-Pfad gefunden -- Cross-User-Leck"
        )


# ═════════════════════ Adversary Fix-Loop (F001/F002/F003) ═══════════════════

def test_f001_id_collision_trip_and_preset_same_id_aborts_and_writes_nothing(tmp_path):
    """F001 (CRITICAL) GIVEN einen Trip UND ein ComparePreset mit derselben
    `id` beim selben User (beide zielen auf `briefings/x.json`) / WHEN
    `--execute` läuft / THEN bricht der Lauf mit Exit != 0 ab, die
    Fehlermeldung nennt BEIDE kollidierenden Entitäten (uid + beide
    kind-Werte), UND es wird NICHTS geschrieben (kein `briefings/`-
    Verzeichnis) -- kein stiller Datenverlust durch Überschreiben oder
    stillen Idempotenz-Skip.
    """
    root = tmp_path / "users"
    trip_x = _trip("x")
    preset_x = _preset("x")
    _write_trip(root, "user-a", trip_x)
    _write_presets(root, "user-a", [preset_x])

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode != 0, (
        f"ID-Kollision (Trip x + Preset x, gleicher User) muss den Lauf "
        f"abbrechen:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "user-a" in result.stderr and "x" in result.stderr, (
        f"Fehlermeldung muss User + kollidierende ID nennen:\n{result.stderr}"
    )
    assert "route" in result.stderr and "vergleich" in result.stderr, (
        f"Fehlermeldung muss BEIDE kind-Werte der kollidierenden Entitäten nennen:\n{result.stderr}"
    )
    assert not (root / "user-a" / "briefings").exists(), (
        "Bei ID-Kollision darf NICHTS geschrieben werden (kein briefings/-Verzeichnis)"
    )


def test_f001_cross_run_collision_second_kind_aborts_without_overwrite(tmp_path):
    """F001 (CRITICAL) GIVEN einen bereits migrierten Trip `x`
    (`briefings/x.json`, kind="route") / WHEN nachträglich ein
    ComparePreset mit derselben `id` "x" hinzukommt und ein zweiter
    `--execute`-Lauf folgt / THEN erkennt der Lauf die Cross-Run-Kollision
    (Ziel trägt bereits ein ANDERES kind als die aktuell zu migrierende
    Entität), bricht ab (Exit != 0), UND die bereits migrierte Datei bleibt
    UNVERÄNDERT (kein stiller Skip, kein Überschreiben).
    """
    root = tmp_path / "users"
    trip_x = _trip("x")
    _write_trip(root, "user-a", trip_x)

    first = _run_migrate(root, extra_args=["--execute"])
    assert first.returncode == 0, (
        f"1. Lauf (nur Trip x) muss grün sein:\nstdout:\n{first.stdout}\nstderr:\n{first.stderr}"
    )

    briefing_path = root / "user-a" / "briefings" / "x.json"
    assert briefing_path.exists()
    before = briefing_path.read_text(encoding="utf-8")
    mtime_before = briefing_path.stat().st_mtime_ns

    # Preset mit derselben id "x" kommt nachträglich hinzu.
    preset_x = _preset("x")
    _write_presets(root, "user-a", [preset_x])

    second = _run_migrate(root, extra_args=["--execute"])
    assert second.returncode != 0, (
        f"Cross-Run-Kollision (Preset x nach bereits migriertem Trip x) muss "
        f"abbrechen:\nstdout:\n{second.stdout}\nstderr:\n{second.stderr}"
    )
    assert "route" in second.stderr and "vergleich" in second.stderr, (
        f"Fehlermeldung muss beide kind-Werte nennen:\n{second.stderr}"
    )
    assert briefing_path.read_text(encoding="utf-8") == before, (
        "Bereits migrierte Datei darf bei Cross-Run-Kollision NICHT verändert werden"
    )
    assert briefing_path.stat().st_mtime_ns == mtime_before, (
        "Bereits migrierte Datei darf bei Cross-Run-Kollision NICHT erneut geschrieben werden"
    )


def test_f002_corrupt_trip_source_skipped_with_report_others_still_migrate(tmp_path):
    """F002 (MEDIUM) GIVEN ein kaputtes `trips/y.json` (kein valides JSON)
    NEBEN einem validen `trips/z.json` / WHEN `--execute` läuft / THEN
    migriert z erfolgreich, der Report nennt y als übersprungen (korrupte
    JSON), UND das Skript crasht nicht (Exit 0) -- die korrupte Quelle
    bleibt unangetastet liegen, kein Datenverlust.
    """
    root = tmp_path / "users"
    trip_z = _trip("z")
    _write_trip(root, "user-a", trip_z)

    corrupt_path = root / "user-a" / "trips" / "y.json"
    corrupt_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_path.write_text("{not valid json", encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Korrupte Nachbardatei darf den Lauf nicht crashen:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert (root / "user-a" / "briefings" / "z.json").exists(), (
        "Valider Trip 'z' muss trotz kaputter Nachbardatei migriert werden"
    )
    assert not (root / "user-a" / "briefings" / "y.json").exists(), (
        "Korrupter Trip 'y' darf NICHT als Zieldatei auftauchen"
    )
    assert "y" in result.stdout and "SKIP" in result.stdout, (
        f"Report muss die korrupte Quelle 'y' als übersprungen nennen:\n{result.stdout}"
    )
    assert corrupt_path.read_text(encoding="utf-8") == "{not valid json", (
        "Korrupte Quelldatei darf durch die Migration nicht verändert werden"
    )


def test_f003_null_kind_target_is_remigrated(tmp_path):
    """F003 (LOW) GIVEN eine bereits existierende `briefings/x.json` mit
    `kind: null` (z.B. unfertiger/handgeschriebener Bestand) / WHEN
    `--execute` für den zugehörigen Trip `x` läuft / THEN wird die Datei
    NICHT als bereits migriert übersprungen, sondern mit den aktuellen
    Quellfeldern neu geschrieben (kind:null/"" gilt nicht als truthy, s.
    kind-genaue Idempotenz).
    """
    root = tmp_path / "users"
    trip_x = _trip("x", name="Neuer Name")
    _write_trip(root, "user-a", trip_x)

    briefings_dir = root / "user-a" / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    stale_path = briefings_dir / "x.json"
    stale_path.write_text(
        json.dumps({"id": "x", "kind": None, "name": "Alter Name"}, indent=2),
        encoding="utf-8",
    )

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"kind:null-Ziel darf den Lauf nicht abbrechen:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    data = _load(stale_path)
    assert data.get("kind") == "route", (
        f"kind:null-Ziel muss re-migriert werden (kind muss gesetzt sein): {data}"
    )
    assert data.get("name") == "Neuer Name", (
        f"kind:null-Ziel muss mit den AKTUELLEN Quellfeldern überschrieben werden: {data}"
    )
