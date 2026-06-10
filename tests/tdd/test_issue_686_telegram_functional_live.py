"""
Issue #686 — Echte funktionale Telegram-Live-Tests.

Schließt die Lücke aus #672: Dort lief der einzige echte-Bot-Test (AC-5) immer
SKIPPED (keine GZ_TELEGRAM_TEST_CHAT_ID) und war nur ein Smoke. Hier wird die
funktionale Wirklichkeit bewiesen: jeder der 7 Menü-Befehle liefert sinnvollen
Inhalt (AC-3) und wird real zugestellt + wieder gelöscht (AC-4), die Test-Identität
ist reproduzierbar (AC-1), `send()` liefert die message_id (AC-2), und ein
übersprungener Telegram-Live-Test blockt das Close-Gate (AC-5).

KEINE Mocks: echter lokaler Socket (AC-2), echte Pipeline + echte Wetterdaten (AC-3),
echte Telegram-API (AC-4, gated).

Spec: docs/specs/modules/issue_686_telegram_functional_live_tests.md
"""
from __future__ import annotations

import http.server
import importlib.util
import json
import os
import socketserver
import sys
import threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest

# Die 7 Menü-Befehle (= BOT_COMMANDS in src/outputs/telegram.py)
SEVEN_COMMANDS = [
    "glance", "heute", "morgen", "heute_gewitter",
    "timeline_heute", "timeline_morgen", "hilfe",
]

REPO = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO / ".claude" / "hooks"


# ---------------------------------------------------------------------------
# Echter lokaler Socket — keine Mocks
# ---------------------------------------------------------------------------

def _make_handler(response_obj):
    class _H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps(response_obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            return

    return _H


@contextmanager
def _socket(response_obj):
    srv = socketserver.TCPServer(("127.0.0.1", 0), _make_handler(response_obj))
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------------------
# AC-2 — send() liefert die message_id (mock-frei, lokaler Socket)
# ---------------------------------------------------------------------------

def test_ac2_send_returns_message_id(monkeypatch):
    """
    GIVEN: ein erfolgreicher sendMessage (HTTP 200, ok=true, result.message_id=4242)
    WHEN: TelegramOutput.send() aufgerufen wird
    THEN: gibt es 4242 zurück (vorher None).
    """
    import outputs.telegram as tg
    from app.config import Settings

    resp = {"ok": True, "result": {"message_id": 4242, "date": 0,
                                    "chat": {"id": 999}, "text": "x"}}
    with _socket(resp) as base:
        monkeypatch.setattr(tg, "TELEGRAM_API_BASE", base)
        settings = Settings(telegram_bot_token="testtoken", telegram_chat_id="999")
        out = tg.TelegramOutput(settings)
        mid = out.send("Betreff", "Inhalt")

    assert mid == 4242, f"send() muss die message_id liefern, war: {mid!r}"


# ---------------------------------------------------------------------------
# AC-1 — Fixture stellt Test-User mit aktivem Trip sicher (idempotent)
# ---------------------------------------------------------------------------

def test_ac1_fixture_ensures_user_with_active_trip(tmp_path):
    """
    GIVEN: GZ_TELEGRAM_TEST_CHAT_ID + ein leeres data_dir
    WHEN: der Fixture-Helper läuft
    THEN: ein User mit telegram_chat_id == chat_id existiert, hat einen heute aktiven
          Trip, und ein zweiter Aufruf ist idempotent (gleiche user_id, keine Duplikate).
    """
    from tests.tdd._telegram_live_fixture import ensure_test_user_with_active_trip
    from app.loader import lookup_user_by_telegram_chat_id

    chat_id = "8346977700"
    data_dir = str(tmp_path)

    user_id = ensure_test_user_with_active_trip(chat_id=chat_id, data_dir=data_dir)
    assert user_id, "Fixture muss eine user_id liefern"
    assert lookup_user_by_telegram_chat_id(chat_id, data_dir=data_dir) == user_id

    # aktiver Trip vorhanden (heute überlappend)
    from tests.tdd._telegram_live_fixture import active_trip_for
    trip = active_trip_for(user_id=user_id, data_dir=data_dir)
    assert trip is not None, "Fixture-User muss einen aktiven Trip haben"
    assert trip.start_date <= date.today() <= trip.end_date

    # idempotent
    user_id2 = ensure_test_user_with_active_trip(chat_id=chat_id, data_dir=data_dir)
    assert user_id2 == user_id, "zweiter Aufruf muss dieselbe user_id liefern"
    users = sorted(p.name for p in Path(data_dir, "users").iterdir() if p.is_dir())
    assert users.count(user_id) == 1, "kein Daten-Duplikat"


# ---------------------------------------------------------------------------
# AC-3 — alle 7 Befehle erzeugen sinnvollen Inhalt (echte Pipeline)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID"),
    reason="GZ_TELEGRAM_TEST_CHAT_ID nicht gesetzt — Inhalts-Live-Test übersprungen",
)
def test_ac3_all_seven_commands_produce_meaningful_content():
    """
    GIVEN: aktive Test-Fixture (User + aktiver Trip) in der echten Umgebung (CWD-data)
    WHEN: jeder der 7 Menü-Befehle durch die echte Pipeline läuft (echte Wetterdaten)
    THEN: jede Antwort ist nicht leer, enthält weder 'Unbekannter Befehl' noch
          'Kein aktiver Trip'.

    Läuft gegen das CWD-`data`-Verzeichnis (get_data_dir ist CWD-relativ) — in der
    Validierung im Staging-Tree mit echten Wetter-Providern.
    """
    from tests.tdd._telegram_live_fixture import (
        ensure_test_user_with_active_trip,
        run_command_through_pipeline,
    )
    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]
    ensure_test_user_with_active_trip(chat_id=chat_id)

    # Nur echte Wetterdaten-Marker — keine Formatierungs-/Header-Strings
    _WEATHER_MARKERS = ("°C", "km/h", "mm", "🌤", "⛈", "🌧", "🌨", "☀", "🌥", "⚡",
                        "%", "Temp", "Wind", "Regen", "Schnee", "Gewitter")

    failures = []
    for cmd in SEVEN_COMMANDS:
        body = run_command_through_pipeline(command=cmd, chat_id=chat_id)
        if not body or not body.strip():
            failures.append(f"{cmd}: leere Antwort")
        elif "Unbekannter Befehl" in body:
            failures.append(f"{cmd}: 'Unbekannter Befehl'")
        elif "Kein aktiver Trip" in body:
            failures.append(f"{cmd}: 'Kein aktiver Trip'")
        elif "Keine Etappe geplant" in body:
            failures.append(f"{cmd}: 'Keine Etappe geplant' — Fixture-Trip hat keine heutige Etappe")
        elif "Kein Wetter-Snapshot" in body:
            failures.append(f"{cmd}: 'Kein Wetter-Snapshot' — kein echter Wetter-Inhalt")
        elif cmd != "hilfe" and not any(m in body for m in _WEATHER_MARKERS):
            failures.append(f"{cmd}: kein Wetter-Marker in Antwort (Schein-Grün?): {body[:80]!r}")
    assert not failures, "Befehle ohne sinnvollen Inhalt: " + "; ".join(failures)


