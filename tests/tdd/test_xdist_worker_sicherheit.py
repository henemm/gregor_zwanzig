"""TDD RED -- Issue #3209: parallele Kern-Suite in CI (pytest-xdist).

Spec: docs/specs/modules/perf_3209_pytest_xdist_ci.md (AC-3, AC-4, AC-6,
AC-7, AC-8).

Alle Nachweise laufen als ECHTE innere pytest-Subprozesse auf Sonden unter
``tests/probes_xdist/`` (kein ``test_``-Praefix, ein normaler Suite-Lauf
sammelt sie nicht) -- geladen wird dabei ``tests/conftest.py`` mit allen
Echtbaum-Waechtern und dem Loopback-Port-Guard. Kein Mock-Theater.

Das Modul traegt ``real_data_root``: es raeumt Sonden-Spuren im ECHTEN
``<repo>/data/users`` weg und stellt fuer den Materialisierungs-Nachweis
Referenz-Kopien wieder her. Damit gehoert es -- korrekt -- in die serielle
Echtdaten-Gruppe.

Zeitbudget: jeder innere Lauf startet einen eigenen Interpreter (mit ``-n 2``
zusaetzlich zwei Worker), importiert die App und wartet in AC-4 bewusst auf
ein Schreibfenster. Der globale ``timeout = 30`` reicht dafuer nicht; die
Anhebung gilt nur fuer diese Subprozess-Tests.
"""
from __future__ import annotations

import ast
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

pytestmark = [pytest.mark.real_data_root, pytest.mark.timeout(240)]

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBES = REPO_ROOT / "tests" / "probes_xdist"
FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "data_root"

# Strukturell relativ zu DIESER Datei, nie ueber app.loader (dessen
# _DATA_ROOT zeigt zur Testzeit auf eine Wegwerf-Wurzel).
ECHTER_USERS_BAUM = REPO_ROOT.joinpath("data", "users")

SONDEN_USER = (
    "probe-3209-ac3-unmarkiert",
    "probe-3209-ac3-markiert",
    "probe-3209-ac4-fenster",
    "probe-3209-f001-spur",
    "probe-3209-f004",
    "probe-3209-g-fenster",
)

OFFLINE_FORM = [
    "--disable-socket",
    "--allow-unix-socket",
    "--allow-hosts=127.0.0.1,::1,localhost",
    "--loopback-own-ports",
]

WAECHTER_MELDUNGEN = ("Issue #1265 Teil C", "Issue #2226")


def _sauberes_env(probe_dir: Path) -> dict[str, str]:
    """Umgebung fuer den inneren Lauf. Laeuft DIESER Test selbst in einem
    xdist-Worker (CI ``-n 4``), erbt er ``PYTEST_XDIST_*`` -- der innere
    Controller hielte sich sonst faelschlich fuer einen Worker."""
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith("PYTEST_XDIST") and k != "PYTEST_CURRENT_TEST"
    }
    env["GZ_XDIST_PROBE_DIR"] = str(probe_dir)
    return env


def _innerer_lauf(
    ziele: list[str], probe_dir: Path, extra: list[str] | None = None,
    *, projekt_addopts: bool = False,
) -> subprocess.CompletedProcess:
    """``projekt_addopts=True`` (#3278): der Lauf behaelt die ``addopts`` des
    Projekts -- fuer Nachweise an der woertlichen Gate-Form."""
    ohne_addopts = [] if projekt_addopts else ["-o", "addopts=", "-p", "no:cacheprovider"]
    with tempfile.TemporaryDirectory(prefix="gz-inner-basetemp-3209-") as basetemp:
        cmd = [
            sys.executable, "-m", "pytest", *ziele,
            *ohne_addopts,
            "--basetemp", basetemp,
            "-v", "-rfE", "--tb=short",
            *(extra or []),
        ]
        return subprocess.run(
            cmd, cwd=str(REPO_ROOT), capture_output=True, text=True,
            timeout=200, env=_sauberes_env(probe_dir),
        )


def _ausgabe(proc: subprocess.CompletedProcess) -> str:
    return f"EXIT={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"


def _protokoll(probe_dir: Path) -> list[dict]:
    pfad = probe_dir / "protokoll.jsonl"
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def _sonden(*namen: str) -> list[str]:
    return [str(PROBES / n) for n in namen]


