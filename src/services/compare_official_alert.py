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
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import Settings
import app.day_window as day_window
from app.loader import load_all_locations
from output.renderers.alert.official_alerts import (
    dedupe_official_alerts,
    official_alert_revision_verdict,
    official_alert_state_entry,
    official_alert_state_key,
)
from services import alert_channel_threshold, alert_daily_limit, alert_log
import services.alert_urgency as alert_urgency
from services.alert_gate import check_briefing_imminent, check_official_alert_gate
from services.alert_state import AlertStateService
from services.compare_alert_channels import (
    effective_compare_channels,
    effective_compare_telegram_style,
)
from services.compare_alert_guard import is_silenced
from services.compare_preset_access import (
    load_compare_alert_presets,
    notification_service_for_preset,
)
from services.compare_slot_scheduler import presets_due_for_hour
from services.notification_service import NotificationService
from services.official_alerts import get_official_alerts_for_location
from utils.timezone import first_resolvable_tz

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


class CompareOfficialAlertService:
    """Wertet amtliche Warnungen je Compare-Preset/Ort aus und versendet EINEN
    gebuendelten Standalone-Alarm (Orts-Scope) bei neuen/eskalierten Treffern."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        user_id: str = "default",
        mail_sink: Optional[object] = None,
        sms_sink: Optional[object] = None,
        telegram_sink: Optional[object] = None,
    ) -> None:
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._user_id = user_id
        self._mail_sink = mail_sink
        self._sms_sink = sms_sink
        self._telegram_sink = telegram_sink

    def check_all_compare_presets(self) -> int:
        presets = self._load_presets()
        if not presets:
            return 0
        all_locations = {loc.id: loc for loc in load_all_locations(user_id=self._user_id)}
        return sum(1 for preset in presets if self._check_one_preset(preset, all_locations))

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
        if not check_official_alert_gate(
            user_id=self._user_id,
            quiet_from=preset.get("alert_quiet_from"),
            quiet_to=preset.get("alert_quiet_to"),
            context_label=preset_id,
            now=datetime.now(timezone.utc),
            zone=zone,
        ).allowed:
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
            briefing_due_at=lambda moment: bool(
                presets_due_for_hour([preset], all_locations, moment)
            ),
        ):
            logger.debug(f"Compare official alert briefing imminent for {preset_id}")
            return False

        locs = [all_locations[lid] for lid in location_ids if lid in all_locations]
        if not locs:
            return False

        sources = (official_warnings or {}).get("sources") or None
        tagged_alerts, per_location_new = self._detect(preset_id, locs, sources)
        if not tagged_alerts:
            return False

        now = datetime.now(timezone.utc)
        notification_service = self._notification_service_for(preset)
        effective_channels = self._effective_channels(preset)
        # Issue #1461 S3b-2b: die Dringlichkeit wird VOR dem Versand
        # hochgezogen (bisher entstand sie erst inline im `append_entry`-
        # Argument, also NACH dem Versand) -- `split_by_threshold()` braucht
        # sie davor. `effective_channels` bleibt fuers Protokoll ROH (rote
        # Linie #638), nur der tatsaechliche Versand (`allowed`) wird gefiltert.
        severity = alert_urgency.highest_urgency(*[
            alert_urgency.urgency_from_official_level(a.level)
            for a, _loc_ids in tagged_alerts
        ])
        allowed, suppressed = alert_channel_threshold.split_by_threshold(
            effective_channels, severity, preset.get("alert_channel_thresholds"),
        )
        result = notification_service.send_multi_location_official_alert(
            preset.get("name", preset_id), locs, tagged_alerts,
            allowed,
            _effective_telegram_style(preset),
            mail_sink=self._mail_sink, sms_sink=self._sms_sink,
            telegram_sink=self._telegram_sink,
        )
        # Issue #1459: die Gefahrenart steht in `hazards`, nicht in `metrics` (O1).
        alert_log.append_entry(
            self._user_id, entity_id=preset_id, entity_type="compare",
            changes_count=len(tagged_alerts),
            severity=severity,
            hazards=alert_log.hazards_from_official_alerts(
                [a for a, _loc_ids in tagged_alerts]
            ),
            reason=alert_log.REASON_OFFICIAL_ALERT,
            effective_channels=effective_channels,
            sent_channels=result.delivered_channels,
            reachable_channels=result.sent_channels,
            below_threshold_channels=suppressed,
            blocked_reason_codes=result.blocked_reason_codes,
        )
        if not result.sent:
            return False

        self._record_state(preset_id, per_location_new)
        alert_daily_limit.increment(self._user_id, now, zone)
        return True

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
        raw = [
            (alert, [loc.id])
            for loc in locs
            for alert in get_official_alerts_for_location(
                loc.lat, loc.lon,
                window_start=now,
                window_end=self._day_window_end(preset_id, loc, now),
                now=now,
            )
        ]
        if sources:
            raw = [(alert, loc_ids) for alert, loc_ids in raw if alert.source in sources]
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
        for loc_id in changed_locs:
            state_svc_by_loc[loc_id].save(f"{preset_id}:{loc_id}", state_by_loc[loc_id])
        return new_or_escalated, per_location_new

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
        tz = tz_for_coords(loc.lat, loc.lon) or timezone.utc
        local_now = now.astimezone(tz)
        end_utc = day_window.window_end_utc_exclusive(local_now.date(), end_hour, tz)
        if start_hour > end_hour and end_utc <= now:
            end_utc = day_window.window_end_utc_exclusive(
                local_now.date() + timedelta(days=1), end_hour, tz
            )
        return max(end_utc, now)

    def _record_state(self, preset_id: str, per_location_new: dict) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        for loc_id, alerts in per_location_new.items():
            entity_id = f"{preset_id}:{loc_id}"
            state_svc = AlertStateService(user_id=self._user_id)
            state = state_svc.load(entity_id)
            for alert in alerts:
                key = official_alert_state_key(alert)
                state[key] = official_alert_state_entry(alert, now_iso)
            state_svc.save(entity_id, state)

    def _effective_channels(self, preset: dict) -> set[str]:
        """Duenner Wrapper (Issue #1467 S2 AG1) — delegiert an den geteilten
        Resolver `services.compare_alert_channels.effective_compare_channels`.
        Aufruf ueber den Modul-Namensraum (`coa_module.effective_compare_channels`
        entspricht hier dem Modulattribut), damit Tests das Symbol im
        VERBRAUCHENDEN Modul patchen koennen (AC-3a)."""
        return effective_compare_channels(preset, self._settings, self._user_id)

    def _notification_service_for(self, preset: dict) -> NotificationService:
        """Duenner Wrapper (Issue #1467 S4a) auf den geteilten Helfer
        `compare_preset_access.notification_service_for_preset`."""
        return notification_service_for_preset(
            self._settings, self._user_id, preset, log_label="Compare-Alert (amtlich):",
        )

    def _load_presets(self) -> list[dict]:
        """Duenner Wrapper (Issue #1467 S4a) auf den geteilten Helfer
        `compare_preset_access.load_compare_alert_presets`."""
        return load_compare_alert_presets(self._user_id)
