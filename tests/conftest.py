# ensures the 'src' directory is on sys.path for imports like 'from app import ...'
import os
import sys
from pathlib import Path

import pytest

root = Path(__file__).resolve().parents[1]
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

# Issue #346: force all tests onto the offline FixtureProvider so pytest runs
# never hit the live Open-Meteo API (and exhaust the server-IP rate limit).
_FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures", "openmeteo")


@pytest.fixture(autouse=True)
def _use_fixture_provider(request):
    """Activate the offline fixture provider for every test.

    Tests marked ``@pytest.mark.live`` get no fixture override — they hit the
    real API (contract-test obligation, mock ban). Function scope ensures
    clean ENV isolation between tests.
    """
    if request.node.get_closest_marker("live"):
        old = os.environ.pop("GZ_TEST_FIXTURE_DIR", None)
        yield
        if old is not None:
            os.environ["GZ_TEST_FIXTURE_DIR"] = old
    else:
        os.environ["GZ_TEST_FIXTURE_DIR"] = os.path.abspath(_FIXTURE_DIR)
        yield
        os.environ.pop("GZ_TEST_FIXTURE_DIR", None)


_REPO_DATA_USERS = root / "data" / "users"


def _snapshot_repo_data_users() -> dict[str, int]:
    """Issue #1265 Teil C (F003-Fix, Adversary Fix-Loop 1): rekursiver
    Aggregat-Fingerprint statt reiner Top-Level-mtime -- EIN ``os.walk`` pro
    Snapshot (Performance), erkennt aber auch In-Place-Content-Mutationen
    bestehender Dateien (die Top-Level-Verzeichnis-mtime ändert sich NICHT,
    wenn eine bestehende Datei per ``write_text``/``open(..., 'w')``
    überschrieben wird -- Adversary-Repro)."""
    if not _REPO_DATA_USERS.exists():
        return {}
    file_count = 0
    max_mtime_ns = 0
    total_size = 0
    try:
        for dirpath, _dirnames, filenames in os.walk(_REPO_DATA_USERS):
            for fname in filenames:
                try:
                    st = (Path(dirpath) / fname).stat()
                except OSError:
                    continue
                file_count += 1
                max_mtime_ns = max(max_mtime_ns, st.st_mtime_ns)
                total_size += st.st_size
    except OSError:
        return {}
    return {"file_count": file_count, "max_mtime_ns": max_mtime_ns, "total_size": total_size}


@pytest.fixture(autouse=True)
def _isolate_data_root(request, tmp_path_factory):
    """Redirect ``app.loader._DATA_ROOT`` to an isolated temp root for every
    test (Issue #1133), so pytest runs never write into the real
    ``data/users/`` tree.

    Tests marked ``@pytest.mark.real_data_root`` or ``@pytest.mark.live``
    opt out — they deliberately read/write the real tree (contract tests).

    Issue #1265 Teil C (Verursacher-Befund): die Redirect-Fixture allein
    schützt nur Code-Pfade, die tatsächlich über ``app.loader`` gehen --
    direkte ``<repo>/data/users``-Pfade laufen vorbei. Der Wächter unten
    prüft deshalb zusätzlich am Test-Ende, dass unter dem ECHTEN
    ``<repo>/data/users`` keine neuen/geänderten Top-Level-Einträge
    entstanden sind, und FAILT den Test sonst mit Klartext-Hinweis.
    """
    if request.node.get_closest_marker(
        "real_data_root"
    ) or request.node.get_closest_marker("live"):
        yield
        return

    from app import loader

    before = getattr(loader, "_DATA_ROOT", None)
    isolated_root = tmp_path_factory.mktemp("data_root")
    loader._DATA_ROOT = str(isolated_root)

    before_snapshot = _snapshot_repo_data_users()
    yield
    loader._DATA_ROOT = before

    after_snapshot = _snapshot_repo_data_users()
    if after_snapshot != before_snapshot:
        pytest.fail(
            "Issue #1265 Teil C (F003-Fix): dieser Test hat unter dem "
            f"ECHTEN {_REPO_DATA_USERS} geschrieben (vorher: "
            f"{before_snapshot}, nachher: {after_snapshot}). "
            "Kern-Tests duerfen nur ueber die isolierte "
            "app.loader.get_data_dir()-Basis bzw. tmp_path schreiben. "
            "Abhilfe: Pfad-Quelle auf get_data_dir()/tmp_path umstellen, "
            "oder falls der Test bewusst den echten Baum braucht: "
            "@pytest.mark.real_data_root / @pytest.mark.live setzen."
        )