def _xdist_lief_mit_zwei_workern(proc: subprocess.CompletedProcess) -> None:
    text = proc.stdout + proc.stderr
    assert "2 workers" in text or "created: 2/2 workers" in text, (
        "Der innere Lauf lief NICHT mit zwei xdist-Workern -- ohne Parallel-"
        "Lauf beweist dieser Test nichts.\n" + _ausgabe(proc)
    )


@pytest.fixture
def probe_dir(tmp_path):
    d = tmp_path / "probe"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _sonden_spuren_entfernen():
    """Sonden-Spuren im echten Baum vor UND nach jedem Test entfernen --
    auch nach einem fehlgeschlagenen inneren Lauf."""
    def _weg():
        for user in SONDEN_USER:
            pfad = ECHTER_USERS_BAUM / user
            if pfad.exists():
                shutil.rmtree(pfad)
    _weg()
    yield
    _weg()


# ---------------------------------------------------------------------------
# AC-3: unmarkierter Echtbaum-Schreiber wird seriell UND parallel rot
# ---------------------------------------------------------------------------


def test_ac3_unmarkierter_schreiber_seriell_rot(probe_dir):
    """AC-3 (Gegenprobe seriell): der bestehende Waechter faengt den
    unmarkierten Schreiber -- Exit != 0 und Waechter-Meldung."""
    proc = _innerer_lauf(_sonden("probe_ac3_unmarkierter_schreiber.py"), probe_dir)
    assert proc.returncode != 0, "unmarkierter Schreiber lief seriell gruen\n" + _ausgabe(proc)
    assert any(m in proc.stdout for m in WAECHTER_MELDUNGEN), _ausgabe(proc)
    assert any(e["art"] == "ac3_unmarkiert_geschrieben" for e in _protokoll(probe_dir)), (
        "Sonde lief nicht -- falsches Rot moeglich\n" + _ausgabe(proc)
    )


def test_ac3_unmarkierter_schreiber_parallel_rot(probe_dir):
    """AC-3: derselbe unmarkierte Schreiber wird mit ``-n 2 --dist loadgroup``
    ebenfalls rot -- und zwar AUCH DANN, wenn gleichzeitig ein legitimer
    ``real_data_root``-Schreiber auf dem anderen Worker laeuft. Die
    Gruppen-Ausnahme darf den Waechter nicht pauschal entschaerfen."""
    proc = _innerer_lauf(
        _sonden("probe_ac3_markierter_schreiber.py", "probe_ac3_unmarkierter_schreiber.py"),
        probe_dir, ["-n", "2", "--dist", "loadgroup"],
    )
    _xdist_lief_mit_zwei_workern(proc)
    assert proc.returncode != 0, "unmarkierter Schreiber lief parallel gruen\n" + _ausgabe(proc)
    assert any(m in proc.stdout for m in WAECHTER_MELDUNGEN), _ausgabe(proc)
    fehlerzeilen = [
        z for z in proc.stdout.splitlines()
        if z.startswith(("ERROR ", "FAILED ")) and "probe_ac3" in z
    ]
    assert any("probe_ac3_unmarkierter_schreiber" in z for z in fehlerzeilen), (
        "Der Verstoss wird nicht dem unmarkierten Schreiber zugeordnet\n" + _ausgabe(proc)
    )
    assert not any("probe_ac3_markierter_schreiber" in z for z in fehlerzeilen), (
        "Der legitime real_data_root-Schreiber wurde faelschlich rot\n" + _ausgabe(proc)
    )


