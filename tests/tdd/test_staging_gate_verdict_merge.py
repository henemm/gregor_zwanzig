"""
TDD RED (#1197): staging_gate.write_verdict — verlustfreier Findings-Merge.

Problem: write_verdict überschreibt die commit-getaggte Attestation
`.claude/e2e_verified/<sha>.json` blind. Zwei Workflows auf demselben HEAD →
die findings des Erstschreibers gehen verloren. Diese Suite fixiert das
gewünschte Merge-Verhalten (AC-1..AC-6 aus
`docs/specs/modules/fix_1197_staging_gate_verdict_merge.md`).

Mock-frei / deterministisch:
- Das Modul wird echt per importlib geladen (Muster wie
  test_issue_668_head_sha_dedup.py) und `write_verdict` direkt aufgerufen.
- Kein Netz: das UNBETEILIGTE Telegram-Live-Gate wird über seinen ehrlichen
  Boundary-Seam (`_telegram_live_gate`) auf No-Op gehalten — wir testen den
  Merge, nicht das Telegram-Gate.
- Keine echte Git-/Scope-Erkennung: `write_verdict` erhält einen expliziten
  `e2e_path` (tmp_path) und `scope_override="backend"`.
- `_head_sha()` liefert den echten Worktree-HEAD; genau dieser reale Wert wird
  für die "bestehende" Attestation verwendet (nicht gemockt).
- Findings sind echte JSON-Dateien; die Ergebnisdatei wird per json.loads
  gelesen und im Verhalten geprüft (kein String-in-Datei-Check).
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"


def _load_module(name: str, path: Path):
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module("staging_gate_verdict_merge", HOOKS_DIR / "staging_gate.py")


# --- Findings (inhaltlich unterscheidbar) --------------------------------
FINDING_A = {
    "ac": "AC-1",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/trips:AC-1",
    "evidence": "Etappen-Button des Erstschreibers gefunden",
}
FINDING_B = {
    "ac": "AC-2",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/compare:AC-2",
    "evidence": "Winner-Box des Zweitschreibers gefunden",
}
FINDING_SHARED = {
    "ac": "AC-3",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/alerts:AC-3",
    "evidence": "gemeinsam geprüftes Finding",
}


@pytest.fixture(autouse=True)
def _no_telegram_gate(monkeypatch):
    """Ehrliche Boundary-Seams UNBETEILIGTER Gates: kein echter Telegram-/Netz-
    und kein Browser-Aufruf während des Merge-Tests. Das Frontend-Browser-Gate
    (#1558) greift beim hier verwendeten Scope 'backend' ohnehin nicht — die
    Neutralisierung hält den Merge-Test aber auch dann frei von fremden
    Nebenwirkungen, wenn ein Fall später mit Frontend-Scope dazukommt."""
    monkeypatch.setattr(mod, "_telegram_live_gate", lambda: 0)
    monkeypatch.setattr(mod, "_frontend_browser_gate", lambda scope, checked=None: 0)


def _write_findings(tmp_path: Path, findings: list) -> Path:
    p = tmp_path / "findings.json"
    p.write_text(json.dumps(findings))
    return p


def _write_existing(e2e_path: Path, verified_commit: str, findings: list,
                    verdict: str = "VERIFIED: Erstschreiber grün") -> None:
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(json.dumps({
        "verified_commit": verified_commit,
        "staging_verdict": verdict,
        "langs": ["de", "en"],
        "findings": findings,
        "verified_at": "2026-07-16T00:00:00+00:00",
        "scope": "backend",
        "environment": "staging",
    }, indent=2))


def _call(verdict: str, findings_path: Path, e2e_path: Path) -> int:
    return mod.write_verdict(
        verdict, findings_path, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    )


def _identifying_parts(f: dict) -> dict:
    """Identifizierende Teile eines Findings (ac/status/url/evidence), OHNE
    das von Fix 3 (#1327/#1228) hinzugefuegte 'workflow'-Feld — fuer
    Vergleiche, die bewusst nur den fachlichen Inhalt pruefen, nicht die
    Workflow-Herkunft."""
    return {k: f.get(k) for k in ("ac", "status", "url", "evidence")}


def _contains_finding(findings: list, expected: dict) -> bool:
    """True wenn `findings` einen Eintrag mit denselben identifizierenden
    Teilen wie `expected` enthaelt (workflow-Tag wird ignoriert)."""
    return any(_identifying_parts(f) == _identifying_parts(expected) for f in findings)


def _count_matching(findings: list, expected: dict) -> int:
    return sum(1 for f in findings if _identifying_parts(f) == _identifying_parts(expected))


def test_ac1_merge_preserves_existing_findings(tmp_path):
    """AC-1: bestehend [A] + neu [B] auf demselben SHA → Ergebnis enthält A und B.

    #1327/#1228 Fix 3: NEU geschriebene Findings tragen zusätzlich ein
    'workflow'-Feld — B wird deshalb über die identifizierenden Teile
    (ac/status/url/evidence) geprüft statt über exakte Dict-Gleichheit. A
    (Altbestand, ohne Tag) bleibt unverändert und wird weiter exakt verglichen
    — die Kernaussage (Erstschreiber-Evidenz geht nicht verloren) ist
    unverändert bewiesen.
    """
    head = mod._head_sha()
    e2e_path = tmp_path / "e2e_verified.json"
    _write_existing(e2e_path, head, [FINDING_A])
    findings_path = _write_findings(tmp_path, [FINDING_B])

    rc = _call("VERIFIED: Zweitschreiber grün", findings_path, e2e_path)

    assert rc == 0
    result = json.loads(e2e_path.read_text())
    assert FINDING_A in result["findings"], (
        "Finding des Erstschreibers ging beim Schreiben verloren (Blind-Overwrite)."
    )
    assert _contains_finding(result["findings"], FINDING_B), "Neues Finding fehlt im Ergebnis."


def test_ac2_merge_deduplicates_shared_finding(tmp_path):
    """AC-2 (#1197, weiterhin gültig unter #1327 Fix 3): bestehend [A, shared]
    + neu [shared, B] → shared genau einmal, Länge 3.

    Der Inhalts-Dedup aus #1197 bleibt aktiv, ignoriert beim Vergleich aber
    das 'workflow'-Tag aus Fix 3 (staging_gate._dedup_key) — ein
    inhaltsgleicher Altbestands-/Fremdeintrag verhindert weiterhin eine
    Zweitfassung, während #1327 AC-3/AC-4 zusätzlich dafür sorgen, dass
    eigene Workflow-Einträge bei Re-Write ersetzt statt dupliziert werden
    (siehe test_ac4_same_workflow_rewrite_replaces_own_keeps_foreign_and_legacy).
    B ist ein genuin neuer Eintrag und trägt deshalb ein 'workflow'-Tag —
    Prüfung über die identifizierenden Teile statt exakter Dict-Gleichheit."""
    head = mod._head_sha()
    e2e_path = tmp_path / "e2e_verified.json"
    _write_existing(e2e_path, head, [FINDING_A, FINDING_SHARED])
    findings_path = _write_findings(tmp_path, [FINDING_SHARED, FINDING_B])

    rc = _call("VERIFIED: gemergt", findings_path, e2e_path)

    assert rc == 0
    result = json.loads(e2e_path.read_text())
    findings = result["findings"]
    shared_count = sum(1 for f in findings if f == FINDING_SHARED)
    assert shared_count == 1, (
        f"Gemeinsames Finding soll genau einmal erscheinen, erschien {shared_count}x: {findings}"
    )
    assert FINDING_A in findings
    assert _contains_finding(findings, FINDING_B), "Neues Finding (B) fehlt im Ergebnis."
    assert len(findings) == 3, f"Erwartet 3 dedup'te Findings, bekam {len(findings)}: {findings}"


def test_ac3_no_existing_file_writes_only_new_findings(tmp_path):
    """AC-3: keine bestehende Datei → nur die neuen Findings (Regressions-Guard).

    #1327/#1228 Fix 3: das einzige geschriebene Finding trägt zusätzlich ein
    'workflow'-Feld — Vergleich über identifizierende Teile statt exakter
    Dict-Gleichheit."""
    e2e_path = tmp_path / "e2e_verified.json"
    assert not e2e_path.exists()
    findings_path = _write_findings(tmp_path, [FINDING_B])

    rc = _call("VERIFIED: erster Lauf", findings_path, e2e_path)

    assert rc == 0
    result = json.loads(e2e_path.read_text())
    findings = result["findings"]
    assert len(findings) == 1 and _contains_finding(findings, FINDING_B), (
        f"Ohne Bestandsdatei nur neue Findings erwartet, bekam: {findings}"
    )


def test_ac4_stale_commit_is_overwritten_not_merged(tmp_path):
    """AC-4: bestehende Datei trägt fremden verified_commit → kein Merge, überschreiben.

    #1327/#1228 Fix 3: das geschriebene Finding trägt zusätzlich ein
    'workflow'-Feld — Vergleich über identifizierende Teile statt exakter
    Dict-Gleichheit."""
    head = mod._head_sha()
    stale = "deadbeef" + head[8:]  # gleich lang, aber != HEAD
    assert stale != head
    e2e_path = tmp_path / "e2e_verified.json"
    _write_existing(e2e_path, stale, [FINDING_A])
    findings_path = _write_findings(tmp_path, [FINDING_B])

    rc = _call("VERIFIED: neuer SHA", findings_path, e2e_path)

    assert rc == 0
    result = json.loads(e2e_path.read_text())
    assert result["verified_commit"] == head
    assert FINDING_A not in result["findings"], (
        "Fremd-Commit-Findings dürfen nicht in die neue Attestation gemischt werden."
    )
    findings = result["findings"]
    assert len(findings) == 1 and _contains_finding(findings, FINDING_B), (
        f"Erwartet nur B (Stale-SHA überschrieben), bekam: {findings}"
    )


def test_ac5_merged_verdict_stays_deploy_gateable(tmp_path):
    """AC-5: nach Merge beginnt staging_verdict mit VERIFIED und verified_commit == HEAD."""
    head = mod._head_sha()
    e2e_path = tmp_path / "e2e_verified.json"
    _write_existing(e2e_path, head, [FINDING_A])
    findings_path = _write_findings(tmp_path, [FINDING_B])

    rc = _call("VERIFIED: gemergt grün", findings_path, e2e_path)

    assert rc == 0
    result = json.loads(e2e_path.read_text())
    assert result["staging_verdict"].startswith("VERIFIED")
    assert result["verified_commit"] == head


def test_ac6_broken_leaves_existing_attestation_untouched(tmp_path):
    """AC-6: BROKEN → Exit 1, bestehende Datei unverändert (kein Merge, kein Overwrite)."""
    head = mod._head_sha()
    e2e_path = tmp_path / "e2e_verified.json"
    _write_existing(e2e_path, head, [FINDING_A],
                    verdict="VERIFIED: Bestand grün")
    before = e2e_path.read_text()
    findings_path = _write_findings(tmp_path, [FINDING_B])

    rc = _call("BROKEN: AC-2 fehlgeschlagen", findings_path, e2e_path)

    assert rc == 1, f"BROKEN muss Exit 1 liefern, bekam {rc}"
    after = json.loads(e2e_path.read_text())
    assert after["findings"] == [FINDING_A], (
        "BROKEN darf die bestehende Attestation nicht verändern."
    )
    assert after["staging_verdict"] == "VERIFIED: Bestand grün"
    assert e2e_path.read_text() == before, "BROKEN-Lauf hat die Bestandsdatei berührt."


# ---------------------------------------------------------------------------
# RED (#1327/#1228 Fix 3, AC-3/AC-4): Findings werden workflow-partitioniert
# statt inhaltsbasiert dedupliziert. Jedes geschriebene Finding traegt ein
# 'workflow'-Feld (aus OPENSPEC_ACTIVE_WORKFLOW). Bei einem Re-Write desselben
# Workflows werden NUR dessen eigene (gleich-getaggte) Findings ersetzt;
# fremde Findings (anderer Workflow ODER kein 'workflow'-Feld = Altbestand)
# bleiben unveraendert erhalten.
# ---------------------------------------------------------------------------

def test_ac3_two_workflows_on_same_sha_keep_both_finding_sets(tmp_path, monkeypatch):
    """AC-3: W1 schreibt F1, danach schreibt W2 auf demselben SHA F2 →
    Ergebnis enthaelt sowohl F1 (workflow=W1) als auch F2 (workflow=W2)."""
    e2e_path = tmp_path / "e2e_verified.json"

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_a = _write_findings(tmp_path, [FINDING_A])
    rc1 = mod.write_verdict(
        "VERIFIED: W1 grün", findings_a, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    )
    assert rc1 == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_b = _write_findings(tmp_path, [FINDING_B])
    rc2 = mod.write_verdict(
        "VERIFIED: W2 grün", findings_b, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    )
    assert rc2 == 0

    result = json.loads(e2e_path.read_text())
    findings = result["findings"]
    w1_entries = [
        f for f in findings
        if f.get("ac") == FINDING_A["ac"] and f.get("workflow") == "workflow-w1"
    ]
    w2_entries = [
        f for f in findings
        if f.get("ac") == FINDING_B["ac"] and f.get("workflow") == "workflow-w2"
    ]
    assert w1_entries, f"F1 (workflow=workflow-w1) fehlt im Ergebnis: {findings}"
    assert w2_entries, f"F2 (workflow=workflow-w2) fehlt im Ergebnis: {findings}"


def test_ac3_written_findings_carry_workflow_field(tmp_path, monkeypatch):
    """AC-3: jedes von write_verdict geschriebene Finding traegt ein
    'workflow'-Feld mit dem Wert von OPENSPEC_ACTIVE_WORKFLOW."""
    e2e_path = tmp_path / "e2e_verified.json"
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_a = _write_findings(tmp_path, [FINDING_A])

    rc = mod.write_verdict(
        "VERIFIED: solo", findings_a, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    )

    assert rc == 0
    result = json.loads(e2e_path.read_text())
    assert result["findings"], "keine Findings geschrieben"
    for f in result["findings"]:
        assert f.get("workflow") == "workflow-w1", (
            f"Finding traegt kein/falsches 'workflow'-Feld: {f}"
        )


def test_ac4_same_workflow_rewrite_replaces_own_keeps_foreign_and_legacy(
    tmp_path, monkeypatch
):
    """AC-4: W1 schreibt F1, W2 schreibt dazwischen F2, W1 schreibt eine
    korrigierte Fassung F1' — Ergebnis: alte F1 (workflow=W1) verschwunden,
    F1' vorhanden, W2-Finding (fremd) weiterhin vorhanden, ein Alt-Finding
    ohne 'workflow'-Feld (Altbestand) bleibt ebenfalls unangetastet."""
    head = mod._head_sha()
    e2e_path = tmp_path / "e2e_verified.json"
    legacy_finding = {
        **FINDING_A,
        "ac": "AC-legacy",
        "evidence": "Altbestand ohne workflow-Tag",
    }
    _write_existing(e2e_path, head, [legacy_finding])

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_f1 = _write_findings(tmp_path, [FINDING_A])
    assert mod.write_verdict(
        "VERIFIED: W1 initial", findings_f1, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_f2 = _write_findings(tmp_path, [FINDING_B])
    assert mod.write_verdict(
        "VERIFIED: W2 dazwischen", findings_f2, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    ) == 0

    finding_a_corrected = {**FINDING_A, "evidence": "korrigierte Fassung"}
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_f1b = _write_findings(tmp_path, [finding_a_corrected])
    assert mod.write_verdict(
        "VERIFIED: W1 Korrektur", findings_f1b, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    ) == 0

    result = json.loads(e2e_path.read_text())
    findings = result["findings"]

    old_a_present = any(
        f.get("ac") == FINDING_A["ac"] and f.get("evidence") == FINDING_A["evidence"]
        for f in findings
    )
    assert not old_a_present, (
        f"alte F1-Fassung (workflow-w1) haette beim Re-Write ersetzt werden "
        f"muessen: {findings}"
    )
    assert any(
        f.get("evidence") == "korrigierte Fassung" and f.get("workflow") == "workflow-w1"
        for f in findings
    ), f"F1' (Korrektur, workflow=workflow-w1) fehlt: {findings}"
    assert any(
        f.get("ac") == FINDING_B["ac"] and f.get("workflow") == "workflow-w2"
        for f in findings
    ), f"W2-Finding (fremd) fehlt nach W1-Korrektur: {findings}"
    assert any(
        f.get("evidence") == "Altbestand ohne workflow-Tag" for f in findings
    ), f"Alt-Finding ohne 'workflow'-Feld ist verloren gegangen: {findings}"


# ---------------------------------------------------------------------------
# Regressions-Schutz fuer Adversary-Fund F002 (#1327/#1228, AC-3/AC-4,
# MEDIUM): der Inhalts-Dedup (staging_gate._content_key) wirkt NUR noch gegen
# taglosen Altbestand. Zwei verschiedene Workflows, die unabhaengig voneinander
# denselben Punkt pruefen und ein INHALTSGLEICHES Finding schreiben, duerfen
# sich NICHT gegenseitig content-dedupliziert wegloeschen -- jeder behaelt
# seinen eigenen, getaggten Eintrag.
# ---------------------------------------------------------------------------

_F002_IDENTICAL_CONTENT = {
    "ac": "AC-1",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/trips:AC-1",
    "evidence": "beide Workflows haben denselben Button unabhängig gefunden",
}


def test_f002_two_workflows_writing_identical_content_finding_both_preserved(
    tmp_path, monkeypatch
):
    """F002: W1 und W2 prüfen unabhängig denselben Punkt und schreiben ein
    inhaltsgleiches Finding (gleiche ac/status/url/evidence) auf demselben
    SHA → beide Einträge bleiben erhalten, je mit eigenem workflow-Tag (kein
    stiller Content-Dedup über getaggte Fremd-Einträge hinweg)."""
    e2e_path = tmp_path / "e2e_verified.json"

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_w1 = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W1", findings_w1, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_w2 = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W2", findings_w2, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    ) == 0

    result = json.loads(e2e_path.read_text())
    findings = result["findings"]
    w1_entries = [f for f in findings if f.get("workflow") == "workflow-w1"]
    w2_entries = [f for f in findings if f.get("workflow") == "workflow-w2"]
    assert len(w1_entries) == 1, f"W1-Eintrag fehlt/dupliziert: {findings}"
    assert len(w2_entries) == 1, (
        f"W2-Eintrag fehlt (F002-Regression: gegen getaggten Fremd-Eintrag "
        f"content-dedupliziert): {findings}"
    )
    assert len(findings) == 2, (
        f"Erwartet 2 getaggte Einträge (gleicher Inhalt, verschiedene "
        f"Workflows), bekam {len(findings)}: {findings}"
    )


def test_f002_rewrite_by_one_workflow_does_not_delete_other_workflows_identical_finding(
    tmp_path, monkeypatch
):
    """F002 Fortsetzung: W1 schreibt danach ERNEUT (Re-Write, inhaltlich
    identisch) — W2s inhaltsgleicher Eintrag bleibt trotzdem erhalten (eigene
    Zuordnung bleibt gewahrt, kein lautloser Verlust bei jedem weiteren
    Schreibvorgang eines Dritten)."""
    e2e_path = tmp_path / "e2e_verified.json"

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_w1 = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W1 initial", findings_w1, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_w2 = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W2", findings_w2, e2e_path=e2e_path, scope_override="backend", langs=["de", "en"]
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_w1_rewrite = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W1 re-write", findings_w1_rewrite, e2e_path=e2e_path,
        scope_override="backend", langs=["de", "en"]
    ) == 0

    result = json.loads(e2e_path.read_text())
    findings = result["findings"]
    w2_entries = [f for f in findings if f.get("workflow") == "workflow-w2"]
    assert w2_entries, (
        f"W2s inhaltsgleicher Eintrag wurde beim Re-Write von W1 gelöscht "
        f"(F002-Regression): {findings}"
    )
    assert len(findings) == 2, (
        f"Erwartet weiterhin 2 Einträge (W1 nach Re-Write, W2 unverändert), "
        f"bekam {len(findings)}: {findings}"
    )


# ===========================================================================
# RED (#2424): Staging-Verdict je Workflow statt "last writer wins".
#
# Spec: docs/specs/modules/fix_2424_staging_gate_verdict_je_workflow.md
#
# Bisher werden beim gleichen verified_commit nur die findings gemergt;
# staging_verdict, scope, langs, frontend_pages_checked und
# frontend_browser_gate kommen ungemergt aus dem letzten Aufruf. Ein spaeteres
# oberflaechliches VERIFIED eines fremden Workflows oeffnet so den Prod-Deploy,
# obwohl ein gruendlicherer Lauf AMBIGUOUS gemeldet hat.
#
# Mock-frei: die Workflow-Kennung wird ueber die echte Umgebungsvariable
# gesetzt; fuer die Gate-Faelle (AC-1/2/7/9) laeuft alles in einem echten,
# isolierten Temp-Git-Repo (REPO_DIR umgebogen, Muster aus
# test_e2e_commit_namespacing.py), damit der echte Deploy-Gate-Leser
# (gate_check) und die echte Vorfahren-Suche die geschriebene Datei lesen,
# ohne das Hauptrepo zu beruehren.
# ===========================================================================

import subprocess  # noqa: E402

WF_A = "fix-2424-wf-a-gruendlich"
WF_B = "fix-2424-wf-b-oberflaechlich"
WF_C = "fix-2424-wf-c-dritter"


def _git(args, cwd):
    return subprocess.run(["git"] + args, capture_output=True, text=True, cwd=str(cwd))


@pytest.fixture
def iso_repo(tmp_path, monkeypatch):
    """Echtes Temp-Git-Repo mit Backend-Commit; REPO_DIR zeigt darauf, damit
    _head_sha, der Default-Nachweis-Pfad und gate_check NUR dieses Repo sehen."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@example.com"], root)
    _git(["config", "user.name", "Tester"], root)
    (root / ".gitignore").write_text(".claude/\n")
    (root / "src").mkdir()
    (root / "src" / "x.py").write_text("a = 1\n")
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "c1"], root)
    monkeypatch.setattr(mod, "REPO_DIR", root)
    head = _git(["rev-parse", "HEAD"], root).stdout.strip()
    assert mod._head_sha() == head
    return root, head


