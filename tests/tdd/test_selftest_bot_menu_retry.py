"""TDD RED — Issue #3219: Prod-Selbsttest, Bot-Menü-Prüfung tolerant gegen
Telegram-Hänger.

Spec: docs/specs/modules/fix_3219_selftest_botmenue_timeout.md (AC-1 … AC-7).

Vorfall 2026-11-20: ein einziger Menü-Abruf mit 8 s Zeitlimit hing einmal,
der Selbsttest meldete "Regression in Produktion" (Exit 1), obwohl
Produktion intakt war. Soll: eigenes Zeitlimit (`MENU_TIMEOUT`), bis zu
`MENU_ATTEMPTS` Versuche mit wachsender Pause (`MENU_RETRY_PAUSE`, dann
doppelt), Wiederholung nur bei Zeitüberschreitung/Netzfehler und HTTP
429/5xx. Bleibt Telegram stumm: eigener Status `UNREACHABLE` (nie PASS,
nie FAIL), eigene Fazit-Zeile, Exit-Code unverändert.

KEINE Mocks für den geprüften Weg: echter lokaler HTTP-Socket-Server mit
skriptbarem, zählendem Handler (Muster test_issue_685_selftest_menu_gate.py).
Konstanten werden per monkeypatch klein gesetzt, damit der Lauf schnell
bleibt. Im End-to-End-Lauf von `run_selftest` werden nur die fachfremden
Umgebungs-Proben (Health, Tote-Trips-Wächter) ersetzt; die Menü-Prüfung
läuft als echte `check_bot_menu` gegen den lokalen Server.
"""
from __future__ import annotations

import http.server
import json
import socketserver
import threading
import time
from contextlib import contextmanager

import pytest

from tests.tdd.conftest import (
    _init_evidence_free_repo,
    _load_prod_selftest_module,
    _make_e2e_verified,
)

# Klein gesetzte Testwerte (Spec: "per monkeypatch klein").
T_TIMEOUT = 0.3
T_PAUSE = 0.05
T_ATTEMPTS = 3
# Wie lange ein "hängender" Request höchstens festgehalten wird. Bewusst
# deutlich länger als T_TIMEOUT: wer das Menü-Zeitlimit nicht nutzt (z. B.
# weiter PROBE_TIMEOUT = 8 s), wartet sichtbar länger als die Toleranz.
HANG_SECONDS = 5.0

EXPECTED = [
    {"command": "start", "description": "Start"},
    {"command": "hilfe", "description": "Hilfe"},
    {"command": "wetter", "description": "Wetter"},
]


# ---------------------------------------------------------------------------
# Echter lokaler getMyCommands-Server mit Drehbuch und Zähler
# ---------------------------------------------------------------------------

class _Script:
    """Drehbuch je Anfrage-Nummer (0-basiert). Der letzte Eintrag gilt für
    alle weiteren Anfragen. Einträge:
      ("hang",)                 -> Antwort zurückhalten (Zeitüberschreitung)
      ("json", status, payload) -> HTTP-Status + JSON-Body
      ("raw", status, bytes)    -> HTTP-Status + roher Body
    """

    def __init__(self, steps):
        self.steps = list(steps)
        self.count = 0
        self.lock = threading.Lock()
        self.release = threading.Event()

    def next_step(self):
        with self.lock:
            idx = self.count
            self.count += 1
        return self.steps[min(idx, len(self.steps) - 1)]


def _make_handler(script: _Script):
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            step = script.next_step()
            kind = step[0]
            if kind == "hang":
                script.release.wait(HANG_SECONDS)
                return  # ohne Antwort schließen
            status = step[1]
            if kind == "json":
                body = json.dumps(step[2]).encode("utf-8")
            else:
                body = step[2]
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass

        def log_message(self, *args):
            return

    return _Handler


class _ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = True


@contextmanager
def _menu_server(steps):
    script = _Script(steps)
    srv = _ThreadingServer(("127.0.0.1", 0), _make_handler(script))
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}", script
    finally:
        script.release.set()
        srv.shutdown()
        srv.server_close()


def _ok(commands):
    return ("json", 200, {"ok": True, "result": commands})


def _wrong_menu():
    return _ok([{"command": "briefing", "description": "alt"}])