def test_ac3_modul_fixture_spur_faengt_der_controller(probe_dir):
    """AC-3 / Fix-Loop 1 F001: eine Modul-Fixture ohne ``real_data_root``
    hinterlaesst eine Spur im echten Baum. Der Per-Test-Waechter sieht sie
    strukturell nicht, die Session-Waechter der Worker sind unter xdist aus --
    der Session-Waechter des CONTROLLERS muss den Lauf mit ``-n 2`` scheitern
    lassen, obwohl der Test selbst gruen ist."""
    proc = _innerer_lauf(
        _sonden("probe_f001_modul_spur.py"), probe_dir, ["-n", "2", "--dist", "loadgroup"],
    )
    _xdist_lief_mit_zwei_workern(proc)
    assert any(e["art"] == "f001_spur_gelegt" for e in _protokoll(probe_dir)), (
        "Sonde lief nicht -- falsches Rot moeglich\n" + _ausgabe(proc)
    )
    assert "PASSED" in proc.stdout and "test_probe_f001" in proc.stdout, (
        "Nachweis ungueltig: der Sondentest selbst muss gruen sein, sonst "
        "faengt nicht der Controller\n" + _ausgabe(proc)
    )
    assert proc.returncode != 0, "bleibende Spur ging unter xdist durch\n" + _ausgabe(proc)
    assert "xdist-Controller" in proc.stdout and "Issue #2226" in proc.stdout, _ausgabe(proc)


def test_ac3_eigener_gruppen_journaleintrag_entschuldigt_nichts(probe_dir):
    """AC-3 / Fix-Loop 1 F004: im SELBEN Worker laeuft nach einem
    ``real_data_root``-Test, der den Teilbaum ``probe-3209-f004`` journalisiert
    hat, ein unmarkierter Test, der in genau diesen Teilbaum schreibt. Der
    Journal-Eintrag liegt im Zeitfenster, stammt aber aus demselben Prozess --
    der Verstoss muss trotzdem rot werden (PID-Ausschluss)."""
    proc = _innerer_lauf(
        _sonden("probe_f004_a_gruppe.py", "probe_f004_b_nachzuegler.py"),
        probe_dir, ["-n", "1", "--dist", "loadgroup"],
    )
    reihenfolge = [e["art"] for e in _protokoll(probe_dir)]
    assert reihenfolge == ["f004_gruppe", "f004_nachzuegler"], (
        f"Nachweis ungueltig: Reihenfolge {reihenfolge} (Gruppe muss zuerst "
        "laufen, im selben Worker)\n" + _ausgabe(proc)
    )
    assert proc.returncode != 0, (
        "eigener Journal-Eintrag hat den Verstoss entschuldigt\n" + _ausgabe(proc)
    )
    fehlerzeilen = [z for z in proc.stdout.splitlines() if z.startswith(("ERROR ", "FAILED "))]
    assert any("probe_f004_b_nachzuegler" in z for z in fehlerzeilen), _ausgabe(proc)
    assert "Issue #1265 Teil C" in proc.stdout, _ausgabe(proc)


# ---------------------------------------------------------------------------
# AC-4: serielle Echtdaten-Gruppe, kein Fehlalarm, Materialisierung einmal
# ---------------------------------------------------------------------------


def test_ac4_echtdaten_gruppe_in_einem_worker_ohne_fehlalarm(probe_dir):
    """AC-4: alle ``real_data_root``-Tests (Modul- UND Test-Marker, zwei
    Dateien) landen automatisch im selben Worker; ein unbeteiligter Test auf
    dem anderen Worker endet, WAEHREND die Gruppe im echten Baum schreibt,
    und bekommt keinen Waechter-Fehler (weder je Test noch session-weit)."""
    proc = _innerer_lauf(
        _sonden(
            "probe_ac4_a1_echtdaten.py",
            "probe_ac4_b_beobachter.py",
            "probe_ac4_a2_echtdaten.py",
            "probe_ac4_c_unbeteiligt.py",
        ),
        probe_dir, ["-n", "2", "--dist", "loadgroup"],
    )
    _xdist_lief_mit_zwei_workern(proc)
    protokoll = _protokoll(probe_dir)

    echtdaten = [e for e in protokoll if e["art"] == "ac4_echtdaten"]
    assert len(echtdaten) == 7, (
        f"erwartet 7 real_data_root-Sondentests, protokolliert {len(echtdaten)}\n" + _ausgabe(proc)
    )
    worker = {e["worker"] for e in echtdaten}
    assert len(worker) == 1, (
        f"real_data_root-Tests liefen auf mehreren Workern {sorted(worker)} -- "
        "keine automatische serielle xdist_group\n" + _ausgabe(proc)
    )

    beobachter = [e for e in protokoll if e["art"] == "ac4_beobachter"]
    assert beobachter and beobachter[0]["fenster_gesehen"], (
        "Nachweis ungueltig: Beobachter hat das Schreibfenster nicht erlebt\n" + _ausgabe(proc)
    )
    assert beobachter[0]["worker"] not in worker, (
        "Beobachter lief im Worker der Echtdaten-Gruppe -- Parallelitaet nicht belegt\n"
        + _ausgabe(proc)
    )

    assert proc.returncode == 0, (
        "Fehlalarm: ein unbeteiligter Test (oder der Session-Waechter eines "
        "anderen Workers) wertet die legitime Gruppenaenderung als Verstoss\n"
        + _ausgabe(proc)
    )
    assert not any(m in proc.stdout for m in WAECHTER_MELDUNGEN), _ausgabe(proc)


