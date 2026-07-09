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


@pytest.fixture(autouse=True)
def _isolate_data_root(request, tmp_path_factory):
    """Redirect ``app.loader._DATA_ROOT`` to an isolated temp root for every
    test (Issue #1133), so pytest runs never write into the real
    ``data/users/`` tree.

    Tests marked ``@pytest.mark.real_data_root`` or ``@pytest.mark.live``
    opt out — they deliberately read/write the real tree (contract tests).
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
    yield
    loader._DATA_ROOT = before