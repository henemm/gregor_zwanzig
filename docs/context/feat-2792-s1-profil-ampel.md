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

## 2. Migration und Test-Lage (Analyse 2026-11-04)

### `corridors` / `ideal_ranges`
- Form `Corridor{metric, range:[min|None,max|None], notify, mark, prio}` (`src/app/models.py:1281-1296`). Fixtures: `tests/fixtures/trip_schema_full.json`, `tests/fixtures/migrate_2454/trip_frozen_wind_chill_structure.json`; Alt-`ideal_ranges` `{"temp_max_c":{"min":10,"max":25}}` (`tests/tdd/test_corridor_migration.py:248`).
- Altdaten sind seit `scripts/migrate_1231_corridors.py:120-152` schon in `corridors` (`mark=True`); `ideal_ranges` blieb stehen (`:10-11`) ⇒ S1 liest `corridors` primär, `ideal_ranges` nur als Rückfall.
- `mark` heute: grüner Randbalken im Band, grüner Hintergrund nur ohne Ampelfarbe (`src/output/renderers/email/corridor_mark.py:75-84`), Grenzen inklusiv (`src/services/corridor_match.py:17-36`).
- `notify` ohne Wirkung (`src/services/trip_alert.py:127-131`).
- **Falle:** Bereiche mit `notify=True, mark=False` stammen aus `alert_rules` und tragen **Δ-Werte** (`migrate_1231_corridors.py:44-53, 97, 111`) ⇒ nicht zu Ampel-Grenzen machen, nur protokollieren und erhalten.
- Abbildung Band → Ampel: `von` → `yellow_lt` exakt (Ampel prüft `value < yellow_lt`); `bis` → `yellow` verschiebt die Grenze um den Randwert (Ampel prüft `value >= yellow`, `src/output/metric_format.py:152-195`). Orange/Rot aus der Vorlage; Reihenfolge gelb < orange < rot ggf. verletzt ⇒ Regel nötig.
- Schlüsselräume verschieden: Trip AlertMetric-IDs (`wind_gust`, `precipitation_sum`, `thunder_level`, `temperature_min/max`, `snow_line`; `html.py:863`), Compare Summary-Keys (`temp_max_c`, `gust_max_kmh`; `compare_html.py:878,1100`).

### `sms_threshold`
- Freie Zahl (`models.py:689`) an drei Stellen: `metrics[]`, `channel_layouts`, `report_layouts` (`loader.py:999, 1040, 1075`; Schreiben `:182-184`).
- Wirkung: unter der Schwelle zeigt die SMS „-“, sonst Wert und Stunde (`src/output/tokens/builder.py:215-220`; Schneefallgrenze umgekehrt `:326-333`). Ersatzwerte uneinheitlich (`builder.py:165`; Mail-Ausblick `helpers.py:1012-1014`).
- Stufen der Oberfläche (`frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1838-1905`): Wind 15/20/30 · Böen 30/40/50 · Niederschlag 0.3/0.8/1.5 · Regenwahrsch. 25/40/60 · Schneehöhe 5/10/20 · Schneefallgrenze 2000/1500/1000 · Gewitter 1/2/3 (Sensibel/Standard/Robust). Globale Ampel gelb zum Vergleich: Wind 30, Böen 30, Niederschlag 1, Regenwahrsch. 30.
- **Konflikt:** `sms_threshold` als `yellow` übernommen ändert auch die Mail-Farbe (z.B. Wind gelb ab 20 statt 30).

### Vorlage eines Bestands-Trips
- Beste Quelle `display_config.preset_name` (`models.py:827`, `loader.py:1087, 1839`). `Trip.activity` (`trip.py:205`) nur über Frontend-Tabelle `ACTIVITY_TO_TEMPLATE` (`WeatherMetricsTab.svelte:662-674`).
- Compare-`profil`: `wintersport | wandern | summer_trekking | allgemein` (`src/app/profile.py:24-27`, Fixtures teils groß) ⇒ `summer_trekking` → `alpen-trekking`, Rest gleichnamig.
- Eigene Vorlagen: Go-`MetricPreset` typisiert (`internal/model/metric_preset.go:30-37`) ⇒ **neues Go-Feld nötig**, sonst geht die Ampel beim Speichern verloren.
- Python lädt `display_config` typisiert ⇒ `UnifiedWeatherDisplayConfig` braucht ein Feld plus Schreiben im Loader (Muster `loader.py:1839`), sonst löscht ein Python-Speichern die Ampel (ADR-0083).

### Migrations-Muster
- Batch-Skripte mit Probelauf, `--execute`, tar.gz-Sicherung, wiederholbar: `scripts/migrate_1231_corridors.py`, `migrate_2454_derived_children.py`, `migrate_1373_compare_active_metrics_format.py`.
- Beim-Laden-Migrationen: `_migrate_metric_alert_levels` (`loader.py:792-808`), `_migrate_weather_config` (`:576-584`).
- Regeln `docs/reference/operations_playbook.md:541-590`, ADR-0101; Reihenfolge erst Lese-Code, dann Migration (`playbook:741`).
- **Empfehlung:** Batch-Skript als Quelle der Wahrheit (Go und Frontend sehen keine Python-Lade-Migration; P3 verlangt Protokoll), dazu Rückfall beim Laden „fehlt die Ampel ⇒ Vorlage“.
- **Übergangsrisiko:** Bis S3a schreibt die alte Oberfläche weiter `corridors`/`sms_threshold`, die dann wirkungslos wären.
- `horizons` → „alle Tage“ in `metrics`, `channel_layouts`, `report_layouts`. CAPE: Metrik `cape` (`metric_catalog.py:515`) bzw. Compare `cape_max_jkg` (`loader.py:784`) → `thunder` an.

### Tests und Gates
- Testnamen nach Verhalten (`gates_und_ratschen.md:204-217`), kein breiter `uv run pytest` (`:219-225`).
- Renderer-Commit-Gate (`gates_und_ratschen.md:91-98`, `mail_validators.md:234-258`): `tests/tdd/test_issue_811_mode_matrix.py` + `briefing_mail_validator.py` frisch grün; Matrix-Test hängt an globalen Gelb-Schwellen (`:29, 42, 151`).
- **Kein Validator prüft Farben** (`briefing_mail_validator.py:376-608`, `email_spec_validator.py:860-1128`) ⇒ eigene Tests am Entstehungsort der Farbe.
- `severity_from_thresholds` kann schon beidseitig (`yellow/orange/red` + `*_lt`) ⇒ Ampel übernimmt diese Form, keine neue Rechnung.

### Umfang
- LoC-Limit 250 je Workflow (Tests und `scripts/` zählen mit). Schätzung gesamt ~1100-1300 LoC ⇒ Lieferung in drei Schritten unter einer Spec: **S1a** Datenmodell + Vorlagen-Grenzen + Auflösung (Ausgabe „Allgemein“ byte-gleich) · **S1b** Migrationsskript · **S1c** Renderer-Umstellung aller vier Kanäle.