def _fehlerzeilen(proc: subprocess.CompletedProcess) -> list[str]:
    return [z for z in proc.stdout.splitlines() if z.startswith(("ERROR ", "FAILED "))]


def test_ac4_innerer_lauf_ausserhalb_der_gruppe_trifft_den_starter(probe_dir):
    """AC-3/AC-4, CI-Lauf vom 2026-11-23: ein Test OHNE Echtdaten-Gruppe
    startet einen inneren seriellen pytest-Lauf mit einem ``real_data_root``-
    Test (``test_issue_1014_live_optin.py`` -> ``test_issue_1001`` TestAC7 ->
    ``default/diagnostics/forecast_budget.json``). Dessen Schreibzugriffe
    stehen in keinem Journal; der Waechter eines UNBETEILIGTEN Tests auf einem
    anderen Worker schlug an (``test_issue_1142``, zweimal ERROR).

    Soll: der innere ``real_data_root``-Test darf ausserhalb der seriellen
    Gruppe nicht in den echten Baum schreiben, der Beobachter bleibt gruen,
    und rot wird der Verursacher -- der Starter --, auch wenn er den
    Exit-Code seines inneren Laufs ignoriert."""
    proc = _innerer_lauf(
        _sonden("probe_g_starter_unmarkiert.py", "probe_g_beobachter.py"),
        probe_dir, ["-n", "2", "--dist", "loadgroup"],
    )
    _xdist_lief_mit_zwei_workern(proc)
    protokoll = _protokoll(probe_dir)
    worker = {e["art"]: e["worker"] for e in protokoll if e["art"] in ("g_starter", "g_beobachter")}
    assert len(worker) == 2 and len(set(worker.values())) == 2, (
        f"Nachweis ungueltig: Starter und Beobachter nicht auf zwei Workern {worker}\n"
        + _ausgabe(proc)
    )
    assert any(e["art"] == "g_innen_exit" for e in protokoll), (
        "Nachweis ungueltig: der innere Lauf wurde nie gestartet\n" + _ausgabe(proc)
    )
    fehler = _fehlerzeilen(proc)
    assert not any("probe_g_beobachter" in z for z in fehler), (
        "Fehlalarm: der unbeteiligte Beobachter wurde rot\n" + _ausgabe(proc)
    )
    assert not any(e["art"] == "g_innen_lief" for e in protokoll), (
        "Der innere real_data_root-Test lief ausserhalb der seriellen Gruppe "
        "und schrieb in den echten Baum\n" + _ausgabe(proc)
    )
    assert any("probe_g_starter_unmarkiert" in z for z in fehler), (
        "Der Verursacher (Starter ohne Echtdaten-Gruppe) blieb gruen\n" + _ausgabe(proc)
    )
    assert "Issue #3209" in proc.stdout and "xdist_group" in proc.stdout, _ausgabe(proc)


def test_ac4_innerer_lauf_in_der_gruppe_ohne_fehlalarm(probe_dir):
    """AC-4: derselbe innere Lauf, gestartet aus der seriellen Echtdaten-Gruppe,
    schreibt journalisiert -- der Beobachter erlebt das offene Fenster und
    bleibt gruen, der ganze Lauf ist gruen."""
    proc = _innerer_lauf(
        _sonden("probe_g_starter_markiert.py", "probe_g_beobachter.py"),
        probe_dir, ["-n", "2", "--dist", "loadgroup"],
    )
    _xdist_lief_mit_zwei_workern(proc)
    protokoll = _protokoll(probe_dir)
    beobachter = [e for e in protokoll if e["art"] == "g_beobachter"]
    assert beobachter and beobachter[0]["fenster_gesehen"], (
        "Nachweis ungueltig: der Beobachter hat das Schreibfenster nicht erlebt\n"
        + _ausgabe(proc)
    )
    starter = [e for e in protokoll if e["art"] == "g_starter"]
    assert starter and starter[0]["worker"] != beobachter[0]["worker"], _ausgabe(proc)
    assert proc.returncode == 0, "Fehlalarm im Gruppen-Fall\n" + _ausgabe(proc)
    assert not any(m in proc.stdout for m in WAECHTER_MELDUNGEN), _ausgabe(proc)