@pytest.fixture
def ps(monkeypatch):
    mod = _load_prod_selftest_module()
    # raising=False: in der RED-Phase existieren die Konstanten noch nicht;
    # der Test soll dann am Verhalten scheitern, nicht am Setzen.
    monkeypatch.setattr(mod, "MENU_TIMEOUT", T_TIMEOUT, raising=False)
    monkeypatch.setattr(mod, "MENU_ATTEMPTS", T_ATTEMPTS, raising=False)
    monkeypatch.setattr(mod, "MENU_RETRY_PAUSE", T_PAUSE, raising=False)
    return mod


# Obergrenze der Laufzeit im Dauer-Hänger-Fall mit den Testwerten:
# 3 × Zeitlimit + Pausen (0,05 + 0,10) + großzügige Toleranz, aber klar
# unter HANG_SECONDS (wer 8 s PROBE_TIMEOUT nutzt, reißt das).
MAX_ALL_HANG = T_ATTEMPTS * T_TIMEOUT + T_PAUSE + 2 * T_PAUSE + 1.5


def _run_selftest_with_menu(ps, monkeypatch, tmp_path, base, workflow):
    """End-to-End-Lauf von `run_selftest`; die Menü-Prüfung ist die echte
    `check_bot_menu` gegen den lokalen Server. Ersetzt werden nur Health und
    Tote-Trips-Wächter (Umgebungsproben ohne Bezug zu #3219). Die Findings
    sind attestiert SKIPPED, damit keine AC-Probe ins Netz geht."""
    root = tmp_path / "repo"
    head = _init_evidence_free_repo(root)
    monkeypatch.setattr(ps, "REPO_DIR", root)
    monkeypatch.setattr(ps, "_check_health", lambda: (True, "stub ok (Test #3219)"))
    monkeypatch.setattr(
        ps,
        "check_dead_trips_guard",
        lambda **kwargs: {"check": "dead_trips_guard", "status": "PASS", "detail": "ok"},
    )
    monkeypatch.setattr(
        ps, "_check_bot_menu_prod", lambda: ps.check_bot_menu("tok", EXPECTED, api_base=base)
    )
    findings = [
        {"ac": "AC-1", "status": "SKIPPED", "evidence": "Backend-AC ohne HTTP"},
    ]
    e2e_path = _make_e2e_verified(tmp_path, verified_commit=head, findings=findings)
    rc = ps.run_selftest(e2e_path, workflow, scope="backend", explicit_path=True)
    report = (root / "docs" / "artifacts" / workflow / "prod-selftest.md").read_text()
    return rc, report


# ---------------------------------------------------------------------------
# AC-1 — ein Hänger, dann richtiges Menü -> PASS, genau 2 Abrufe, Exit 0
# ---------------------------------------------------------------------------

def test_ac1_single_hang_then_correct_menu_is_pass(ps):
    """GIVEN Telegram hängt beim ersten Abruf und liefert beim zweiten das
    Soll-Menü / WHEN check_bot_menu läuft / THEN PASS nach genau 2 Abrufen,
    und das Warten richtet sich nach MENU_TIMEOUT, nicht nach PROBE_TIMEOUT."""
    with _menu_server([("hang",), _ok(EXPECTED)]) as (base, script):
        t0 = time.monotonic()
        finding = ps.check_bot_menu("tok", EXPECTED, api_base=base)
        elapsed = time.monotonic() - t0

    assert finding["status"] == "PASS", f"erwartet PASS nach Wiederholung, war: {finding!r}"
    assert script.count == 2, f"erwartet genau 2 Abrufe, waren {script.count}"
    assert elapsed < T_TIMEOUT + T_PAUSE + 1.5, (
        f"Menü-Abruf wartete {elapsed:.2f}s — das eigene Menü-Zeitlimit greift nicht"
    )


def test_ac1_single_hang_end_to_end_exit_zero(ps, monkeypatch, tmp_path):
    """AC-1 im echten run_selftest-Rundlauf: Exit 0, Bot-Menü PASS."""
    with _menu_server([("hang",), _ok(EXPECTED)]) as (base, script):
        rc, report = _run_selftest_with_menu(ps, monkeypatch, tmp_path, base, "wf-3219-ac1")

    assert rc == 0, f"einmaliger Telegram-Hänger darf nicht Exit 1 geben, bekam {rc}:\n{report}"
    assert "Status: **PASS**" in report, f"Bot-Menü-Abschnitt nicht PASS:\n{report}"
    assert script.count == 2


# ---------------------------------------------------------------------------
# AC-2 — dauerhaft stumm -> UNREACHABLE, Fazit-Zeile, keine Regression, Exit 0
# ---------------------------------------------------------------------------

