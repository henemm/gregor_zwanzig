"""
TDD RED: Bug #1353 — Post-Deploy-Selbsttest wertet JEDEN HTTP-302 als PASS,
auch wenn Prod unauthentifiziert auf die Login-Seite umleitet. Dadurch besteht
ein geschuetzter Endpoint den Selbsttest, ohne dass sein Akzeptanzkriterium
je geprueft wurde (`_probe_ac`, `.claude/hooks/prod_selftest.py:283`:
`ok = status in (200, 302)`).

Spec: docs/specs/modules/fix_1353_selftest_auth_redirect.md (AC-1..AC-5)
Vorbild-Testmuster: tests/tdd/test_prod_selftest_564.py
  -> TestFix2MethodNotAllowedYieldsSkip (lokaler HTTP-Server, Direktaufruf
     von `_probe_ac` per importlib, PROD_BASE per monkeypatch umgebogen).

AC-1 und AC-5 sind die eigentlichen RED-Repro-Tests: sie MUESSEN vor dem Fix
fehlschlagen. AC-2/AC-3/AC-4 sind Regressions-Anker fuer bestehendes
Verhalten und duerfen schon vor dem Fix gruen sein.

Netzfrei: nur echte lokale `ThreadingHTTPServer`-Instanzen (127.0.0.1,
Zufallsport) werden angesprochen -- kein Zugriff auf echtes Internet/Prod,
kein Mock/Patch der Probe-Logik selbst.
"""

import importlib.util as _importlib_util
import json
import shutil
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Issue #1327/#1228: repo-relative Auflösung statt Hauptrepo-Hartkodierung —
# das ausgeführte Script kommt aus dem AKTUELLEN Arbeitsverzeichnis (Worktree),
# nicht aus dem Hauptrepo hartkodiert (Muster test_prod_selftest_564.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
PROD_SELFTEST = _REPO_ROOT / ".claude" / "hooks" / "prod_selftest.py"


