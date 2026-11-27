"""Deploy-Stand in der Workflow-Seitenleiste eindeutig (Issue #2873).

Spec: docs/specs/modules/workflow_deploy_status.md (AC-1 bis AC-7).

Prüft aus Sicht dessen, was die Seitenleiste (Plan) und die Endzustandszeile anzeigen:
das echte, installierte Plugin-`workflow.py` läuft per subprocess gegen eine
Temp-Projektkopie mit der ECHTEN `openspec.yaml` dieses Repos. Kein Mock.
Ohne installiertes Plugin (z. B. CI) wird übersprungen (Muster
tests/unit/test_secret_output_gate.py).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
OPENSPEC = REPO / "openspec.yaml"
DEPLOY_CMD = REPO / ".claude" / "commands" / "70-deploy.md"
ISSUE = 4242


def _plugin_workflow_py() -> Path | None:
    try:
        with open(os.path.expanduser("~/.claude/plugins/installed_plugins.json")) as fh:
            daten = json.load(fh)
        for schluessel, eintraege in daten.get("plugins", {}).items():
            if schluessel.startswith("agent-os-openspec@"):
                eintrag = next((e for e in eintraege if e.get("scope") == "user"), eintraege[0])
                pfad = Path(eintrag.get("installPath", "")) / "core" / "hooks" / "workflow.py"
                return pfad if pfad.is_file() else None
    except Exception:
        return None
    return None


WORKFLOW_PY = _plugin_workflow_py()
needs_plugin = pytest.mark.skipif(
    WORKFLOW_PY is None, reason="agent-os-openspec-Plugin nicht installiert (#2873)")


def _projekt(tmp_path: Path, deploy_status: str | None = None) -> Path:
    """Temp-Projekt: echte openspec.yaml + Workflow in Phase 8, Merge fertig."""
    (tmp_path / ".claude" / "workflows").mkdir(parents=True)
    shutil.copy(OPENSPEC, tmp_path / "openspec.yaml")
    state = {"name": "fix-4242-probe", "current_phase": "phase8_complete",
             "workflow_type": "feature", "issue_number": ISSUE,
             "ship_status": "done", "status": "active"}
    if deploy_status:
        state["deploy_status"] = deploy_status
    (tmp_path / ".claude" / "workflows" / "fix-4242-probe.json").write_text(json.dumps(state))
    return tmp_path


def _wf(projekt: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    env.update(CLAUDE_PROJECT_DIR=str(projekt), OPENSPEC_ACTIVE_WORKFLOW="fix-4242-probe")
    r = subprocess.run([sys.executable, str(WORKFLOW_PY), *args], cwd=projekt, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"workflow.py {args} Exit {r.returncode}: {r.stderr[-800:]}"
    return r.stdout


@needs_plugin
def test_ac1_deploy_config_eingerichtet_und_autonom(tmp_path):
    out = _wf(_projekt(tmp_path), "deploy-config")
    assert "DEPLOY_CONFIGURED=yes" in out
    assert "autonomous: true" in out
    assert re.search(r"^command: .*deploy-gregor-prod\.sh", out, re.M), out
    assert re.search(r"^verify: .*prod_selftest\.py", out, re.M), out
    assert re.search(r"^rollback: .*operations_playbook", out, re.M), out


@needs_plugin
def test_ac2_deploy_offen_in_der_leiste(tmp_path):
    plan = _wf(_projekt(tmp_path), "plan")
    assert "▶ Deploy  (offen)" in plan, plan
    assert "nicht eingerichtet" not in plan


@needs_plugin
def test_ac3_endzustand_wartet_auf_claude_statt_po(tmp_path):
    out = _wf(_projekt(tmp_path), "endstate")
    assert "ENDSTATE=waiting" in out, out
    assert f"Claude deployt #{ISSUE}" in out, out
    assert "❗" not in out and "/70-deploy" not in out, out


@needs_plugin
@pytest.mark.parametrize("status,zeile", [
    ("running", "▶ Deploy  (läuft)"),
    ("done", "✔ Deploy"),
    ("failed", "✘ Deploy  (fehlgeschlagen)"),
])
def test_ac4_deploy_status_in_der_leiste(tmp_path, status, zeile):
    projekt = _projekt(tmp_path, status)
    plan = _wf(projekt, "plan")
    assert zeile in plan, plan
    if status == "done":
        end = _wf(projekt, "endstate")
        assert "ENDSTATE=done" in end and "/70-deploy" not in end, end
        assert "deployt" in end, end


def _anleitung() -> str:
    return DEPLOY_CMD.read_text(encoding="utf-8")


def test_ac5_anleitung_setzt_ship_und_deploy_status():  # doc-compliance-test
    text = _anleitung()
    for wert in ("running", "done", "failed"):
        assert re.search(rf"ship-status {wert}\b", text), f"ship-status {wert} fehlt"
        assert re.search(rf"deploy-status {wert}\b", text), f"deploy-status {wert} fehlt"
    assert re.search(r"deploy-status failed[^\n]*--note", text), "failed ohne --note"
    # beide Wege: Server (Selftest 4b) und Nicht-Server (Commit-Status deploy/prod)
    server = text.split("## Schritt 4b", 1)[1].split("## Schritt 5", 1)[0]
    ausserhalb = text.split("### Schritt 4 außerhalb", 1)[1].split("## Schritt 4b", 1)[0]
    for teil, name in ((server, "Server"), (ausserhalb, "Nicht-Server")):
        assert "deploy-status done" in teil, f"{name}-Weg ohne deploy-status done"
        assert "deploy-status failed" in teil, f"{name}-Weg ohne deploy-status failed"
    assert "deploy-status running" in ausserhalb, "Nicht-Server-Weg ohne deploy-status running"


def test_ac6_doku_ausnahme_und_reihenfolge():  # doc-compliance-test
    text = _anleitung()
    assert re.search(r"deploy-status done --note", text), "Doku-Ausnahme ohne Notiz"
    assert "installed_plugins.json" in text, "keine Plugin-Pfadauflösung für workflow.py"
    abschluss = text.split("## Schritt 5", 1)[1]
    assert abschluss.find("deploy-status") != -1, "Abschluss ohne Status"
    assert abschluss.find("deploy-status") < abschluss.find("write-log"), \
        "Status muss vor write-log/finish stehen"


def test_ac7_openspec_bleibt_gueltig_mit_allen_schluesseln():
    daten = yaml.safe_load(OPENSPEC.read_text(encoding="utf-8"))
    vorher = {"project", "workflow", "protected_paths", "always_allowed", "strict_code_gate",
              "specs", "claude_md", "modules", "agents", "spec_validation", "scope_guard",
              "bash_gate", "hooks", "herdr"}
    assert vorher <= set(daten), vorher - set(daten)
    assert isinstance(daten.get("deploy"), dict)
    assert daten["deploy"].get("autonomous") is True


# --- Fix-Loop 1 (#2873): Wirkstellen bewachen (F001-F003) -------------------------

def _abschnitt(text: str, start: str, ende: str) -> str:
    return text.split(start, 1)[1].split(ende, 1)[0]


def _setup_block() -> str:
    setup = _abschnitt(_anleitung(), "## Setup", "\n## ")
    return setup.split("```bash\n", 1)[1].split("```", 1)[0]


@needs_plugin
@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_f001_setup_block_laeuft_in_bash_und_zsh(tmp_path, shell):
    if shutil.which(shell) is None:
        pytest.skip(f"{shell} nicht vorhanden")
    skript = _setup_block() + '\nprintf "%s\\n" "$_H"\nwf deploy-config\n'
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    projekt = _projekt(tmp_path)
    env.update(CLAUDE_PROJECT_DIR=str(projekt), OPENSPEC_ACTIVE_WORKFLOW="fix-4242-probe")
    r = subprocess.run([shell, "-c", skript], cwd=projekt, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"{shell} Exit {r.returncode}: {r.stderr[-800:]}"
    assert r.stdout.splitlines()[0] == str(WORKFLOW_PY.parent), r.stdout
    assert "DEPLOY_CONFIGURED=yes" in r.stdout, r.stdout


def test_f003_status_steht_an_der_richtigen_stelle():  # doc-compliance-test
    text = _anleitung()
    s1 = _abschnitt(text, "## Schritt 1", "## Schritt 2")
    assert -1 < s1.find("ship-status running") < s1.find("git push"), "running nicht vor Push"
    assert -1 < s1.find("gh pr merge") < s1.find("ship-status done"), "done nicht nach Merge"
    s4 = _abschnitt(text, "## Schritt 4 — Prod-Deploy", "### Schritt 4 außerhalb")
    assert -1 < s4.find("deploy-status running") < s4.find("deploy-gregor-prod.sh"), \
        "Server-Weg: running nicht vor dem Deploy-Skript"
    s4b = _abschnitt(text, "## Schritt 4b", "## Schritt 5")
    assert -1 < s4b.find("prod_selftest.py") < s4b.find("deploy-status done"), \
        "done nicht nach dem Selftest"
    staging = _abschnitt(text, "## Schritt 2 + 3", "## Schritt 4")
    assert "deploy-status failed" in staging, "Staging BROKEN ohne deploy-status failed"


def test_f003_failed_mit_note_und_jeder_aufruf_mit_issue_ref():  # doc-compliance-test
    text = _anleitung()
    for zeile in text.splitlines():
        if re.search(r"(ship|deploy)-status failed", zeile):
            assert "--note" in zeile, f"failed ohne --note: {zeile}"
    aufrufe = list(re.finditer(r"\bwf (ship|deploy)-status (\w+)([^`#\n]*)", text))
    assert len(aufrufe) >= 10, [a.group(0) for a in aufrufe]
    for a in aufrufe:  # Ref `<N>` als eigenes Wort, auch hinter `--note "…"`
        assert re.search(r"(^|\s)<N>(\s|$)", a.group(3)), f"ohne Issue-Ref: {a.group(0)}"


@needs_plugin
def test_f002_echte_sequenz_nach_archivierung(tmp_path):
    projekt = _projekt(tmp_path)
    _wf(projekt, "ship-status", "running", str(ISSUE))
    assert "ARCHIVED=" in _wf(projekt, "ship-status", "done", str(ISSUE))
    assert "DEPLOY_STATUS=running" in _wf(projekt, "deploy-status", "running", str(ISSUE))
    assert "DEPLOY_STATUS=done" in _wf(projekt, "deploy-status", "done", str(ISSUE))
    end = _wf(projekt, "endstate", str(ISSUE))
    assert "ENDSTATE=done" in end and "deployt" in end, end


# --- Fix-Loop 2 (#2873): ARCHIVED-Regel in Schritt 5 (F004) -----------------------

def test_f004_abschluss_nur_ohne_archived_write_log_finish():  # doc-compliance-test
    abschluss = _abschnitt(_anleitung(), "## Schritt 5", "## Verboten")
    klein = abschluss.lower()
    assert "archived=" in klein and "entfallen" in klein, abschluss
    assert not re.search(r"(nur mit|bei|wenn)\s+`?archived=", klein), "Regel umgedreht"
    bedingung = klein.find("nur ohne `archived=`")
    assert bedingung != -1, "Bedingung 'Nur ohne ARCHIVED=' fehlt"
    for aufruf in ("wf write-log", "wf finish"):
        assert -1 < bedingung < klein.find(aufruf), f"{aufruf} nicht hinter der Bedingung"


@needs_plugin
def test_f004_write_log_und_finish_scheitern_nach_archivierung(tmp_path):
    """Belegt, warum die Regel noetig ist: nach ARCHIVED= gibt es keinen aktiven Workflow."""
    projekt = _projekt(tmp_path)
    assert "ARCHIVED=" in _wf(projekt, "ship-status", "done", str(ISSUE))
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"}
    env.update(CLAUDE_PROJECT_DIR=str(projekt), OPENSPEC_ACTIVE_WORKFLOW="fix-4242-probe")
    for args in (["write-log", "success"], ["finish"]):
        r = subprocess.run([sys.executable, str(WORKFLOW_PY), *args], cwd=projekt, env=env,
                           capture_output=True, text=True, timeout=120)
        assert r.returncode != 0, f"{args} lief trotz Archivierung: {r.stdout[-400:]}"