def _write_as(monkeypatch, workflow: str, verdict: str, tmp_path: Path,
              e2e_path: Path | None, scope: str = "backend",
              langs: list | None = None, findings: list | None = None) -> int:
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", workflow)
    monkeypatch.delenv("GZ_ACTIVE_WORKFLOW", raising=False)
    fp = tmp_path / f"findings-{workflow}.json"
    fp.write_text(json.dumps(findings or []))
    return mod.write_verdict(
        verdict, fp, e2e_path=e2e_path, scope_override=scope,
        langs=["de", "en"] if langs is None else langs,
    )


def _default_path(head: str) -> Path:
    return mod._commit_e2e_path(head)


def test_ac1_fremdes_verified_ueberschreibt_ambiguous_nicht(iso_repo, tmp_path, monkeypatch):
    """AC-1: A schreibt AMBIGUOUS, fremder B schreibt danach VERIFIED auf
    denselben Commit -> Top-Level bleibt AMBIGUOUS und nennt A."""
    root, head = iso_repo
    assert _write_as(monkeypatch, WF_A, "AMBIGUOUS: AC-3 unklar (gruendlich)", tmp_path, None) == 0
    assert _write_as(monkeypatch, WF_B, "VERIFIED: Smoke grün", tmp_path, None) == 0

    data = json.loads(_default_path(head).read_text())
    assert data["verified_commit"] == head
    assert data["staging_verdict"].startswith("AMBIGUOUS"), (
        "Fremdes VERIFIED hat ein AMBIGUOUS ueberschrieben (last writer wins): "
        f"{data['staging_verdict']!r}"
    )
    assert WF_A in data["staging_verdict"], (
        f"Top-Level-Verdict muss den blockierenden Workflow {WF_A} nennen: "
        f"{data['staging_verdict']!r}"
    )
    assert set(data.get("verdicts", {})) == {WF_A, WF_B}, (
        f"verdicts-Map muss je Workflow einen Eintrag fuehren: {data.get('verdicts')!r}"
    )
    assert data["verdicts"][WF_A]["verdict"].startswith("AMBIGUOUS")
    assert data["verdicts"][WF_B]["verdict"].startswith("VERIFIED")


