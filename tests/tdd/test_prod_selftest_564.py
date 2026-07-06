"""
TDD RED: Tests für prod_selftest.py (Issue #564 — Post-Deploy-Selbsttest).

prod_selftest.py existiert noch nicht — alle Tests müssen FAIL sein (RED Phase).

ACs abgedeckt:
  AC-1: Happy path — Exit 0, Bericht mit PASS
  AC-2: Commit-Mismatch — Exit 1, Bericht mit FAIL
  AC-3: Partial — PASS-Finding mit 404 auf Prod → Exit 1, PARTIAL
  AC-4: SKIPPED-Findings → ATTESTED_SKIPPED, blockieren PASS nicht
  AC-5: Kein e2e_verified.json → Exit 0, kein Bericht
  AC-6: Report-Format + <60s Laufzeit
"""

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


PROD_SELFTEST = Path("/home/hem/gregor_zwanzig/.claude/hooks/prod_selftest.py")
REPO_DIR = Path("/home/hem/gregor_zwanzig")
PROD_BASE = "https://gregor20.henemm.com"


def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(REPO_DIR),
    )
    return result.stdout.strip()


def _run_selftest(e2e_path=None, workflow=None, extra_args=None, env_override=None):
    """Ruft prod_selftest.py auf, gibt (returncode, stdout, stderr) zurück."""
    cmd = ["python3", str(PROD_SELFTEST)]
    if e2e_path:
        cmd += ["--e2e-path", str(e2e_path)]
    if workflow:
        cmd += ["--workflow", workflow]
    if extra_args:
        cmd += extra_args

    run_env = os.environ.copy()
    run_env.pop("GZ_ACTIVE_WORKFLOW", None)
    if env_override:
        run_env.update(env_override)

    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO_DIR), env=run_env
    )
    return result.returncode, result.stdout, result.stderr


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


class TestScriptExists:
    def test_prod_selftest_script_exists(self):
        """Grundlage: prod_selftest.py muss vorhanden sein."""
        assert PROD_SELFTEST.exists(), (
            f"prod_selftest.py nicht gefunden unter {PROD_SELFTEST}. "
            "Bitte implementieren (Issue #564)."
        )

    def test_prod_selftest_script_syntactically_valid(self):
        """prod_selftest.py muss syntaktisch korrekt sein."""
        result = subprocess.run(
            ["python3", "-c", f"import ast; ast.parse(open('{PROD_SELFTEST}').read())"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntaxfehler in prod_selftest.py: {result.stderr}"


class TestAC1HappyPath:
    """AC-1: Alle Findings PASS, Prod antwortet korrekt → Exit 0, Bericht PASS."""

    def test_exit0_when_commit_matches_and_routes_reachable(self, tmp_path):
        """AC-1: e2e_verified.json mit HEAD-Commit + PASS-Findings auf erreichbaren Routen → Exit 0."""
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/:AC-1",
                    "evidence": "Root antwortet",
                },
                {
                    "ac": "AC-2",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/trips/new:AC-2",
                    "evidence": "Form-Route antwortet",
                },
            ],
        )
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="issue-564-ac1-happy")
        assert rc == 0, (
            f"Erwartet Exit 0 (PASS), aber Exit {rc}\nstdout: {out}\nstderr: {err}"
        )

    def test_report_written_to_artifacts_dir(self, tmp_path):
        """AC-1: Bericht erscheint unter docs/artifacts/<workflow>/prod-selftest.md."""
        workflow_name = "issue-564-ac1-report-path"
        e2e = _make_e2e_verified(tmp_path)
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert report_path.exists(), (
            f"Bericht nicht gefunden unter {report_path}. "
            "prod_selftest.py muss ihn nach docs/artifacts/<workflow>/prod-selftest.md schreiben."
        )

    def test_report_shows_pass_verdict(self, tmp_path):
        """AC-1: Bericht enthält 'PASS' als Gesamtverdikt."""
        workflow_name = "issue-564-ac1-pass-verdict"
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/:AC-1",
                    "evidence": "ok",
                },
            ],
        )
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert report_path.exists(), f"Bericht fehlt: {report_path}"
        content = report_path.read_text()
        assert "PASS" in content, f"'PASS'-Verdict fehlt im Bericht:\n{content}"


