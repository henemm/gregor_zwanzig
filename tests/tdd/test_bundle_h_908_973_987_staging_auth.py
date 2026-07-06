"""TDD RED — Bündel H: Staging-Basic-Auth-Nachrüstung (Issues #908, #973, #987).

Seit dem nginx-Basic-Auth-Rollout auf Staging (henemm-infra #159, 28.06.2026)
schlagen diverse Test-/Gate-Läufe gegen https://staging.gregor20.henemm.com mit
401 fehl, weil weder Testdateien noch die Playwright-Staging-Config noch
prod_selftest.py's Prod-Probe Basic-Auth-Credentials mitsenden.

RED-Treiber (was jetzt fehlschlägt):
- AC-1: `tests/helpers/staging_auth.py` existiert nicht → ImportError.
- AC-2: `playwright.staging.config.ts` hat kein httpCredentials → Setup-Login 401
        (separat als echter `npx playwright`-Subprozess-Lauf bewiesen, siehe
        docs/artifacts/fix-908-973-987-staging-auth/playwright-setup-red.txt).
- AC-3: Radar-Trigger-Call ohne Auth (analog test_issue_830) → 401.
- AC-4: prod_selftest.py hat noch keinen pfadbasierten Skip für
        Mail-Preview-Test-Trip-URLs → beide synthetischen Findings landen als
        FAIL/PARTIAL, "SKIPPED_PREVIEW_TEST_TRIP" taucht nirgends im Bericht auf.

Mock-frei: echte HTTP-Calls gegen Staging/Prod, echter Subprozess-Lauf von
prod_selftest.py (Muster: tests/tdd/test_prod_selftest_730.py).

SPEC: docs/specs/modules/fix_908_973_987_staging_auth.md

Bewusst NICHT Teil dieser Spec: das 500-Problem am Radar-Debug-Trigger
(separater, potenziell eigener Produkt-Bug) — der Trigger-Call in AC-3 prüft
nur, dass KEIN 401 mehr auftritt, nicht dass der Endpoint 200 liefert.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

REPO_DIR = Path("/home/hem/gregor_zwanzig")
_VALIDATOR_ENV = REPO_DIR / ".claude" / "validator.env"

# Diese Testdatei liegt unter <worktree>/tests/tdd/... — parents[2] ist die
# Worktree-Wurzel. WICHTIG: prod_selftest.py wird bewusst aus dem WORKTREE
# geladen, NICHT aus dem Hauptrepo (REPO_DIR). Grund: Der Hauptrepo-Pfad
# .claude/hooks/prod_selftest.py wird von anderen, parallel laufenden
# Claude-Sessions jederzeit mutiert/zurückgesetzt (mehrfach beobachtet in
# diesem Workflow — der F003-Fix verschwand wiederholt aus der Hauptrepo-Kopie).
# Die Worktree-Kopie ist dagegen stabil: sie steht unter exklusiver Kontrolle
# dieser Session und ist zusätzlich durch den worktree_write_guard-Hook vor
# Fremdzugriff geschützt. REPO_DIR bleibt für _head_sha()/_make_e2e_verified()
# unverändert das Hauptrepo — das ist konsistent, weil prod_selftest.py intern
# selbst ein hartcodiertes REPO_DIR = Path("/home/hem/gregor_zwanzig") für den
# Commit-Ancestor-Check und den Report-Pfad verwendet. Nur das LADEN der
# Codedatei selbst erfolgt aus der stabilen Worktree-Kopie.
WORKTREE_DIR = Path(__file__).resolve().parents[2]
HOOKS_DIR = WORKTREE_DIR / ".claude" / "hooks"
PROD_SELFTEST = HOOKS_DIR / "prod_selftest.py"


def _load_prod_selftest_module():
    """Lädt prod_selftest.py als Modul (direkter Aufruf statt Subprozess), damit
    `scope` explizit übergeben werden kann — die automatische Scope-Erkennung
    haengt am *tatsaechlichen* letzten Commit des Hauptrepos (git diff HEAD~1..HEAD)
    und wuerde hier faelschlich 'docs-only' liefern (Selftest wuerde ungetestet
    uebersprungen), da der zuletzt gemergte Commit nur docs/tests aendert.

    Geladen wird bewusst aus HOOKS_DIR (Worktree-Kopie, siehe Kommentar oben),
    NICHT aus dem Hauptrepo: die Hauptrepo-Kopie kann von parallelen Sessions
    jederzeit mutiert werden, die Worktree-Kopie ist stabil und wird exklusiv
    von dieser Session verwaltet."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("prod_selftest", PROD_SELFTEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_validator_env() -> dict:
    env = {}
    for line in _VALIDATOR_ENV.read_text().splitlines():
        line = line.strip().removeprefix("export ").strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


_ENV = _load_validator_env()
STAGING_BASE = os.environ.get("GZ_SVELTE_BASE") or _ENV.get(
    "GZ_VALIDATION_URL", "https://staging.gregor20.henemm.com"
)
TRIGGER_PATH = "/api/debug/trigger-radar-alert"