def test_ac1_gate_check_blockt_und_nennt_workflow(iso_repo, tmp_path, monkeypatch, capsys):
    """AC-1 end-to-end: der echte Deploy-Gate-Leser blockt (Exit 1) und die
    Meldung nennt Workflow A als Urheber."""
    root, head = iso_repo
    assert _write_as(monkeypatch, WF_A, "AMBIGUOUS: AC-3 unklar (gruendlich)", tmp_path, None) == 0
    assert _write_as(monkeypatch, WF_B, "VERIFIED: Smoke grün", tmp_path, None) == 0
    capsys.readouterr()

    rc = mod.gate_check(None, "backend")

    err = capsys.readouterr().err
    assert rc == 1, "Prod-Deploy-Gate oeffnet trotz AMBIGUOUS eines fremden Workflows."
    assert WF_A in err, f"Gate-Meldung nennt den blockierenden Workflow nicht:\n{err}"


def test_ac2_eigener_rerun_ersetzt_eigenen_eintrag(iso_repo, tmp_path, monkeypatch):
    """AC-2: derselbe Workflow A schreibt nach AMBIGUOUS erneut VERIFIED ->
    sein Eintrag wird ersetzt, Top-Level VERIFIED, Gate oeffnet."""
    root, head = iso_repo
    assert _write_as(monkeypatch, WF_A, "AMBIGUOUS: Flake", tmp_path, None) == 0
    assert _write_as(monkeypatch, WF_A, "VERIFIED: Re-Run grün", tmp_path, None) == 0

    data = json.loads(_default_path(head).read_text())
    assert data["staging_verdict"].startswith("VERIFIED")
    assert set(data.get("verdicts", {})) == {WF_A}, (
        f"Eigener Re-Run muss den eigenen Eintrag ersetzen: {data.get('verdicts')!r}"
    )
    assert data["verdicts"][WF_A]["verdict"] == "VERIFIED: Re-Run grün"
    assert mod.gate_check(None, "backend") == 0


