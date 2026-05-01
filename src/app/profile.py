"""
Canonical ActivityProfile enum — Single Source of Truth.

Both src/app/trip.py and src/app/user.py re-export or alias this enum
during PR 1; in PR 2 the aliases are removed.
"""
from __future__ import annotations

from enum import Enum


class ActivityProfile(str, Enum):
    """Semantisches Label fuer eine Aktivitaets-/Sportart.

    Dieses Enum ist ein semantisches Label — KEIN Behavior-Key.
    Die zugehoerigen Dispatch-Tabellen sind unabhaengig:
    - src/app/trip.py::AggregationConfig.for_profile (Aggregations-Semantik)
    - src/web/pages/compare.py::calculate_score      (Scoring-Semantik)

    Bei Erweiterung um neue Sportarten MUSS die Go-Whitelist in
    internal/handler/subscription.go synchronisiert werden.
    """

    WINTERSPORT     = "wintersport"      # Schnee/Lawinen
    WANDERN         = "wandern"          # Tieflagen-Wanderung
    SUMMER_TREKKING = "summer_trekking"  # Alpine Mehrtagestour
    ALLGEMEIN       = "allgemein"        # Generischer Default
