"""
TDD RED — Attestation-Findings: gemeinsamer Typkontrakt (hart schreiben, weich lesen).

Spec: docs/specs/modules/fix_1689_attestation_findings_typkontrakt.md (AC-1..AC-10)
Kontext: #1653, #1677, #1689 — sobald der Pruef-Agent statt einer JSON-**Liste**
ein JSON-**Objekt** an `--findings-json` uebergibt, iteriert write_verdict()
heute lautlos ueber dessen SCHLUESSEL statt seine Elemente zu pruefen — genau
so entstand die real vorgefundene Fehlform
`.claude/e2e_verified/1001273d00382645824a11c96855a2ed9878fc51.json`:
`"findings": ["issue", "commit", "steps", "cleanup", "skipped", "notes"]`
(exakt die sechs Top-Level-Schluessel eines Findings-Objekts). Auf der
Leseseite laesst genau diese Fehlform prod_selftest.py mit AttributeError
abstuerzen (`_probe_ac` ruft `finding.get(...)` auf einem bloßen String auf).
Eine zweite, unabhaengige Fehlerklasse betrifft das TOP-LEVEL der Attestation
selbst (nicht nur das findings-Array): an drei Stellen wird `.get()` auf einem
geladenen JSON-Wert aufgerufen, ohne zu pruefen, ob ueberhaupt ein Dict
geladen wurde.

Kein Netz (Kern-Schicht):
- Die vier prod_selftest.py-Tests (AC-5/AC-6/AC-7/AC-10) rufen `run_selftest()`
  direkt auf; der Health-Check/die HTTP-Proben laufen ueber einen ehrlichen
  Boundary-Seam (`_http_get` per monkeypatch, Muster
  test_prod_selftest_internal_url_skip.py::_HttpGetRecorder) — der Seam
  spiegelt NIE die zu testende Findings-Logik zurueck, sondern liefert einen
  fest verdrahteten Status.
- Die staging_gate.py-Tests (AC-2/AC-3/AC-4/AC-8/AC-9) laufen als Subprozess
  gegen ein HERMETISCHES Ein-Commit-Git-Repo (Muster
  test_staging_gate.py::_setup_repo). e2e_telegram_live.py wird bewusst NICHT
  mitkopiert: write_verdict() ruft ueber _telegram_live_gate() IMMER einen
  echten `git diff HEAD~1..HEAD` auf (unabhaengig vom --scope-Override); in
  einem Ein-Commit-Repo scheitert HEAD~1, was _telegram_live_gate() ohne
  GZ_TELEGRAM_TEST_CHAT_ID sonst zum Blocken bringen wuerde. Das Fehlen der
  Datei loest denselben fail-soft-Pfad aus, den test_staging_gate.py::_setup_repo
  bereits nutzt (Import-Fehler abgefangen, Gate uebersprungen) — keine
  Netzabhaengigkeit, kein Mock der eigentlich getesteten Logik.

Pfadregel (#1409): Pruefling wird relativ zur Testdatei aufgeloest
(Path(__file__).resolve().parents[2] -> .claude/hooks/...), NIE ueber einen
festen Hauptrepo-Pfad — auch das hermetische Ein-Commit-Repo kopiert seine
.claude/hooks aus genau dieser Worktree-Ablage, kein Bezug zum beweglichen
Hauptrepo.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from tests.tdd.conftest import _init_evidence_free_repo, _load_prod_selftest_module

WORKTREE_DIR = Path(__file__).resolve().parents[2]
HOOKS_DIR = WORKTREE_DIR / ".claude" / "hooks"


# ---------------------------------------------------------------------------
# Gemeinsame Helfer
# ---------------------------------------------------------------------------

def _load_e2e_paths_module():
    """Laedt _e2e_paths.py frisch per importlib aus der Worktree-Kopie
    (Muster test_staging_gate_verdict_merge.py::_load_module)."""
    spec = importlib.util.spec_from_file_location(
        "_e2e_paths_typsicher", str(HOOKS_DIR / "_e2e_paths.py")
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_e2e_paths_mod = _load_e2e_paths_module()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _setup_isolated_repo(tmp_path: Path) -> Path:
    """Hermetisches Ein-Commit-Git-Repo mit eigener .claude/hooks-Kopie
    (Muster test_staging_gate.py::_setup_repo) -- isoliert vom beweglichen
    Hauptrepo. e2e_telegram_live.py wird bewusst NICHT mitkopiert (s.
    Modul-Docstring)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("staging_gate.py", "prod_selftest.py", "_e2e_paths.py"):
        shutil.copy(HOOKS_DIR / name, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _repo_head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout.strip()


def _run_gate_in(repo: Path, args: list[str]) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["GZ_ACTIVE_WORKFLOW"] = "fix-1689-attestation-robustheit"
    result = subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py")] + args,
        capture_output=True, text=True, cwd=str(repo), env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _add_commit(root: Path, relpath: str, content: str, message: str) -> str:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=root, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()


class _HealthOkRecorder:
    """Ehrlicher Boundary-Seam an der Netzgrenze (Muster
    test_prod_selftest_internal_url_skip.py::_HttpGetRecorder): liefert IMMER
    einen erfolgreichen Health-Check und einen generischen 200 fuer jede
    andere geprobte URL -- fest verdrahtet, spiegelt NIE die
    Findings-Partitionierung zurueck."""

    def __init__(self, mod):
        self._health_url = mod.HEALTH_URL
        self.calls: list[str] = []

    def __call__(self, url: str, follow_redirects: bool = False):
        self.calls.append(url)
        if url == self._health_url:
            return 200, b'{"status": "ok"}', ""
        return 200, b"", ""


# Reale Fehlform aus .claude/e2e_verified/1001273d00382645824a11c96855a2ed9878fc51.json
REAL_FEHLFORM = ["issue", "commit", "steps", "cleanup", "skipped", "notes"]


# ---------------------------------------------------------------------------
# AC-1: _e2e_paths.partition_findings() — reine Funktion, kein Netz, kein Seam
# ---------------------------------------------------------------------------

def test_partition_findings_splits_dicts_and_non_dicts():
    """AC-1: gemischte Liste aus Dict- und Nicht-Dict-Eintraegen rein, korrekt
    getrenntes Tupel (gueltige, unverwertbare) raus, jeweils in Reihenfolge."""
    dict_a = {"ac": "AC-1", "status": "PASS"}
    dict_b = {"ac": "AC-2", "status": "PASS"}
    raw = [dict_a, "issue", 42, dict_b, None, "commit"]

    gueltige, unverwertbare = _e2e_paths_mod.partition_findings(raw)

    assert gueltige == [dict_a, dict_b], (
        f"gueltige soll ausschliesslich die Dict-Eintraege in Reihenfolge enthalten: {gueltige}"
    )
    assert unverwertbare == ["issue", 42, None, "commit"], (
        f"unverwertbare soll ausschliesslich die Nicht-Dict-Eintraege in Reihenfolge enthalten: {unverwertbare}"
    )


def test_partition_findings_non_list_root_is_fully_unusable():
    """AC-1 (Ergaenzung): raw selbst ist keine Liste (ein JSON-Objekt) ->
    gueltige ist leer, unverwertbare traegt den gesamten Wert."""
    raw = {
        "issue": "#1653",
        "commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "steps": "1) Playwright-Lauf 2) Screenshots",
        "cleanup": "keine",
        "skipped": "keine",
        "notes": "Objekt statt Liste",
    }

    gueltige, unverwertbare = _e2e_paths_mod.partition_findings(raw)

    assert gueltige == [], f"Bei Nicht-Listen-Root darf 'gueltige' nicht befuellt sein: {gueltige}"
    assert unverwertbare == [raw], (
        f"Bei Nicht-Listen-Root soll 'unverwertbare' den Rohwert als einzigen Eintrag tragen: {unverwertbare}"
    )


