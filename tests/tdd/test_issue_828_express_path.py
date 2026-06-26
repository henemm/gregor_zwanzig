"""TDD RED: Issue #828 — Express-Pfad für Trivial-Issues.

Beweist das Verhalten des neuen `workflow_type=express`:
- Commit ohne Adversary-Verdict erlaubt wenn LoC-Delta ≤ 10
- Commit blockiert wenn LoC-Delta > 10
- Sampling-Counter erzwingt vollen Lauf beim 5. Express-Workflow
- Sampling-Counter reset nach vollständigem Lauf mit VERIFIED
- `workflow.py status` zeigt Express-Zeile

Alle Tests laufen gegen echten Code (keine Mocks, kein Dateiinhalt-Check).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

_THIS_FILE = Path(__file__).resolve()
# tests/tdd/test_...py → parents[2] = Worktree-Root
HOOKS_DIR = _THIS_FILE.parents[2] / ".claude" / "hooks"
WORKFLOW_PY = HOOKS_DIR / "workflow.py"

sys.path.insert(0, str(HOOKS_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_repo(tmp_path: Path) -> Path:
    """Minimales Fake-Repo mit .git + .claude/workflows/_log/ + openspec.yaml."""
    (tmp_path / ".git").mkdir()
    (tmp_path / ".claude" / "workflows" / "_log").mkdir(parents=True)
    (tmp_path / "openspec.yaml").write_text(
        "project:\n  name: test\n"
        "workflow:\n  spec_auto_advance: true\n"
        "protected_paths: []\n"
    )
    return tmp_path


def _run_workflow(args: list[str], tmp_path: Path, session_id: str = "test-828") -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_CODE_SESSION_ID"] = session_id
    for k in ("GZ_ACTIVE_WORKFLOW", "GZ_HOOK_SESSION_ID", "OPENSPEC_ACTIVE_WORKFLOW"):
        env.pop(k, None)
    return subprocess.run(
        [sys.executable, str(WORKFLOW_PY)] + args,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )


def _write_execution_log(tmp_path: Path, name: str) -> None:
    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    log_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    (log_dir / f"{date}_{name}.yaml").write_text(
        f"workflow: {name}\noutcome: success\nat: {datetime.now().isoformat()}\n"
    )


def _write_counter(tmp_path: Path, count: int) -> None:
    """Schreibt den Express-Counter in den Fake-Repo-Baum."""
    counter_path = tmp_path / ".claude" / "workflows" / "_express_counter.json"
    counter_path.write_text(json.dumps({"count": count, "last_full_run": None}))


def _read_counter(tmp_path: Path) -> int:
    counter_path = tmp_path / ".claude" / "workflows" / "_express_counter.json"
    if not counter_path.exists():
        return 0
    return json.loads(counter_path.read_text()).get("count", 0)


def _express_workflow_data(
    name: str,
    verdict: str | None = None,
    sampling_required: bool = False,
    loc_verified: bool = False,
) -> dict:
    """Hilfsfunktion: Workflow-State-Dict für Express-Typ."""
    return {
        "name": name,
        "workflow_type": "express",
        "adversary_verdict": verdict,
        "express_loc_verified": loc_verified,
        "express_sampling_required": sampling_required,
        "phase_transitions": [],
        "phases_completed": [],
        "fix_loop_iterations": 0,
    }


# ---------------------------------------------------------------------------
# AC-1: Express + ≤10 LoC → kein Adversary-Verdict nötig (Gate lässt durch)
# ---------------------------------------------------------------------------

class TestAC1ExpressSmallLocAllowed:
    """AC-1: Express-Workflow + ≤10 LoC → pre_commit_gate erlaubt ohne Verdict."""

    def test_workflow_start_with_express_type_succeeds(self, tmp_path):
        """
        GIVEN: Leeres Repo
        WHEN:  workflow.py start myfeature --type express
        THEN:  Exit-Code 0, workflow_type='express' im State gespeichert
        """
        repo = _setup_repo(tmp_path)
        result = _run_workflow(["start", "myfeature", "--type", "express"], repo, session_id="test-828-ac1")

        assert result.returncode == 0, (
            f"EXPECTED 'workflow.py start --type express' to succeed.\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        wf_file = repo / ".claude" / "workflows" / "myfeature.json"
        assert wf_file.exists(), "Workflow-Datei muss angelegt werden."
        data = json.loads(wf_file.read_text())
        assert data.get("workflow_type") == "express", (
            f"workflow_type muss 'express' sein, war: {data.get('workflow_type')!r}"
        )

    def test_express_commit_gate_allows_without_verdict_small_loc(self):
        """
        GIVEN: Express-Workflow, express_loc_verified=True (≤10 LoC), kein Adversary-Verdict
        WHEN:  _check_express_commit_gate aufgerufen
        THEN:  gibt (True, reason) zurück — Commit erlaubt
        """
        from bash_gate import _check_express_commit_gate  # existiert noch nicht → ImportError

        data = _express_workflow_data("wf-ac1", verdict=None, loc_verified=True)
        allowed, reason = _check_express_commit_gate(data)

        assert allowed is True, (
            f"Express-Commit mit verifiziertem LoC MUSS erlaubt sein.\nReason: {reason}"
        )

    def test_express_commit_gate_does_not_require_phase6b(self):
        """
        GIVEN: Express-Workflow ohne phase6b-Transition (Phasen-Skip), kein Verdict
        WHEN:  _check_express_commit_gate aufgerufen (keine phase6b im State)
        THEN:  gibt (True, ...) zurück — phase6b ist optional für Express
        """
        from bash_gate import _check_express_commit_gate

        data = _express_workflow_data("wf-ac1b", verdict=None, loc_verified=True)
        # Explizit: phase6b_adversary ist NICHT in Transitions (Skip bleibt erhalten)
        assert not any(
            "phase6b" in (t.get("to", "") or "")
            for t in data["phase_transitions"]
        ), "Testvoraussetzung: kein phase6b in Transitions"

        allowed, reason = _check_express_commit_gate(data)
        assert allowed is True, f"Express ohne phase6b darf nicht blocken. Reason: {reason}"


# ---------------------------------------------------------------------------
# AC-2: Express + >10 LoC → Commit blockiert mit Meldung
# ---------------------------------------------------------------------------

class TestAC2ExpressLargeLocBlocked:
    """AC-2: Express-Workflow + >10 LoC → pre_commit_gate blockiert."""

    def test_express_commit_gate_blocks_when_loc_exceeded(self):
        """
        GIVEN: Express-Workflow, express_loc_verified=False (>10 LoC berechnet)
        WHEN:  _check_express_commit_gate aufgerufen mit loc_delta=15
        THEN:  gibt (False, reason) zurück, reason enthält 'LoC-Limit' und Typ-Wechsel-Hinweis
        """
        from bash_gate import _check_express_commit_gate

        data = _express_workflow_data("wf-ac2", verdict=None, loc_verified=False)
        # loc_delta > 10 → Sicherheitsnetz greift
        allowed, reason = _check_express_commit_gate(data, loc_delta=15)

        assert allowed is False, (
            f"Express-Commit mit >10 LoC MUSS blockiert werden.\nReason: {reason}"
        )
        assert "loc" in reason.lower() or "loc-limit" in reason.lower(), (
            f"Reason muss 'LoC-Limit' erwähnen.\nReason: {reason}"
        )

    def test_express_commit_gate_block_message_mentions_type_switch(self):
        """
        GIVEN: Express-Workflow, loc_delta=20 (> Limit)
        WHEN:  _check_express_commit_gate aufgerufen
        THEN:  reason enthält Hinweis auf 'workflow_type feature'
        """
        from bash_gate import _check_express_commit_gate

        data = _express_workflow_data("wf-ac2b", verdict=None, loc_verified=False)
        allowed, reason = _check_express_commit_gate(data, loc_delta=20)

        assert allowed is False
        assert "feature" in reason.lower(), (
            f"Block-Meldung muss den Wechsel auf 'feature' vorschlagen.\nReason: {reason}"
        )

    def test_express_start_creates_skip_transitions_for_phase6b(self, tmp_path):
        """
        GIVEN: Neuer Express-Workflow
        WHEN:  workflow.py start <name> --type express
        THEN:  phase_transitions enthält einen Skip-Eintrag für phase6b_adversary
        """
        repo = _setup_repo(tmp_path)
        result = _run_workflow(["start", "wf-express-skip", "--type", "express"], repo, session_id="test-828-ac2c")

        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"
        wf_file = repo / ".claude" / "workflows" / "wf-express-skip.json"
        data = json.loads(wf_file.read_text())

        # Neues System (v3.4+): kein auto:express_skip in phase_transitions,
        # stattdessen werden express-Felder initialisiert
        assert data.get("express_loc_verified") is False, (
            f"Express-Workflow muss express_loc_verified=False haben.\nState: {data}"
        )
        assert data.get("express_sampling_required") is False, (
            f"Express-Workflow muss express_sampling_required=False haben.\nState: {data}"
        )
        assert data.get("current_phase") == "phase3_spec", (
            f"Express-Workflow muss bei phase3_spec starten.\nPhase: {data.get('current_phase')}"
        )


# ---------------------------------------------------------------------------
# AC-3: 4 abgeschlossene Express → 5. triggert Sampling-Required
# ---------------------------------------------------------------------------

class TestAC3SamplingRequiredOnFifthExpress:
    """AC-3: Jeder 5. Express-Workflow erzwingt vollen Adversary-Lauf."""

    def test_complete_fifth_express_sets_sampling_required(self, tmp_path):
        """
        GIVEN: Express-Counter steht auf 4 (4 vorige Abschlüsse)
        WHEN:  workflow.py complete für 5. Express-Workflow (ohne Verdict)
        THEN:  Counter wird auf 5 erhöht UND express_sampling_required=True gesetzt
               (Workflow wird NICHT archiviert solange Sampling aussteht)
        """
        repo = _setup_repo(tmp_path)
        sid = "test-828-ac3"
        name = "wf-828-sampling"

        # Counter auf 4 vorsetzen
        _write_counter(repo, count=4)

        # Express-Workflow starten (Start muss existieren → scheitert wenn --type express fehlt)
        result = _run_workflow(["start", name, "--type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"Start Express fehlgeschlagen: {result.stderr}"

        _write_execution_log(repo, name)

        # Complete ohne Verdict aufrufen
        result_complete = _run_workflow(["complete", name], repo, session_id=sid)

        # Bei counter=4 → 5. Workflow → Sampling REQUIRED → complete soll blocken (noch kein Verdict)
        assert result_complete.returncode != 0, (
            f"5. Express-Workflow MUSS sampling-required setzen und blockieren.\n"
            f"stdout={result_complete.stdout}\nstderr={result_complete.stderr}"
        )
        # Meldung muss Sampling erwähnen
        output = result_complete.stdout + result_complete.stderr
        assert "sampling" in output.lower(), (
            f"Ausgabe muss 'Sampling' erwähnen.\nOutput: {output}"
        )

    def test_pre_commit_gate_blocks_express_when_sampling_required(self):
        """
        GIVEN: Express-Workflow mit express_sampling_required=True, kein Verdict
        WHEN:  _check_express_commit_gate aufgerufen
        THEN:  gibt (False, reason) zurück — Adversary-Pflicht wie bei feature-Workflow
        """
        from bash_gate import _check_express_commit_gate

        data = _express_workflow_data("wf-ac3-gate", verdict=None, sampling_required=True, loc_verified=True)
        allowed, reason = _check_express_commit_gate(data, loc_delta=5)

        assert allowed is False, (
            f"Express-Commit mit Sampling-Required MUSS blockieren.\nReason: {reason}"
        )
        assert "sampling" in reason.lower() or "adversary" in reason.lower(), (
            f"Block-Meldung muss Sampling oder Adversary erwähnen.\nReason: {reason}"
        )

    def test_status_shows_sampling_required(self, tmp_path):
        """
        GIVEN: Express-Workflow gestartet, express_sampling_required=True im State
        WHEN:  workflow.py status
        THEN:  Ausgabe enthält 'Sampling: REQUIRED'
        """
        repo = _setup_repo(tmp_path)
        sid = "test-828-ac3-status"
        name = "wf-828-sampling-status"

        result = _run_workflow(["start", name, "--type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        # Patch: sampling_required=True direkt in State setzen
        wf_file = repo / ".claude" / "workflows" / f"{name}.json"
        data = json.loads(wf_file.read_text())
        data["express_sampling_required"] = True
        wf_file.write_text(json.dumps(data))

        status_result = _run_workflow(["status"], repo, session_id=sid)
        output = status_result.stdout + status_result.stderr

        assert "sampling" in output.lower() and "required" in output.lower(), (
            f"Status muss 'Sampling: REQUIRED' zeigen.\nOutput: {output}"
        )


# ---------------------------------------------------------------------------
# AC-4: Sampling-Required + VERIFIED → complete → Counter reset auf 0
# ---------------------------------------------------------------------------

class TestAC4SamplingResetAfterFullRun:
    """AC-4: Nach vollem Adversary-Lauf (VERIFIED) wird der Counter zurückgesetzt."""

    def test_complete_with_verified_resets_counter(self, tmp_path):
        """
        GIVEN: Express-Workflow, sampling_required=True, Verdict=VERIFIED, Counter=5
        WHEN:  workflow.py complete
        THEN:  Workflow wird archiviert (Exit 0), Counter reset auf 0
        """
        repo = _setup_repo(tmp_path)
        sid = "test-828-ac4"
        name = "wf-828-ac4-reset"

        # Counter auf 5 (Sampling-Runde)
        _write_counter(repo, count=5)

        result = _run_workflow(["start", name, "--type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        # Patch: sampling_required=True + VERIFIED-Verdict
        wf_file = repo / ".claude" / "workflows" / f"{name}.json"
        data = json.loads(wf_file.read_text())
        data["express_sampling_required"] = True
        data["adversary_verdict"] = "VERIFIED"
        # phase6b in Transitions — Sampling-Runde hat den vollen Lauf gemacht
        data["phase_transitions"].append({
            "from": "phase6_implement",
            "to": "phase6b_adversary",
            "at": datetime.now().isoformat(),
            "trigger": "command",
        })
        wf_file.write_text(json.dumps(data))
        _write_execution_log(repo, name)

        result_complete = _run_workflow(["complete", name], repo, session_id=sid)

        assert result_complete.returncode == 0, (
            f"complete mit VERIFIED-Verdict MUSS erfolgreich sein.\n"
            f"stdout={result_complete.stdout}\nstderr={result_complete.stderr}"
        )

        # Counter muss auf 0 zurückgesetzt sein
        count_after = _read_counter(repo)
        assert count_after == 0, (
            f"Express-Counter muss nach vollem Lauf auf 0 zurückgesetzt werden. War: {count_after}"
        )

        # Workflow muss archiviert sein
        archive = repo / ".claude" / "workflows" / "_archive" / f"{name}.json"
        assert archive.exists(), "Workflow muss nach erfolgreichem complete archiviert werden."

    def test_complete_without_sampling_increments_counter(self, tmp_path):
        """
        GIVEN: Express-Workflow, sampling_required=False, kein Verdict, Counter=2
        WHEN:  workflow.py complete (Express-Pfad, kein Sampling)
        THEN:  Exit 0, Counter auf 3 erhöht
        """
        repo = _setup_repo(tmp_path)
        sid = "test-828-ac4b"
        name = "wf-828-ac4b-increment"

        _write_counter(repo, count=2)

        result = _run_workflow(["start", name, "--type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        # express_loc_verified=True → Commit-Netz bestanden, kein Verdict nötig
        wf_file = repo / ".claude" / "workflows" / f"{name}.json"
        data = json.loads(wf_file.read_text())
        data["express_loc_verified"] = True
        data["express_sampling_required"] = False
        wf_file.write_text(json.dumps(data))
        _write_execution_log(repo, name)

        result_complete = _run_workflow(["complete", name], repo, session_id=sid)

        assert result_complete.returncode == 0, (
            f"Express-complete ohne Sampling MUSS erfolgreich sein.\n"
            f"stdout={result_complete.stdout}\nstderr={result_complete.stderr}"
        )
        count_after = _read_counter(repo)
        assert count_after == 3, (
            f"Counter muss von 2 auf 3 gestiegen sein. War: {count_after}"
        )


# ---------------------------------------------------------------------------
# AC-5: workflow.py status zeigt Express-Zeile
# ---------------------------------------------------------------------------

class TestAC5StatusShowsExpressInfo:
    """AC-5: `workflow.py status` zeigt Express-spezifische Infos."""

    def test_status_shows_express_line(self, tmp_path):
        """
        GIVEN: Express-Workflow gestartet
        WHEN:  workflow.py status
        THEN:  Ausgabe enthält eine 'Express:'-Zeile mit LoC-verified und Sampling-Status
        """
        repo = _setup_repo(tmp_path)
        sid = "test-828-ac5"
        name = "wf-828-ac5-status"

        result = _run_workflow(["start", name, "--type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        status_result = _run_workflow(["status"], repo, session_id=sid)
        output = status_result.stdout + status_result.stderr

        assert "express" in output.lower(), (
            f"Status muss eine 'Express:'-Zeile enthalten.\nOutput: {output}"
        )

    def test_status_shows_loc_verified_false_initially(self, tmp_path):
        """
        GIVEN: Frisch gestarteter Express-Workflow (noch kein Commit)
        WHEN:  workflow.py status
        THEN:  LoC-verified=no (noch nicht verifiziert)
        """
        repo = _setup_repo(tmp_path)
        sid = "test-828-ac5b"
        name = "wf-828-ac5b-loc"

        result = _run_workflow(["start", name, "--type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        status_result = _run_workflow(["status"], repo, session_id=sid)
        output = status_result.stdout + status_result.stderr

        # LoC noch nicht verifiziert (kein Commit gemacht)
        assert "loc" in output.lower(), (
            f"Status muss LoC-verified-Info enthalten.\nOutput: {output}"
        )

    def test_status_shows_sampling_no_initially(self, tmp_path):
        """
        GIVEN: Frisch gestarteter Express-Workflow
        WHEN:  workflow.py status
        THEN:  Sampling=no (kein Sampling erforderlich)
        """
        repo = _setup_repo(tmp_path)
        sid = "test-828-ac5c"
        name = "wf-828-ac5c-sampling"

        result = _run_workflow(["start", name, "--type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        status_result = _run_workflow(["status"], repo, session_id=sid)
        output = status_result.stdout + status_result.stderr

        assert "sampling" in output.lower(), (
            f"Status muss Sampling-Info enthalten.\nOutput: {output}"
        )

class TestF002RetroactiveExpressInitialization:
    """F002 (#828): Nachträglicher Typ-Wechsel feature→express initialisiert Express-Felder."""

    def test_set_field_workflow_type_express_initializes_express_fields(self, tmp_path):
        """Given ein laufender feature-Workflow / When set-field workflow_type express /
        Then sind express_loc_verified und express_sampling_required im State vorhanden."""
        repo = _setup_repo(tmp_path)
        sid = "test-828-f002a"
        name = "wf-828-f002-setfield"

        result = _run_workflow(["start", name, "--type", "feature"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        result = _run_workflow(["set-field", "workflow_type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"set-field fehlgeschlagen: {result.stderr}"

        # State direkt lesen und Express-Felder prüfen
        state_file = repo / ".claude" / "workflows" / f"{name}.json"
        import json
        state = json.loads(state_file.read_text())
        assert "express_loc_verified" in state, (
            "express_loc_verified muss nach Typ-Wechsel initialisiert sein"
        )
        assert "express_sampling_required" in state, (
            "express_sampling_required muss nach Typ-Wechsel initialisiert sein"
        )
        assert state["express_loc_verified"] is False
        assert state["express_sampling_required"] is False

    def test_set_type_express_initializes_express_fields(self, tmp_path):
        """Given ein laufender feature-Workflow / When set-type express /
        Then sind express_loc_verified und express_sampling_required im State vorhanden."""
        repo = _setup_repo(tmp_path)
        sid = "test-828-f002b"
        name = "wf-828-f002-settype"

        result = _run_workflow(["start", name, "--type", "feature"], repo, session_id=sid)
        assert result.returncode == 0, f"Start fehlgeschlagen: {result.stderr}"

        result = _run_workflow(["set-type", "express"], repo, session_id=sid)
        assert result.returncode == 0, f"set-type fehlgeschlagen: {result.stderr}"

        state_file = repo / ".claude" / "workflows" / f"{name}.json"
        import json
        state = json.loads(state_file.read_text())
        assert "express_loc_verified" in state, (
            "express_loc_verified muss nach set-type express initialisiert sein"
        )
        assert state["express_loc_verified"] is False
        assert state["express_sampling_required"] is False

