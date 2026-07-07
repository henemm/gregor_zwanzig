"""Quellen-Interface + Registry fuer amtliche Wetterwarnungen (Issue #1034).

Registry-Pattern analog zu ``providers/base.py``. Geo-Scope-Vorfilter analog
zu ``services/radar_service.py``. Keine echte Quelle in diesem Slice — folgt
in #1035.

SPEC: docs/specs/modules/issue_1034_official_alerts_foundation.md

Kein Import aus ``services.comparison_engine`` (Kreis-Import-Verbot laut
Spec) — nur Standardlib und eigene Modelle.
"""
from __future__ import annotations

import logging
from typing import Protocol

from services.official_alerts.models import OfficialAlert

logger = logging.getLogger(__name__)


class OfficialAlertSource(Protocol):
    """Protocol fuer amtliche Alert-Quellen (strukturelles Subtyping)."""

    @property
    def name(self) -> str: ...

    def covers(self, lat: float, lon: float) -> bool:
        """True, wenn diese Quelle fuer den gegebenen Punkt zustaendig ist."""
        ...

    def fetch(self, lat: float, lon: float) -> list[OfficialAlert]:
        """Liefert aktuelle Alerts fuer den gegebenen Punkt."""
        ...


_REGISTERED_SOURCES: list[OfficialAlertSource] = []


def register_official_alert_source(source: OfficialAlertSource) -> None:
    """Registriert eine Quelle in der Modul-Registry."""
    _REGISTERED_SOURCES.append(source)


def get_official_alerts_for_location(lat: float, lon: float) -> list[OfficialAlert]:
    """Fragt alle zustaendigen registrierten Quellen ab, fail-soft pro Quelle.

    Wirft selbst nie — ein Fehler einer Quelle darf den Wetter-Fetch der
    ComparisonEngine nicht stoeren (AC-3).
    """
    results: list[OfficialAlert] = []
    for source in _REGISTERED_SOURCES:
        try:
            source_name = str(source.name)
        except Exception:
            source_name = "unbekannte Quelle"
        try:
            if not source.covers(lat, lon):
                continue
            results.extend(source.fetch(lat, lon))
        except Exception:
            logger.warning("official_alerts: %s fetch failed", source_name, exc_info=True)
    return results