# ---------------------------------------------------------------------------
# AC-2/AC-3: staging_gate.py write_verdict — Eingangspruefung Findings-JSON
# ---------------------------------------------------------------------------

def test_write_verdict_rejects_object_instead_of_list(tmp_path):
    """AC-2: --findings-json zeigt auf ein JSON-OBJEKT statt einer Liste (der
    reale Ausloeser von #1653/#1677) -> Exit != 0, KEIN Artefakt geschrieben,
    Meldung nennt den vorgefundenen Typ 'dict'."""
    repo = _setup_isolated_repo(tmp_path)
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps({
        "issue": "#1653",
        "commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "steps": "1) Playwright-Lauf 2) Screenshots",
        "cleanup": "keine",
        "skipped": "keine",
        "notes": "Objekt statt Liste an --findings-json uebergeben (echte Ursache von #1653/#1677)",
    }))
    out_path = tmp_path / "e2e_verified.json"

    rc, out, err = _run_gate_in(repo, [
        "--write-verdict", "VERIFIED: sollte abgelehnt werden",
        "--findings-json", str(findings_path),
        "--e2e-path", str(out_path),
        "--scope=backend",
    ])

    combined = out + err
    assert rc != 0, f"JSON-Objekt statt Liste muss Exit != 0 liefern, bekam {rc}.\n{combined}"
    assert not out_path.exists(), (
        f"Trotz Objekt statt Liste wurde eine Attestation geschrieben: {out_path}"
    )
    # F001-Haertung (Adversary): ein unbehandelter Absturz darf NIE als
    # kontrollierte Meldung durchgehen. Ohne diese Zeile erfuellt bereits der
    # Substring 'dict' aus der Traceback-Zeile 'return write_verdict(...)'
    # (aus main()) die naechste Assertion, obwohl gar keine echte
    # Typ-Meldung vorliegt -- z.B. wenn nur die isinstance(list)-Pruefung
    # entfernt wird, aber die nachgelagerte partition_findings-Auswertung
    # (die eine Liste voraussetzt) an einem Nicht-Listen-Wert mit
    # KeyError/TypeError abstuerzt.
    assert "Traceback" not in err, (
        f"write_verdict ist mit einem unbehandelten Python-Traceback abgestuerzt "
        f"statt kontrolliert mit einer eigenen Typ-Meldung abzulehnen:\n{err}"
    )
    assert "dict" in combined.lower(), (
        f"Meldung soll den vorgefundenen Typ 'dict' nennen, bekam: {combined}"
    )
    assert "muss eine json-liste sein" in combined.lower(), (
        f"Meldung soll die echte Typkontrakt-Meldung enthalten (nicht nur "
        f"zufaellig 'dict' aus einer Traceback-Zeile), bekam: {combined}"
    )


