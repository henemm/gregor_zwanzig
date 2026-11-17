# Context: feat-3096-mail-resolver

## Request Summary
Issue #3096 (Phase 3a von Epic #3058 / #3047): Die E-Mail-Renderer für Trip (HTML + Klartext) und Orte-Vergleich (HTML + Klartext) lesen Spalten, Reihenfolge und Darstellung direkt aus dem gemeinsamen Resolver `resolve_channel_lists` (ADR-0121). Die Mail-Altpfade `resolve_metric_col_order`, die Sonderpfade in `_visible_hour_metrics` und `HOURLY_DEFAULT_METRIC_IDS` als zweite Quelle werden gelöscht. Die zugestellte Mail bleibt in allen Prüfkatalog-Fällen gleich.

## Related Files
| File | Relevance |
|------|-----------|
| src/services/channel_list_resolver.py | Resolver. `ChannelRow` :29 (metric_id, enabled, format raw/simplified/None, order), `MailViewModel` :40 (email/telegram/sms/premium_sms/outlook/hourly, layout_channels), `resolve_channel_lists(dc, "trip"\|"compare", report_type)` :69, `trip_channel_metrics` :82 (ADR-0050-Kaskade), `_compare_view` :212, hourly :235/244 über `resolve_hourly_metric_ids` |
| src/output/renderers/email/helpers.py:305 | `resolve_metric_col_order(dc)`: enabled + `selectable` aus `dc.metrics` → col_key-Liste. Zu löschen |
| src/output/renderers/email/html.py:51,872 · plain.py:42,197 | Trip-Mail-Aufrufer von `resolve_metric_col_order` |
| src/output/renderers/trip_report.py:141 (Telegram :293, SMS :359) | Trip-Kette: `dc.get_metrics_for_channel("email", report_type)` → dc wird auf E-Mail-Auswahl kollabiert, bevor Renderer laufen. Resolver-Werte kommen also schon an, aber als MetricConfig-Liste |
| src/app/models.py:979 | `get_metrics_for_channel` → `trip_channel_metrics` (Adapter seit #3057) |
| src/output/renderers/email/compare_html.py:1078 | `_visible_hour_metrics(hourly_metrics, zeilen)`: `None` → `HOURLY_DEFAULT_METRIC_IDS` (:1102-1107), sonst Filter in Reihenfolge. Aufrufer :1122, :1192, :1615; comparison.py:43/:369 (Klartext) |
| src/output/renderers/compare_hourly_metric_ids.py:114,271 | `HOURLY_DEFAULT_METRIC_IDS`; :271 Rückfall in `_schnitt_mit_grundauswahl` — speist den Resolver-`hourly` und bleibt die eine Quelle |
| src/output/renderers/compare_metric_catalog.py:73,443 | `hourlyDefault` fürs Frontend (Katalog, keine zweite Renderer-Quelle) |
| src/services/report_config_resolver.py:257-340 | `resolve_compare_render_options`: nutzt `view` nur für `channel_rows` der Layout-Kanäle; `hourly_metrics` :278/:307 noch separat über `resolve_hourly_metrics` statt `view.hourly`; Outlook über `resolve_compare_outlook_*` |
| src/services/scheduler_dispatch_service.py:983 · compare_preview_service.py:161 | Orte-Kette Versand / Vorschau → `resolve_compare_render_options` |

## Existing Patterns
- Adapter-Prinzip ADR-0121 Nr. 8: bestehende Funktionen lesen aus dem Resolver, Signaturen bleiben.
- None-Vertrag (Nachtrag 2b Nr. 4): `None` = Renderer-Vorgabemenge, `()` = Block entfällt.
- Trip und Orte teilen Code (ADR-0097); keine neue Regel im Renderer.

## Dependencies
- Upstream: `channel_list_resolver`, `compare_hourly_metric_ids.resolve_hourly_metric_ids`, Metrik-Katalog `get_metric(...).selectable`.
- Downstream: Trip-Mail (html/plain), Orte-Mail (compare_html, comparison.py Klartext), Vorschau (`compare_preview_service`), Alarm-Mail über dieselben Renderer.

## Tests, die das Verhalten festhalten
- Golden-Mails: `tests/fixtures/einstellung_gleich_mail/{trip_altbestand_golden.*, orte_altbestand.golden.*, orte_altbestand_ohne_grundauswahl.golden.*}`.
- Prüfkatalog: `tests/tdd/test_einstellung_gleich_mail_{trip,orte,fallliste,validatoren,runde7_katalog}.py`, `test_einstellung_gleich_auslieferung.py`, `test_compare_einstellung_auslieferung_kette.py`, `test_compare_alarm_einstellung_auslieferung_kette.py`, `tests/test_erwartungsdatei_drift_einstellung_gleich_auslieferung.py`.
- Nutzen die Altfunktionen direkt (müssen umgestellt werden): `test_einstellung_gleich_mail_editor_standard.py:40,43,113,141`, `test_channel_metric_matrix.py:121,248-256,569,715`, `tests/test_resolution_loss_guard.py:702,852` (Allowlist `helpers.py::resolve_metric_col_order`), `test_einstellung_gleich_mail_orte.py:104/594` (Soll-Orakel mit `HOURLY_DEFAULT_METRIC_IDS`), `tests/helpers/metrik_listen_scan.py:346`; Erwähnungen in `test_trip_renderer_characterization.py:144`, `test_compare_preview_hourly_parity.py`, `test_compare_metric_order_and_wind_direction.py:169`, `unit/test_compare_hourly_legacy_selection_bestandsschutz.py`.
- Differenztest-Orakel (neu = alt): `test_3057_channel_list_resolver.py`, `test_3065_ausblick_stundenverlauf_resolver.py` — Löschung erst in #3102.

## Existing Specs
- `docs/specs/modules/feat_3057_kanal_liste_resolver.md`, `docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md`, ADR `docs/adr/0121-kanonische-kanal-liste.md`.

## Risks & Considerations
- Golden-Mails müssen byte-gleich bleiben (Trip und Orte, HTML und Klartext).
- `resolve_metric_col_order` filtert über `selectable` aus dem Katalog; der Resolver tut das heute nicht → Gleichheit muss im neuen Pfad erhalten bleiben.
- Format: Trip-Format kommt heute aus `MetricConfig` (format_mode/use_friendly_format), nicht aus `ChannelRow.format`. Standard ohne Angabe unterscheidet sich (Trip Katalog, Orte Roh) — Produktfrage, ob vereinheitlichen oder beibehalten.
- Orte-hourly wird doppelt berechnet (`report_config_resolver` :278/:307 und Resolver :235/244) → auf `view.hourly` umstellen, dann entfällt der None-Sonderpfad im Renderer nur, wenn der Resolver nie `None` für „nie eingestellt“ liefert, sondern die konkrete Vorgabeliste. Sonst muss die Vorgabe genau einmal (in `compare_hourly_metric_ids`) aufgelöst werden.
- `hourlyDefault` im Katalog fürs Frontend bleibt (Editor-Anzeige), ist keine zweite Renderer-Quelle.
- Abgrenzung: Telegram/SMS/Premium-SMS (#3098-#3100), Vokabular (#3101), Migration/Orakel/Import-Sperre (#3102), Roh/Einfach Stundenverlauf (#3097) nicht hier.

## Analysis

### Type
Feature (Umbau ohne sichtbare Änderung; Mail bleibt byte-gleich)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/trip_report.py | MODIFY | `resolve_channel_lists(_dc_uncollapsed, "trip", report_type)` einmal VOR der Kollabierung (:141), `view.email` an `render_email` durchreichen (analog `outlook_metrics`) |
| src/output/renderers/email/__init__.py | MODIFY | neuer Parameter (E-Mail-Zeilen) an `render_html`/`render_plain` durchreichen |
| src/output/renderers/email/helpers.py | MODIFY | `resolve_metric_col_order` löschen; Adapter `email_col_order(rows)`: metric_id → `get_metric().col_key`, Folge erhalten, `enabled` + `selectable` filtern, KeyError überspringen |
| src/output/renderers/email/html.py :872 · plain.py :197 | MODIFY | Spaltenfolge aus Adapter; ohne Parameter (nur direkte Testaufrufe) einziger Rückfall `resolve_channel_lists(dc, "trip", report_type).email` |
| src/output/renderers/compare_hourly_metric_ids.py | MODIFY | `_standard_aus_grundauswahl` liefert statt `None` die konkrete Liste `HOURLY_DEFAULT_METRIC_IDS` (einzige Quelle bleibt hier) |
| src/output/renderers/email/compare_html.py | MODIFY | `_visible_hour_metrics` ohne None-Zweig, Import `HOURLY_DEFAULT_METRIC_IDS` (:38) weg; `_should_merge_wind_dir` ohne `is None`; Signatur `list[str]` |
| src/output/renderers/comparison.py :369 | MODIFY (formal) | Klartext ruft denselben `_visible_hour_metrics` |
| src/services/report_config_resolver.py :278/:307 | MODIFY | `hourly_metrics` aus `view.hourly` (→ `dp_field` genau einmal hier), statt zweiter Auflösung über `resolve_hourly_metrics` |
| src/services/validator_render_service.py :573 | MODIFY | `hourly_metrics` vor `render_compare_html` auflösen (None → dieselben neun Vorgabespalten wie bisher) |
| src/services/channel_list_resolver.py | MODIFY | Docstrings (`MailViewModel.hourly` für Orte nie `None`) |
| docs/adr/0121-kanonische-kanal-liste.md | MODIFY | kurzer Nachtrag zu Nachtrag 2b Nr. 4: Orte-`hourly` ist nie `None`; `None` nur noch Trip-`hourly` und kanalweise „kein Filter“ |
| tests: test_einstellung_gleich_mail_editor_standard.py (:40,43,113,141), test_channel_metric_matrix.py (:121,248-256,569,715), test_einstellung_gleich_mail_orte.py (:104,594), tests/helpers/metrik_listen_scan.py:346, tests/test_resolution_loss_guard.py (:702,852 Allowlist auf neuen Adapter) | MODIFY | auf Resolver/Adapter umstellen |
| tests (nur Kommentare): test_compare_preview_hourly_parity.py, test_compare_metric_order_and_wind_direction.py:169, unit/test_compare_hourly_legacy_selection_bestandsschutz.py | MODIFY | Textkorrektur |

Unverändert gültig: Hook-Helfer `_soll_aus_konfiguration.py` (:62/:525) und Katalog `hourlyDefault` (compare_metric_catalog.py:443, Editor-Anzeige) importieren die Konstante aus ihrer einzigen Quelle.

### Scope Assessment
- Files: ~10 src, ~8 tests, 1 ADR
- Estimated LoC: src ca. +60/-60, tests ca. +150/-80
- Risk Level: MEDIUM (zentrale Mail-Pfade, aber eng bewacht durch Golden-Mails und Prüfkatalog)

### Technical Approach
- Trip: Alle produktiven Wege laufen über `TripReportFormatter.format_email` → `render_email` (auch `preview_service.py:370`); Alarm-Mails nutzen `alert/render.py`, nicht diese Renderer. Resolver NICHT auf dem kollabierten dc aufrufen (enabled=True erzwungen, Layouts noch gesetzt → Idempotenz unbewiesen), sondern einmal auf dem unkollabierten dc. morning/evening: identisch zur Kollabierung (beide über `trip_channel_metrics`); übrige report_types: Global-Zweig = nur enabled, wie heute.
- `selectable`-Filter bleibt im Adapter (Resolver kennt ihn nicht und bleibt unverändert).
- Orte: Vorgabemenge wird genau einmal in `compare_hourly_metric_ids` aufgelöst, Renderer bekommt nie `None`. Auch der zweite None-Fall (Grundauswahl ohne Stundengröße) lieferte bisher die neun Vorgabespalten → gleich. `wind_direction` (Merge-only) steht nicht in der Vorgabeliste → `_should_merge_wind_dir` bleibt False.
- Format-Standard ohne Angabe (Trip Katalog, Orte Roh): **beibehalten** — Vereinheitlichung würde Golden-Mails ändern und widerspricht dem Auftrag „Mail bleibt gleich“; wäre ein eigenes Produkt-Issue.
- Reihenfolge: 1) Orte (`_standard_aus_grundauswahl`, report_config_resolver, Validator-Aufruf, Renderer-None weg), 2) Trip (Durchreichen + Adapter), 3) Löschung `resolve_metric_col_order`, 4) Tests/Allowlist, 5) ADR-Nachtrag. Golden + Prüfkatalog nach jedem Schritt grün.

