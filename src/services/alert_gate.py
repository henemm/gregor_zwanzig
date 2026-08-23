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
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, NamedTuple, Optional
from zoneinfo import ZoneInfo

import services.alert_urgency as alert_urgency
from services import alert_daily_limit, alert_log
from services.alert_briefing_anchor import last_briefing_at
from services.alert_state import AlertStateService
from services.deviation_alert_engine import DeviationAlertEngine
from services.radar_service import NOWCAST_HORIZON_MIN
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
    # Issue #2018: additiv, defaultet. `True` = die Meldung geht raus, aber
    # als NACHTRAG zu einer bereits zugestellten AMTLICHEN Warnung, statt als
    # zweiter voller Alarm -- ausschliesslich fuer eine Zustellung, die
    # ohnehin stattgefunden haette (s. `check_event_identity_gate`).
    # `allowed` bleibt "geht raus oder nicht"; bestehende
    # `if not gate.allowed`-Zweige sind unveraendert (Muster
    # `AlertMessage.reference_at`, #1916).
    is_addendum: bool = False
    addendum_source: Optional[str] = None       # "official" | "deviation" erreichbar (Issue #2050 S4c)
    addendum_reported_at: Optional[datetime] = None


_ALLOWED = GateResult(True, None)

# Ersatz-Zeitpunkt fuer Kandidaten ohne (parsbares) `reported_at` -- sie
# verlieren den Gleichstands-Vergleich, statt ihn zum Absturz zu bringen.
_MIN_TS = datetime.min.replace(tzinfo=timezone.utc)


def _entry_source(entry: dict) -> str:
    """Quelle eines Registereintrags. Alt-Eintraege (vor #2018) tragen kein
    `"source"`-Feld -- ihre Quelle steckt fail-soft in der Anwesenheit der
    Zeitfelder: Nowcast setzt NUR `point_at`, amtlich NUR `window_*`. Dieselbe
    Ableitung wie beim Schreiben (`record_event_identity`), damit ein Eintrag
    seine Quellen-Zuordnung nie durch sein Alter verliert (AC-A2)."""
    return entry.get("source") or ("nowcast" if entry.get("point_at") else "official")


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


