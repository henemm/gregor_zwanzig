"""
TDD RED: Tests fuer staging_gate.py (Issue #521 — Staging Validator Agent).

Mocks sind in diesem Projekt VERBOTEN. Alle Tests laufen gegen das echte Script.
staging_gate.py existiert noch nicht — alle Tests muessen FAIL sein (RED Phase).

Getestete ACs:
  AC-2: verified_commit + staging_verdict in e2e_verified.json nach Write-Verdict
  AC-3: verified_commit != HEAD → --check exit 1
  AC-4: staging_verdict != VERIFIED → --check exit 1
  AC-5: GZ_SKIP_E2E_GATE=1 → --check exit 0 + Warn-Log
  AC-6: BROKEN → kein VERIFIED-Artefakt geschrieben
  AC-7: docs-only scope → --check exit 0
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


STAGING_GATE = Path("/home/hem/gregor_zwanzig/.claude/hooks/staging_gate.py")
REPO_DIR = Path("/home/hem/gregor_zwanzig")

# Issue #1096: hermetisches Temp-Repo fuer TestGateCheckModeB (AC-5/AC-6) —
# Hook-Kopien kommen aus dem AKTUELLEN Arbeitsverzeichnis (Worktree), nicht
# aus dem Hauptrepo hartkodiert (Muster test_issue_916_gate_scope_marker.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"


def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=REPO_DIR
    )
    return result.stdout.strip()


def _run_gate(args: list[str], env_extra: dict | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["GZ_ACTIVE_WORKFLOW"] = "issue-521-staging-validator"
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        ["python3", str(STAGING_GATE)] + args,
        capture_output=True, text=True,
        cwd=str(REPO_DIR), env=env
    )
    return result.returncode, result.stdout, result.stderr


def _write_e2e_json(tmp_path: Path, **overrides) -> Path:
    """Schreibt eine e2e_verified.json mit kontrollierten Inhalten."""
    data = {
        "verified_commit": _head_sha(),
        "staging_verdict": "VERIFIED: alle ACs grün",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "environment": "staging",
        "scope": "frontend-only",
        "checks": ["playwright_login", "ac_checks"],
        "feature_checks": ["AC-1: PASS", "AC-2: PASS"],
        "findings": [],
    }
    data.update(overrides)
    json_file = tmp_path / "e2e_verified.json"
    json_file.write_text(json.dumps(data, indent=2))
    return json_file


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True, text=True)


def _setup_repo(tmp_path: Path) -> Path:
    """Standalone Git-Repo mit eigener .claude/hooks-Kopie (Worktree-sicher,
    Muster test_issue_916_gate_scope_marker.py::_setup_repo). Isoliert
    TestGateCheckModeB vom echten, beweglichen Hauptrepo (AC-5/AC-6)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.de")
    _git(repo, "config", "user.name", "Test")

    hooks = repo / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    for name in ("staging_gate.py", "prod_selftest.py", "_e2e_paths.py"):
        shutil.copy(_HOOKS_SRC / name, hooks / name)

    (repo / "README.md").write_text("# baseline\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "baseline")
    return repo


def _repo_head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo,
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _run_gate_in(repo: Path, args: list[str], env_extra: dict | None = None) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["GZ_ACTIVE_WORKFLOW"] = "issue-521-staging-validator"
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(repo / ".claude" / "hooks" / "staging_gate.py")] + args,
        capture_output=True, text=True, cwd=str(repo), env=env,
    )
    return result.returncode, result.stdout, result.stderr


def _write_e2e_json_in(repo: Path, tmp_path: Path, **overrides) -> Path:
    """Analog zu _write_e2e_json(), aber gegen den HEAD des Temp-Repos."""
    data = {
        "verified_commit": _repo_head_sha(repo),
        "staging_verdict": "VERIFIED: alle ACs grün",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "environment": "staging",
        "scope": "frontend-only",
        "checks": ["playwright_login", "ac_checks"],
        "feature_checks": ["AC-1: PASS", "AC-2: PASS"],
        "findings": [],
    }
    data.update(overrides)
    json_file = tmp_path / "e2e_verified.json"
    json_file.write_text(json.dumps(data, indent=2))
    return json_file


