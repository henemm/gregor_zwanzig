"""
TDD RED Tests für Issue #603 — Design-Fidelity Gate

Alle Tests MÜSSEN fehlschlagen bis die Implementierung existiert.
Keine Mocks — echtes Verhalten aus Nutzerperspektive.

# doc-compliance-test (AC-4 pyproject-Check)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.tdd.conftest import gh_shim_call_log, gh_shim_path

# #1307: design_fidelity_diff.py macht einen echten Playwright-Login-Versuch
# gegen Staging; unter dem globalen 30s-Test-Timeout (#1210) reissen 4 von 5
# vormals roten Tests rein durch Timeout, nicht durch echten Fehlschlag
# (Direktlauf ohne Timeout-Limit: 10/11 gruen). Datei-lokaler Override.
pytestmark = pytest.mark.timeout(180)

# Issue #1409: Die frühere Einzel-Konstante REPO trug zwei Rollen; sie ist in
# zwei benannte Konstanten aufgeteilt.
#   _REPO_ROOT  = dieser Checkout (Worktree). Trägt den PRÜFLING — geprüft werden
#                 soll die hier bearbeitete Fassung, nicht die unveränderte
#                 Hauptrepo-Kopie (sonst falsches Grün).
#   MAIN_REPO   = Hauptrepo. Trägt Soll-Bilder, Artefakt-Ablage (docs/artifacts)
#                 und ist cwd der Subprozess-Aufrufe: design_fidelity_diff.py löst
#                 seine Datenpfade über Path(".") relativ zum cwd auf (Z. 292-294)
#                 und liest .claude/validator.env von dort — welcher CODE läuft,
#                 entscheidet der Prüfling-Pfad; welche DATEN er sieht, das cwd.
# Muster: test_prod_selftest_564.py:31-43.
_REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_REPO = Path("/home/hem/gregor_zwanzig")

DIFF_TOOL = _REPO_ROOT / ".claude/hooks/design_fidelity_diff.py"
GATE_HOOK = _REPO_ROOT / ".claude/hooks/pre_issue_close_design_gate.py"
# Soll-Bilder folgen bewusst dem cwd des Vergleichs (MAIN_REPO), nicht dem Ort
# dieser Testdatei: der Bildvergleich in design_fidelity_diff.py liest sie über
# Path(".") relativ zum cwd. Worktree-relativ hier hiesse, die Existenz von
# Datei A zu pruefen und anschliessend Datei B zu vergleichen.
SOLL_DIR = MAIN_REPO / "claude-code-handoff/current/soll"
PILOT_SCREEN = "G-compare-uebersicht-kacheln"


def _tool_env(workflow: str) -> dict:
    """AC-14 für die Werkzeug-Läufe: Umgebung selbst gesetzt.

    Der frühere Aufbau `{**os.environ, "GZ_ACTIVE_WORKFLOW": …}` liess die von
    aussen gesetzte OPENSPEC_ACTIVE_WORKFLOW mitlaufen. Seit #1307 Scheibe B
    loest auch das Werkzeug den Ordnernamen aus BEIDEN Schreibweisen auf, mit
    OPENSPEC zuerst (gleiche Reihenfolge wie der Waechter, sonst kehrt der
    Ordner-Bruch aus AC-12 zurueck). Der Test mass damit nicht mehr, was er zu
    messen behauptet: er legte den Ordner A an und das Werkzeug schrieb nach B.
    Beide Schreibweisen deshalb erst raus, dann genau eine gezielt rein.
    """
    env = {k: v for k, v in os.environ.items() if k not in _WORKFLOW_ENV_VARS}
    env["GZ_ACTIVE_WORKFLOW"] = workflow
    return env


class TestAC1DiffToolProducesReport:
    """AC-1: design_fidelity_diff.py erzeugt JSON-Report + Diff-PNG."""

    def test_diff_tool_file_exists(self):
        """
        GIVEN: Issue #603 implementiert
        WHEN: .claude/hooks/design_fidelity_diff.py gesucht wird
        THEN: Datei existiert
        """
        assert DIFF_TOOL.exists(), (
            f"design_fidelity_diff.py nicht gefunden: {DIFF_TOOL}\n"
            "Implementierung fehlt noch (erwartetes RED)"
        )

    @pytest.mark.staging
    def test_diff_tool_exit_code_zero_or_one_only(self):
        """
        GIVEN: Soll-PNG für G-compare-uebersicht-kacheln existiert
        WHEN: design_fidelity_diff.py --screen G-compare-uebersicht-kacheln ausgeführt wird
        THEN: Exit-Code ist 0 (pass) oder 1 (fail) — niemals ein Python-Traceback (Exit 2+)
        """
        # gz-main-path: Soll-Bild, kein Pruefling — muss aus dem cwd des Vergleichs (MAIN_REPO) kommen, s. o. Z. 39-42
        assert SOLL_DIR.joinpath(f"{PILOT_SCREEN}.png").exists(), (
            f"Soll-PNG fehlt: {SOLL_DIR}/{PILOT_SCREEN}.png"
        )
        result = subprocess.run(
            [sys.executable, str(DIFF_TOOL), "--screen", PILOT_SCREEN],
            capture_output=True, text=True, cwd=str(MAIN_REPO)
        )
        assert result.returncode in [0, 1], (
            f"Unerwarteter Exit-Code {result.returncode} — Tool muss 0 (pass) oder 1 (fail) liefern.\n"
            f"stderr: {result.stderr[:500]}"
        )

    @pytest.mark.staging
    def test_diff_tool_produces_json_report(self):
        """
        GIVEN: Tool läuft mit --screen G-compare-uebersicht-kacheln
        WHEN: Ausführung abgeschlossen
        THEN: JSON-Report existiert und enthält diff_pct, passed, screen
        """
        workflow = os.environ.get("GZ_ACTIVE_WORKFLOW", "issue-603-design-fidelity-gate")
        report_dir = MAIN_REPO / "docs/artifacts" / workflow
        report_path = report_dir / f"design-diff-{PILOT_SCREEN}.json"

        # Löschen falls Altlast
        report_path.unlink(missing_ok=True)

        result = subprocess.run(
            [sys.executable, str(DIFF_TOOL), "--screen", PILOT_SCREEN],
            capture_output=True, text=True, cwd=str(MAIN_REPO),
            env=_tool_env(workflow)
        )

        assert report_path.exists(), (
            f"JSON-Report nicht erzeugt: {report_path}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

        report = json.loads(report_path.read_text())
        assert "diff_pct" in report, f"diff_pct fehlt in Report: {report}"
        assert "passed" in report, f"passed fehlt in Report: {report}"
        assert "screen" in report, f"screen fehlt in Report: {report}"
        assert report["screen"] == PILOT_SCREEN

    @pytest.mark.staging
    def test_diff_tool_produces_diff_image(self):
        """
        GIVEN: Tool läuft erfolgreich
        WHEN: Ausführung abgeschlossen
        THEN: Diff-PNG liegt neben dem JSON-Report
        """
        workflow = os.environ.get("GZ_ACTIVE_WORKFLOW", "issue-603-design-fidelity-gate")
        report_dir = MAIN_REPO / "docs/artifacts" / workflow
        diff_png = report_dir / f"design-diff-{PILOT_SCREEN}-diff.png"

        diff_png.unlink(missing_ok=True)

        subprocess.run(
            [sys.executable, str(DIFF_TOOL), "--screen", PILOT_SCREEN],
            capture_output=True, text=True, cwd=str(MAIN_REPO),
            env=_tool_env(workflow)
        )

        assert diff_png.exists(), (
            f"Diff-PNG nicht erzeugt: {diff_png}"
        )
        assert diff_png.stat().st_size > 1000, "Diff-PNG ist leer / zu klein"

    @pytest.mark.staging
    def test_diff_tool_exit_matches_passed_field(self):
        """
        GIVEN: JSON-Report mit passed=true/false
        WHEN: Exit-Code des Tools geprüft
        THEN: Exit 0 ↔ passed=true, Exit 1 ↔ passed=false
        """
        workflow = os.environ.get("GZ_ACTIVE_WORKFLOW", "issue-603-design-fidelity-gate")
        report_dir = MAIN_REPO / "docs/artifacts" / workflow
        report_path = report_dir / f"design-diff-{PILOT_SCREEN}.json"
        report_path.unlink(missing_ok=True)

        result = subprocess.run(
            [sys.executable, str(DIFF_TOOL), "--screen", PILOT_SCREEN],
            capture_output=True, text=True, cwd=str(MAIN_REPO),
            env=_tool_env(workflow)
        )

        assert report_path.exists(), "JSON-Report muss existieren"
        report = json.loads(report_path.read_text())

        if report["passed"]:
            assert result.returncode == 0, f"passed=true aber Exit {result.returncode}"
        else:
            assert result.returncode == 1, f"passed=false aber Exit {result.returncode}"


# ---------------------------------------------------------------------------
# AC-14 (#1307 Scheibe B): Die Gate-Prüfungen setzen ihre Umgebung SELBST.
#
# Der frühere Aufbau `{**os.environ, "GZ_ACTIVE_WORKFLOW": …}` liess die von
# aussen gesetzte OPENSPEC_ACTIVE_WORKFLOW mitlaufen — und die gewinnt im Gate
# (pre_issue_close_design_gate.py:50). Der Test mass damit nicht, was er zu
# messen behauptete: das Gate suchte im Ordner des AKTIVEN Workflows statt in
# dem, den der Test angelegt hatte.
# ---------------------------------------------------------------------------

_WORKFLOW_ENV_VARS = ("OPENSPEC_ACTIVE_WORKFLOW", "GZ_ACTIVE_WORKFLOW")
_GATE_ISSUE = "603"          # trägt das Label design-compliance
_PLAIN_ISSUE = "1"           # trägt es nicht


def _shim_dir(project_dir: Path) -> Path:
    return project_dir / "_bin"


def _gate_env(project_dir: Path, command: str, workflow: str | None,
              var: str = "OPENSPEC_ACTIVE_WORKFLOW") -> dict:
    """Vollständig selbst gesetzte Umgebung für einen Gate-Lauf.

    Beide Schreibweisen der Workflow-Kennung werden zuerst ausdrücklich
    entfernt, damit keine von aussen gesetzte Kennung durchschlägt.
    `CLAUDE_PROJECT_DIR` hält die Artefakt-Ablage im Testverzeichnis (das echte
    Repo bleibt unberührt).

    Ein aufgezeichnetes `gh` liegt an erster PATH-Stelle: das Gate holt die
    Kennzeichen des Issues per `gh issue view` und läuft bei jedem gh-Fehler
    fail-open (Exit 0). Ohne angemeldetes gh — auf dem Bauserver der Normalfall
    — belegten diese Prüfungen deshalb nichts. Echtes Ersatzskript, echter
    Subprozess, kein Mock; Details in tests/tdd/conftest.py.
    """
    env = {k: v for k, v in os.environ.items() if k not in _WORKFLOW_ENV_VARS}
    env["CLAUDE_TOOL_INPUT"] = json.dumps({"command": command})
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    env.setdefault("GH_REPO", "henemm/gregor_zwanzig")
    env["PATH"] = gh_shim_path(_shim_dir(project_dir))
    if workflow:
        env[var] = workflow
    return env


def _run_gate(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE_HOOK)],
        capture_output=True, text=True, env=env, cwd=env["CLAUDE_PROJECT_DIR"],
    )


def _assert_labels_were_fetched(project_dir: Path, issue: str) -> None:
    """Exit 0 ist mehrdeutig: es kann „Nachweis gefunden" heissen oder
    „gh-Aufruf fehlgeschlagen, also fail-open". Das Aufruf-Protokoll des
    Ersatz-`gh` trennt die beiden Fälle."""
    calls = gh_shim_call_log(_shim_dir(project_dir))
    assert any(c.startswith(f"issue view {issue}") for c in calls), (
        "Das Gate hat die Kennzeichen nie abgefragt — ein Exit 0 belegt hier "
        f"nichts. Aufrufe: {calls!r}"
    )


def _artefact_dir(project_dir: Path, workflow: str) -> Path:
    d = project_dir / "docs" / "artifacts" / workflow
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_pass_artefact(project_dir: Path, workflow: str) -> Path:
    path = _artefact_dir(project_dir, workflow) / f"design-diff-{PILOT_SCREEN}.json"
    path.write_text(json.dumps({
        "screen": PILOT_SCREEN,
        "diff_pct": 7.3,
        "passed": True,
        "workflow": workflow,
    }))
    return path


class TestAC2GateBlocksWithoutArtefact:
    """AC-13/AC-14: pre_issue_close_design_gate.py lässt mit Nachweis durch und
    blockiert ohne — in beiden Schreibweisen der Workflow-Kennung."""

    def test_gate_hook_file_exists(self):
        """
        GIVEN: Issue #603 implementiert
        WHEN: .claude/hooks/pre_issue_close_design_gate.py gesucht wird
        THEN: Datei existiert
        """
        assert GATE_HOOK.exists(), (
            f"pre_issue_close_design_gate.py nicht gefunden: {GATE_HOOK}\n"
            "Implementierung fehlt noch (erwartetes RED)"
        )

    def test_gate_blocks_issue_close_without_pass_artefact(self, tmp_path):
        """
        AC-13 (Richtung 1)
        GIVEN: Issue mit Label design-compliance, kein Pass-Artefakt im Workflow
        WHEN: Hook mit 'gh issue close 603' als CLAUDE_TOOL_INPUT aufgerufen
        THEN: Exit-Code 2, und die Meldung benennt, was fehlt
        """
        workflow = "test-1307b-design-gate-blocks"
        _artefact_dir(tmp_path, workflow)  # existiert, aber leer

        env = _gate_env(tmp_path, f"gh issue close {_GATE_ISSUE}", workflow)
        result = _run_gate(env)

        assert result.returncode == 2, (
            f"Gate muss bei fehlendem Pass-Artefakt Exit 2 liefern, "
            f"got Exit {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )
        combined = result.stdout + result.stderr
        assert "design" in combined.lower() and _GATE_ISSUE in combined, (
            "Die Blockade-Meldung muss benennen, um welches Issue es geht und "
            f"welcher Nachweis fehlt. Ausgabe: {combined[:400]!r}"
        )

    def test_gate_allows_close_with_pass_artefact(self, tmp_path):
        """
        AC-13 (Richtung 2)
        GIVEN: Pass-Artefakt mit passed=true im Workflow-Artefaktordner
        WHEN: Hook mit 'gh issue close 603' aufgerufen
        THEN: Exit-Code 0 (erlaubt)
        """
        workflow = "test-1307b-design-gate-allows"
        _write_pass_artefact(tmp_path, workflow)

        env = _gate_env(tmp_path, f"gh issue close {_GATE_ISSUE}", workflow)
        result = _run_gate(env)

        assert result.returncode == 0, (
            f"Gate muss mit Pass-Artefakt Exit 0 liefern, "
            f"got Exit {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )
        _assert_labels_were_fetched(tmp_path, _GATE_ISSUE)

    def test_gate_reads_legacy_workflow_variable(self, tmp_path):
        """
        AC-13/AC-12 (Rückwärtskompatibilität)
        GIVEN: nur die ältere Schreibweise GZ_ACTIVE_WORKFLOW ist gesetzt
        WHEN: das Schliessen eines Design-Issues ohne Nachweis versucht wird
        THEN: das Gate blockiert trotzdem (Exit 2)

        Die Geschwister-Gates akzeptieren beide Schreibweisen
        (prod_send_gate.py:305-309). Dieses Gate liest heute nur
        OPENSPEC_ACTIVE_WORKFLOW und läuft bei der älteren Schreibweise still
        ins Fail-open — es bewacht dann gar nichts.
        """
        workflow = "test-1307b-design-gate-legacy"
        _artefact_dir(tmp_path, workflow)  # leer

        env = _gate_env(tmp_path, f"gh issue close {_GATE_ISSUE}", workflow,
                        var="GZ_ACTIVE_WORKFLOW")
        result = _run_gate(env)

        assert result.returncode == 2, (
            "Gate muss auch bei gesetztem GZ_ACTIVE_WORKFLOW (ohne "
            "OPENSPEC_ACTIVE_WORKFLOW) blockieren, wenn kein Nachweis vorliegt; "
            f"got Exit {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

    def test_gate_reads_legacy_workflow_variable_and_allows_with_artefact(self, tmp_path):
        """AC-12/AC-13: derselbe Fall mit Nachweis — dann lässt das Gate durch.

        Zusammen mit dem vorigen Fall belegt das, dass die ältere Schreibweise
        wirklich AUFGELÖST wird und nicht bloss beide Male fail-open Exit 0
        liefert.
        """
        workflow = "test-1307b-design-gate-legacy-pass"
        _write_pass_artefact(tmp_path, workflow)

        env = _gate_env(tmp_path, f"gh issue close {_GATE_ISSUE}", workflow,
                        var="GZ_ACTIVE_WORKFLOW")
        result = _run_gate(env)

        assert result.returncode == 0, (
            f"Gate muss mit Pass-Artefakt Exit 0 liefern, got Exit {result.returncode}\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )
        _assert_labels_were_fetched(tmp_path, _GATE_ISSUE)

    def test_gate_environment_is_self_set_not_inherited(self, tmp_path, monkeypatch):
        """
        AC-14: Eine von aussen gesetzte Workflow-Kennung darf nicht durchschlagen.

        Aufbau: im Prozess-Environment steht eine FREMDE Kennung, deren Ordner
        einen bestandenen Nachweis enthält. Der Gate-Lauf bekommt eine eigene
        Kennung ohne Nachweis. Läuft die fremde Kennung mit (der alte
        `{**os.environ, …}`-Aufbau), findet das Gate den fremden Nachweis und
        lässt durch — der Test wäre blind.
        """
        poison = "test-1307b-design-gate-poison"
        _write_pass_artefact(tmp_path, poison)
        monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", poison)
        monkeypatch.setenv("GZ_ACTIVE_WORKFLOW", poison)

        workflow = "test-1307b-design-gate-own"
        _artefact_dir(tmp_path, workflow)  # leer

        env = _gate_env(tmp_path, f"gh issue close {_GATE_ISSUE}", workflow)
        assert env.get("OPENSPEC_ACTIVE_WORKFLOW") == workflow
        assert "GZ_ACTIVE_WORKFLOW" not in env
        result = _run_gate(env)

        assert result.returncode == 2, (
            "Gate muss blockieren — der bestandene Nachweis gehört zu einem "
            f"FREMDEN Workflow ({poison}). Exit {result.returncode} bedeutet, dass "
            "die ambient gesetzte Kennung durchgeschlagen ist.\n"
            f"stdout: {result.stdout[:300]}\nstderr: {result.stderr[:300]}"
        )

    def test_gate_ignores_non_design_compliance_issues(self, tmp_path):
        """
        GIVEN: Issue ohne design-compliance Label
        WHEN: Hook mit 'gh issue close 1' aufgerufen (normales Issue)
        THEN: Exit-Code 0 (Gate greift nicht)
        """
        env = _gate_env(tmp_path, f"gh issue close {_PLAIN_ISSUE}",
                        "test-1307b-design-gate-plain")
        result = _run_gate(env)
        assert result.returncode == 0, (
            f"Gate darf normale Issues nicht blockieren, got Exit {result.returncode}\n"
            f"stderr: {result.stderr[:300]}"
        )
        _assert_labels_were_fetched(tmp_path, _PLAIN_ISSUE)


class TestAC4PillowDependency:
    """AC-4: Pillow ist in pyproject.toml und importierbar.
    # doc-compliance-test
    """

    def test_pillow_importable(self):
        """
        GIVEN: Pillow wurde zu pyproject.toml ergänzt und uv sync gelaufen
        WHEN: import PIL ausgeführt
        THEN: Kein ModuleNotFoundError
        """
        try:
            import PIL  # noqa: F401
        except ModuleNotFoundError as e:
            raise AssertionError(
                "Pillow ist nicht installiert — muss in pyproject.toml ergänzt werden.\n"
                f"Fehler: {e}"
            ) from e

    def test_pillow_image_module_available(self):
        """
        GIVEN: Pillow installiert
        WHEN: PIL.Image importiert
        THEN: Image.open und Image.fromarray verfügbar
        """
        from PIL import Image  # noqa: F401
        assert hasattr(Image, "open"), "PIL.Image.open nicht verfügbar"
        assert hasattr(Image, "fromarray"), "PIL.Image.fromarray nicht verfügbar"