@pytest.mark.parametrize("folge, erwartet", [
    (["full-stack", "docs-only"], "full-stack"),
    (["frontend-only", "backend"], "full-stack"),
    (["backend", "docs-only"], "backend"),
])
def test_ac3_scope_breitester_rang_kein_herabstufen(tmp_path, monkeypatch, folge, erwartet):
    """AC-3: Top-Level-Scope ist der breiteste; frontend-only + backend =
    full-stack; ein spaeterer schmaler Lauf stuft nicht herab."""
    head = mod._head_sha()
    e2e_path = tmp_path / "e2e_verified.json"
    for wf, scope in zip((WF_A, WF_B), folge):
        assert _write_as(monkeypatch, wf, f"VERIFIED: {scope}", tmp_path, e2e_path,
                         scope=scope) == 0
    data = json.loads(e2e_path.read_text())
    assert data["verified_commit"] == head
    assert data["scope"] == erwartet, (
        f"Scope-Folge {folge} muss {erwartet!r} ergeben, bekam {data['scope']!r}"
    )


def test_ac4_langs_vereinigung(tmp_path, monkeypatch):
    """AC-4: A bezeugt de, B bezeugt en (je docs-only, dort ist eine Sprache
    zulaessig) -> Top-Level langs ist die Vereinigung."""
    e2e_path = tmp_path / "e2e_verified.json"
    assert _write_as(monkeypatch, WF_A, "VERIFIED: de", tmp_path, e2e_path,
                     scope="docs-only", langs=["de"]) == 0
    assert _write_as(monkeypatch, WF_B, "VERIFIED: en", tmp_path, e2e_path,
                     scope="docs-only", langs=["en"]) == 0
    data = json.loads(e2e_path.read_text())
    assert sorted(data.get("langs", [])) == ["de", "en"], (
        f"langs muss die Vereinigung beider Laeufe sein: {data.get('langs')!r}"
    )


