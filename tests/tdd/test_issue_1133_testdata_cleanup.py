"""
TDD RED Tests for Issue #1133 — Testdaten-Cleanup + isolierter Test-Daten-Root.

Each test maps to one AC from
docs/specs/modules/issue_1133_testdata_cleanup.md.

These tests MUST fail in RED phase:
- `get_data_dir()` (src/app/loader.py) does not yet honor `_DATA_ROOT` or
  `GZ_DATA_DIR` — it always returns the hardcoded relative `Path("data/users")`.
- `tests/conftest.py::_isolate_data_root` (the new autouse fixture) does not
  exist yet.
- `scripts/cleanup_1133_testdata.py` does not exist yet.

NO MOCKS — real filesystem operations under `tmp_path`, real subprocess calls,
real fixture-generator execution (via `.__wrapped__`, not `Mock()`/`patch()`).

CRITICAL: none of these tests may write into the real `data/users/` tree.
Every test that calls `save_trip()` protects itself via
`monkeypatch.chdir(tmp_path)` and/or an explicit `data_dir=`/`_DATA_ROOT`
override before touching the filesystem.
"""
from __future__ import annotations

import inspect
import importlib.util
import subprocess
from pathlib import Path



REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# AC-1 + AC-3 + AC-4: get_data_dir() path-resolution + real save_trip roundtrip
# ---------------------------------------------------------------------------


def test_ac1_fixture_isolation_path_resolution_and_roundtrip(tmp_path, monkeypatch):
    """AC-1: Given die neue autouse-Fixture ist aktiv (kein real_data_root-
    Marker) / When ein Test get_trips_dir()/save_trip() ohne data_dir=
    aufruft / Then landet die Datei ausschliesslich im temporaeren
    Fixture-Root, und der echte data/users/-Baum bleibt unveraendert.

    Teil A prueft reine Pfad-Auflösung (kein Schreiben): get_trips_dir()
    muss auf einen absoluten Pfad AUSSERHALB des Repos zeigen — das
    Erkennungsmerkmal fuer eine aktive Fixture-Isolation. Schlaegt fehl,
    weil get_data_dir() aktuell immer den relativen "data/users"-Pfad
    zurueckgibt, unabhaengig von jeder Fixture.

    Teil B ist der Verhaltens-Beweis mit echtem save_trip()-Roundtrip,
    abgesichert durch monkeypatch.chdir(tmp_path) (der RED-Test selbst darf
    den echten Baum niemals verschmutzen). Vor dem Fix haengt der
    geschriebene Pfad vom (versehentlich sicheren) chdir-Ziel ab; nach dem
    Fix haengt er ausschliesslich vom (unabhaengigen) Fixture-Root ab.
    """
    from app.loader import get_trips_dir, save_trip
    from app.trip import Trip

    # --- Teil A: Pfad-Auflösung, kein Schreiben ---------------------------
    trips_dir = get_trips_dir("tdd-1133-proof")
    assert trips_dir.is_absolute(), (
        f"AC-1 verletzt: get_trips_dir() liefert relativen Pfad {trips_dir!r} "
        "— autouse-Fixture existiert noch nicht"
    )
    assert not str(trips_dir.resolve()).startswith(str(REPO_ROOT)), (
        f"AC-1 verletzt: get_trips_dir() zeigt weiterhin auf den echten "
        f"Repo-Baum: {trips_dir}"
    )

    # --- Teil B: echter Roundtrip, sicher via chdir -------------------------
    real_trip_path = (
        REPO_ROOT / "data" / "users" / "tdd-1133-proof" / "trips"
        / "tdd-1133-proof.json"
    )
    assert not real_trip_path.exists(), (
        "Präbedingung verletzt: Testartefakt existiert bereits im echten Baum"
    )

    monkeypatch.chdir(tmp_path)
    cwd_relative_path = (
        tmp_path / "data" / "users" / "tdd-1133-proof" / "trips"
        / "tdd-1133-proof.json"
    )
    trip = Trip(id="tdd-1133-proof", name="RED-Proof", stages=[])
    saved_path = save_trip(trip, user_id="tdd-1133-proof")

    assert saved_path.resolve() != cwd_relative_path.resolve(), (
        f"AC-1 verletzt: save_trip() schreibt weiterhin relativ zum "
        f"(zufaellig sicheren) cwd ({saved_path}) statt in einen vom "
        "Fixture-Root unabhaengigen, dedizierten Pfad"
    )
    assert not real_trip_path.exists(), (
        "Der echte data/users/-Baum wurde trotz chdir verschmutzt"
    )