def test_write_verdict_rejects_list_with_bare_string_entries(tmp_path):
    """AC-3: --findings-json ist eine Liste mit Nicht-Dict-Elementen (die
    reale Fehlform, sechs Bare-Strings) -> Exit != 0, KEIN Artefakt
    geschrieben, Meldung weist auf unverwertbare Elemente hin."""
    repo = _setup_isolated_repo(tmp_path)
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps(REAL_FEHLFORM))
    out_path = tmp_path / "e2e_verified.json"

    rc, out, err = _run_gate_in(repo, [
        "--write-verdict", "VERIFIED: sollte abgelehnt werden",
        "--findings-json", str(findings_path),
        "--e2e-path", str(out_path),
        "--scope=backend",
    ])

    combined = out + err
    assert rc != 0, f"Liste mit Bare-String-Elementen muss Exit != 0 liefern, bekam {rc}.\n{combined}"
    assert not out_path.exists(), (
        f"Trotz Bare-String-Elementen wurde eine Attestation geschrieben: {out_path}"
    )
    assert any(kw in combined.lower() for kw in ["unverwertbar", "kein dict", "nicht dict", "index"]), (
        f"Meldung soll auf unverwertbare Listenelemente hinweisen, bekam: {combined}"
    )


# ---------------------------------------------------------------------------
# AC-4: staging_gate.py write_verdict — Merge-Bereinigung von Findings-Altlast
# ---------------------------------------------------------------------------

