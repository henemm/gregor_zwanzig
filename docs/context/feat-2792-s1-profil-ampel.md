# Context: S1 #2792 — Beidseitige Profil-Ampel im Datenmodell, alle Renderer, Migration

- **Workflow:** `feat_2792_s1_profil_ampel` (OpenSpec-Phasen von Hand, Plugin in der Cloud-Sitzung nicht installiert)
- **Epic:** #2791 · **ADR:** ADR-0106 *Akzeptiert* 2026-11-04 (P1 CAPE wie heute, P2 Gewitter „leicht“ gelb, P3 Altstufen relativ zur Vorlage)
- **Gemessen gegen:** `origin/main` @ `73f22f23e` (2026-11-04)
- **Fachliche Quelle:** `docs/context/einstellungen_neu.md` §4 (Grenzen aller 7 Vorlagen), Issue #2792

## 1. Datenmodell und Persistenz heute

### Python
- `Trip` (`src/app/trip.py:176`): `display_config: Optional[UnifiedWeatherDisplayConfig]` (:197), `alert_rules` (:199), `corridors: List[Corridor]` (:200), `activity: str` (:205), `extra: Dict` als Auffangnetz unbekannter Top-Level-Keys (:232).
- `UnifiedWeatherDisplayConfig` (`src/app/models.py:816`): `metrics: list[MetricConfig]`, `preset_name` (Vorlagen-Schlüssel, :827), `alert_preset` (:847), `metric_alert_levels` (:848), `per_channel_layouts`, `per_report_layouts`, `outlook_metrics`.
- `MetricConfig` (`models.py:663`): `metric_id`, `enabled`, `alert_enabled`, `alert_threshold`, `horizons` (:683), `bucket`, `order`, `sms_threshold` (:689), `derived`.
- `Corridor` (`models.py:1282`): `metric`, `range: [min,max]`, `notify`, `mark`, `prio`.
- `ComparePreset` (`models.py:1299`): `profil` (:1320), `display_config: dict` roh (:1334), `corridors` (:1361), `raw` (:1382).
- **Geteilt ist der JSON-Schlüsselraum `display_config`, nicht der Typ:** Trip parst zu `UnifiedWeatherDisplayConfig`, Compare bleibt Dict.
- `ideal_ranges` nur im Compare (`display_config.ideal_ranges`, geschrieben vom Frontend `compareEditorSave.ts:143`, `:500`), Python liest es nicht.

### Loader (`src/app/loader.py`)
- Trip lesen `_parse_trip` (:488), `_parse_display_config` (:951), Fallback `build_default_display_config_for_profile` (:589ff).
- Trip schreiben `save_trip` (:1986) → `_write_trip_locked` (:2048) mit `_deep_merge_preserve_unknown` (:137): Dicts rekursiv gemergt, Listen ersetzt.
- Compare: `compare_preset_from_dict` (:249) nur lesend, Python schreibt Compare nicht (macht Go).
- Bestehende Migrationen: `_migrate_legacy_alert_rules` (:383), `_migrate_metric_alert_levels` (:792), `_migrate_preset_display_config` (:811), `_migrate_rule_channels_to_metric_channels` (:852), `_migrate_weather_config` (:1128).

### Go
- `model.Trip` (`internal/model/trip.go:114`) und `model.ComparePreset` (`internal/model/compare_preset.go:14`) typisiert, `DisplayConfig map[string]interface{}` als Pass-through (:121 bzw. :48).
- **Go hat kein Auffangnetz für unbekannte Top-Level-Felder:** ein neues Top-Level-Feld geht beim Speichern über Go still verloren, wenn es nicht in beiden Go-Modellen steht. Drift-Gate `internal/model/trip_schema_drift_test.go` + `tests/test_trip_schema_drift.py`.
- Merge: Trip-PUT `internal/handler/trip.go:303`, `mergeConfigMap` nur eine Ebene tief (`config_merge.go:11`); `PutTripWeatherConfigHandler` (`weather_config.go:101`); Compare-PUT `applyComparePresetPatch` (`compare_preset.go:305`) → `mergeBriefingPatch` (`briefing_subscription.go:184`).
- **Folgerung:** Ampel unter `display_config` ⇒ Go braucht keine Modelländerung (Pass-through). Achtung: `mergeConfigMap` ist nur eine Ebene tief ⇒ ein PUT mit Teil-Ampel ersetzt den ganzen Ampel-Unterbaum (in der Spec klären).

### Vorlagen
- `WEATHER_TEMPLATES` (`metric_catalog.py:1296`): `{id: {label, metrics}}`, 7 Einträge, ohne Grenzen; `GET /templates` (`api/routers/config.py:25`), Proxy `/api/templates` (`internal/router/router.go:238`).
- Eigene Vorlagen = Go-`MetricPreset` (`internal/model/metric_preset.go:30`), Datei `data/users/<uid>/metric_presets.json`, Endpunkte `/api/metric-presets` (`router.go:287-290`). `SavePresetDialog.svelte:119-128` sendet keine Grenzen/Alarmstufen. `is_default` exklusiv, wird von neuen Trips **nicht** übernommen.
- Trip merkt die Vorlage in `display_config.preset_name` (`WeatherMetricsTab.svelte:498`, `:967`); Compare hat kein Gegenstück.

### `horizons`
- Filter `_allowed_col_keys_for_horizon` (`src/output/renderers/email/html.py:759`), übersprungen nur bei `horizons[h] is False`; `derive_horizon` (`email/helpers.py:321`); zweiter Leser `visible_cols` (`helpers.py:256ff`).
- „Alle Tage“ = Feld fehlt (`None`) oder `{"today":true,"tomorrow":true,"day_after":true}`.

### Compare-`profil`
- `scheduler_dispatch_service.py:919f` → `_parse_activity_profile` (`loader.py:2136`) → `run_comparison_parallel(profile=...)` → `calculate_score` (`comparison_scoring.py:19`); Mail-Kopf `profile_signature` (`email/compare_html.py:1746`, Zelle „Profil“ :1405-1410).
- **Wertebereiche passen nicht zusammen:** Python 4 Profile (`app/profile.py:24-27`), Go andere 4 (`activity_profile.go:11-14`), `WEATHER_TEMPLATES` 7 Schlüssel.

### Hook `data_schema_backup`
- Löst aus bei `internal/model/`, `internal/store/store.go`, `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py` (`.claude/hooks/data_schema_backup.py:25-31`); nicht bei `internal/store/trip.go`, `internal/store/compare_preset.go`, `src/app/metric_catalog.py`.

### API-Vertrag (`docs/reference/api_contract.md`)
MetricConfig :820 · Orts-Vergleich-Presets §10 :905 · Trip DTO §10.5 :971 · Weather Config §11 :1302 · MetricPreset §15.5 :2340 · ComparePreset §16 :2535 (ideal_ranges :2671) · Corridor §24 :4737.
