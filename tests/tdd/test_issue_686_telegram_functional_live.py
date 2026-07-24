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
import threading
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pytest

from tests.tdd._telegram_live_fixture import live_telegram_enabled

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
    import output.channels.telegram as tg
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

@pytest.mark.real_data_root
@pytest.mark.skipif(
    not live_telegram_enabled(),
    reason="GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)",
)
def test_ac3_all_seven_commands_produce_meaningful_content():
    """
    GIVEN: aktive Test-Fixture (User + aktiver Trip) in der echten Umgebung (CWD-data)
    WHEN: jeder der 7 Menü-Befehle durch die echte Pipeline läuft (echte Wetterdaten)
    THEN: jede Antwort ist nicht leer, enthält weder 'Unbekannter Befehl' noch
          'Kein aktiver Trip'.

    Issue #1007 (PO-Semantik ab 2026-07-04): heute/morgen lösen nicht mehr den
    Einzeiler aus, sondern den vollen Voll-Briefing-Versand über den Scheduler
    (kein Wetter-Marker mehr im Pipeline-Rückgabewert — die Bestätigung IST
    „…-Briefing wird gesendet."). Der reale Beweis für diese beiden Befehle ist
    ein frischer briefing_log-Eintrag mit Kanal telegram (echter Dispatch, siehe
    docs/specs/modules/issue_1007_heute_voll_briefing.md). Die anderen fünf
    Befehle bleiben streng auf echte Wetter-Marker geprüft.

    Läuft gegen das CWD-`data`-Verzeichnis (get_data_dir ist CWD-relativ) — in der
    Validierung im Staging-Tree mit echten Wetter-Providern.
    """
    from tests.tdd._telegram_live_fixture import (
        TEST_USER_ID,
        _delete_snapshot,
        _ensure_weather_snapshot,
        active_trip_for,
        ensure_test_user_with_active_trip,
        run_command_through_pipeline,
    )
    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]
    ensure_test_user_with_active_trip(chat_id=chat_id)

    # Issue #1007: heute/morgen fassen die "aktuelle" (heute+morgen kombinierte)
    # Momentaufnahme seit dem Adversary-Fix nicht mehr an (trip_report_scheduler
    # ._send_trip_report_outcome überspringt save()/save_dated() im On-Demand-
    # Modus — siehe test_snapshot_bleibt_kombiniert_nach_heute). Trotzdem hier
    # defensiv eine frische kombinierte Momentaufnahme erzwingen, damit die
    # Lesebefehle unabhängig vom Zustand eines vorherigen Testlaufs prüfbar sind.
    trip = active_trip_for(user_id=TEST_USER_ID)
    assert trip is not None, "Fixture-Trip muss nach ensure_test_user... existieren"
    _delete_snapshot(user_id=TEST_USER_ID, trip_id=trip.id, data_dir="data")
    _ensure_weather_snapshot(trip, TEST_USER_ID)

    # Nur echte Wetterdaten-Marker — keine Formatierungs-/Header-Strings
    _WEATHER_MARKERS = ("°C", "km/h", "mm", "🌤", "⛈", "🌧", "🌨", "☀", "🌥", "⚡",
                        "%", "Temp", "Wind", "Regen", "Schnee", "Gewitter")
    _ON_DEMAND_CMDS = ("heute", "morgen")
    log_path = Path(f"data/users/{TEST_USER_ID}/briefing_log.json")

    def _log_entry_count() -> int:
        if not log_path.exists():
            return 0
        return len(json.loads(log_path.read_text()).get("entries", []))

    # Ausführungsreihenfolge bewusst NICHT SEVEN_COMMANDS: heute/morgen fassen
    # die kombinierte Momentaufnahme zwar seit dem Adversary-Fix nicht mehr an
    # (s.o.), aber die Lesebefehle zuerst und heute/morgen zuletzt laufen zu
    # lassen bleibt eine robuste, unschädliche Reihenfolge (kein Produktverhalten
    # hängt an dieser Reihenfolge — reine Testrobustheit gegen Restzustand).
    _run_order = [c for c in SEVEN_COMMANDS if c not in _ON_DEMAND_CMDS] + list(_ON_DEMAND_CMDS)

    failures = []
    for cmd in _run_order:
        entries_before = _log_entry_count()
        body = run_command_through_pipeline(command=cmd, chat_id=chat_id)

        if not body or not body.strip():
            failures.append(f"{cmd}: leere Antwort")
            continue
        if "Unbekannter Befehl" in body:
            failures.append(f"{cmd}: 'Unbekannter Befehl'")
            continue
        if "Kein aktiver Trip" in body:
            failures.append(f"{cmd}: 'Kein aktiver Trip'")
            continue
        if "Keine Etappe geplant" in body:
            failures.append(f"{cmd}: 'Keine Etappe geplant' — Fixture-Trip hat keine heutige/morgige Etappe")
            continue

        if cmd in _ON_DEMAND_CMDS:
            if "Briefing wird gesendet" not in body:
                failures.append(f"{cmd}: kein Bestätigungstext für Voll-Briefing-Dispatch: {body[:80]!r}")
                continue
            if _log_entry_count() <= entries_before:
                failures.append(f"{cmd}: kein neuer briefing_log-Eintrag (Dispatch nicht nachweisbar)")
                continue
            last = json.loads(log_path.read_text())["entries"][-1]
            if "telegram" not in last.get("channels", []):
                failures.append(f"{cmd}: briefing_log-Eintrag ohne Kanal telegram: {last!r}")
            continue

        if "Kein Wetter-Snapshot" in body:
            failures.append(f"{cmd}: 'Kein Wetter-Snapshot' — kein echter Wetter-Inhalt")
        elif cmd != "hilfe" and not any(m in body for m in _WEATHER_MARKERS):
            failures.append(f"{cmd}: kein Wetter-Marker in Antwort (Schein-Grün?): {body[:80]!r}")
    assert not failures, "Befehle ohne sinnvollen Inhalt: " + "; ".join(failures)


