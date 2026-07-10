"""Datentyp fuer amtliche Wetterwarnungen (Issue #1034).

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md
ADR-0016: eigener additiver Datentyp statt Wiederverwendung von
WeatherProvider- oder Delta-Alert-Modellen (absolute Behoerden-Einstufung).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class OfficialAlert:
    """Eine amtliche Warnung einer offiziellen Quelle (z.B. Météo-France Vigilance).

    Level 1=gruen, 2=gelb, 3=orange, 4=rot (analog zu Vigilance-Farbstufen).
    """
    source: str
    hazard: str
    level: int
    label: str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    url: Optional[str] = None
    region_label: Optional[str] = None
    # Issue #1217/#1218 (F001): stabile, stufen-unabhängige Dedup-Identität.
    # Quellen, deren Label den Schweregrad codiert (z.B. Massiv-Sperren:
    # "Zugang eingeschränkt" vs. "gesperrt" fürs GLEICHE Massiv), setzen hier
    # eine über Stufen konstante Kennung, damit Eskalationen nicht als zwei
    # verschiedene Warnungen erscheinen. None -> Fallback auf region_label/label.
    dedup_id: Optional[str] = None