def test_write_verdict_merge_drops_non_dict_legacy_entries(tmp_path):
    """AC-4: eine bestehende Attestation fuer denselben verified_commit
    traegt bereits Nicht-Dict-Altlasten im findings-Array (reale Fehlform);
    ein weiterer regulaerer --write-verdict mit sauberen Findings muss diese
    Altlast beim Merge entfernen und die Anzahl auf stderr melden."""
    repo = _setup_isolated_repo(tmp_path)
    head = _repo_head_sha(repo)
    e2e_path = tmp_path / "e2e_verified.json"
    e2e_path.write_text(json.dumps({
        "verified_commit": head,
        "staging_verdict": "VERIFIED: Altlast (reale Fehlform #1653/#1677)",
        "findings": list(REAL_FEHLFORM),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "backend",
        "environment": "staging",
    }, indent=2))

    clean_finding = {
        "ac": "AC-1",
        "status": "PASS",
        "url": "https://staging.gregor20.henemm.com/trips:AC-1",
        "evidence": "sauberer Folge-Lauf",
    }
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps([clean_finding]))

    rc, out, err = _run_gate_in(repo, [
        "--write-verdict", "VERIFIED: sauberer Folge-Lauf",
        "--findings-json", str(findings_path),
        "--e2e-path", str(e2e_path),
        "--scope=backend",
    ])

    assert rc == 0, (
        f"Regulaerer Folge-Schreibvorgang mit sauberen Findings muss gelingen, "
        f"bekam Exit {rc}.\nstdout: {out}\nstderr: {err}"
    )
    result = json.loads(e2e_path.read_text())
    findings = result.get("findings", [])
    assert all(isinstance(f, dict) for f in findings), (
        f"Nicht-Dict-Altlast wurde beim Merge NICHT entfernt: {findings}"
    )
    assert any(
        f.get("ac") == "AC-1" and f.get("evidence") == "sauberer Folge-Lauf" for f in findings
    ), f"Neues sauberes Finding fehlt nach dem Merge: {findings}"
    combined = out + err
    assert any(kw in combined.lower() for kw in ["verworfen", "entfernt", "discard"]), (
        f"Anzahl der verworfenen Altlast-Eintraege soll auf stderr gemeldet werden, bekam: {combined}"
    )


# ---------------------------------------------------------------------------
# AC-8/AC-9: Top-Level-Typkontrakt (Merge-Lesepfad + Gate-Check)
# ---------------------------------------------------------------------------

def test_write_verdict_merge_survives_non_dict_top_level_existing(tmp_path):
    """AC-8: die BESTEHENDE Attestation-Datei fuer denselben verified_commit
    hat ein valides, aber NICHT-Dict Top-Level-JSON (eine Liste) -> der
    Merge-Lesepfad behandelt dies wie eine kaputte Datei und ueberschreibt
    regulaer -- kein AttributeError, kein Abbruch des Schreibvorgangs."""
    repo = _setup_isolated_repo(tmp_path)
    e2e_path = tmp_path / "e2e_verified.json"
    e2e_path.write_text(json.dumps(["kaputt", "kein", "dict"]))

    clean_finding = {
        "ac": "AC-1",
        "status": "PASS",
        "url": "https://staging.gregor20.henemm.com/trips:AC-1",
        "evidence": "regulaerer Schreibvorgang nach kaputter Bestandsdatei",
    }
    findings_path = tmp_path / "findings.json"
    findings_path.write_text(json.dumps([clean_finding]))

    rc, out, err = _run_gate_in(repo, [
        "--write-verdict", "VERIFIED: ueberschrieben nach kaputtem Bestand",
        "--findings-json", str(findings_path),
        "--e2e-path", str(e2e_path),
        "--scope=backend",
    ])

    assert rc == 0, (
        f"Top-Level-Nicht-Dict-Bestandsdatei muss wie eine kaputte Attestation behandelt "
        f"und regulaer ueberschrieben werden, bekam Exit {rc}.\nstdout: {out}\nstderr: {err}"
    )
    result = json.loads(e2e_path.read_text())
    assert isinstance(result, dict), f"Ergebnis muss ein sauberes Dict sein, war: {result!r}"
    assert any(
        f.get("ac") == "AC-1" and f.get("evidence") == clean_finding["evidence"]
        for f in result.get("findings", [])
    ), f"Neues Finding fehlt nach dem Ueberschreiben: {result.get('findings')}"