class TestStagingGateScriptExists:
    """Das Script muss existieren, sonst schlagen alle anderen Tests aus dem falschen Grund fehl."""

    def test_staging_gate_script_exists(self):
        """AC-Grundlage: staging_gate.py muss vorhanden sein."""
        assert STAGING_GATE.exists(), (
            f"staging_gate.py nicht gefunden unter {STAGING_GATE}. "
            "Implementation fehlt noch (RED-Phase korrekt)."
        )

    def test_staging_gate_script_is_executable(self):
        """staging_gate.py muss syntaktisch korrekt sein."""
        result = subprocess.run(
            ["python3", "-c", f"import ast; ast.parse(open('{STAGING_GATE}').read())"],
            capture_output=True, text=True
        )
        assert result.returncode == 0, f"Syntaxfehler in staging_gate.py: {result.stderr}"


class TestGateCheckModeB:
    """Mode B: --check — aufgerufen von deploy-gregor-prod.sh (AC-3, AC-4, AC-5, AC-7).

    Issue #1096 (AC-5/AC-6): laeuft ausschliesslich gegen ein hermetisches
    Temp-Git-Repo (_setup_repo) statt gegen das echte, bewegliche Hauptrepo —
    sonst mutiert der Testlauf die echte .claude/last_gate_scope.json und wird
    instabil, sobald der Scope des Hauptrepos zufaellig auf docs-only steht.
    Tests ohne Scope-Erkennungs-Bezug erhalten einen expliziten
    --scope=backend, damit der docs-only-Skip-Zweig ihre eigentliche
    Pruefung nicht vor der Zeit greift.
    """

    def test_gate_blocks_when_file_missing(self, tmp_path, monkeypatch):
        """AC-3/AC-4: Fehlende e2e_verified.json → Exit 1."""
        repo = _setup_repo(tmp_path)
        nonexistent = str(tmp_path / "does_not_exist.json")
        rc, out, err = _run_gate_in(
            repo, ["--check", f"--e2e-path={nonexistent}", "--scope=backend"]
        )
        assert rc == 1, f"Erwartet Exit 1 bei fehlender Datei, bekam {rc}"
        combined = out + err
        assert any(w in combined.lower() for w in ["e2e_verified", "fehler", "error", "missing"]), (
            f"Fehlermeldung erwartet, bekam: {combined}"
        )

    def test_gate_blocks_when_commit_mismatch(self, tmp_path):
        """AC-3: verified_commit != HEAD → Exit 1."""
        repo = _setup_repo(tmp_path)
        json_file = _write_e2e_json_in(
            repo, tmp_path,
            verified_commit="0000000000000000000000000000000000000000"
        )
        rc, out, err = _run_gate_in(repo, ["--check", f"--e2e-path={json_file}", "--scope=backend"])
        assert rc == 1, f"Erwartet Exit 1 bei falschem Commit, bekam {rc}"
        combined = out + err
        assert any(w in combined.lower() for w in ["commit", "sha", "mismatch", "verifizier"]), (
            f"Hinweis auf Commit-Mismatch erwartet, bekam: {combined}"
        )

    def test_gate_blocks_when_verdict_broken(self, tmp_path):
        """AC-4: staging_verdict = BROKEN → Exit 1."""
        repo = _setup_repo(tmp_path)
        json_file = _write_e2e_json_in(
            repo, tmp_path,
            staging_verdict="BROKEN: AC-2 fehlgeschlagen"
        )
        rc, out, err = _run_gate_in(repo, ["--check", f"--e2e-path={json_file}", "--scope=backend"])
        assert rc == 1, f"Erwartet Exit 1 bei BROKEN, bekam {rc}"

    def test_gate_blocks_when_verdict_ambiguous(self, tmp_path):
        """AC-4: staging_verdict = AMBIGUOUS → Exit 1 (kein stilles Durchlaufen)."""
        repo = _setup_repo(tmp_path)
        json_file = _write_e2e_json_in(
            repo, tmp_path,
            staging_verdict="AMBIGUOUS: Screenshot nicht auswertbar"
        )
        rc, out, err = _run_gate_in(repo, ["--check", f"--e2e-path={json_file}", "--scope=backend"])
        assert rc == 1, f"Erwartet Exit 1 bei AMBIGUOUS, bekam {rc}"

    def test_gate_blocks_when_verdict_missing(self, tmp_path):
        """AC-4: staging_verdict fehlt komplett → Exit 1."""
        repo = _setup_repo(tmp_path)
        data = {
            "verified_commit": _repo_head_sha(repo),
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "environment": "staging",
        }
        json_file = tmp_path / "e2e_verified.json"
        json_file.write_text(json.dumps(data))
        rc, out, err = _run_gate_in(repo, ["--check", f"--e2e-path={json_file}", "--scope=backend"])
        assert rc == 1, f"Erwartet Exit 1 bei fehlendem staging_verdict, bekam {rc}"

    def test_gate_blocks_when_stale(self, tmp_path):
        """AC-4/TTL: verified_at älter als 24h → Exit 1."""
        repo = _setup_repo(tmp_path)
        stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
        json_file = _write_e2e_json_in(
            repo, tmp_path,
            verified_at=stale_time.isoformat()
        )
        rc, out, err = _run_gate_in(repo, ["--check", f"--e2e-path={json_file}", "--scope=backend"])
        assert rc == 1, f"Erwartet Exit 1 bei abgelaufenem Artefakt, bekam {rc}"
        combined = out + err
        assert any(w in combined.lower() for w in ["alt", "stale", "abgelaufen", "24"]), (
            f"Hinweis auf abgelaufenes Artefakt erwartet, bekam: {combined}"
        )

    def test_gate_passes_when_verified_and_matching_commit(self, tmp_path):
        """AC-2/AC-3: Korrekter Commit + VERIFIED → Exit 0."""
        repo = _setup_repo(tmp_path)
        json_file = _write_e2e_json_in(repo, tmp_path)
        rc, out, err = _run_gate_in(repo, ["--check", f"--e2e-path={json_file}", "--scope=backend"])
        assert rc == 0, (
            f"Erwartet Exit 0 bei korrektem Commit + VERIFIED, bekam {rc}.\n"
            f"stdout: {out}\nstderr: {err}"
        )

    def test_gate_skip_env_allows_deploy_with_warning(self, tmp_path):
        """AC-5: GZ_SKIP_E2E_GATE=1 → Exit 0, aber Warn-Nachricht in Ausgabe."""
        repo = _setup_repo(tmp_path)
        json_file = _write_e2e_json_in(
            repo, tmp_path,
            verified_commit="0000000000000000000000000000000000000000"
        )
        rc, out, err = _run_gate_in(
            repo, ["--check", f"--e2e-path={json_file}", "--scope=backend"],
            env_extra={"GZ_SKIP_E2E_GATE": "1"}
        )
        assert rc == 0, f"Erwartet Exit 0 bei GZ_SKIP_E2E_GATE=1, bekam {rc}"
        combined = out + err
        assert any(w in combined.lower() for w in ["warn", "skip", "override", "bypass", "ueberspring"]), (
            f"Warn-Hinweis erwartet bei GZ_SKIP_E2E_GATE=1, bekam: {combined}"
        )

    def test_gate_docs_only_scope_skips_check(self, tmp_path):
        """AC-7: scope=docs-only → Exit 0 ohne Gate-Block (auch wenn kein VERIFIED-Artefakt)."""
        repo = _setup_repo(tmp_path)
        nonexistent = str(tmp_path / "does_not_exist.json")
        rc, out, err = _run_gate_in(
            repo, ["--check", f"--e2e-path={nonexistent}", "--scope=docs-only"]
        )
        assert rc == 0, (
            f"Erwartet Exit 0 bei docs-only Scope, bekam {rc}.\n"
            f"stdout: {out}\nstderr: {err}"
        )
        combined = out + err
        assert any(w in combined.lower() for w in ["docs", "skip", "ueberspring"]), (
            f"Docs-only-Hinweis erwartet, bekam: {combined}"
        )