def check_official_alert_gate(
    *,
    user_id: str,
    quiet_from: Optional[str],
    quiet_to: Optional[str],
    context_label: str,
    now: datetime,
    zone: ZoneInfo,
) -> GateResult:
    """Darf fuer diese Entitaet jetzt ein AMTLICHER Alarm rausgehen?
    (Issue #1467 Scheibe S4a)

    EIN Baustein fuer BEIDE amtlichen Pfade — den Trip-Zweig
    (`trip_alert.py::_send_official_alert_only`) und den Vergleichs-Zweig
    (`compare_official_alert.py::_check_one_preset`).

    Feste Reihenfolge, Abbruch bei der ERSTEN zutreffenden Stufe:

        Ruhezeit  ->  Tages-Obergrenze

    🔴 KEIN Cooldown-Parameter, und das ist hier kein Weglassen aus
    Sparsamkeit: „ein amtlicher Alarm scheitert nie an einer Sperrzeit" ist
    eine Eigenschaft des Funktionstyps, nicht eine Disziplin der Aufrufstelle
    (AC-3). Der Trip-Pfad las bis S4a den geteilten Sperrzeit-Topf `"trip"`
    mit — ein zugestellter Aenderungsalarm verschluckte damit bis zu 120
    Minuten lang jede amtliche Eskalation (E1). Geschrieben wird der Topf
    weiterhin, nur gelesen nicht mehr.

    Die Tages-Obergrenze prueft rein lesend (`is_allowed`); gebucht wird
    ausschliesslich per `alert_daily_limit.increment()` nach erfolgreicher
    Zustellung — beide Aufrufstellen behalten diese Buchung an ihrer Stelle
    (AC-15). Deshalb ist es wirkungsfrei, dass die Obergrenze mit diesem
    Baustein in beiden Pfaden VOR die Briefing-Sperre wandert (AC-12b).

    `is_quiet_hours()` wird UNVERAENDERT durchgereicht, wie bei
    `check_nowcast_gate()`: kein eigenes `try/except` an dieser Aufrufstelle.

    Der Grund im `GateResult` ist Diagnose, kein Protokoll-Auftrag: der
    amtliche Pfad schreibt weiterhin KEINE Unterdrueckungsgruende ins
    `alert_log` (E3, Geltungsbereich bleibt Nowcast-only).
    """
    if DeviationAlertEngine.is_quiet_hours(
        now, quiet_from, quiet_to, zone, context_label=context_label
    ):
        logger.debug("Amtlicher Alarm unterdrueckt (Ruhezeit) fuer %s", context_label)
        return GateResult(False, alert_log.REASON_QUIET_HOURS)

    if not alert_daily_limit.is_allowed(user_id, now, zone):
        logger.debug(
            "Amtlicher Alarm unterdrueckt (Tages-Obergrenze) fuer %s", context_label
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
    precip_mm: Optional[float] = None,
    urgency: Optional[str] = None,
    is_escalation_breakthrough: bool = False,
) -> None:
    """Tageszaehler und Sperrzeit buchen — NUR nach erfolgreicher Zustellung.
    #1726: `zone` ist PFLICHT; wer hier eine andere uebergibt als
    `check_nowcast_gate()`, fuellt einen anderen Zaehler als den geprueften.

    Issue #2065: `precip_mm` ist die gemeldete Menge und wird zur
    Vergleichsbasis der naechsten Ueberholungspruefung
    (`radar_overtakes_cooldown`). Sie wird — wie die Sperrzeit selbst —
    ausschliesslich NACH erfolgreicher Zustellung fortgeschrieben
    (F001-Symmetrie); wer sie weglaesst, hinterlaesst keine Basis.

    Issue #2050 S3b: `urgency` und `is_escalation_breakthrough` gehen
    unveraendert an `alert_daily_limit.increment()` durch — exakt das Muster,
    mit dem #2065 hier `precip_mm` ergaenzt hat. Auch sie werden
    ausschliesslich NACH erfolgreicher Zustellung fortgeschrieben: eine
    gescheiterte Zustellung darf weder die hoechste Stufe des Tages heben noch
    den einen Durchbruch verbrauchen.
    """
    alert_daily_limit.increment(
        user_id, now, zone,
        urgency=urgency, is_escalation_breakthrough=is_escalation_breakthrough,
    )
    _resolve_store(user_id, throttle_store).record(
        throttle_scope, throttle_key, now, precip_mm=precip_mm,
    )


# Issue #2065: Definition von "deutlich schlimmer" fuer die Sperrzeit-
# Ueberholung. Muster identisch zur PO-freigegebenen Briefing-Ueberholung
# (`trip_alert.py`, F008/#2020), aber mit EIGENEN Konstanten: die
# Vergleichsbasis ist eine andere (zuletzt GEMELDETE Menge statt
# Briefing-Ankuendigung), beide Regler sind deshalb eigenstaendig nachziehbar.
_COOLDOWN_OVERTAKE_FACTOR = 2.0
_COOLDOWN_OVERTAKE_MIN_ABSOLUTE_MM = 2.0


