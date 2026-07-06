"""
prod_selftest Bot-Menü-Wächter umgebungsunabhängig machen (Issue #685).

Folge-Härtung aus #671: Der Post-Deploy-Menü-Check (`check_bot_menu`, AC-4 von
#671) meldet in Produktion immer `SKIPPED — BOT_COMMANDS nicht ladbar`, weil der
Deploy `prod_selftest.py` mit System-`python3` startet und `_load_bot_commands()`
dort `from output.channels.telegram import BOT_COMMANDS` macht → `outputs/__init__.py`
zieht `sms → app.config → pydantic`, das fehlt → ModuleNotFoundError → None.

Fix: BOT_COMMANDS dependency-frei per `ast.literal_eval` aus der Quelldatei lesen.

ACs:
  - AC-1: _load_bot_commands() liefert die 7 Befehle auch wenn `pydantic` NICHT
          importierbar ist (echte Deploy-Bedingung im Subprozess reproduziert).
  - AC-2: Live-Menü == BOT_COMMANDS → check_bot_menu PASS (nicht SKIPPED).
  - AC-3: Abweichung → FAIL + Fazit-Text nennt FAIL statt „PARTIAL" (F001).
  - AC-4: Nicht-parsebare Quelle → None (fail-soft) → Menü-Check SKIPPED.

Spec: docs/specs/modules/issue_685_selftest_menu_gate.md
GitHub Issue: #685
KEINE Mocks — echter Subprozess mit real blockiertem pydantic + echter Socket.
"""
from __future__ import annotations

import http.server
import importlib.util
import json
import os
import socketserver
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

HOOKS_DIR = Path(".claude/hooks").resolve()
PS_PATH = (HOOKS_DIR / "prod_selftest.py").resolve()

EXPECTED_COMMANDS = [
    "glance", "heute", "morgen", "now", "heute_gewitter",
    "timeline_heute", "timeline_morgen", "hilfe",
]