def test_ac5_frontend_pages_vereinigung_und_browser_gate_vermerk(tmp_path, monkeypatch):
    """AC-5: A prueft /trips, B prueft /compare, C laeuft ohne Browser-Nachweis
    (Vermerk) -> Top-Level enthaelt beide Seiten UND den Vermerk."""
    e2e_path = tmp_path / "e2e_verified.json"

    def _gate_mit(seiten):
        def _gate(scope, checked=None):
            if checked is not None:
                checked.extend(seiten)
            return 0
        return _gate

    monkeypatch.setattr(mod, "_frontend_browser_gate", _gate_mit(["/trips"]))
    assert _write_as(monkeypatch, WF_A, "VERIFIED: trips", tmp_path, e2e_path,
                     scope="frontend-only") == 0
    monkeypatch.setattr(mod, "_frontend_browser_gate", _gate_mit(["/compare"]))
    assert _write_as(monkeypatch, WF_B, "VERIFIED: compare", tmp_path, e2e_path,
                     scope="frontend-only") == 0
    monkeypatch.setattr(mod, "_frontend_browser_gate", _gate_mit([]))
    assert _write_as(monkeypatch, WF_C, "VERIFIED: ohne Browser", tmp_path, e2e_path,
                     scope="frontend-only") == 0

    data = json.loads(e2e_path.read_text())
    seiten = set(data.get("frontend_pages_checked", []))
    assert {"/trips", "/compare"} <= seiten, (
        f"frontend_pages_checked muss die Vereinigung sein: {data.get('frontend_pages_checked')!r}"
    )
    assert data.get("frontend_browser_gate"), (
        "Vermerk eines Laufs ohne Browser-Nachweis ging verloren."
    )