def _materialisierte_kopien() -> list[tuple[Path, Path]]:
    """(Quelle, Kopie im echten Baum) fuer jede Referenz-Datei, deren Kopie
    byte-gleich zur Quelle ist -- nur solche reinen Kopien nimmt der
    Materialisierungs-Nachweis kurzzeitig weg."""
    paare = []
    for src in sorted(FIXTURE_SRC.rglob("*")):
        if not src.is_file():
            continue
        ziel = REPO_ROOT / "data" / src.relative_to(FIXTURE_SRC)
        if ziel.is_file() and ziel.read_bytes() == src.read_bytes():
            paare.append((src, ziel))
    return paare


def test_ac4_materialisierung_einmal_ohne_race(probe_dir, tmp_path):
    """AC-4: fehlen die materialisierten Referenz-Kopien (frischer Checkout
    wie in CI), materialisieren mehrere gleichzeitig startende Worker sie
    ohne Race: kein Worker bricht ab, kein Session-Waechter schlaegt an,
    jede Kopie ist am Ende byte-gleich zur Quelle, und alle unbeteiligten
    Tests aller Worker sehen dieselbe vollstaendige Wurzel.

    Drei Wiederholungen mit vier Workern, weil ein Race zeitabhaengig ist."""
    paare = _materialisierte_kopien()
    assert paare, "keine materialisierten Referenz-Kopien gefunden -- Nachweis leer"
    sicherung = tmp_path / "sicherung"
    gemerkt = []
    for i, (_src, ziel) in enumerate(paare):
        st = ziel.stat()
        ablage = sicherung / str(i)
        ablage.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ziel, ablage)
        gemerkt.append((ziel, ablage, st.st_atime_ns, st.st_mtime_ns))
    try:
        for runde in range(3):
            for ziel, *_ in gemerkt:
                ziel.unlink()
            (probe_dir / "protokoll.jsonl").unlink(missing_ok=True)
            proc = _innerer_lauf(
                _sonden("probe_ac4_c_unbeteiligt.py"), probe_dir,
                ["-n", "4", "--dist", "loadgroup"],
            )
            assert "4 workers" in proc.stdout + proc.stderr, _ausgabe(proc)
            assert proc.returncode == 0, f"Runde {runde}: Materialisierungs-Race\n" + _ausgabe(proc)
            for src, ziel in paare:
                assert ziel.is_file() and ziel.read_bytes() == src.read_bytes(), (
                    f"Runde {runde}: {ziel} fehlt oder ist unvollstaendig"
                )
            sichten = {
                json.dumps(e["fingerprint"], sort_keys=True)
                for e in _protokoll(probe_dir) if e["art"] == "ac4_unbeteiligt"
            }
            assert len(sichten) == 1, (
                f"Runde {runde}: Worker sahen unterschiedliche Wurzeln {sichten}\n" + _ausgabe(proc)
            )
    finally:
        for ziel, ablage, atime, mtime in gemerkt:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ablage, ziel)
            os.utime(ziel, ns=(atime, mtime))


# ---------------------------------------------------------------------------
# AC-6: Egress-Sperre und Loopback-Port-Guard in JEDEM Worker
# ---------------------------------------------------------------------------


