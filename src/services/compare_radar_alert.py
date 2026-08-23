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
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import Settings
from app.loader import load_all_locations
from services import alert_channel_threshold, alert_daily_limit, alert_log
import services.alert_urgency as alert_urgency
from services.alert_gate import (
    check_event_identity_gate,
    check_nowcast_gate,
    record_event_identity,
    record_nowcast_sent,
    resolve_hazard_class,
)
from utils.timezone import first_resolvable_tz
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
from services.notification_service import NotificationService
from services import radar_service as radar_service_mod
from services.trip_alert import radar_alert_due

logger = logging.getLogger("compare_radar_alert")

_DEFAULT_COOLDOWN_MINUTES = 120
# Issue #1467 S3: eigener Sperrzeit-Scope im geteilten `ThrottleStore`.
# NICHT `radar` (dort liegen Trip-Kennungen; seit dem #1250-Cutover sind Trip-
# und Vergleichs-Kennungen frei gewaehlte Slugs im selben Verzeichnis, eine
# Kollision ist real moeglich) und NICHT `compare_preset` (den belegt der
# Aenderungsalarm auf demselben Preset-Schluessel — ein gemeinsamer Scope
# liesse die beiden Alarmarten einander gegenseitig unterdruecken).
_THROTTLE_SCOPE = "compare_radar"


def _identity_inputs(nowcast, now_utc: datetime) -> tuple:
    """Issue #1917 S4b-2: `(Gefahrenklasse, Dringlichkeit, Onset-Zeitpunkt)`
    einer Nowcast-Meldung — EINE Ableitung fuer Pruefung UND Registrierung,
    damit beide Seiten nie auseinanderlaufen koennen."""
    # Issue #2050 S2b: ohne kuenftigen Beginn, aber mit laufendem Ereignis ist
    # JETZT der Bezugszeitpunkt. Bliebe `onset_at` hier `None`, faende
    # `_times_overlap` (`alert_gate.py`) nie einen Kandidaten und die
    # Entdopplung waere ein stiller No-Op -- funktionsfaehig aussehend, aber
    # ohne Wirkung (Bruchstelle 2).
    onset_at = (
        now_utc + timedelta(minutes=nowcast.onset_minutes)
        if nowcast.onset_minutes is not None
        else (now_utc if getattr(nowcast, "already_running", False) else None)
    )
    return (
        resolve_hazard_class(is_convective=nowcast.is_convective),
        alert_urgency.urgency_from_radar(
            is_convective=nowcast.is_convective,
            intensity_label=nowcast.intensity_label,
        ),
        onset_at,
    )


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


