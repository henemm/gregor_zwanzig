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
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

# Dialt real gegen Staging/Prod (#1211 Scheibe 2a) -- nur via -m staging ausfuehren.
pytestmark = pytest.mark.staging


# Issue #1327/#1228: repo-relative Auflösung statt Hauptrepo-Hartkodierung —
# das ausgeführte Script kommt aus dem AKTUELLEN Arbeitsverzeichnis (Worktree),
# nicht aus dem Hauptrepo hartkodiert (Muster
# test_staging_gate_verdict_merge.py:31-32). Ein hartkodierter Hauptrepo-Pfad
# würde bei Worktree-Isolation die UNVERÄNDERTE Hauptrepo-Kopie testen statt
# der hier bearbeiteten Datei (Fix 1/Fix 2/Fix 5 blieben sonst rot). REPO_DIR
# bleibt bewusst der Hauptrepo-Pfad — das Script selbst hat sein REPO_DIR
# (Attestation/Report-Ablage, HEAD-Ermittlung) fest auf den Hauptrepo verdrahtet
# (geteilte Attestation, Produktion wird nur von dort deployt), unabhängig
# davon, welche Dateikopie ausgeführt wird.
#
# _load_prod_selftest_module/_head_sha/_make_e2e_verified/
# _init_evidence_free_repo sind seit Issue #1196 S1 AC-10 (PO-Korrektur
# 2026-08-03) nach tests/tdd/conftest.py verschoben (geteilter Ort mit
# tests/tdd/test_fix_853_842_837_tooling_gates.py, das dieselben Helfer ohne
# den `staging`-Modul-Marker dieser Datei braucht) und werden von dort
# zurückimportiert -- keine Neudefinition, ein Ort.
from tests.tdd.conftest import (  # noqa: E402
    PROD_SELFTEST,
    REPO_DIR,
    _init_evidence_free_repo,
    _load_prod_selftest_module,
    _make_e2e_verified,
)