def test_ac6_altbestand_wird_legacy_und_bleibt_blockierend(tmp_path, monkeypatch):
    """AC-6: Datei im Altformat (ohne verdicts) mit AMBIGUOUS, fremder Lauf
    schreibt VERIFIED -> Altbestand als 'legacy', Top-Level bleibt AMBIGUOUS."""
    head = mod._head_sha()
    e2e_path = tmp_path / "e2e_verified.json"
    _write_existing(e2e_path, head, [FINDING_A], verdict="AMBIGUOUS: Altbestand unklar")
    assert "verdicts" not in json.loads(e2e_path.read_text())

    assert _write_as(monkeypatch, WF_B, "VERIFIED: fremder Lauf", tmp_path, e2e_path) == 0

    data = json.loads(e2e_path.read_text())
    assert data["staging_verdict"].startswith("AMBIGUOUS"), (
        f"Altbestand-AMBIGUOUS ging durch fremden Lauf verloren: {data['staging_verdict']!r}"
    )
    assert "legacy" in data.get("verdicts", {}), (
        f"Altbestand muss als Eintrag 'legacy' uebernommen werden: {data.get('verdicts')!r}"
    )
    assert data["verdicts"]["legacy"]["verdict"].startswith("AMBIGUOUS")
    assert WF_B in data["verdicts"]


