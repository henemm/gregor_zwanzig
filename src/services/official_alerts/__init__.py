"""Fundament fuer amtliche Wetterwarnungen im Orts-Vergleich (Issue #1034).

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md
"""
from __future__ import annotations

from services.official_alerts.base import (
    OfficialAlertSource,
    filter_alerts_to_window,
    get_official_alerts_for_location,
    get_official_alerts_with_status,
    register_official_alert_source,
)
from services.official_alerts.dpc import DpcSource
from services.official_alerts.geosphere_warn import GeoSphereWarnSource
from services.official_alerts.massif_closure import MassifClosureSource
from services.official_alerts.meteo_forets import MeteoForetsSource
from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource
from services.official_alerts.models import OfficialAlert
from services.official_alerts.vigilance import VigilanceSource

# Lazy-Registration bei Modul-Import (analog Provider-Pattern), Issue #1035/#1036/#1037/#1085/#1086/#1427/#1445.
# Reihenfolge verbindlich: GeoSphereWarnSource VOR MeteoAlarmFeedSource("AT")
# (Issue #1445 S3 Implementation Details Punkt 4/6 -- "null zusaetzliche
# ZAMG-Abrufe": die AT-Zonenaufloesung nutzt den ohnehin von GeoSphereWarnSource
# befuellten ZAMG-Cache weiter, funktioniert aber NUR in dieser Reihenfolge).
# MeteoAlarmFeedSource("AT") NACH MeteoAlarmFeedSource("IT") (Konsistenz,
# keine funktionale Notwendigkeit), VOR DpcSource -- eine ganz normale
# additive Quelle, kein fallback_for (Issue #1427 S2, Gewitter-Tie-Break bei
# Ueberschneidung: bei gleicher Stufe gewinnt MeteoAlarm als zuerst
# registrierte Quelle). ``MeteoAlarmSource`` (EDR-Index-Apparat, meteoalarm.py)
# wird seit Issue #1445 S3 NICHT MEHR registriert -- Code bleibt bestehen,
# dient nur noch dem Aequivalenznachweis (AC-5), ueber ihren eigenen
# Modulpfad ``services.official_alerts.meteoalarm.MeteoAlarmSource`` weiter
# erreichbar.
register_official_alert_source(VigilanceSource())
register_official_alert_source(MeteoForetsSource())
register_official_alert_source(MassifClosureSource())
register_official_alert_source(GeoSphereWarnSource())
register_official_alert_source(MeteoAlarmFeedSource("IT"))
register_official_alert_source(MeteoAlarmFeedSource("AT"))
register_official_alert_source(DpcSource())

__all__ = [
    "OfficialAlert",
    "OfficialAlertSource",
    "register_official_alert_source",
    "get_official_alerts_for_location",
    "get_official_alerts_with_status",
    "filter_alerts_to_window",
    "VigilanceSource",
    "MeteoForetsSource",
    "MassifClosureSource",
    "GeoSphereWarnSource",
    "MeteoAlarmFeedSource",
    "DpcSource",
]
