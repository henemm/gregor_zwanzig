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
from datetime import datetime, timezone
from typing import Protocol

from services.official_alerts import warn_egress
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


def _as_aware_utc(value: datetime | None) -> datetime | None:
    """Adversary F001: manche Quellen (vigilance.py/meteoalarm.py) liefern
    naive (tz-lose) Zeitstempel, wenn der Rohstring ohne "Z"/Offset kommt.
    Ein Vergleich naiv-vs-aware wirft sonst TypeError -- das verletzt das
    dokumentierte "wirft selbst nie"-Versprechen von
    get_official_alerts_for_location(). Naive Werte werden hier als UTC
    interpretiert (Quellen-Parser bleiben unangetastet, Scope von #1316)."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def filter_alerts_to_window(
    alerts: list[OfficialAlert],
    window_start: datetime | None,
    window_end: datetime | None,
) -> list[OfficialAlert]:
    """Ueberlappungssemantik (Issue #1316): eine Warnung bleibt, wenn ihr
    Zeitraum das Fenster ``[window_start, window_end]`` irgendwo schneidet.
    Teilueberlappung genuegt (AC-2). Warnungen ohne ``valid_from`` ODER ohne
    ``valid_to`` bleiben IMMER erhalten -- fail-safe, da eine fehlende
    Zeitangabe nie sicher als "abgelaufen" gelten kann (AC-3).

    Reihenfolge der Eingabeliste bleibt erhalten (keine Sortierung, kein
    zusaetzlicher Dedup-Schritt).

    Adversary F001: naive (tz-lose) ``valid_from``/``valid_to``/Fenstergrenzen
    werden vor dem Vergleich als UTC interpretiert (``_as_aware_utc``), damit
    kein ``TypeError`` bei naiv-vs-aware-Vergleichen entsteht."""
    window_start = _as_aware_utc(window_start)
    window_end = _as_aware_utc(window_end)
    kept: list[OfficialAlert] = []
    for alert in alerts:
        if alert.valid_from is None or alert.valid_to is None:
            kept.append(alert)
            continue
        valid_from = _as_aware_utc(alert.valid_from)
        valid_to = _as_aware_utc(alert.valid_to)
        if valid_to >= window_start and (window_end is None or valid_from <= window_end):
            kept.append(alert)
    return kept


def get_official_alerts_with_status(
    lat: float,
    lon: float,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    now: datetime | None = None,
) -> tuple[list[OfficialAlert], bool]:
    """Wie ``get_official_alerts_for_location``, liefert zusaetzlich einen
    ``unavailable``-Status (Issue #1348).

    ``unavailable = covering > 0 and failed >= 1`` (PO-Entscheid 2026-07-23,
    STRENG): schon EINE abdeckende, beim Fetch ausgefallene Quelle genuegt —
    sie haette eine Warnung tragen koennen, die die anderen Quellen nicht
    abdecken. Fehlt Coverage ganz (``covering == 0``) oder liefern ALLE
    abdeckenden Quellen erfolgreich (auch leer), ist ``unavailable = False``.

    "Ausgefallen" umfasst ZWEI Faelle (Issue #1348 Fix-Loop): (a) ``fetch()``
    wirft eine Exception; (b) ``fetch()`` liefert fail-soft ``[]``, obwohl ein
    ``warn_egress.cached_fetch()``-Aufruf darin real fehlschlug (Egress-Block/
    429/HTTP>=400/Netz-/Parse-Fehler ODER gecachter Fehlschlag). Fall (b) wird
    ueber ``warn_egress.observe_fetch_failure()`` erkannt — ohne den Fail-soft-
    Vertrag von ``fetch()`` zu brechen. Fall (b) ist der eigentliche Real-Pfad:
    die echten Quellen fangen jeden Fehler intern ab und werfen NICHT.

    Wirft selbst nie (fail-soft pro Quelle) — Fetch-/Filter-/Dedup-Koerper
    identisch zu ``get_official_alerts_for_location``.
    """
    results: list[OfficialAlert] = []
    covering, failed = 0, 0
    for source in _REGISTERED_SOURCES:
        try:
            source_name = str(source.name)
        except Exception:
            source_name = "unbekannte Quelle"
        try:
            does_cover = source.covers(lat, lon)
        except Exception:
            # Faellt-sicher: KEIN Coverage-Nachweis -> zaehlt weder als covering
            # noch als failed (ohne Zustaendigkeit kein Nicht-abrufbar-Alarm).
            logger.warning("official_alerts: %s covers() failed", source_name, exc_info=True)
            continue
        if not does_cover:
            continue
        covering += 1
        with warn_egress.observe_fetch_failure() as fetch_status:
            try:
                results.extend(source.fetch(lat, lon))
            except Exception:
                logger.warning("official_alerts: %s fetch failed", source_name, exc_info=True)
                failed += 1
                continue
        # Kein Throw, aber ein interner cached_fetch-Fehlschlag (Real-Pfad):
        # die Quelle lieferte fail-soft [], war aber real nicht abrufbar.
        if fetch_status["failed"]:
            failed += 1
    unavailable = covering > 0 and failed >= 1

    if now is None:
        now = datetime.now(timezone.utc)
    effective_start = max(now, window_start) if window_start is not None else now
    results = filter_alerts_to_window(results, effective_start, window_end)

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
    return [kept[k] for k in order], unavailable


def get_official_alerts_for_location(
    lat: float,
    lon: float,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    now: datetime | None = None,
) -> list[OfficialAlert]:
    """Fragt alle zustaendigen registrierten Quellen ab, fail-soft pro Quelle.

    Duenner Wrapper um ``get_official_alerts_with_status`` (Issue #1348) — der
    Rueckgabetyp bleibt eine reine Liste, damit alle 37 Bestandsaufrufer (u.a.
    ``trip_alert.py``, ``compare_official_alert.py``, ``comparison_engine.py``)
    unveraendert bleiben (AC-5).

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

    Issue #1316: VOR dem Zwei-Pass-Dedup wird ``filter_alerts_to_window()``
    angewendet, effektives Fenster ``[max(now, window_start or now),
    window_end or +inf)`` -- eine in der Vergangenheit liegende
    ``window_start`` darf ``now`` nie unterschreiten (Klemm-Invariante). Der
    Filter laeuft bewusst VOR Pass 1, sonst koennte eine bereits abgelaufene
    Warnung als "beste Quelle" gewinnen und eine noch gueltige verdraengen
    (AC-5).
    """
    alerts, _unavailable = get_official_alerts_with_status(
        lat, lon,
        window_start=window_start, window_end=window_end, now=now,
    )
    return alerts
