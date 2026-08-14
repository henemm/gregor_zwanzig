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
from datetime import datetime, timedelta
from typing import Callable, NamedTuple, Optional
from zoneinfo import ZoneInfo

from services import alert_daily_limit, alert_log
from services.alert_briefing_anchor import last_briefing_at
from services.deviation_alert_engine import DeviationAlertEngine
from services.throttle_store import ThrottleStore
from utils.timezone import local_fmt

logger = logging.getLogger("alert_gate")

# Issue #1594: Vorlauf der Sperre, in Minuten. 60 — PO-Entscheidung, gemessen
# begruendet: die redundanten Alarme lagen 60 und 15 Minuten vor dem Briefing
# (04:00 und 04:45 UTC gegen 05:00). Ein 15-Minuten-Vorlauf haette die
# 04:00-Faelle nicht gefangen.
#
# 🔴 Es gibt KEINEN Nachlauf (Spec-Korrektur 2026-08-14). Die erste Fassung
# hatte einen — „letztes Briefing weniger als 15 Minuten her sperrt" — mit der
# Begruendung, ein gescheiterter Versand lasse den Anker unveraendert. Diese
# Begruendung war angenommen, nicht gemessen, und sie ist falsch:
# `_anchor_and_reset()` steht in BEIDEN Versandpfaden im Fehler-Zweig
# (`scheduler_dispatch_service.py`, `trip_report_scheduler.py`, #1629).
# `last_briefing_at()` beantwortet „wurde ein Briefing VERSUCHT?", nicht
# „wurde eines ZUGESTELLT?" — der Nachlauf schwieg damit gerade dann, wenn
# nichts ankam. Gemessen in der GREEN-Phase: sieben rote Bestandstests aus dem
# Nachlauf-Zweig, keiner aus dem Vorlauf. Der Anker hat hier deshalb das
# UMGEKEHRTE Vorzeichen — er beendet die Sperre, statt sie auszuloesen.
BRIEFING_VORLAUF_MINUTEN = 60

# Abtastung des Faelligkeits-Fensters. Das Praedikat beantwortet „faellig zu
# DIESEM Zeitpunkt?"; zwei Stichproben (jetzt und jetzt+Vorlauf) koennen ein
# dazwischen liegendes Faelligkeits-Fenster ueberspringen. Fuenf Minuten sind
# feiner als jede real existierende Faelligkeit — Versandzeiten sind
# stundengenau (Go kappt sie beim Schreiben UND beim Laden,
# `internal/store/slot_hour_normalization.go`), das schmalste reale Fenster ist
# damit eine volle Stunde. Die abgetastete Funktion ist rein, die Auswertungen
# kosten keinen Abruf.
_ABTAST_SCHRITT_MINUTEN = 5

# Wie weit zurueck der BEGINN eines bereits offenen Faelligkeits-Fensters
# gesucht wird — noetig, um „gab es fuer DIESES Briefing schon einen Versuch?"
# von „das war der Versuch von gestern" zu unterscheiden. Das breiteste reale
# Fenster ist das Trip-Nachholfenster (`NACHHOL_FENSTER_STUNDEN = 3`), der
# Ortsvergleich prueft Stundengleichheit (eine Stunde); vier Stunden decken
# beide mit Reserve ab. Bewusst eine eigene Zahl statt eines Imports aus dem
# Briefing-Scheduler: diese Stufe kennt nur das Praedikat, nicht sein
# Innenleben. Reicht ein Fenster doch weiter zurueck, faellt die Untergrenze
# auf `now - 4 h` — die Sperre endet dann eher zu frueh als zu spaet, und das
# ist die richtige Fehlerrichtung („kein Schweigen ohne Ersatz", AC-7/AC-8).
_RUECKBLICK_MINUTEN = 240


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


