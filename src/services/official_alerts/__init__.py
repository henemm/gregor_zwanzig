"""Fundament fuer amtliche Wetterwarnungen im Orts-Vergleich (Issue #1034).

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md
"""
from __future__ import annotations

from services.official_alerts.base import (
    OfficialAlertSource,
    get_official_alerts_for_location,
    register_official_alert_source,
)
from services.official_alerts.models import OfficialAlert

__all__ = [
    "OfficialAlert",
    "OfficialAlertSource",
    "register_official_alert_source",
    "get_official_alerts_for_location",
]
