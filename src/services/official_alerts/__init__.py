"""Fundament fuer amtliche Wetterwarnungen im Orts-Vergleich (Issue #1034).

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md
"""
from __future__ import annotations

from services.official_alerts.avalanche_report import AvalancheReportSource
from services.official_alerts.base import (
    OfficialAlertSource,
    OfficialSourceQuery,
    collect_source_queries,
    filter_alerts_to_window,
    get_official_alerts_for_location,
    get_official_alerts_with_sources,
    get_official_alerts_with_status,
    register_official_alert_source,
)
from services.official_alerts.dpc import DpcSource
from services.official_alerts.geosphere_warn import GeoSphereWarnSource
from services.official_alerts.massif_closure import MassifClosureSource
from services.official_alerts.meteo_forets import MeteoForetsSource
from services.official_alerts.meteoalarm_feed import MeteoAlarmFeedSource
from services.official_alerts.models import OfficialAlert
from services.official_alerts.slf import SlfSource
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
# registrierte Quelle). Die fruehere kontingentierte EDR-Klasse (seit #1445 S3
# nicht mehr registriert) ist mit Issue #2266 zurueckgebaut; ``meteoalarm.py``
# enthaelt nur noch den geteilten CAP-Mapper, den der Feed-Weg nutzt.
register_official_alert_source(VigilanceSource())
register_official_alert_source(MeteoForetsSource())
register_official_alert_source(MassifClosureSource())
register_official_alert_source(GeoSphereWarnSource())
register_official_alert_source(MeteoAlarmFeedSource("IT"))
register_official_alert_source(MeteoAlarmFeedSource("AT"))
# Issue #1681: MeteoAlarmFeedSource("DE") NACH AT, VOR DpcSource -- keine
# funktionale Abhaengigkeit (eigene DWD-Kreisgeometrie, kein ZAMG-Cache);
# Gewitter-Tie-Break "zuerst registriert gewinnt" betrifft DE nur bei
# Ueberschneidung mit DPC. "Nicht zustaendig"-Antworten von AT/GeoSphere/DPC
# kompensieren einen DE-Ausfall nicht (warn_egress.mark_not_covered, AC-3).
register_official_alert_source(MeteoAlarmFeedSource("DE"))
# Issue #1442 S1: MeteoAlarmFeedSource("CH") NACH DE, VOR DpcSource und SLF --
# Gewitter-Tie-Break "zuerst registriert gewinnt" (#1427 S2); SLF liefert eine
# andere Gefahrenart (avalanche_bulletin), Wetterwarnung steht vor der Lawine.
register_official_alert_source(MeteoAlarmFeedSource("CH"))
# Issue #1442 S2: NO, SE, FI NACH CH, VOR DpcSource (gleicher Tie-Break). Keine
# Nationalquelle ueberlappt; an Grenzpunkten liefert jede Quelle nur Warnungen
# ihres eigenen Feed-Polygons bzw. ihrer EMMA-Zone -- keine Doppelanzeige.
register_official_alert_source(MeteoAlarmFeedSource("NO"))
register_official_alert_source(MeteoAlarmFeedSource("SE"))
register_official_alert_source(MeteoAlarmFeedSource("FI"))
register_official_alert_source(DpcSource())
# Issue #1441 (ADR-0089): Lawinen-Lagebericht als LETZTE Quelle -- eigene
# Gefahrenart `avalanche_bulletin`, konkurriert mit keiner Bestandsquelle;
# die Position haelt den Tie-Break der Bestandsquellen unveraendert.
register_official_alert_source(AvalancheReportSource())
# Issue #1441 S3 (ADR-0091): SLF-Lagebericht DIREKT nach avalanche.report (AT/CH-
# Polygone disjunkt). Diese Zeile ist der einzige Schalter: lehnt das SLF die
# Nutzung ab, wird nur sie entfernt (Antrag #7).
register_official_alert_source(SlfSource())

__all__ = [
    "OfficialAlert",
    "OfficialAlertSource",
    "register_official_alert_source",
    "get_official_alerts_for_location",
    "get_official_alerts_with_status",
    "get_official_alerts_with_sources",
    "collect_source_queries",
    "OfficialSourceQuery",
    "filter_alerts_to_window",
    "VigilanceSource",
    "MeteoForetsSource",
    "MassifClosureSource",
    "GeoSphereWarnSource",
    "MeteoAlarmFeedSource",
    "DpcSource",
    "AvalancheReportSource",
    "SlfSource",
]
