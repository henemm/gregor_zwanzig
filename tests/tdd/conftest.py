"""
TDD Test Fixtures.

Provides ground truth fetcher for TDD tests.
"""

import importlib.util as _importlib_util
import json
import os
import subprocess
import sys
from datetime import date as _date
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# .claude/hooks muss auf sys.path liegen, damit Hooks die importieren
# (z.B. staging_gate, prod_selftest) `import _e2e_paths` auflösen können —
# unabhängig von der Reihenfolge, in der Testdateien geladen werden.
_HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

# tests/ selbst auf sys.path (#1709): test_wanduhr_matrix.py importiert das
# Messwerkzeug als `from helpers.wanduhr_matrix import ...` -- OHNE
# "tests."-Präfix, anders als die übliche Absolut-Importform
# `from tests.helpers.xxx import yyy` (die über pythonpath="." im
# Repo-Root bereits funktioniert). Ohne diesen Eintrag bliebe der Import ein
# ModuleNotFoundError, unabhängig von der Implementierung des Werkzeugs.
_TESTS_DIR = Path(__file__).resolve().parents[1]
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from validation import GroundTruthFetcher

# ---------------------------------------------------------------------------
# prod_selftest.py Testhelfer -- geteilter Ort (Issue #1196 S1 AC-10, PO-
# Korrektur 2026-08-03): verschoben aus test_prod_selftest_564.py, damit
# tests/tdd/test_fix_853_842_837_tooling_gates.py sie importieren kann, ohne
# dass eine Testdatei die andere importiert. test_prod_selftest_564.py holt
# sie von hier zurück (import statt Neudefinition).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
PROD_SELFTEST = _REPO_ROOT / ".claude" / "hooks" / "prod_selftest.py"
# REPO_DIR bleibt bewusst der Hauptrepo-Pfad (Pfadregel #1409: geteilte
# Ablage, HEAD-Ermittlung/Attestation) -- unabhaengig davon, welche
# Dateikopie (Worktree oder Hauptrepo) den Testcode tatsaechlich ausfuehrt.
REPO_DIR = Path("/home/hem/gregor_zwanzig")


# ---------------------------------------------------------------------------
# Zwei-Zonen-Tour -- geteilter Ort (Issue #1727 S5a, Spec-Sektion "Testfixtur")
#
# Gehoben aus tests/tdd/test_drilldown_day_window_local_date.py (#1470).
# Wellington und Vizzavona liegen zwoelf Stunden auseinander: genau die
# Spanne, die den Ortstag-Anker sichtbar macht. Eine dritte Kopie waere
# genau der Fehler, den ADR-0044 fuer die Zonen-Aufloesung selbst verbietet.
# ---------------------------------------------------------------------------

WP_NZ = (-41.3, 174.8)      # Wellington -> Pacific/Auckland, im August UTC+12
WP_KORSIKA = (42.1, 9.0)    # Vizzavona  -> Europe/Paris,     im August UTC+2


def trip_two_zones(
    day0: _date, trip_id: str = "zwei-zonen", trip_name: str = "Zwei-Zonen-Tour",
):
    """Etappe 0 in Neuseeland, ab Etappe 1 auf Korsika (drei Tage ab ``day0``)."""
    from app.trip import Stage, Trip, Waypoint

    coords = [WP_NZ, WP_KORSIKA, WP_KORSIKA]
    return Trip(
        id=trip_id,
        name=trip_name,
        stages=[
            Stage(
                id=f"S{i}", name=f"Etappe {i}", date=day0 + timedelta(days=i),
                waypoints=[
                    Waypoint(id=f"W{i}", name=f"WP{i}", lat=lat, lon=lon,
                             elevation_m=100),
                ],
            )
            for i, (lat, lon) in enumerate(coords)
        ],
    )


# ---------------------------------------------------------------------------
# Vorbedingungs-Anker -- geteilter Ort (Issue #1795, gehoben aus
# tests/tdd/test_befehlspfade_folgen_ortszone.py:100-118, #1727 S5a).
#
# Eine dritte Kopie waere derselbe Regelverstoss, den ADR-0044 fuer die
# Zonen-Aufloesung selbst verbietet -- der Altnutzer importiert ab #1795
# von hier statt einer eigenen Definition.
# ---------------------------------------------------------------------------