def _load_prod_selftest_module():
    """Laedt prod_selftest.py frisch per importlib (Muster
    test_prod_selftest_564.py) -- fuer Direktaufrufe von `_probe_ac`/
    `run_selftest` ohne Subprocess/echten Netzwerk-Rundlauf."""
    spec = _importlib_util.spec_from_file_location(
        "prod_selftest_direct_1353", str(PROD_SELFTEST)
    )
    assert spec is not None and spec.loader is not None
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_handler(status: int, location: str | None = None):
    """Baut eine BaseHTTPRequestHandler-Subklasse, die auf jedes GET mit
    `status` antwortet (optional inkl. Location-Header fuer Redirects)."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            self.send_response(status)
            if location is not None:
                self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # Ruhe im pytest-Output
            pass

    return _Handler


class _LocalServer:
    """Kontextmanager fuer einen lokalen ThreadingHTTPServer (Muster
    TestFix2MethodNotAllowedYieldsSkip aus test_prod_selftest_564.py)."""

    def __init__(self, handler_cls):
        self._handler_cls = handler_cls
        self.server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url = ""

    def __enter__(self) -> "_LocalServer":
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_cls)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"
        return self

    def __exit__(self, *exc_info):
        assert self.server is not None
        self.server.shutdown()
        self.server.server_close()
        assert self._thread is not None
        self._thread.join(timeout=5)


class TestAC1LoginRedirectMustNotPassSilently:
    """AC-1 (RED-Repro, MUSS vor dem Fix fehlschlagen): Ein geschuetzter
    Endpoint antwortet unauthentifiziert mit 302 -> /login. `_probe_ac` MUSS
    dafuer prod_status=SKIPPED_AUTH_REDIRECT liefern, nicht PASS.

    Aktueller Bug-Code (`_probe_ac`, Zeile ~283) wertet `status in (200, 302)`
    pauschal als PASS -- der Login-Redirect wird dabei nicht von einem
    echten inhaltlichen Redirect unterschieden.
    """

    def test_302_to_login_yields_skipped_auth_redirect_not_pass(self, monkeypatch):
        mod = _load_prod_selftest_module()
        handler_cls = _make_handler(302, location="/login")
        with _LocalServer(handler_cls) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            finding = {
                "ac": "AC-protected",
                "status": "PASS",
                "url": "https://staging.gregor20.henemm.com/trips:AC-protected",
                "evidence": "Geschuetzte Route, unauth 302 -> /login (Issue #1353)",
            }
            result = mod._probe_ac(finding)

        assert result["prod_status"] == "SKIPPED_AUTH_REDIRECT", (
            f"Bug #1353: erwartet prod_status=SKIPPED_AUTH_REDIRECT bei "
            f"302-Redirect auf die Login-Seite, bekam "
            f"{result.get('prod_status')!r}. Der aktuelle Code wertet JEDEN "
            f"302 pauschal als PASS (`ok = status in (200, 302)`), auch den "
            f"reinen Anmelde-Redirect -- das AC wurde nie inhaltlich geprueft."
        )


class TestAC2NonLoginRedirectStillPasses:
    """AC-2 (Regressions-Anker, darf gruen sein): Ein 302 auf ein Ziel
    UNGLEICH der Anmeldeseite bleibt PASS (echter inhaltlicher Redirect)."""

    def test_302_to_non_login_target_still_yields_pass(self, monkeypatch):
        mod = _load_prod_selftest_module()
        handler_cls = _make_handler(302, location="/app")
        with _LocalServer(handler_cls) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            finding = {
                "ac": "AC-redirect",
                "status": "PASS",
                "url": "https://staging.gregor20.henemm.com/old-path:AC-redirect",
                "evidence": "Echter inhaltlicher Redirect auf /app",
            }
            result = mod._probe_ac(finding)

        assert result["prod_status"] == "PASS", (
            f"Ein 302 auf ein Nicht-Login-Ziel (/app) muss weiterhin PASS "
            f"bleiben, bekam {result.get('prod_status')!r}."
        )


class TestAC3Http200StillPasses:
    """AC-3 (Regressions-Anker, darf gruen sein): 200 bleibt PASS."""

    def test_http_200_still_yields_pass(self, monkeypatch):
        mod = _load_prod_selftest_module()
        handler_cls = _make_handler(200)
        with _LocalServer(handler_cls) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            finding = {
                "ac": "AC-public",
                "status": "PASS",
                "url": "https://staging.gregor20.henemm.com/:AC-public",
                "evidence": "Oeffentliche Route antwortet 200",
            }
            result = mod._probe_ac(finding)

        assert result["prod_status"] == "PASS", (
            f"HTTP 200 muss weiterhin PASS liefern, bekam "
            f"{result.get('prod_status')!r}."
        )


class TestAC4Http401StillFails:
    """AC-4 (Regressions-Anker, darf gruen sein): 401 ohne Redirect bleibt
    FAIL (bestehender Anker aus #1197 -- Auth-Wall ohne Redirect ist
    weiterhin ein Fehler)."""

    def test_http_401_still_yields_fail(self, monkeypatch):
        mod = _load_prod_selftest_module()
        handler_cls = _make_handler(401)
        with _LocalServer(handler_cls) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            finding = {
                "ac": "AC-authwall",
                "status": "PASS",
                "url": "https://staging.gregor20.henemm.com/api/secret:AC-authwall",
                "evidence": "Auth-Wall ohne Redirect (#1197)",
            }
            result = mod._probe_ac(finding)

        assert result["prod_status"] == "FAIL", (
            f"HTTP 401 ohne Redirect muss weiterhin FAIL liefern, bekam "
            f"{result.get('prod_status')!r}."
        )


class TestAC5AllLoginRedirectsMustNotYieldPassVerdict:
    """AC-5 (RED-Repro, MUSS vor dem Fix fehlschlagen): Bestehen ALLE
    Findings ausschliesslich aus Login-Redirects, muss `run_selftest` Exit 0
    liefern (kein Deploy-Block), aber der Gesamt-Verdict darf NICHT "PASS"
    lauten, und der Bericht muss SKIPPED_AUTH_REDIRECT je Zeile zeigen --
    keine vorgetaeuschte Pruefung.

    Health-Check und Bot-Menue-Check (Phase 2/4 von `run_selftest`) werden
    per monkeypatch auf deterministische Stubs gelegt -- sie sind nicht
    Gegenstand dieses Bugs (der betrifft ausschliesslich die
    AC-Attestation/Verdict-Bildung in Phase 3) und wuerden sonst echtes
    Prod-/Telegram-Netz beruehren.
    """

    def test_all_login_redirects_exit0_but_verdict_not_pass(self, monkeypatch, tmp_path):
        mod = _load_prod_selftest_module()
        handler_cls = _make_handler(302, location="/login")

        workflow_name = "fix-1353-selftest-302-login-red"
        report_path = mod.REPO_DIR / "docs" / "artifacts" / workflow_name / "prod-selftest.md"

        with _LocalServer(handler_cls) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            monkeypatch.setattr(
                mod, "_check_health", lambda: (True, "stub ok (RED-Test #1353)")
            )
            monkeypatch.setattr(
                mod,
                "_check_bot_menu_prod",
                lambda: {
                    "check": "bot_menu",
                    "status": "SKIPPED",
                    "detail": "stub (RED-Test #1353)",
                },
            )

            head = mod._head_sha()
            e2e_data = {
                "verified_commit": head,
                "staging_verdict": "VERIFIED: 2/2 ACs gruen",
                "findings": [
                    {
                        "ac": "AC-1",
                        "status": "PASS",
                        "url": "https://staging.gregor20.henemm.com/trips:AC-1",
                        "evidence": "Geschuetzte Route",
                    },
                    {
                        "ac": "AC-2",
                        "status": "PASS",
                        "url": "https://staging.gregor20.henemm.com/compare:AC-2",
                        "evidence": "Geschuetzte Route",
                    },
                ],
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "scope": "frontend-only",
                "environment": "staging",
            }
            e2e_path = tmp_path / "e2e_verified.json"
            e2e_path.write_text(json.dumps(e2e_data, indent=2))

            try:
                rc = mod.run_selftest(e2e_path, workflow_name, scope="backend")
                content = report_path.read_text() if report_path.exists() else ""
            finally:
                shutil.rmtree(report_path.parent, ignore_errors=True)

        assert rc == 0, (
            f"Erwartet Exit 0 (kein Deploy-Block) bei ausschliesslich "
            f"Login-Redirect-Findings, bekam Exit {rc}."
        )
        assert "SKIPPED_AUTH_REDIRECT" in content, (
            f"Bug #1353: Bericht muss SKIPPED_AUTH_REDIRECT je Zeile zeigen "
            f"(kein vorgetaeuschter Pruef-Erfolg fuer Login-Redirects):\n{content}"
        )
        assert "**Verdict: PASS**" not in content, (
            f"Bug #1353: Gesamt-Verdict darf bei ausschliesslich "
            f"Login-Redirects NICHT PASS lauten (aktueller Code wertet "
            f"jeden 302 blind als PASS, dadurch faelschlich Gesamt-PASS):\n"
            f"{content}"
        )
