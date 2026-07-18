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

def test_append_briefing_log_creates_file_with_entry():
    """
    GIVEN: Kein briefing_log.json existiert
    WHEN: _append_briefing_log("trip-123", "morning", ["email"]) aufgerufen
    THEN: briefing_log.json wird erstellt mit trip_id, kind, channels, sent_at

    Issue #1133-Fixture-Kollision: _append_briefing_log() schreibt ueber
    get_data_dir(), das von der autouse-Isolationsfixture auf einen
    eigenen isolierten Root umgebogen wird -- der Test muss denselben
    Pfad benutzen statt einen eigenen tmp_path-Baum zu bauen.
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

    svc = _make_scheduler_service("test-user")
    svc._append_briefing_log("trip-123", "morning", ["email"])

    log_file = user_dir / "briefing_log.json"
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


def test_append_briefing_log_appends_to_existing_file():
    """
    GIVEN: briefing_log.json existiert mit einem Eintrag
    WHEN: _append_briefing_log ein zweites Mal aufgerufen
    THEN: Eintrag wird angehängt, erster Eintrag bleibt erhalten
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

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


def test_append_briefing_log_channels_list_preserved():
    """
    GIVEN: Mehrere Kanäle konfiguriert (email + signal + telegram)
    WHEN: _append_briefing_log aufgerufen
    THEN: Alle Kanäle landen korrekt im Eintrag
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

    svc = _make_scheduler_service("test-user")
    svc._append_briefing_log("trip-xyz", "evening", ["email", "signal", "telegram"])

    log_file = user_dir / "briefing_log.json"
    data = json.loads(log_file.read_text())
    assert data["entries"][0]["channels"] == ["email", "signal", "telegram"]


def test_append_briefing_log_kind_evening():
    """
    GIVEN: Report-Typ ist 'evening'
    WHEN: _append_briefing_log("trip-123", "evening", [...]) aufgerufen
    THEN: kind ist 'evening' im Eintrag
    """
    from app.loader import get_data_dir

    user_dir = get_data_dir("test-user")
    user_dir.mkdir(parents=True, exist_ok=True)

    svc = _make_scheduler_service("test-user")
    svc._append_briefing_log("trip-123", "evening", ["email"])

    log_file = user_dir / "briefing_log.json"
    data = json.loads(log_file.read_text())
    assert data["entries"][0]["kind"] == "evening"
