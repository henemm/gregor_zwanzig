"""Fundament fuer amtliche Wetterwarnungen im Orts-Vergleich (Issue #1034).

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md
"""
from __future__ import annotations

from services.official_alerts.base import (
    OfficialAlertSource,
    get_official_alerts_for_location,
    register_official_alert_source,
)
from services.official_alerts.geosphere_warn import GeoSphereWarnSource
from services.official_alerts.massif_closure import MassifClosureSource
from services.official_alerts.meteo_forets import MeteoForetsSource
from services.official_alerts.meteoalarm import MeteoAlarmSource
from services.official_alerts.models import OfficialAlert
from services.official_alerts.vigilance import VigilanceSource

# Lazy-Registration bei Modul-Import (analog Provider-Pattern), Issue #1035/#1036/#1037/#1085/#1086.
# Reihenfolge verbindlich: MeteoAlarmSource NACH GeoSphereWarnSource (Label-Tie-Break
# bei gleicher Stufe im Cross-Source-Dedup, s. Spec #1086).
register_official_alert_source(VigilanceSource())
register_official_alert_source(MeteoForetsSource())
register_official_alert_source(MassifClosureSource())
register_official_alert_source(GeoSphereWarnSource())
register_official_alert_source(MeteoAlarmSource())

__all__ = [
    "OfficialAlert",
    "OfficialAlertSource",
    "register_official_alert_source",
    "get_official_alerts_for_location",
    "VigilanceSource",
    "MeteoForetsSource",
    "MassifClosureSource",
    "GeoSphereWarnSource",
    "MeteoAlarmSource",
]
