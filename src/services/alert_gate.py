"""Geteilte Freigabe-Steuerung des Nowcast-Alarms (Issue #1467 Scheibe S3).

SPEC: docs/specs/modules/rework_1467_s3_nowcast.md

EIN Baustein fuer BEIDE Nowcast-Pfade — den Trip-Radar-Zweig
(`trip_alert.py::check_radar_alerts`) und den Vergleichs-Nowcast
(`compare_radar_alert.py::_check_one_preset`). Vorlage ist die bisherige
Inline-Kette des Trip-Pfads (`trip_alert.py:748-765`); der Vergleichs-Pfad
zieht damit an sie heran, statt eine zweite, unvollstaendige Fassung
weiterzufuehren (ADR-0021, Trip/Vergleich-Teilungsregel).

Feste Reihenfolge, Abbruch bei der ERSTEN zutreffenden Stufe:

    Ruhezeit  ->  Sperrzeit  ->  Tages-Obergrenze

Die Reihenfolge ist Teil der Zusicherung, nicht Geschmack: die Ruhezeit ist
die billigste Pruefung und die einzige, die auch dann gilt, wenn gar kein
Alarm anstuende; die Tages-Obergrenze ist die teuerste (Dateizugriff auf den
Zaehler). Alle drei laufen VOR der Datenbeschaffung — ein gesperrter Lauf
kostet damit keinen Nowcast-Abruf mehr.

`is_quiet_hours()` wird UNVERAENDERT durchgereicht: kein eigenes `try/except`,
kein `contextlib.suppress` an dieser Aufrufstelle. Der Schutz gegen
unbrauchbare Ruhezeit-Werte lebt ausschliesslich in
`DeviationAlertEngine.is_quiet_hours()` (fix_1479 AC-11, AST-Waechter
`tests/tdd/test_alert_quiet_hours_robustness.py`).

`record_nowcast_sent()` buendelt die beiden Buchungen (Tageszaehler +
Sperrzeit) und wird AUSSCHLIESSLICH nach erfolgreicher Zustellung gerufen —
ein fehlgeschlagener Versuch darf weder Budget noch Sperrzeit verbrauchen
(F001-Semantik, unveraendert aus beiden Bestandsstellen uebernommen).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import NamedTuple, Optional
from zoneinfo import ZoneInfo

from services import alert_daily_limit, alert_log
from services.deviation_alert_engine import DeviationAlertEngine
from services.throttle_store import ThrottleStore

logger = logging.getLogger("alert_gate")


class GateResult(NamedTuple):
    """Ergebnis der Freigabe-Pruefung.

    `reason` traegt bei einer Abweisung die sperrende Stufe als
    `alert_log`-Konstante (`REASON_QUIET_HOURS` | `REASON_COOLDOWN` |
    `REASON_DAILY_LIMIT`) und ist bei einer Freigabe `None`.
    """

    allowed: bool
    reason: Optional[str] = None


_ALLOWED = GateResult(True, None)


def _resolve_store(user_id: str, throttle_store: Optional[ThrottleStore]) -> ThrottleStore:
    """Uebergebenen Speicher benutzen, sonst einen eigenen oeffnen.

    Der Trip-Pfad haelt seit #1213 ohnehin einen `ThrottleStore` je Service —
    er reicht ihn durch, statt einen zweiten zu oeffnen (jede Instanz laeuft
    beim Anlegen durch die Legacy-Migrationspruefung).
    """
    return throttle_store if throttle_store is not None else ThrottleStore(user_id)


def check_nowcast_gate(
    *,
    user_id: str,
    throttle_scope: str,
    throttle_key: str,
    cooldown_minutes: Optional[int],
    quiet_from: Optional[str],
    quiet_to: Optional[str],
    context_label: str,
    now: datetime,
    zone: ZoneInfo,
    daily_limit_reason: str = "nowcast",
    throttle_store: Optional[ThrottleStore] = None,
) -> GateResult:
    """Darf fuer diese Entitaet jetzt ein Nowcast-Alarm rausgehen?

    `daily_limit_reason` ist mit Bedacht auf `"nowcast"` vorbelegt: nur dieser
    Grund prueft gegen das VOLLE Tagesbudget. `reason="forecast_change"`
    prueft gegen ein um die NowCast-Reserve reduziertes Limit (#1555) — ein
    Compare-eigener Grund waere zwar heute gleichwertig, verloere den Schutz
    aber still, sobald die Reserve-Tabelle waechst. Beide Nowcast-Pfade
    benutzen deshalb denselben Grund.

    Issue #1726: `zone` ist PFLICHT und geht an BEIDE zonenabhaengigen Stufen —
    Ruhezeit UND Tages-Obergrenze. Die Schranke hat kein eigenes Objekt im Scope
    (geteilt Trip+Vergleich), deshalb liefern ihre zwei Aufrufer die Zone."""
    if DeviationAlertEngine.is_quiet_hours(
        now, quiet_from, quiet_to, zone, context_label=context_label
    ):
        logger.debug("Nowcast-Alarm unterdrueckt (Ruhezeit) fuer %s", context_label)
        return GateResult(False, alert_log.REASON_QUIET_HOURS)

    if _resolve_store(user_id, throttle_store).is_throttled(
        throttle_scope, throttle_key, cooldown_minutes, now
    ):
        logger.debug("Nowcast-Alarm unterdrueckt (Sperrzeit) fuer %s", context_label)
        return GateResult(False, alert_log.REASON_COOLDOWN)

    if not alert_daily_limit.is_allowed(user_id, now, zone, reason=daily_limit_reason):
        logger.debug(
            "Nowcast-Alarm unterdrueckt (Tages-Obergrenze) fuer %s", context_label
        )
        return GateResult(False, alert_log.REASON_DAILY_LIMIT)

    return _ALLOWED


def record_nowcast_sent(
    *,
    user_id: str,
    throttle_scope: str,
    throttle_key: str,
    now: datetime,
    zone: ZoneInfo,
    throttle_store: Optional[ThrottleStore] = None,
) -> None:
    """Tageszaehler und Sperrzeit buchen — NUR nach erfolgreicher Zustellung.
    #1726: `zone` ist PFLICHT; wer hier eine andere uebergibt als
    `check_nowcast_gate()`, fuellt einen anderen Zaehler als den geprueften.
    """
    alert_daily_limit.increment(user_id, now, zone)
    _resolve_store(user_id, throttle_store).record(throttle_scope, throttle_key, now)