# ---------------------------------------------------------------------------
# AC-4 — echte Zustellung + Cleanup gegen den echten Bot (gated)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not (os.environ.get("GZ_TELEGRAM_BOT_TOKEN") and os.environ.get("GZ_TELEGRAM_TEST_CHAT_ID")),
    reason="GZ_TELEGRAM_BOT_TOKEN + GZ_TELEGRAM_TEST_CHAT_ID nicht gesetzt — Live-Zustellung übersprungen",
)
def test_ac4_live_delivery_and_cleanup():
    """
    GIVEN: Staging-Bot-Token + Test-Chat-ID gesetzt
    WHEN: die Antwort jedes der 7 Befehle real an den Test-Chat gesendet wird
    THEN: jede Zustellung liefert eine message_id (≠ None) und wird danach per
          deleteMessage wieder entfernt (ok=True). Keine Mocks.
    """
    from tests.tdd._telegram_live_fixture import deliver_and_cleanup

    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]
    failures = []
    for cmd in SEVEN_COMMANDS:
        message_id, deleted = deliver_and_cleanup(command=cmd, chat_id=chat_id)
        if message_id is None:
            failures.append(f"{cmd}: keine message_id (nicht zugestellt)")
        elif not deleted:
            failures.append(f"{cmd}: deleteMessage fehlgeschlagen (Chat-Müll)")
    assert not failures, "Live-Zustellung/Cleanup fehlgeschlagen: " + "; ".join(failures)


# ---------------------------------------------------------------------------
# AC-5 — /e2e-verify blockt bei übersprungenem Telegram-Live-Test
# ---------------------------------------------------------------------------