def _load_prod_selftest():
    """prod_selftest.py als Modul laden (Hooks-Dir auf sys.path für `import _e2e_paths`)."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("prod_selftest_685", str(PS_PATH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Echter lokaler getMyCommands-Socket — keine Mocks
# ---------------------------------------------------------------------------

def _make_handler(get_result):
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = json.dumps({"ok": True, "result": get_result()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    return _Handler


@contextmanager
def _menu_server(get_result):
    srv = socketserver.TCPServer(("127.0.0.1", 0), _make_handler(get_result))
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()


def _cmds(names):
    return [{"command": n, "description": f"desc-{n}"} for n in names]


# ---------------------------------------------------------------------------
# AC-1 — BOT_COMMANDS laden OHNE importierbares pydantic (Deploy-Bedingung)
# ---------------------------------------------------------------------------

def test_ac1_load_bot_commands_without_pydantic(tmp_path):
    """
    GIVEN: ein Python-Interpreter, in dem `pydantic` NICHT importierbar ist
           (reproduziert den System-`python3` des Deploys via meta_path-Blocker)
    WHEN: _load_bot_commands() in diesem Subprozess läuft
    THEN: es liefert die 7 BOT_COMMANDS (command-Namen), nicht None,
          ohne ModuleNotFoundError — weil es per AST aus der Quelle liest.
    """
    # sitecustomize blockiert pydantic-Import hart → echte gebrochene Umgebung.
    blocker_dir = tmp_path / "noenv"
    blocker_dir.mkdir()
    (blocker_dir / "sitecustomize.py").write_text(
        "import sys\n"
        "class _Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'pydantic' or name.startswith('pydantic.'):\n"
        "            raise ModuleNotFoundError(\"No module named 'pydantic'\")\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
    )

    code = (
        "import importlib.util, json, sys\n"
        f"sys.path.insert(0, {str(HOOKS_DIR)!r})\n"
        f"spec = importlib.util.spec_from_file_location('ps685', {str(PS_PATH)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "res = mod._load_bot_commands()\n"
        "print(json.dumps([c['command'] for c in res] if res else None))\n"
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = str(blocker_dir) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, timeout=60,
    )

    # Sicherstellen, dass pydantic im Subprozess wirklich blockiert war
    sanity = subprocess.run(
        [sys.executable, "-c", "import pydantic"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert sanity.returncode != 0 and "pydantic" in sanity.stderr, (
        "Testumgebung ungueltig: pydantic war NICHT blockiert"
    )

    assert proc.returncode == 0, f"Subprozess-Fehler: {proc.stderr}"
    loaded = json.loads(proc.stdout.strip().splitlines()[-1])
    assert loaded == EXPECTED_COMMANDS, (
        f"_load_bot_commands() ohne pydantic lieferte {loaded!r}, "
        f"erwartet {EXPECTED_COMMANDS}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Menü-Check meldet PASS bei Live-Übereinstimmung
# ---------------------------------------------------------------------------

def test_ac2_menu_check_pass_when_live_matches():
    """
    GIVEN: Live-Menü (echter Socket) == die geladenen BOT_COMMANDS
    WHEN: check_bot_menu() gegen den Socket läuft
    THEN: status == PASS (der Wächter greift, nicht SKIPPED).
    """
    ps = _load_prod_selftest()
    expected = ps._load_bot_commands()
    assert expected is not None, "_load_bot_commands() darf hier nicht None sein"

    with _menu_server(get_result=lambda: expected) as base:
        finding = ps.check_bot_menu("tok", expected, api_base=base)

    assert finding.get("status") == "PASS", f"erwartet PASS, war: {finding!r}"


# ---------------------------------------------------------------------------
# AC-3 — Abweichung → FAIL + Fazit-Text nennt FAIL (F001)
# ---------------------------------------------------------------------------

def test_ac3_menu_fail_report_text_is_fail():
    """
    GIVEN: Live-Menü weicht ab (alter briefing/wetter-Stand)
    WHEN: check_bot_menu() das feststellt UND _render_full_report mit
          verdict="FAIL" gerendert wird
    THEN: check_bot_menu status FAIL, und der Bericht-Fazit nennt FAIL,
          nicht „PARTIAL".
    """
    ps = _load_prod_selftest()
    expected = ps._load_bot_commands()

    with _menu_server(get_result=lambda: _cmds(["briefing", "wetter"])) as base:
        finding = ps.check_bot_menu("tok", expected, api_base=base)
    assert finding.get("status") == "FAIL", f"erwartet FAIL, war: {finding!r}"

    # F001: Bericht-Fazit bei verdict=FAIL darf nicht „PARTIAL" sagen.
    probes = [{"ac": "AC-1", "status": "SKIPPED"}]
    report = ps._render_full_report("wf", "deadbeef" * 5, "HTTP 200", "FAIL", probes)
    assert "## Fazit" in report
    fazit = report.split("## Fazit", 1)[1]
    assert "FAIL" in fazit, f"Fazit-Text nennt FAIL nicht: {fazit!r}"
    assert "PARTIAL" not in fazit, (
        f"Fazit-Text sagt faelschlich PARTIAL bei verdict=FAIL: {fazit!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Nicht-parsebare Quelle → None (fail-soft) → SKIPPED
# ---------------------------------------------------------------------------

def test_ac4_load_bot_commands_unparseable_returns_none(tmp_path, monkeypatch):
    """
    GIVEN: die BOT_COMMANDS-Quelle ist nicht literal-auswertbar / fehlt
    WHEN: _load_bot_commands() aufgerufen wird
    THEN: es gibt None zurück (kein Crash) und der Menü-Check meldet SKIPPED.
    """
    ps = _load_prod_selftest()

    # REPO_DIR auf ein leeres Verzeichnis umbiegen → src/outputs/telegram.py fehlt.
    monkeypatch.setattr(ps, "REPO_DIR", tmp_path)
    result = ps._load_bot_commands()
    assert result is None, f"erwartet None bei fehlender Quelle, war: {result!r}"

    # _check_bot_menu_prod muss dann SKIPPED melden (kein falscher PASS).
    finding = ps._check_bot_menu_prod()
    assert finding.get("status") == "SKIPPED", f"erwartet SKIPPED, war: {finding!r}"
