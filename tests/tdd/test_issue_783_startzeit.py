"""TDD RED — Issue #783: Briefing-Stundentabelle ignoriert die Etappen-Startzeit.

SPEC: docs/specs/modules/issue_783_776_778_briefing_fixes.md (AC-1, AC-2)

User stellt die Etappen-Startzeit auf 14:00. Die Stundentabelle in der Briefing-Mail
beginnt trotzdem bei 07:00, weil `_convert_trip_to_segments` fuer den ERSTEN Waypoint
das persistierte `arrival_calculated` (alter Naismith-Wert, z.B. 07:00) VOR
`stage.start_time` priorisiert.

AC-1 MUSS ROT sein: aktuell gewinnt arrival_calculated="07:00" -> segment.start_time.hour == 7.
Nach dem Fix: stage.start_time (14:00) gewinnt am Startpunkt -> segment.start_time.hour == 14.

Reykjavik (UTC+0, kein DST) als Koordinate => lokale Stunde == UTC-Stunde, keine
Zeitzonen-Verwirrung in der Assertion.

KEINE MOCKS — echter Aufruf von _convert_trip_to_segments mit echten Modell-Objekten.
"""
from __future__ import annotations

import os
from datetime import date, time, timezone

import pytest

_TARGET_DATE = date(2026, 7, 15)
# Reykjavik = UTC+0 (kein DST): lokale Eingabe-Stunde == gespeicherte UTC-Stunde.
_REYKJAVIK = (64.1, -21.9)


def _make_svc():
    from services.trip_report_scheduler import TripReportSchedulerService
    return TripReportSchedulerService.__new__(TripReportSchedulerService)


def _make_trip(*, stage_start, wp1_arrival_calculated,
               wp1_arrival_override=None, wp1_time_window=None):
    """Trip mit 2 Wegpunkten. Der erste Wegpunkt traegt einen persistierten
    arrival_calculated-Wert; die Etappe hat eine eigene Startzeit."""
    from app.trip import Stage, Trip, Waypoint

    wp1 = Waypoint(
        id="W1", name="Start", lat=_REYKJAVIK[0], lon=_REYKJAVIK[1],
        elevation_m=50,
        time_window=wp1_time_window,
        arrival_calculated=wp1_arrival_calculated,
        arrival_override=wp1_arrival_override,
    )
    wp2 = Waypoint(
        id="W2", name="Ziel", lat=64.2, lon=-21.0, elevation_m=100,
        arrival_calculated="18:00",
    )
    stage = Stage(id="S1", name="Etappe 1", date=_TARGET_DATE,
                  waypoints=[wp1, wp2], start_time=stage_start)
    return Trip(id="t783", name="Startzeit-Trip", stages=[stage])


# ===========================================================================
# AC-1: Etappen-Startzeit gewinnt am Startpunkt vor arrival_calculated
# ===========================================================================

def test_stage_start_time_overrides_stale_arrival_calculated_at_start():
    """AC-1: GIVEN Etappe mit start_time=14:00 und Startpunkt-arrival_calculated=07:00
    (kein time_window, kein arrival_override) / WHEN _convert_trip_to_segments /
    THEN segment.start_time.hour == 14 (nicht 07).

    RED: aktuell gewinnt arrival_calculated -> hour == 7.
    """
    svc = _make_svc()
    trip = _make_trip(stage_start=time(14, 0), wp1_arrival_calculated="07:00")
    segments = svc._convert_trip_to_segments(trip, _TARGET_DATE)

    assert segments, "Segmentliste darf nicht leer sein"
    start_utc = segments[0].start_time.astimezone(timezone.utc)
    assert start_utc.hour == 14, (
        f"Etappen-Startzeit 14:00 muss den Startpunkt bestimmen, "
        f"aktuell beginnt das Segment bei {start_utc.hour:02d}:00 "
        f"(stale arrival_calculated gewinnt -> Bug #783)"
    )


# ===========================================================================
# AC-1 (Regressionsschutz): per-Waypoint arrival_override behaelt Vorrang
# ===========================================================================

def test_explicit_waypoint_override_still_wins_over_stage_start():
    """GIVEN Startpunkt mit arrival_override=06:00 UND Etappe start_time=14:00 /
    WHEN _convert_trip_to_segments / THEN segment.start_time.hour == 6.

    Muss VOR und NACH dem Fix gruen sein: ein bewusster per-Waypoint Nutzer-Override
    (#303) hat hoechste Prioritaet und darf von der Etappen-Startzeit NICHT verdraengt
    werden.
    """
    svc = _make_svc()
    trip = _make_trip(stage_start=time(14, 0), wp1_arrival_calculated="07:00",
                      wp1_arrival_override="06:00")
    segments = svc._convert_trip_to_segments(trip, _TARGET_DATE)

    assert segments
    start_utc = segments[0].start_time.astimezone(timezone.utc)
    assert start_utc.hour == 6, (
        f"arrival_override=06:00 muss Vorrang behalten, ist {start_utc.hour:02d}:00"
    )


# ===========================================================================
# AC-2: Echter Staging-Versand zeigt 14:00 in der Stundentabelle (E2E-Stage)
# ===========================================================================

@pytest.mark.skipif(
    not os.environ.get("GZ_STAGING_E2E"),
    reason="AC-2 ist ein Staging-E2E-Test (GZ_STAGING_E2E gesetzt); laeuft in der "
           "Acceptance-Stage gegen staging.gregor20.henemm.com mit IMAP-Verifikation.",
)
def test_briefing_mail_starts_at_configured_time_on_staging():
    """AC-2: GIVEN Trip mit Etappen-Startzeit 14:00 auf Staging /
    WHEN Test-Briefing-Versand ausgeloest / THEN erste Stundentabellen-Zeile = 14:00.

    Echter HTTP-POST + IMAP-Poll aus dem Stalwart-Test-Postfach (GZ_IMAP_*).
    Implementierungsdetail folgt in der E2E-Phase (kein Mock, kein Gmail).
    """
    pytest.skip("Staging-E2E wird in /e2e-verify ausgefuehrt, nicht im lokalen RED-Lauf")