class TestGateWriteVerdictModeA:
    """Mode A: --write-verdict — aufgerufen vom Staging Validator Agent (AC-2, AC-6)."""

    def test_write_verdict_verified_creates_file(self, tmp_path):
        """AC-2: --write-verdict VERIFIED schreibt e2e_verified.json mit verified_commit."""
        findings = tmp_path / "findings.json"
        findings.write_text(json.dumps([
            {"ac": "AC-1", "status": "PASS", "url": "https://staging.gregor20.henemm.com/trips:AC-1", "evidence": "button gefunden"},
        ]))
        out_path = tmp_path / "e2e_verified.json"
        rc, out, err = _run_gate([
            "--write-verdict", "VERIFIED: 1/1 ACs grün",
            "--findings-json", str(findings),
            "--e2e-path", str(out_path),
        ])
        assert rc == 0, f"Erwartet Exit 0 bei VERIFIED, bekam {rc}.\nstdout: {out}\nstderr: {err}"
        assert out_path.exists(), "e2e_verified.json wurde nicht geschrieben"
        data = json.loads(out_path.read_text())
        assert "verified_commit" in data, "verified_commit fehlt in geschriebener Datei"
        assert data["verified_commit"] == _head_sha(), (
            f"verified_commit soll HEAD-SHA sein, bekam: {data['verified_commit']}"
        )
        assert "staging_verdict" in data, "staging_verdict fehlt"
        assert data["staging_verdict"].startswith("VERIFIED"), (
            f"staging_verdict soll mit VERIFIED beginnen, bekam: {data['staging_verdict']}"
        )
        assert "findings" in data, "findings[] fehlt"
        assert isinstance(data["findings"], list), "findings muss eine Liste sein"

    def test_write_verdict_verified_includes_timestamp(self, tmp_path):
        """AC-2: e2e_verified.json enthält verified_at als ISO-Timestamp."""
        findings = tmp_path / "findings.json"
        findings.write_text(json.dumps([]))
        out_path = tmp_path / "e2e_verified.json"
        _run_gate([
            "--write-verdict", "VERIFIED: smoke only",
            "--findings-json", str(findings),
            "--e2e-path", str(out_path),
        ])
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert "verified_at" in data, "verified_at fehlt"
        datetime.fromisoformat(data["verified_at"])

    def test_write_verdict_broken_returns_exit1(self, tmp_path):
        """AC-6: --write-verdict BROKEN → Exit 1."""
        findings = tmp_path / "findings.json"
        findings.write_text(json.dumps([
            {"ac": "AC-1", "status": "FAIL", "url": "https://staging.gregor20.henemm.com/trips:AC-1", "evidence": "Element nicht gefunden"},
        ]))
        out_path = tmp_path / "e2e_verified.json"
        rc, out, err = _run_gate([
            "--write-verdict", "BROKEN: AC-1 fehlgeschlagen",
            "--findings-json", str(findings),
            "--e2e-path", str(out_path),
        ])
        assert rc == 1, f"Erwartet Exit 1 bei BROKEN, bekam {rc}"

    def test_write_verdict_broken_does_not_write_verified_artifact(self, tmp_path):
        """AC-6: Bei BROKEN wird KEIN VERIFIED-Artefakt geschrieben."""
        findings = tmp_path / "findings.json"
        findings.write_text(json.dumps([
            {"ac": "AC-1", "status": "FAIL", "url": "https://staging.gregor20.henemm.com/trips:AC-1", "evidence": "button fehlt"},
        ]))
        out_path = tmp_path / "e2e_verified.json"
        _run_gate([
            "--write-verdict", "BROKEN: AC-1 fehlgeschlagen",
            "--findings-json", str(findings),
            "--e2e-path", str(out_path),
        ])
        if out_path.exists():
            data = json.loads(out_path.read_text())
            assert not data.get("staging_verdict", "").startswith("VERIFIED"), (
                "BROKEN-Lauf darf kein VERIFIED-Artefakt hinterlassen"
            )

    def test_write_verdict_ambiguous_returns_exit0(self, tmp_path):
        """AMBIGUOUS → Exit 0 (kein harter Block, aber kein VERIFIED)."""
        findings = tmp_path / "findings.json"
        findings.write_text(json.dumps([]))
        out_path = tmp_path / "e2e_verified.json"
        rc, _, _ = _run_gate([
            "--write-verdict", "AMBIGUOUS: Screenshot nicht auswertbar",
            "--findings-json", str(findings),
            "--e2e-path", str(out_path),
        ])
        assert rc == 0, f"AMBIGUOUS soll Exit 0 liefern, bekam {rc}"


