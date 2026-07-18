"""
TDD RED: Tests für Bug #730 — prod_selftest.py crasht (InvalidURL) bei Findings
ohne echte abrufbare URL.

Vor dem Fix crasht das Script mit `http.client.InvalidURL` (MRO: HTTPException →
Exception, KEIN URLError/OSError-Subtyp), sobald eine PASS-Finding eine `url` mit
Leerzeichen/Steuerzeichen trägt (z.B. eine Backend-AC-Beschreibung
`/api/trips/{id} PUT/GET`). Der Crash blockiert fälschlich den Issue-Close.

Mock-frei: echter Subprozess-Lauf des Scripts gegen echtes Prod, verified_commit=HEAD.

ACs:
  AC-1: Nicht-probebare PASS-Finding → kein Crash, Exit 0, kein InvalidURL-Traceback
  AC-2: Mix aus erreichbarer + nicht-probebarer Finding → Verdict PASS (kein PARTIAL/FAIL)
  AC-3: Nicht-probebare Finding erscheint als SKIPPED_NO_URL im Bericht (nicht still verworfen)
  AC-4: Regressionsschutz — echte probebare 404-Finding bleibt PARTIAL/Exit 1
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging

PROD_SELFTEST = Path("/home/hem/gregor_zwanzig/.claude/hooks/prod_selftest.py")
REPO_DIR = Path("/home/hem/gregor_zwanzig")


def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(REPO_DIR),
    )
    return result.stdout.strip()


def _run_selftest(e2e_path=None, workflow=None):
    """Ruft prod_selftest.py als echten Subprozess auf → (returncode, stdout, stderr)."""
    cmd = ["python3", str(PROD_SELFTEST)]
    if e2e_path:
        cmd += ["--e2e-path", str(e2e_path)]
    if workflow:
        cmd += ["--workflow", workflow]
    run_env = os.environ.copy()
    run_env.pop("GZ_ACTIVE_WORKFLOW", None)
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO_DIR), env=run_env
    )
    return result.returncode, result.stdout, result.stderr


def _make_e2e_verified(tmp_path, findings, verified_commit=None):
    if verified_commit is None:
        verified_commit = _head_sha()
    data = {
        "verified_commit": verified_commit,
        "staging_verdict": "VERIFIED: ACs grün",
        "findings": findings,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "full-stack",
        "environment": "staging",
    }
    json_file = tmp_path / "e2e_verified.json"
    json_file.write_text(json.dumps(data, indent=2))
    return json_file


# Eine nicht-probebare Finding-URL: Freitext mit Leerzeichen statt echtem Pfad.
# urllib wirft hierfür InvalidURL ('URL can't contain control characters').
_NON_PROBEABLE_FINDING = {
    "ac": "AC-7",
    "status": "PASS",
    "url": "/api/trips/{id} PUT/GET",
    "evidence": "Backend-Verhalten, keine probebare GET-Route",
}


class TestAC1NoCrash:
    """AC-1: Nicht-probebare PASS-Finding crasht den Selftest nicht."""

    def test_exit0_and_no_invalidurl_traceback(self, tmp_path):
        e2e = _make_e2e_verified(tmp_path, findings=[_NON_PROBEABLE_FINDING])
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="bug-730-ac1-nocrash")
        assert rc == 0, (
            f"Erwartet Exit 0 (kein Crash bei nicht-probebarer URL), aber Exit {rc}\n"
            f"stdout: {out}\nstderr: {err}"
        )
        combined = out + err
        assert "InvalidURL" not in combined, (
            f"InvalidURL-Crash trat auf — Finding hätte übersprungen werden müssen:\n{combined}"
        )
        assert "Traceback" not in combined, (
            f"Unbehandelter Traceback im Selftest:\n{combined}"
        )


class TestAC2VerdictNotBlocked:
    """AC-2: Mix aus erreichbarer + nicht-probebarer Finding → Verdict bleibt PASS."""

    def test_pass_verdict_with_one_reachable_and_one_non_probeable(self, tmp_path):
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/:AC-1",
                    "evidence": "Root erreichbar",
                },
                _NON_PROBEABLE_FINDING,
            ],
        )
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="bug-730-ac2-noblock")
        assert rc == 0, (
            f"Erwartet Exit 0 (PASS), aber Exit {rc}\nstdout: {out}\nstderr: {err}"
        )
        report = (
            REPO_DIR / "docs" / "artifacts" / "bug-730-ac2-noblock" / "prod-selftest.md"
        )
        assert report.exists(), f"Bericht fehlt: {report}"
        content = report.read_text()
        assert "Verdict: PARTIAL" not in content, (
            f"Nicht-probebare Finding hat fälschlich PARTIAL ausgelöst:\n{content}"
        )
        assert "Verdict: FAIL" not in content, (
            f"Nicht-probebare Finding hat fälschlich FAIL ausgelöst:\n{content}"
        )


class TestAC3TransparentSkip:
    """AC-3: Nicht-probebare Finding wird im Bericht als SKIPPED_NO_URL ausgewiesen."""

    def test_report_marks_non_probeable_as_skipped_no_url(self, tmp_path):
        e2e = _make_e2e_verified(tmp_path, findings=[_NON_PROBEABLE_FINDING])
        _run_selftest(e2e_path=e2e, workflow="bug-730-ac3-transparent")
        report = (
            REPO_DIR / "docs" / "artifacts" / "bug-730-ac3-transparent" / "prod-selftest.md"
        )
        assert report.exists(), f"Bericht fehlt: {report}"
        content = report.read_text()
        assert "SKIPPED_NO_URL" in content, (
            f"Nicht-probebare Finding nicht transparent als SKIPPED_NO_URL markiert:\n{content}"
        )


class TestAC4RegressionGuard:
    """AC-4: Echte probebare 404-Finding bleibt PARTIAL/Exit 1 (kein Über-Skip)."""

    def test_real_404_finding_still_partial(self, tmp_path):
        e2e = _make_e2e_verified(
            tmp_path,
            findings=[
                {
                    "ac": "AC-1",
                    "status": "PASS",
                    "url": "https://staging.gregor20.henemm.com/api/does-not-exist-730test:AC-1",
                    "evidence": "ok auf Staging",
                },
            ],
        )
        rc, out, err = _run_selftest(e2e_path=e2e, workflow="bug-730-ac4-regression")
        assert rc == 1, (
            f"Erwartet Exit 1 (PARTIAL bei echter 404-Route), aber Exit {rc}\n"
            f"stdout: {out}\nstderr: {err}"
        )
        report = (
            REPO_DIR / "docs" / "artifacts" / "bug-730-ac4-regression" / "prod-selftest.md"
        )
        assert report.exists(), f"Bericht fehlt: {report}"
        assert "PARTIAL" in report.read_text(), "PARTIAL-Verdict fehlt bei echter 404-Route"
