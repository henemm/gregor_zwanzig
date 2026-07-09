"""Ortsvergleich als zweiter Consumer der Deviation-Alert-Engine.

Issue #1169 — Scheibe 2/3, Epic #1095.

`CompareAlertService` ist analog `TripAlertService` aufgebaut: pro Nutzer
instanziiert (`user_id`-Parameter, NIE ein `"default"`-Fallback), lädt
`compare_presets.json`, baut je Preset/Ort eine hartkodierte
`AlertEvaluationConfig` (B2 — editierbare UI folgt in Scheibe 3, #1170), ruft
`DeviationAlertEngine.evaluate()`, prüft Cooldown (neuer Store, keyed
`preset_id`) und Alert-State-Dedup (`entity_id = f"{preset_id}:{location_id}"`)
und versendet über `NotificationService.send_location_deviation_alert()`.

SPEC: docs/specs/modules/issue_1169_compare_alert_consumer.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.loader import load_all_locations
from services.alert_preset import _PRESET_TABLE
from services.alert_state import AlertStateService
from services.compare_location_weather_source import CompareLocationWeatherSource
from services.compare_weather_snapshot import CompareWeatherSnapshotService
from services.deviation_alert_engine import DeviationAlertEngine
from services.notification_service import NotificationService
from services.point_weather import AlertEvaluationConfig

logger = logging.getLogger("compare_alert")

# B2 (Spec): alle 12 Tabellenmetriken auf "standard" — äquivalent zu
# expand_preset("standard") / expand_per_metric_levels(..., display_config=None).
_STANDARD_METRIC_LEVELS: dict[str, str] = {row[0].value: "standard" for row in _PRESET_TABLE}
_DEFAULT_COOLDOWN_MINUTES = 120


class CompareAlertService:
    """Wertet frisches Wetter je Compare-Preset/Ort gegen den Δ-Anker aus und
    versendet Deviation-Alert-Mails an die Preset-Empfänger."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        user_id: str = "default",
        weather_source: Optional[object] = None,
        mail_sink: Optional[object] = None,
    ) -> None:
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._user_id = user_id
        self._weather_source = weather_source or CompareLocationWeatherSource()
        self._mail_sink = mail_sink
        self._snapshot_service = CompareWeatherSnapshotService(user_id=user_id)
        self._throttle_file = Path(f"data/users/{user_id}/compare_alert_throttle.json")
        self._last_alert_times: dict[str, datetime] = self._load_throttle_times()

    def check_all_compare_presets(self) -> int:
        """Prüft alle Compare-Presets dieses Nutzers und versendet Alarme.

        Returns:
            Anzahl der tatsächlich versendeten Deviation-Alert-Mails.
        """
        presets = self._load_presets()
        if not presets:
            return 0

        all_locations = {loc.id: loc for loc in load_all_locations(user_id=self._user_id)}
        sent = 0

        for preset in presets:
            preset_id = preset.get("id", "")
            location_ids = preset.get("location_ids") or []
            if not preset_id or not location_ids:
                continue

            cooldown_minutes = preset.get("cooldown_minutes", _DEFAULT_COOLDOWN_MINUTES)
            last_alert = self._last_alert_times.get(preset_id)
            if DeviationAlertEngine.is_cooldown_active(
                datetime.now(timezone.utc), last_alert, cooldown_minutes
            ):
                logger.debug(f"Compare-Alert cooldown active for preset {preset_id}")
                continue

            config = self._build_eval_config(preset, cooldown_minutes)
            notification_service = self._notification_service_for(preset)

            preset_sent = 0
            for location_id in location_ids:
                loc = all_locations.get(location_id)
                if loc is None:
                    logger.warning(
                        f"Compare-Alert: Ort {location_id} nicht aufloesbar fuer Preset {preset_id}"
                    )
                    continue
                try:
                    if self._check_one_location(
                        preset, location_id, loc, notification_service, config
                    ):
                        preset_sent += 1
                except Exception as e:
                    logger.error(
                        f"Compare-Alert check failed for {preset_id}/{location_id}: {e}"
                    )

            if preset_sent:
                self._last_alert_times[preset_id] = datetime.now(timezone.utc)
                self._save_throttle_times()
                sent += preset_sent

        return sent

    def _check_one_location(
        self, preset: dict, location_id: str, loc, notification_service, config
    ) -> bool:
        preset_id = preset.get("id", "")
        cached = self._snapshot_service.load(preset_id, location_id)
        fresh_point = self._weather_source.fetch(location_id, loc.lat, loc.lon)
        fresh = [fresh_point]

        entity_id = f"{preset_id}:{location_id}"
        state_svc = AlertStateService(user_id=self._user_id)
        alert_state = state_svc.load(entity_id)

        engine = DeviationAlertEngine()
        result = engine.evaluate(cached=cached, fresh=fresh, config=config, alert_state=alert_state)
        if not result.triggered:
            return False

        notif_result = notification_service.send_location_deviation_alert(
            entity_name=loc.name,
            points=fresh,
            changes=result.changes,
            effective_channels=result.channels,
            mail_sink=self._mail_sink,
        )
        if not notif_result.sent:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        for change in result.changes:
            key = f"{change.metric}:{change.segment_id}"
            alert_state[key] = {"last_reported_value": float(change.new_value), "reported_at": now_iso}
        state_svc.save(entity_id, alert_state)
        return True

    def _build_eval_config(self, preset: dict, cooldown_minutes) -> AlertEvaluationConfig:
        """B2-Defaults, vorwärtskompatible Overrides via `preset.get(feld, DEFAULT)`.
        Kanal ist IMMER `{"email"}` — Compare-Versand ist heute E-Mail-only."""
        return AlertEvaluationConfig(
            cooldown_minutes=cooldown_minutes,
            quiet_from=preset.get("quiet_from"),
            quiet_to=preset.get("quiet_to"),
            metric_alert_levels=preset.get("metric_alert_levels") or _STANDARD_METRIC_LEVELS,
            channels={"email"},
            display_config=None,
        )

    def _notification_service_for(self, preset: dict) -> NotificationService:
        """Preset-Empfänger (`preset.empfaenger`, Fallback `settings.mail_to`)."""
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

    def _load_throttle_times(self) -> dict[str, datetime]:
        if not self._throttle_file.exists():
            return {}
        try:
            data = json.loads(self._throttle_file.read_text())
            return {k: datetime.fromisoformat(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.warning(f"Failed to load compare alert throttle file: {e}")
            return {}

    def _save_throttle_times(self) -> None:
        try:
            self._throttle_file.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.isoformat() for k, v in self._last_alert_times.items()}
            self._throttle_file.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.error(f"Failed to save compare alert throttle file: {e}")
