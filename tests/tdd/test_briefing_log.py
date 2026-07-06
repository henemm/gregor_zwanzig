"""
TDD RED Tests für Issue #393 — Cockpit-Kacheln: Versandstatus.

Testet _append_briefing_log() auf TripReportSchedulerService.
Diese Methode existiert noch nicht → Tests MÜSSEN ROT sein.

Spec: docs/specs/modules/issue_393_cockpit_kacheln.md (AC-1)
Test-Manifest: docs/specs/tests/issue_393_cockpit_kacheln_tests.md

Ausführung:
    cd /home/hem/gregor_zwanzig && uv run pytest tests/tdd/test_briefing_log.py -v
"""
from __future__ import annotations

import json
from datetime import datetime



def _make_scheduler_service(user_id: str = "test-user"):
    """Erstellt TripReportSchedulerService ohne SMTP-Abhängigkeit."""
    from services.trip_report_scheduler import TripReportSchedulerService

    svc = TripReportSchedulerService.__new__(TripReportSchedulerService)
    svc._user_id = user_id
    return svc


# --- AC-1: _append_briefing_log schreibt Eintrag in briefing_log.json ---

def test_append_briefing_log_creates_file_with_entry(tmp_path, monkeypatch):
    """
    GIVEN: Kein briefing_log.json existiert
    WHEN: _append_briefing_log("trip-123", "morning", ["email"]) aufgerufen
    THEN: briefing_log.json wird erstellt mit trip_id, kind, channels, sent_at
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "users" / "test-user").mkdir(parents=True)

    svc = _make_scheduler_service("test-user")
    svc._append_briefing_log("trip-123", "morning", ["email"])

    log_file = tmp_path / "data" / "users" / "test-user" / "briefing_log.json"
    assert log_file.exists(), "briefing_log.json wurde nicht erstellt"

    data = json.loads(log_file.read_text())
    assert "entries" in data
    assert len(data["entries"]) == 1

    entry = data["entries"][0]
    assert entry["trip_id"] == "trip-123"
    assert entry["kind"] == "morning"
    assert entry["channels"] == ["email"]
    assert "sent_at" in entry

    parsed = datetime.fromisoformat(entry["sent_at"])
    assert parsed.tzinfo is not None, "sent_at muss timezone-aware sein"


def test_append_briefing_log_appends_to_existing_file(tmp_path, monkeypatch):
    """
    GIVEN: briefing_log.json existiert mit einem Eintrag
    WHEN: _append_briefing_log ein zweites Mal aufgerufen
    THEN: Eintrag wird angehängt, erster Eintrag bleibt erhalten
    """
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / "data" / "users" / "test-user"
    user_dir.mkdir(parents=True)

    existing = {
        "entries": [
            {
                "trip_id": "trip-abc",
                "kind": "morning",
                "sent_at": "2026-05-27T07:03:00+00:00",
                "channels": ["email"],
            }
        ]
    }
    (user_dir / "briefing_log.json").write_text(json.dumps(existing))

    svc = _make_scheduler_service("test-user")
    svc._append_briefing_log("trip-abc", "evening", ["email", "signal"])

    data = json.loads((user_dir / "briefing_log.json").read_text())
    assert len(data["entries"]) == 2
    assert data["entries"][0]["kind"] == "morning"
    assert data["entries"][1]["kind"] == "evening"
    assert data["entries"][1]["channels"] == ["email", "signal"]


def test_append_briefing_log_channels_list_preserved(tmp_path, monkeypatch):
    """
    GIVEN: Mehrere Kanäle konfiguriert (email + signal + telegram)
    WHEN: _append_briefing_log aufgerufen
    THEN: Alle Kanäle landen korrekt im Eintrag
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "users" / "test-user").mkdir(parents=True)

    svc = _make_scheduler_service("test-user")
    svc._append_briefing_log("trip-xyz", "evening", ["email", "signal", "telegram"])

    log_file = tmp_path / "data" / "users" / "test-user" / "briefing_log.json"
    data = json.loads(log_file.read_text())
    assert data["entries"][0]["channels"] == ["email", "signal", "telegram"]


def test_append_briefing_log_kind_evening(tmp_path, monkeypatch):
    """
    GIVEN: Report-Typ ist 'evening'
    WHEN: _append_briefing_log("trip-123", "evening", [...]) aufgerufen
    THEN: kind ist 'evening' im Eintrag
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "users" / "test-user").mkdir(parents=True)

    svc = _make_scheduler_service("test-user")
    svc._append_briefing_log("trip-123", "evening", ["email"])

    log_file = tmp_path / "data" / "users" / "test-user" / "briefing_log.json"
    data = json.loads(log_file.read_text())
    assert data["entries"][0]["kind"] == "evening"