PROD_BASE = "https://gregor20.henemm.com"


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
    """Fix #1382 löst #564 AC-5 TEILWEISE ab: fehlender Nachweis blockiert
    jetzt (Exit 1) UND schreibt einen Bericht, sofern der Scope NICHT
    docs-only ist — echter Code wurde dann ausgerollt, ohne dass irgendein
    Nachweis (exakt oder Ancestor) vorliegt. Der docs-only-Teil von AC-5
    bleibt unverändert gültig (Exit 0, kein Bericht — reiner
    Doku-/Tooling-Deploy, kein Code in Prod), s.
    test_docs_only_scope_with_missing_evidence_still_exits_zero.

    Direktaufruf von run_selftest() mit explizitem ``scope=`` statt über
    den Subprozess-Helfer _run_selftest(): das Skript ermittelt den Scope
    sonst selbst gegen das ECHTE Hauptrepo (REPO_DIR ist dort fest
    verdrahtet, keine --scope-CLI-Option existiert) — am aktuellen HEAD
    steht das faktisch auf 'docs-only' und der Kurzschluss (run_selftest,
    Scope-Check) greift, bevor die Nachweis-Logik überhaupt erreicht wird.
    Zusätzlich wird ``REPO_DIR`` für die drei 'kein Nachweis'-Fälle per
    Monkeypatch auf ein isoliertes, evidenzfreies Repo umgebogen (s.
    _init_evidence_free_repo) — sonst fände die Ancestor-Suche reale
    Attestationen im echten Hauptrepo und der Test würde je nach dessen
    Zustand zufällig PASS statt FAIL liefern (PO-Befund 2026-07-26)."""

    def test_exit1_when_e2e_verified_missing_and_scope_not_docs_only(
        self, tmp_path, monkeypatch
    ):
        """Fix #1382 (löst #564 AC-5 teilweise ab): Fehlendes e2e_verified.json
        bei explizit nicht-docs-only Scope UND ohne jeden Vorfahren-Nachweis
        → Exit 1 statt wie bisher Exit 0. Vorher: test_exit0_when_e2e_verified_missing,
        erwartete Exit 0 (das von #564 AC-5 festgelegte, für diesen Fall jetzt
        abgelöste Verhalten)."""
        mod = _load_prod_selftest_module()
        root = tmp_path / "repo"
        _init_evidence_free_repo(root)
        monkeypatch.setattr(mod, "REPO_DIR", root)
        non_existent = root / ".claude" / "e2e_verified" / "does_not_exist.json"

        rc = mod.run_selftest(non_existent, "issue-564-ac5-no-file", scope="backend")

        assert rc == 1, (
            f"Erwartet Exit 1 bei fehlendem Nachweis (weder exakt noch Vorfahre) "
            f"und Nicht-docs-only-Scope (Fix #1382 löst #564 AC-5 teilweise ab), "
            f"aber Exit {rc}"
        )

    def test_fail_message_when_e2e_verified_missing_and_scope_not_docs_only(
        self, tmp_path, monkeypatch, capfd
    ):
        """Ersetzt die alte INFO-Meldung (test_info_message_when_e2e_verified_missing):
        bei Nicht-docs-only-Scope und fehlendem Nachweis ist die Meldung jetzt
        eine FAIL-Meldung, die klar benennt, dass kein Nachweis vorlag."""
        mod = _load_prod_selftest_module()
        root = tmp_path / "repo"
        _init_evidence_free_repo(root)
        monkeypatch.setattr(mod, "REPO_DIR", root)
        non_existent = root / ".claude" / "e2e_verified" / "does_not_exist.json"

        capfd.readouterr()
        rc = mod.run_selftest(non_existent, "issue-564-ac5-fail-message", scope="backend")
        combined = "".join(capfd.readouterr())

        assert rc == 1
        assert "FAIL" in combined
        assert any(
            kw in combined.lower() for kw in ["kein nachweis", "keine attestation"]
        ), f"Meldung muss erklären, dass kein Nachweis vorlag:\n{combined}"

    def test_report_written_when_e2e_verified_missing_and_scope_not_docs_only(
        self, tmp_path, monkeypatch
    ):
        """Ersetzt test_no_report_written_when_e2e_verified_missing: die neue
        Regel (Fix #1382, AC-7) schreibt jetzt EINEN Bericht, der den
        fehlenden Nachweis erklärt — das genaue Gegenteil der alten
        Erwartung 'kein Bericht'."""
        mod = _load_prod_selftest_module()
        root = tmp_path / "repo"
        _init_evidence_free_repo(root)
        monkeypatch.setattr(mod, "REPO_DIR", root)
        non_existent = root / ".claude" / "e2e_verified" / "does_not_exist.json"
        workflow_name = "issue-564-ac5-report-on-missing-evidence"
        report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

        rc = mod.run_selftest(non_existent, workflow_name, scope="backend")

        assert rc == 1
        assert report_path.exists(), (
            f"Fix #1382 (AC-7): bei fehlendem Nachweis und Nicht-docs-only-Scope "
            f"MUSS jetzt ein Bericht geschrieben werden: {report_path}"
        )
        content = report_path.read_text()
        assert "FAIL" in content
        assert any(
            kw in content.lower() for kw in ["kein nachweis", "keine attestation"]
        ), f"Bericht muss erklären, dass kein Nachweis vorlag:\n{content}"

    def test_docs_only_scope_with_missing_evidence_still_exits_zero(
        self, tmp_path, monkeypatch
    ):
        """Weiterhin gültiger Teil von #564 AC-5 (NICHT abgelöst): docs-only
        Scope + fehlender Nachweis → Exit 0, kein Bericht (reiner
        Doku-/Tooling-Deploy, kein Code in Prod — der Scope-Check läuft vor
        der Nachweis-Logik und greift unverändert, unabhängig davon, ob im
        Repo Attestationen existieren)."""
        mod = _load_prod_selftest_module()
        root = tmp_path / "repo"
        _init_evidence_free_repo(root)
        monkeypatch.setattr(mod, "REPO_DIR", root)
        non_existent = root / ".claude" / "e2e_verified" / "does_not_exist.json"
        workflow_name = "issue-564-ac5-docs-only-still-exit0"
        report_path = root / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

        rc = mod.run_selftest(non_existent, workflow_name, scope="docs-only")

        assert rc == 0, "Docs-only-Scope + fehlender Nachweis muss weiterhin Exit 0 liefern"
        assert not report_path.exists(), "Docs-only-Skip darf keinen Bericht schreiben"


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


class TestFix1FreetextUrlSkippedWithoutHttpCall:
    """RED (#1327/#1228 Fix 1, AC-1): Ein Finding mit Freitext-`url` ohne
    führendes 'http(s)://' oder '/' (z.B. 'compareMetricDefs.ts/ALL_METRICS')
    muss VOR jeder Host-Konkatenation als SKIPPED_NO_URL erkannt werden —
    kein `_http_get`-Aufruf gegen den aus der Konkatenation entstehenden
    Fantasie-Host (`_staging_to_prod_url` baut sonst
    'https://gregor20.henemm.comcompareMetricDefs.ts/ALL_METRICS').

    Netzfrei: `_probe_ac` wird direkt (kein Subprocess) aufgerufen; `_http_get`
    wird per monkeypatch durch einen Sensor ersetzt, der bei Aufruf sofort
    fehlschlägt (Nachweis "kein Netzwerk-Request", statt auf einen echten
    DNS-Fehler zu warten).
    """

    def test_freetext_url_yields_skipped_no_url_without_http_call(self, monkeypatch):
        mod = _load_prod_selftest_module()
        calls: list[str] = []

        def _forbidden_http_get(url, follow_redirects=False):
            calls.append(url)
            raise AssertionError(
                f"_http_get haette fuer eine Freitext-URL nicht aufgerufen "
                f"werden duerfen: {url}"
            )

        monkeypatch.setattr(mod, "_http_get", _forbidden_http_get)

        finding = {
            "ac": "AC-compare",
            "status": "PASS",
            "url": "compareMetricDefs.ts/ALL_METRICS",
            "evidence": "Freitext statt echter URL (Issue #1327)",
        }
        result = mod._probe_ac(finding)

        assert result["prod_status"] == "SKIPPED_NO_URL", (
            f"Erwartet prod_status=SKIPPED_NO_URL fuer Freitext-URL, bekam "
            f"{result.get('prod_status')!r} (prod_url={result.get('prod_url')!r})"
        )
        assert calls == [], (
            f"_http_get wurde trotz Freitext-URL aufgerufen (kaputter "
            f"Fantasie-Host): {calls}"
        )


