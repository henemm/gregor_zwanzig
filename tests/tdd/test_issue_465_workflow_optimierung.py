"""TDD RED: Tests für Issue #465 — Workflow-Optimierung: Typen, Auto-Advance, Observability.

Spec: docs/specs/modules/issue_465_workflow_optimierung.md
Test-Manifest: docs/specs/tests/issue_465_workflow_optimierung_tests.md

Hinweis (Rot-Triage #1211b, Batch 1): 7 der ursprünglich 9 Tests wurden
gelöscht — sie prüften `workflow.py`, das inzwischen ins Plugin-Repo
`henemm/agent-os-openspec` migriert wurde (Commits `33da201c`/`465380c1`/
`f1e3acc1`) und unter dem alten Pfad nicht mehr existiert.

Nachtrag (#1409, Lieferung A): Auch `test_ac3_start_type_invalid_exits_with_error`
samt der zugehörigen Pfad-Konstante ist ersatzlos entfallen. Der dort geprüfte
Workflow-Treiber existiert nach der Plugin-Migration unter KEINEM Pfad mehr; der
Test assertete `returncode != 0` und verbuchte damit den Interpreter-Exit 2
(„can't open file") als Erfolg — strukturell falsch grün, der Prüfling lief nie.
Heilbar ist er nicht: Plugin-Code wird hier bewusst nicht geprüft (Präzedenz:
tests/tdd/test_code_gate_allowed_dirs.py:5-11). Verbleibend ist
`test_ac10_email_validator_creates_yaml_log`, das echtes Verhalten prüft.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Issue #1409: Der Pruefling wird repo-relativ aufgeloest, nicht hartkodiert auf
# den Hauptrepo-Pfad — aus einem Worktree pruefte der Test sonst die
# unveraenderte Hauptrepo-Kopie des Validators und meldete falsches Gruen.
# Muster: test_prod_selftest_564.py:40-45, test_staging_gate.py:32-36.
_REPO_ROOT = Path(__file__).resolve().parents[2]
EMAIL_VALIDATOR_PY = _REPO_ROOT / ".claude" / "hooks" / "email_spec_validator.py"


# ---------------------------------------------------------------------------
# AC-10 (smoke): email_spec_validator._write_validation_log erstellt YAML
# ---------------------------------------------------------------------------

def test_ac10_email_validator_creates_yaml_log(tmp_path):
    """AC-10 (smoke): _write_validation_log erstellt YAML in log_dir mit korrekten Feldern.
    Testet die Hilfsfunktion direkt — kein IMAP nötig.
    """
    log_dir = tmp_path / "_log"
    log_dir.mkdir(parents=True)

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "email_spec_validator", str(EMAIL_VALIDATOR_PY)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module._write_validation_log(
        success=True,
        errors=[],
        min_locations=3,
        log_dir=log_dir,
        workflow_id="test-wf",
    )

    yaml_files = list(log_dir.glob("*_email_validation.yaml"))
    assert len(yaml_files) >= 1, (
        f"Kein email_validation.yaml in {log_dir}.\n"
        f"Files: {list(log_dir.iterdir())}"
    )

    data = yaml.safe_load(yaml_files[0].read_text())
    for key in ("validator", "validated_at", "workflow_id", "passed", "error_count", "errors"):
        assert key in data, (
            f"Schlüssel '{key}' fehlt im Validator-Log: {list(data.keys())}"
        )
