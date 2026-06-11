r"""
TDD tests for Issue #762 — Sub-Etappen-Suffix bei Dedup erhalten.

RED phase: _STAGE_PREFIX_RE matcht r'\d+' zu gierig, 'a' in '3a' wird zu rest
           -> numbered_stage_label() erzeugt 'Etappe 2: a' statt 'Etappe 2: Etappe 3a'.
GREEN phase: r'\d+\b' stoppt vor Wortzeichen -> Originalname bleibt erhalten.

Keine Mocks. Echte Trip/Stage-Objekte.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.trip import Stage, Trip, Waypoint


# ---------------------------------------------------------------------------
# Shared helpers (nach Stil der #760-Testdatei)
# ---------------------------------------------------------------------------

def _waypoint(wp_id: str = "G1") -> Waypoint:
    return Waypoint(
        id=wp_id,
        name="Testpunkt",
        lat=47.0,
        lon=11.0,
        elevation_m=1000,
    )


def _stage(stage_id: str, name: str, d: date) -> Stage:
    return Stage(
        id=stage_id,
        name=name,
        date=d,
        waypoints=[_waypoint()],
    )


# ---------------------------------------------------------------------------
# AC-1 — Sub-Etappe '3a' an chronologischer Position 2 bleibt erhalten
# ---------------------------------------------------------------------------

class TestStageSuffixPreserved:
    """AC-1 + AC-2: Suffix-Zeichen nach der Ziffer (z.B. '3a', '3b') gehen
    bei numbered_stage_label() nicht verloren."""

    def test_ac1_sub_stage_3a_at_position_2(self):
        """AC-1: 'Etappe 3a' an Position 2 → 'Etappe 2: Etappe 3a', NICHT 'Etappe 2: a'."""
        s1 = _stage("T1", "Erste Etappe", date(2026, 10, 1))
        s2 = _stage("T2", "Etappe 3a", date(2026, 10, 2))
        trip = Trip(id="t", name="GR20", stages=[s1, s2])

        result = trip.numbered_stage_label(s2)

        assert result == "Etappe 2: Etappe 3a", (
            f"Suffix '3a' wurde verstümmelt: {result!r}"
        )
        assert "Etappe 2: a" != result, (
            "Regex hat '3a' aufgespalten — 'a' wurde fälschlich als rest extrahiert"
        )

    def test_ac2_sub_stage_3b_at_position_3(self):
        """AC-2: 'Etappe 3b' an Position 3 → 'Etappe 3: Etappe 3b', NICHT 'Etappe 3: b'."""
        s1 = _stage("T1", "Tag 1", date(2026, 10, 1))
        s2 = _stage("T2", "Tag 2", date(2026, 10, 2))
        s3 = _stage("T3", "Etappe 3b", date(2026, 10, 3))
        trip = Trip(id="t", name="GR20", stages=[s1, s2, s3])

        result = trip.numbered_stage_label(s3)

        assert result == "Etappe 3: Etappe 3b", (
            f"Suffix '3b' wurde verstümmelt: {result!r}"
        )
        assert "Etappe 3: b" != result, (
            "Regex hat '3b' aufgespalten — 'b' wurde fälschlich als rest extrahiert"
        )