def _naechste_faelligkeit(
    now: datetime,
    briefing_due_at: Callable[[datetime], bool],
    vorlauf_minuten: int,
) -> Optional[datetime]:
    """Frueheste abgetastete Faelligkeit in `[now, now + vorlauf]` — `None`,
    wenn dort kein Briefing ansteht."""
    for versatz in range(0, vorlauf_minuten + 1, _ABTAST_SCHRITT_MINUTEN):
        moment = now + timedelta(minutes=versatz)
        if briefing_due_at(moment):
            return moment
    return None


def _fensterbeginn_untergrenze(
    now: datetime, briefing_due_at: Callable[[datetime], bool],
) -> datetime:
    """Der spaeteste abgetastete Zeitpunkt VOR dem laufenden Faelligkeits-
    Fenster — die Untergrenze, ab der ein Briefing-Versuch zu DIESEM Slot
    gehoeren kann.

    Nur aufzurufen, wenn das Fenster jetzt bereits offen ist. Bewusst der
    letzte NICHT-faellige Zeitpunkt statt des ersten faelligen: `now` liegt
    im 15-Minuten-Alarmtakt, nicht auf dem Fensterraster, die Rueckwaerts-
    Stichproben treffen den Fensterbeginn also nicht exakt. Der Versuch selbst
    liegt zwangslaeufig INNERHALB des Fensters (dort laeuft der Versand), eine
    Untergrenze bis zu einem Abtastschritt davor ist damit folgenlos — die
    umgekehrte Wahl waere es nicht: sie erklaerte einen echten Versuch zum
    „noch nicht versucht" und liesse die Sperre stehen.
    """
    for versatz in range(
        _ABTAST_SCHRITT_MINUTEN, _RUECKBLICK_MINUTEN + 1, _ABTAST_SCHRITT_MINUTEN,
    ):
        moment = now - timedelta(minutes=versatz)
        if not briefing_due_at(moment):
            return moment
    return now - timedelta(minutes=_RUECKBLICK_MINUTEN)