# Issue #2050 S6 (E-1): Ereigniszeit-Ableitung aus dem GETEILTEN Baustein --
# dieselbe Fassung benutzt der Trip-Radar-Zweig (`trip_alert.py`), damit
# Protokoll-Beginn und -Ende auf beiden Flaechen nicht auseinanderlaufen.
_onset_at = alert_log.nowcast_onset_at
_event_end_at = alert_log.nowcast_event_end_at


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
        # Issue #1726: Ortszeit des ERSTEN aufloesbaren Orts (#1378 AC-4,
        # AC-15). Dieselbe Zone geht in die Buchung — sonst pruefte die
        # Schranke einen anderen Zaehler als sie fuellt.
        zone = first_resolvable_tz(
            (all_locations.get(lid) for lid in location_ids), context_label=preset_id,
        )
        gate = check_nowcast_gate(
            user_id=self._user_id,
            throttle_scope=_THROTTLE_SCOPE,
            throttle_key=preset_id,
            cooldown_minutes=cooldown_minutes,
            quiet_from=preset.get("alert_quiet_from"),
            quiet_to=preset.get("alert_quiet_to"),
            context_label=preset_id,
            now=datetime.now(timezone.utc),
            zone=zone,
        )
        # Issue #2050 S3b (Szenario 7, AC-20): dieselbe Ausnahme wie im
        # Trip-Radarpfad — bei erschoepfter Tages-Obergrenze haelt der Lauf
        # hier nicht mehr an, sondern holt die Daten und entscheidet unten
        # gegen die dort abgeleitete Dringlichkeit. Ruhezeit und Sperrzeit
        # bleiben an dieser Stelle unveraendert harte Stops.
        _budget_erschoepft = (
            not gate.allowed and gate.reason == alert_log.REASON_DAILY_LIMIT
        )
        if not gate.allowed and not _budget_erschoepft:
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

        # Issue #1917 S4b-2: quellenuebergreifende Ereignis-Identitaet, PRO
        # getriggertem Ort (Batch-Teilfilterung) — derselbe geteilte Baustein
        # wie im Trip-Nowcast-Pfad (`trip_alert.py`, #1467 S4b-1). Die
        # Registertrennung laeuft bei Compare ueber die Ort-Datei
        # `f"{preset_id}:{loc.id}"`, `segment_ids` traegt trotzdem die
        # Ortskennung: eine LEERE Segment-Menge erzeugt strukturell nie ein
        # Match (`alert_gate.py::_find_matching_entry`) und waere ein stiller
        # No-Op. Gefiltert wird VOR der Dringlichkeits-Berechnung, sonst
        # bestimmte ein unterdrueckter Ort noch die Kanal-Schwelle mit.
        now_utc = datetime.now(timezone.utc)
        allowed_triggered: list[tuple] = []
        for name, loc, nowcast in triggered:
            hazard_class, urgency, onset_at = _identity_inputs(nowcast, now_utc)
            identity_gate = check_event_identity_gate(
                user_id=self._user_id, entity_id=f"{preset_id}:{loc.id}",
                hazard_class=hazard_class, segment_ids=[loc.id],
                severity=urgency, now=now_utc, point_at=onset_at,
            )
            if identity_gate.allowed:
                allowed_triggered.append((name, loc, nowcast))
                continue
            logger.debug(
                f"Compare-Radar-Alert unterdrueckt ({identity_gate.reason}) "
                f"fuer {preset_id}:{loc.id}"
            )
            try:
                # Issue #2050 S6 (E-1): `nowcast`/`loc` liegen hier EINZELN vor
                # (innere Schleife) -- alles bekannt bis auf `reference_at`
                # (strukturell `None`, wie beim Radar-Compare-Zweig generell --
                # es gibt hier keine "bereits im Briefing angekuendigt"-Pruefung).
                _event_end_dt = _event_end_at(nowcast, now_utc)
                alert_log.append_suppressed_entry(
                    self._user_id, entity_id=preset_id, entity_type="compare",
                    reason=alert_log.REASON_NOWCAST,
                    gate_reason=identity_gate.reason,
                    effective_channels=effective_channels,
                    lead_time_minutes=nowcast.onset_minutes,
                    event_at=_onset_at(nowcast, now_utc).isoformat(),
                    event_end_at=_event_end_dt.isoformat() if _event_end_dt else None,
                    measurement_point={"location_id": loc.id},
                    source=nowcast.source,
                )
            except Exception as e:
                logger.error(
                    "Compare-Radar-Alert: Unterdrueckungs-Protokoll (Ereignis-"
                    "Identitaet) fuer %s:%s fehlgeschlagen (%s) — der Alarm "
                    "blieb aus, nur der Protokoll-Eintrag fehlt.",
                    preset_id, loc.id, e,
                )
        if not allowed_triggered:
            return False
        triggered = allowed_triggered

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
        # Issue #2050 S3b (Szenario 7, AC-20): jetzt — mit der Dringlichkeit
        # dieses Abrufs in der Hand — entscheidet der Aufrufer, ob die Lage
        # das erschoepfte Tagesbudget durchbricht. Geteilter Baustein, dieselbe
        # Zone wie Gate und Buchung (#1726).
        _budget_durchbruch = False
        if _budget_erschoepft:
            _budget_durchbruch = alert_daily_limit.escalation_breaks_through(
                self._user_id, now_utc, zone, severity,
            )
            logger.info(
                "Compare-Radar-Alert: Budget-Durchbruch fuer Preset %s geprueft "
                "— Dringlichkeit %s: %s",
                preset_id, severity,
                "Durchbruch" if _budget_durchbruch else "Tages-Obergrenze bleibt",
            )
            if not _budget_durchbruch:
                try:
                    alert_log.append_suppressed_entry(
                        self._user_id, entity_id=preset_id, entity_type="compare",
                        reason=alert_log.REASON_NOWCAST,
                        gate_reason=alert_log.REASON_DAILY_LIMIT,
                        effective_channels=effective_channels,
                    )
                except Exception as e:
                    logger.error(
                        "Compare-Radar-Alert: Unterdrueckungs-Protokoll "
                        "(Tages-Obergrenze) fuer Preset %s fehlgeschlagen (%s) "
                        "— der Alarm blieb aus, nur der Eintrag fehlt.",
                        preset_id, e,
                    )
                return False

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
            telegram_style=effective_compare_telegram_style(preset),
        )
        # Issue #2050 S6 (E-1): nur, wenn ALLE getriggerten Orte uebereinstimmen
        # (`unique_or_none`) -- `reference_at` bleibt strukturell `None`
        # (dieser Zweig kennt keine "bereits im Briefing angekuendigt"-Pruefung,
        # anders als der Trip-Pfad).
        _e1_lead_time = alert_log.unique_or_none(
            nowcast.onset_minutes for _name, _loc, nowcast in triggered
        )
        _e1_event_at_dt = alert_log.unique_or_none(
            _onset_at(nowcast, now_utc) for _name, _loc, nowcast in triggered
        )
        _e1_event_at = _e1_event_at_dt.isoformat() if _e1_event_at_dt is not None else None
        _e1_event_end_dt = alert_log.unique_or_none(
            _event_end_at(nowcast, now_utc) for _name, _loc, nowcast in triggered
        )
        _e1_event_end_at = (
            _e1_event_end_dt.isoformat() if _e1_event_end_dt is not None else None
        )
        _e1_loc_id = alert_log.unique_or_none(loc.id for _name, loc, _nowcast in triggered)
        _e1_measurement_point = (
            {"location_id": _e1_loc_id} if _e1_loc_id is not None else None
        )
        _e1_source = alert_log.unique_or_none(
            nowcast.source for _name, _loc, nowcast in triggered
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
            lead_time_minutes=_e1_lead_time,
            event_at=_e1_event_at, event_end_at=_e1_event_end_at,
            measurement_point=_e1_measurement_point, source=_e1_source,
        )
        if not notif_result.sent:
            return False

        self._finalize_triggered_state(preset_id, triggered)
        # Issue #1917 S4b-2 (F001-Symmetrie): NUR nach erfolgreicher
        # Zustellung — eine spaetere amtliche Warnung fuer dasselbe Ereignis
        # findet diesen Eintrag ueber `check_event_identity_gate()`.
        for _name, loc, nowcast in triggered:
            hazard_class, urgency, onset_at = _identity_inputs(nowcast, now_utc)
            if hazard_class is None:
                continue
            record_event_identity(
                user_id=self._user_id, entity_id=f"{preset_id}:{loc.id}",
                hazard_class=hazard_class, segment_ids=[loc.id],
                severity=urgency, point_at=onset_at,
                now=datetime.now(timezone.utc),
            )
        # Issue #1467 S3: Tageszaehler + Sperrzeit im geteilten Speicher, erst
        # NACH erfolgreicher Zustellung (F001-Semantik, unveraendert).
        record_nowcast_sent(
            user_id=self._user_id, throttle_scope=_THROTTLE_SCOPE,
            throttle_key=preset_id, now=datetime.now(timezone.utc),
            zone=zone,
            # Issue #2050 S3b: hoechste heute in dieser Zone zugestellte Stufe
            # bei JEDEM Versand fortschreiben; der verbrauchte Durchbruch nur,
            # wenn er diesen Lauf getragen hat (F001-Symmetrie).
            urgency=severity,
            is_escalation_breakthrough=_budget_durchbruch,
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
                result = radar_service.get_nowcast(
                    loc.lat, loc.lon, elevation_m=loc.elevation_m, priority="polling"
                )
            except Exception as e:
                logger.error(f"Compare-Radar-Alert nowcast failed for {preset_id}/{location_id}: {e}")
                continue
            # Issue #2009: geteilte Schwelle aus `services.radar_service`,
            # ueber die Modul-Referenz gelesen (kein `from ... import` — eine
            # gebundene Kopie waere eine stille Kopie). Alias, weil der lokale
            # Name `radar_service` hier bereits die Dienst-Instanz traegt.
            if not radar_alert_due(result, radar_service_mod.RADAR_ONSET_THRESHOLD_MIN):
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
        """Dünner Wrapper (Issue #1467 S4a) auf den geteilten Helfer
        `compare_preset_access.notification_service_for_preset`."""
        return notification_service_for_preset(
            self._settings, self._user_id, preset, log_label="Compare-Alert (Radar):",
        )

    def _get_radar_service(self):
        if self._radar_service is None:
            from services.radar_service import RadarNowcastService
            self._radar_service = RadarNowcastService()
        return self._radar_service

    def _load_presets(self) -> list[dict]:
        """Dünner Wrapper (Issue #1467 S4a) auf den geteilten Helfer
        `compare_preset_access.load_compare_alert_presets`."""
        return load_compare_alert_presets(self._user_id)