def test_ac2_all_attempts_hang_is_unreachable_never_pass(ps):
    with _menu_server([("hang",)]) as (base, script):
        finding = ps.check_bot_menu("tok", EXPECTED, api_base=base)

    assert finding["status"] == "UNREACHABLE", (
        f"dauerhaft stummes Telegram muss UNREACHABLE sein, war: {finding!r}"
    )
    assert finding["status"] != "PASS"
    assert script.count == T_ATTEMPTS, f"erwartet {T_ATTEMPTS} Abrufe, waren {script.count}"
    assert "nicht erreichbar" in finding["detail"], finding
    assert str(T_ATTEMPTS) in finding["detail"], (
        f"Detail muss die Versuchszahl nennen: {finding['detail']!r}"
    )


def test_ac2_all_hang_end_to_end_report_and_exit(ps, monkeypatch, tmp_path):
    with _menu_server([("hang",)]) as (base, script):
        rc, report = _run_selftest_with_menu(ps, monkeypatch, tmp_path, base, "wf-3219-ac2")

    assert rc == 0, f"Telegram-Ausfall ist keine Deploy-Regression, Exit muss 0 sein, war {rc}"
    assert "**Verdict: FAIL**" not in report, report
    assert "Status: **UNREACHABLE**" in report, f"Menü-Status fehlt im Bericht:\n{report}"
    fazit = report.split("## Fazit", 1)[1]
    assert "Regression in Produktion" not in fazit, (
        f"Fazit behauptet eine Regression, obwohl nur Telegram stumm war:\n{fazit}"
    )
    assert "Telegram nicht erreichbar" in fazit, f"Nicht-erreichbar-Zeile fehlt:\n{fazit}"
    assert "Bot-Menü nicht belegt" in fazit, fazit
    assert "keine Regression belegt" in fazit, fazit
    assert script.count == T_ATTEMPTS


# ---------------------------------------------------------------------------
# AC-3 — 429/5xx werden wiederholt; dauerhaft -> UNREACHABLE; 502 dann 200 -> PASS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", [503, 429, 500])
def test_ac3_persistent_429_or_5xx_is_unreachable(ps, code):
    with _menu_server([("json", code, {"ok": False, "description": "busy"})]) as (base, script):
        finding = ps.check_bot_menu("tok", EXPECTED, api_base=base)

    assert finding["status"] == "UNREACHABLE", (
        f"HTTP {code} dauerhaft muss UNREACHABLE sein, war: {finding!r}"
    )
    assert script.count == T_ATTEMPTS, f"HTTP {code}: erwartet {T_ATTEMPTS} Abrufe, waren {script.count}"


def test_ac3_502_then_correct_menu_is_pass(ps):
    with _menu_server([("json", 502, {"ok": False}), _ok(EXPECTED)]) as (base, script):
        finding = ps.check_bot_menu("tok", EXPECTED, api_base=base)

    assert finding["status"] == "PASS", f"502 dann 200 muss PASS sein, war: {finding!r}"
    assert script.count == 2, f"erwartet genau 2 Abrufe, waren {script.count}"


# ---------------------------------------------------------------------------
# AC-4 — falsches Menü -> FAIL ohne Wiederholung, Exit 1, Regression im Fazit
# ---------------------------------------------------------------------------

def test_ac4_wrong_menu_is_fail_without_retry(ps):
    with _menu_server([_wrong_menu()]) as (base, script):
        finding = ps.check_bot_menu("tok", EXPECTED, api_base=base)

    assert finding["status"] == "FAIL", finding
    assert script.count == 1, f"falsches Menü darf nicht wiederholt werden, Abrufe: {script.count}"


def test_ac4_wrong_menu_end_to_end_exit_one(ps, monkeypatch, tmp_path):
    with _menu_server([_wrong_menu()]) as (base, script):
        rc, report = _run_selftest_with_menu(ps, monkeypatch, tmp_path, base, "wf-3219-ac4")

    assert rc == 1, f"echtes Menü-Abweichen muss Exit 1 bleiben, war {rc}"
    assert "**Verdict: FAIL**" in report
    fazit = report.split("## Fazit", 1)[1]
    assert "Regression in Produktion" in fazit, fazit
    assert "Telegram nicht erreichbar" not in fazit, (
        f"bei echtem Menü-Fehler darf keine Nicht-erreichbar-Zeile stehen:\n{fazit}"
    )
    assert script.count == 1