def test_gate_check_fails_closed_on_non_dict_top_level(tmp_path):
    """AC-9: eine exakt zum Ziel-Commit passende Attestation-Datei hat ein
    valides, aber NICHT-Dict Top-Level-JSON -> `--check` (Exakt-Match-Zweig,
    aufgerufen vom echten Prod-Deploy) blockt FAIL-CLOSED mit einer eigenen
    Meldung -- niemals stilles Durchlassen (Exit 0) UND niemals ein
    unbehandelter Python-Absturz (Traceback), der nur zufaellig denselben
    Exit-Code liefert."""
    repo = _setup_isolated_repo(tmp_path)
    e2e_path = tmp_path / "broken_top_level.json"
    e2e_path.write_text(json.dumps(["not", "a", "dict"]))

    rc, out, err = _run_gate_in(repo, ["--check", f"--e2e-path={e2e_path}", "--scope=backend"])

    combined = out + err
    assert rc != 0, f"Erwartet Exit != 0 bei Top-Level-Nicht-Dict, bekam {rc}.\n{combined}"
    assert "Traceback" not in err, (
        "gate_check ist mit einem unbehandelten Python-Traceback abgestuerzt statt "
        f"kontrolliert fail-closed mit einer eigenen Meldung zu blocken:\n{err}"
    )
    assert any(kw in combined.lower() for kw in ["list", "kein dict", "nicht dict", "typ"]), (
        f"Meldung soll den vorgefundenen Typ nennen, bekam: {combined}"
    )


# ---------------------------------------------------------------------------
# AC-5/AC-6/AC-7: prod_selftest.py — Findings-Partitionierung vor pool.map
# ---------------------------------------------------------------------------

def test_prod_selftest_survives_mixed_findings_without_crash(tmp_path, monkeypatch):
    """AC-5: das findings-Array einer Attestation mischt gueltige Dict-
    Findings mit unverwertbaren Nicht-Dict-Eintraegen -> kein AttributeError/
    TypeError, die unverwertbaren Eintraege erscheinen als eigener sichtbarer
    Abschnitt im Bericht, das Verdict richtet sich ausschliesslich nach den
    gueltigen Findings."""
    mod = _load_prod_selftest_module()
    root = tmp_path / "repo"
    head = _init_evidence_free_repo(root)
    monkeypatch.setattr(mod, "REPO_DIR", root)
    recorder = _HealthOkRecorder(mod)
    monkeypatch.setattr(mod, "_http_get", recorder)

    valid_finding = {
        "ac": "AC-1",
        "status": "PASS",
        "url": "https://staging.gregor20.henemm.com/trips:AC-1",
        "evidence": "gueltiges Finding",
    }
    mixed_findings = [valid_finding, "issue", 42, None]
    e2e_path = tmp_path / "e2e_verified.json"
    e2e_path.write_text(json.dumps({
        "verified_commit": head,
        "staging_verdict": "VERIFIED: gemischte Findings",
        "findings": mixed_findings,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "backend",
        "environment": "staging",
    }))

    workflow_name = "fix-1689-ac5-mixed-findings"
    report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

    rc = mod.run_selftest(e2e_path, workflow_name, scope="backend", explicit_path=True)

    assert rc == 0, f"Erwartet Exit 0 (einziges gueltiges Finding PASS), bekam {rc}"
    assert report_path.exists(), "Bericht wurde nicht geschrieben"
    content = report_path.read_text()
    assert "unverwertbar" in content.lower(), (
        f"Bericht muss einen sichtbaren Abschnitt fuer unverwertbare Findings enthalten:\n{content}"
    )
    assert "AC-1" in content, f"Gueltiges Finding fehlt im Bericht:\n{content}"