def test_ac3_gz_data_dir_env_override(tmp_path, monkeypatch):
    """AC-3: Given GZ_DATA_DIR ist als Umgebungsvariable gesetzt (ohne
    aktiven _DATA_ROOT-Modul-Override) / When get_data_dir() aufgerufen
    wird / Then wird der Pfad relativ zum Wert von GZ_DATA_DIR aufgeloest,
    analog zum Go-seitigen DATA_DIR-Envconfig. Schlaegt aktuell fehl, weil
    get_data_dir() die Env-Var komplett ignoriert.
    """
    import app.loader as loader

    monkeypatch.setenv("GZ_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(loader, "_DATA_ROOT", None, raising=False)

    result = loader.get_data_dir("u")

    assert str(result).startswith(str(tmp_path)), (
        f"AC-3 verletzt: GZ_DATA_DIR wird von get_data_dir() nicht "
        f"respektiert, bekam {result} (erwartet unter {tmp_path})"
    )


def test_ac4_throttle_reset_would_follow_overridden_root(tmp_path, monkeypatch):
    """AC-4: Given tests/tdd/conftest.py's Throttle-Reset-Fixture fuer
    tdd-638-*-User wird (im Zuge dieses Fixes) von einer hartkodierten
    Path(__file__)-Konstruktion auf loader.get_data_dir(uid).parent
    umgestellt / When _DATA_ROOT auf ein Temp-Verzeichnis umgelenkt ist /
    Then loest get_data_dir(uid).parent unter diesem Temp-Root auf (Beweis,
    dass eine derart migrierte Throttle-Fixture dem umgelenkten Root
    folgen wuerde).

    Ueber denselben Pfad-Auflösungs-Mechanismus wie AC-1/AC-3 getestet
    (siehe Spec-Hinweis): ein eigenstaendiger Roundtrip-Test der
    Throttle-Datei selbst ist in RED-Phase nicht sinnvoll, bevor der
    Override-Mechanismus, von dem die migrierte Fixture abhaengen soll
    (get_data_dir() honoriert _DATA_ROOT), ueberhaupt existiert. Schlaegt
    aktuell fehl, weil get_data_dir() den Modul-Override komplett
    ignoriert.
    """
    import app.loader as loader

    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path), raising=False)

    uid = "tdd-638-ac1"
    result = loader.get_data_dir(uid).parent

    assert str(result.resolve()).startswith(str(tmp_path.resolve())), (
        f"AC-4 verletzt: get_data_dir({uid!r}).parent folgt nicht dem "
        f"_DATA_ROOT-Override — eine auf get_data_dir() migrierte "
        f"Throttle-Reset-Fixture wuerde weiterhin den echten Baum treffen: "
        f"{result}"
    )


# ---------------------------------------------------------------------------
# AC-2: @pytest.mark.real_data_root opt-out of the new autouse fixture
# ---------------------------------------------------------------------------


