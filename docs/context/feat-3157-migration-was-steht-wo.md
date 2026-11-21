# Context: feat-3157-migration-was-steht-wo

## Request Summary
Issue #3157 (Epic #3122, Scheibe #2795): Bestands-Abos (Trip und Orte) einmalig ins Tabellenformat `placements` überführen. Erst Probelauf gegen Prod-Daten mit Änderungsarten je Abo, dann AC-11 der Spec mit den Zahlen ergänzen und dem PO vorlegen, dann schreibende Migration (Merge, Pre-Snapshot, idempotent), danach Altpfad (Lese-Adapter, Differenz-Orakel) entfernen und per AST-Wächter sperren.

## Related Files
| File | Relevance |
|------|-----------|
| src/services/placements.py | Einzige Umrechnung: `placements_from_legacy` :398 (→ `LegacyConversion(placements, changes, show_stability_off)`), `legacy_placements` :388, `_legacy_outlook_reports` :333, `_legacy_rows` :362; Änderungsarten :48-63 (13 Stück), Klassifikation `_output_changes` :505, `_stelle_changes` :460, `_regel_changes` :487, `_art_*` :432-450 |
| src/services/channel_list_resolver.py | Lese-Adapter; `ALTBESTAND_UEBER_UMRECHNUNG = False` :39, gelesen :149/:155 in `resolve_channel_lists` :114; `legacy_view` :190, `legacy_lists` :343, `trip_channel_metrics` :360, `_trip_view` :424, `_compare_view` :495, `_abo_schalter` :170 |
| src/services/placements_view_service.py | `erstanlage_begleitfelder` :104 (show_stability beim ersten Speichern) |
| src/app/models.py | `_cascade_source_for_channel` :780, `cascade_source_for_channel` :1031, `get_metrics_for_channel` :949, `placements` :890 |
| src/app/loader.py | placements laden :611/:631/:1040, serialisieren :1756/:2011, Merge :2222 |
| src/output/renderers/compare_metric_ids.py | `resolve_channel_enabled_metrics` :251, `resolve_channel_layout_rows` :387, `resolve_enabled_metrics(_report)` :195/:170 |
| src/output/renderers/compare_outlook_metric_ids.py | `resolve_*_outlook_*` :80-300 (nur von channel_list_resolver gerufen; Namensgleichheit mit neuem `placements.resolve_outlook_reports` :252 → Erlaubnisliste im Wächter) |
| src/services/report_config_resolver.py | `_channel_unresolved_count` :449 (Sonderfall, Diagnose) |
| api/routers/validator.py | ruft `cascade_source_for_channel` :169 und `get_metrics_for_channel` :592 (Produktionsaufrufer des Altpfads) |
| src/output/renderers/channel_layout.py:133 | ruft `get_metrics_for_channel` |
| comparison.py:267, email/compare_html.py:1927 | `resolve_hourly_metrics(None)` – Vorgabeliste, darf bleiben |
| tests/helpers/kanal_liste_orakel.py + 4 Tests | Differenz-Orakel, zu löschen (Liste im Issue-Kommentar 20.11.) |
| Validator-Soll `_soll_aus_konfiguration.py` (Hooks) | liest Spalten/Formen nur aus Altfeldern (#3218), importiert privat `_legacy_outlook_reports` – bricht nach B6 |
| internal/store/briefing_placements.go, internal/handler/placements.go, api/routers/placements.py | Speicherweg der Tabelle (Go RMW auf `display_config.placements`) |
| scripts/migrate_2792_profil_ampel.py, scripts/migrate_3196_trip_tempo.py | Muster: `--root --backup-dir --execute`, Probelauf ohne `--execute`, tar.gz-Sicherung je Nutzer, `file_lock.exclusive_lock`, atomares Schreiben |

## Existing Patterns
- Migrationsskripte `scripts/migrate_*.py` mit Probelauf-Default, Sicherung je Nutzer, Sperre, Merge (ADR-0101/ADR-0083), Tests `tests/test_<N>_migration_*.py`.
- Datenablage: `data/users/<uid>/briefings/<id>.json`, Orte über `kind == "vergleich"`, Sperrdatei `<id>.json.lock`.
- AST-Import-Sperre: `tests/test_mail_recipient_parity.py:582-594`.

## Dependencies
- Upstream: `placements_from_legacy`, `channel_list_resolver.legacy_lists/grundauswahl`, Metrik-Katalog.
- Downstream: alle Renderer über `resolve_channel_lists` (outlook.py:663, helpers.py:333, placements_view_service :139/:355, report_config_resolver :211/:329/:338, notification_service :652), Validator-Router, Mail-Validatoren.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` – Teil A Nr. 8 (:135-143), AC-11 (:221), AC-13 (:227), AC-38 (:304), Affected Files (:340)
- `docs/adr/0124-was-steht-wo-eine-tabelle.md` Folgepflichten :55-58, Nachtrag Nr. 4 :78

## Risks & Considerations
- **Spec ↔ Issue:** Spec Nr. 8 lässt die Migration nach dem Schreiben von `placements` die umgerechneten Altfelder entfernen; Issue sagt „Merge, nie Ersetzen“. Vereinbar: Merge betrifft alle übrigen Felder (bytegleich), Altfelder erst entfernen, wenn kein Leser mehr existiert; Sicherung vorher.
- **Änderungsarten über AC-11 hinaus:** Code kennt 13 Arten (Spec nennt 4), dazu drei Fälle aus #3164 Abschnitt A ohne eigene Art (landen ggf. in `unerklaert`): Telegram-Ausblick bei `show_outlook:false`; HTML-Mail „Wetterlage“ bei `outlook_metrics: []`; Trip ohne `report_config` mit `multi_day_trend_reports: []`. → PO-Vorlage mit echten Zahlen aus dem Probelauf (Produktentscheidung).
- **Produktionsaufrufer des Altpfads** außerhalb des Adapters (validator.py, channel_layout.py) müssen vor der Import-Sperre umgestellt werden.
- **Validator** (#3218) muss vor dem Entfernen der Altfelder auf `placements` umgestellt sein.
- **Gleichzeitige Schreiber:** Go-PUT und Migration auf derselben Datei → Sperrdatei nutzen.
- Prod-Probelauf nur lesend als Dienstnutzer (`sudo -n -u claude-gregor`), Ausgabe nicht weltlesbar.
- Zwei Nutzer getrennt halten (AC-13), Idempotenz, `show_stability` bei `show_outlook:false` mitschreiben.
- Umfang groß → in Teilschritte schneiden (Probelauf+Vorlage / Migration / Rückbau Altpfad).

## Analysis

### Type
Feature (Datenmigration, Teil von Epic #3122, B6)

### Probelauf Prod (lesend, 2026-11-21, `placements_from_legacy` je Abo als `claude-gregor`)
- 21 Abos: 1 Orte-Abo hat schon `placements`, 20 alt (14 Trips, 6 Orte), 0 Lade-/Umrechnungsfehler, 0 `unerklaert`, kein `show_stability_off`.
- `nur_text_folgt_html`: 13 Trips (47 Einträge).
- `reihenfolge_wie_sms`: 1 Trip (2 Einträge) + 3 Orte-Abos (10 Einträge).
- Alle anderen Arten (inkl. `auswertungen_gekoppelt`, `ausserhalb_grundauswahl`, `morgen_folgt_abend`, `premium_folgt_sms`, `ohne_spalte_folgt_grundauswahl`) kommen in Prod nicht vor.
- Probe-Skript lag nur im Scratchpad (Aufruf: `sudo -n -u claude-gregor GZ_DATA_DIR=/var/lib/gregor <repo>/.venv/bin/python - < probe.py`; als Dienstnutzer im Worktree NIE `uv run` → legt `.venv`/`__pycache__` mit fremdem Besitzer an, danach aufräumen).

### Schnitt (Tech-Lead-Entscheidung)
- **Dieser Workflow (#3157, Schritte 1–3):** Migrationsskript + Tests + AC-11-Ergänzung + Prod-Lauf. Altfelder bleiben in den Daten stehen (Frontend liest sie noch: `types.ts`, `mailInhaltZustand.ts:31` `show_outlook`, `cockpitHelpers568.ts:60` `channel_layouts`).
- **Kind-Issue (Schritt 4):** Validator-Soll auf `placements` (#3218 Voraussetzung), `api/routers/validator.py` :169/:592 + `channel_layout.py:133` umstellen, Altpfad + Orakel + 4 Tests löschen, AST-Wächter. Danach erst Entfernen der Altfelder aus den Daten (Frontend vorher umstellen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| scripts/migrate_3157_placements.py | CREATE | Probelauf (Bericht je Abo mit Änderungsarten) / `--execute`; Muster migrate_3196 (`schreiben` aus migrate_2792: Sperre, atomar, Inhaltsvergleich), tar.gz-Sicherung je Nutzer, Merge nur `display_config.placements` (+ `report_config.show_stability=false` bei `show_stability_off`), idempotent, **fail-closed bei `unerklaert`** |
| tests/test_3157_migration_placements.py | CREATE | AC-13: zwei Nutzer, Sicherung, Dateivergleich (nur placements neu), zweiter Lauf ändert nichts, Ausgabe = Umrechnung; AC-12-Fall `show_outlook:false` |
| docs/specs/modules/feat_3122_was_steht_wo.md | MODIFY | AC-11 um Prod-Zahlen; Nr. 8: Altfelder-Entfernung verschoben bis kein Leser mehr existiert |
| docs/reference/operations_playbook.md (o. ä.) | MODIFY | Migrationsaufruf nach Deploy |

### Scope Assessment
- Files: 3–4 · LoC ca. +500 (Skript ~250, Test ~250) · Risk: MEDIUM (schreibt Prod-Daten; abgesichert durch Sicherung, Merge, Probelauf, Idempotenz)

### Technical Approach
Skript ruft je Abo dieselben Lade-Wege wie die Tabellen-Ansicht (`placements_view_service._trip_abo/_orte_abo` bzw. deren Datenquellen) und `placements_from_legacy`; schreibt per RMW auf dem Roh-JSON (nicht über Modelle serialisieren → übrige Felder bytegleich). Ausführung auf Prod nach dem Deploy als `claude-gregor`.

### Dependencies
`services.placements.placements_from_legacy`, `read_placements`; `scripts/migrate_2792_profil_ampel.schreiben`; `file_lock`. Go-Seite liest Altfelder nicht (nur Kommentare/Tests), schreibt `placements` per RMW unter derselben Sperrdatei.

### Open Questions
- PO-Freigabe der zwei sichtbaren Änderungsarten erfolgt mit der Spec-Freigabe (AC-11), nicht separat.