def _load_e2e_hook():
    path = HOOKS_DIR / "e2e_telegram_live.py"
    spec = importlib.util.spec_from_file_location("e2e_telegram_live_686", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ac5_e2e_verify_blocks_on_skipped_telegram(monkeypatch):
    """
    GIVEN: ein Change, dessen Scope den Telegram-Pfad berührt, aber
           GZ_TELEGRAM_TEST_CHAT_ID fehlt
    WHEN: die /e2e-verify-Verankerung (e2e_telegram_live.gate) läuft
    THEN: Exit ≠ 0 (Nicht-bestanden) — SKIPPED zählt nicht als grün.
          Berührt der Scope Telegram NICHT, ist Exit 0 (sauberer Skip erlaubt).
    """
    mod = _load_e2e_hook()
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)

    rc_touch = mod.gate(scope_touches_telegram=True, env=dict(os.environ))
    assert rc_touch != 0, "Telegram-Scope ohne Test-Chat-ID muss Nicht-bestanden sein"

    rc_notouch = mod.gate(scope_touches_telegram=False, env=dict(os.environ))
    assert rc_notouch == 0, "Ohne Telegram-Scope ist ein Skip erlaubt"


# ---------------------------------------------------------------------------
# AC-5 (echtes Close-Gate) — write_verdict() verweigert das Verdict, wenn der
# committete Scope Telegram berührt und die Test-Chat-ID fehlt. Mock-frei:
# echtes temporäres git-Repo, monkeypatch nur für ENV + REPO_DIR-Attribut.
# ---------------------------------------------------------------------------

def _load_staging_gate():
    path = HOOKS_DIR / "staging_gate.py"
    spec = importlib.util.spec_from_file_location("staging_gate_686", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args):
    import subprocess
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, text=True)


def test_ac5_write_verdict_blocks_telegram_scope_without_chat_id(tmp_path, monkeypatch):
    """
    GIVEN: ein echtes git-Repo, dessen letzter Commit (HEAD~1..HEAD) eine Datei
           mit 'telegram' im Pfad ändert (= Telegram-Scope), und ein staging_gate,
           dessen REPO_DIR auf dieses Repo zeigt
    WHEN: write_verdict("VERIFIED: ...") aufgerufen wird
    THEN: OHNE GZ_TELEGRAM_TEST_CHAT_ID → Rückgabe 1 UND es entsteht KEIN out.json
          (Verdict verweigert — SKIPPED zählt nicht als grün).
          MIT GZ_TELEGRAM_TEST_CHAT_ID → Rückgabe 0 UND out.json existiert.

    Beweist, dass das echte Close-Gate (das deploy-gregor-prod.sh liest) bei
    Telegram-Scope ohne Test-Chat-ID hart blockt — kein kosmetisches Gate.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    # 1) harmloser Erst-Commit (damit HEAD~1 existiert)
    (repo / "README.md").write_text("hello\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")

    # 2) Commit, der den Telegram-Pfad berührt (Pfad genügt für die Heuristik)
    tg_file = repo / "src" / "outputs" / "telegram.py"
    tg_file.parent.mkdir(parents=True)
    tg_file.write_text("# touches telegram\n")
    _git(repo, "add", "src/outputs/telegram.py")
    _git(repo, "commit", "-m", "feat(telegram): touch")

    gate_mod = _load_staging_gate()
    monkeypatch.setattr(gate_mod, "REPO_DIR", repo)

    findings_path = tmp_path / "findings.json"
    findings_path.write_text("[]")
    out_path = tmp_path / "out.json"

    # OHNE Test-Chat-ID → Verdict verweigert, kein out.json
    monkeypatch.delenv("GZ_TELEGRAM_TEST_CHAT_ID", raising=False)
    rc_block = gate_mod.write_verdict("VERIFIED: test", findings_path, e2e_path=out_path)
    assert rc_block == 1, "Telegram-Scope ohne Test-Chat-ID muss write_verdict blocken (rc=1)"
    assert not out_path.exists(), "kein Verdict-Artefakt bei verweigertem Gate"

    # MIT Test-Chat-ID → Verdict geschrieben
    monkeypatch.setenv("GZ_TELEGRAM_TEST_CHAT_ID", "8346977700")
    rc_pass = gate_mod.write_verdict("VERIFIED: test", findings_path, e2e_path=out_path)
    assert rc_pass == 0, "mit gesetzter Test-Chat-ID muss das Verdict geschrieben werden (rc=0)"
    assert out_path.exists(), "Verdict-Artefakt muss bei bestandenem Gate existieren"
