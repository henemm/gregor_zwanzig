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

    Issue #1086 / Issue #1245 (Adversary-Korrektur F003, KRITISCH -- ersetzt
    den vorherigen Greedy-Merge, der nicht-transitiv und reihenfolgeabhaengig
    war und dadurch Same-Source-Perioden verschlucken konnte): deterministische
    ZWEI-PASS-QUELLEN-PARTITIONIERUNG statt eines mutierenden Scans.

    PO-Entscheidung (Zielkonflikt-Aufloesung): **„nie doppelt"** hat Vorrang.
    Pass 1 bestimmt je ``hazard`` die EINE „beste" Quelle (hoechstes ``level``
    ueber alle Alerts dieser Gefahr an diesem Punkt; bei Gleichstand die
    ZUERST gesammelte = zuerst registrierte Quelle). Pass 2 behaelt NUR Alerts
    dieser besten Quelle je Gefahr -- Alerts anderer Quellen derselben Gefahr
    entfallen ersatzlos (Cross-Source-Kollaps, #1086: GeoSphere vs.
    MeteoAlarm liefern nie zwei Karten fuer dasselbe Ereignis, unabhaengig
    davon, ob ihre gemeldeten Zeitraeume geringfuegig abweichen). Innerhalb
    der besten Quelle kollabieren nur EXAKTE Dubletten (identischer
    ``(valid_from, valid_to)``) auf das hoechste ``level``; unterschiedliche
    Perioden derselben Quelle bleiben getrennt (#1245 -- der Ur-Fall, zwei
    Vigilance-Hitze-Zeitfenster derselben Single-Source, ist automatisch die
    „beste" Quelle und behaelt daher alle seine Perioden).

    Bewusst NICHT ueber einen normalisierten Namens-Schluessel in
    ``dedupe_official_alerts()``, weil diese Funktion im Orts-Vergleich ueber
    MEHRERE Orte kombiniert aufgerufen wird und ein namensbasierter Schluessel
    dort verschiedene Orte faelschlich verschmelzen wuerde (Adversary F002).
    Da dieser Kollaps ausschliesslich innerhalb eines einzelnen
    ``(lat, lon)``-Aufrufs wirkt, ist eine ortsuebergreifende Verwechslung
    strukturell ausgeschlossen. Alerts unterschiedlicher ``hazard`` bleiben
    alle erhalten; die Reihenfolge bleibt stabil (erstes Auftreten der
    behaltenen Alerts).

    Known Limitation (PO-akzeptiert): eine Periode, die EXKLUSIV von einer
    NICHT-besten Quelle derselben Gefahr gemeldet wird, faellt weg -- Folge
    der „nie doppelt"-Entscheidung, keine Nebenwirkung.
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

    # Pass 1: je hazard die "beste" Quelle bestimmen (hoechstes level;
    # Gleichstand: zuerst gesammelt).
    best_source: dict[str, str] = {}
    best_level: dict[str, int] = {}
    for alert in results:
        if alert.hazard not in best_level or alert.level > best_level[alert.hazard]:
            best_level[alert.hazard] = alert.level
            best_source[alert.hazard] = alert.source

    # Pass 2: nur Alerts der besten Quelle je hazard behalten; exakte
    # Dubletten (gleicher Zeitraum) kollabieren auf hoechstes level;
    # verschiedene Perioden derselben Quelle bleiben getrennt.
    kept: dict[tuple, OfficialAlert] = {}
    order: list[tuple] = []
    for alert in results:
        if alert.source != best_source[alert.hazard]:
            continue
        key = (alert.hazard, alert.valid_from, alert.valid_to)
        if key not in kept:
            kept[key] = alert
            order.append(key)
        elif alert.level > kept[key].level:
            kept[key] = alert
    return [kept[k] for k in order]
