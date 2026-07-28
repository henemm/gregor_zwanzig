"""
TDD RED: Bug #1367 — Post-Deploy-Selbsttest wertet 401/403 auf geschuetzten
Endpoints als Fehlschlag. Antwortet ein Endpoint unangemeldet korrekt mit
"Anmeldung erforderlich", faellt das in den Sammel-Zweig `else: FAIL`
(`_probe_ac`, `.claude/hooks/prod_selftest.py`) -> Verdict PARTIAL, Exit 1,
Issue-Close blockiert, obwohl der Deploy in Ordnung ist.

Spec: docs/specs/modules/fix_1367_selftest_auth_required.md (AC-1..AC-5)
Vorbild-Testmuster: tests/tdd/test_selftest_auth_redirect.py (#1353)
  -> lokaler ThreadingHTTPServer, Direktaufruf von `_probe_ac`/`run_selftest`
     per importlib, PROD_BASE per monkeypatch umgebogen.

AC-1/AC-3/AC-4/AC-5 sind RED-Repro-Tests: sie MUESSEN vor dem Fix fehlschlagen
(401/403 fallen heute in den Sammel-Zweig `else: FAIL`, wodurch auch der
Teil-Nachweis aus AC-4 vor dem Fix als PARTIAL statt PASS durchfaellt).
AC-2 (echte Fehler wie 404/500 bleiben FAIL) ist der einzige Regressions-Anker,
der schon vorher gruen ist.

Netzfrei: nur echte lokale `ThreadingHTTPServer`-Instanzen (127.0.0.1,
Zufallsport) werden angesprochen -- kein Zugriff auf echtes Internet/Prod,
kein Mock/Patch der Probe-Logik selbst.

AC-6/AC-7 der Spec (Worktree-Korrektheit der Pfadauflösung / Commit-Attestation
gegen die geteilte Deploy-Wurzel) sind PO-Entscheidung 2026-07-28 aus dieser
Umsetzung ausgegliedert (Sammel-Issue #1199) und hier bewusst NICHT getestet.
"""

import importlib.util as _importlib_util
import json
import shutil
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# Issue #1327/#1228: repo-relative Aufloesung statt Hauptrepo-Hartkodierung —
# das ausgefuehrte Script kommt aus dem AKTUELLEN Arbeitsverzeichnis (Worktree).
_REPO_ROOT = Path(__file__).resolve().parents[2]
PROD_SELFTEST = _REPO_ROOT / ".claude" / "hooks" / "prod_selftest.py"


def _load_prod_selftest_module():
    """Laedt prod_selftest.py frisch per importlib (Muster
    test_selftest_auth_redirect.py) -- fuer Direktaufrufe von `_probe_ac`/
    `run_selftest` ohne Subprocess/echten Netzwerk-Rundlauf."""
    spec = _importlib_util.spec_from_file_location(
        "prod_selftest_direct_1367", str(PROD_SELFTEST)
    )
    assert spec is not None and spec.loader is not None
    mod = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_handler(status: int, location: str | None = None):
    """Handler, der auf jedes GET mit `status` antwortet (optional inkl.
    Location-Header fuer Redirects)."""
    return _make_routed_handler({"*": (status, location)})