# ============================================================================
# AC-1: Zentraler Helper liefert Credentials, die echt authentifizieren
# ============================================================================

class TestAC1CentralHelperAuthenticates:
    """AC-1: tests/helpers/staging_auth.py liefert gültige Basic-Auth-Credentials."""

    def test_helper_credentials_return_200_instead_of_401(self):
        from tests.helpers.staging_auth import httpx_auth  # noqa: PLC0415

        resp = httpx.get(f"{STAGING_BASE}/api/health", auth=httpx_auth(), timeout=15.0)
        assert resp.status_code == 200, (
            f"Erwartet HTTP 200 mit Helper-Credentials, aber {resp.status_code}. "
            f"Body: {resp.text[:200]}"
        )


# ============================================================================
# AC-3: Betroffene Testdatei (test_issue_830) — kein 401 mehr mit Helper-Auth
# ============================================================================

class TestAC3RadarTriggerNoLonger401:
    """AC-3: Repräsentativ für die 6 betroffenen Testdateien — Radar-Trigger-Call
    mit Helper-Auth wird nicht mehr durch fehlende Basic-Auth blockiert.

    Bewusst KEIN Assert auf 200 — der Endpoint hat laut #987 einen separaten,
    aus dem Scope ausgeklammerten 500-Bug. Diese Spec beweist nur "kein 401
    mehr wegen fehlender Nginx-Basic-Auth".
    """

    def test_trigger_call_with_helper_auth_is_not_401(self):
        from tests.helpers.staging_auth import httpx_auth  # noqa: PLC0415

        resp = httpx.post(
            f"{STAGING_BASE}{TRIGGER_PATH}",
            params={"user_id": "default"},
            auth=httpx_auth(),
            timeout=30.0,
        )
        assert resp.status_code != 401, (
            f"Trigger-Call ist weiterhin 401 trotz Helper-Auth — Basic-Auth-Fix "
            f"greift nicht. Body: {resp.text[:300]}"
        )


# ============================================================================
# AC-4: prod_selftest.py — pfadbasierter Skip für Mail-Preview-Test-Trips
# ============================================================================

def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(REPO_DIR)
    )
    return result.stdout.strip()


def _run_selftest(e2e_path, workflow: str):
    """Realer Aufruf von run_selftest() mit scope='full-stack' erzwungen (siehe
    _load_prod_selftest_module-Docstring) — echtes HTTP gegen echtes Prod,
    echter Report auf Platte, nur die Scope-Auto-Erkennung wird umgangen."""
    module = _load_prod_selftest_module()
    rc = module.run_selftest(Path(e2e_path), workflow, scope="full-stack")
    return rc, "", ""


def _make_e2e_verified(tmp_path, findings):
    data = {
        "verified_commit": _head_sha(),
        "staging_verdict": "VERIFIED: ACs grün",
        "findings": findings,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "full-stack",
        "environment": "staging",
    }
    json_file = tmp_path / "e2e_verified.json"
    json_file.write_text(json.dumps(data, indent=2))
    return json_file


_PREVIEW_TEST_TRIP_FINDING = {
    "ac": "AC-1",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/api/preview/e2e-908-test/email:AC-1",
    "evidence": "Mail-Preview für Staging-Test-Trip via Playwright verifiziert",
}

_PREVIEW_REAL_TRIP_FINDING = {
    "ac": "AC-2",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/api/preview/some-real-trip-908/email:AC-2",
    "evidence": "Mail-Preview für regulären (Nicht-Test-)Trip",
}

# Regression (Adversary-Finding F003): Erst-Implementierung kannte nur das
# Suffix '-test' und matchte per startswith() jeden Sub-Pfad unter
# /api/preview/<trip>/* — nicht nur /email. Die folgenden zwei Findings decken
# genau diese beiden Lücken ab.

_PREVIEW_TDD_SUFFIX_TRIP_FINDING = {
    "ac": "AC-4-TDD-SUFFIX",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/api/preview/some-trip-908-tdd/email:AC-4",
    "evidence": "Mail-Preview für Staging-Test-Trip mit '-tdd'-Suffix (nicht '-test')",
}

_PREVIEW_TEST_SUFFIX_NON_EMAIL_PATH_FINDING = {
    "ac": "AC-4-PATH-RESTRICTION",
    "status": "PASS",
    "url": "https://staging.gregor20.henemm.com/api/preview/e2e-908-test/sms:AC-4",
    "evidence": "Test-Trip-Suffix, aber SMS- statt Mail-Preview-Pfad",
}