# ---------------------------------------------------------------------------
# AC-4 — echte Zustellung + Cleanup gegen den echten Bot (gated)
# ---------------------------------------------------------------------------

@pytest.mark.real_data_root
@pytest.mark.timeout(240)
@pytest.mark.skipif(
    not live_telegram_enabled(),
    reason="GZ_TELEGRAM_LIVE=1 nicht gesetzt — Live-Sends nur opt-in (#1014)",
)
def test_ac4_live_delivery_and_cleanup():
    """
    GIVEN: Staging-Bot-Token + Test-Chat-ID gesetzt
    WHEN: die Antwort jedes der 7 Befehle real an den Test-Chat gesendet wird
    THEN: jede Zustellung liefert eine message_id (≠ None) und wird danach per
          deleteMessage wieder entfernt (ok=True). Keine Mocks.

    Issue #1007: heute/morgen liefern beim Reader by design KEINE Bestätigungs-
    message_id mehr (suppress — das volle Briefing kommt als Bubble-Serie direkt
    vom Scheduler). `deliver_and_cleanup()` weist das für diese beiden Befehle
    über das TelegramOutput-Klassenregister nach (mindestens 2 neue IDs = Kopf-
    + Segment-Bubble) und räumt sie ebenfalls auf — damit ist das siebte
    Akzeptanzkriterium aus der 1007-Spec (volle Bubbles statt Einzeiler) hier
    erstmals live bewiesen.

    @pytest.mark.timeout(240) (statt globalem 30s-Default, Issue #1210 AC-1
    erlaubt deklarierte Ausnahmen): der Live-Sendepfad im Fixture pacet jeden
    Telegram-POST (_paced_telegram_post in _telegram_live_fixture.py) mit
    ~3.5s Abstand, weil Telegram sonst mit HTTP 429 abriegelt (7 Kommandos,
    teils mehrere Bubbles, plus Cleanup-deleteMessage zählt ebenfalls aufs
    Limit) — die Summe der Wartezeiten sprengt 30s, bleibt aber im Rahmen
    "ein paar Minuten" für einen Test, der nur beim Deploy läuft.
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