def test_ac7_neuer_commit_startet_frisch(iso_repo, tmp_path, monkeypatch):
    """AC-7: bestehende Datei eines ANDEREN Commits mit AMBIGUOUS -> frische
    Map nur mit eigenem Eintrag, Gate oeffnet."""
    root, head = iso_repo
    path = _default_path(head)
    stale = "deadbeef" + head[8:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "verified_commit": stale,
        "staging_verdict": f"AMBIGUOUS (Workflow {WF_A}): alter Stand",
        "verdicts": {WF_A: {"verdict": "AMBIGUOUS: alter Stand", "scope": "backend",
                            "langs": ["de", "en"], "at": "2026-11-01T00:00:00+00:00"}},
        "langs": ["de", "en"], "findings": [], "scope": "backend",
        "verified_at": "2026-11-01T00:00:00+00:00", "environment": "staging",
    }))

    assert _write_as(monkeypatch, WF_B, "VERIFIED: neuer Commit", tmp_path, None) == 0

    data = json.loads(path.read_text())
    assert data["verified_commit"] == head
    assert set(data.get("verdicts", {})) == {WF_B}, (
        f"Neuer Commit muss frisch starten (nur eigener Eintrag): {data.get('verdicts')!r}"
    )
    assert mod.gate_check(None, "backend") == 0