def test_prod_selftest_survives_non_list_findings_field(tmp_path, monkeypatch):
    """AC-6: das findings-Feld selbst ist gar keine Liste (ein JSON-Objekt)
    -> kein Absturz, das gesamte Feld wird als unverwertbar behandelt und im
    Bericht entsprechend ausgewiesen."""
    mod = _load_prod_selftest_module()
    root = tmp_path / "repo"
    head = _init_evidence_free_repo(root)
    monkeypatch.setattr(mod, "REPO_DIR", root)
    recorder = _HealthOkRecorder(mod)
    monkeypatch.setattr(mod, "_http_get", recorder)

    e2e_path = tmp_path / "e2e_verified.json"
    e2e_path.write_text(json.dumps({
        "verified_commit": head,
        "staging_verdict": "VERIFIED: findings ist ein Objekt statt einer Liste",
        "findings": {"issue": "#1653", "commit": "deadbeef"},
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "backend",
        "environment": "staging",
    }))

    workflow_name = "fix-1689-ac6-findings-not-a-list"
    report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

    mod.run_selftest(e2e_path, workflow_name, scope="backend", explicit_path=True)

    assert report_path.exists(), "Bericht wurde trotz Nicht-Listen-findings nicht geschrieben"
    content = report_path.read_text()
    assert "unverwertbar" in content.lower(), (
        f"Ein findings-Feld ohne Listentyp muss vollstaendig als unverwertbar "
        f"ausgewiesen werden:\n{content}"
    )


def test_prod_selftest_all_unusable_findings_is_not_pass(tmp_path, monkeypatch):
    """AC-7 (Kern): das findings-Array besteht AUSSCHLIESSLICH aus
    unverwertbaren Nicht-Dict-Eintraegen (die reale Fehlform). Die Assertion
    laeuft ueber den VOLLSTAENDIGEN Lauf von run_selftest() bis
    _derive_verdict -- nicht ueber einen kuenstlich vorgezogenen Kurzschluss
    -- und prueft das ENDGUELTIGE, tatsaechlich zurueckgegebene Ergebnis
    (Verdict-String + Exit-Code), nicht einen internen Zwischenwert. Ohne die
    neue 'alles unverwertbar => nicht PASS'-Regel wuerde eine nach
    Partitionierung leere Probe-Liste ueber _derive_verdict([]) faelschlich
    PASS liefern (prod_selftest.py:553-556)."""
    mod = _load_prod_selftest_module()
    root = tmp_path / "repo"
    head = _init_evidence_free_repo(root)
    monkeypatch.setattr(mod, "REPO_DIR", root)
    recorder = _HealthOkRecorder(mod)
    monkeypatch.setattr(mod, "_http_get", recorder)

    e2e_path = tmp_path / "e2e_verified.json"
    e2e_path.write_text(json.dumps({
        "verified_commit": head,
        "staging_verdict": "VERIFIED: reale Fehlform #1653/#1677",
        "findings": list(REAL_FEHLFORM),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "backend",
        "environment": "staging",
    }))

    workflow_name = "fix-1689-ac7-all-unusable-not-pass"
    report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

    rc = mod.run_selftest(e2e_path, workflow_name, scope="backend", explicit_path=True)

    assert rc != 0, (
        f"Ausschliesslich unverwertbare Findings duerfen NIE als Erfolg (Exit 0) "
        f"gewertet werden (kein stiller Erfolg fuer einen unbrauchbaren Nachweis), "
        f"bekam Exit {rc}"
    )
    assert report_path.exists(), "Bericht fehlt trotz vollstaendig unverwertbarer Findings"
    content = report_path.read_text()
    match = re.search(r"\*\*Verdict:\s*([A-Za-z_]+)\*\*", content)
    assert match, f"Verdict-Zeile fehlt im Bericht:\n{content}"
    verdict_str = match.group(1)
    assert verdict_str not in ("PASS", "SKIPPED_ALL", "SKIPPED_AUTH_REDIRECT", "SKIPPED_AUTH"), (
        f"Verdict darf bei ausschliesslich unverwertbaren Findings kein Erfolgs-Status sein "
        f"(Kurzschluss ueber _derive_verdict([]) waere PASS gewesen), war: {verdict_str}"
    )


