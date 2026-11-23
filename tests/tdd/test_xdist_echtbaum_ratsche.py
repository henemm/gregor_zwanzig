"""TDD RED -- Issue #3209 AC-5: Echtbaum-Ratsche fuer parallele CI-Laeufe.

Spec: docs/specs/modules/perf_3209_pytest_xdist_ci.md (AC-5).

Unter ``pytest-xdist`` laufen nur Tests mit ``real_data_root`` (bzw.
``xdist_group("echtdaten")``) gemeinsam seriell in einem Worker. Eine
Testdatei, die den ECHTEN ``data/``-Baum ueber einen relativen Pfad beruehrt
(``Path("data/users")``, ``Path("data") / "users"``,
``os.path.join("data", "users", ...)``, ``rmtree`` fester user_ids darunter),
OHNE zur seriellen Gruppe zu gehoeren, wuerde parallel mit anderen Workern
kollidieren. Die Ratsche ``tests/helpers/echtbaum_ratsche.py`` meldet solche
Dateien; Neuzugaenge werden rot.

Schnittstelle (vom Developer umzusetzen):
``finde_echtbaum_verstoesse(wurzel: Path) -> list[str]`` -- relative Pfade
(POSIX, relativ zu ``wurzel``) aller Testdateien (``test_*.py``) mit
Verstoss, sortiert.

Die Beispiel-Inhalte unten sind bewusst aus Teilstuecken zusammengesetzt,
damit DIESE Datei selbst nicht als Verstoss erscheint.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

_D = '"da' + 'ta'
REL_USERS = "Path(" + _D + '/users")'                 # Path("data/users")
REL_GETEILT = "Path(" + _D + '") / "users"'           # Path("data") / "users"
OS_JOIN = "os.path.join(" + _D + '", "users", "fester-user")'


def _ratsche():
    from tests.helpers.echtbaum_ratsche import finde_echtbaum_verstoesse

    return finde_echtbaum_verstoesse


def _datei(wurzel: Path, name: str, inhalt: str) -> Path:
    pfad = wurzel / name
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


VERSTOESSE = {
    "relativer_users_pfad": (
        "from pathlib import Path\n\n"
        "def test_liest():\n"
        f"    assert {REL_USERS}.exists() or True\n"
    ),
    "geteilter_pfad": (
        "from pathlib import Path\n\n"
        "def test_schreibt():\n"
        f"    ({REL_GETEILT} / 'x').mkdir(parents=True, exist_ok=True)\n"
    ),
    "rmtree_fester_user": (
        "import shutil\nfrom pathlib import Path\n\n"
        "def test_raeumt():\n"
        f"    shutil.rmtree({REL_USERS} / 'fester-user', ignore_errors=True)\n"
    ),
    "os_path_join": (
        "import os, shutil\n\n"
        "def test_raeumt():\n"
        f"    shutil.rmtree({OS_JOIN}, ignore_errors=True)\n"
    ),
    # Fix-Loop 1 F003: absolute Repo-Wurzel statt relativem Pfad
    "repo_wurzel": (
        "import shutil\nfrom pathlib import Path\n\n"
        "REPO_ROOT = Path(__file__).resolve().parents[2]\n\n"
        "def test_raeumt():\n"
        f"    shutil.rmtree(REPO_ROOT / {_D}\" / \"users\" / 'fester-user', ignore_errors=True)\n"
    ),
    # Fix-Loop F007: Repo-Wurzel als erstes Argument von os.path.join
    "os_path_join_repo_wurzel": (
        "import os, shutil\nfrom pathlib import Path\n\n"
        "REPO_ROOT = Path(__file__).resolve().parents[2]\n\n"
        "def test_raeumt():\n"
        f"    shutil.rmtree(os.path.join(REPO_ROOT, {_D}\", \"users\", 'fester-user'), ignore_errors=True)\n"
    ),
    # Fix-Loop 2 (CI-Befund test_trip_alert_channel_precedence): f-String-Pfade
    "fstring_users_pfad": (
        "from pathlib import Path\n\n"
        "def test_schreibt():\n"
        "    uid = 'fester-user'\n"
        "    (Path(f" + _D + '/users/{uid}") / "user.json").write_text("{}")\n'
    ),
    "fstring_ohne_platzhalter": (
        "from pathlib import Path\n\n"
        "def test_liest():\n"
        "    assert Path(f" + _D + '/users").exists() or True\n'
    ),
    "fstring_data_dann_users": (
        "from pathlib import Path\n\n"
        "def test_liest():\n"
        "    uid = 'fester-user'\n"
        "    assert (Path(f" + _D + '") / f"users/{uid}").exists() or True\n'
    ),
    "fstring_os_path_join": (
        "import os, shutil\n\n"
        "def test_raeumt():\n"
        "    uid = 'fester-user'\n"
        "    shutil.rmtree(os.path.join(f" + _D + '/users", uid), ignore_errors=True)\n'
    ),
}


@pytest.mark.parametrize("fall", sorted(VERSTOESSE))
def test_ac5_verstoss_ohne_marker_wird_gemeldet(tmp_path, fall):
    """AC-5: Echtbaum-Zugriff ohne ``real_data_root`` -> Datei wird genannt."""
    _datei(tmp_path, f"tdd/test_{fall}.py", VERSTOESSE[fall])
    assert _ratsche()(tmp_path) == [f"tdd/test_{fall}.py"]


@pytest.mark.parametrize(
    "markierung",
    [
        "import pytest\npytestmark = pytest.mark.real_data_root\n",
        "import pytest\npytestmark = [pytest.mark.real_data_root]\n",
        "import pytest\npytestmark = pytest.mark.xdist_group('echtdaten')\n",
    ],
    ids=["modul-marker", "modul-marker-liste", "xdist-gruppe-echtdaten"],
)
def test_ac5_konforme_datei_bleibt_gruen(tmp_path, markierung):
    """AC-5: derselbe Zugriff MIT Zugehoerigkeit zur seriellen Gruppe ist
    erlaubt."""
    _datei(tmp_path, "tdd/test_konform.py", markierung + VERSTOESSE["rmtree_fester_user"])
    assert _ratsche()(tmp_path) == []


def test_ac5_marker_am_einzelnen_test_ist_konform(tmp_path):
    """AC-5: auch der Marker direkt am beruehrenden Test reicht."""
    inhalt = (
        "import pytest\nfrom pathlib import Path\n\n"
        "@pytest.mark.real_data_root\n"
        "def test_liest():\n"
        f"    assert {REL_USERS}.exists() or True\n"
    )
    _datei(tmp_path, "test_einzeln.py", inhalt)
    assert _ratsche()(tmp_path) == []


def test_ac5_fremde_xdist_gruppe_ist_nicht_konform(tmp_path):
    """AC-5: eine BELIEBIGE andere xdist-Gruppe ist nicht die serielle
    Echtdaten-Gruppe -- der Verstoss bleibt."""
    inhalt = "import pytest\npytestmark = pytest.mark.xdist_group('andere')\n" + VERSTOESSE["geteilter_pfad"]
    _datei(tmp_path, "test_andere_gruppe.py", inhalt)
    assert _ratsche()(tmp_path) == ["test_andere_gruppe.py"]


_HELFER = (
    "import shutil\nimport pytest\nfrom pathlib import Path\n\n"
    "def _aufraeumen(uid):\n"
    f"    shutil.rmtree({REL_USERS} / uid, ignore_errors=True)\n\n"
    "@pytest.mark.real_data_root\n"
    "def test_markiert():\n"
    "    _aufraeumen('a')\n\n"
)


def test_ac5_helfer_nur_von_markierten_tests_ist_konform(tmp_path):
    """AC-5 / Fix-Loop 1 F003: ein Helfer mit Echtbaum-Zugriff, den nur
    markierte Tests aufrufen, laeuft nur in der Gruppe -- konform."""
    _datei(tmp_path, "test_helfer_ok.py", _HELFER)
    assert _ratsche()(tmp_path) == []


def test_ac5_helfer_auch_von_unmarkiertem_test_ist_verstoss(tmp_path):
    """AC-5 / Fix-Loop 1 F003: ruft ZUSAETZLICH ein unmarkierter Test denselben
    Helfer auf, ist die transitive Konformitaet verletzt -- ein markierter
    Aufrufer allein entlastet nicht."""
    inhalt = _HELFER + "def test_unmarkiert():\n    _aufraeumen('b')\n"
    _datei(tmp_path, "test_helfer_gemischt.py", inhalt)
    assert _ratsche()(tmp_path) == ["test_helfer_gemischt.py"]


def test_ac5_unbeteiligte_datei_bleibt_gruen(tmp_path):
    """AC-5: ohne Echtbaum-Zugriff kein Befund (auch nicht fuer tmp_path-
    Unterordner namens ``data/users``)."""
    _datei(
        tmp_path, "test_sauber.py",
        "def test_tmp(tmp_path):\n"
        "    (tmp_path / 'data' / 'users').mkdir(parents=True)\n",
    )
    assert _ratsche()(tmp_path) == []


def test_ac5_fstring_unter_tmp_path_bleibt_gruen(tmp_path):
    """Fix-Loop 2: ein f-String-Pfad relativ zu ``tmp_path`` ist kein
    Echtbaum-Zugriff."""
    _datei(
        tmp_path, "test_sauber_fstring.py",
        "def test_tmp(tmp_path):\n"
        "    uid = 'u'\n"
        "    (tmp_path / f'data/users/{uid}').mkdir(parents=True)\n",
    )
    assert _ratsche()(tmp_path) == []


def test_ac5_mehrere_verstoesse_sortiert(tmp_path):
    _datei(tmp_path, "z/test_b.py", VERSTOESSE["os_path_join"])
    _datei(tmp_path, "a/test_a.py", VERSTOESSE["relativer_users_pfad"])
    assert _ratsche()(tmp_path) == ["a/test_a.py", "z/test_b.py"]


def test_ac5_echter_testbaum_ist_konform():
    """AC-5 Gegenprobe: der echte ``tests/``-Baum hat keinen Verstoss -- jede
    Datei mit Echtbaum-Zugriff gehoert zur seriellen Gruppe oder nutzt
    ``tmp_path``."""
    befunde = _ratsche()(REPO_ROOT / "tests")
    assert befunde == [], (
        "Testdateien beruehren den echten data/-Baum ohne real_data_root "
        "(unter xdist nicht seriell): " + ", ".join(befunde)
    )
