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


def test_ac1_merge_preserves_existing_findings(tmp_path):
    """AC-1: bestehend [A] + neu [B] auf demselben SHA → Ergebnis enthält A und B."""
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
    assert FINDING_B in result["findings"], "Neues Finding fehlt im Ergebnis."


def test_ac2_merge_deduplicates_shared_finding(tmp_path):
    """AC-2: bestehend [A, shared] + neu [shared, B] → shared genau einmal, Länge 3."""
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
        f"Gemeinsames Finding soll genau einmal erscheinen, erschien {shared_count}x."
    )
    assert FINDING_A in findings
    assert FINDING_B in findings
    assert len(findings) == 3, f"Erwartet 3 dedup'te Findings, bekam {len(findings)}: {findings}"


def test_ac3_no_existing_file_writes_only_new_findings(tmp_path):
    """AC-3: keine bestehende Datei → nur die neuen Findings (Regressions-Guard)."""
    e2e_path = tmp_path / "e2e_verified.json"
    assert not e2e_path.exists()
    findings_path = _write_findings(tmp_path, [FINDING_B])

    rc = _call("VERIFIED: erster Lauf", findings_path, e2e_path)

    assert rc == 0
    result = json.loads(e2e_path.read_text())
    assert result["findings"] == [FINDING_B], (
        f"Ohne Bestandsdatei nur neue Findings erwartet, bekam: {result['findings']}"
    )


def test_ac4_stale_commit_is_overwritten_not_merged(tmp_path):
    """AC-4: bestehende Datei trägt fremden verified_commit → kein Merge, überschreiben."""
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
    assert result["findings"] == [FINDING_B]


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