def check_briefing_imminent(
    *,
    user_id: str,
    entity_id: str,
    entity_type: str,
    now: datetime,
    zone: ZoneInfo,
    briefing_due_at: Callable[[datetime], bool],
    vorlauf_minuten: int = BRIEFING_VORLAUF_MINUTEN,
) -> bool:
    """Steht fuer diese Entitaet unmittelbar ein geplantes Briefing an, das
    noch nicht versucht wurde? (Issue #1594)

    `True` bedeutet: die Aenderungs- bzw. amtliche Meldung wird NICHT als
    eigenstaendige Zusatz-Nachricht verschickt. Sie geht dem Nutzer nicht
    verloren, sondern kommt Sekunden bis Minuten spaeter vollstaendig im
    Briefing an — die Meldung wird ERSETZT, nicht verschluckt (ADR-0009).

    Eine UND-verknuepfte Bedingung, beide Haelften rein lesend:

    1. **Vorlauf:** `briefing_due_at` ist fuer irgendeinen Zeitpunkt in
       `[now, now + vorlauf_minuten]` wahr.
    2. **Noch nicht versucht:** fuer dieses anstehende Briefing gab es noch
       keinen Versandversuch. Sobald einer stattgefunden hat — erfolgreich
       ODER gescheitert — endet die Sperre.

    🔴 Zu (2): `last_briefing_at()` heisst „versucht", nicht „zugestellt" —
    `_anchor_and_reset()` steht in beiden Versandpfaden im Fehler-Zweig
    (#1629). Genau deshalb beendet der Anker die Sperre, statt sie
    auszuloesen: nach einem Fehlschlag laufen Anker und Idempotenz-Vermerk
    auseinander (Anker gesetzt, Vermerk zurueckgenommen), der Trip bliebe das
    volle Nachholfenster ueber „faellig" — 60 Minuten Vorlauf + 3 Stunden
    Nachholfenster = bis zu vier Stunden Alarmstille, real gemessen (R6).

    🔴 Zuordnung des Versuchs zum SLOT, nicht zum Tag: verglichen wird gegen
    den Beginn des gerade offenen Faelligkeits-Fensters
    (`_fensterbeginn_untergrenze`), nicht gegen Mitternacht Ortszeit. Sonst
    beendete das erfolgreich verschickte MORGEN-Briefing auch die Sperre des
    Abend-Briefings desselben Tages. Ein Anker vom Vortag liegt weit vor jeder
    Untergrenze (Rueckblick 4 h) und beendet die Sperre folglich nie. Oeffnet
    das Fenster erst in der Zukunft, ist die Untergrenze `now` — ein Versuch
    liegt immer in der Vergangenheit, es gibt also nichts zu beenden.

    🔴 Ausdruecklich NICHT fuer NowCast (Regen-/Gewitter-Onset): der bleibt
    zeitkritisch und laeuft unveraendert weiter. `check_nowcast_gate()` ruft
    diese Funktion deshalb nicht auf.

    🔴 Rein lesend. Kein Melde-Gedaechtnis (`AlertStateService`), keine
    Sperrzeit (`ThrottleStore`), kein Tageszaehler, kein `alert_log`-Eintrag —
    dieselbe Eigenschaft, die #1233 fuer die Ruhezeit-Unterdrueckung
    zusichert. Und insbesondere kein Verbrauch von `report_config.skip_next`:
    `briefing_due_at` MUSS seiteneffektfrei sein (der Trip-Sammellauf
    `_get_active_trips()` ist es NICHT, er konsumiert `skip_next` per
    Read-Modify-Write mit `save_trip()`).

    Args:
        user_id: echte Nutzer-Kennung (Mandantentrennung, nie `"default"`).
        entity_id/entity_type: PROTOKOLL-Kennung des Briefing-Ankers — Trip
            `(trip.id, "trip")`, Ortsvergleich `(preset_id, "compare")`, genau
            so, wie beide Briefing-Pfade ihn schreiben
            (`trip_report_scheduler.py`, `scheduler_dispatch_service.py`).
        now: Zeitpunkt des Alarm-Laufs. Pflicht-Parameter ohne Systemuhr-
            Rueckfall (ADR-0051 Regel 3).
        zone: Ortszone der Entitaet (#1726) — Trip `anchor_tz(trip, now)`,
            Ortsvergleich `first_resolvable_tz(...)`. Beantwortet „welche
            Ortszeit war/ist gemeint", und genau so steht es in der Diagnose.
        briefing_due_at: das bestehende Faelligkeits-Praedikat der Entitaet,
            gegen einen Zeitpunkt ausgewertet. Es wird GEFRAGT, nicht neu
            gerechnet — eine eigene Zeitrechnung waere die vierte Fassung
            derselben Regel (eine liegt bereits im Frontend,
            `cockpitHelpers568.ts::deriveNextSend`).
        vorlauf_minuten: Fensterbreite, s. `BRIEFING_VORLAUF_MINUTEN`.

    Returns:
        True, wenn die Meldung unterdrueckt werden soll.
    """
    faellig_ab = _naechste_faelligkeit(now, briefing_due_at, vorlauf_minuten)
    if faellig_ab is None:
        return False

    untergrenze = (
        _fensterbeginn_untergrenze(now, briefing_due_at)
        if faellig_ab <= now
        else now
    )
    letzter_versuch = last_briefing_at(
        user_id=user_id, entity_id=entity_id, entity_type=entity_type,
    )
    if letzter_versuch is not None and letzter_versuch > untergrenze:
        logger.debug(
            "Keine Sperre fuer %s: das anstehende Briefing wurde um %s Ortszeit "
            "bereits versucht.",
            entity_id, local_fmt(letzter_versuch, zone),
        )
        return False

    logger.debug(
        "Meldung unterdrueckt: Briefing fuer %s ist um %s Ortszeit faellig und "
        "noch nicht versucht.",
        entity_id, local_fmt(faellig_ab, zone),
    )
    return True


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