def test_ac6_egress_und_loopback_guard_in_jedem_worker(probe_dir):
    """AC-6: mit der sicheren Offline-Form und ``-n 2 --dist each`` laeuft
    jede Netz-Sonde auf BEIDEN Workern; in beiden ist Egress gesperrt, ein
    fremder Loopback-Port gesperrt und der eigene ``:0``-Port erlaubt."""
    proc = _innerer_lauf(
        _sonden("probe_ac6_netz.py"), probe_dir,
        [*OFFLINE_FORM, "-n", "2", "--dist", "each"],
    )
    _xdist_lief_mit_zwei_workern(proc)
    assert proc.returncode == 0, _ausgabe(proc)
    protokoll = _protokoll(probe_dir)
    for art, soll in (("ac6_egress", "blockiert"), ("ac6_fremd", "blockiert"), ("ac6_eigen", "erlaubt")):
        je_worker = {e["worker"]: e["ergebnis"] for e in protokoll if e["art"] == art}
        assert set(je_worker) == {"gw0", "gw1"}, (
            f"{art}: nicht in beiden Workern gelaufen: {je_worker}\n" + _ausgabe(proc)
        )
        assert all(v == soll for v in je_worker.values()), (
            f"{art}: erwartet '{soll}' in jedem Worker, gefunden {je_worker}"
        )


# ---------------------------------------------------------------------------
# AC-7: serielle Gate-Form bleibt frei; von den ``-n``-Formen ist genau das
# parallele Literal frei (#3278), jede andere bleibt gesperrt
# ---------------------------------------------------------------------------

GATE = REPO_ROOT / ".claude" / "hooks" / "broad_test_run_gate.py"


def _gate(command: str) -> subprocess.CompletedProcess:
    leer = tempfile.mkdtemp(prefix="gate3209-")
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = leer
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(GATE)], input=payload, capture_output=True,
        text=True, cwd=str(REPO_ROOT), env=env, timeout=30,
    )


def _paralleles_literal() -> str:
    """``OFFLINE_PARALLEL_CALL`` per ``ast`` aus der Gate-Datei -- kein Import,
    damit der Nachweis auch in CI (ohne Plugin agent-os-openspec) laeuft."""
    for knoten in ast.parse(GATE.read_text(encoding="utf-8")).body:
        if isinstance(knoten, ast.Assign) and any(
            isinstance(z, ast.Name) and z.id == "OFFLINE_PARALLEL_CALL" for z in knoten.targets
        ):
            return ast.literal_eval(knoten.value)
    raise AssertionError("OFFLINE_PARALLEL_CALL fehlt im Gate -- keine parallele Form (#3278)")


def test_ac7_serielle_form_frei_und_andere_n_formen_bleiben_gesperrt():
    """AC-7 (praezisiert durch #3278): die serielle Offline-Form bleibt frei,
    das parallele Literal ist die EINZIGE freie ``-n``-Form.

    Ohne das Plugin agent-os-openspec (CI) bricht das Gate schon beim Import
    ab -- dann uebersprungen wie ``tests/tdd/test_broad_test_run_gate_*.py``."""
    if str(GATE.parent) not in sys.path:
        sys.path.insert(0, str(GATE.parent))
    pytest.importorskip("broad_test_run_gate", exc_type=ImportError)
    seriell = "uv run pytest " + " ".join(OFFLINE_FORM) + " --ignore=tests/red/"
    assert _gate(seriell).returncode == 0, _gate(seriell).stderr
    parallel = _paralleles_literal()
    assert _gate(parallel).returncode == 0, _gate(parallel).stderr
    for andere in (seriell + " -n 4", seriell + " -n 2 --dist loadgroup",
                   parallel.replace("-n 2", "-n 4"), parallel + " -n 4"):
        proc = _gate(andere)
        assert proc.returncode == 2, f"Gate laesst eine andere -n-Form durch: {andere}"
        assert "BLOCKED" in proc.stderr


# ---------------------------------------------------------------------------
# #3278 AC-3: Pflichtflags des parallelen Literals
# ---------------------------------------------------------------------------

PARALLEL_PRAEFIX = ["nice", "-n", "10", "uv", "run", "pytest"]
PFLICHTFLAGS = (
    ("-n", "2"),
    ("--dist", "loadgroup"),
    ("--disable-socket",),
    ("--allow-unix-socket",),
    ("--allow-hosts=127.0.0.1,::1,localhost",),
    ("--loopback-own-ports",),
    ("--ignore=tests/red/",),
)


