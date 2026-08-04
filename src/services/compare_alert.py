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

import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import Settings
from app.loader import compare_preset_to_dict, load_all_locations, load_compare_presets
from services import alert_daily_limit, alert_log
import services.alert_urgency as alert_urgency
from services.alert_preset import _PRESET_TABLE
from services.alert_state import AlertStateService
from services.compare_alert_channels import (
    effective_compare_channels,
    effective_compare_telegram_style,
)
from services.compare_alert_guard import is_silenced
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

            # Issue #1467 S2 AG6: pausierte/archivierte Ortsvergleiche
            # verhalten sich, als gaebe es sie nicht (PO-Vorgabe). Der Riegel
            # sitzt bewusst GANZ vorne — vor Sperrzeit, Tageslimit, Ruhezeit
            # und vor jedem Wetterabruf (AC-20b): ein stillgelegter Vergleich
            # darf weder Abruf-Kontingent noch Laufzeit kosten. Die Regel
            # steht nur im geteilten Baustein (AC-28), nie hier inline.
            if is_silenced(preset):
                logger.debug(f"Compare-Alert skipped: preset {preset_id} is paused/archived")
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

            # Issue #1467 S2 AG2: Ruhezeit VOR den Wetterabruf ziehen — bisher
            # prüfte nur die Engine (`DeviationAlertEngine.evaluate()`), NACH
            # dem Fetch in `_evaluate_one_location()`. Muster übernommen aus
            # `compare_official_alert.py:105-113`. Dieselbe geteilte Funktion
            # wie dort (`DeviationAlertEngine.is_quiet_hours`) — keine zweite
            # Fassung. Sperrzeit/Tageslimit oben wurden nur GELESEN, hier wird
            # ebenfalls nur gelesen: kein Zähler wird durch den Riegel veraendert.
            #
            # Issue #1479 (Wurzel-Härtung): der Behelfs-Schutz aus AG2
            # (`try/except` + Protokollzeile + Neutralisieren von
            # `config.quiet_from`/`config.quiet_to` vor der Weitergabe an
            # `DeviationAlertEngine.evaluate()`) ist hier entfallen. Ein
            # unbrauchbarer Ruhezeit-Wert wird jetzt in der geteilten Funktion
            # selbst abgefangen und protokolliert — auch beim zweiten,
            # Preset-internen Aufruf in `evaluate()`
            # (`deviation_alert_engine.py:243`), weshalb das Neutralisieren
            # überflüssig wurde. Kein eigener `try/except` an dieser
            # Aufrufstelle: der Schutz gehört in den geteilten Baustein
            # (ADR-0021), nicht in eine vierte Kopie.
            quiet_hours_active = DeviationAlertEngine.is_quiet_hours(
                now, config.quiet_from, config.quiet_to, context_label=preset_id
            )
            if quiet_hours_active:
                logger.debug(f"Compare-Alert quiet hours active for preset {preset_id}")
                continue

            triggered = self._detect_triggered_locations(
                preset_id, location_ids, all_locations, config
            )
            if not triggered:
                continue

            # Issue #1452: Versandobjekt erst NACH der Detect-Phase bauen — die
            # Warnung bei fehlendem `mail_to` gehört an die Stelle, an der ein
            # Versand tatsächlich anstünde (sonst Log-Rauschen je Leerlauf).
            notification_service = self._notification_service_for(preset)
            entities = [(t["loc"].name, [t["fresh_point"]], t["changes"]) for t in triggered]
            notif_result = notification_service.send_multi_location_deviation_alert(
                entities=entities,
                effective_channels=config.channels,
                mail_sink=self._mail_sink,
                location_positions=self._location_positions(location_ids, all_locations),
                # Issue #1467 S2, Korrektur K-5: der Kurzstil-Schalter (#1260)
                # wirkte auf genau diesem Versandweg bisher gar nicht. Gelesen
                # wird er ueber DENSELBEN Aufloeser wie beim amtlichen
                # Ortsvergleich-Alarm (ADR-0021, keine zweite Fassung).
                telegram_style=effective_compare_telegram_style(preset),
            )
            # Issue #1459: der Ortsvergleich protokollierte bisher gar nicht
            # (B1). Seit #1467 S1 traegt der Eintrag die Preset-Kennung im
            # gemeinsamen Feld `entity_id`, unterschieden durch `entity_type`.
            alle_changes = [c for t in triggered for c in t["changes"]]
            alert_log.append_entry(
                self._user_id, entity_id=preset_id, entity_type="compare",
                changes_count=len(alle_changes),
                severity=alert_urgency.urgency_from_changes(alle_changes),
                metrics=alert_log.register_pairs_from_changes(alle_changes),
                reason=alert_log.REASON_FORECAST_CHANGE,
                effective_channels=config.channels,
                sent_channels=notif_result.delivered_channels,
                reachable_channels=notif_result.sent_channels,
            )
            if not notif_result.sent:
                continue

            self._finalize_triggered_state(triggered)
            self._throttle_store.record("compare_preset", preset_id, now)
            alert_daily_limit.increment(self._user_id, now)
            sent += 1

        return sent

    @staticmethod
    def _location_positions(location_ids: list[str], all_locations: dict) -> dict[str, int]:
        """Ortsname → 1-basierte Position in der KONFIGURIERTEN Ortsliste des
        Presets (Issue #1467 S2 AG3b, PO E2).

        Quelle der Reihenfolge ist ausdruecklich `preset["location_ids"]` und
        NICHT die Trefferreihenfolge — dieselbe Reihenfolge, in der die
        Vergleichs-E-Mail ihre Ortsspalten fuehrt. Die Zuordnung deckt ALLE
        Orte des Presets ab, auch die, die diesmal nicht ausgeloest haben:
        sonst verschoeben sich die Zahlen von Lauf zu Lauf.

        Korrektur-Runde 2026-08-04 (K-4, PO woertlich): "die nummer soll
        immer die Reihenfolge darstellen. Wenn ein Ort geloescht wird, ruecken
        die anderen nach." Gezaehlt wird deshalb nur ueber die AUFLOESBAREN
        Orte — eine Kennung ohne gespeicherten Ort (Nutzer hat ihn geloescht)
        zaehlt NICHT mehr mit, die folgenden ruecken auf. Die fruehere
        Zusicherung "nicht aufloesbare Kennungen behalten ihre Position" ist
        damit hinfaellig: sie hinterliess eine Luecke, die auf einen Ort
        zeigte, den der Empfaenger in seiner Liste gar nicht mehr findet.

        Unveraendert bleibt die andere Art von Luecke: ein Ort, der NOCH in
        der Liste steht und diesmal nur nicht ausgeloest hat, zaehlt mit —
        seine Zahl bleibt vergeben, die folgenden ruecken NICHT auf."""
        positions: dict[str, int] = {}
        index = 0
        for location_id in location_ids:
            loc = all_locations.get(location_id)
            if loc is None:
                continue
            index += 1
            positions[loc.name] = index
        return positions

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

        Issue #1467 S2 AG4: die Kanalliste war hier fest `{"email"}` verdrahtet —
        der Telegram-/SMS-Schalter im Alarme-Tab (`AlertChannelPicker`,
        `AlarmeTab.svelte:295`) war dadurch wirkungslos. Jetzt entscheidet der
        EINE Compare-Kanal-Resolver aus AG1 (`compare_alert_channels.py`,
        ADR-0021) — dieselbe Fassung, die `compare_official_alert.py` und
        `scheduler_dispatch_service.py` schon nutzen; dies ist ihr dritter
        Aufrufer, keine vierte Kopie.

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
            channels=effective_compare_channels(preset, self._settings, self._user_id),
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
        # Issue #1373 Scheibe B: BEWUSST dieselbe Normalisierungsfunktion wie der
        # Render-Pfad (`resolve_enabled_metrics`) — eine zweite Kopie der
        # Format-Verzweigung waere genau die Duplikat-Falle, durch die dieser
        # Leser bei #1191 schon einmal auseinandergelaufen ist.
        from output.renderers.compare_metric_ids import _to_key
        from services.weather_change_detection import _ALERT_METRIC_TO_CATALOG_ID

        active = (preset.get("display_config") or {}).get("active_metrics")
        if active is None:
            return None  # Legacy: nie migriert → konservativer None-Fallback

        active_catalog_ids: set[str] = set()
        for item in active:
            # Issue #1373 Scheibe B (AC-11): die Auswahl kann als Zeichenkette
            # (Altformat) ODER als {"metric_id", "aggregation"} (Neuformat)
            # gespeichert sein — hier wird jedes Element zuerst auf den
            # Auswahl-Schluessel zurueckgenommen, damit derselbe Vergleich vor
            # und nach der Umstellung EXAKT dieselben Groessen ueberwacht.
            # _SUMMARY_KEY_TO_CATALOG_ID bleibt unveraendert: sie fuehrt in
            # einen anderen Namensraum (Alarm-Engine-IDs wie
            # "temperature_cold"), den der Katalog-Index nicht ersetzt.
            key = _to_key(item)
            if key is None:
                continue
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
        """Empfänger kommen AUSSCHLIESSLICH aus den Konto-Settings des Nutzers
        (Muster `trip_alert.py:125`). Issue #1452: `preset.empfaenger` ist inert —
        ein preset-eigenes Override stellte an eine Adresse zu, die der Nutzer
        in seinem Konto nie hinterlegt hat.

        Fehlt `mail_to`, wird das laut gemeldet (statt stillem Skip); der Lauf
        läuft für die übrigen Presets weiter (Spec AC-4)."""
        if not self._settings.mail_to:
            logger.warning(
                "Compare-Alert: Nutzer %s hat keine Empfaenger-Adresse (mail_to) "
                "in den Konto-Settings — Preset %s kann keine E-Mail zustellen.",
                self._user_id, preset.get("id", ""),
            )
        return NotificationService(self._settings, self._user_id)

    def _load_presets(self) -> list[dict]:
        # Issue #1250 Scheibe 1: zentraler Loader statt rohem json.loads.
        return [compare_preset_to_dict(p) for p in load_compare_presets(user_id=self._user_id)]