class TestAC2CommitMismatch:
    """AC-2: verified_commit != HEAD → Exit 1, Bericht mit FAIL-Verdict."""

    def test_exit1_on_commit_mismatch(self, tmp_path):
        """AC-2: Veralteter verified_commit → Exit 1."""
        wrong_commit = "a" * 40
        e2e = _make_e2e_verified(tmp_path, verified_commit=wrong_commit)
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="issue-564-ac2-mismatch")
        assert rc == 1, (
            f"Erwartet Exit 1 (FAIL bei Commit-Mismatch), aber Exit {rc}\nstdout: {out}\nstderr: {err}"
        )

    def test_report_contains_fail_on_commit_mismatch(self, tmp_path):
        """AC-2: Bericht enthält 'FAIL' und Commit-Mismatch-Hinweis."""
        workflow_name = "issue-564-ac2-fail-report"
        e2e = _make_e2e_verified(tmp_path, verified_commit="0" * 40)
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert report_path.exists(), f"Bericht fehlt: {report_path}"
        content = report_path.read_text()
        assert "FAIL" in content, f"'FAIL'-Verdict fehlt im Bericht:\n{content}"
        assert any(
            kw in content.lower() for kw in ["commit", "mismatch", "übereinstimm", "stimmt nicht"]
        ), f"Kein Commit-Mismatch-Hinweis im Bericht:\n{content}"


class TestAC3PartialVerdict:
    """AC-3: PASS-Finding auf nicht erreichbarer Prod-Route → Exit 1, PARTIAL."""

    def test_exit1_when_pass_finding_returns_404(self, tmp_path):
        """AC-3: PASS-Finding zeigt auf Prod-Route die 404 liefert → Exit 1."""
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    # Diese API-Route existiert nicht → Prod gibt 404
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/api/does-not-exist-564test:AC-1",
                    "evidence": "ok auf Staging",
                },
            ],
        )
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="issue-564-ac3-partial")
        assert rc == 1, (
            f"Erwartet Exit 1 (PARTIAL bei 404-Route), aber Exit {rc}\nstdout: {out}\nstderr: {err}"
        )

    def test_report_contains_partial_verdict(self, tmp_path):
        """AC-3: Bericht enthält 'PARTIAL' wenn eine Route fehlt."""
        workflow_name = "issue-564-ac3-partial-report"
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-X",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/api/nonexistent-route-564:AC-X",
                    "evidence": "ok auf Staging",
                },
            ],
        )
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert report_path.exists(), f"Bericht fehlt: {report_path}"
        content = report_path.read_text()
        assert "PARTIAL" in content, f"'PARTIAL'-Verdict fehlt im Bericht:\n{content}"


class TestAC4SkippedFindings:
    """AC-4: SKIPPED-Findings → ATTESTED_SKIPPED im Bericht, blockieren PASS nicht."""

    def test_skipped_findings_do_not_block_pass(self, tmp_path):
        """AC-4: PASS-Finding ok + SKIPPED-Finding → Exit 0."""
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/:AC-1",
                    "evidence": "Root ok",
                },
                {
                    "ac": "AC-2",
                    "status": "SKIPPED",
                    "url": "https://staging.gregor20.henemm.com/api/send-mail:AC-2",
                    "evidence": "Backend-E-Mail-AC, kein UI-Check möglich",
                },
            ],
        )
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="issue-564-ac4-skip-noblock")
        assert rc == 0, (
            f"SKIPPED-Findings dürfen PASS nicht blockieren, aber Exit {rc}\nstdout: {out}\nstderr: {err}"
        )

    def test_skipped_findings_appear_as_attested_skipped_in_report(self, tmp_path):
        """AC-4: SKIPPED-Findings erscheinen im Bericht als 'ATTESTED_SKIPPED'."""
        workflow_name = "issue-564-ac4-skipped-label"
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-email",
                    "status": "SKIPPED",
                    "url": "https://staging.gregor20.henemm.com/api/scheduler/run:AC-email",
                    "evidence": "E-Mail-AC — kein HTTP-Nachweis möglich",
                },
            ],
        )
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert report_path.exists(), f"Bericht fehlt: {report_path}"
        content = report_path.read_text()
        assert "ATTESTED_SKIPPED" in content, (
            f"'ATTESTED_SKIPPED' fehlt für SKIPPED-Findings im Bericht:\n{content}"
        )

    def test_all_skipped_findings_yield_exit0(self, tmp_path):
        """AC-4: Wenn ausschließlich SKIPPED-Findings vorhanden → Exit 0 (SKIPPED_ALL)."""
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "SKIPPED",
                    "url": "https://staging.gregor20.henemm.com/api/send:AC-1",
                    "evidence": "Backend-AC",
                },
                {
                    "ac": "AC-2",
                    "status": "SKIPPED",
                    "url": "https://staging.gregor20.henemm.com/api/mail:AC-2",
                    "evidence": "E-Mail-AC",
                },
            ],
        )
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="issue-564-ac4-all-skipped")
        assert rc == 0, (
            f"Nur SKIPPED-Findings → Exit 0 (SKIPPED_ALL) erwartet, aber Exit {rc}\n{out}\n{err}"
        )


