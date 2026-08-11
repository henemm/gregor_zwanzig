"""Compare-Radar-Alarm-Service — Issue #1041 Slice 1b, Epic #1095.

Verdrahtet den in Slice 1a (LIVE) gelieferten Bündel-Versand-Baustein
(`NotificationService.send_multi_location_radar_alert`) zu einem echten
Compare-Radar-Alarm-Pfad: pro Compare-Preset und pro Ort wird der aktuelle
Radar-Nowcast geprüft; bei Regen-Onset ≤ 20 Min (konvektive Gefahr steuert
nur das Label) wird EINE gebündelte E-Mail an die Preset-Empfänger
versendet. Eigener Parallelpfad neben `CompareAlertService` (Metrik-
Abweichungs-Alarme) — Struktur-Vorbild ist `CompareAlertService`
(`compare_alert.py`), Auslöse-/Fetch-Logik (Nowcast-Abruf +
`radar_alert_due()`-Schwelle) ist vom Trip-Radar-Pfad übernommen
(`TripAlertService.check_radar_alerts()`, `trip_alert.py:887`). Diese
Übernahme betrifft NICHT die tagesübergreifende Segment-Auswahl seit
Issue #1667 S3 (`resolve_current_segment`, `trip_segments.py`) — Compare-
Presets arbeiten direkt auf `location_ids`, es gibt hier keine Etappen/
Segmente und damit auch keinen Vortags-Rückgriff.

SPEC: docs/specs/modules/issue_1041b_compare_radar_alert_service.md
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import Settings
from app.loader import compare_preset_to_dict, load_all_locations, load_compare_presets
from services import alert_channel_threshold, alert_log
import services.alert_urgency as alert_urgency
from services.alert_gate import check_nowcast_gate, record_nowcast_sent
from services.alert_state import AlertStateService
from services.compare_alert_channels import effective_compare_channels
from services.compare_alert_guard import is_silenced
from services.notification_service import NotificationService
from services.trip_alert import radar_alert_due

logger = logging.getLogger("compare_radar_alert")

_RADAR_ONSET_THRESHOLD_MIN = 20
_DEFAULT_COOLDOWN_MINUTES = 120
# Issue #1467 S3: eigener Sperrzeit-Scope im geteilten `ThrottleStore`.
# NICHT `radar` (dort liegen Trip-Kennungen; seit dem #1250-Cutover sind Trip-
# und Vergleichs-Kennungen frei gewaehlte Slugs im selben Verzeichnis, eine
# Kollision ist real moeglich) und NICHT `compare_preset` (den belegt der
# Aenderungsalarm auf demselben Preset-Schluessel — ein gemeinsamer Scope
# liesse die beiden Alarmarten einander gegenseitig unterdruecken).
_THROTTLE_SCOPE = "compare_radar"


def _format_cooldown_display(cooldown_minutes: int) -> str:
    """Menschenlesbarer Cooldown-Hinweis-Text — Muster
    `radar_alert_service.py::_cooldown_display` (Trip-Radar-Pfad), hier auf
    dem bereits aufgelösten `cooldown_minutes`-Wert des Presets statt eines
    Trip-Objekts (Pflicht-Fix, Staging-Befund: fehlender Cooldown-Hinweis in
    Compare-Radar-Alarm-Mails)."""
    if cooldown_minutes % 60 == 0:
        n = cooldown_minutes // 60
        return f"{n} Stunde" if n == 1 else f"{n} Stunden"
    return f"{cooldown_minutes} Minuten"


class CompareRadarAlertService:
    """Prüft je Compare-Preset/Ort den Radar-Nowcast und versendet gebündelte
    Onset-Alarm-Mails an die Preset-Empfänger (Parallelpfad zu
    `CompareAlertService`, siehe Modul-Docstring)."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        user_id: str = "default",
        radar_service: Optional[object] = None,
        mail_sink: Optional[object] = None,
    ) -> None:
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._user_id = user_id
        self._radar_service = radar_service
        self._mail_sink = mail_sink

    def check_all_compare_presets(self) -> int:
        """Prüft alle Compare-Presets dieses Nutzers und versendet gebündelte
        Radar-Onset-Alarme. Returns die Anzahl tatsächlich versendeter
        (gebündelter) Mails — eine je auslösendem Preset-Lauf."""
        presets = self._load_presets()
        if not presets:
            return 0

        all_locations = {loc.id: loc for loc in load_all_locations(user_id=self._user_id)}
        sent = 0
        for preset in presets:
            if self._check_one_preset(preset, all_locations):
                sent += 1
        return sent

    def _check_one_preset(self, preset: dict, all_locations: dict) -> bool:
        preset_id = preset.get("id", "")
        location_ids = preset.get("location_ids") or []
        if not preset_id or not location_ids:
            return False
        # Issue #1467 S2 AG6: pausierte/archivierte Ortsvergleiche schweigen
        # in ALLEN Alarm-Pfaden (PO-Vorgabe). Der Riegel sitzt vor der
        # `radar_alert_enabled`-Pruefung und vor jedem Nowcast-Abruf
        # (AC-20b-Wirkung im zweiten Pfad). Regel nur im geteilten Baustein
        # (AC-28), nie hier inline.
        if is_silenced(preset):
            logger.debug(
                f"Compare-Radar-Alert skipped: preset {preset_id} is paused/archived"
            )
            return False
        # AC-6: Default AUS — kein get_nowcast-Aufruf bei fehlendem/false Feld.
        if not preset.get("radar_alert_enabled", False):
            return False

        cooldown_minutes = preset.get("alert_cooldown_minutes", _DEFAULT_COOLDOWN_MINUTES)
        # Issue #1461 S3b-2b (AC-5): die Kanalliste war hier hart auf
        # `{"email"}` verdrahtet — unabhaengig vom Telegram-/SMS-Opt-in des
        # Nutzers (verfallene Begruendung aus #1041 Slice 1b, s. Spec
        # "Implementation Details" Punkt 3). Jetzt derselbe EINE Resolver wie
        # bei den beiden anderen Compare-Alarmwegen (ADR-0021, kein
        # Compare-eigener Filter).
        # Issue #1467 S3: die Aufloesung steht VOR der Freigabe-Pruefung — der
        # Protokoll-Eintrag einer Abweisung braucht die Kanaele des Nutzers.
        # Die Funktion ist rein (liest nur Preset/Settings/Tier), das Vorziehen
        # aendert am Versandverhalten nichts.
        effective_channels = effective_compare_channels(preset, self._settings, self._user_id)

        # Issue #1467 S3: Ruhezeit -> Sperrzeit -> Tages-Obergrenze aus dem
        # geteilten Baustein, VOR jedem Nowcast-Abruf. Ersetzt den frueheren
        # eigenen Cooldown (presetseigene Datei `compare_radar_alert_throttle.json`)
        # und die Ruhezeit-Pruefung NACH der Erkennung; die Tages-Obergrenze
        # fehlte hier bisher vollstaendig.
        gate = check_nowcast_gate(
            user_id=self._user_id,
            throttle_scope=_THROTTLE_SCOPE,
            throttle_key=preset_id,
            cooldown_minutes=cooldown_minutes,
            quiet_from=preset.get("alert_quiet_from"),
            quiet_to=preset.get("alert_quiet_to"),
            context_label=preset_id,
            now=datetime.now(timezone.utc),
        )
        if not gate.allowed:
            # Die Protokollierung darf den Stapellauf NIE mitreissen: ein
            # Ortsvergleich, dessen Eintrag scheitert, kostet sonst ALLE
            # uebrigen Ortsvergleiche dieses Nutzers ihren Alarm — genau das
            # Muster aus `fix_1479` (dort riss ein kaputter Ruhezeit-Wert den
            # ganzen Lauf mit), und es widerspricht dem Leitsatz „der
            # gefaehrlichste Fehler ist der ausbleibende Alarm".
            # Bewusst breit auf `Exception` (Muster des Nowcast-Abrufs in
            # `_detect_triggered_locations`): der Schaden einer zu engen
            # Klausel ist der Totalausfall, der einer zu breiten eine
            # Protokollzeile. Still verschluckt wird nichts — die Kennung
            # steht namentlich in der Meldung.
            try:
                alert_log.append_suppressed_entry(
                    self._user_id, entity_id=preset_id, entity_type="compare",
                    reason=alert_log.REASON_NOWCAST, gate_reason=gate.reason,
                    effective_channels=effective_channels,
                )
            except Exception as e:
                logger.error(
                    "Compare-Radar-Alert: Unterdrueckungs-Protokoll fuer Preset "
                    "%s fehlgeschlagen (%s) — der Alarm blieb aus (Grund: %s), "
                    "nur der Protokoll-Eintrag fehlt.",
                    preset_id, e, gate.reason,
                )
            return False

        triggered = self._detect_triggered_locations(preset_id, location_ids, all_locations)
        if not triggered:
            return False

        notification_service = self._notification_service_for(preset)
        # Die Dringlichkeit wird VOR dem Versand hochgezogen (bisher entstand
        # sie erst inline im `append_entry`-Argument, also NACH dem Versand) --
        # `split_by_threshold()` braucht sie davor. `effective_channels`
        # bleibt fuers Protokoll ROH (rote Linie #638), nur der tatsaechliche
        # Versand (`allowed`) wird gefiltert.
        severity = alert_urgency.highest_urgency(*[
            alert_urgency.urgency_from_radar(
                is_convective=nowcast.is_convective,
                intensity_label=nowcast.intensity_label,
            )
            for _name, _loc, nowcast in triggered
        ])
        allowed, suppressed = alert_channel_threshold.split_by_threshold(
            effective_channels, severity, preset.get("alert_channel_thresholds"),
        )
        # Issue #1383: Das Orts-Objekt MUSS mitgereicht werden — der Versand
        # leitet daraus die Ortszeit ab (vorher wurde `_loc` verworfen und die
        # Mail rendete alle Uhrzeiten in UTC).
        entities = list(triggered)
        notif_result = notification_service.send_multi_location_radar_alert(
            entities=entities, effective_channels=allowed, mail_sink=self._mail_sink,
            cooldown_display=_format_cooldown_display(cooldown_minutes),
        )
        # Issue #1459: gemischt konvektive/nicht-konvektive Orte ergeben BEIDE
        # Register-Paare in EINEM Eintrag.
        alert_log.append_entry(
            self._user_id, entity_id=preset_id, entity_type="compare",
            changes_count=len(triggered),
            severity=severity,
            metrics=alert_log.register_pairs_for_nowcast(
                [nowcast.is_convective for _name, _loc, nowcast in triggered]
            ),
            reason=alert_log.REASON_NOWCAST,
            effective_channels=effective_channels,
            sent_channels=notif_result.delivered_channels,
            reachable_channels=notif_result.sent_channels,
            below_threshold_channels=suppressed,
            blocked_reason_codes=notif_result.blocked_reason_codes,
        )
        if not notif_result.sent:
            return False

        self._finalize_triggered_state(preset_id, triggered)
        # Issue #1467 S3: Tageszaehler + Sperrzeit im geteilten Speicher, erst
        # NACH erfolgreicher Zustellung (F001-Semantik, unveraendert).
        record_nowcast_sent(
            user_id=self._user_id, throttle_scope=_THROTTLE_SCOPE,
            throttle_key=preset_id, now=datetime.now(timezone.utc),
        )
        return True

    def _detect_triggered_locations(
        self, preset_id: str, location_ids: list[str], all_locations: dict
    ) -> list[tuple]:
        """Je Ort im Preset: Nowcast holen, Auslöse-Schwelle prüfen (`radar_alert_due`,
        `trip_alert.py:33`) — reine Detect-Phase, kein Versand.

        Liefert `(loc.name, loc, NowcastResult)`-Tripel; das Orts-Objekt wird
        vom Versand für die Ortszeit-Ableitung gebraucht (Issue #1383) und vom
        Dedup-Gedächtnis für `loc.id`."""
        radar_service = self._get_radar_service()
        triggered: list[tuple] = []
        for location_id in location_ids:
            loc = all_locations.get(location_id)
            if loc is None:
                logger.warning(
                    f"Compare-Radar-Alert: Ort {location_id} nicht aufloesbar fuer Preset {preset_id}"
                )
                continue
            try:
                # Issue #1329 C2: Scheduler-Radar ist ein polling-Check
                # (drosselbar bei Budget-Druck) -- kein Nutzer-Briefing.
                result = radar_service.get_nowcast(loc.lat, loc.lon, priority="polling")
            except Exception as e:
                logger.error(f"Compare-Radar-Alert nowcast failed for {preset_id}/{location_id}: {e}")
                continue
            if not radar_alert_due(result, _RADAR_ONSET_THRESHOLD_MIN):
                continue
            triggered.append((loc.name, loc, result))
        return triggered

    def _finalize_triggered_state(self, preset_id: str, triggered: list[tuple]) -> None:
        """Dedup-Melde-Gedächtnis je getriggertem Ort (RMW), `entity_id =
        f"{preset_id}:{location_id}"` (Muster `compare_alert.py:149`)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        state_svc = AlertStateService(user_id=self._user_id)
        for _name, loc, _result in triggered:
            entity_id = f"{preset_id}:{loc.id}"
            state = state_svc.load(entity_id)
            state["radar_onset"] = {"reported_at": now_iso}
            state_svc.save(entity_id, state)

    def _notification_service_for(self, preset: dict) -> NotificationService:
        """Empfänger ausschliesslich aus den Konto-Settings — Muster
        `compare_alert.py::_notification_service_for`. Issue #1452:
        `preset.empfaenger` ist inert; fehlt `mail_to`, wird laut gemeldet, der
        Lauf bricht aber nicht ab (Spec AC-4)."""
        if not self._settings.mail_to:
            logger.warning(
                "Compare-Alert (Radar): Nutzer %s hat keine Empfaenger-Adresse "
                "(mail_to) in den Konto-Settings — Preset %s kann keine E-Mail "
                "zustellen.",
                self._user_id, preset.get("id", ""),
            )
        return NotificationService(self._settings, self._user_id)

    def _get_radar_service(self):
        if self._radar_service is None:
            from services.radar_service import RadarNowcastService
            self._radar_service = RadarNowcastService()
        return self._radar_service

    def _load_presets(self) -> list[dict]:
        # Issue #1250 Scheibe 1: zentraler Loader statt rohem json.loads.
        return [compare_preset_to_dict(p) for p in load_compare_presets(user_id=self._user_id)]
