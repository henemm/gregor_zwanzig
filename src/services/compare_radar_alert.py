"""Compare-Radar-Alarm-Service — Issue #1041 Slice 1b, Epic #1095.

Verdrahtet den in Slice 1a (LIVE) gelieferten Bündel-Versand-Baustein
(`NotificationService.send_multi_location_radar_alert`) zu einem echten
Compare-Radar-Alarm-Pfad: pro Compare-Preset und pro Ort wird der aktuelle
Radar-Nowcast geprüft; bei Regen-Onset ≤ 20 Min (konvektive Gefahr steuert
nur das Label) wird EINE gebündelte E-Mail an die Preset-Empfänger
versendet. Eigener Parallelpfad neben `CompareAlertService` (Metrik-
Abweichungs-Alarme) — Struktur-Vorbild ist `CompareAlertService`
(`compare_alert.py`), Auslöse-/Fetch-Logik ist 1:1 vom Trip-Radar-Pfad
übernommen (`TripAlertService.check_radar_alerts()`, `trip_alert.py:628`).

SPEC: docs/specs/modules/issue_1041b_compare_radar_alert_service.md
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import Settings
from app.loader import load_all_locations
from services.alert_state import AlertStateService
from services.deviation_alert_engine import DeviationAlertEngine
from services.notification_service import NotificationService
from services.trip_alert import radar_alert_due

logger = logging.getLogger("compare_radar_alert")

_RADAR_ONSET_THRESHOLD_MIN = 20
_DEFAULT_COOLDOWN_MINUTES = 120


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
        self._throttle_file = Path(f"data/users/{user_id}/compare_radar_alert_throttle.json")
        self._last_alert_times: dict[str, datetime] = self._load_throttle_times()

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
        # AC-6: Default AUS — kein get_nowcast-Aufruf bei fehlendem/false Feld.
        if not preset.get("radar_alert_enabled", False):
            return False

        cooldown_minutes = preset.get("alert_cooldown_minutes", _DEFAULT_COOLDOWN_MINUTES)
        last_alert = self._last_alert_times.get(preset_id)
        if DeviationAlertEngine.is_cooldown_active(
            datetime.now(timezone.utc), last_alert, cooldown_minutes
        ):
            logger.debug(f"Compare-Radar-Alert cooldown active for preset {preset_id}")
            return False

        triggered = self._detect_triggered_locations(preset_id, location_ids, all_locations)
        if not triggered:
            return False

        # AC-5: Onset ist bereits erkannt — Ruhezeit unterdrückt erst hier den Versand.
        if DeviationAlertEngine.is_quiet_hours(
            datetime.now(timezone.utc),
            preset.get("alert_quiet_from"),
            preset.get("alert_quiet_to"),
        ):
            logger.debug(f"Compare-Radar-Alert quiet hours active for preset {preset_id}")
            return False

        notification_service = self._notification_service_for(preset)
        entities = [(name, result) for name, _loc, result in triggered]
        notif_result = notification_service.send_multi_location_radar_alert(
            entities=entities, effective_channels={"email"}, mail_sink=self._mail_sink,
            cooldown_display=_format_cooldown_display(cooldown_minutes),
        )
        if not notif_result.sent:
            return False

        self._finalize_triggered_state(preset_id, triggered)
        self._last_alert_times[preset_id] = datetime.now(timezone.utc)
        self._save_throttle_times()
        return True

    def _detect_triggered_locations(
        self, preset_id: str, location_ids: list[str], all_locations: dict
    ) -> list[tuple]:
        """Je Ort im Preset: Nowcast holen, Auslöse-Schwelle prüfen (`radar_alert_due`,
        `trip_alert.py:33`) — reine Detect-Phase, kein Versand."""
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
                result = radar_service.get_nowcast(loc.lat, loc.lon)
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
        """Preset-Empfänger (`preset.empfaenger`, Fallback `settings.mail_to`) —
        Muster `compare_alert.py::_notification_service_for`."""
        empfaenger = preset.get("empfaenger") or (
            [self._settings.mail_to] if self._settings.mail_to else []
        )
        preset_settings = (
            self._settings.model_copy(update={"mail_to": ", ".join(empfaenger)})
            if empfaenger else self._settings
        )
        return NotificationService(preset_settings, self._user_id)

    def _get_radar_service(self):
        if self._radar_service is None:
            from services.radar_service import RadarNowcastService
            self._radar_service = RadarNowcastService()
        return self._radar_service

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
            logger.warning(f"Failed to load compare radar alert throttle file: {e}")
            return {}

    def _save_throttle_times(self) -> None:
        try:
            self._throttle_file.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.isoformat() for k, v in self._last_alert_times.items()}
            self._throttle_file.write_text(json.dumps(data, indent=2))
        except OSError as e:
            logger.error(f"Failed to save compare radar alert throttle file: {e}")
