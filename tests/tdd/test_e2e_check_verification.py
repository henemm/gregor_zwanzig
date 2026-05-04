"""
TDD RED — E2E Commit Gate: check_verification() Scope-Based Logic (#86)

Tests fuer check_verification() in e2e_commit_gate.py.

ROTE Tests (schlagen fehl bis Implementierung):
- test_check_verification_frontend_only_passes_with_server_restart_only
- test_check_verification_backend_passes_with_all_fields          (message enthaelt kein scope)
- test_check_verification_full_stack_verified_covers_backend_commit (message enthaelt kein scope)
- test_check_verification_scope_too_low_full_stack_blocked
- test_check_verification_scope_too_low_backend_vs_frontend_blocked

GRUENE Tests (bestehende Logik, Regression-Schutz):
- test_check_verification_docs_only_skips_gate
- test_check_verification_no_json_returns_false
- test_check_verification_stale_timestamp_returns_false
- test_check_verification_missing_required_field_backend
- test_check_verification_no_scope_field_backward_compat
- test_check_verification_corrupt_json_returns_false
- test_check_verification_missing_timestamp_returns_false
- test_check_verification_frontend_only_missing_server_restart_blocks
"""
import json
import sys
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))
import e2e_commit_gate


# ──────────────────────────────────────────────────────────
# Hilfsfunktionen
# ──────────────────────────────────────────────────────────

def _write_json(tmp_path: Path, data: dict) -> None:
    """Schreibt e2e_verified.json in tmp_path/.claude/."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "e2e_verified.json").write_text(json.dumps(data))


def _fresh_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stale_ts() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()


def _mock_scope(monkeypatch, scope: str) -> None:
    monkeypatch.setattr(e2e_commit_gate, "detect_scope", lambda: scope)


def _mock_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(e2e_commit_gate, "find_project_root", lambda: tmp_path)


# ──────────────────────────────────────────────────────────
# GRUENE Tests — Bestehende Logik (Regression-Schutz)
# ──────────────────────────────────────────────────────────

def test_check_verification_docs_only_skips_gate(monkeypatch, tmp_path):
    """
    GIVEN: Scope = docs-only (nur .md / docs/ Dateien gestaget)
    WHEN: check_verification() aufgerufen
    THEN: Gate uebersprungen, (True, '...docs-only...')
    """
    _mock_scope(monkeypatch, "docs-only")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is True
    assert "docs-only" in msg


def test_check_verification_no_json_returns_false(monkeypatch, tmp_path):
    """
    GIVEN: Scope = backend, keine e2e_verified.json vorhanden
    WHEN: check_verification() aufgerufen
    THEN: (False, Hinweis auf /e2e-verify)
    """
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "e2e-verify" in msg.lower() or "verifikation" in msg.lower()


def test_check_verification_stale_timestamp_returns_false(monkeypatch, tmp_path):
    """
    GIVEN: Scope = backend, JSON mit veraltetem Timestamp (> 2 Stunden)
    WHEN: check_verification() aufgerufen
    THEN: (False, Hinweis auf Alter in Minuten)
    """
    _write_json(tmp_path, {
        "verified_at": _stale_ts(),
        "server_restarted": True, "test_trip_created": True,
        "emails_checked": True, "test_trip_cleaned": True,
    })
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "minuten" in msg.lower() or "alt" in msg.lower()


def test_check_verification_corrupt_json_returns_false(monkeypatch, tmp_path):
    """
    GIVEN: e2e_verified.json enthaelt kein valides JSON
    WHEN: check_verification() aufgerufen
    THEN: (False, Hinweis auf korrupte Datei)
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "e2e_verified.json").write_text("NOT_VALID_JSON{{{")
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "korrupt" in msg.lower() or "json" in msg.lower()


def test_check_verification_missing_timestamp_returns_false(monkeypatch, tmp_path):
    """
    GIVEN: JSON ohne verified_at Feld
    WHEN: check_verification() aufgerufen
    THEN: (False, Hinweis auf fehlenden Timestamp)
    """
    _write_json(tmp_path, {
        "server_restarted": True, "test_trip_created": True,
        "emails_checked": True, "test_trip_cleaned": True,
    })
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "timestamp" in msg.lower()


def test_check_verification_missing_required_field_backend(monkeypatch, tmp_path):
    """
    GIVEN: Scope = backend, test_trip_created fehlt im JSON
    WHEN: check_verification() aufgerufen
    THEN: (False, Fehlermeldung nennt test_trip_created)
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": True,
        "emails_checked": True, "test_trip_cleaned": True,
        # test_trip_created fehlt absichtlich
    })
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "test_trip_created" in msg


def test_check_verification_frontend_only_missing_server_restart_blocks(monkeypatch, tmp_path):
    """
    GIVEN: Scope = frontend-only, server_restarted=False
    WHEN: check_verification() aufgerufen
    THEN: (False, server_restarted fehlt)
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": False,
    })
    _mock_scope(monkeypatch, "frontend-only")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "server_restarted" in msg


