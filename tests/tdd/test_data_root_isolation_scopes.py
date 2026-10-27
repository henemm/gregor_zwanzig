"""TDD RED -- Issue #2226: Testdaten-Isolation ueber Fixture-Scopes hinweg.

Spec: docs/specs/modules/fix_2226_testdaten_isolation.md, AC-1 bis AC-5.

Root Cause (Defekt 1 + 3): ``tests/conftest.py::_isolate_data_root`` ist
funktionsweit und schaltet sich fuer ``live``-markierte Tests komplett ab.
Beides laesst Schreibzugriffe unbemerkt in den ECHTEN ``<repo>/data/users``-
Baum durch: (1) hoeher gescopte Fixtures (module/class/session), die VOR der
funktionsweiten Redirect-Fixture laufen, und (3) ``live`` allein, obwohl das
laut ``pyproject.toml`` nur Netz-Egress bedeuten soll.

Diese Kern-Tests starten dafuer je einen INNEREN pytest-Subprozess ueber eine
synthetische Sonde unter ``tests/probes_data_root_isolation/`` (geladen wird
``tests/conftest.py``, aber ein normaler Suite-Lauf sammelt die Sonden nicht,
da sie kein ``test_``-Praefix im Dateinamen tragen) und pruefen danach den
ECHTEN Baum -- strukturell relativ zu DIESER Testdatei aufgeloest, NIE ueber
``app.loader``/``get_data_root()`` (dessen ``_DATA_ROOT`` zeigt zur Testzeit
selbst auf die isolierte Wegwerf-Wurzel DIESES aeusseren Tests).

KEINE Mocks (Projektregel) -- echte Subprozesse, echtes Dateisystem.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBES_DIR = REPO_ROOT / "tests" / "probes_data_root_isolation"


def _repo_data_users_root() -> Path:
    """Strukturell relativ zu DIESER Testdatei aufgeloest -- niemals ueber
    app.loader/get_data_root(), s. Moduldocstring."""
    return REPO_ROOT / "data" / "users"


def _fingerprint(path: Path) -> dict:
    """Eigenstaendige Kopie des Fingerprint-Algorithmus aus
    ``tests/conftest.py::_snapshot_repo_data_users`` -- bewusst NICHT von
    dort importiert, damit dieser Test seinen Pruefling unabhaengig vom
    Bestand der Wächter-Implementierung misst."""
    if not path.exists():
        return {"file_count": 0, "max_mtime_ns": 0, "total_size": 0}
    file_count = 0
    max_mtime_ns = 0
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for fname in filenames:
            try:
                st = (Path(dirpath) / fname).stat()
            except OSError:
                continue
            file_count += 1
            max_mtime_ns = max(max_mtime_ns, st.st_mtime_ns)
            total_size += st.st_size
    return {"file_count": file_count, "max_mtime_ns": max_mtime_ns, "total_size": total_size}


def _parent_dir_mtime_ns(path: Path) -> int:
    """AC-1: die reine Datei-Fingerprint-Zaehlung sieht neu angelegte LEERE
    Verzeichnisse nicht -- zusaetzlich die mtime von ``data/users`` SELBST."""
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _run_inner(probe_relpath: str, marker_expr: str = "") -> subprocess.CompletedProcess:
    """Startet einen inneren pytest-Lauf gegen eine Sonde unter tests/.

    ``-o addopts=`` neutralisiert die ini-Marker-Filterung
    (``pyproject.toml``: ``-m 'not email and not live and not staging'``),
    die sonst live-markierte Sonden aus dem inneren Lauf herausfiltert und
    ein falsches Gruen erzeugen wuerde (0 gesammelte Tests). Eigenes
    ``--basetemp``, damit der innere ``tmp_path_factory`` nicht mit dem
    aeusseren kollidiert.
    """
    with tempfile.TemporaryDirectory(prefix="gz-inner-basetemp-2226-") as basetemp:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(PROBES_DIR / probe_relpath),
            "-v",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            basetemp,
        ]
        if marker_expr:
            cmd += ["-m", marker_expr]
        return subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)


def _assert_probe_collected(proc: subprocess.CompletedProcess, expected_substr: str) -> None:
    assert expected_substr in proc.stdout, (
        f"Sonde wurde nicht gesammelt/ausgefuehrt (falsches Gruen waere moeglich) -- "
        f"'{expected_substr}' fehlt in stdout.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


@pytest.fixture(scope="module", autouse=True)
def _warm_up_real_data_root_materialization():
    """Muss VOR jeder Baseline-Messung laufen: der erste innere pytest-Lauf
    ueberhaupt fuehrt ``_materialize_real_data_root_fixtures``
    (session-autouse in ``tests/conftest.py``) aus und kopiert Referenz-
    Fixtures additiv in den ECHTEN Baum. Ohne diesen Aufwaermlauf waere diese
    einmalige Kopie faelschlich Teil des ersten AC-Diffs. Nach dem ersten
    Lauf ist die Materialisierung idempotent (``if target.exists(): continue``).
    """
    proc = _run_inner("probe_warmup_noop.py")
    assert proc.returncode == 0, (
        f"Aufwaermlauf ist fehlgeschlagen -- Baseline unsicher.\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    yield


def _cleanup_probe_user_dir(user_id: str) -> None:
    probe_dir = _repo_data_users_root() / user_id
    if probe_dir.exists():
        shutil.rmtree(probe_dir)


# ---------------------------------------------------------------------------
# AC-1: module-scope Fixture ohne Marker -- Defekt 3
# ---------------------------------------------------------------------------


def test_ac1_module_scope_fixture_without_marker_leaves_real_tree_untouched():
    """AC-1: eine module-scope Fixture ohne jeden Marker, die ueber
    get_data_dir() schreibt, darf den echten Baum weder inhaltlich noch in
    der mtime veraendern -- auch nicht voruebergehend."""
    real_root = _repo_data_users_root()
    before = _fingerprint(real_root)
    before_mtime = _parent_dir_mtime_ns(real_root)

    try:
        proc = _run_inner("probe_ac1_module_fixture.py")
        _assert_probe_collected(proc, "test_probe_ac1_placeholder")

        after = _fingerprint(real_root)
        after_mtime = _parent_dir_mtime_ns(real_root)

        assert before == after and before_mtime == after_mtime, (
            "AC-1 verletzt: eine module-scope Fixture ohne Marker hat den "
            f"ECHTEN {real_root} veraendert (Defekt 3 -- module-Fixtures "
            "laufen vor der funktionsweiten _isolate_data_root-Redirect-"
            f"Fixture). Vorher: {before} (mtime {before_mtime}), "
            f"nachher: {after} (mtime {after_mtime}).\n"
            f"Inner STDOUT:\n{proc.stdout}"
        )
    finally:
        _cleanup_probe_user_dir("probe-2226-ac1-modul")


# ---------------------------------------------------------------------------
# AC-2: dieselbe Sonde B mit real_data_root -- Opt-in muss weiter funktionieren
# ---------------------------------------------------------------------------


def test_ac2_real_data_root_marker_still_reaches_real_tree():
    """AC-2: mit @pytest.mark.real_data_root markiert, erreicht dieselbe
    Sonde weiterhin den echten Baum -- das Opt-in darf durch den Fix nicht
    kaputtgehen (Regressionssperre, kein Defekt)."""
    user_id = "probe-2226-ac2-modul-optin"
    trace_file = _repo_data_users_root() / user_id / "user.json"

    real_root = _repo_data_users_root()
    before = _fingerprint(real_root)

    try:
        proc = _run_inner("probe_ac2_module_fixture_real_data_root.py", marker_expr="real_data_root")
        _assert_probe_collected(proc, "test_probe_ac2_placeholder")

        assert trace_file.exists(), (
            "AC-2 verletzt: @pytest.mark.real_data_root sollte weiterhin den "
            f"echten Baum erreichen, aber {trace_file} wurde nicht angelegt.\n"
            f"Inner STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    finally:
        _cleanup_probe_user_dir(user_id)

    after = _fingerprint(real_root)
    assert before == after, (
        "Aufraeumen unvollstaendig -- der echte Baum weicht nach dem Test "
        f"noch vom Vorzustand ab. Vorher: {before}, nachher: {after}."
    )


# ---------------------------------------------------------------------------
# AC-3: live-markierter Test ohne real_data_root -- Defekt 1
# ---------------------------------------------------------------------------


def test_ac3_live_marker_alone_leaves_real_tree_untouched():
    """AC-3: ein live-markiertes Modul ohne real_data_root, das save_trip()
    aufruft, darf NICHT in den echten Baum schreiben -- live allein darf die
    Isolation nicht mehr abschalten (Defekt 1)."""
    real_root = _repo_data_users_root()
    before = _fingerprint(real_root)
    before_mtime = _parent_dir_mtime_ns(real_root)

    try:
        proc = _run_inner("probe_ac3_live_save_trip.py", marker_expr="live")
        _assert_probe_collected(proc, "test_probe_ac3_live_save_trip_no_real_data_root")

        after = _fingerprint(real_root)
        after_mtime = _parent_dir_mtime_ns(real_root)

        assert before == after and before_mtime == after_mtime, (
            "AC-3 verletzt: ein live-markierter save_trip()-Aufruf ohne "
            f"real_data_root hat den ECHTEN {real_root} veraendert (Defekt 1 "
            "-- _isolate_data_root gibt fuer den live-Marker heute komplett "
            f"fruehzeitig zurueck). Vorher: {before} (mtime {before_mtime}), "
            f"nachher: {after} (mtime {after_mtime}).\n"
            f"Inner STDOUT:\n{proc.stdout}"
        )
    finally:
        _cleanup_probe_user_dir("probe-2226-ac3-live")


# ---------------------------------------------------------------------------
# AC-4: live + real_data_root -- Opt-in muss weiter funktionieren
# ---------------------------------------------------------------------------


def test_ac4_live_and_real_data_root_still_reaches_real_tree():
    """AC-4: mit live UND real_data_root markiert, erreicht save_trip()
    weiterhin den echten Baum (Regressionssperre, kein Defekt)."""
    user_id = "probe-2226-ac4-live-optin"
    trace_dir = _repo_data_users_root() / user_id

    real_root = _repo_data_users_root()
    before = _fingerprint(real_root)

    try:
        proc = _run_inner(
            "probe_ac4_live_real_data_root_save_trip.py", marker_expr="live and real_data_root"
        )
        _assert_probe_collected(proc, "test_probe_ac4_live_real_data_root_save_trip")

        assert trace_dir.exists() and any(trace_dir.rglob("*.json")), (
            "AC-4 verletzt: live + real_data_root sollte weiterhin den echten "
            f"Baum erreichen, aber unter {trace_dir} liegt keine JSON-Datei.\n"
            f"Inner STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    finally:
        _cleanup_probe_user_dir(user_id)

    after = _fingerprint(real_root)
    assert before == after, (
        "Aufraeumen unvollstaendig -- der echte Baum weicht nach dem Test "
        f"noch vom Vorzustand ab. Vorher: {before}, nachher: {after}."
    )


# ---------------------------------------------------------------------------
# AC-5: hartkodierter Pfad -- session-weiter Waechter muss den Lauf scheitern lassen
# ---------------------------------------------------------------------------


def test_ac5_hardcoded_path_write_fails_the_inner_run():
    """AC-5: eine module-scope Fixture, die per hartkodiertem Pfad (nicht
    ueber app.loader) eine Datei unter dem echten Baum anlegt, muss den
    inneren Lauf scheitern lassen -- der bestehende funktionsweite Waechter
    sieht das strukturell nicht (sein before_snapshot liegt bereits NACH der
    Verschmutzung durch die module-scope Fixture)."""
    real_root = _repo_data_users_root()
    probe_file = real_root / "probe-2226-ac5-hardcoded" / "marker.txt"

    try:
        proc = _run_inner("probe_ac5_hardcoded_path_write.py")
        _assert_probe_collected(proc, "test_probe_ac5_placeholder")

        assert proc.returncode != 0, (
            "AC-5 verletzt: der innere Lauf ist trotz hartkodiertem "
            f"Schreibzugriff unter dem echten {real_root} mit returncode 0 "
            "durchgelaufen (Defekt 3 -- der bestehende funktionsweite "
            "Waechter nimmt seinen before_snapshot erst NACH der module-"
            f"scope Fixture, sieht die Verschmutzung also nie). Datei "
            f"existiert: {probe_file.exists()}.\n"
            f"Inner STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    finally:
        probe_dir = real_root / "probe-2226-ac5-hardcoded"
        if probe_dir.exists():
            shutil.rmtree(probe_dir)
