"""#3279 Scheibe 1: Bezeichner-Vorfilter der Scanner-Ratschen.

Der Vorfilter entscheidet, welche Datei ein Waechter ueberhaupt parst. Ist er
zu streng, wird der Waechter still blind -- deshalb steht hier sein Vertrag,
dazu die Parsebarkeits-Pruefung (gefilterte Scanner parsen kaputte Dateien
nicht mehr zwingend) und der Nachweis der Worker-Gruppe (AC-8).

Spec: ``docs/specs/modules/rework_3279_scanner_ratschen_tempo_s1.md``.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
# Datei -> (Tests ohne Echtbaum fuer den inneren Lauf, Kennung der Echtbaum-Tests)
CACHE_DATEIEN = {
    "tests/tdd/test_fixture_wallclock_ratchet.py": ("scanner", "known_violations"),
    "tests/tdd/test_trip_fixtures_laufen_unter_gestellter_uhr.py": (
        "scanner", "known_violations"),
    "tests/tdd/test_thunder_scale_local_copy_guard.py": ("ac18", "echten_tests_baum"),
}


@pytest.fixture
def helfer():
    from tests.helpers import bezeichner_vorfilter
    return bezeichner_vorfilter


@pytest.mark.parametrize("quelle, alle, eines_aus, treffer", [
    ("x.strftime('%H')\n", ("strftime",), (), True),
    ("x.ｓｔｒｆｔｉｍｅ('%H')\n", ("strftime",), (), True),
    ("# Überschrift\nx.strftime('%H')\n", ("strftime",), (), True),
    ("from a import Stage as S\n", ("Stage",), (), True),
    ("x = 1\n", ("strftime",), (), False),
    ("# Überschrift\nx = 1\n", ("strftime",), (), False),
    ("make_trip()\n", ("make_trip", "save_trip"), (), False),
    ("make_trip(); save_trip()\n", ("make_trip", "save_trip"), (), True),
    ("import alert_gate\nStage()\n", ("Stage",), ("trip_alert", "alert_gate"), True),
    ("import q\nStage()\n", ("Stage",), ("trip_alert", "alert_gate"), False),
    ("import alert_gate\n", ("Stage",), ("trip_alert", "alert_gate"), False),
])
def test_vorfilter_liefert_quelltext_nur_bei_treffer(
    helfer, tmp_path, quelle, alle, eines_aus, treffer,
):
    datei = tmp_path / "x.py"
    datei.write_text(quelle, encoding="utf-8")
    ergebnis = helfer.quelltext_mit_bezeichnern(datei, alle=alle, eines_aus=eines_aus)
    assert ergebnis == (quelle if treffer else None)


def test_vorfilter_verschluckt_keine_lesefehler(helfer, tmp_path):
    (tmp_path / "x.py").write_bytes(b"strftime = '\xff'\n")
    with pytest.raises(UnicodeDecodeError):
        helfer.quelltext_mit_bezeichnern(tmp_path / "x.py", alle=("strftime",))
    with pytest.raises(OSError):
        helfer.quelltext_mit_bezeichnern(tmp_path / "fehlt.py", alle=("strftime",))


@pytest.mark.parametrize("inhalt", [
    b"def kaputt(:\n", b"x = 1\x00\n", b"x = '\xff'\n", None,
], ids=["syntax", "nullbyte", "utf8", "oserror"])
def test_unparsbare_datei_ergibt_befund_mit_dateiname(helfer, tmp_path, inhalt):
    """``None``: Symlink ins Leere -- Dateirechte griffen unter root nicht."""
    (tmp_path / "unter").mkdir()
    (tmp_path / "heil.py").write_text("x = 1\n", encoding="utf-8")
    assert helfer.unparsbare_dateien(tmp_path) == []
    kaputt = tmp_path / "unter" / "kaputt_xy.py"
    if inhalt is None:
        kaputt.symlink_to(tmp_path / "gibt_es_nicht")
    else:
        kaputt.write_bytes(inhalt)
    befunde = helfer.unparsbare_dateien(tmp_path)
    assert len(befunde) == 1 and "kaputt_xy.py" in befunde[0], befunde


def test_jede_testdatei_ist_parsbar(helfer):
    befunde = helfer.unparsbare_dateien(TESTS_ROOT)
    assert not befunde, "Nicht parsbare Dateien unter tests/:\n" + "\n".join(befunde)


def test_cache_dateien_laufen_je_in_einem_worker(tmp_path):
    """AC-8. Der innere Lauf beschraenkt sich auf die Faelle ohne Echtbaum
    (``-k`` je Datei), sonst fraesse er die Einsparung auf; dass die Gruppe
    ALLE Tests der Datei traegt, folgt aus der Modul-Markierung, die ueber
    ``pytestmark`` geprueft wird."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYTEST_XDIST") and k != "PYTEST_CURRENT_TEST"}
    lauf = subprocess.run(
        [sys.executable, "-m", "pytest", *CACHE_DATEIEN, "-o", "addopts=",
         "-p", "no:cacheprovider", "--basetemp", str(tmp_path / "innen"),
         "-v", "-n", "2", "--dist", "loadgroup",
         "-k", " or ".join(sorted({wahl for wahl, _ in CACHE_DATEIEN.values()}))],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=28, env=env,
    )
    gruppen = set()
    for datei, (wahl, echtbaum) in CACHE_DATEIEN.items():
        zeilen = re.findall(
            rf"^\[(gw\d)\].*(?:PASSED|FAILED) {re.escape(datei)}::(.+?)\s*$", lauf.stdout, re.M)
        assert len(zeilen) >= 4, f"{datei}: {lauf.stdout}\n{lauf.stderr}"
        assert all(wahl in k and echtbaum not in k for _, k in zeilen), zeilen
        assert len({worker for worker, _ in zeilen}) == 1, (
            f"{datei} verteilt sich auf mehrere Worker, der Cache wirkt nicht: {zeilen}")
        marke = importlib.import_module(datei[:-3].replace("/", ".")).pytestmark
        assert marke.name == "xdist_group"
        assert {k.rpartition("@")[2] for _, k in zeilen} == {marke.args[0]}
        gruppen.add(marke.args[0])
    assert len(gruppen) == 3 and "echtdaten" not in gruppen, gruppen
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