class TestFix2MethodNotAllowedYieldsSkip:
    """RED (#1327/#1228 Fix 2, AC-2): Eine GET-Probe, die HTTP 405 liefert
    (POST-only-Endpoint), muss prod_status=SKIPPED_METHOD_NOT_PROBEABLE
    ergeben — nicht FAIL — und darf den Gesamt-Verdict allein nicht auf
    PARTIAL/FAIL ziehen.

    Netzfrei: echter lokaler `ThreadingHTTPServer` (Vorbild
    test_issue_1142_geosphere_direct_fallback.py) liefert 405 auf GET;
    `PROD_BASE` wird testseitig per monkeypatch auf den lokalen Server
    umgebogen (Modul-Import statt Subprocess, damit die Modul-Konstante
    ueberschreibbar ist).
    """

    class _MethodNotAllowedHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            self.send_response(405)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # Ruhe im pytest-Output
            pass

    def test_405_get_response_yields_skipped_method_not_probeable(self, monkeypatch):
        mod = _load_prod_selftest_module()

        server = ThreadingHTTPServer(("127.0.0.1", 0), self._MethodNotAllowedHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            monkeypatch.setattr(mod, "PROD_BASE", f"http://{host}:{port}")
            finding = {
                "ac": "AC-register",
                "status": "PASS",
                "url": "https://staging.gregor20.henemm.com/api/auth/register:AC-register",
                "evidence": "POST-only Endpoint (Issue #1228)",
            }
            result = mod._probe_ac(finding)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        assert result["prod_http"] == 405, (
            f"Erwartet prod_http=405, bekam {result.get('prod_http')!r}"
        )
        assert result["prod_status"] == "SKIPPED_METHOD_NOT_PROBEABLE", (
            f"Erwartet prod_status=SKIPPED_METHOD_NOT_PROBEABLE bei HTTP 405, "
            f"bekam {result.get('prod_status')!r}"
        )
        verdict = mod._derive_verdict([result])
        assert verdict not in ("PARTIAL", "FAIL"), (
            f"Ein 405-Finding allein darf den Gesamt-Verdict nicht auf "
            f"{verdict} ziehen (bekam {verdict!r})."
        )


class TestFix5ReportPathGzActiveWorkflowFallback:
    """RED (#1327/#1228 Fix 5, AC-6): Ist OPENSPEC_ACTIVE_WORKFLOW NICHT
    gesetzt, aber GZ_ACTIVE_WORKFLOW schon (Legacy-Fallback, analog
    prod_send_gate.py), und wird kein --workflow-Arg übergeben, muss der
    Bericht unter docs/artifacts/<GZ_ACTIVE_WORKFLOW>/prod-selftest.md
    landen — nicht unter docs/artifacts/unknown/.

    Bestandscode kennt in main() nur OPENSPEC_ACTIVE_WORKFLOW als Env-Quelle
    (Zeile ~670) und faellt bei dessen Fehlen direkt auf 'unknown' zurueck,
    obwohl die Logzeile faelschlich von GZ_ACTIVE_WORKFLOW spricht.
    """

    def test_falls_back_to_gz_active_workflow_when_openspec_unset(self, tmp_path):
        workflow_name = "issue-1327-legacy-fallback"
        e2e = _make_e2e_verified(tmp_path)
        _run_selftest(
            e2e_path=e2e,
            env_override={
                "OPENSPEC_ACTIVE_WORKFLOW": "",
                "GZ_ACTIVE_WORKFLOW": workflow_name,
            },
        )

        report_path = REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"
        unknown_path = REPO_DIR / "docs" / "artifacts" / "unknown" / "prod-selftest.md"
        assert report_path.exists(), (
            f"Bericht nicht unter dem GZ_ACTIVE_WORKFLOW-Fallback-Pfad "
            f"gefunden: {report_path}. Aktueller Code kennt nur "
            f"OPENSPEC_ACTIVE_WORKFLOW als Quelle und faellt direkt auf "
            f"'unknown' zurueck (unknown_path exists={unknown_path.exists()})."
        )