class TestAC5NoE2EFile:
    """AC-5: Kein e2e_verified.json → Exit 0 (graceful skip), kein Bericht."""

    def test_exit0_when_e2e_verified_missing(self, tmp_path):
        """AC-5: Fehlendes e2e_verified.json → Exit 0."""
        non_existent = tmp_path / "does_not_exist.json"
        rc, out, err = _run_selftest(
            e2e_path=non_existent, workflow="issue-564-ac5-no-file"
        )
        combined = out + err
        assert rc == 0, (
            f"Erwartet Exit 0 bei fehlendem e2e_verified.json, aber Exit {rc}\n{combined}"
        )

    def test_info_message_when_e2e_verified_missing(self, tmp_path):
        """AC-5: INFO-Meldung wenn kein e2e_verified.json vorhanden."""
        non_existent = tmp_path / "does_not_exist.json"
        rc, out, err = _run_selftest(e2e_path=non_existent, workflow="issue-564-ac5-info")
        combined = out + err
        assert any(
            kw in combined.lower()
            for kw in ["übersprungen", "skipped", "info", "nicht vorhanden", "not found", "missing"]
        ), f"Keine INFO-Meldung bei fehlendem e2e_verified.json:\n{combined}"

    def test_no_report_written_when_e2e_verified_missing(self, tmp_path):
        """AC-5: Kein Bericht wird geschrieben wenn e2e_verified.json fehlt."""
        workflow_name = "issue-564-ac5-no-report"
        non_existent = tmp_path / "does_not_exist.json"
        _run_selftest(e2e_path=non_existent, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert not report_path.exists(), (
            f"Bericht fälschlicherweise geschrieben obwohl kein e2e_verified.json vorhanden: {report_path}"
        )


class TestAC6ReportFormat:
    """AC-6: Bericht hat korrekte Tabellen-Spalten, Fazit-Abschnitt, <60s Laufzeit."""

    def test_report_contains_required_table_columns(self, tmp_path):
        """AC-6: Bericht-Tabelle enthält Spalten AC, Staging-Status, Prod-URL, Prod-HTTP, Prod-Status."""
        workflow_name = "issue-564-ac6-columns"
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/:AC-1",
                    "evidence": "ok",
                },
                {
                    "ac": "AC-2",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/trips/new:AC-2",
                    "evidence": "ok",
                },
                {
                    "ac": "AC-3",
                    "status": "SKIPPED",
                    "url": "https://staging.gregor20.henemm.com/api/mail:AC-3",
                    "evidence": "backend",
                },
            ],
        )
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert report_path.exists(), f"Bericht fehlt: {report_path}"
        content = report_path.read_text()

        required_columns = ["AC", "Staging", "Prod", "HTTP", "Status"]
        for col in required_columns:
            assert col in content, (
                f"Pflicht-Spalte '{col}' fehlt im Bericht:\n{content[:600]}"
            )

    def test_report_contains_fazit_section(self, tmp_path):
        """AC-6: Bericht enthält einen Fazit-/Verdict-Abschnitt."""
        workflow_name = "issue-564-ac6-fazit"
        e2e = _make_e2e_verified(tmp_path)
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        assert report_path.exists(), f"Bericht fehlt: {report_path}"
        content = report_path.read_text()
        assert any(
            kw in content.lower() for kw in ["fazit", "verdict", "ergebnis", "gesamt"]
        ), f"Kein Fazit/Verdict-Abschnitt im Bericht:\n{content[:600]}"

    def test_url_rewriting_strips_staging_domain_and_ac_suffix(self, tmp_path):
        """AC-6: Staging-URL wird korrekt in Prod-URL umgeschrieben (Domain + :AC-N entfernt)."""
        workflow_name = "issue-564-ac6-url-rewrite"
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/trips/my-path:AC-1",
                    "evidence": "ok",
                },
            ],
        )
        _run_selftest(e2e_path=e2e, workflow=workflow_name)

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        if report_path.exists():
            content = report_path.read_text()
            # Prod-URL muss gregor20.henemm.com/trips/my-path enthalten (ohne staging.)
            assert "gregor20.henemm.com/trips/my-path" in content, (
                f"Prod-URL nicht korrekt umgeschrieben im Bericht (staging. muss weg):\n{content}"
            )
            # :AC-1 Suffix muss aus der Prod-URL entfernt sein
            # (Der AC-Name selbst darf vorkommen, aber nicht als URL-Suffix)
            assert "my-path:AC-1" not in content, (
                f"':AC-1'-Suffix wurde nicht aus der Prod-URL entfernt:\n{content}"
            )

    def test_completes_within_60_seconds(self, tmp_path):
        """AC-6: Selftest mit 5 PASS-Findings läuft in <60s durch (parallele Probes)."""
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": f"AC-{i}",
                    "status": "PASS",
                    "url": f"https://staging.gregor20.henemm.com/:AC-{i}",
                    "evidence": "ok",
                }
                for i in range(1, 6)
            ],
        )
        start = time.monotonic()
        _run_selftest(e2e_path=e2e, workflow="issue-564-ac6-timing")
        elapsed = time.monotonic() - start
        assert elapsed < 60, (
            f"Selftest dauerte {elapsed:.1f}s — muss unter 60s bleiben (parallele HTTP-Probes nötig)"
        )