# ---------------------------------------------------------------------------
# AC-10: prod_selftest.py — Top-Level-Guard im Exakt-Match-Zweig
# ---------------------------------------------------------------------------

def test_prod_selftest_falls_back_to_ancestor_on_non_dict_exact_match(tmp_path, monkeypatch):
    """AC-10: die exakt zum HEAD passende Attestation-Datei hat ein valides,
    aber NICHT-Dict Top-Level-JSON -> dies wird wie 'kein exakter Treffer'
    behandelt, sodass die bestehende Ancestor-Suche
    (_e2e_paths._nearest_verified_ancestor) greift statt mit AttributeError
    abzustuerzen. Die Ancestor-Suche selbst (unveraendert) zaehlt den
    Ziel-Commit als ERSTEN Kandidaten mit -- trifft sie dort bereits auf eine
    (wenn auch kaputte) Attestation, bricht sie fail-closed ab (Fix #1382
    Scheibe 2, _e2e_paths.py:344, wird von dieser Spec NICHT angefasst). Das
    erwartbare Ergebnis ist deshalb KEIN AttributeError und eine definierte
    FAIL-Meldung ('kein Nachweis') -- nicht PASS ueber einen gueltigen
    Vorgaenger, der wegen genau dieser Vorrangregel nie erreicht wird."""
    mod = _load_prod_selftest_module()
    root = tmp_path / "repo"
    parent_sha = _init_evidence_free_repo(root)
    monkeypatch.setattr(mod, "REPO_DIR", root)
    recorder = _HealthOkRecorder(mod)
    monkeypatch.setattr(mod, "_http_get", recorder)

    att_dir = root / ".claude" / "e2e_verified"
    att_dir.mkdir(parents=True, exist_ok=True)
    (att_dir / f"{parent_sha}.json").write_text(json.dumps({
        "verified_commit": parent_sha,
        "staging_verdict": "VERIFIED: gueltiger Vorgaenger",
        "findings": [],
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "backend",
        "environment": "staging",
    }))

    head_sha = _add_commit(root, "src/b.py", "b = 2\n", "head mit kaputter Exakt-Attestation")
    (att_dir / f"{head_sha}.json").write_text(json.dumps(["kaputt", "kein", "dict"]))

    workflow_name = "fix-1689-ac10-non-dict-exact-match"
    report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
    e2e_path = mod._commit_e2e_path()

    rc = mod.run_selftest(e2e_path, workflow_name, scope="backend", explicit_path=False)

    assert rc == 1, (
        f"Kaputte Exakt-Attestation muss kontrolliert blocken (Ancestor-Suche greift, "
        f"scheitert aber an ihrer eigenen Vorrangregel fuer den ersten -- kaputten -- "
        f"gefundenen Kandidaten) statt abzustuerzen oder still PASS zu liefern. "
        f"Bekam Exit {rc}."
    )
    assert report_path.exists(), "Bericht fehlt trotz kontrolliertem FAIL"
    content = report_path.read_text()
    assert any(kw in content.lower() for kw in ["kein nachweis", "keine attestation"]), (
        f"Bericht muss erklaeren, dass kein (nutzbarer) Nachweis vorlag:\n{content}"
    )