def _make_routed_handler(routes: dict[str, tuple[int, str | None]]):
    """Handler, der je nach Pfad unterschiedlich antwortet — noetig fuer
    gemischte Laeufe (ein Endpoint leitet zur Anmeldung um, ein anderer weist
    direkt ab). Schluessel '*' ist der Fallback."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (http.server API)
            status, location = routes.get(self.path, routes.get("*", (200, None)))
            self.send_response(status)
            if location is not None:
                self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):  # Ruhe im pytest-Output
            pass

    return _Handler


class _LocalServer:
    """Kontextmanager fuer einen lokalen ThreadingHTTPServer."""

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


def _finding(ac: str, path: str, evidence: str) -> dict:
    return {
        "ac": ac,
        "status": "PASS",
        "url": f"https://staging.gregor20.henemm.com{path}:{ac}",
        "evidence": evidence,
    }


def _run_selftest_with_routes(mod, monkeypatch, tmp_path, routes, findings, workflow):
    """Faehrt `run_selftest` gegen einen lokalen Server mit `routes`.

    Health-Check und Bot-Menue-Check (Phase 2/4) werden auf deterministische
    Stubs gelegt — sie sind nicht Gegenstand dieses Bugs (der betrifft die
    AC-Attestation/Verdict-Bildung in Phase 3) und wuerden sonst echtes
    Prod-/Telegram-Netz beruehren.

    Returns: (exit_code, report_content)
    """
    # Heutiger Stand: der Bericht landet unter mod.REPO_DIR (kein Worktree-Split
    # — AC-6/AC-7 sind ausgegliedert, s. Modul-Docstring).
    report_path = mod.REPO_DIR / "docs" / "artifacts" / workflow / "prod-selftest.md"

    with _LocalServer(_make_routed_handler(routes)) as server:
        monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
        monkeypatch.setattr(
            mod, "_check_health", lambda: (True, "stub ok (Test #1367)")
        )
        monkeypatch.setattr(
            mod,
            "_check_bot_menu_prod",
            lambda: {
                "check": "bot_menu",
                "status": "SKIPPED",
                "detail": "stub (Test #1367)",
            },
        )

        e2e_data = {
            "verified_commit": mod._head_sha(),
            "staging_verdict": f"VERIFIED: {len(findings)}/{len(findings)} ACs gruen",
            "findings": findings,
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "scope": "backend",
            "environment": "staging",
        }
        e2e_path = tmp_path / "e2e_verified.json"
        e2e_path.write_text(json.dumps(e2e_data, indent=2))

        try:
            rc = mod.run_selftest(e2e_path, workflow, scope="backend")
            content = report_path.read_text() if report_path.exists() else ""
        finally:
            shutil.rmtree(report_path.parent, ignore_errors=True)

    return rc, content


class TestAC1AuthRequiredIsNotAFailure:
    """AC-1 (RED-Repro, MUSS vor dem Fix fehlschlagen): Ein geschuetzter
    Endpoint antwortet unangemeldet mit 401 bzw. 403. `_probe_ac` MUSS dafuer
    prod_status=SKIPPED_AUTH_REQUIRED liefern statt FAIL, und der Selbsttest
    darf den Abschluss nicht allein deswegen blockieren (Exit 0)."""

    def test_http_401_yields_skipped_auth_required_not_fail(self, monkeypatch):
        mod = _load_prod_selftest_module()
        with _LocalServer(_make_handler(401)) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            result = mod._probe_ac(
                _finding("AC-protected", "/api/trips", "Geschuetzte Route, unauth 401")
            )

        assert result["prod_status"] == "SKIPPED_AUTH_REQUIRED", (
            f"Bug #1367: erwartet prod_status=SKIPPED_AUTH_REQUIRED bei HTTP 401 "
            f"(Endpoint liegt korrekt hinter der Anmelde-Schranke), bekam "
            f"{result.get('prod_status')!r}. Der aktuelle Code faengt 401 im "
            f"Sammel-Zweig `else: FAIL` ab und blockiert dadurch legitime Deploys."
        )

    def test_http_403_yields_skipped_auth_required_not_fail(self, monkeypatch):
        mod = _load_prod_selftest_module()
        with _LocalServer(_make_handler(403)) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            result = mod._probe_ac(
                _finding("AC-forbidden", "/api/settings", "Geschuetzte Route, unauth 403")
            )

        assert result["prod_status"] == "SKIPPED_AUTH_REQUIRED", (
            f"Bug #1367: erwartet prod_status=SKIPPED_AUTH_REQUIRED bei HTTP 403, "
            f"bekam {result.get('prod_status')!r}."
        )

    def test_all_auth_required_run_exits_zero(self, monkeypatch, tmp_path):
        mod = _load_prod_selftest_module()
        rc, content = _run_selftest_with_routes(
            mod,
            monkeypatch,
            tmp_path,
            routes={"*": (401, None)},
            findings=[
                _finding("AC-1", "/api/trips", "Geschuetzt"),
                _finding("AC-2", "/api/compare", "Geschuetzt"),
            ],
            workflow="fix-1367-selftest-auth-required-ac1",
        )

        assert rc == 0, (
            f"Bug #1367: ausschliesslich geschuetzte Endpoints (401) duerfen den "
            f"Abschluss nicht blockieren, bekam Exit {rc}. Bericht:\n{content}"
        )


class TestAC2RealErrorsStillFail:
    """AC-2 (Regressions-Anker): Die Ausnahme bleibt eng — nur 401/403 wird
    uebersprungen. Weggebrochene Route (404) und Serverfehler (5xx) bleiben
    FAIL, Gesamtnote PARTIAL, Exit 1."""

    def test_http_404_still_yields_fail(self, monkeypatch):
        mod = _load_prod_selftest_module()
        with _LocalServer(_make_handler(404)) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            result = mod._probe_ac(
                _finding("AC-gone", "/api/trips", "Route weggebrochen")
            )

        assert result["prod_status"] == "FAIL", (
            f"Eine weggebrochene Route (404) muss FAIL bleiben — auch auf einem "
            f"sonst geschuetzten Pfad, bekam {result.get('prod_status')!r}."
        )

    def test_http_500_still_yields_fail(self, monkeypatch):
        mod = _load_prod_selftest_module()
        with _LocalServer(_make_handler(500)) as server:
            monkeypatch.setattr(mod, "PROD_BASE", server.base_url)
            result = mod._probe_ac(
                _finding("AC-broken", "/api/trips", "Serverfehler")
            )

        assert result["prod_status"] == "FAIL", (
            f"Ein Serverfehler (500) muss FAIL bleiben, bekam "
            f"{result.get('prod_status')!r}."
        )

    def test_run_with_404_finding_is_partial_and_exits_one(self, monkeypatch, tmp_path):
        mod = _load_prod_selftest_module()
        rc, content = _run_selftest_with_routes(
            mod,
            monkeypatch,
            tmp_path,
            routes={"/api/trips": (401, None), "*": (404, None)},
            findings=[
                _finding("AC-1", "/api/trips", "Geschuetzt"),
                _finding("AC-2", "/api/weggebrochen", "Route weg"),
            ],
            workflow="fix-1367-selftest-auth-required-ac2",
        )

        assert "**Verdict: PARTIAL**" in content, (
            f"Ein 404-Finding muss die Gesamtnote auf PARTIAL druecken, "
            f"Bericht:\n{content}"
        )
        assert rc == 1, (
            f"Ein echter Fehlschlag (404) muss den Abschluss weiter blockieren "
            f"(Exit 1), bekam Exit {rc}."
        )


class TestAC3MixedAuthSkipsMustNotYieldPassVerdict:
    """AC-3 (RED-Repro, MUSS vor dem Fix fehlschlagen): Konnte kein einziges
    Kriterium inhaltlich geprueft werden, weil alle Endpoints nur die
    Anmelde-Schranke zeigten — teils als Weiterleitung (302 -> /login), teils
    als direkte Abweisung (401) — darf die Gesamtnote NICHT PASS lauten.

    Ohne gemeinsame Betrachtung beider Skip-Arten faellt genau diese MISCHUNG
    durch die `all(... == SKIPPED_AUTH_REDIRECT)`-Pruefung aus #1353 und gilt
    faelschlich als PASS — der Bug, den #1353 beseitigt hat, kaeme ueber die
    Hintertuer zurueck.
    """

    def test_mixed_redirect_and_required_is_not_pass(self, monkeypatch, tmp_path):
        mod = _load_prod_selftest_module()
        rc, content = _run_selftest_with_routes(
            mod,
            monkeypatch,
            tmp_path,
            routes={
                "/trips": (302, "/login"),
                "/api/trips": (401, None),
            },
            findings=[
                _finding("AC-1", "/trips", "Frontend-Route, Anmelde-Weiterleitung"),
                _finding("AC-2", "/api/trips", "API-Route, direkte Abweisung"),
            ],
            workflow="fix-1367-selftest-auth-required-ac3",
        )

        assert "**Verdict: PASS**" not in content, (
            f"Bug #1367: Eine MISCHUNG aus Anmelde-Weiterleitung und direkter "
            f"Abweisung darf nicht als PASS gelten — es wurde kein einziges "
            f"Kriterium inhaltlich geprueft. Bericht:\n{content}"
        )
        assert rc == 0, (
            f"Ein Lauf ohne inhaltlichen Nachweis blockiert nicht (Praezedenz "
            f"#1353), erwartet Exit 0, bekam Exit {rc}."
        )
        assert "kein inhaltlicher Prod-Nachweis" in content, (
            f"Bug #1367: Der Bericht muss benennen, dass kein inhaltlicher "
            f"Prod-Nachweis vorliegt. Bericht:\n{content}"
        )


class TestAC4PartialEvidenceCounts:
    """AC-4 (RED-Repro, MUSS vor dem Fix fehlschlagen): Ein Lauf mit
    erbrachtem Nachweis (200) und einem nicht pruefbaren Kriterium (401) gilt
    als bestanden, solange kein Kriterium fehlgeschlagen ist. Vor dem Fix
    zaehlt 401 als FAIL -> Verdict PARTIAL statt PASS."""

    def test_mix_of_200_and_401_is_pass_exit_zero(self, monkeypatch, tmp_path):
        mod = _load_prod_selftest_module()
        rc, content = _run_selftest_with_routes(
            mod,
            monkeypatch,
            tmp_path,
            routes={"/": (200, None), "/api/trips": (401, None)},
            findings=[
                _finding("AC-1", "/", "Oeffentliche Route, inhaltlich geprueft"),
                _finding("AC-2", "/api/trips", "Geschuetzt"),
            ],
            workflow="fix-1367-selftest-auth-required-ac4",
        )

        assert "**Verdict: PASS**" in content, (
            f"Ein erbrachter inhaltlicher Nachweis (200) neben einem nicht "
            f"pruefbaren Kriterium (401) muss PASS ergeben. Bericht:\n{content}"
        )
        assert rc == 0, f"Erwartet Exit 0, bekam Exit {rc}."


class TestAC5ReportDistinguishesSkipReasons:
    """AC-5 (RED-Repro, MUSS vor dem Fix fehlschlagen): Im Bericht muss
    ablesbar bleiben, WARUM ein Kriterium nicht geprueft werden konnte —
    Weiterleitung zur Anmeldung und direkte Abweisung sind unterscheidbar."""

    def test_report_shows_both_skip_kinds_distinctly(self, monkeypatch, tmp_path):
        mod = _load_prod_selftest_module()
        _rc, content = _run_selftest_with_routes(
            mod,
            monkeypatch,
            tmp_path,
            routes={
                "/trips": (302, "/login"),
                "/api/trips": (401, None),
            },
            findings=[
                _finding("AC-1", "/trips", "Frontend-Route, Anmelde-Weiterleitung"),
                _finding("AC-2", "/api/trips", "API-Route, direkte Abweisung"),
            ],
            workflow="fix-1367-selftest-auth-required-ac5",
        )

        assert "SKIPPED_AUTH_REDIRECT" in content, (
            f"Der Bericht muss die Anmelde-Weiterleitung als eigene Statusangabe "
            f"ausweisen. Bericht:\n{content}"
        )
        assert "SKIPPED_AUTH_REQUIRED" in content, (
            f"Bug #1367: Der Bericht muss die direkte Abweisung als eigene, von "
            f"der Weiterleitung unterscheidbare Statusangabe ausweisen. "
            f"Bericht:\n{content}"
        )