def test_check_verification_no_scope_field_backward_compat(monkeypatch, tmp_path):
    """
    GIVEN: Scope = backend, JSON hat KEIN scope-Feld (Legacy-JSON)
    WHEN: check_verification() aufgerufen
    THEN: (True, ...) — Fallback auf full-stack, kein Regressionsrisiko

    Bestehende JSONs ohne scope-Feld duerfen niemals zu Blockierungen fuehren.
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": True, "test_trip_created": True,
        "emails_checked": True, "test_trip_cleaned": True,
        # kein 'scope'-Feld — Legacy
    })
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is True


# ──────────────────────────────────────────────────────────
# ROTE Tests — Schlagen fehl bis Implementierung
# ──────────────────────────────────────────────────────────

def test_check_verification_frontend_only_passes_with_server_restart_only(monkeypatch, tmp_path):
    """
    GIVEN: Scope = frontend-only, JSON hat NUR server_restarted=True (keine Backend-Felder)
    WHEN: check_verification() aufgerufen
    THEN: (True, ...) — fuer frontend-only ist nur server_restarted Pflicht

    AKTUELLES VERHALTEN: FAIL — check_verification() verlangt alle 4 Felder
    NACH IMPLEMENTIERUNG: PASS
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": True,
        # test_trip_created, emails_checked, test_trip_cleaned absichtlich nicht gesetzt
    })
    _mock_scope(monkeypatch, "frontend-only")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is True


def test_check_verification_backend_passes_with_all_fields(monkeypatch, tmp_path):
    """
    GIVEN: Scope = backend, JSON hat alle 4 Pflichtfelder + scope='backend'
    WHEN: check_verification() aufgerufen
    THEN: (True, Nachricht enthaelt 'backend')

    AKTUELLES VERHALTEN: FAIL — Erfolgs-Message enthaelt kein Scope-Info
    NACH IMPLEMENTIERUNG: PASS
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": True, "test_trip_created": True,
        "emails_checked": True, "test_trip_cleaned": True,
        "scope": "backend",
    })
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is True
    assert "backend" in msg.lower()


def test_check_verification_full_stack_verified_covers_backend_commit(monkeypatch, tmp_path):
    """
    GIVEN: Commit-Scope = backend, JSON scope = 'full-stack' (alle 4 Felder vorhanden)
    WHEN: check_verification() aufgerufen
    THEN: (True, Nachricht enthaelt 'backend') — full-stack deckt backend ab

    AKTUELLES VERHALTEN: FAIL — Erfolgs-Message enthaelt kein Scope-Info
    NACH IMPLEMENTIERUNG: PASS
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": True, "test_trip_created": True,
        "emails_checked": True, "test_trip_cleaned": True,
        "scope": "full-stack",
    })
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is True
    assert "backend" in msg.lower()


def test_check_verification_scope_too_low_full_stack_blocked(monkeypatch, tmp_path):
    """
    GIVEN: Commit-Scope = full-stack, JSON scope = 'frontend-only'
    WHEN: check_verification() aufgerufen
    THEN: (False, Fehlermeldung nennt 'frontend-only' oder 'scope')

    AKTUELLES VERHALTEN: FAIL — kein Scope-Vergleich, Gate blockiert nicht aus richtigem Grund
    NACH IMPLEMENTIERUNG: PASS
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": True,
        "scope": "frontend-only",
    })
    _mock_scope(monkeypatch, "full-stack")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "frontend-only" in msg or "scope" in msg.lower()


def test_check_verification_scope_too_low_backend_vs_frontend_blocked(monkeypatch, tmp_path):
    """
    GIVEN: Commit-Scope = backend, JSON scope = 'frontend-only'
    WHEN: check_verification() aufgerufen
    THEN: (False, Fehlermeldung nennt Scope-Konflikt — 'frontend-only' oder 'scope')

    AKTUELLES VERHALTEN: FAIL — blockiert zwar (fehlende Felder), aber
    Fehlermeldung nennt nicht den Scope-Konflikt
    NACH IMPLEMENTIERUNG: PASS
    """
    _write_json(tmp_path, {
        "verified_at": _fresh_ts(),
        "server_restarted": True,
        "scope": "frontend-only",
    })
    _mock_scope(monkeypatch, "backend")
    _mock_root(monkeypatch, tmp_path)

    ok, msg = e2e_commit_gate.check_verification()

    assert ok is False
    assert "frontend-only" in msg or "scope" in msg.lower()