class TestAC4ProdSelftestSkipsPreviewTestTrip:
    """AC-4: Mail-Preview-Test-Trip-Finding wird als eigener Skip markiert und
    löst kein PARTIAL aus — ein Nicht-Test-Trip-Preview-Finding bleibt hingegen
    PARTIAL (Regressionsschutz gegen zu großzügigen Skip)."""

    def test_test_trip_preview_marked_skipped_not_partial(self, tmp_path):
        e2e = _make_e2e_verified(tmp_path, findings=[_PREVIEW_TEST_TRIP_FINDING])
        rc, out, err = _run_selftest(e2e, workflow="bundle-h-908-ac4-skip")
        report = REPO_DIR / "docs" / "artifacts" / "bundle-h-908-ac4-skip" / "prod-selftest.md"
        assert report.exists(), f"Bericht fehlt: {report}"
        content = report.read_text()
        assert "SKIPPED_PREVIEW_TEST_TRIP" in content, (
            f"Test-Trip-Preview-Finding nicht als SKIPPED_PREVIEW_TEST_TRIP markiert:\n{content}"
        )
        assert "Verdict: PARTIAL" not in content, (
            f"Test-Trip-Preview-Finding hat fälschlich PARTIAL ausgelöst:\n{content}"
        )
        assert rc == 0, f"Erwartet Exit 0, aber {rc}\nstdout: {out}\nstderr: {err}"

    def test_non_test_trip_preview_still_partial_regression_guard(self, tmp_path):
        e2e = _make_e2e_verified(tmp_path, findings=[_PREVIEW_REAL_TRIP_FINDING])
        rc, out, err = _run_selftest(e2e, workflow="bundle-h-908-ac4-regression")
        report = REPO_DIR / "docs" / "artifacts" / "bundle-h-908-ac4-regression" / "prod-selftest.md"
        assert report.exists(), f"Bericht fehlt: {report}"
        content = report.read_text()
        assert "SKIPPED_PREVIEW_TEST_TRIP" not in content, (
            f"Nicht-Test-Trip-Preview-Finding wurde fälschlich geskippt:\n{content}"
        )
        assert "PARTIAL" in content, (
            f"Regressionsschutz verletzt — Nicht-Test-Trip-Preview-Finding sollte "
            f"weiterhin PARTIAL auslösen:\n{content}"
        )
        assert rc == 1, f"Erwartet Exit 1 (PARTIAL), aber {rc}\nstdout: {out}\nstderr: {err}"

    def test_tdd_suffix_trip_preview_marked_skipped(self, tmp_path):
        """Regression F003: '-tdd' ist eines von drei bekannten Test-Trip-Suffixen
        (neben '-test' und '-adv-test') — die Erst-Implementierung kannte nur
        '-test' und hätte dieses Finding fälschlich NICHT geskippt."""
        e2e = _make_e2e_verified(tmp_path, findings=[_PREVIEW_TDD_SUFFIX_TRIP_FINDING])
        rc, out, err = _run_selftest(e2e, workflow="bundle-h-908-ac4-tdd-suffix")
        report = REPO_DIR / "docs" / "artifacts" / "bundle-h-908-ac4-tdd-suffix" / "prod-selftest.md"
        assert report.exists(), f"Bericht fehlt: {report}"
        content = report.read_text()
        assert "SKIPPED_PREVIEW_TEST_TRIP" in content, (
            f"'-tdd'-Suffix-Trip nicht als SKIPPED_PREVIEW_TEST_TRIP erkannt "
            f"(Regression zur Erst-Implementierung mit nur einem Suffix '-test'):\n{content}"
        )
        assert "Verdict: PARTIAL" not in content, (
            f"'-tdd'-Suffix-Trip hat fälschlich PARTIAL ausgelöst:\n{content}"
        )
        assert rc == 0, f"Erwartet Exit 0, aber {rc}\nstdout: {out}\nstderr: {err}"

    def test_test_trip_suffix_but_non_email_path_stays_partial(self, tmp_path):
        """Regression F003: Die Erst-Implementierung matchte per
        `startswith('/api/preview/')` JEDEN Sub-Pfad, nicht nur `/email` — ein
        SMS-Preview-Pfad mit Test-Trip-Suffix wäre fälschlich mitgeskippt worden.
        Die Spec schränkt den Skip exakt auf den Mail-Kanal ein."""
        e2e = _make_e2e_verified(
            tmp_path, findings=[_PREVIEW_TEST_SUFFIX_NON_EMAIL_PATH_FINDING]
        )
        rc, out, err = _run_selftest(e2e, workflow="bundle-h-908-ac4-path-restriction")
        report = (
            REPO_DIR / "docs" / "artifacts" / "bundle-h-908-ac4-path-restriction"
            / "prod-selftest.md"
        )
        assert report.exists(), f"Bericht fehlt: {report}"
        content = report.read_text()
        assert "SKIPPED_PREVIEW_TEST_TRIP" not in content, (
            f"Test-Trip-Suffix auf Nicht-/email-Pfad wurde fälschlich geskippt "
            f"(Pfad-Einschränkung auf /email verletzt):\n{content}"
        )
        assert "PARTIAL" in content, (
            f"Pfad-Einschränkung verletzt — SMS-Pfad mit Test-Trip-Suffix sollte "
            f"weiterhin PARTIAL auslösen:\n{content}"
        )
        assert rc == 1, f"Erwartet Exit 1 (PARTIAL), aber {rc}\nstdout: {out}\nstderr: {err}"
