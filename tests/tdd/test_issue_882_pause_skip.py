"""Issue #882 — Email: PAUSE im Footer + SKIP Keyword-Routing.

Prüft:
- PAUSE und SKIP sind im HTML- und Plaintext-Footer sichtbar
- PAUSE 2d und SKIP werden korrekt an _apply_pause/_apply_skip gerouted
- SKIP setzt skip_next=True (einmalig, AC-2/AC-3 Basis)
"""
from __future__ import annotations

import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import get_trips_dir, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import InboundMessage, TripCommandProcessor  # noqa: E402

TZ = ZoneInfo("UTC")
_USER = "tdd-882-user"
_TRIP_ID = "issue882-trip"
_TRIP_NAME = "Issue882 Trip"


def _make_trip() -> Trip:
    wp = Waypoint(id="W1", name="A", lat=47.0, lon=11.0, elevation_m=800)
    stage = Stage(
        id="S1",
        name="Tag 1",
        date=date(2026, 7, 10),
        waypoints=[wp],
    )
    rc = TripReportConfig(trip_id=_TRIP_ID)
    return Trip(
        id=_TRIP_ID,
        name=_TRIP_NAME,
        stages=[stage],
        report_config=rc,
    )


def _load_trip() -> Trip:
    from app.loader import load_all_trips
    trips = load_all_trips(_USER)
    return next(t for t in trips if t.id == _TRIP_ID)


def _msg(text: str) -> InboundMessage:
    return InboundMessage(
        body=text,
        trip_name=_TRIP_NAME,
        sender="test@example.com",
        channel="email",
        received_at=datetime(2026, 7, 10, 8, 0, tzinfo=timezone.utc),
        user_id=_USER,
    )


@pytest.fixture(autouse=True)
def clean_user_dir():
    trips_dir = get_trips_dir(_USER)
    shutil.rmtree(trips_dir, ignore_errors=True)
    yield
    shutil.rmtree(trips_dir, ignore_errors=True)


# ===========================================================================
# AC-1: Footer HTML
# ===========================================================================

class TestAC1HtmlFooter:
    def test_pause_in_html_footer(self):  # doc-compliance-test
        # Superseded by #884 design: PAUSE CMD is now "PAUSE 2d" (no bracket hint),
        # description changed to "Briefings pausieren"
        source = (REPO_ROOT / "src/output/renderers/email/html.py").read_text()
        assert "PAUSE" in source, "HTML-Footer muss PAUSE enthalten (AC-1)"
        assert "PAUSE 2d" in source, "HTML-Kommandos-Block muss PAUSE 2d enthalten (AC-1/#884)"

    def test_skip_in_html_footer(self):  # doc-compliance-test
        # Superseded by #884 design: SKIP description changed from "Nächstes Briefing überspringen"
        # to "Nächstes überspringen"
        source = (REPO_ROOT / "src/output/renderers/email/html.py").read_text()
        assert "SKIP" in source, "HTML-Footer muss SKIP enthalten (AC-1)"
        assert "Nächstes überspringen" in source, "HTML-Kommandos-Block muss SKIP-Beschreibung 'Nächstes überspringen' enthalten (AC-1/#884)"

    def test_pause_in_plain_footer(self):  # doc-compliance-test
        source = (REPO_ROOT / "src/output/renderers/email/plain.py").read_text()
        assert "PAUSE" in source, "Plaintext-Footer muss PAUSE enthalten (AC-1)"

    def test_skip_in_plain_footer(self):  # doc-compliance-test
        source = (REPO_ROOT / "src/output/renderers/email/plain.py").read_text()
        assert "SKIP" in source, "Plaintext-Footer muss SKIP enthalten (AC-1)"


# ===========================================================================
# AC-2: SKIP Keyword-Routing → skip_next=True
# ===========================================================================

class TestAC2SkipRouting:
    def test_skip_bare_keyword_sets_flag(self):
        save_trip(_make_trip(), user_id=_USER)
        result = TripCommandProcessor().process(_msg("SKIP"))
        assert result.success, f"SKIP muss erfolgreich sein, war: {result.command!r}"
        loaded = _load_trip()
        assert loaded.report_config.skip_next is True, \
            "SKIP muss skip_next=True im Trip setzen (AC-2)"

    def test_skip_sends_confirmation(self):
        save_trip(_make_trip(), user_id=_USER)
        result = TripCommandProcessor().process(_msg("SKIP"))
        assert result.confirmation_subject, "SKIP muss Bestätigungs-Betreff haben (AC-2)"
        assert "übersprungen" in (result.confirmation_body or "").lower() or \
               "skip" in (result.confirmation_subject or "").lower(), \
            "Bestätigungstext muss 'übersprungen' oder 'Skip' enthalten (AC-2)"


# ===========================================================================
# AC-3: PAUSE Keyword-Routing → paused_until gesetzt
# ===========================================================================

class TestAC3PauseRouting:
    def test_pause_2d_sets_paused_until(self):
        save_trip(_make_trip(), user_id=_USER)
        result = TripCommandProcessor().process(_msg("PAUSE 2d"))
        assert result.success, f"PAUSE 2d muss erfolgreich sein, war: {result.command!r}"
        loaded = _load_trip()
        assert loaded.report_config.paused_until is not None, \
            "PAUSE 2d muss paused_until setzen (AC-3)"

    def test_pause_12h_sets_paused_until(self):
        save_trip(_make_trip(), user_id=_USER)
        result = TripCommandProcessor().process(_msg("PAUSE 12h"))
        assert result.success, f"PAUSE 12h muss erfolgreich sein, war: {result.command!r}"
        loaded = _load_trip()
        assert loaded.report_config.paused_until is not None, \
            "PAUSE 12h muss paused_until setzen (AC-3)"

    def test_pause_without_duration_fails_gracefully(self):
        save_trip(_make_trip(), user_id=_USER)
        result = TripCommandProcessor().process(_msg("PAUSE"))
        assert not result.success, "PAUSE ohne Dauer muss Fehlermeldung liefern"
        assert result.confirmation_body, "Fehlermeldung muss erklären was fehlt"