def _literal_maengel(literal: str) -> list[str]:
    """Abweichungen von Praefix und Pflichtflags (leer = in Ordnung): jedes
    Pflichtflag genau einmal, nichts Zusaetzliches."""
    worte = shlex.split(literal)
    rest = worte[len(PARALLEL_PRAEFIX):]
    maengel = [] if worte[:len(PARALLEL_PRAEFIX)] == PARALLEL_PRAEFIX else [f"Praefix: {worte[:6]}"]
    for flag in PFLICHTFLAGS:
        stellen = [i for i in range(len(rest)) if tuple(rest[i:i + len(flag)]) == flag]
        if len(stellen) != 1:
            maengel.append(f"{' '.join(flag)}: {len(stellen)}x")
            continue
        del rest[stellen[0]:stellen[0] + len(flag)]
    return maengel + ([f"zusaetzlich: {rest}"] if rest else [])


def test_3278_ac3_paralleles_literal_traegt_alle_pflichtflags():
    assert _literal_maengel(_paralleles_literal()) == []


@pytest.mark.parametrize("flag", PFLICHTFLAGS, ids=lambda f: f[0].split("=")[0].strip("-"))
@pytest.mark.parametrize("art", ["fehlt", "tippfehler", "doppelt"])
def test_3278_ac3_verfaelschtes_literal_faellt_auf(flag, art):
    """Gegenprobe: dieselbe Pruefung erkennt jede Verfaelschung je Pflichtflag."""
    teil = " " + " ".join(flag)
    vorn, hinten = _paralleles_literal().rsplit(teil, 1)
    ersatz = {"fehlt": "", "tippfehler": f"{teil[:-1]}x", "doppelt": teil * 2}[art]
    maengel = _literal_maengel(vorn + ersatz + hinten)
    assert any(m.startswith(teil.strip()) for m in maengel), maengel


# ---------------------------------------------------------------------------
# #3278 AC-4: Netzsperren in beiden Workern, an der WOERTLICHEN Form
# ---------------------------------------------------------------------------

NETZ_SOLL = {"ac6_egress": "blockiert", "ac6_fremd": "blockiert", "ac6_eigen": "erlaubt"}


def _form_argumente() -> list[str]:
    worte = shlex.split(_paralleles_literal())
    assert worte[:len(PARALLEL_PRAEFIX)] == PARALLEL_PRAEFIX, worte
    return worte[len(PARALLEL_PRAEFIX):]


def _netz_befunde(protokoll: list[dict]) -> list[str]:
    """Verstoesse: Pruefung fehlt in einem der zwei Worker oder Ergebnis falsch."""
    befunde = []
    for art, soll in NETZ_SOLL.items():
        eintraege = [e for e in protokoll if e["art"] == art]
        worker = {e["worker"] for e in eintraege}
        if worker != {"gw0", "gw1"}:
            befunde.append(f"{art}: nur in {sorted(worker)} gelaufen")
        befunde += [
            f"{art}: {e['worker']} meldet {e['ergebnis']} statt {soll}"
            for e in eintraege if e["ergebnis"] != soll
        ]
    return befunde


def _lauf_der_form(probe_dir: Path, argumente: list[str]) -> subprocess.CompletedProcess:
    return _innerer_lauf(
        _sonden("probe_netz_barriere.py"), probe_dir, argumente, projekt_addopts=True,
    )


def test_3278_ac4_woertliche_form_sperrt_netz_in_beiden_workern(probe_dir):
    proc = _lauf_der_form(probe_dir, _form_argumente())
    assert proc.returncode == 0, _ausgabe(proc)
    protokoll = _protokoll(probe_dir)
    assert _netz_befunde(protokoll) == [], _ausgabe(proc)
    # Die Auswertung selbst darf einen einzelnen Worker nicht durchwinken.
    for art in NETZ_SOLL:
        einseitig = [e for e in protokoll if e["art"] != art or e["worker"] == "gw0"]
        assert _netz_befunde(einseitig) == [f"{art}: nur in ['gw0'] gelaufen"]


def test_3278_ac4_gegenprobe_ein_worker_laeuft_in_die_barriere(probe_dir):
    argumente = _form_argumente()
    argumente[argumente.index("-n") + 1] = "1"
    proc = _lauf_der_form(probe_dir, argumente)
    assert proc.returncode == 1, _ausgabe(proc)
    assert "Barriere abgelaufen" in proc.stdout, _ausgabe(proc)
    assert _netz_befunde(_protokoll(probe_dir)), "Auswertung winkt einen Worker durch"


