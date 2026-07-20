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
    """Ehrlicher Boundary-Seam eines UNBETEILIGTEN Gates: kein echter
    Telegram-/Netz-Aufruf während des Merge-Tests."""
    monkeypatch.setattr(mod, "_telegram_live_gate", lambda: 0)


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
        "findings": findings,
        "verified_at": "2026-07-16T00:00:00+00:00",
        "scope": "backend",
        "environment": "staging",
    }, indent=2))


def _call(verdict: str, findings_path: Path, e2e_path: Path) -> int:
    return mod.write_verdict(
        verdict, findings_path, e2e_path=e2e_path, scope_override="backend"
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
        "VERIFIED: W1 grün", findings_a, e2e_path=e2e_path, scope_override="backend"
    )
    assert rc1 == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_b = _write_findings(tmp_path, [FINDING_B])
    rc2 = mod.write_verdict(
        "VERIFIED: W2 grün", findings_b, e2e_path=e2e_path, scope_override="backend"
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
        "VERIFIED: solo", findings_a, e2e_path=e2e_path, scope_override="backend"
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
        "VERIFIED: W1 initial", findings_f1, e2e_path=e2e_path, scope_override="backend"
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_f2 = _write_findings(tmp_path, [FINDING_B])
    assert mod.write_verdict(
        "VERIFIED: W2 dazwischen", findings_f2, e2e_path=e2e_path, scope_override="backend"
    ) == 0

    finding_a_corrected = {**FINDING_A, "evidence": "korrigierte Fassung"}
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_f1b = _write_findings(tmp_path, [finding_a_corrected])
    assert mod.write_verdict(
        "VERIFIED: W1 Korrektur", findings_f1b, e2e_path=e2e_path, scope_override="backend"
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
        "VERIFIED: W1", findings_w1, e2e_path=e2e_path, scope_override="backend"
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_w2 = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W2", findings_w2, e2e_path=e2e_path, scope_override="backend"
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
        "VERIFIED: W1 initial", findings_w1, e2e_path=e2e_path, scope_override="backend"
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w2")
    findings_w2 = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W2", findings_w2, e2e_path=e2e_path, scope_override="backend"
    ) == 0

    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", "workflow-w1")
    findings_w1_rewrite = _write_findings(tmp_path, [dict(_F002_IDENTICAL_CONTENT)])
    assert mod.write_verdict(
        "VERIFIED: W1 re-write", findings_w1_rewrite, e2e_path=e2e_path,
        scope_override="backend"
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
