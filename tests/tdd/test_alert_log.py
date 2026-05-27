"""
TDD RED Tests für Issue #393 — Cockpit-Kacheln: Alarm-Historie.

Testet _append_alert_log() auf TripAlertService.
Diese Methode existiert noch nicht → Tests MÜSSEN ROT sein.

Spec: docs/specs/modules/issue_393_cockpit_kacheln.md (AC-2, AC-9)
Test-Manifest: docs/specs/tests/issue_393_cockpit_kacheln_tests.md

Ausführung:
    cd /home/hem/gregor_zwanzig && uv run pytest tests/tdd/test_alert_log.py -v
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest


def _make_alert_service(user_id: str = "test-user"):
    """Erstellt TripAlertService ohne SMTP-Abhängigkeit."""
    from services.trip_alert import TripAlertService

    svc = TripAlertService.__new__(TripAlertService)
    svc._user_id = user_id
    svc._last_alert_times = {}
    return svc


# --- AC-2: _append_alert_log schreibt Eintrag in alert_log.json ---

def test_append_alert_log_creates_file_with_entry(tmp_path, monkeypatch):
    """
    GIVEN: Kein alert_log.json existiert
    WHEN: _append_alert_log("trip-123", 2, "MODERATE") aufgerufen
    THEN: alert_log.json wird erstellt mit trip_id, sent_at, changes_count, severity
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data" / "users" / "test-user").mkdir(parents=True)

    svc = _make_alert_service("test-user")
    svc._append_alert_log("trip-123", 2, "MODERATE")

    log_file = tmp_path / "data" / "users" / "test-user" / "alert_log.json"
    assert log_file.exists(), "alert_log.json wurde nicht erstellt"

    data = json.loads(log_file.read_text())
    assert "entries" in data
    assert len(data["entries"]) == 1

    entry = data["entries"][0]
    assert entry["trip_id"] == "trip-123"
    assert entry["changes_count"] == 2
    assert entry["severity"] == "MODERATE"
    assert "sent_at" in entry

    parsed = datetime.fromisoformat(entry["sent_at"])
    assert parsed.tzinfo is not None, "sent_at muss timezone-aware sein"


def test_append_alert_log_appends_to_existing(tmp_path, monkeypatch):
    """
    GIVEN: alert_log.json existiert mit einem Eintrag
    WHEN: _append_alert_log ein zweites Mal aufgerufen
    THEN: Neuer Eintrag wird angehängt, alter Eintrag bleibt erhalten
    """
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / "data" / "users" / "test-user"
    user_dir.mkdir(parents=True)

    now = datetime.now(timezone.utc)
    existing = {
        "entries": [
            {
                "trip_id": "trip-abc",
                "sent_at": now.isoformat(),
                "changes_count": 1,
                "severity": "LOW",
            }
        ]
    }
    (user_dir / "alert_log.json").write_text(json.dumps(existing))

    svc = _make_alert_service("test-user")
    svc._append_alert_log("trip-abc", 3, "HIGH")

    data = json.loads((user_dir / "alert_log.json").read_text())
    assert len(data["entries"]) == 2
    assert data["entries"][0]["severity"] == "LOW"
    assert data["entries"][1]["severity"] == "HIGH"
    assert data["entries"][1]["changes_count"] == 3


def test_append_alert_log_purges_entries_older_than_48h(tmp_path, monkeypatch):
    """
    GIVEN: alert_log.json enthält Einträge, darunter einen älter als 48h
    WHEN: _append_alert_log aufgerufen
    THEN: Eintrag älter als 48h wird entfernt, neue + frische Einträge bleiben
    """
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / "data" / "users" / "test-user"
    user_dir.mkdir(parents=True)

    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(hours=49)).isoformat()
    fresh_ts = (now - timedelta(hours=1)).isoformat()

    existing = {
        "entries": [
            {
                "trip_id": "trip-abc",
                "sent_at": old_ts,
                "changes_count": 1,
                "severity": "LOW",
            },
            {
                "trip_id": "trip-abc",
                "sent_at": fresh_ts,
                "changes_count": 2,
                "severity": "MODERATE",
            },
        ]
    }
    (user_dir / "alert_log.json").write_text(json.dumps(existing))

    svc = _make_alert_service("test-user")
    svc._append_alert_log("trip-abc", 3, "HIGH")

    data = json.loads((user_dir / "alert_log.json").read_text())
    # Alter Eintrag weg, frischer und neuer vorhanden
    assert len(data["entries"]) == 2
    severities = [e["severity"] for e in data["entries"]]
    assert "LOW" not in severities, "Eintrag älter als 48h sollte entfernt sein"
    assert "MODERATE" in severities
    assert "HIGH" in severities


def test_append_alert_log_retains_fresh_entries(tmp_path, monkeypatch):
    """
    GIVEN: alert_log.json enthält ausschließlich frische Einträge (< 48h)
    WHEN: _append_alert_log aufgerufen
    THEN: Alle frischen Einträge bleiben erhalten
    """
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / "data" / "users" / "test-user"
    user_dir.mkdir(parents=True)

    now = datetime.now(timezone.utc)
    existing = {
        "entries": [
            {
                "trip_id": "trip-abc",
                "sent_at": (now - timedelta(hours=12)).isoformat(),
                "changes_count": 1,
                "severity": "LOW",
            },
            {
                "trip_id": "trip-abc",
                "sent_at": (now - timedelta(hours=6)).isoformat(),
                "changes_count": 2,
                "severity": "MODERATE",
            },
        ]
    }
    (user_dir / "alert_log.json").write_text(json.dumps(existing))

    svc = _make_alert_service("test-user")
    svc._append_alert_log("trip-abc", 3, "HIGH")

    data = json.loads((user_dir / "alert_log.json").read_text())
    assert len(data["entries"]) == 3, "Alle frischen Einträge + neuer Eintrag sollen vorhanden sein"