def test_3278_ac4_gegenprobe_ohne_port_guard_faellt_die_auswertung_durch(probe_dir):
    argumente = [a for a in _form_argumente() if a != "--loopback-own-ports"]
    proc = _lauf_der_form(probe_dir, argumente)
    befunde = _netz_befunde(_protokoll(probe_dir))
    assert len(befunde) == 2 and all(b.startswith("ac6_fremd: gw") for b in befunde), (
        f"{befunde}\n" + _ausgabe(proc)
    )


# ---------------------------------------------------------------------------
# AC-8: test_bug305_mobile_email.py ohne feste /tmp-Namen, parallel gruen
# ---------------------------------------------------------------------------

BUG305 = REPO_ROOT / "tests" / "tdd" / "test_bug305_mobile_email.py"
FESTE_TMP_NAMEN = (
    Path("/tmp/bug305_mobile_375px_ist.png"),
    Path("/tmp/bug305v2_mobile_375px.png"),
)


def _zustand(p: Path):
    try:
        st = p.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def test_ac8_bug305_parallel_ohne_feste_tmp_pfade(probe_dir):
    """AC-8: die Datei laeuft zweimal gleichzeitig (``-n 2 --dist each``)
    gruen und schreibt dabei KEINE Datei unter festen ``/tmp``-Namen -- die
    Bildschirmfotos gehoeren in ``tmp_path`` (je Test, je Worker eigen)."""
    vorher = {p: _zustand(p) for p in FESTE_TMP_NAMEN}
    proc = _innerer_lauf([str(BUG305)], probe_dir, ["-n", "2", "--dist", "each"])
    _xdist_lief_mit_zwei_workern(proc)
    assert proc.returncode == 0, _ausgabe(proc)
    zusammenfassung = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    assert "passed" in zusammenfassung and "skipped" not in zusammenfassung, (
        "bug305 lief nicht vollstaendig (uebersprungen?) -- Nachweis leer\n" + _ausgabe(proc)
    )
    nachher = {p: _zustand(p) for p in FESTE_TMP_NAMEN}
    veraendert = [str(p) for p in FESTE_TMP_NAMEN if vorher[p] != nachher[p]]
    assert not veraendert, (
        f"test_bug305_mobile_email.py schreibt weiter feste /tmp-Pfade: {veraendert}"
    )


def _wurzel_conftest(config):
    """Das tatsaechlich geladene ``tests/conftest.py``-Modul (kein Neuimport:
    nur dessen Modulvariablen bestimmen, welche Journale gelesen werden)."""
    ziel = (REPO_ROOT / "tests" / "conftest.py").resolve()
    for plugin in config.pluginmanager.get_plugins():
        datei = getattr(plugin, "__file__", None)
        if datei and Path(datei).resolve() == ziel:
            return plugin
    raise AssertionError("tests/conftest.py ist nicht als Plugin geladen")


def test_f008_journal_erklaert_ignoriert_fremdlauf_eintraege(request, tmp_path, monkeypatch):
    """F008: ein ``fremdlauf``-Eintrag (Form wie ``_melde_fremdlauf``, ohne
    ``pfad``) im Journal darf den Beobachter nicht mit KeyError abbrechen und
    nichts erklaeren -- erklaert wird nur der ``datei``-Pfad."""
    conftest = _wurzel_conftest(request.config)
    jetzt = conftest._echte_uhr()
    fremde_pid = os.getpid() + 100000
    journal = tmp_path / "journal.jsonl"
    journal.write_text(
        json.dumps({"t": jetzt, "quelle": fremde_pid, "art": "fremdlauf",
                    "ziel": os.getpid(), "test": "tests/x.py::test_y"}) + "\n"
        + json.dumps({"t": jetzt, "quelle": fremde_pid, "art": "datei",
                      "pfad": "default/trips/a.json"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(conftest, "_EIGENES_JOURNAL", journal)
    monkeypatch.setattr(conftest, "_GEERBTE_BEOBACHTUNG", [])
    monkeypatch.setattr(conftest, "_GEERBTE_JOURNALE", [])
    assert conftest._erklaerende_journale() == [str(journal)]

    dateien, baeume = conftest._journal_erklaert(jetzt)

    assert dateien == {"default/trips/a.json"}
    assert baeume == []