def _anker(now_utc: datetime, zone: str, erwarteter_ortstag: _date) -> None:
    """Vorbedingungs-Anker — PFLICHT vor jeder Hauptzusicherung, die einen
    vom Weltzeit-/Servertag abweichenden Ortstag behauptet.

    Belegt, dass Ortstag, Weltzeit-Tag und Servertag bei DIESER Fixtur zu
    DIESEM Zeitpunkt wirklich auseinanderfallen. Ohne ihn koennte die
    Hauptzusicherung strukturell nie fehlschlagen (Fehlerklasse #1726 F002).
    Der Sollwert wird aus der Zone gebildet, nicht aus dem Prueflingsweg.
    """
    ortstag = now_utc.astimezone(ZoneInfo(zone)).date()
    assert ortstag == erwarteter_ortstag, (
        f"Testaufbau: Ortstag in {zone} ist {ortstag}, der Test rechnet mit "
        f"{erwarteter_ortstag} (Zeitpunkt {now_utc.isoformat()})"
    )
    assert ortstag != now_utc.date(), (
        f"Testaufbau nicht diskriminierend: Ortstag ({ortstag}) und "
        f"Weltzeit-Tag ({now_utc.date()}) sind gleich (#1726 F002)"
    )
    assert ortstag != _date.today(), (
        f"Testaufbau nicht diskriminierend: Ortstag ({ortstag}) und Servertag "
        f"date.today() ({_date.today()}) sind gleich (#1726 F002)"
    )


def _load_prod_selftest_module():
    """Laedt prod_selftest.py frisch per importlib (Muster
    test_staging_gate_verdict_merge.py) -- fuer Direktaufrufe ohne
    Subprocess/echten Netzwerk-Rundlauf (Fix 1/Fix 2, #1327/#1228)."""
    spec = _importlib_util.spec_from_file_location(
        "prod_selftest_direct_1327", str(PROD_SELFTEST)
    )
    assert spec is not None and spec.loader is not None
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(REPO_DIR),
    )
    return result.stdout.strip()


def _make_e2e_verified(
    tmp_path,
    verified_commit=None,
    staging_verdict="VERIFIED: 2/2 ACs grün",
    findings=None,
):
    """Schreibt eine e2e_verified.json mit kontrollierten Inhalten."""
    if verified_commit is None:
        verified_commit = _head_sha()
    if findings is None:
        findings = [
            {
                "ac": "AC-1",
                "status": "PASS",
                "url": "https://staging.gregor20.henemm.com/:AC-1",
                "evidence": "Root-Route ok",
            },
            {
                "ac": "AC-2",
                "status": "PASS",
                "url": "https://staging.gregor20.henemm.com/trips/new:AC-2",
                "evidence": "Form-Route ok",
            },
        ]
    data = {
        "verified_commit": verified_commit,
        "staging_verdict": staging_verdict,
        "findings": findings,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "frontend-only",
        "environment": "staging",
    }
    json_file = tmp_path / "e2e_verified.json"
    json_file.write_text(json.dumps(data, indent=2))
    return json_file


def _init_evidence_free_repo(root: Path) -> str:
    """Erzeugt ein isoliertes, echtes Git-Repo OHNE JEDE Attestation.

    Fuer 'kein Nachweis'-Faelle reicht ein Direktaufruf mit explizitem
    ``scope=`` allein NICHT: run_selftest() sucht bei Nicht-Exakt-Treffer
    ueber ``_e2e_paths._nearest_verified_ancestor`` im Git-Verlauf von
    ``REPO_DIR`` nach einem Vorfahren mit gueltiger Attestation. Bliebe
    ``REPO_DIR`` auf dem echten Hauptrepo verdrahtet, faende dieser Scan
    reale, dort tatsaechlich vorhandene Attestationen fuer Vorfahren des
    aktuellen HEAD und der Test wuerde faelschlich PASS liefern -- abhaengig
    vom Zufallszustand des Hauptrepos (genau die vom PO gemeldete
    Fehlerklasse, 2026-07-26). Ein `.gitignore` analog dem echten Projekt
    verhindert zusaetzlich, dass eine versehentlich geschriebene
    Attestations-Datei durch `git add -A` eingecheckt wird.
    """
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=root, check=True)
    (root / ".gitignore").write_text(".claude/e2e_verified/\n.claude/e2e_verified.json\n")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("a = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
    ).stdout.strip()


# ---------------------------------------------------------------------------
# Aufgezeichnetes `gh` als PATH-Shim (#1307 Scheibe B, CI-Rot vom 2026-08-05)
#
# `pre_issue_close_design_gate.py` holt die Kennzeichen eines Issues per
# `gh issue view <N> --json labels` und laeuft bei jedem gh-Fehler bewusst
# fail-open (Exit 0). Auf dem Bauserver gibt es kein angemeldetes gh — dort
# belegten die Waechter-Tests deshalb NICHTS: sie waeren auch dann gruen
# geblieben, wenn der Waechter kaputt ist, sobald das Fail-open zufaellig zum
# erwarteten Ergebnis passt.
#
# Gegenmittel ohne Mock-Theater: ein echtes ausfuehrbares Ersatzskript an
# erster PATH-Stelle, das AUFGEZEICHNETE Antworten liefert (Muster: der
# git-Shim in test_issue_668_head_sha_dedup.py). Echtes Skript, echter
# Subprozess, deterministisch und netzfrei.
# ---------------------------------------------------------------------------

