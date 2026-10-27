# Context: fix-1981-alarm-abwahl-vokabular

## Request Summary
Im Ortsvergleich wirkt eine im Alarme-Reiter auf `off` gestellte Metrik nicht, wenn ihr Level unter einem
Alt-Schlüssel im Summary-Vokabular gespeichert ist (`temp_max_c` statt `temperature_max`). Der Alarm feuert
trotz Abwahl. Ziel: gespeicherte Alarm-Stufen werden im Vergleich vollständig und im richtigen Vokabular
ausgewertet — ohne neuen Widerspruch zwischen Anzeige und Wirkung.

## Ursache (belegt)
- Alt-Schlüssel entstanden **13.–30.07.2026**: Commit `13afcd873` (#1231 Slice 4) schrieb im Vergleichs-
  Wertebereiche-Editor `metricAlertLevels[r.metric]` mit Summary-Key; entfernt mit `e5cec9ce5` (#1371 S6).
- **Heute entstehen keine neuen Alt-Schlüssel** — das Frontend schreibt nur alertMetric-Namen
  (`frontend/src/lib/components/shared/alarme-tab/activeAlertMetricsFromCatalog.ts:19-30`).
- Alt-Schlüssel **überleben jedes Speichern**: Hydration übernimmt das Objekt 1:1
  (`compareHubHydration.ts:99`), Speichern spreizt es (`alarmePropsAus.ts:137-138`, `compareEditorSave.ts:201-202`).
- Auswertung: `compare_alert.py:701-704` reicht `metric_alert_levels` unübersetzt an
  `expand_per_metric_levels` (`src/services/alert_preset.py:178`); dort wirft `AlertMetric(key)` `ValueError`
  → Schlüssel verworfen; #961-Backfill setzt die (aktive) Metrik wieder auf `standard`.
- Kein Normalisierer für Compare-Presets: Go `internal/store/trip.go:331` und Python `src/app/loader.py:764`
  migrieren nur `snow_line`→`freezing_level` und nur für Trips. `load_compare_presets` (`loader.py:309`) migriert nichts.

## Anzeige vs. Wirkung (kritisch für den Entwurf)
- `AlertMetricLevelTable.svelte:83`: `level={levels[metric] ?? 'standard'}` — Alt-Schlüssel wird nie
  nachgeschlagen. **Der Nutzer sieht heute „Standard“, gespeichert ist „off“, ausgewertet wird „standard“.**
  Anzeige und Wirkung stimmen also heute überein; nur der gespeicherte Alt-Wert widerspricht beiden.
- Folge: Eine reine Übersetzung beim Auswerten würde Alarme abschalten, die der Editor als „Standard“ zeigt
  → neuer Widerspruch. Entscheidungsbedarf (PO, Spec): welcher Wert gilt bei Alt-Schlüssel — gespeicherter
  (Nutzerabsicht vom Juli) oder angezeigter? Und: Vorrang, wenn Alt- und Neu-Schlüssel beide stehen.

## Übersetzung Summary-Key → alertMetric (per Python-Aufruf geprüft)
Quelle: `alert_metric_for(metric_id, aggregation)` (`src/app/metric_catalog.py:982`), dieselbe Quelle wie das
Frontend (`compare_metric_catalog.py:406`). Keine direkte Funktion Summary-Key → alertMetric; Umkehr über
`summary_fields` / `summary_field_for` (`metric_catalog.py:968`).

| Summary-Key | (metric_id, agg) | alertMetric |
|---|---|---|
| temp_max_c | temperature, max | temperature_max |
| temp_min_c | temperature, min | temperature_min (temperature_cold/min → None) |
| gust_max_kmh | gust, max | wind_gust |
| precip_sum_mm | precipitation, sum | precipitation_sum |
| visibility_min_m | visibility, min | visibility |
| cape_max_jkg | cape, max | cape |
| thunder_level_max | thunder, max | thunder_level |
| wind_max_kmh | wind, max | wind_change |
| wind_chill_min_c | wind_chill, min | **None** — keine Alarm-Identität, nur verwerfbar |

Umkehr von `_ALERT_METRIC_TO_SUMMARY_FIELD` (`weather_change_detection.py:38-58`) ist NICHT eindeutig
(`freezing_level_m` doppelt, Delta-Felder geteilt mit `*_change`) — nicht verwenden.

## Related Files
| File | Relevance |
|------|-----------|
| src/services/compare_alert.py:680-720 | `_build_eval_config` — einziger Python-Leser im Compare-Pfad |
| src/services/alert_preset.py:178-290 | `expand_per_metric_levels`, interne snow_line-Normalisierung :221-224 (Andockmuster) |
| src/app/metric_catalog.py:968,982 | `summary_field_for`, `alert_metric_for` — Übersetzungsquelle |
| src/app/loader.py:309,764,1057 | Compare-Laden ohne Migration; Trip-Migrationsmuster |
| internal/store/compare_preset.go:~101 | Go-Ladepfad, Andockpunkt neben `migrateComparePresetSlots` |
| internal/store/trip.go:272,331 | Go-Migrationsmuster `migrateMetricAlertLevels` |
| frontend/.../compareHubHydration.ts:99 | Hydration 1:1 |
| frontend/.../alarmePropsAus.ts:124,137-138 | Weiterreichen + Spread beim Ändern |
| frontend/.../compareEditorSave.ts:200-202,530 | PUT-Payload |
| frontend/.../AlertMetricLevelTable.svelte:32,83 | Anzeige-Default `standard`, `activeCount` |
| frontend/.../corridorPropsAus.ts:41-71, compareWizardState.svelte.ts:91,174, CompareTabs.svelte:391 | weitere Frontend-Leser |
| scripts/migrate_1373_compare_active_metrics_format.py | Skript-Muster: Probelauf default, `--execute`, tar.gz-Backup |

## Existing Patterns
- Lade-Migration mit Umbenennung, bestehender Neu-Schlüssel gewinnt (`setdefault`), Quelle unverändert (#959).
- Migrationsskripte: Dry-Run default, `--execute`, Backup (#1373, #1191, #946).
- Read-Modify-Write mit Merge (#102).

## Dependencies
- Upstream: Metrik-Katalog/Register (`metric_catalog.py`), `AlertMetric`-Enum, `_PRESET_TABLE`.
- Downstream: `deviation_alert_engine.py:180-200`, `point_weather.py:66` (verarbeiten nur die gebaute Config);
  Go liest das Feld für Presets nicht.

## Existing Specs
- `docs/specs/modules/issue_1971_legacy_preset_alarm_fallback.md` (Known Limitation nennt #1981)
- `weather_change_detection.md` (#961), `rework_1351_compare_catalog.md` (#1191)
- `feat_1373_s2_ein_katalog.md`, `feat_1373_s2b_metrik_speicherformat.md`
- `feat_1435_e1a_alarmfaehigkeit_register.md`, `feat_1435_e1a2_alarme_reiter_register.md`, `fix_1435_e5_alert_mapping_unify.md`

## Tests (Bestand)
- `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py` (:271 nutzt `temp_max_c` — Erwartung prüfen!)
- `test_issue_1170_compare_alert_config.py`, `test_compare_alert_metric_gating.py`,
  `test_bug_alert_ignores_weather_tab_disable.py`, `test_issue_864_859_alert_metric_levels.py`,
  `test_issue_946_alert_architecture.py`, `test_alert_sensitivity_levels.py`
- `tests/unit/services/test_deviation_alert_engine_matches_frontend_derivation.py`, `tests/unit/test_alert_metric_identity_delivery.py`
- Frontend: `corridor-editor/__tests__/wertebereicheVergleichPruefstand.ts:56` nutzt Alt-Schlüssel

## Trip-Pfad
`trip_alert.py:713-714,991-992` lesen dasselbe Feld. Trip-Corridors schrieben immer alertMetric-Namen
(`scripts/migrate_1231_corridors.py:43`) → vermutlich nicht betroffen. **Nicht an echten Daten gemessen.**

## Risks & Considerations
- **Ausmaß in Produktion unbekannt:** `/var/lib/gregor/users` ist für `hem` nicht lesbar (Permission denied).
  Bekannt ist ein Preset (`cp-eb6ba0b239d90e37` „Le Var", Nutzer henning, 8/11 Alt-Einträge). Zählung braucht
  einen anderen Weg (Migrationsskript im Probelauf durch berechtigten Prozess / infra).
- Anzeige-vs-Wirkung-Widerspruch (siehe oben) — PO-Entscheid in der Spec.
- Doppelte Schlüssel (Alt + Neu) — Vorrangregel nötig; Vorbild #959: Neu gewinnt.
- `wind_chill_min_c` und mehrdeutiges `temp_min_c` → definierte Behandlung (verwerfen bzw. Register-Default).
- Bereinigung muss in Go-Ladepfad UND Python-Auswertung konsistent sein, sonst schreibt das Frontend Leichen zurück.
- Ein Bestandstest nutzt bereits Alt-Schlüssel — Erwartung kann sich ändern.
- Kein Vergleichs-Mail-Inhalt betroffen → `email_spec_validator.py` voraussichtlich nicht im Umfang; in Analyse bestätigen.

## Analysis

### Type
Bug (nutzersichtbar: Abwahl im Alarme-Reiter des Ortsvergleichs wirkt nicht)

### Entscheidende Befunde der Analyse
- **Python liest Vergleiche direkt von Platte**, nicht über Go: `compare_preset_access.py:22,33` →
  `load_compare_presets` (`loader.py:309`) → `compare_preset_to_dict` (`loader.py:~273`, `display_config` 1:1).
  Eine Go-Normalisierung allein erreicht die Auswertung also erst nach dem nächsten Speichern im Editor.
- Einziger Python-Leser im Vergleichspfad: `compare_alert.py:701-704` (`_build_eval_config`, Aufruf :249).
  Weitere Leser (`deviation_alert_engine.py:180-200`, `point_weather.py:66`) verarbeiten nur die gebaute Config.
  Trotzdem Andockpunkt **im Loader**, damit jeder heutige und künftige Leser abgedeckt ist.
- Python schreibt Vergleichsdateien nur per eigenem Read-Modify-Write (`scheduler_dispatch_service.py:265,303`,
  Status/Pause) — liest dort die Datei selbst. Die Normalisierung bleibt im Speicher; die Platte heilt über Go
  beim nächsten Speichern im Editor. Kein Python-Rückschreiben der übersetzten Werte nötig.
- `temp_min_c`: Normalisierer bildet auf `temperature_min` ab. Der #961-Filter erwartet für TEMPERATURE_MIN
  die Katalog-IDs `("temperature_cold", "temperature")` (`weather_change_detection.py:99`); `active_metrics`
  übersetzt `temp_min_c` → `temperature_cold` (`compare_alert.py:65`) → passt. End-to-End-Test über
  `_build_eval_config` trotzdem Pflicht (Prüfort = Wirkort).
- `_SUMMARY_KEY_TO_CATALOG_ID` (`compare_alert.py:63-74`) bedient ein anderes Vokabular (Katalog-ID) — unangetastet.
- Bestandstest `test_compare_alert_missing_active_metrics_with_levels.py:271` ist nur ein Kommentar
  (Feldliste) — nicht betroffen. Frontend-Fixture `wertebereicheVergleichPruefstand.ts:56` nutzt
  `wind_max_kmh` als Testdatum für den Wertebereiche-Editor — prüfen, ob Anpassung nötig.

### Nebenbefunde aus #1199 (Kommentar im Ticket)
- **B2-33** (Summary-Vokabular in `metric_alert_levels`) = genau dieser Bug → wird mit behoben.
- **B1-04** (CAPE im Rückfall `_STANDARD_METRIC_LEVELS`, `compare_alert.py:50`): **durch #1971 bereits
  entschieden — kein Änderungsbedarf.** Die freigegebenen ACs **AC-4 und AC-6** in
  `docs/specs/modules/issue_1971_legacy_preset_alarm_fallback.md:245-269` verlangen ausdrücklich, dass
  Alt-Vergleiche ohne `active_metrics` die CAPE-Regel BEHALTEN (Tests `test_cape_rule_survives_*`,
  `test_legacy_preset_without_levels_unchanged_rule_count`). Zudem füllt die #1971-Ergänzung
  (`alert_preset.py:~408`) direkt aus `_PRESET_TABLE` auf — ein Filter an `:50` hätte keine Wirkung.
  Beim Abschluss im Ticket mit diesem Verweis abhaken.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/app/loader.py | MODIFY | Gemeinsamer Normalisierer `metric_alert_levels` (Summary-Key → alertMetric + bestehendes snow_line→freezing_level), Aufruf im Trip- UND Vergleichs-Ladepfad (`:764`, `:1057`, `load_compare_presets`/`_parse_compare_preset`) |
| internal/store/trip.go | MODIFY | `migrateMetricAlertLevels` (`:331`) um dieselbe Übersetzungstabelle erweitern |
| internal/store/compare_preset.go | MODIFY | Aufruf in `normalizeLoadedComparePreset` (`:88-114`, neben `migrateComparePresetSlots`) → Editor zeigt gespeicherten Wert, Speichern heilt die Datei |
| src/services/alert_preset.py | evtl. MODIFY | interne snow_line-Normalisierung `:221-224` ggf. auf den geteilten Baustein umstellen (nur falls ohne Risiko) |
| tests/tdd/test_alarm_abwahl_alt_vokabular.py (Name vorläufig) | CREATE | Abwahl wirkt (Regel- UND Feld-Ebene), Vorrang, Sonderfälle, Paritätstest Tabelle ↔ `alert_metric_for` |
| internal/store/compare_preset_test.go | MODIFY | Go-Ladetest: Alt-Schlüssel → Neu, Neu gewinnt, idempotent, fremde Schlüssel bleiben |

### Scope Assessment
- Files: 4–5 produktiv + 2 Testdateien
- Estimated LoC: ca. +120/−20 produktiv (unter Limit 250)
- Risk Level: MEDIUM — betrifft die zentrale Alarm-Auswertung; Wirkung aber eng auf Alt-Schlüssel begrenzt

### Technical Approach (Empfehlung)
**Ein geteilter Normalisierer, in Python UND Go, für Trip UND Vergleich:**
1. Feste Übersetzungstabelle (8 Einträge laut Tabelle oben; `wind_chill_min_c` → verwerfen, da keine
   Alarm-Identität; `temp_min_c` → `temperature_min`). Paritätstest prüft sie gegen
   `alert_metric_for`/`summary_field_for` (`metric_catalog.py:968,982`) und Go↔Python.
2. Regeln: **Neu-Schlüssel gewinnt** bei Doppelbelegung (Vorbild #959), Alt-Schlüssel wird entfernt,
   alle übrigen Schlüssel bleiben unverändert (Merge, kein Neuaufbau), zweiter Lauf = No-Op.
3. Python: im Vergleichs-Ladepfad → Auswertung wirkt sofort für alle Bestandsdaten.
4. Go: im Lade-Normalisierer → Editor zeigt den gespeicherten Wert; nächstes Speichern schreibt Neu-Schlüssel.
5. **Leere-Map-Grenzfall:** `or _STANDARD_METRIC_LEVELS` (`compare_alert.py:702-703`) bleibt unverändert.
   Ein Preset nur mit `wind_chill_min_c: off` wird nach Normalisierung `{}` → voller Standard-Satz — dasselbe
   Verhalten wie heute (Schlüssel wird heute ebenfalls verworfen). Grenzfall-Test sichert das.
6. Kein Migrationsskript im Umfang (Datenbestand für `hem` unlesbar; Selbstheilung über Lade-Normalisierung genügt).

### Dependencies
- Upstream: `metric_catalog.py` (`alert_metric_for`, `summary_field_for`), `AlertMetric`-Enum, `_PRESET_TABLE`.
- Downstream: `deviation_alert_engine.py`, `point_weather.py` (nur gebaute Config); Frontend liest das Feld über Go.
- Vergleichs-Mail-Inhalt unberührt → `email_spec_validator.py` nicht im Umfang.

### Risiken
- Sichtbare Wirkung: Alarme, die heute trotz gespeichertem „aus“ feuern, verstummen. Bekanntes Preset
  „Le Var“ (Nutzer henning = PO selbst): praktisch keine Änderung, weil `active_metrics` dieselben Metriken
  ohnehin abschaltet. Anzahl weiterer betroffener Vergleiche unbekannt (Daten für `hem` unlesbar).
- Go- und Python-Tabelle müssen deckungsgleich sein → Paritätstest.
- Trip-Daten vermutlich frei von Alt-Schlüsseln (ungemessen) — Normalisierer ist dort No-Op.

### Open Questions
- [ ] **PO-Entscheid (als AC in /30 zur Freigabe):** Bei einem Alt-Eintrag gilt die **damals gespeicherte
  Einstellung** (Empfehlung, Variante A — genau das verlangt das Ticket „Abwahl wirkt nicht“) statt der
  heute angezeigten „Standard“-Stufe. Folge: Editor-Anzeige und Wirkung zeigen danach beide den gespeicherten Wert.
