# Context: feat-3277-altfelder-entfernen

## Request Summary
Issue #3277 (Epic #3122, B6b-3): Ein Skript entfernt je Nutzer die zehn Altfelder aus gespeicherten Trips und Ortsvergleichen (RMW mit Merge, Sicherung, idempotent, Probelauf). Danach `show_outlook` und `multi_day_trend_reports` (und die übrigen Altfelder) aus Modell, Loader, Serialisierung und Renderer-Signaturen entfernen. Danach schließt #3102 als Nachweis. Voraussetzungen #3237 und #3276 sind zu und live (PRs #3303, #3309 am 23.11. gemergt).

Altfeld-Liste (Spec `feat_3122_was_steht_wo.md` Teil A Nr. 8, Nachtrag 21.11.): `channel_layouts`, `channel_layouts_per_report`, `channel_active_metrics`, `outlook_metrics`, `outlook_metric_formats`, `hourly_metrics`, `hourly_metric_formats`, `show_outlook`, `multi_day_trend_reports`, `outlook_enabled`.

## Bestand in Produktion (Zählung 25.11., read-only)
Pfad `/var/lib/gregor/users/<uid>/briefings/<id>.json` (Trip und Vergleich gemeinsam, `kind`).
- `display_config.channel_active_metrics` 3, `.channel_layouts` 1, `.hourly_metric_formats` 1, `.hourly_metrics` 3, `.multi_day_trend_reports` 4, `.outlook_metric_formats` 1, `.outlook_metrics` 3
- Top-Level `outlook_enabled` 4 (Ortsvergleiche!)
- `report_config.multi_day_trend_reports` 6, `report_config.show_outlook` 3
- `default/compare_presets.json` enthält noch 1× `display_config.channel_layouts` (Altdatei, laut Code nicht mehr gelesen).

