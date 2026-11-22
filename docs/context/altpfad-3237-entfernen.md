# Context: altpfad-3237-entfernen (#3237, Epic #3122)

## Request Summary
Nach der Migration (#3157, live 21.11.: alle 21 Prod-Abos tragen `display_config.placements`) soll nur noch die Tabelle „Was steht wo“ bestimmen, welche Metrik in welchem Kanal/Fläche steht. Altpfad (Lese-Adapter, Differenz-Orakel, Kanal-Kaskade) löschen, per AST-Import-Sperre bewachen, danach Altfelder aus Daten entfernen (Spec #3122 Teil A Nr. 8). Voraussetzungen #3157, #3218, #3242 sind geschlossen.

## Related Files
| File | Relevance |
|------|-----------|
| api/routers/validator.py:151-169, :574-593 | `_determine_cascade_source` → `dc.cascade_source_for_channel`; Endpoint `metrics-for-channel` → `dc.get_metrics_for_channel` (Vertrag `{source, metric_ids}`, Spec issue_448) |
| src/output/renderers/channel_layout.py:124-165 | `render_for_channel` liest `dc.get_metrics_for_channel`; alle Prod-Aufrufer (narrow.py:818, comparison.py:819, placements_view_service.py:457, trip_report.py:326-338) liefern bereits fertige Liste → kann `dc.metrics` je Report-Typ nehmen |
| src/services/channel_list_resolver.py | `ALTBESTAND_UEBER_UMRECHNUNG`:39, `legacy_view`:190, `legacy_lists`:343, `trip_channel_metrics`:360, `_trip_view`:424, `_compare_view`:495, `vm_lists`:318 u. Helfer; Tabellenpfad `placements_view`:255, `grundauswahl`:225 |
| src/services/placements.py | `placements_from_legacy`/`legacy_placements`/`_legacy_rows`:362-420/`_output_changes`:505 hängen an `legacy_view`/`legacy_lists`; `resolve_outlook_reports`:252 (Erlaubnis), `_legacy_outlook_reports`:344 |
| src/services/placements_view_service.py:104-151 | `erstanlage_begleitfelder` (Erstanlage-Umrechnung über Altzweig), via api/routers/placements.py:57-65 und Go-PUT |
| scripts/migrate_3157_placements.py | Migrationsskript, nutzt `placements_from_legacy`; nach Live-Migration entbehrlich |
| src/app/models.py:780-802, :949-989, :1031-1043 | `_cascade_source_for_channel`, `get_metrics_for_channel`, `cascade_source_for_channel`; Loader-Parse :1133-1167, Serialisierung :1760-1774, :2015-2029 (`per_channel_layouts`/`per_report_layouts`) |
| compare_outlook_metric_ids.py | `resolve_trip/compare_outlook_metrics/formats` :201-300 (nur Resolver ruft) |
| compare_metric_ids.py | `resolve_channel_enabled_metrics`:251, `resolve_channel_layout_rows`:387 (nur Resolver); `resolve_enabled_metrics(_report)` bleiben (Grundauswahl `active_metrics`) |
| src/services/report_config_resolver.py:150-182, :352, :449-460 | `_options_bisher` (show_outlook, multi_day_trend_reports), `_channel_unresolved_count` liest `channel_active_metrics` |
| email/html.py:1199/1428, plain.py:355/385 | `show_outlook` (Großwetterlage, #3155) |
| src/services/validator_render_service.py:480-490 | `hourly_metrics` für Vorschau-Payload |
| .claude/hooks/_soll_aus_konfiguration.py | Validator-Soll: Altzweige nur ohne Tabelle, ABER `orte_soll` :1019-1035 liest Altfelder zuerst; importiert `placements._legacy_outlook_reports`, `_feld` |
| tests/helpers/kanal_liste_orakel.py + test_3057_channel_list_resolver.py, test_3065_ausblick_stundenverlauf_resolver.py, test_einstellung_gleich_mail_trip_tabelle.py (`_adapter_gegen_orakel`), test_placements_umrechnung_altbestand.py | Löschliste aus Kommentar #3157 (20.11.) |
| weitere Tests mit Altprimitiven | test_channel_metric_matrix, test_ausblick_erbt_grundauswahl, test_compare_ausblick_erbt_grundauswahl, test_einstellung_gleich_mail_editor_standard, test_einstellung_gleich_mail_orte, test_outlook_acc_spalte, test_outlook_darstellungsform, test_outlook_metric_id_persistence, test_3156_renderer_nachzug_roh_einfach, unit/test_compare_channel_metric_cascade, unit/test_trip_metric_cascade_single_source |
| Frontend: types.ts, mailInhaltZustand.ts, MailInhaltCard.svelte, mailInhaltKonstanten.ts, pickEigenfelder.ts, cockpitHelpers568.ts:60, WeatherMetricsTab.svelte, weatherMetricsSavePayload.ts, channelMetricLayouts.ts, compareChannelMetricLayouts.ts, weatherMetricsCompareSave.ts, compareEditorSave.ts, versand/alarme/wertebereicheVergleichSpeicherung.ts | lesen UND schreiben Altfelder (channel_layouts, outlook_metrics(_formats), channel_active_metrics, hourly_metrics, show_outlook) |
| Go: model/trip.go:124, compare_preset.go:48/71, handler/config_merge.go, handler/compare_preset.go:326-345 | display_config generisch (map), einzig typisiert `OutlookEnabled` |

## Existing Patterns
- AST-Wächter: tests/test_mail_recipient_parity.py (`# doc-compliance-test`, Region per ast.walk, Selbstnachweis mit synthetischem Quelltext, Negativfall, Ausnahmen als Daten mit Begründung + EXPIRY).
- Kontext-Muster: docs/context/feat-3157-migration-was-steht-wo.md, fix-3242-validator-soll-auswahl.md.
- Read-Modify-Write mit Merge bei Schemaänderungen (CLAUDE.md, #102); Backup-Hook data_schema_backup.py.

## Dependencies
- Upstream: services/placements.py (read_placements, resolve_rows, metrics_at, resolve_outlook_reports, outlook_applies).
- Downstream: alle Renderer (Mail/Telegram/SMS/Premium-SMS), Validator-Endpoint, Validator-Soll-Hook, Editor-Speicherpfade im Frontend, Erstanlage (Go-PUT → Python).

## Existing Specs
- docs/specs/modules/feat_3122_was_steht_wo.md: Teil A Nr. 8 (:135-143, Altfeld-Liste Nachtrag 21.11.), AC-38, Affected Files B6.
- docs/specs/modules/feat_3157_migration_placements.md: :40/:141/:75/:146 verweisen Löschung an #3237.
- issue_448_validator_metrics_for_channel.md: Vertrag `source` (ohne placements-Entsprechung).

## Risks & Considerations
- Scope sehr groß (Backend-Löschung + Wächter + Frontend-Schreibpfade + Datenbereinigung) → Schnitt in Teil-Issues prüfen (Epic-Regel: eigene Issues statt Teilaufgaben).
- Erstanlage und Migrationsskript hängen am Altzweig: wegnehmen/einfrieren entscheiden.
- Frontend schreibt Altfelder weiter; Datenbereinigung vorher sinnlos (würden neu entstehen).
- `show_outlook` steuert noch Großwetterlage (#3155); Spec führt es als Altfeld, Klärung nötig.
- Validator-Endpoint-Feld `source` neu definieren.
- Validator-Soll-Hook bricht, wenn `_legacy_outlook_reports`/`_feld` entfallen; `orte_soll` liest Altfelder zuerst.
- Kanal-Parität (alle vier Kanäle) und Mandantentrennung bei Datenbereinigung (je Nutzer, Merge statt Replace).

## Analysis

### Type
Feature (Rückbau mit Verhaltensbruch nur für Abos ohne Tabelle). Paket: #3275 (B6b-0) + #3237 (B6b-1) in einem Durchlauf. Folge-Issues: #3276 (B6b-2 Frontend), #3277 (B6b-3 Daten/Modell); alle Sub-Issues von Epic #3122. Zuschnitt als Kommentar in #3237 (22.11.).

### Key Finding (gegen Spec-Annahme Nr. 8)
Neue Abos haben bis zum ersten Speichern der Karte KEINE `placements.rows`: Orte-Anlage schreibt nur `{version:1, outlook_reports}` (`internal/handler/compare_preset.go:314-345` `ausblickMarkeNeuanlage`, bewusst ohne rows), Trip-Anlage nichts. Lesepfad fällt auf `legacy_view` zurück (`channel_list_resolver.py:145-148`); Karte zeigt `placements_from_legacy` (`placements_view_service.py:136-155`); `erstanlage_begleitfelder` (`:104-130`, `api/routers/placements.py:57-65`, Go `internal/handler/placements.go:19`, `placements_erstanlage_3154_test.go:71`) setzt `show_stability=false` über den Altzweig. Ohne B6b-0 wäre Löschen eine Regression. Prod: alle 21 Abos haben rows → 0 Prod-Abos vom Lesepfad-Wechsel betroffen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/placements.py | MODIFY | NEU `placements_aus_grundauswahl` (Grundauswahl → rows + outlook_reports, ohne Altfelder); `placements_from_legacy`/`legacy_placements`/`_legacy_rows`/`_output_changes`/`_legacy_outlook_reports` löschen; `anlage_outlook_reports` prüfen |
| internal/handler/compare_preset.go, Trip-Anlage-Handler, internal/handler/placements.go (+Go-Tests) | MODIFY | Anlage (Trip + Orte) schreibt volle Tabelle, EINE Quelle = Python; `show_stability_off`-Begleitfeld entfällt; mitgeschickte placements bleiben |
| src/services/placements_view_service.py, api/routers/placements.py | MODIFY | `erstanlage_begleitfelder` weg; Karte ohne rows → `placements_aus_grundauswahl` |
| src/services/channel_list_resolver.py | MODIFY (großteils DELETE) | `legacy_view`, `legacy_lists`, `trip_channel_metrics`, `_trip_view`, `_compare_view`, `vm_lists`, `ALTBESTAND_UEBER_UMRECHNUNG` weg; ohne rows → Grundauswahl-Tabelle |
| src/app/models.py | MODIFY | `_cascade_source_for_channel` (:780-802), `get_metrics_for_channel` (:949-989), `cascade_source_for_channel` (:1031-1043) löschen; Loader/Serialisierung der Altfelder BLEIBT bis #3277 |
| src/output/renderers/channel_layout.py | MODIFY | `render_for_channel` ohne `dc.get_metrics_for_channel` (Aufrufer liefern Liste) |
| compare_outlook_metric_ids.py (:201-300), compare_metric_ids.py (:251, :387) | DELETE (Teile) | nur vom Resolver gerufen; `resolve_enabled_metrics(_report)` bleibt |
| api/routers/validator.py (:151-169, :574-593) | MODIFY | `source` neu = `"placements"`/`"grundauswahl"`, `metric_ids` aus `resolve_trip_view` |
| src/services/report_config_resolver.py (:150-182, :352, :449-460) | MODIFY | `_options_bisher`/`_legacy_outlook_reports`/`channel_active_metrics`-Lesestellen weg |
| src/services/validator_render_service.py (:480-490) | MODIFY | Vorschau `hourly_metrics` aus Tabelle |
| scripts/migrate_3157_placements.py | DELETE | nach Live-Migration entbehrlich |
| .claude/hooks/_soll_aus_konfiguration.py | MODIFY | Altzweige raus (:296-297, :488-501, :524, :656, :751-824, `orte_soll` :1019-1035 Tabelle-zuerst); ohne rows → Grundauswahl; #3273 beachten |
| tests/helpers/kanal_liste_orakel.py, test_3057_channel_list_resolver, test_3065_ausblick_stundenverlauf_resolver, test_einstellung_gleich_mail_trip_tabelle (`_adapter_gegen_orakel`), test_placements_umrechnung_altbestand, unit/test_compare_channel_metric_cascade, unit/test_trip_metric_cascade_single_source | DELETE/MODIFY | Differenz-Orakel, Alt-Kaskaden-Tests |
| test_channel_metric_matrix, test_sms_user_metric_order (:68/:481), integration/test_issue_448_validator_metrics_for_channel, test_ausblick_erbt_grundauswahl, test_compare_ausblick_erbt_grundauswahl, test_einstellung_gleich_mail_editor_standard/_orte, test_outlook_*, test_3156_renderer_nachzug_roh_einfach | MODIFY | auf Tabelle umschreiben |
| tests/test_altpfad_import_sperre.py | CREATE | AST-Wächter (Muster test_mail_recipient_parity.py, `# doc-compliance-test`, Selbstnachweis, Negativfall, Ausnahmen mit Begründung + EXPIRY) |
| AC-38-Test | CREATE | Ausgabe aller vier Kanäle gleich mit/ohne gesetzte Altfelder (Abo mit Tabelle) |
| docs/specs/modules/feat_3122_was_steht_wo.md, issue_448-Spec, docs/reference/api_contract.md | MODIFY | Nachtrag Erstanlage, `source`-Vertrag |

### Scope Assessment
- Files: ca. 22 Prod (inkl. Go) + ca. 15 Tests
- Estimated LoC: B6b-0 ca. +250; B6b-1 netto ca. −1500 bis −2000
- Risk Level: HIGH (zentraler Lesepfad aller vier Kanäle, Anlage Trip+Orte, Prüfwerkzeuge); gemildert, weil alle Prod-Abos rows tragen

### Technical Approach
1. B6b-0 zuerst: `placements_aus_grundauswahl` in Python als einzige Quelle; Go-Anlage (Trip + Orte) ruft sie beim Anlegen (Muster Go → Python wie bisher `erstanlage_begleitfelder`, unter Briefing-Sperre), speichert volle `placements`. Lesepfad ohne rows nutzt dieselbe Funktion.
2. Vor dem Löschen Schnappschuss (Golden) der Ausgaben Mail HTML/Text, Telegram, SMS, Premium-SMS für Tabellen-Abos; nach dem Löschen identisch (ersetzt das Orakel, Kanal-Parität).
3. Löschung Backend + Soll-Hook + Validator-Endpoint + Vorschau + report_config_resolver.
4. AST-Import-Sperre mit Erlaubnisliste (`placements.resolve_outlook_reports`, ggf. `report_config_resolver._channel_unresolved_count`, `resolve_hourly_metrics(None)` in comparison.py / email/compare_html.py).
5. `show_outlook` ist Altfeld (wirkt mit Tabelle nicht, report_config_resolver:144-147): in B6b-1 nur Lesestelle `_options_bisher` weg; Feld + Renderer-Parameter in #3277.

### Dependencies
- Upstream: placements.read_placements/resolve_rows/metrics_at/resolve_outlook_reports/outlook_applies; resolve_enabled_metrics(_report).
- Downstream: alle vier Renderer, Validator-Endpoint + Soll-Hook + Mail-Validatoren, Vorschau, Go-Anlage/PUT; Frontend schreibt Altfelder weiter (danach wirkungslos bis #3276).

### Open Questions
- [x] Schnitt → Sub-Issues #3275/#3276/#3277 angelegt (technischer Zuschnitt, keine PO-Frage).
- [x] show_outlook → Altfeld, Entfernen in #3277.
- [ ] Spec: Verhaltensbruch „neues Abo ohne Tabelle“ (bisher Assistenten-Ausblick-Metriken/-Formate, künftig Tabelle aus Grundauswahl) als bewusste Änderung benennen; Abgleich #3164 — Freigabe mit der Spec.
- [ ] Spec Known Limitation: bis #3276 speichern alte Editoren wirkungslos (zwei Bedienwege); #3276 direkt danach.