def _load_top_conftest():
    """Loads tests/conftest.py as an isolated module (not via pytest's own
    plugin manager) purely to inspect/execute its `_isolate_data_root`
    fixture directly. Harmless re-execution of module-level sys.path setup.
    """
    path = REPO_ROOT / "tests" / "conftest.py"
    spec = importlib.util.spec_from_file_location(
        "gz_top_conftest_1133_probe", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class _FakeMarker:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeNode:
    """Minimal stand-in for pytest's request.node — plain attribute carrier,
    NOT a Mock()/MagicMock. Only implements the single method the fixture
    under test is expected to call (get_closest_marker)."""

    def __init__(self, marker_name: str | None) -> None:
        self._marker_name = marker_name

    def get_closest_marker(self, name: str):
        if name == self._marker_name:
            return _FakeMarker(name)
        return None


class _FakeRequest:
    def __init__(self, marker_name: str | None = None) -> None:
        self.node = _FakeNode(marker_name)


class _FakeTmpPathFactory:
    """Minimal stand-in for pytest's tmp_path_factory fixture — real
    filesystem operations under a real tmp_path, no mocking."""

    def __init__(self, base: Path) -> None:
        self._base = base
        self._n = 0

    def mktemp(self, basename: str) -> Path:
        self._n += 1
        p = self._base / f"{basename}{self._n}"
        p.mkdir(parents=True, exist_ok=True)
        return p


def _call_fixture_generator(fixture_fn, request, factory):
    """Unwraps a pytest-decorated fixture function (pytest forbids calling
    fixtures directly) and drives its raw generator with kwargs matched by
    parameter name, so the exact parameter order the implementer chooses
    does not matter as long as the names match the spec vocabulary."""
    raw = getattr(fixture_fn, "__wrapped__", fixture_fn)
    sig = inspect.signature(raw)
    kwargs = {}
    if "request" in sig.parameters:
        kwargs["request"] = request
    if "tmp_path_factory" in sig.parameters:
        kwargs["tmp_path_factory"] = factory
    return raw(**kwargs)


def test_ac2_marked_test_opts_out_of_data_root_override(tmp_path):
    """AC-2: Given ein Test ist mit @pytest.mark.real_data_root markiert /
    When er get_data_dir() (via die neue autouse-Fixture) aufruft / Then
    wird der echte data/users/-Pfad zurueckgegeben — kein Fixture-Override
    greift fuer diesen Test.

    Getestet durch direkte Ausfuehrung der (noch nicht existierenden)
    Fixture-Funktion tests/conftest.py::_isolate_data_root mit einem
    minimalen Fake-Request (marker_name="real_data_root") und einer echten
    Fake-TmpPathFactory (schreibt echte Verzeichnisse unter tmp_path,
    keine Mocks). Schlaegt aktuell mit AttributeError fehl, weil
    _isolate_data_root in tests/conftest.py noch nicht existiert.

    Angenommener Fixture-Vertrag (durch diesen RED-Test spezifiziert):
    Parameter heissen `request` und `tmp_path_factory`; die Fixture setzt
    `loader._DATA_ROOT` NICHT, wenn `request.node.get_closest_marker(
    "real_data_root")` einen Treffer liefert.
    """
    import app.loader as loader

    module = _load_top_conftest()
    fixture_fn = module._isolate_data_root  # AttributeError in RED

    before = getattr(loader, "_DATA_ROOT", None)
    request = _FakeRequest(marker_name="real_data_root")
    factory = _FakeTmpPathFactory(tmp_path)

    gen = _call_fixture_generator(fixture_fn, request, factory)
    next(gen)  # setup phase

    assert loader._DATA_ROOT == before, (
        "AC-2 verletzt: der Daten-Root-Override greift trotz "
        "@pytest.mark.real_data_root"
    )

    try:
        next(gen)  # teardown phase
    except StopIteration:
        pass


def test_ac1_unmarked_test_gets_override_via_real_fixture(tmp_path):
    """AC-1 (Fixture-Mechanik selbst, Ergaenzung zu oben): Given kein
    real_data_root-Marker ist gesetzt / When die (noch nicht existierende)
    Fixture tests/conftest.py::_isolate_data_root fuer einen normalen Test
    ausgefuehrt wird / Then setzt sie loader._DATA_ROOT auf ein frisches
    Temp-Verzeichnis (ueber tmp_path_factory.mktemp), NICHT auf None/den
    echten Baum. Schlaegt aktuell mit AttributeError fehl (Fixture fehlt).
    """
    import app.loader as loader

    module = _load_top_conftest()
    fixture_fn = module._isolate_data_root  # AttributeError in RED

    request = _FakeRequest(marker_name=None)
    factory = _FakeTmpPathFactory(tmp_path)

    gen = _call_fixture_generator(fixture_fn, request, factory)
    next(gen)  # setup phase

    assert loader._DATA_ROOT is not None, (
        "AC-1 verletzt: Fixture setzt loader._DATA_ROOT nicht fuer einen "
        "nicht markierten Test"
    )
    assert Path(loader._DATA_ROOT).resolve().is_relative_to(tmp_path.resolve()), (
        f"AC-1 verletzt: _DATA_ROOT ({loader._DATA_ROOT}) liegt nicht unter "
        f"dem erwarteten tmp_path_factory-Root ({tmp_path})"
    )

    try:
        next(gen)  # teardown phase
    except StopIteration:
        pass


# ---------------------------------------------------------------------------
# AC-5 – AC-8: scripts/cleanup_1133_testdata.py
# ---------------------------------------------------------------------------


def _cleanup_script_path() -> Path:
    return REPO_ROOT / "scripts" / "cleanup_1133_testdata.py"


def _build_test_tree(base: Path) -> None:
    """Baut eine Kopie-Baum-Fixture unter `base` (NICHT der echte Baum)."""
    (base / "admin" / "trips").mkdir(parents=True)
    (base / "admin" / "trips" / "gr221-mallorca.json").write_text(
        '{"id": "gr221-mallorca", "real": true}'
    )
    (base / "admin" / "trips" / "e2e-foo.json").write_text(
        '{"id": "e2e-foo", "residue": true}'
    )

    (base / "default").mkdir(parents=True)
    (base / "default" / "user.json").write_text('{"user_id": "default"}')

    (base / "henning" / "weather_snapshots").mkdir(parents=True)
    (base / "henning" / "weather_snapshots" / "real-snapshot.json").write_text(
        '{"real": true}'
    )
    (base / "henning" / "weather_snapshots" / "test-trip.json").write_text(
        '{"residue": true}'
    )

    (base / "validator-issue110" / "trips").mkdir(parents=True)
    (base / "validator-issue110" / "trips" / "x.json").write_text(
        '{"residue": true}'
    )

    (base / "tdd-999-x").mkdir(parents=True)
    (base / "tdd-999-x" / "user.json").write_text('{"residue": true}')


def _run_cleanup_script(root: Path, extra_args=None, backup_dir=None):
    """Angenommener CLI-Vertrag (durch diese RED-Tests spezifiziert):
    `scripts/cleanup_1133_testdata.py --root <pfad> --positivlist a,b,c
    [--backup-dir <pfad>] [--execute]` — ohne --execute ist Dry-Run der
    Default. `--positivlist` macht das Script host-unabhaengig testbar
    (echte Host-Positivlisten laut Spec sind fest verdrahtet, aber die
    Test-Baeume sind synthetisch und brauchen eine explizite Liste)."""
    script = _cleanup_script_path()
    args = [
        "uv", "run", "python3", str(script),
        "--root", str(root),
        "--positivlist", "admin,default,henning",
    ]
    if backup_dir is not None:
        args += ["--backup-dir", str(backup_dir)]
    if extra_args:
        args += extra_args
    return subprocess.run(
        args, capture_output=True, text=True, timeout=60, cwd=REPO_ROOT
    )


def test_ac5_dry_run_deletes_nothing_and_prints_plan(tmp_path):
    """AC-5: Given das Cleanup-Script laeuft im Dry-Run-Modus (Default,
    ohne --execute) gegen eine Kopie-Baum-Fixture / When es ausgefuehrt
    wird / Then wird keine einzige Datei/kein Verzeichnis geloescht, aber
    ein vollstaendiger Loeschplan mit allen betroffenen Pfaden wird
    ausgegeben. Schlaegt aktuell fehl (Exit != 0), weil
    scripts/cleanup_1133_testdata.py nicht existiert.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    _build_test_tree(tree)

    before = {p: p.stat().st_mtime for p in tree.rglob("*") if p.is_file()}

    result = _run_cleanup_script(tree)

    assert result.returncode == 0, (
        f"AC-5 verletzt: Cleanup-Script (Dry-Run) sollte Exit 0 liefern, "
        f"bekam {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    after = {p: p.stat().st_mtime for p in tree.rglob("*") if p.is_file()}
    assert before == after, "Dry-Run hat Dateien veraendert/geloescht — verboten"

    for expected_fragment in [
        "validator-issue110", "tdd-999-x", "e2e-foo.json", "test-trip.json",
    ]:
        assert expected_fragment in result.stdout, (
            f"AC-5 verletzt: Loeschplan sollte {expected_fragment!r} "
            f"auflisten, stdout:\n{result.stdout}"
        )


def test_ac6_execute_keeps_only_positivlist_and_writes_backup(tmp_path):
    """AC-6: Given das Cleanup-Script laeuft mit --execute gegen eine
    Prod-artige Positivliste (admin, default, henning) auf einer
    Kopie-Baum-Fixture, die zusaetzlich validator-issue110 und weitere
    Test-Residuen enthaelt / When der Lauf abgeschlossen ist / Then
    existieren ausschliesslich die Positivlisten-Verzeichnisse,
    validator-issue110 und alle anderen Residuen sind entfernt, und ein
    tar.gz-Backup des Vor-Zustands liegt unter --backup-dir. Schlaegt
    aktuell fehl (Exit != 0), weil das Script nicht existiert.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    _build_test_tree(tree)
    backup_dir = tmp_path / "backups"

    result = _run_cleanup_script(
        tree, extra_args=["--execute"], backup_dir=backup_dir
    )

    assert result.returncode == 0, (
        f"AC-6 verletzt: --execute-Lauf sollte Exit 0 liefern, bekam "
        f"{result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    remaining = sorted(p.name for p in tree.iterdir())
    assert remaining == ["admin", "default", "henning"], (
        f"AC-6 verletzt: nach --execute duerfen nur Positivlisten-User "
        f"uebrig sein, gefunden: {remaining}"
    )
    assert not (tree / "validator-issue110").exists(), (
        "AC-6 verletzt: validator-issue110 wurde nicht entfernt"
    )
    assert not (tree / "tdd-999-x").exists(), (
        "AC-6 verletzt: tdd-999-x wurde nicht entfernt"
    )

    backups = list(backup_dir.glob("*.tar.gz")) if backup_dir.exists() else []
    assert backups, f"AC-6 verletzt: kein tar.gz-Backup unter {backup_dir} gefunden"


def test_ac7_in_user_pattern_cleanup_preserves_real_files(tmp_path):
    """AC-7: Given ein Positivlisten-User enthaelt sowohl echte Trip-Dateien
    (gr221-mallorca.json) als auch Residuen-Muster (e2e-*, test-trip*) in
    trips/ bzw. weather_snapshots/ / When das Cleanup-Script mit --execute
    laeuft / Then werden ausschliesslich die Muster-Treffer geloescht,
    alle anderen Dateien bleiben inhaltlich und in der mtime unveraendert.
    Schlaegt aktuell fehl (Exit != 0), weil das Script nicht existiert.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    _build_test_tree(tree)

    real_trip = tree / "admin" / "trips" / "gr221-mallorca.json"
    real_snapshot = tree / "henning" / "weather_snapshots" / "real-snapshot.json"
    real_trip_content_before = real_trip.read_text()
    real_trip_mtime_before = real_trip.stat().st_mtime
    real_snapshot_mtime_before = real_snapshot.stat().st_mtime

    result = _run_cleanup_script(
        tree, extra_args=["--execute"], backup_dir=tmp_path / "backups"
    )

    assert result.returncode == 0, (
        f"AC-7 verletzt: --execute-Lauf sollte Exit 0 liefern, bekam "
        f"{result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert real_trip.exists(), (
        "AC-7 verletzt: gr221-mallorca.json (echter Trip) wurde faelschlich "
        "geloescht"
    )
    assert real_snapshot.exists(), (
        "AC-7 verletzt: real-snapshot.json wurde faelschlich geloescht"
    )
    assert real_trip.read_text() == real_trip_content_before, (
        "AC-7 verletzt: Inhalt von gr221-mallorca.json wurde veraendert"
    )
    assert real_trip.stat().st_mtime == real_trip_mtime_before, (
        "AC-7 verletzt: mtime von gr221-mallorca.json wurde veraendert"
    )
    assert real_snapshot.stat().st_mtime == real_snapshot_mtime_before, (
        "AC-7 verletzt: mtime von real-snapshot.json wurde veraendert"
    )

    assert not (tree / "admin" / "trips" / "e2e-foo.json").exists(), (
        "AC-7 verletzt: e2e-foo.json (Residuen-Muster) wurde nicht geloescht"
    )
    assert not (
        tree / "henning" / "weather_snapshots" / "test-trip.json"
    ).exists(), (
        "AC-7 verletzt: test-trip.json (Residuen-Muster) wurde nicht geloescht"
    )


def test_ac8_second_execute_run_is_idempotent(tmp_path):
    """AC-8: Given das Cleanup-Script wurde bereits einmal erfolgreich mit
    --execute ausgefuehrt (Residuen bereits entfernt) / When es ein
    zweites Mal mit --execute gegen denselben Baum laeuft / Then bricht es
    nicht mit einem Fehler ab (bereits geloeschte Pfade werden als "nichts
    zu tun" uebersprungen) — idempotentes Verhalten. Schlaegt aktuell
    fehl (Exit != 0 bereits beim ersten Lauf), weil das Script nicht
    existiert.
    """
    tree = tmp_path / "tree"
    tree.mkdir()
    _build_test_tree(tree)
    backup_dir = tmp_path / "backups"

    first = _run_cleanup_script(
        tree, extra_args=["--execute"], backup_dir=backup_dir
    )
    assert first.returncode == 0, (
        f"AC-8 verletzt: erster --execute-Lauf sollte gruen sein, bekam "
        f"{first.returncode}\nstdout:\n{first.stdout}\n"
        f"stderr:\n{first.stderr}"
    )

    second = _run_cleanup_script(
        tree, extra_args=["--execute"], backup_dir=backup_dir
    )
    assert second.returncode == 0, (
        f"AC-8 verletzt: zweiter --execute-Lauf gegen denselben Baum "
        f"bricht ab\nstdout:\n{second.stdout}\nstderr:\n{second.stderr}"
    )

    remaining = sorted(p.name for p in tree.iterdir())
    assert remaining == ["admin", "default", "henning"], (
        f"AC-8 verletzt: nach zweitem Lauf sind nicht mehr nur die "
        f"Positivlisten-User uebrig: {remaining}"
    )


# ---------------------------------------------------------------------------
# Adversary-Fix-Loop Regressionstests: F002-F005
# ---------------------------------------------------------------------------


def test_f002_empty_positivlist_hard_fails_and_deletes_nothing(tmp_path):
    """F002 (CRITICAL): Given eine leer geparste Positivliste (z.B. via
    --positivlist "" oder ausschliesslich Kommas/Whitespace) / When das
    Script mit --execute laeuft / Then bricht es mit Exit != 0 ab, OHNE
    irgendetwas zu loeschen — eine leere Positivliste wuerde sonst JEDES
    User-Verzeichnis als "outside" behandeln und den kompletten Baum
    loeschen."""
    tree = tmp_path / "tree"
    tree.mkdir()
    _build_test_tree(tree)
    before = sorted(p.name for p in tree.iterdir())
    assert before, "Praebedingung verletzt: Test-Baum ist leer"

    result = _run_cleanup_script(
        tree,
        extra_args=["--positivlist", " , ,", "--execute"],
        backup_dir=tmp_path / "backups",
    )

    assert result.returncode != 0, (
        f"F002 verletzt: leere Positivliste sollte hart fehlschlagen "
        f"(Exit != 0), bekam {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    after = sorted(p.name for p in tree.iterdir())
    assert after == before, (
        f"F002 verletzt: trotz Fehlschlag wurde der Baum veraendert: "
        f"{before} -> {after}"
    )


def test_f003_directory_shaped_residue_removed_cleanly(tmp_path):
    """F003 (HIGH): Given ein Residuen-Muster-Treffer (z.B. "e2e-foo") ist
    im echten Baum ein VERZEICHNIS statt einer Datei (z.B. ein fehlerhaft
    als Ordner angelegter Test-Trip-Export) / When das Script mit --execute
    laeuft / Then wird das Verzeichnis rekursiv entfernt (rmtree) statt
    dass ein IsADirectoryError den Lauf in einem Teilzustand abbricht."""
    tree = tmp_path / "tree"
    tree.mkdir()
    trips_dir = tree / "admin" / "trips"
    trips_dir.mkdir(parents=True)
    (trips_dir / "gr221-mallorca.json").write_text('{"real": true}')

    residue_dir = trips_dir / "e2e-broken-export"
    residue_dir.mkdir()
    (residue_dir / "inner.json").write_text('{"residue": true}')

    result = _run_cleanup_script(
        tree, extra_args=["--execute"], backup_dir=tmp_path / "backups"
    )

    assert result.returncode == 0, (
        f"F003 verletzt: Verzeichnis-Residuum darf den Lauf nicht mit "
        f"Exit != 0 abbrechen, bekam {result.returncode}\nstdout:\n"
        f"{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not residue_dir.exists(), (
        "F003 verletzt: Verzeichnis-foermiges Residuum wurde nicht entfernt"
    )
    assert (trips_dir / "gr221-mallorca.json").exists(), (
        "F003 verletzt: echter Trip wurde faelschlich mitentfernt"
    )


def test_f004_symlink_user_removed_without_following_target(tmp_path):
    """F004 (MEDIUM): Given ein Verzeichnis-Eintrag unter --root ist ein
    Symlink auf ein Verzeichnis AUSSERHALB des Baums (z.B. versehentlich
    verlinkter Nutzer) / When das Script mit --execute laeuft / Then wird
    NUR der Symlink selbst entfernt — sein Ziel bleibt unangetastet — und
    "Removed" wird nur bei tatsaechlichem Erfolg ausgegeben (kein
    ignore_errors=True, das einen Misserfolg als Erfolg meldet)."""
    tree = tmp_path / "tree"
    tree.mkdir()
    _build_test_tree(tree)

    real_target = tmp_path / "outside_target"
    real_target.mkdir()
    (real_target / "important.json").write_text('{"do_not_touch": true}')

    linked_user = tree / "linked-user"
    linked_user.symlink_to(real_target, target_is_directory=True)

    result = _run_cleanup_script(
        tree, extra_args=["--execute"], backup_dir=tmp_path / "backups"
    )

    assert result.returncode == 0, (
        f"F004 verletzt: Symlink-User darf den Lauf nicht mit Exit != 0 "
        f"abbrechen, bekam {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert not linked_user.exists(), (
        "F004 verletzt: der Symlink-Eintrag selbst wurde nicht entfernt"
    )
    assert not linked_user.is_symlink(), (
        "F004 verletzt: der Symlink-Eintrag existiert noch"
    )
    assert real_target.is_dir(), (
        "F004 verletzt: das Symlink-Ziel wurde geloescht — der Fix darf "
        "NIE dem Symlink in sein Ziel folgen"
    )
    assert (real_target / "important.json").read_text() == '{"do_not_touch": true}', (
        "F004 verletzt: Inhalt des Symlink-Ziels wurde veraendert"
    )


def test_f005_nonexistent_root_hard_fails(tmp_path):
    """F005 (MEDIUM): Given --root zeigt auf einen nicht existierenden Pfad
    / When das Script (mit oder ohne --execute) laeuft / Then bricht es mit
    Exit != 0 und einer expliziten Fehlermeldung ab, statt stillschweigend
    "nichts zu tun" (Exit 0) zu melden."""
    missing_root = tmp_path / "does-not-exist"
    assert not missing_root.exists()

    result = _run_cleanup_script(missing_root, backup_dir=tmp_path / "backups")

    assert result.returncode != 0, (
        f"F005 verletzt: nicht-existierendes --root sollte hart fehlschlagen "
        f"(Exit != 0), bekam {result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