## Kernbefund: `outlook_enabled` ist NICHT wirkungslos
`outlook_enabled` (Ortsvergleich, Top-Level) wird noch aktiv gelesen und geschrieben:
- Python: `src/services/report_config_resolver.py:284`, `src/services/placements_view_service.py:716` (→ `placements_aus_grundauswahl(outlook_enabled=…)`, `src/services/placements.py:275-291`, `channel_list_resolver.py:65-80`)
- Hook: `.claude/hooks/_soll_aus_konfiguration.py:647`
- Go: `internal/model/compare_preset.go:71` (`OutlookEnabled *bool`), Tests `compare_preset_outlook_enabled_test` u. a.
- Frontend schreibt es: `compare/compareEditorSave.ts:187/398`; liest: `weatherMetricsCompareSave.ts:138`, `alarmeVergleichSpeicherung.ts:171`, `versandVergleichSpeicherung.ts:172`, `wertebereicheVergleichSpeicherung.ts:77`, `CompareTabs.svelte:580`.
Wirkung: bei Abo ohne `rows` steuert es `outlook_reports=[]` in der Grundauswahl-Tabelle; ggf. weitere Lesestellen (Ausblick-Schalter im Orte-Editor). → In `/20-analyse` klären: Ist es nach ADR-0124 durch `placements.outlook_reports` ersetzt (dann Leser umstellen, Bestand: `outlook_enabled:false` ⇒ `outlook_reports=[]` sichern, bevor das Feld fällt), oder bleibt es als eigenständiger Schalter (dann aus der Liste nehmen, Spec-Nachtrag)?

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/models.py` :815-852 (`UnifiedWeatherDisplayConfig.multi_day_trend_reports`, `per_channel_layouts`, `per_report_layouts`, `outlook_metrics`, `outlook_metric_formats`), :1060/:1073 (`TripReportConfig.multi_day_trend_reports`, `show_outlook`) | Modellfelder entfernen |
| `src/app/loader.py` :666-679 (rc lesen), `_parse_display_config` :1048 (:1133-1223), `save_location` :1751-1768, `_trip_to_dict` :1980-2094, RMW `_deep_merge_preserve_unknown` :139, `save_trip` ~:2169, `update_trip` :2238 | Lesen/Schreiben der Altfelder; Achtung: Deep-Merge erhält unbekannte Schlüssel → nach Modellentfernung bleiben Bestandswerte sonst stehen (Skript muss sie aktiv löschen) |
| `src/app/metric_catalog.py:1143` `normalize_outlook_metric_formats` | Lade-Normalisierung, ggf. entfernen |
| `src/output/renderers/email/__init__.py:69/180/218`, `email/html.py:842` (+:1199/:1276/:1428), `email/plain.py:176` (+:275/:355/:385), `trip_report.py:287` | `show_outlook`-Parameter: NUR E-Mail-Renderer haben ihn (immer True via `report_config_resolver.py:111/142`). Telegram/SMS/Premium-SMS haben keinen. `multi_day_trend_reports` ist in keinem Renderer Parameter |
| `src/output/renderers/trip_report.py:331-337` | liest `per_channel_layouts`/`per_report_layouts` aus dem Modell |
| `src/services/report_config_resolver.py:86-87, 111, 142, 284` | Altfeld-Vermerke, `show_outlook` konstant True, `outlook_enabled`-Lesestelle |
| `src/output/renderers/compare_outlook_metric_ids.py:371` (`__all__` :520) `resolve_hourly_metric_formats` | ohne Produktionsaufrufer → mitlöschen samt Tests `tests/tdd/test_katalog_stellen_formen.py:88`, `tests/tdd/test_3156_renderer_nachzug_roh_einfach.py:339` (Issue-Kommentar F005) |
| `src/services/validator_render_service.py:481-491`, `api/routers/validator.py:620-623` | Request-Schema `hourly_metrics`/`hourly_metric_formats` (Validator-Vorschau) – Request-Parameter, nicht gespeichertes Feld; in Analyse prüfen |
| Renderer-Parameter `outlook_metrics`/`hourly_metrics`/`outlook_enabled` in `comparison.py`, `email/compare_html.py`, `narrow.py`, `compact.py`, `outlook.py`, `helpers.py` | Werte kommen aus `placements`/View-Model, nicht aus Store → keine Altfelder, bleiben |
| `internal/model/compare_preset.go:71`, `internal/model/trip.go:124-125` (`DisplayConfig`/`ReportConfig` als map) | Go reicht Altfelder ungeprüft durch; `config_merge.go:11` flaches Merge |
| Frontend: `lib/types.ts` :286/:296/:329/:330/:341/:345/:750; `WeatherMetricsTab.svelte` liest :494/:505/:510/:582/:922 und **schreibt** `channel_layouts`/`outlook_metrics`/`outlook_metric_formats` :939-948; `shared/pickEigenfelder.ts` :55/:69/:79-83; `MailInhaltCard.svelte:31/56/79/133` (`show_outlook` RMW, Kommentar „Entfernung #3277“), `mailInhaltZustand.ts:9/31`, `mailInhaltKonstanten.ts:21`; `versand-tab/reportConfigPayload.ts:54-127`, `zustellung-tab/kanalStilSpeicherung.ts:29/43`, `trip-new/tripNewLogic.ts:392-410` (`multi_day_trend_reports` schreiben/vorbelegen); `utils/cockpitHelpers568.ts:60`; `weatherMetricsSavePayload.ts:36/88`; Orte lesen `weatherMetricsCompareSave.ts:94-140`, `compareChannelMetricLayouts.ts:40` | **Trip-Frontend schreibt noch Altfelder** (#3276 betraf nur Ortsvergleich). Ohne Rückbau entstehen sie nach der Bereinigung beim Speichern neu |
| `.claude/hooks/_soll_aus_konfiguration.py:484-499, 647` | `outlook_enabled`-Leser im Soll-Hook |
| `scripts/migrate_2792_profil_ampel.py` | Vorbild-Skript (s. Muster) |
| `scripts/migrate_2454_derived_children.py:116-122`, `scripts/backfill_display_config_issue111.py:47`, `scripts/send_gate_test_mails.py:447` | weitere Skripte mit Altfeldbezug → prüfen/entfernen |
| `tests/test_altpfad_import_sperre.py` | AST-Wächter gegen gelöschte Altpfad-Funktionsnamen, `ERLAUBT` leer; geeignet, um Namen wie `resolve_hourly_metric_formats` aufzunehmen; ein Wächter auf Feldnamen existiert nicht |

## Existing Patterns
- **Migrations-Skript** (`scripts/migrate_2792_profil_ampel.py`): CLI `--root` (Pflicht), `--backup-dir` (Default `root.parent/.backups`), `--execute` (sonst Probelauf mit Bericht). Zwei Phasen: alle Nutzer planen, dann je Nutzer `tar.gz`-Sicherung (`_sichern` :290), dann `schreiben` :325: `exclusive_lock(pfad)` (`services.file_lock`, gemeinsam mit Go), neu lesen, nur schreiben wenn Text = geplanter Alttext, atomar (`_atomar` :310 tmp+fsync+chmod+`os.replace`). Nutzerordner mit `.`/`_` übersprungen; Dateien `udir/briefings/*.json`. Idempotent (unverändert ⇒ nicht geschrieben), Exit 1 bei offenen Dateien/Sicherungsfehler. Das gelöschte `migrate_3157_placements.py` (letzte Fassung Commit 4d6676a44) nutzte genau dieses Muster inkl. fail-closed je Abo.
- **Datenschutz-Regel** ADR-0101 / CLAUDE.md „Daten-Schema-Reworks“: RMW mit Merge, nie Replace; Edits an Schema-Dateien lösen `data_schema_backup.py` aus.
- **Golden-Vier-Kanal-Test** `tests/tdd/test_3237_golden_vier_kanaele.py` (`TRIP_ALTFELDER`/`ORTE_ALTFELDER`/`TRIP_RC_ALT` :67-95): beweist Byte-Gleichheit aller vier Kanäle mit/ohne Altfelder (AC-38) – Basis für den Nachweis, dass das Entfernen nichts an der Ausgabe ändert.
- Go-Seite: `DisplayConfig`/`ReportConfig` sind Maps, also keine Struct-Felder zu entfernen außer `OutlookEnabled`.

## Dependencies
- Upstream: `services.file_lock`, `services.placements.placements_aus_grundauswahl`, ADR-0124, ADR-0101.
- Downstream: Loader/Serialisierung (Python), alle Renderer (E-Mail-Signatur), Frontend-Editoren Trip (Wetter-Metriken, Mail-Inhalt, Versand, Zustellung, Trip-Anlage), Orte-Editor (`outlook_enabled`), Soll-Hook und Mail-Validatoren, sehr viele Tests (Python ca. 60 Dateien, Frontend ca. 75 Dateien, Go ca. 15) mit Altfeld-Fixtures.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` – Teil A Nr. 8 (Altfeld-Liste, Nachträge 21./22.11.), AC-38
- `docs/specs/modules/feat_3237_altpfad_entfernen.md` – Abgrenzung: Altfelder bleiben bis #3277 in Loader/Serialisierung/Bestand
- `docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md` – Frontend-Schreibwege Ortsvergleich
- `docs/specs/modules/feat_3157_migration_placements.md` – Migrationsmuster B6
- `docs/reference/api_contract.md` – DTO-Vertrag (Altfelder dort nachziehen)

## Risks & Considerations
1. **Trip-Frontend schreibt noch Altfelder** (`WeatherMetricsTab.svelte`, `reportConfigPayload.ts`, `kanalStilSpeicherung.ts`, `tripNewLogic.ts`, `MailInhaltCard.svelte`). Reihenfolge zwingend: erst Schreiber (Frontend + Python-Serialisierung) entfernen und live, dann Skript laufen lassen – sonst entstehen die Felder neu. Umfang spricht für Schnitt in Teilschritte (Epic-Regel: eigene Kind-Issues).
2. **`outlook_enabled` hat noch Wirkung** (Ortsvergleich-Ausblick an/aus). Vor Entfernen fachlich klären bzw. Wirkung in `placements.outlook_reports` überführen; sonst Verhaltensänderung für 4 Bestandsabos.
3. **Deep-Merge beim Speichern erhält unbekannte Schlüssel**: Modellentfernung allein entfernt nichts; das Skript muss aktiv löschen, und Go `mergeConfigMap` darf sie nicht aus einem Client-Payload zurückholen.
4. Issue-Text „Renderer-Parameter gleichzeitig in allen vier Kanälen“: faktisch hat nur der E-Mail-Renderer `show_outlook`; `multi_day_trend_reports` ist nirgends Renderer-Parameter. Kanalparität bleibt gewahrt, da Telegram/SMS/Premium-SMS ohnehin keinen haben.
5. Viele Tests nutzen Altfelder als Fixture; beim Entfernen der Modellfelder brechen Tests, die sie setzen/erwarten → Tests anpassen, nicht Code verbiegen. Golden-Test AC-38 muss grün bleiben.
6. `compare_presets.json` (Altdatei, user `default`) enthält Altfeld – klären, ob Skript sie mit bereinigt oder die Datei als tot entfernt wird.
7. Mehrere Scripts referenzieren Altfelder (`migrate_2454`, `backfill_…issue111`, `send_gate_test_mails.py`) – auf Lauffähigkeit prüfen.
8. `resolve_hourly_metric_formats` ohne Aufrufer → löschen und in `VERBOTEN` von `tests/test_altpfad_import_sperre.py` aufnehmen.
9. Nach Abschluss: #3102 als Nachweis schließen.

## Analysis

### Type
Feature (Rückbau, Epic #3122 B6b-3)

### Schnitt-Entscheidung (Tech Lead, 25.11., Kommentar in #3277)
Ein Datenlauf vor dem Code-Rückbau ist wertlos (Python `_trip_to_dict` schreibt `multi_day_trend_reports`/`show_outlook` als Defaults bei jedem Speichern; Trip-Frontend #3297 und Orte-Frontend `outlook_enabled` schreiben weiter). Daher:
- **#3277 (dieser Workflow) = Code-Rückbau Python + Go + Hook**, ohne Frontend und ohne Datenlauf.
- **Datenlauf → neues Kind-Issue #3351** (Skript nach `migrate_2792`-Muster, Staging+Prod, Nachzählung, schließt #3102). Voraussetzung #3277, #3297, #3298 live.
- `outlook_enabled`-Frontend-Round-Trip → Scope #3298 (Kommentar dort).
- Reihenfolge der Kette: #3277 → #3297 → #3301/#3298 → #3351 → #3020 → #3009 (Auftragsliste um #3351 vor #3020 ergänzen).
- `outlook_enabled` wird entfernt (ADR-0124 Nr. 6: ersetzt durch `outlook_reports`; Prod: alle Abos mit `rows`/`outlook_reports`, alle Werte `true`; keine Bedienfläche, Frontend sendet konstant true → Erstanlage unverändert).
- Kein Go-Strip auf Schreibwegen (würde noch schreibende UI stumm zurückspringen lassen, Wegwerfcode); stattdessen entfernt Python-Speichern die zehn Namen aktiv, dazu Feldnamen-Wächter.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/models.py` | MODIFY | `UnifiedWeatherDisplayConfig`: `multi_day_trend_reports`, `per_channel_layouts`, `per_report_layouts`, `outlook_metrics`, `outlook_metric_formats` entfernen; `TripReportConfig`: `multi_day_trend_reports`, `show_outlook` entfernen |
| `src/app/loader.py` | MODIFY | Lesen (666-679, 1133-1223), Schreiben (`save_location` 1751-1768, `_trip_to_dict` 1980-2094) entfernen; beim Speichern die zehn Namen aus `extra`/Merge-Ergebnis aktiv verwerfen |
| `src/app/metric_catalog.py` | MODIFY | `normalize_outlook_metric_formats` entfernen, falls ohne weiteren Aufrufer |
| `src/output/renderers/email/__init__.py`, `email/html.py`, `email/plain.py`, `trip_report.py` | MODIFY | Parameter `show_outlook` entfernen; `trip_report.py:331-337` Lesestelle `per_channel_layouts`/`per_report_layouts` entfernen |
| `src/services/report_config_resolver.py` | MODIFY | `ReportRenderOptions.show_outlook`, Altfeld-Vermerke 86-87, `outlook_enabled`-Lesen 284 entfernen |
| `src/services/placements_view_service.py`, `placements.py`, `channel_list_resolver.py` | MODIFY | Parameter `outlook_enabled` entfernen |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | `resolve_hourly_metric_formats` + `__all__` löschen (samt Tests) |
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | `outlook_enabled` 484-499/647 entfernen |
| `internal/model/compare_preset.go` + Go-Tests | MODIFY | Feld `OutlookEnabled` entfernen |
| `scripts/migrate_2454_derived_children.py`, `scripts/backfill_display_config_issue111.py`, `scripts/send_gate_test_mails.py` | MODIFY/DELETE | verbrauchte Einmal-Migrationen löschen bzw. Altfeld-Bezug entfernen |
| `tests/test_altpfad_import_sperre.py` | MODIFY | `resolve_hourly_metric_formats` (+ ggf. `normalize_outlook_metric_formats`) in `VERBOTEN` |
| `tests/test_altfeld_namen_sperre.py` | CREATE | Wächter: die zehn Namen als Schlüssel-Literal/Attribut in Backend-Code verboten (ERLAUBT mit Grund+Ablauf, Selbstnachweis) |
| `tests/tdd/test_3237_golden_vier_kanaele.py` | MODIFY | umdeuten: Altfelder im Eingang ignoriert und beim Speichern entfernt; Byte-Gleichheit bleibt |
| ca. 60 Python-, 15 Go-Testdateien | MODIFY | Fixtures auf `placements` umstellen, nicht still löschen |
| `docs/reference/api_contract.md`, Spec `feat_3122_was_steht_wo.md` (Nachtrag) | MODIFY | Vertrag/Nachtrag |

### Scope Assessment
- Files: ca. 25 Produktion + ca. 75 Tests + Doku
- Estimated LoC: +300 / -900
- Risk Level: MEDIUM (zentrale Lade-/Speicherpfade und E-Mail-Renderer; Ausgabe muss bytegleich bleiben)

### Technical Approach
1. Python-Modell/Loader/Serializer: Felder raus; Speichern verwirft die zehn Namen aktiv.
2. E-Mail-Renderer: `show_outlook` raus (war konstant True).
3. `outlook_enabled` raus in Resolver, Placements-View, Hook, Go-Modell.
4. Toter Code raus, Sperren ergänzen.
5. Nachweis: Golden-Vier-Kanal-Test bytegleich mit/ohne Altfelder; Speichern eines Abos mit Altfeldern hinterlässt keine; zwei Nutzer.

### Dependencies
- Upstream: ADR-0124 Nr. 6/8, ADR-0101, `placements_aus_grundauswahl`.
- Downstream: Frontend schreibt bis #3297/#3298 weiter Altfelder; sie wirken nicht, Python-Speichern entfernt sie wieder.

### Open Questions
- Keine an den PO (Rückbau ohne Verhaltensänderung; Reihenfolge ist Tech-Lead-Entscheidung).
- In der Spec prüfen: Go-Speicherwege, die Dateien ohne Python schreiben (Client-Altfelder bleiben dann bis #3351 auf der Platte, wirkungslos).