class TestDetectCommittedScope:
    """_detect_committed_scope() — wird intern von --check ohne --scope verwendet."""

    def test_scope_detection_returns_valid_string(self):
        """detect_scope muss einen der erwarteten Scope-Strings zurückgeben."""
        rc, out, err = _run_gate(["--detect-scope"])
        assert rc == 0, f"--detect-scope schlug fehl: {err}"
        scope = (out + err).strip().lower()
        valid_scopes = {"frontend-only", "backend", "full-stack", "docs-only"}
        assert any(s in scope for s in valid_scopes), (
            f"Unbekannter Scope-Wert: {scope!r}"
        )


class TestE2EVerifiedPersistence:
    """Regression-Tests: .claude/e2e_verified.json muss gitignored + untracked bleiben.

    Hintergrund: In e0c72c8 wurde die Datei aus dem Git-Index entfernt (Issue #525).
    Diese Tests stellen sicher, dass das Gate-Artefakt nie wieder versehentlich
    committed wird und dass git reset --hard es nicht loescht.
    """

    def test_e2e_verified_is_not_git_tracked(self):
        """AC-2: git ls-files --error-unmatch schlaegt fehl → Datei ist untracked."""
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".claude/e2e_verified.json"],
            cwd=str(REPO_DIR),
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            ".claude/e2e_verified.json ist im Git-Index — muss untracked bleiben "
            "(Sofortfix e0c72c8 wurde rueckgaengig gemacht?). "
            f"Ausgabe: {result.stderr}"
        )

    def test_e2e_verified_survives_git_reset_hard(self, tmp_path):
        """AC-1: git reset --hard loescht untracked+gitignored Dateien nicht."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=str(repo), check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=str(repo), check=True, capture_output=True,
        )
        gitignore = repo / ".gitignore"
        gitignore.write_text(".claude/e2e_verified.json\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=str(repo), check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(repo), check=True, capture_output=True,
        )
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        verified = claude_dir / "e2e_verified.json"
        verified.write_text('{"verified_commit": "abc123", "staging_verdict": "VERIFIED"}')
        subprocess.run(
            ["git", "reset", "--hard", "HEAD"],
            cwd=str(repo), check=True, capture_output=True,
        )
        assert verified.exists(), (
            ".claude/e2e_verified.json wurde durch git reset --hard geloescht — "
            "sie muss als untracked Datei erhalten bleiben."
        )
        content = verified.read_text()
        assert "abc123" in content, (
            f"Dateiinhalt wurde veraendert — erwartet 'abc123', bekam: {content!r}"
        )