def test_jedes_item_der_cache_dateien_traegt_nur_die_gruppe_seiner_datei(tmp_path):
    """AC-8 fuer ALLE Items, auch die Echtbaum-Tests: eine fremde Gruppe an
    einem einzelnen Test wuerde ihn auf einen anderen Worker holen."""
    (tmp_path / "gruppen_plugin.py").write_text(
        "import json, pathlib\n"
        "def pytest_collection_finish(session):\n"
        "    zeilen = [(i.nodeid, [str(x) for m in i.iter_markers('xdist_group')\n"
        "               for x in (*m.args, *m.kwargs.values())]) for i in session.items]\n"
        "    pathlib.Path(__file__).with_name('gruppen.json').write_text(json.dumps(zeilen))\n",
        encoding="utf-8")
    pfade = os.pathsep.join(filter(None, [str(tmp_path), os.environ.get("PYTHONPATH")]))
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    lauf = subprocess.run(
        [sys.executable, "-m", "pytest", *CACHE_DATEIEN, "-o", "addopts=",
         "-p", "no:cacheprovider", "-p", "gruppen_plugin", "--collect-only"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=28,
        env=env | {"PYTHONPATH": pfade},
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    zeilen = json.loads((tmp_path / "gruppen.json").read_text(encoding="utf-8"))
    for datei, (_, echtbaum) in CACHE_DATEIEN.items():
        eigene = {k: gruppen for k, gruppen in zeilen if k.startswith(f"{datei}::")}
        erwartet = [importlib.import_module(datei[:-3].replace("/", ".")).pytestmark.args[0]]
        assert any(echtbaum in k for k in eigene), "Echtbaum-Tests fehlen"
        falsch = {k: g for k, g in eigene.items() if g != erwartet}
        assert not falsch, falsch