# Abgerufen am 2026-08-05 mit `gh -R henemm/gregor_zwanzig issue view <N>
# --json labels`. #603 traegt design-compliance (der Waechter greift), #1
# traegt gar kein Kennzeichen (der Waechter darf nicht greifen).
RECORDED_ISSUE_LABELS = {
    "603": ["type:rework", "frontend", "design-compliance"],
    "1": [],
}

_GH_SHIM_TEMPLATE = '''#!{python}
"""Aufgezeichnetes `gh` fuer Waechter-Tests — echtes Skript, kein Mock."""
import json
import sys

RECORDED = {recorded}
argv = sys.argv[1:]
with open({log!r}, "a") as fh:
    fh.write(" ".join(argv) + "\\n")
if argv[:2] == ["issue", "view"] and "--json" in argv:
    labels = RECORDED.get(argv[2])
    if labels is None:
        sys.stderr.write("gh-Ersatz: Issue %s ist nicht aufgezeichnet\\n" % argv[2])
        sys.exit(1)
    print(json.dumps({{"labels": [{{"name": n}} for n in labels]}}))
    sys.exit(0)
sys.stderr.write("gh-Ersatz: unerwarteter Aufruf: %r\\n" % (argv,))
sys.exit(1)
'''


def gh_shim_call_log(shim_dir: Path) -> list[str]:
    """Die Aufrufe, die das Ersatz-`gh` tatsaechlich gesehen hat.

    Damit laesst sich pruefen, dass der Waechter die Kennzeichen wirklich
    abgefragt hat — ein leeres Protokoll heisst, er ist vorher ausgestiegen.
    """
    log = shim_dir / "gh-calls.log"
    return log.read_text().splitlines() if log.exists() else []


def install_recorded_gh(shim_dir: Path) -> Path:
    """Legt das Ersatz-`gh` in ``shim_dir`` an und gibt das Verzeichnis zurueck."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "gh"
    shim.write_text(_GH_SHIM_TEMPLATE.format(
        python=sys.executable,
        recorded=repr(RECORDED_ISSUE_LABELS),
        log=str(shim_dir / "gh-calls.log"),
    ))
    shim.chmod(0o755)
    return shim_dir


def gh_shim_path(shim_dir: Path) -> str:
    """PATH-Wert mit dem Ersatz-`gh` an erster Stelle."""
    return f"{install_recorded_gh(shim_dir)}{os.pathsep}{os.environ.get('PATH', '')}"


def pytest_configure(config: pytest.Config) -> None:
    """Skip-Gruende immer in der Kurzfassung zeigen (Issue #1014, AC-1/AC-3):

    project-weites addopts="-q ..." haelt die Verbosity per -v/-q-Saldo auf 0,
    wodurch pytest die skipif-reason nicht inline zeigt. 's' in reportchars
    erzwingt den Eintrag in der "short test summary info" unabhaengig davon.
    """
    if "s" not in config.option.reportchars:
        config.option.reportchars += "s"


@pytest.fixture(scope="session")
def ground_truth() -> GroundTruthFetcher:
    """Ground truth fetcher for TDD tests (cached per session)."""
    return GroundTruthFetcher()


# Issue #638: Clean throttle files for test users before each test run.
# TripAlertService throttle files persist between runs; tdd-638-* users
# are synthetic test users whose throttle must reset each test invocation.
_TDD_638_USERS = ["tdd-638-ac1", "tdd-638-ac2", "tdd-638-ac3", "tdd-638-ac4",
                  "tdd-638-ac5", "tdd-638-userA", "tdd-638-userB",
                  "tdd-638-mixed", "tdd-638-f001", "tdd-638-legacy",
                  "tdd-638-alloff"]


@pytest.fixture(autouse=True)
def _clear_tdd_638_throttle():
    """Auto-reset alert throttle for synthetic #638 test users (runs before each test).

    Issue #1133: resolves the root via ``loader.get_data_dir(uid).parent``
    instead of a hardcoded ``data/users`` path, so the cleanup follows the
    (possibly overridden) data root the tests themselves are isolated to.
    """
    from app import loader

    for uid in _TDD_638_USERS:
        throttle = loader.get_data_dir(uid).parent / uid / "alert_throttle.json"
        if throttle.exists():
            throttle.unlink(missing_ok=True)
    yield