def test_ac8_findings_merge_unveraendert_neben_verdict_merge(tmp_path, monkeypatch):
    """AC-8: Findings und Verdicts im selben Schreibvorgang — Findings-Merge
    (#1197/#1327/F002) unveraendert, Verdicts je Workflow zusaetzlich."""
    e2e_path = tmp_path / "e2e_verified.json"
    assert _write_as(monkeypatch, WF_A, "AMBIGUOUS: A unklar", tmp_path, e2e_path,
                     findings=[FINDING_A]) == 0
    assert _write_as(monkeypatch, WF_B, "VERIFIED: B grün", tmp_path, e2e_path,
                     findings=[FINDING_B]) == 0
    # A schreibt sein Set neu: eigene Findings ersetzt, fremde bleiben.
    assert _write_as(monkeypatch, WF_A, "AMBIGUOUS: A immer noch unklar", tmp_path, e2e_path,
                     findings=[FINDING_SHARED]) == 0

    data = json.loads(e2e_path.read_text())
    fs = data["findings"]
    assert not _contains_finding(fs, FINDING_A), "Eigenes altes Finding von A muss ersetzt sein."
    assert _count_matching(fs, FINDING_B) == 1, "Fremdes Finding von B ging verloren."
    assert _count_matching(fs, FINDING_SHARED) == 1
    assert set(data.get("verdicts", {})) == {WF_A, WF_B}
    assert data["verdicts"][WF_A]["verdict"] == "AMBIGUOUS: A immer noch unklar"
    assert data["staging_verdict"].startswith("AMBIGUOUS")


@pytest.mark.parametrize("folge, erwartet_ok", [
    ([(WF_A, "VERIFIED: A grün"), (WF_B, "VERIFIED: B grün")], True),
    ([(WF_A, "AMBIGUOUS: A unklar"), (WF_B, "VERIFIED: B grün")], False),
])
def test_ac9_leser_sehen_korrektes_toplevel(iso_repo, tmp_path, monkeypatch, folge, erwartet_ok):
    """AC-9: unveraenderte Leser (gate_check, _nearest_verified_ancestor)
    entscheiden auf dem abgeleiteten Top-Level richtig."""
    root, head = iso_repo
    for wf, verdict in folge:
        assert _write_as(monkeypatch, wf, verdict, tmp_path, None) == 0

    ancestor, _cdata = mod._e2e_paths._nearest_verified_ancestor(head, root, root)
    rc = mod.gate_check(None, "backend")
    if erwartet_ok:
        assert ancestor == head, "Reines VERIFIED muss von der Vorfahren-Suche akzeptiert werden."
        assert rc == 0
    else:
        assert ancestor is None, (
            "Gemischter Stand mit AMBIGUOUS darf von der Vorfahren-Suche nicht akzeptiert werden."
        )
        assert rc == 1


def test_aggregate_verdicts_deterministisch():
    """Reine Funktion _aggregate_verdicts(verdicts, aktuell) -> dict mit den
    abgeleiteten Top-Level-Feldern. Bei zwei AMBIGUOUS-Eintraegen gewinnt
    unabhaengig von der Einfuegereihenfolge der nach Workflow-Name erste; das
    Ergebnis traegt das AMBIGUOUS-Praefix vorn und nennt den Urheber."""
    eintraege = {
        "zz-wf": {"verdict": "AMBIGUOUS: zweiter Text", "scope": "backend",
                  "langs": ["de", "en"], "at": "2026-11-10T10:00:00+00:00"},
        "aa-wf": {"verdict": "AMBIGUOUS: erster Text", "scope": "backend",
                  "langs": ["de", "en"], "at": "2026-11-10T11:00:00+00:00"},
        "mm-wf": {"verdict": "VERIFIED: grün", "scope": "full-stack",
                  "langs": ["de", "en"], "at": "2026-11-10T12:00:00+00:00"},
    }
    umgekehrt = dict(reversed(list(eintraege.items())))

    r1 = mod._aggregate_verdicts(eintraege, "mm-wf")
    r2 = mod._aggregate_verdicts(umgekehrt, "mm-wf")

    assert r1["staging_verdict"] == r2["staging_verdict"]
    assert r1["staging_verdict"].startswith("AMBIGUOUS")
    assert "aa-wf" in r1["staging_verdict"] and "erster Text" in r1["staging_verdict"]
    assert r1["scope"] == "full-stack"

    nur_gruen = {"mm-wf": eintraege["mm-wf"]}
    assert mod._aggregate_verdicts(nur_gruen, "mm-wf")["staging_verdict"] == "VERIFIED: grün"