def radar_overtakes_cooldown(
    *, basis_mm: Optional[float], menge_mm: Optional[float],
) -> bool:
    """Ueberholt diese Lage die laufende Sperrzeit? (Issue #2065)

    UND-verknuepft: die Menge muss das `_COOLDOWN_OVERTAKE_FACTOR`-fache der
    zuletzt gemeldeten Menge erreichen UND fuer sich genommen ueber
    `_COOLDOWN_OVERTAKE_MIN_ABSOLUTE_MM` liegen. Ohne die absolute
    Untergrenze verdoppelte sich auch ein Nieselregen "deutlich".

    Fehlt die Vergleichsbasis (kein gespeicherter Wert — z.B. Sperre vom
    Kurzfristhinweis im Briefing gebucht), gibt es keinen Durchbruch: ein
    Durchbruch ohne Nachweis waere die gefaehrlichere Fehlerrichtung
    (Alarmflut), die Stille hier die konservative.

    🔴 Bewusst NICHT in `check_nowcast_gate()`: der Vergleich lebt im
    Trip-Pfad. Der geteilte Baustein bliebe sonst nicht in Signatur UND
    Verhalten unveraendert und der PO-zurueckgestellte Ortsvergleich bekaeme
    die Ausnahme still mit.
    """
    if basis_mm is None or menge_mm is None:
        return False
    return (
        menge_mm >= basis_mm * _COOLDOWN_OVERTAKE_FACTOR
        and menge_mm >= _COOLDOWN_OVERTAKE_MIN_ABSOLUTE_MM
    )


def last_nowcast_precip_mm(
    *,
    user_id: str,
    throttle_scope: str,
    throttle_key: str,
    throttle_store: Optional[ThrottleStore] = None,
) -> Optional[float]:
    """Die zuletzt gemeldete Menge zu dieser Sperre — die Vergleichsbasis der
    Ueberholungspruefung (Issue #2065). `None`, wenn der Eintrag aus dem
    Alt-Format stammt oder ohne Mengenangabe gebucht wurde."""
    _, precip_mm = _resolve_store(user_id, throttle_store).last_sent_with_precip(
        throttle_scope, throttle_key,
    )
    return precip_mm


def deviation_overtakes_cooldown(
    *, basis_urgency: Optional[str], urgency: str,
) -> bool:
    """Ueberholt diese Lage die laufende Sperrzeit? — Abweichungs-Zweig
    (Issue #2050 S3c)

    Schwester von `radar_overtakes_cooldown()`, gleiche Grundform (fehlende
    Vergleichsbasis ⇒ kein Durchbruch), andere Vergleichsformel: ein ordinaler
    RANGSPRUNG auf der bestehenden LOW/MODERATE/HIGH-Skala statt eines
    Faktors. Der Radar-Zweig vergleicht EINE physikalische Menge (mm/h), der
    Abweichungs-Zweig traegt potenziell mehrere heterogene Metriken (°C, km/h,
    mm) gleichzeitig — ein gemeinsamer Faktor ist auf ihnen nicht definierbar.
    `alert_urgency.exceeds` ist dafuer bereits etabliertes Vokabular, kein
    dritter Eskalationsbegriff.

    Bekannte Grenze, bewusst nicht gefangen: die Skala saettigt bei `HIGH` —
    eine Lage, die von `HIGH` auf noch schlimmer geht, erzeugt keinen
    Rangsprung und bricht nicht durch (s. Spec „Known Limitations").

    🔴 Bewusst NICHT in `check_nowcast_gate()` und in keinem anderen geteilten
    Gate: die Verortungs-Begruendung aus #2065 (s.o.) gilt unveraendert — der
    PO-zurueckgestellte Ortsvergleich darf die Ausnahme nicht erben.
    """
    if basis_urgency is None:
        return False
    return alert_urgency.exceeds(urgency, basis_urgency)


def last_deviation_urgency(
    *,
    user_id: str,
    throttle_scope: str,
    throttle_key: str,
    throttle_store: Optional[ThrottleStore] = None,
) -> Optional[str]:
    """Die Dringlichkeit, mit der die laufende Sperre gebucht wurde — die
    Vergleichsbasis der Ueberholungspruefung (Issue #2050 S3c). `None`, wenn
    der Eintrag aus dem Alt-Format stammt oder ohne Dringlichkeit gebucht
    wurde (amtlicher Zweig, `trip_alert.py:2480`)."""
    _, urgency = _resolve_store(user_id, throttle_store).last_sent_with_urgency(
        throttle_scope, throttle_key,
    )
    return urgency