### Dependencies
Upstream: `channel_list_resolver`, `resolve_hourly_metric_ids`, Katalog `get_metric(...).selectable/col_key/dp_field`. Downstream: Trip-Mail HTML/Klartext, Orte-Mail HTML/Klartext, Vorschau (`compare_preview_service`, `preview_service`), Validator-Vorschau (`validator_render_service`).

### Open Questions
- keine (Format-Standard technisch entschieden: beibehalten, siehe oben)

## TDD RED (Phase 5) — Hinweise für /50-implement
- Neue Testdatei `tests/tdd/test_3096_mail_resolver.py`: 10 rot, 6 grün (Regression).
- Parametername für die E-Mail-Zeilen ist durch die Tests festgelegt: `email_rows` (an `render_email`, `render_html`, `render_plain`; heute würde er still von `**_ignored` geschluckt).
- `test_trip_mail_folgt_resolver_email_liste[update]`: ein report_type außer morning/evening mit eigener E-Mail-Liste folgt künftig der Resolver-E-Mail-Liste (AC-2). Produktiv laufen nur morning/evening, Golden-Mails bleiben gleich.
- Die Bestands-Tests, die `resolve_metric_col_order` importieren (`test_channel_metric_matrix.py`, `test_einstellung_gleich_mail_editor_standard.py`, `test_trip_renderer_characterization.py`, `test_resolution_loss_guard.py`) und das `HOURLY_DEFAULT_METRIC_IDS`-Orakel in `test_einstellung_gleich_mail_orte.py` stellt der Developer in GREEN auf `email_col_order`/Resolver um (Test Plan der Spec).
- Validator-Vorschau (`validator_render_service.render_compare_email_preview`) muss `hourly_metrics` vor dem Render auflösen, sonst TypeError nach Wegfall des None-Pfads.
