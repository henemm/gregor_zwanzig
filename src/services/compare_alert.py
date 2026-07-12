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
from services import alert_daily_limit
from services.alert_preset import _PRESET_TABLE
from services.alert_state import AlertStateService
from services.compare_location_weather_source import CompareLocationWeatherSource
from services.compare_weather_snapshot import CompareWeatherSnapshotService
from services.deviation_alert_engine import DeviationAlertEngine
from services.notification_service import NotificationService
from services.point_weather import AlertEvaluationConfig
from services.throttle_store import ThrottleStore

logger = logging.getLogger("compare_alert")

# B2 (Spec): alle 12 Tabellenmetriken auf "standard" — äquivalent zu
# expand_preset("standard") / expand_per_metric_levels(..., display_config=None).
_STANDARD_METRIC_LEVELS: dict[str, str] = {row[0].value: "standard" for row in _PRESET_TABLE}
_DEFAULT_COOLDOWN_MINUTES = 120

# Bug #1191: Summary-Key (Compare-Editor `display_config.active_metrics`) →
# Alarm-Katalog-ID (`display_config.metrics[].metric_id`, wie #961-Filter sie prüft).
# Nur alarmfähige Metriken sind gelistet; reine Vergleichs-Keys (cloud_avg_pct,
# sunny_hours_h, uv_index_max, snow_depth_cm) haben bewusst KEIN Mapping und
# beeinflussen den Deaktivieren-Filter nicht. IDs korrespondieren zu
# `weather_change_detection._ALERT_METRIC_TO_CATALOG_ID`.
_SUMMARY_KEY_TO_CATALOG_ID: dict[str, str] = {
    "temp_max_c": "temperature",
    "temp_min_c": "temperature_cold",
    "wind_max_kmh": "wind",
    "gust_max_kmh": "gust",
    "precip_sum_mm": "precipitation",
    "thunder_level_max": "thunder",
    "visibility_min_m": "visibility",
    "snow_new_sum_cm": "fresh_snow",
    "cape_max_jkg": "cape",
    "freezing_level_m": "freezing_level",
}


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
        # Issue #1213: gemeinsamer ThrottleStore ersetzt das In-Memory-Dict
        # + die dateibasierte `compare_alert_throttle.json`-Persistenz.
        self._throttle_store = ThrottleStore(user_id)

    def check_all_compare_presets(self) -> int:
        """Prüft alle Compare-Presets dieses Nutzers und versendet Alarme.

        Issue #1170 (Adversary F001): ALLE gleichzeitig betroffenen Orte
        EINES Presets werden in EINER gebündelten Mail zusammengefasst statt
        je Ort einzeln versendet.

        Returns:
            Anzahl der tatsächlich versendeten (gebündelten) Deviation-
            Alert-Mails — EINE je Preset-Lauf mit ≥1 Treffer, nicht eine je Ort.
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

            # Issue #1213 (AC-4): `None`/fehlend muss VOR dem Store-Aufruf auf
            # denselben Default wie der Trip-Pfad aufgelöst werden — `.get(key,
            # default)` griff nur, wenn der Key ganz fehlte, nicht bei explizitem
            # `None` (heutiger Bug: Compare lief dadurch ungedrosselt).
            cooldown_minutes = preset.get("alert_cooldown_minutes")
            if cooldown_minutes is None:
                cooldown_minutes = _DEFAULT_COOLDOWN_MINUTES
            now = datetime.now(timezone.utc)
            if self._throttle_store.is_throttled("compare_preset", preset_id, cooldown_minutes, now):
                logger.debug(f"Compare-Alert cooldown active for preset {preset_id}")
                continue

            # Issue #1213 (AC-6): Compare an dieselbe Tageslimit-Prüfung
            # anbinden wie der Trip-Pfad (Epic #1067 Slice 3, #1070).
            if not alert_daily_limit.is_allowed(self._user_id, now):
                logger.debug(f"Compare-Alert suppressed: daily limit reached for preset {preset_id}")
                continue

            config = self._build_eval_config(preset, cooldown_minutes)
            notification_service = self._notification_service_for(preset)

            triggered = self._detect_triggered_locations(
                preset_id, location_ids, all_locations, config
            )
            if not triggered:
                continue

            entities = [(t["loc"].name, [t["fresh_point"]], t["changes"]) for t in triggered]
            notif_result = notification_service.send_multi_location_deviation_alert(
                entities=entities,
                effective_channels=config.channels,
                mail_sink=self._mail_sink,
            )
            if not notif_result.sent:
                continue

            self._finalize_triggered_state(triggered)
            self._throttle_store.record("compare_preset", preset_id, now)
            alert_daily_limit.increment(self._user_id, now)
            sent += 1

        return sent

    def _detect_triggered_locations(
        self, preset_id: str, location_ids: list[str], all_locations: dict, config
    ) -> list[dict]:
        """Wertet jeden Ort des Presets gegen den Δ-Anker aus (Detect-Phase,
        kein Versand). Sammelt alle Treffer für den nachfolgenden gebündelten
        Versand (Issue #1170)."""
        triggered: list[dict] = []
        for location_id in location_ids:
            loc = all_locations.get(location_id)
            if loc is None:
                logger.warning(
                    f"Compare-Alert: Ort {location_id} nicht aufloesbar fuer Preset {preset_id}"
                )
                continue
            try:
                entry = self._evaluate_one_location(preset_id, location_id, loc, config)
            except Exception as e:
                logger.error(f"Compare-Alert check failed for {preset_id}/{location_id}: {e}")
                continue
            if entry is not None:
                triggered.append(entry)
        return triggered

    def _evaluate_one_location(
        self, preset_id: str, location_id: str, loc, config
    ) -> Optional[dict]:
        """Δ-Auswertung für EINEN Ort — reine Detect-Logik ohne Versand/
        State-Update (das übernimmt `_finalize_triggered_state()` NUR für
        tatsächlich versendete Treffer, Issue #1170)."""
        cached = self._snapshot_service.load(preset_id, location_id)
        fresh_point = self._weather_source.fetch(location_id, loc.lat, loc.lon)

        entity_id = f"{preset_id}:{location_id}"
        state_svc = AlertStateService(user_id=self._user_id)
        alert_state = state_svc.load(entity_id)

        engine = DeviationAlertEngine()
        result = engine.evaluate(
            cached=cached, fresh=[fresh_point], config=config, alert_state=alert_state
        )
        if not result.triggered:
            return None

        return {
            "loc": loc,
            "fresh_point": fresh_point,
            "changes": result.changes,
            "entity_id": entity_id,
            "state_svc": state_svc,
            "alert_state": alert_state,
        }

    def _finalize_triggered_state(self, triggered: list[dict]) -> None:
        """Alert-State-Update nach ERFOLGREICHEM gebündeltem Versand — pro
        Ort (Cooldown bleibt preset-weit, s. Aufrufer)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        for entry in triggered:
            alert_state = entry["alert_state"]
            for change in entry["changes"]:
                key = f"{change.metric}:{change.segment_id}"
                alert_state[key] = {
                    "last_reported_value": float(change.new_value), "reported_at": now_iso,
                }
            entry["state_svc"].save(entry["entity_id"], alert_state)

    def _build_eval_config(self, preset: dict, cooldown_minutes) -> AlertEvaluationConfig:
        """B2-Defaults, vorwärtskompatible Overrides via `preset.get(feld, DEFAULT)`.
        Kanal ist IMMER `{"email"}` — Compare-Versand ist heute E-Mail-only.

        Bug #1191: `display_config` wird jetzt IMMER durchgereicht (analog
        Trip-Pfad `trip_alert.py:191`) — aus `active_metrics` (Summary-Keys)
        via Mapper in ein `UnifiedWeatherDisplayConfig` mit Katalog-IDs
        übersetzt. Der #961-Filter (`expand_per_metric_levels`) unterdrückt so
        im Compare-Editor DEAKTIVIERTE Metriken."""
        return AlertEvaluationConfig(
            cooldown_minutes=cooldown_minutes,
            quiet_from=preset.get("alert_quiet_from"),
            quiet_to=preset.get("alert_quiet_to"),
            metric_alert_levels=(
                (preset.get("display_config") or {}).get("metric_alert_levels")
                or _STANDARD_METRIC_LEVELS
            ),
            channels={"email"},
            display_config=self._display_config_from_active_metrics(preset),
        )

    def _display_config_from_active_metrics(self, preset: dict):
        """Baut ein `UnifiedWeatherDisplayConfig`, das den im Compare-Editor
        gesetzten Aktivierungsstatus je alarmfähiger Metrik EXPLIZIT abbildet.

        Bug #1191 (Adversary F001) — kritische Unterscheidung:
          - `active_metrics` FEHLT ganz (Key absent / `None`) = Legacy-Preset vor
            der Migration → `display_config=None` → der #961-Filter greift NICHT →
            konservatives Alt-Verhalten (alle Metriken feuern). Die Migration setzt
            `active_metrics` ohnehin, sodass dieser Pfad nur echte Alt-Presets trifft.
          - `active_metrics` VORHANDEN (eine Liste, auch leer `[]`) = der Nutzer hat
            im Editor bewusst (evtl. alles) ab-/ausgewählt → JEDE alarmfähige
            Katalog-ID wird EXPLIZIT gelistet mit `enabled=(id in aktive_ids)`.
            Deaktivierte Metriken stehen als `enabled=False` drin → die `metrics`-
            Liste ist NIE leer → `is_alert_metric_active` triggert die „nie
            konfiguriert = alles aktiv"-Heuristik (leeres `metrics[]`) NICHT mehr →
            „deaktiviert = stumm" statt „alles feuert" (Adversary F001)."""
        from app.models import MetricConfig, UnifiedWeatherDisplayConfig
        from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID

        active = (preset.get("display_config") or {}).get("active_metrics")
        if active is None:
            return None  # Legacy: nie migriert → konservativer None-Fallback

        active_catalog_ids: set[str] = set()
        for key in active:
            cid = _SUMMARY_KEY_TO_CATALOG_ID.get(key)
            if cid:
                active_catalog_ids.add(cid)

        # Union aller alarmrelevanten Katalog-IDs — jede EXPLIZIT mit ihrem
        # Aktivierungsstatus, damit der OR-Check je AlertMetric deterministisch
        # gegen echte Einträge läuft (fehlende ID ⇒ False; hier gibt es keine
        # fehlenden mehr).
        all_catalog_ids: list[str] = []
        for catalog_ids in _ALERT_METRIC_TO_CATALOG_ID.values():
            for cid in catalog_ids:
                if cid not in all_catalog_ids:
                    all_catalog_ids.append(cid)
        return UnifiedWeatherDisplayConfig(
            metrics=[
                MetricConfig(metric_id=cid, enabled=(cid in active_catalog_ids))
                for cid in all_catalog_ids
            ]
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