# ═══════════════════════════════════════════════════════════════════════════
# Issue #1467 Scheibe S4b-1 — quellenuebergreifende Ereignis-Identitaet
# SPEC: docs/specs/modules/rework_1467_s4b_entdopplung.md
#
# `check_event_identity_gate()` ist die LETZTE Stufe an beiden Trip-
# Aufrufstellen (Nowcast `check_radar_alerts`, amtlich
# `_send_official_alert_only`) -- nach allen bestehenden, billigeren
# Pruefungen. Sie entdoppelt EIN UND DASSELBE Ereignis, wenn es ueber ZWEI
# verschiedene Quellen gemeldet wird (Nowcast und amtliche Warnung), anhand
# von Gefahrenklasse + Ortsbezug + ueberlappendem Zeitfenster. Anders als
# `check_nowcast_gate()`/`check_official_alert_gate()` ist sie
# entitaetsparametrisiert von Anfang an (Trip UND Compare, S4b-2 haengt nur
# noch an).
# ═══════════════════════════════════════════════════════════════════════════

# T2-Kanon (PO-Entscheid 2026-08-16): EINE Gefahrenklasse statt zwei. Die
# Messung am Produktivprotokoll (Spec Implementation Details) zeigt, dass die
# Radar-Einstufung konvektiv/nicht-konvektiv nur die Erscheinungsform
# DERSELBEN Zelle unterscheidet, nicht das Ereignis -- eine Aufspaltung in
# zwei Klassen liesse drei von vier gemessenen quellenuebergreifenden Paaren
# aneinander vorbeilaufen.
HAZARD_CLASS_WET = "wet"
_WET_HAZARDS = frozenset({"thunderstorm", "flood", "rain"})

# Issue #2050 S4c: dritter Auflösungsweg — der Abweichungs-Zweig kennt weder
# `is_convective` noch `hazard`, sondern eine Liste von Metrik-Schlüsseln.
# EIGENER Kanon, NICHT identisch mit `_WET_HAZARDS` (das sind amtliche
# Hazard-STRINGS, ein anderer Namensraum). Schnee-Metriken gehören
# ausdrücklich NICHT dazu (AC-7) — physikalisch Niederschlag, aber außerhalb
# des T2-Kanons.
_WET_METRICS = frozenset({
    "precip_sum_mm", "precip_heavy_onset_utc", "thunder_level_max",
    "thunder_onset_utc",
})


