"""Ortsvergleich-Standalone-Alarm fuer amtliche Warnungen (#1216 Slice 2a).

Struktur-Analogie zu `CompareAlertService` (Preset-Loop, Tageslimit,
`_load_presets`, `_notification_service_for`), Detect-Logik-Analogie zu
`TripAlertService.check_official_alert_triggers` (State-Vergleich gegen den
zuletzt gemeldeten Warnstufen-Stand statt Δ-Wetter-Auswertung).

SPEC: docs/specs/modules/issue_1216_slice2_compare_official_alert.md

Kein Zeit-Cooldown (Adversary-Fix F002): anders als der Δ-Wetter-Pfad
(`CompareAlertService`, KEIN persistentes Level-Gedaechtnis, deshalb
zeitbasierter Cooldown) hat dieser Trigger-Typ mit dem alert_state-Vergleich
in `_detect()` (Key `official_alert:{region}:{hazard}`, Trigger nur bei
neuer Warnung oder gestiegenem Level) bereits ein ausreichendes, persistentes
Anti-Spam-Gedaechtnis. Ein zusaetzlicher ThrottleStore-Cooldown wuerde eine
echte Eskalation (z.B. GELB -> ORANGE Sekunden nach der GELB-Meldung) fuer
bis zu `cooldown_minutes` unterdruecken -- das widerspricht dem Zweck des
Features (rechtzeitige Warnung vor Verschaerfung). Das Tageslimit
(`alert_daily_limit`) bleibt die Obergrenze gegen Massen-Alarme.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import Settings
from i18n import Lang, resolve_user_lang
import app.day_window as day_window
from app.loader import load_all_locations
from output.renderers.alert.official_alerts import (
    dedupe_official_alerts,
    official_alert_revision_verdict,
    official_alert_state_entry,
    official_alert_state_key,
)
from services import alert_channel_threshold, alert_daily_limit, alert_log
from services import alert_retry_backoff, parallel_fetch
from services.compare_alert import preset_deadline, run_deadline_from
from services.throttle_store import ThrottleStore
import services.alert_urgency as alert_urgency
from services.alert_gate import (
    check_briefing_imminent,
    check_event_identity_gate,
    check_official_alert_gate,
    record_event_identity,
    resolve_hazard_class,
)
from services.alert_check_state import report_unit_failure
from services.briefing_slots import compare_slot_store
from services.alert_state import AlertStateService
from services.alert_channels import effective_alert_channels
from services.compare_alert_channels import effective_compare_telegram_style
from services.compare_alert_guard import is_silenced
from services.compare_preset_access import (
    load_compare_alert_presets,
    notification_service_for_preset,
)
from services.compare_slot_scheduler import due_or_raise, presets_due_for_hour
from services.notification_service import NotificationService
from services.alert_state import prune_expired_official
from services.official_alert_allclear import (
    AllClearQuery, allclear_settled, apply_official_allclears, detect_official_allclear,
    reported_meta,
)
from services.official_alerts import collect_source_queries, get_official_alerts_for_location
from utils.timezone import first_resolvable_tz, local_dt

logger = logging.getLogger("compare_official_alert")


def _effective_telegram_style(preset: dict) -> str:
    """Duenner Wrapper auf den EINEN Aufloeser (Issue #1467 S2, K-5).

    Die Fassung wohnt seit der Korrektur-Runde in
    `compare_alert_channels.py` — dort, wo schon die Compare-Kanalregel aus
    AG1 steht —, weil sie seither von BEIDEN Ortsvergleich-Alarmwegen
    gebraucht wird (amtliche Warnung hier, Aenderungsalarm in
    `compare_alert.py`). Dieser Name bleibt als Bestands-Einstiegspunkt
    stehen; das Verhalten ist unveraendert."""
    return effective_compare_telegram_style(preset)


def _raise_first_failure(preset_id: str, outcomes: list) -> None:
    """Issue #1539 S6: Fristablauf je Ort laut loggen, dann die erste
    gescheiterte Eingabeposition als Ausnahme des Presets werfen."""
    for out in outcomes:
        if out.skipped:
            logger.error(
                "Compare-Amtlich-Alarm: Warn-Abruf fuer Preset %s / Ort %s nicht "
                "abgeschlossen (Grund: %s)", preset_id, out.item[0].id, out.skipped,
            )
    for out in outcomes:
        if out.error is not None:
            raise out.error
        if out.skipped:
            raise RuntimeError(
                f"Warn-Abruf fuer Preset {preset_id} / Ort {out.item[0].id} "
                f"nicht abgeschlossen ({out.skipped})"
            )


#: Issue #1405 S1: Backoff-Scope des amtlichen Ortsvergleich-Alarms (dieser
#: Pfad kennt sonst keine Sperrzeit im ``ThrottleStore``).
_RETRY_SCOPE = "compare_official"

class CompareOfficialAlertService:
    """Wertet amtliche Warnungen je Compare-Preset/Ort aus und versendet EINEN
    gebuendelten Standalone-Alarm (Orts-Scope) bei neuen/eskalierten Treffern."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        user_id: str,
        mail_sink: Optional[object] = None,
        sms_sink: Optional[object] = None,
        telegram_sink: Optional[object] = None,
    ) -> None:
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._user_id = user_id
        # Issue #2672: Sprache EINMAL je Dienstobjekt (Nutzer), kein Modulzustand.
        self._lang: Lang = resolve_user_lang(user_id)
        self._mail_sink = mail_sink
        self._sms_sink = sms_sink
        self._telegram_sink = telegram_sink

    # Issue #2217: Zahl der im letzten Lauf gescheiterten Presets (Router -> failed).
    last_failed_count: int = 0
    # Issue #1539 S0: Messung des letzten Laufs (Router -> checked/duration_s).
    last_checked_count: int = 0
    last_duration_s: float = 0.0
    # Issue #1539 S6: Lauf-Frist (absolut, monotonic); None = keine Lauf-Frist.
    _run_deadline_at: Optional[float] = None

    def check_all_compare_presets(self) -> int:
        started_at = time.monotonic()
        self._run_deadline_at = run_deadline_from(started_at)
        try:
            sent, self.last_failed_count = self._check_all_counted()
        finally:
            self._run_deadline_at = None
        self.last_duration_s = time.monotonic() - started_at
        logger.info(
            f"compare_official_alert: Lauf beendet nach {self.last_duration_s:.3f}s fuer "
            f"user_id={self._user_id} (checked={self.last_checked_count} "
            f"alerts_sent={sent} failed={self.last_failed_count})"
        )
        return sent

    def _check_all_counted(self) -> tuple[int, int]:
        presets = self._load_presets()
        self.last_checked_count = len(presets)
        if not presets:
            return 0, 0
        all_locations = {loc.id: loc for loc in load_all_locations(user_id=self._user_id)}
        sent = failed = 0
        for preset in presets:
            try:
                if self._check_one_preset(preset, all_locations):
                    sent += 1
            except Exception:
                # Issue #2217: ein kaputtes Preset reisst die Folge-Presets nicht mit.
                report_unit_failure("Compare-Amtlich-Alarmlauf", preset.get("id", ""))
                failed += 1
        return sent, failed

    def _check_one_preset(self, preset: dict, all_locations: dict) -> bool:
        preset_id = preset.get("id", "")
        location_ids = preset.get("location_ids") or []
        if not preset_id or not location_ids:
            return False
        # #1233 (schedule=="manual" / archived_at) — seit Issue #1467 S2 AG6
        # steht diese Regel nur noch EINMAL, im geteilten Baustein (AC-28);
        # `paused_at` kommt dort hinzu. Verhaltensgleich fuer den amtlichen
        # Pfad, deshalb bleibt `test_compare_official_alert.py` (AC-4 aus
        # #1233) unveraendert gruen.
        if is_silenced(preset):
            logger.debug(
                f"Compare official alert skipped: preset {preset_id} is paused/archived"
            )
            return False
        official_warnings = preset.get("official_warnings")
        # Issue #1258: official_warnings.enabled loest das Legacy-Feld ab.
        # official_warnings is None -> Preset noch nicht migriert -> Fallback
        # auf das bisherige Ist-Verhalten (kein Bestandsnutzer verliert Alarme).
        # Fix-Loop F003: ein leeres {} (kein "enabled"-Schluessel) zaehlt
        # NICHT als migriert -> ebenfalls Legacy-Fallback statt stillem
        # Default True (analog trip_alert.py).
        official_warnings_migrated = (
            isinstance(official_warnings, dict) and "enabled" in official_warnings
        )
        if official_warnings_migrated:
            if not official_warnings.get("enabled", True):
                return False
        elif not preset.get("official_alert_triggers_enabled", True):
            return False
        # Issue #1726: Ruhezeit UND Tageszaehler laufen auf der Ortszeit des
        # ERSTEN aufloesbaren Orts (#1378 AC-4, AC-15) — EINE Aufloesung fuer
        # beide Stufen, damit sie nicht auseinanderfallen.
        zone = first_resolvable_tz(
            (all_locations.get(lid) for lid in location_ids), context_label=preset_id,
        )
        # #1233: Ruhezeit unterdrueckt frueh -> kein State-Verbrauch der Warnung,
        # damit sie nach Ende der Ruhezeit noch als "neu" zugestellt wird (AC-2).
        #
        # Issue #1467 S4a: Ruhezeit UND Tages-Obergrenze stehen seither im
        # geteilten Baustein `check_official_alert_gate` — demselben, den auch
        # der amtliche Trip-Pfad ruft. Die Tages-Obergrenze wandert damit VOR
        # `_detect()` (E2): ein erschoepftes Kontingent kostet keinen
        # Warnungs-Abruf mehr gegen eine Quelle, die produktiv ohnehin an ihrem
        # Tagesbudget haengt. Rein lesend — gebucht wird weiterhin erst nach
        # erfolgreicher Zustellung (`alert_daily_limit.increment`, AC-15).
        # `is_silenced` bleibt bewusst AUSSERHALB des Bausteins (AC-9): Trips
        # kennen den Riegel nicht, und ein pausierter Trip soll weiter
        # alarmieren (#995).
        # Issue #2050 S3b (Szenario 10, AC-9, Luecke E3 spiegelbildlich zum
        # Trip): der Grund lag hier schon immer vor — bis dahin verwarf ihn
        # der Aufrufer mitsamt dem `GateResult`.
        gate = check_official_alert_gate(
            user_id=self._user_id,
            quiet_from=preset.get("alert_quiet_from"),
            quiet_to=preset.get("alert_quiet_to"),
            context_label=preset_id,
            now=datetime.now(timezone.utc),
            zone=zone,
        )
        if not gate.allowed:
            # Absicherung je Preset, nicht um den Stapellauf (Muster `fix_1479`).
            try:
                alert_log.append_suppressed_entry(
                    self._user_id, entity_id=preset_id, entity_type="compare",
                    reason=alert_log.REASON_OFFICIAL_ALERT,
                    gate_reason=gate.reason,
                    effective_channels=self._effective_channels(preset),
                )
            except Exception as e:
                logger.error(
                    "Compare-Amtlich: Unterdrueckungs-Protokoll fuer Preset %s "
                    "fehlgeschlagen (%s) — der Alarm blieb aus (Grund: %s), "
                    "nur der Protokoll-Eintrag fehlt.", preset_id, e, gate.reason,
                )
            return False

        # Issue #1594: dieselbe Stufe wie im Vergleichs-Aenderungspfad, gleiche
        # Position (nach der Ruhezeit, VOR `_detect()`). Rein lesend — die
        # #1233-Zusicherung „kein State-Verbrauch bei Unterdrueckung" bleibt
        # damit auch fuer diese Stufe erhalten. Ein Preset OHNE geplantes
        # Briefing faellt aus der Sperre (AC-7/AC-9): `presets_due_for_hour`
        # prueft Stilllegung, `end_date`, `weekly` und Slot-Schalter selbst.
        if check_briefing_imminent(
            user_id=self._user_id, entity_id=preset_id, entity_type="compare",
            now=datetime.now(timezone.utc), zone=zone,
            # Issue #1777: Fenster + abgeschlossener Vermerk (is_recorded).
            briefing_due_at=lambda moment, store=compare_slot_store(self._user_id): due_or_raise(
                presets_due_for_hour([preset], all_locations, moment, store=store)
            ),
        ):
            logger.debug(f"Compare official alert briefing imminent for {preset_id}")
            return False

        locs = [all_locations[lid] for lid in location_ids if lid in all_locations]
        if not locs:
            return False

        sources = (official_warnings or {}).get("sources") or None
        self._pending_allclears = []
        tagged_alerts, per_location_new = self._detect(preset_id, locs, sources)
        allclears = list(self._pending_allclears)  # Issue #1441 S2
        if not tagged_alerts and not allclears:
            return False

        now = datetime.now(timezone.utc)
        notification_service = self._notification_service_for(preset)
        effective_channels = self._effective_channels(preset)

        # Issue #1917 S4b-2: quellenuebergreifende Ereignis-Identitaet, EIN
        # Gate-Aufruf PRO betroffenem Ort — anders als im Trip-Pfad (#1467
        # S4b-1, EIN Aufruf je Alert), weil die Registertrennung bei Compare
        # ueber die Ort-Datei `f"{preset_id}:{loc_id}"` laeuft. Betrifft ein
        # Alert mehrere Orte und ist er nur an einem davon eine Dublette,
        # wird das Paar auf die verbleibenden Orte REDUZIERT — es ganz zu
        # verwerfen kostete den anderen Orten ihre berechtigte Warnung
        # (Fehlerrichtung „Alarm bleibt aus"). Gefiltert wird VOR der
        # Dringlichkeits-Berechnung, sonst bestimmte eine unterdrueckte
        # Warnung noch die Kanal-Schwelle mit.
        filtered_alerts: list = []
        for alert, loc_ids in tagged_alerts:
            hazard_class = resolve_hazard_class(hazard=alert.hazard)
            alert_severity = alert_urgency.urgency_from_official_level(alert.level)
            remaining_loc_ids: list[str] = []
            for loc_id in loc_ids:
                identity_gate = check_event_identity_gate(
                    user_id=self._user_id, entity_id=f"{preset_id}:{loc_id}",
                    hazard_class=hazard_class, segment_ids=[loc_id],
                    severity=alert_severity, now=now,
                    window_start=alert.valid_from, window_end=alert.valid_to,
                )
                if identity_gate.allowed:
                    remaining_loc_ids.append(loc_id)
                    continue
                logger.debug(
                    f"Compare official alert unterdrueckt ({identity_gate.reason}) "
                    f"fuer {preset_id}:{loc_id}"
                )
                # Eine unterdrueckte Warnung darf das amtliche Melde-
                # Gedaechtnis nicht verbrauchen (Muster Trip-Pfad: dort geht
                # ebenfalls nur die GEFILTERTE Liste in die Zustands-
                # Fortschreibung) — sonst bliebe sie nach dem naechsten
                # Register-Reset dauerhaft aus.
                for_loc = per_location_new.get(loc_id) or []
                if alert in for_loc:
                    for_loc.remove(alert)
                try:
                    # Issue #2050 S6 (E-1): dieser Zweig steht INNERHALB der
                    # `for loc_id in loc_ids`-Schleife -- Warnung und Ort sind
                    # hier je EIN Wert, `measurement_point` ist deshalb IMMER
                    # eindeutig (kein `unique_or_none` noetig).
                    alert_log.append_suppressed_entry(
                        self._user_id, entity_id=preset_id, entity_type="compare",
                        reason=alert_log.REASON_OFFICIAL_ALERT,
                        gate_reason=identity_gate.reason,
                        effective_channels=effective_channels,
                        event_at=alert.valid_from.isoformat() if alert.valid_from else None,
                        event_end_at=alert.valid_to.isoformat() if alert.valid_to else None,
                        measurement_point={"location_id": loc_id},
                        source=alert.source,
                    )
                except Exception as e:
                    logger.error(
                        "Compare official alert: Unterdrueckungs-Protokoll "
                        "(Ereignis-Identitaet) fuer %s:%s fehlgeschlagen (%s) "
                        "— der Alarm blieb aus, nur der Protokoll-Eintrag fehlt.",
                        preset_id, loc_id, e,
                    )
            if remaining_loc_ids:
                filtered_alerts.append((alert, remaining_loc_ids))
        if not filtered_alerts and not allclears:
            return False
        tagged_alerts = filtered_alerts

        # Issue #1461 S3b-2b: die Dringlichkeit wird VOR dem Versand
        # hochgezogen (bisher entstand sie erst inline im `append_entry`-
        # Argument, also NACH dem Versand) -- `split_by_threshold()` braucht
        # sie davor. `effective_channels` bleibt fuers Protokoll ROH (rote
        # Linie #638), nur der tatsaechliche Versand (`allowed`) wird gefiltert.
        # Issue #1441 S2 (AC-4): Stapel-Max ueber Warnungen UND alte Stufen der
        # Entwarnungen.
        severity = alert_urgency.highest_urgency(*[
            alert_urgency.urgency_from_official_level(a.level)
            for a, _loc_ids in tagged_alerts
        ], *[
            alert_urgency.urgency_from_official_transition(ac.old_level, ac.new_level)
            for ac, _loc_ids in allclears
        ])
        allowed, suppressed = alert_channel_threshold.split_by_threshold(
            effective_channels, severity, preset.get("alert_channel_thresholds"),
        )
        # Issue #1405 S1 (ADR-0086): Fehlversuchs-Backoff je Ereignis (Ort +
        # Meldungs-Kennung) -- geteilter Baustein wie im amtlichen Trip-Pfad.
        retry_store = ThrottleStore(self._user_id)
        retry_fp = alert_retry_backoff.event_fingerprint(preset_id, [*(
            f"{loc_id}/{part}"
            for alert, loc_ids in tagged_alerts
            for part in alert_retry_backoff.official_alert_parts([alert])
            for loc_id in loc_ids
        ), *(f"{loc_ids[0]}/allclear:{ac.key}:{ac.new_rank}" for ac, loc_ids in allclears)])
        if alert_retry_backoff.backoff_active(retry_store, _RETRY_SCOPE, retry_fp):
            return False
        result = notification_service.send_multi_location_official_alert(
            preset.get("name", preset_id), locs, tagged_alerts,
            allowed,
            _effective_telegram_style(preset),
            mail_sink=self._mail_sink, sms_sink=self._sms_sink,
            telegram_sink=self._telegram_sink, allclears=[ac for ac, _l in allclears],
        )
        # Issue #2050 S6 (E-1): Ereigniszeit/Messpunkt/Quelle nur, wenn ALLE
        # Warnungen dieses Eintrags uebereinstimmen (`unique_or_none`) --
        # amtliche Warnungen kennen strukturell keine Vorwarnzeit und keine
        # Vergleichsbasis (analog Trip).
        _e1_event_at_dt = alert_log.unique_or_none(
            a.valid_from for a, _loc_ids in tagged_alerts
        )
        _e1_event_at = _e1_event_at_dt.isoformat() if _e1_event_at_dt is not None else None
        _e1_event_end_at_dt = alert_log.unique_or_none(
            a.valid_to for a, _loc_ids in tagged_alerts
        )
        _e1_event_end_at = (
            _e1_event_end_at_dt.isoformat() if _e1_event_end_at_dt is not None else None
        )
        _e1_loc_id = alert_log.unique_or_none(
            loc_id for _a, loc_ids in tagged_alerts for loc_id in loc_ids
        )
        _e1_measurement_point = (
            {"location_id": _e1_loc_id} if _e1_loc_id is not None else None
        )
        _e1_source = alert_log.unique_or_none(a.source for a, _loc_ids in tagged_alerts)
        # Issue #1459: die Gefahrenart steht in `hazards`, nicht in `metrics` (O1).
        alert_log.append_entry(
            self._user_id, entity_id=preset_id, entity_type="compare",
            changes_count=len(tagged_alerts) + len(allclears),
            severity=severity,
            hazards=alert_log.hazards_from_official_alerts(
                [a for a, _loc_ids in tagged_alerts] + [ac.alert for ac, _l in allclears]
            ),
            reason=alert_log.REASON_OFFICIAL_ALERT,
            effective_channels=effective_channels,
            sent_channels=result.delivered_channels,
            reachable_channels=result.attempted_channels,
            below_threshold_channels=suppressed,
            blocked_reason_codes=result.blocked_reason_codes,
            event_at=_e1_event_at, event_end_at=_e1_event_end_at,
            measurement_point=_e1_measurement_point, source=_e1_source,
            # Issue #1944: derselbe geteilte Baustein wie im Trip-Pfad.
            **alert_log.capture_kwargs_from_alerts(
                [a for a, _loc_ids in tagged_alerts]
            ),
        )
        if not alert_retry_backoff.settle(
            retry_store, _RETRY_SCOPE, retry_fp, result.delivery_outcome,
        ):
            return False

        self._record_state(preset_id, per_location_new)
        if allclear_settled(result):
            self._apply_allclears(preset_id, allclears)
        alert_daily_limit.increment(self._user_id, now, zone)
        # Issue #1917 S4b-2 (F001-Symmetrie): NUR nach erfolgreicher
        # Zustellung. Gefahrenarten ausserhalb des `wet`-Kanons
        # (hazard_class=None) werden bewusst NICHT registriert — ein Eintrag
        # ohne Klasse kaeme nie zum Zuge (kein Praefix-Match moeglich).
        for alert, loc_ids in tagged_alerts:
            hazard_class = resolve_hazard_class(hazard=alert.hazard)
            if hazard_class is None:
                continue
            for loc_id in loc_ids:
                record_event_identity(
                    user_id=self._user_id, entity_id=f"{preset_id}:{loc_id}",
                    hazard_class=hazard_class, segment_ids=[loc_id],
                    severity=alert_urgency.urgency_from_official_level(alert.level),
                    window_start=alert.valid_from, window_end=alert.valid_to,
                    now=datetime.now(timezone.utc),
                )
        return result.sent

    def _detect(
        self, preset_id: str, locs: list, sources: Optional[list[str]] = None
    ) -> tuple[list, dict]:
        """Fetch je Ort (getaggt mit `loc.id` -- niemals mit dem Ortsnamen,
        F005: gleichnamige Orte kollabieren sonst im Rueckweg ueber ein
        Namens-Dict und der State landet am falschen Ort), dedupliziert ueber
        alle Orte, filtert auf neue/eskalierte Warnungen (State-Vergleich je
        betroffener location_id). Liefert `(new_or_escalated_tagged,
        per_location_new_alerts)` — BEIDE bleiben durchgaengig id-basiert
        (F006: die Anzeige-/Scope-Schicht loest IDs erst ganz am Ende in
        Namen auf, s. `build_compare_official_alert_notices`).

        Issue #1258 (AC-7/AC-8): `sources` (aus `official_warnings.sources`)
        filtert NACH dem Fetch, VOR der Neu/Eskalations-Entscheidung — leer/
        None laesst alle Quellen unveraendert durch (Ist-Verhalten).

        Issue #1460 (P4): Jeder Ort wird mit dem Zeitfenster „jetzt bis Ende
        des heutigen Tagesfensters in seiner ORTSZEIT" abgefragt (ADR-0035-
        Default 4-19 Uhr, wenn das Preset nichts anderes sagt). Orte haben
        keine Etappen — die Menge der geprueften Orte bleibt deshalb
        unveraendert die des Presets (AC-33), nur die Zeit kommt hinzu."""
        now = datetime.now(timezone.utc)
        raw, queries_by_loc = self._fetch_locations(preset_id, locs, now)
        if sources:
            # Issue #1441: Quellenname = Teil vor dem ersten ':' (Lagebericht
            # `avalanche_report:AT-07` -> `avalanche_report`); Quellen ohne ':'
            # verhalten sich unveraendert.
            raw = [(alert, loc_ids) for alert, loc_ids in raw
                   if alert.source.split(":", 1)[0] in sources]
        deduped = dedupe_official_alerts(raw)

        state_svc_by_loc = {loc.id: AlertStateService(user_id=self._user_id) for loc in locs}
        state_by_loc = {
            loc_id: svc.load(f"{preset_id}:{loc_id}") for loc_id, svc in state_svc_by_loc.items()
        }

        new_or_escalated: list = []
        per_location_new: dict = {}
        changed_locs: set = set()
        for alert, loc_ids in deduped:
            is_new = False
            for loc_id in loc_ids:
                should_report, stale_key, merged_entry = official_alert_revision_verdict(
                    alert, state_by_loc[loc_id]
                )
                if should_report:
                    is_new = True
                    per_location_new.setdefault(loc_id, []).append(alert)
                elif merged_entry is not None:
                    # Issue #1685: stille Fenster-Revision -- Fortschreibung
                    # sofort, identisch zum Trip-Pfad (check_official_alert_triggers).
                    del state_by_loc[loc_id][stale_key]
                    state_by_loc[loc_id][official_alert_state_key(alert)] = merged_entry
                    changed_locs.add(loc_id)
            if is_new:
                new_or_escalated.append((alert, loc_ids))
        # Issue #1441 S2: GC + Entwarnungs-Erkennung je Ort (eigenes Gedaechtnis).
        self._pending_allclears = []
        self._pending_meta = {}
        for loc_id, state in state_by_loc.items():
            queries = queries_by_loc.get(loc_id, [])
            self._pending_meta[loc_id] = reported_meta(queries)
            pruned = prune_expired_official(state, now)
            allclears, absent_changed = detect_official_allclear(state, queries, now)
            self._pending_allclears.extend((ac, [loc_id]) for ac in allclears)
            if pruned or absent_changed:
                changed_locs.add(loc_id)
        for loc_id in changed_locs:
            state_svc_by_loc[loc_id].save(f"{preset_id}:{loc_id}", state_by_loc[loc_id])
        return new_or_escalated, per_location_new

    def _fetch_locations(self, preset_id: str, locs: list, now: datetime) -> tuple[list, dict]:
        """Abruf je Ort; Issue #1441 S2: Pro-Quelle-Ergebnis desselben Abrufs
        (``collect_source_queries``) als ``AllClearQuery`` je Ort.

        Issue #1539 S6 dreiphasig: Tagesfenster seriell, NUR der Warn-Abruf
        parallel (je Aufgabe eigene Senke), Zusammenfuehren seriell in
        Eingabereihenfolge. Scheitert ein Ort, scheitert das Preset (nie eine
        Teilmenge ohne Entwarnungs-Basis an `_detect`, ADR-0021)."""
        auftraege = [(loc, self._day_window_end(preset_id, loc, now)) for loc in locs]

        def abruf(auftrag):
            loc, window_end = auftrag
            sink: list = []
            with collect_source_queries(sink):
                alerts = list(get_official_alerts_for_location(
                    loc.lat, loc.lon, window_start=now, window_end=window_end, now=now,
                ))
            return alerts, sink

        outcomes = parallel_fetch.fetch_ordered(
            auftraege, abruf, provider="official_alerts",
            deadline_at=preset_deadline(self._run_deadline_at),
        )
        _raise_first_failure(preset_id, outcomes)
        raw: list = []
        queries_by_loc: dict = {}
        for out in outcomes:
            (loc, window_end), (alerts, sink) = out.item, out.value
            raw.extend((alert, [loc.id]) for alert in alerts)
            queries_by_loc[loc.id] = [AllClearQuery(
                scope=loc.id, scope_ids=(loc.id,), window_start=now, window_end=window_end,
                sources=sink[-1].sources if sink else None, shown=tuple(alerts),
            )]
        return raw, queries_by_loc

    def _day_window_end(self, preset_id: str, loc, now: datetime) -> datetime:
        """Issue #1460 (P4): Ende des HEUTIGEN Tagesfensters dieses Ortes, in
        dessen ORTSZEIT (ADR-0035-Default 4-19 Uhr, wenn das Preset nichts
        anderes gesetzt hat).

        Ein Fenster ueber Mitternacht (`start > end`, seit #1361/#1372 S1b
        gueltig) endet am FOLGETAG zur Endstunde. Liegt das Fensterende bereits
        hinter uns (Abruf nach Feierabend), wird auf `now` geklemmt statt ein
        rueckwaerts laufendes Fenster zu bilden -- dann bleiben genau die
        gerade gueltigen Warnungen sichtbar, statt dass der Ortsvergleich
        abends taub wird.

        Issue #1599: Die Endstunde ist INKLUSIV -- der Horizont reicht bis
        (end_hour+1):00 Ortszeit. Umgerechnet wird ueber denselben Helfer wie
        im Trip-Alarmpfad und im Ortsvergleich-Δ-Alarm, statt hier ein drittes
        Mal selbst zu rechnen."""
        from output.renderers.day_window import resolve_configured_window
        from utils.timezone import tz_for_coords

        preset = next(
            (p for p in self._load_presets() if p.get("id") == preset_id), {}
        )
        start_hour, end_hour = resolve_configured_window(
            preset.get("day_window_start_hour"), preset.get("day_window_end_hour")
        )
        tz = tz_for_coords(loc.lat, loc.lon)
        local_now = local_dt(now, tz)
        end_utc = day_window.window_end_utc_exclusive(local_now.date(), end_hour, tz)
        if start_hour > end_hour and end_utc <= now:
            end_utc = day_window.window_end_utc_exclusive(
                local_now.date() + timedelta(days=1), end_hour, tz
            )
        return max(end_utc, now)

    def _record_state(self, preset_id: str, per_location_new: dict) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_by_loc = getattr(self, "_pending_meta", {}) or {}
        for loc_id, alerts in per_location_new.items():
            entity_id = f"{preset_id}:{loc_id}"
            state_svc = AlertStateService(user_id=self._user_id)
            state = state_svc.load(entity_id)
            meta = meta_by_loc.get(loc_id, {})
            for alert in alerts:
                key = official_alert_state_key(alert)
                state[key] = official_alert_state_entry(
                    alert, now_iso, source=(meta.get(key) or {}).get("source"), scope=[loc_id],
                )
            state_svc.save(entity_id, state)

    def _apply_allclears(self, preset_id: str, allclears: list) -> None:
        """Issue #1441 S2: nach Zustellung senken bzw. Tombstone setzen (je Ort)."""
        now = datetime.now(timezone.utc)
        for ac, loc_ids in allclears:
            for loc_id in loc_ids:
                entity_id = f"{preset_id}:{loc_id}"
                state_svc = AlertStateService(user_id=self._user_id)
                state = state_svc.load(entity_id)
                if apply_official_allclears(state, [ac], now):
                    state_svc.save(entity_id, state)

    def _effective_channels(self, preset: dict) -> set[str]:
        """Duenner Wrapper (Issue #2279 S1) — delegiert an die geteilte
        Alarm-Auflösung `services.alert_channels.effective_alert_channels`
        (vormals eine gleichnamige, jetzt entfernte Funktion in
        `compare_alert_channels.py`). Aufruf ueber den Modul-Namensraum
        (`coa_module.effective_alert_channels` entspricht hier dem
        Modulattribut), damit Tests das Symbol im VERBRAUCHENDEN Modul
        patchen koennen (AC-6)."""
        return effective_alert_channels(preset, self._settings, self._user_id)

    def _notification_service_for(self, preset: dict) -> NotificationService:
        """Duenner Wrapper (Issue #1467 S4a) auf den geteilten Helfer
        `compare_preset_access.notification_service_for_preset`."""
        return notification_service_for_preset(
            self._settings, self._user_id, preset, log_label="Compare-Alert (amtlich):",
            lang=self._lang,
        )

    def _load_presets(self) -> list[dict]:
        """Duenner Wrapper (Issue #1467 S4a) auf den geteilten Helfer
        `compare_preset_access.load_compare_alert_presets`."""
        return load_compare_alert_presets(self._user_id)