# ---------------------------------------------------------------------------
# AC-5 — ungültiger Token / Müll-Body / ok:false -> FAIL ohne Wiederholung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "step",
    [
        ("json", 401, {"ok": False, "error_code": 401, "description": "Unauthorized"}),
        ("json", 404, {"ok": False, "error_code": 404, "description": "Not Found"}),
        ("raw", 200, b"<html>kein json</html>"),
        ("json", 200, {"ok": False, "description": "irgendwas"}),
    ],
    ids=["401", "404", "garbage-body", "ok-false"],
)
def test_ac5_config_errors_are_fail_without_retry(ps, step):
    with _menu_server([step]) as (base, script):
        finding = ps.check_bot_menu("tok", EXPECTED, api_base=base)

    assert finding["status"] == "FAIL", f"{step[:2]}: erwartet FAIL, war {finding!r}"
    assert script.count == 1, f"{step[:2]}: keine Wiederholung erlaubt, Abrufe: {script.count}"


# ---------------------------------------------------------------------------
# AC-6 — PROBE_TIMEOUT bleibt 8 und gilt ohne timeout; ohne Token SKIPPED
# ---------------------------------------------------------------------------

def test_ac6_probe_timeout_unchanged():
    mod = _load_prod_selftest_module()
    assert mod.PROBE_TIMEOUT == 8


def test_ac6_http_get_without_timeout_uses_probe_timeout(monkeypatch):
    mod = _load_prod_selftest_module()
    monkeypatch.setattr(mod, "PROBE_TIMEOUT", T_TIMEOUT)
    with _menu_server([("hang",)]) as (base, _script):
        t0 = time.monotonic()
        with pytest.raises(OSError):
            mod._http_get(f"{base}/x")
        elapsed = time.monotonic() - t0
    assert elapsed < T_TIMEOUT + 1.5, f"_http_get ignorierte PROBE_TIMEOUT ({elapsed:.2f}s)"


def test_ac6_http_get_explicit_timeout_overrides(monkeypatch):
    """Der neue optionale `timeout`-Parameter von `_http_get` gilt, wenn
    gesetzt; PROBE_TIMEOUT bleibt für alle anderen Aufrufer unverändert."""
    mod = _load_prod_selftest_module()
    assert mod.PROBE_TIMEOUT == 8
    with _menu_server([("hang",)]) as (base, _script):
        t0 = time.monotonic()
        with pytest.raises(OSError):
            mod._http_get(f"{base}/x", timeout=T_TIMEOUT)
        elapsed = time.monotonic() - t0
    assert elapsed < T_TIMEOUT + 1.5, f"explizites timeout griff nicht ({elapsed:.2f}s)"


def test_ac6_no_token_still_skipped(ps):
    with _menu_server([_ok(EXPECTED)]) as (base, script):
        finding = ps.check_bot_menu("", EXPECTED, api_base=base)
    assert finding["status"] == "SKIPPED", finding
    assert script.count == 0


# ---------------------------------------------------------------------------
# AC-7 — Laufzeit-Obergrenze
# ---------------------------------------------------------------------------

def test_ac7_default_constants_bound_42_seconds():
    mod = _load_prod_selftest_module()
    assert getattr(mod, "MENU_TIMEOUT", None) == 12
    assert getattr(mod, "MENU_ATTEMPTS", None) == 3
    assert getattr(mod, "MENU_RETRY_PAUSE", None) == 2
    pauses = sum(mod.MENU_RETRY_PAUSE * (2 ** i) for i in range(mod.MENU_ATTEMPTS - 1))
    assert mod.MENU_ATTEMPTS * mod.MENU_TIMEOUT + pauses <= 42


def test_ac7_measured_duration_all_hang_within_bound(ps):
    with _menu_server([("hang",)]) as (base, script):
        t0 = time.monotonic()
        finding = ps.check_bot_menu("tok", EXPECTED, api_base=base)
        elapsed = time.monotonic() - t0

    assert finding["status"] == "UNREACHABLE", finding
    assert script.count == T_ATTEMPTS
    assert elapsed <= MAX_ALL_HANG, (
        f"Dauer-Hänger brauchte {elapsed:.2f}s, Obergrenze {MAX_ALL_HANG:.2f}s"
    )
    # Pausen wurden tatsächlich eingehalten (nicht null): mindestens
    # 3 Zeitlimits + Pausen 0,05 + 0,10.
    assert elapsed >= T_ATTEMPTS * T_TIMEOUT + 3 * T_PAUSE - 0.05, (
        f"Dauer-Hänger zu schnell ({elapsed:.2f}s) — Zeitlimit/Pause nicht eingehalten"
    )
