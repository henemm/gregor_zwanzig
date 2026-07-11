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

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.loader import load_all_locations
from output.renderers.alert.official_alerts import dedupe_official_alerts
from services import alert_daily_limit
from services.alert_state import AlertStateService
from services.notification_service import NotificationService
from services.official_alerts import get_official_alerts_for_location
from services.user_tier import sms_allowed

logger = logging.getLogger("compare_official_alert")


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
        if not preset.get("official_alert_triggers_enabled", True):
            return False

        locs = [all_locations[lid] for lid in location_ids if lid in all_locations]
        if not locs:
            return False

        tagged_alerts, per_location_new = self._detect(preset_id, locs)
        if not tagged_alerts:
            return False

        now = datetime.now(timezone.utc)
        if not alert_daily_limit.is_allowed(self._user_id, now):
            logger.debug(f"Compare official alert suppressed: daily limit for preset {preset_id}")
            return False

        notification_service = self._notification_service_for(preset)
        result = notification_service.send_multi_location_official_alert(
            preset.get("name", preset_id), locs, tagged_alerts,
            self._effective_channels(preset),
            mail_sink=self._mail_sink, sms_sink=self._sms_sink,
            telegram_sink=self._telegram_sink,
        )
        if not result.sent:
            return False

        self._record_state(preset_id, per_location_new)
        alert_daily_limit.increment(self._user_id, now)
        return True

    def _detect(self, preset_id: str, locs: list) -> tuple[list, dict]:
        """Fetch je Ort (getaggt mit `loc.id` -- niemals mit dem Ortsnamen,
        F005: gleichnamige Orte kollabieren sonst im Rueckweg ueber ein
        Namens-Dict und der State landet am falschen Ort), dedupliziert ueber
        alle Orte, filtert auf neue/eskalierte Warnungen (State-Vergleich je
        betroffener location_id). Liefert `(new_or_escalated_tagged,
        per_location_new_alerts)` — BEIDE bleiben durchgaengig id-basiert
        (F006: die Anzeige-/Scope-Schicht loest IDs erst ganz am Ende in
        Namen auf, s. `build_compare_official_alert_notices`)."""
        raw = [
            (alert, [loc.id])
            for loc in locs
            for alert in get_official_alerts_for_location(loc.lat, loc.lon)
        ]
        deduped = dedupe_official_alerts(raw)

        state_by_loc = {
            loc.id: AlertStateService(user_id=self._user_id).load(f"{preset_id}:{loc.id}")
            for loc in locs
        }

        new_or_escalated: list = []
        per_location_new: dict = {}
        for alert, loc_ids in deduped:
            key = f"official_alert:{alert.region_label}:{alert.hazard}"
            is_new = False
            for loc_id in loc_ids:
                prev = state_by_loc[loc_id].get(key)
                if prev is None or alert.level > prev.get("last_reported_value", 0):
                    is_new = True
                    per_location_new.setdefault(loc_id, []).append(alert)
            if is_new:
                new_or_escalated.append((alert, loc_ids))
        return new_or_escalated, per_location_new

    def _record_state(self, preset_id: str, per_location_new: dict) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        for loc_id, alerts in per_location_new.items():
            entity_id = f"{preset_id}:{loc_id}"
            state_svc = AlertStateService(user_id=self._user_id)
            state = state_svc.load(entity_id)
            for alert in alerts:
                key = f"official_alert:{alert.region_label}:{alert.hazard}"
                state[key] = {"last_reported_value": float(alert.level), "reported_at": now_iso}
            state_svc.save(entity_id, state)

    def _effective_channels(self, preset: dict) -> set[str]:
        """E-Mail immer; Telegram/SMS nur bei Preset-Opt-in UND globaler
        User-Faehigkeit (wie Trip). Ohne Opt-in bleibt es E-Mail-only."""
        channels = {"email"}
        if preset.get("send_telegram") and self._settings.can_send_telegram():
            channels.add("telegram")
        if preset.get("send_sms") and self._settings.can_send_sms() and sms_allowed(self._user_id):
            channels.add("sms")
        return channels

    def _notification_service_for(self, preset: dict) -> NotificationService:
        """Preset-Empfaenger (`preset.empfaenger`, Fallback `settings.mail_to`)."""
        empfaenger = preset.get("empfaenger") or (
            [self._settings.mail_to] if self._settings.mail_to else []
        )
        preset_settings = (
            self._settings.model_copy(update={"mail_to": ", ".join(empfaenger)})
            if empfaenger else self._settings
        )
        return NotificationService(preset_settings, self._user_id)

    def _load_presets(self) -> list[dict]:
        path = Path(f"data/users/{self._user_id}/compare_presets.json")
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Corrupt compare_presets.json for {self._user_id}: {e}")
            return []