def resolve_hazard_class(
    *, is_convective: Optional[bool] = None, hazard: Optional[str] = None,
    metrics: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """T2-Kanon. Genau EIN Identifikationsweg pro Aufrufer: Nowcast liefert
    `is_convective`, amtlich liefert `hazard`, der Abweichungs-Zweig liefert
    `metrics` (Issue #2050 S4c). Unbekannter/anderer Hazard bzw. Metrik-Mix
    -> None (keine Klasse, nie entdoppelt, AC-4/AC-7).

    Ein Nowcast ist IMMER Niederschlag — `is_convective` unterscheidet nur
    die Erscheinungsform derselben Zelle, nicht das Ereignis (PO-Entscheid
    2026-08-16, Messung s. Spec Implementation Details T2, AC-4b).

    `metrics` ist nur dann `wet` (Entscheidung 1, Spec Implementation Details
    Punkt 1), wenn die Liste NICHT leer ist UND JEDE Metrik zum
    `_WET_METRICS`-Kanon gehört — ein einziger Anteil außerhalb des Kanons
    (z.B. eine Schnee- oder Windböen-Metrik) macht die Klasse `None` (AC-7).
    Eine leere Liste liefert ebenfalls `None` (`all([])` wäre sonst `True`)."""
    if is_convective is not None:
        return HAZARD_CLASS_WET
    if hazard in _WET_HAZARDS:
        return HAZARD_CLASS_WET
    if metrics is not None:
        metrics_list = list(metrics)
        if metrics_list and all(m in _WET_METRICS for m in metrics_list):
            return HAZARD_CLASS_WET
    return None


def _parse_event_ts(raw: object) -> Optional[datetime]:
    """Fail-soft (AC-7/AC-19): ein fehlendes oder unparsbares Zeitfeld liefert
    `None` statt zu knallen — der Aufrufer behandelt `None` als "kein
    Zeitbezug", nie als Absturz."""
    if raw is None:
        return None
    try:
        ts = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _covered_until(
    point_at: Optional[datetime], window_end: Optional[datetime],
) -> Optional[datetime]:
    """"Abgedecktes Ende" einer Meldung (V1): ein Zeitpunkt deckt sich selbst
    plus den Nowcast-Horizont ab, ein Intervall bis zu seinem Ende. Gilt fuer
    BEIDE Seiten des Vergleichs (Registereintrag UND neue Meldung) -- dieselbe
    Funktion, damit die V1-Ausnahme symmetrisch bleibt."""
    if point_at is not None:
        return point_at + timedelta(minutes=NOWCAST_HORIZON_MIN)
    return window_end


def _times_overlap(
    entry_point_at: Optional[datetime],
    entry_window_start: Optional[datetime],
    entry_window_end: Optional[datetime],
    point_at: Optional[datetime],
    window_start: Optional[datetime],
    window_end: Optional[datetime],
    cooldown_minutes: Optional[int],
) -> bool:
    """T4 — drei Vergleichsfaelle (Spec Implementation Details).

    Punkt gegen Punkt: Differenz <= `cooldown_minutes` (Vollstaendigkeits-
    fall, ueber die Trip-Aufrufstellen dieser Scheibe nicht end-to-end
    erreichbar). Punkt gegen Intervall: Ueberlappung mit `NOWCAST_HORIZON_MIN`-
    Puffer auf der Punkt-Seite -- der gemessene Kernfall (AC-6). Intervall
    gegen Intervall: echte Ueberlappung ohne Puffer, analog
    `official_alert_revision_verdict()`.

    Fehlt einer Seite jeder vergleichbare Zeitbezug -> kein Match, fail-soft
    (AC-7)."""
    if entry_point_at is not None and point_at is not None:
        limit_min = (
            cooldown_minutes if cooldown_minutes is not None else NOWCAST_HORIZON_MIN
        )
        return abs((point_at - entry_point_at).total_seconds()) <= limit_min * 60

    if entry_point_at is not None:
        entry_start = entry_point_at - timedelta(minutes=NOWCAST_HORIZON_MIN)
        entry_end = entry_point_at + timedelta(minutes=NOWCAST_HORIZON_MIN)
    elif entry_window_start is not None and entry_window_end is not None:
        entry_start, entry_end = entry_window_start, entry_window_end
    else:
        return False

    if point_at is not None:
        new_start = point_at - timedelta(minutes=NOWCAST_HORIZON_MIN)
        new_end = point_at + timedelta(minutes=NOWCAST_HORIZON_MIN)
    elif window_start is not None and window_end is not None:
        new_start, new_end = window_start, window_end
    else:
        return False

    return entry_start < new_end and new_start < entry_end


def _find_matching_entry(
    state: dict,
    hazard_class: str,
    segment_ids: list,
    point_at: Optional[datetime],
    window_start: Optional[datetime],
    window_end: Optional[datetime],
    cooldown_minutes: Optional[int],
) -> Optional[dict]:
    """Scannt das Register nach einem Kandidaten derselben Gefahrenklasse
    (T3/T4). Fail-soft ueberall (AC-7/AC-19): ein einzelner kaputter
    Registereintrag (fehlende Felder, unparsbare Zeit) wird uebersprungen,
    nie zum Absturz -- die naechsten Kandidaten werden trotzdem geprueft.

    AC-5 (Bruchstelle): eine leere Segment-Menge -- auf der neuen ODER der
    registrierten Seite -- erzeugt NIE ein Match.

    Issue #2018 (AC-A10): gesammelt werden ALLE gueltigen Kandidaten, geliefert
    wird der STAERKSTE (hoechste Dringlichkeit, bei Gleichstand der zuletzt
    gemeldete) -- nicht mehr der erstbeste. Der Nachtrag zitiert einen
    KONKRETEN Eintrag (Quelle + Uhrzeit im Text); ein zufaellig erstbester
    Treffer wuerde einen schwaecheren Bezug nennen. Vorbild
    `official_alerts.py::_pick_strongest`."""
    new_segments = {s for s in (segment_ids or []) if s}
    if not new_segments:
        return None

    candidates: list[dict] = []
    prefix = f"event_identity:{hazard_class}:"
    for key, entry in state.items():
        if not isinstance(key, str) or not key.startswith(prefix):
            continue
        if not isinstance(entry, dict):
            continue
        try:
            entry_segments = {s for s in (entry.get("segment_ids") or []) if s}
            if not entry_segments or new_segments.isdisjoint(entry_segments):
                continue

            entry_point_at = _parse_event_ts(entry.get("point_at"))
            entry_window_start = _parse_event_ts(entry.get("window_start"))
            entry_window_end = _parse_event_ts(entry.get("window_end"))
            if not _times_overlap(
                entry_point_at, entry_window_start, entry_window_end,
                point_at, window_start, window_end, cooldown_minutes,
            ):
                continue

            severity = entry["severity"]
            covered_until = _covered_until(entry_point_at, entry_window_end)
            if covered_until is None:
                continue
            candidates.append({
                "severity": severity,
                "covered_until": covered_until,
                # Issue #2018: Quelle und Meldezeitpunkt tragen den Bezug des
                # Nachtrags. `reported_at` ist fail-soft `None`, wenn das Feld
                # fehlt oder unparsbar ist -- das verhindert das Match NICHT,
                # laesst aber die Uhrzeit im Nachtragstext entfallen.
                "source": _entry_source(entry),
                "reported_at": _parse_event_ts(entry.get("reported_at")),
            })
        except (KeyError, TypeError, ValueError):
            # AC-19: ein kaputter/unbekannter Registereintrag zaehlt fail-soft
            # als "kein Match" -- nicht als Absturz. Issue #2018/#1405: der
            # Ueberspringen-Fall wird protokolliert, damit ein kaputter
            # Registereintrag nicht still ein Match verhindert -- sonst
            # ginge wieder ein VOLLER zweiter Alarm raus statt des
            # gerichteten Nachtrags.
            logger.warning(
                "Kaputter Registereintrag beim Auflösen übersprungen "
                "(Issue #2018/#1405), Schlüssel=%s",
                key,
            )
            continue
    if not candidates:
        return None
    # Staerkster Treffer ueber die GETEILTE Rangordnung (`highest_urgency`),
    # keine zweite Rangtabelle (#1481); bei Gleichstand der juengste Eintrag.
    staerkste = alert_urgency.highest_urgency(*(c["severity"] for c in candidates))
    return max(
        (c for c in candidates if c["severity"] == staerkste),
        key=lambda c: c["reported_at"] or _MIN_TS,
    )


def _covers_materially_more(
    entry_covered_until: datetime,
    point_at: Optional[datetime],
    window_end: Optional[datetime],
) -> bool:
    """V1-Ausnahme (AC-9): reicht die neue Meldung "wesentlich" -- mehr als
    `NOWCAST_HORIZON_MIN` -- ueber das bereits abgedeckte Ende des
    Registereintrags hinaus, kommt sie durch. Dieselbe `_covered_until()`
    wie oben, jetzt auf die neue Meldung angewendet -- symmetrische
    Definition von "abgedeckt"."""
    new_covered_until = _covered_until(point_at, window_end)
    if new_covered_until is None:
        return False
    return new_covered_until > entry_covered_until + timedelta(minutes=NOWCAST_HORIZON_MIN)


def check_event_identity_gate(
    *,
    user_id: str,
    entity_id: str,
    hazard_class: Optional[str],
    segment_ids: Iterable[str],
    severity: str,
    now: datetime,
    point_at: Optional[datetime] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    cooldown_minutes: Optional[int] = None,
    quantitative_escalation: bool = False,
    source: Optional[str] = None,
) -> GateResult:
    """Darf diese Meldung raus, oder ist sie ein quellenuebergreifendes
    Duplikat einer bereits gemeldeten Meldung (Issue #1467 Scheibe S4b-1)?

    Reiner Lesevorgang (AC-3) -- Registrierung ist ausschliesslich Sache von
    `record_event_identity()`, aufgerufen NACH erfolgreicher Zustellung
    (F001-Symmetrie zu `record_nowcast_sent`).

    `hazard_class=None` (T2: Gefahrenart ausserhalb des `wet`-Kanons) laesst
    IMMER durch (AC-4) -- die Pruefung greift fuer diese Gefahrenart
    strukturell nie, ohne das Register ueberhaupt zu lesen.

    Reihenfolge nach Fund eines Kandidaten, strukturell fest (Spec V1/V2):

        Eskalation (V2, IMMER zuerst) -> V1-Ausnahme -> Unterdrueckung

    Die Eskalationspruefung ist der ERSTE Zweig mit eigenem `return` -- vor
    der V1-Ausnahme und vor der eigentlichen Unterdrueckung. Eine echte
    Verschaerfung (hoehere Dringlichkeit) muss IMMER durchkommen, auch wenn
    ihr Zeitfenster das bereits abgedeckte NICHT wesentlich erweitert
    (AC-10) -- das ist die Absicherung gegen die gefaehrlichste
    Fehlerrichtung "Alarm bleibt aus".

    Issue #2065: `quantitative_escalation` ist eine bereits vom Aufrufer
    getroffene MENGEN-Feststellung, ODER-verknuepft mit der bestehenden
    Stufenpruefung. Notwendig, weil die dreistufige Skala
    LOW/MODERATE/HIGH bei 4 mm/h saettigt: eine Verdreifachung von 11 auf
    30 mm/h ist zweimal `HIGH`, `exceeds("HIGH","HIGH")` also False — die
    Verschaerfung ist an dieser Stelle strukturell unsichtbar. Vorbelegt mit
    `False`: kein Bestandsaufrufer aendert sein Verhalten.

    Issue #2050 S4c: `source` ist additiv. Radar und amtlich lassen ihn
    unveraendert weg -- der Fallback (Ableitung aus der Anwesenheit von
    `point_at`) bleibt fuer sie identisch (AC-12). Der Abweichungs-Zweig
    uebergibt IMMER `source="deviation"` explizit (AC-11), sonst laese ihn die
    alte Ableitung -- er traegt ein Zeitintervall wie ein amtlicher Eintrag --
    faelschlich als `"official"`."""
    if hazard_class is None:
        return _ALLOWED

    state = AlertStateService(user_id=user_id).load(entity_id)
    match = _find_matching_entry(
        state, hazard_class, list(segment_ids or []),
        point_at, window_start, window_end, cooldown_minutes,
    )
    if match is None:
        return _ALLOWED

    # Issue #2018: die Richtung entscheidet ausschliesslich ueber die FORM der
    # Zustellung, nie ueber ihr Ob. Nur "amtlich/Abweichung zuerst, Nowcast
    # danach" kennt den dritten Ausgang -- die Gegenrichtung ist eigenstaendig
    # ueber #1467 S4b PO-freigegeben und bleibt hier unangetastet.
    new_source = source if source is not None else (
        "nowcast" if point_at is not None else "official"
    )
    # Issue #2050 S4c: der Δ-Zweig ist jetzt ein zweiter moeglicher Vorgaenger
    # eines Nachtrags (bisher nur "official") -- Spec Implementation Details
    # Punkt 6.
    addendum_direction = (
        match["source"] in ("official", "deviation") and new_source == "nowcast"
    )

    if quantitative_escalation or alert_urgency.exceeds(severity, match["severity"]):
        # V2 — struktureller erster Zweig, bricht IMMER durch. In der
        # Nachtrags-Richtung geht DIESELBE Zustellung raus, nur als Nachtrag
        # statt als zweiter voller Alarm (AC-A1); sonst unveraendert.
        if addendum_direction:
            return GateResult(
                True, None, is_addendum=True,
                addendum_source=match["source"],
                addendum_reported_at=match["reported_at"],
            )
        return _ALLOWED

    if _covers_materially_more(match["covered_until"], point_at, window_end):
        # V1-Ausnahme — quellenunabhaengig und weiterhin VOLLER Alarm (AC-A7):
        # wesentlich neue Zeitabdeckung ist neue Information, kein Nachtrag.
        return _ALLOWED

    # Unveraendert Stille (AC-A8): aus Stille wird nie ein Nachtrag -- der
    # PO-Entscheid aendert die Form einer ohnehin stattfindenden Zustellung.
    logger.debug(
        "Ereignis-Identitaet unterdrueckt (%s) fuer %s/%s", hazard_class,
        entity_id, user_id,
    )
    return GateResult(False, alert_log.REASON_EVENT_DUPLICATE)


def record_event_identity(
    *,
    user_id: str,
    entity_id: str,
    hazard_class: str,
    segment_ids: Iterable[str],
    severity: str,
    now: datetime,
    point_at: Optional[datetime] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    source: Optional[str] = None,
) -> None:
    """Legt GENAU EINEN Registereintrag an (AC-2) -- AUSSCHLIESSLICH nach
    erfolgreicher Zustellung aufzurufen (F001-Symmetrie zu
    `record_nowcast_sent`). Read-Modify-Write mit Merge (CLAUDE.md): laedt
    den vollen Zustand der Entitaet, ergaenzt den neuen Schluessel, schreibt
    alles zurueck -- bestehende Eintraege (amtliches Melde-Gedaechtnis,
    Doppel-Alert-Guard) bleiben unangetastet.

    Registerschluessel `event_identity:<hazard_class>:<segment_ids>:<now>`
    (analog `_identity_hazard_prefix()` in `official_alerts.py`) -- eindeutig
    je Meldung, damit spaetere Registrierungen einander nicht ueberschreiben.

    Issue #2050 S4c: `source` ist additiv (AC-11/AC-12). Radar und amtlich
    lassen ihn weiterhin weg -- der Fallback (Ableitung aus der Anwesenheit
    von `point_at`) bleibt fuer sie identisch, die Signatur bricht fuer sie
    nicht. Der Abweichungs-Zweig traegt ein Zeitintervall wie ein amtlicher
    Eintrag und uebergibt deshalb IMMER `source="deviation"` explizit --
    sonst wuerde die alte Ableitung ihn faelschlich als `"official"` lesen."""
    segments = sorted({s for s in (segment_ids or []) if s})
    key = f"event_identity:{hazard_class}:{','.join(segments)}:{now.isoformat()}"

    service = AlertStateService(user_id=user_id)
    state = service.load(entity_id)
    state[key] = {
        "hazard_class": hazard_class,
        "segment_ids": segments,
        "severity": severity,
        # Issue #2018 (AC-A2) / #2050 S4c: expliziter Quellenvermerk, sonst
        # (Radar/amtlich, additiv unveraendert) dieselbe Fallunterscheidung
        # wie T2/T4 -- Nowcast setzt NUR `point_at`, amtlich NUR `window_*`.
        "source": source if source is not None else (
            "nowcast" if point_at is not None else "official"
        ),
        "point_at": point_at.isoformat() if point_at is not None else None,
        "window_start": window_start.isoformat() if window_start is not None else None,
        "window_end": window_end.isoformat() if window_end is not None else None,
        "reported_at": now.isoformat(),
    }
    service.save(entity_id, state)
