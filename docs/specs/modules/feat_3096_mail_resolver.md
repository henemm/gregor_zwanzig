---
entity_id: feat_3096_mail_resolver
type: refactor
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: feat-3096-mail-resolver
tags: [epic-3058, phase-3a, epic-3047, resolver, kanal-liste, email, mail-altpfade]
---

# E-Mail (Trip und Orte) liest direkt aus dem Resolver, Mail-Altpfade entfernen (Phase 3a von #3047)

## Approval

- [ ] Approved

## Purpose

Die E-Mail-Renderer für Trip und Orte-Vergleich (HTML und Klartext) beziehen Spalten, Reihenfolge und Stundenverlauf-Vorgabe künftig aus dem gemeinsamen Resolver `resolve_channel_lists` (ADR-0121). Die Mail-Altpfade (`resolve_metric_col_order`, der `None`-Sonderpfad in `_visible_hour_metrics`, `HOURLY_DEFAULT_METRIC_IDS` als zweite Quelle im Renderer) werden gelöscht. Morgen-/Abendbericht und Orte-Mail bleiben für den Nutzer unverändert. Einzige gewollte sichtbare Änderung (PO-Entscheidung 2026-11-17): Update- und Alarm-Mails eines Trips folgen ebenfalls der E-Mail-Auswahl des Nutzers (bisher Grundauswahl).

## Source

- **File:** `src/output/renderers/email/helpers.py`, `src/output/renderers/email/compare_html.py`, `src/output/renderers/trip_report.py`
- **Identifier:** `resolve_metric_col_order` (entfällt, ersetzt durch Adapter `email_col_order`), `_visible_hour_metrics`, `TripReportFormatter.format_email`

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/output/renderers/`, `src/services/`). Kein Frontend, keine Go-API. Katalog-Feld `hourlyDefault` im Frontend bleibt (Editor-Anzeige, keine zweite Renderer-Quelle).
>
> **Trip/Orte-Teilung:** Weiter ein Resolver mit `surface="trip"|"compare"`; keine neue Regel im Renderer, kein Pendant-Paar (ADR-0097).
>
> **Mandantentrennung:** Die Änderung bewegt keine neuen Nutzerdaten, aber die Spaltenfolge wird je Nutzer aus dessen Konfiguration abgeleitet; ein Zwei-Nutzer-Test (AC-6) belegt, dass keine Auswahl in die Mail eines anderen Nutzers wandert. `user_id` kommt wie bisher aus dem Auth-Kontext, kein Fallback auf `"default"`.
>
> **Kanäle:** Betroffen ist nur die E-Mail (HTML und Klartext). Telegram, SMS und Premium-SMS bleiben unverändert (ADR-0095; eigene Schnitte #3098 bis #3100).

## Scope

Phase 3a von #3047 (Epic #3058). Die E-Mail-Renderer für Trip (HTML und Klartext) und Orte-Vergleich (HTML und Klartext) beziehen Spaltenauswahl, Reihenfolge und Stundenverlauf-Vorgabe aus `resolve_channel_lists` (ADR-0121). Gelöscht werden `resolve_metric_col_order`, der `None`-Sonderpfad in `_visible_hour_metrics` und die zweite Auflösung der Stundenverlauf-Vorgabe im Renderer; `HOURLY_DEFAULT_METRIC_IDS` bleibt nur in `compare_hourly_metric_ids` als einzige Quelle. Die zugestellte Mail bleibt in allen Prüfkatalog-Fällen byte-gleich; Update-/Alarm-Mails mit eigener E-Mail-Auswahl folgen dieser Auswahl (PO-Entscheidung 2026-11-17, siehe unten).

## Estimated Scope

- **LoC:** src ca. +60/-60, Tests ca. +150/-80, ADR-Nachtrag klein
- **Files:** ca. 10 src, ca. 8 Tests, 1 ADR
- **Effort:** medium (Risiko MEDIUM: zentrale Mail-Pfade, aber eng bewacht durch Golden-Mails und Prüfkatalog)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_channel_lists`, `MailViewModel`, `ChannelRow` (`src/services/channel_list_resolver.py`) | module | Einzige Quelle für E-Mail-Zeilen (Trip) und `hourly` (Orte); Resolver selbst bleibt bis auf Docstrings unverändert |
| `trip_channel_metrics`, `get_metrics_for_channel` (`src/app/models.py`) | function | ADR-0050-Kaskade hinter dem Trip-Resolver; Kollabierung in `trip_report.py` bleibt für Telegram/SMS |
| `resolve_hourly_metric_ids`, `_standard_aus_grundauswahl`, `HOURLY_DEFAULT_METRIC_IDS` (`compare_hourly_metric_ids.py`) | function/const | Einzige Quelle der Stundenverlauf-Vorgabe; liefert künftig die konkrete Liste statt `None` |
| `get_metric(...)` mit `col_key`, `selectable`, `dp_field` (`app/metric_catalog.py`) | function | Adapter `email_col_order` filtert `selectable` und bildet auf `col_key` ab |
| `resolve_compare_render_options` (`report_config_resolver.py`) | function | Orte-Kette Versand und Vorschau; liest `hourly` aus `view.hourly` |
| `validator_render_service.py` | module | Validator-Vorschau löst `hourly_metrics` vor dem Rendern auf |
| Golden-Mails `tests/fixtures/einstellung_gleich_mail/*`, Prüfkatalog `test_einstellung_gleich_mail_*` | tests | Messlatte, bleibt unverändert grün |
| ADR-0121, ADR-0097, ADR-0095 | ADR | Entscheidungsgrundlage; ADR-0121 bekommt kurzen Nachtrag |

## Implementation Details

Reihenfolge, nach jedem Schritt Golden-Mails und Prüfkatalog grün:

1. **Orte:** `_standard_aus_grundauswahl` liefert statt `None` die konkrete Liste `HOURLY_DEFAULT_METRIC_IDS` (einzige Quelle bleibt in `compare_hourly_metric_ids.py`). Auch der zweite None-Fall (Grundauswahl ohne Stundengröße) lieferte bisher dieselben neun Vorgabespalten, also gleich. `resolve_compare_render_options` (:278/:307) nimmt `hourly_metrics` aus `view.hourly` (`dp_field`-Abbildung genau einmal dort) statt aus zweiter Auflösung über `resolve_hourly_metrics`. `validator_render_service.py` (:573) löst `hourly_metrics` vor `render_compare_html` auf. In `compare_html.py` verliert `_visible_hour_metrics` den `None`-Zweig (Signatur `list[str]`), der Import `HOURLY_DEFAULT_METRIC_IDS` entfällt, `_should_merge_wind_dir` ohne `is None`. `wind_direction` (Merge-only) steht nicht in der Vorgabeliste, bleibt also unverändert nicht verschmolzen. Klartext (`comparison.py`) ruft denselben `_visible_hour_metrics`.
2. **Trip:** `trip_report.py` ruft `resolve_channel_lists(dc_unkollabiert, "trip", report_type)` einmal VOR der Kollabierung (:141) auf (nicht auf dem kollabierten dc: `enabled=True` erzwungen, Idempotenz unbewiesen) und reicht `view.email` über `render_email` an `render_html`/`render_plain` durch (analog `outlook_metrics`). morning/evening verhalten sich identisch zur Kollabierung (beide über `trip_channel_metrics`), übrige `report_type` (Update, Alarm): Die Kaskade `trip_channel_metrics` wendet die E-Mail-Auswahl auch dort an; die Kollabierung läuft daher für jeden `report_type`. Ohne Kanal-Ebene bleibt es wie heute die Grundauswahl (nur `enabled`).
3. **Adapter:** `email_col_order(rows)` in `helpers.py`: `metric_id` nach `get_metric().col_key`, Folge erhalten, `enabled` und `selectable` filtern (Resolver kennt `selectable` nicht, bleibt unverändert), `KeyError` überspringen. `html.py` (:872) und `plain.py` (:197) nutzen ihn; nur ohne Parameter (direkte Testaufrufe) gilt als einziger Rückfall `resolve_channel_lists(dc, "trip", report_type).email`.
4. **Löschung:** `resolve_metric_col_order` entfällt samt Aufrufern.
5. **Tests und ADR:** Tests und Allowlist umstellen; ADR-0121 Nachtrag.

### PO-Entscheidung 2026-11-17: Update- und Alarm-Mail folgen der E-Mail-Auswahl

Der Adversary fand: Update-/Alarm-Mails zeigten bisher die Grundauswahl und ignorierten die E-Mail-Kanal-Auswahl; der Resolver liefert für jeden `report_type` die E-Mail-Auswahl. Der PO hat entschieden, dass die E-Mail-Auswahl überall gilt (einheitlich mit Morgen-/Abendbericht). Trips ohne eigene E-Mail-Auswahl sind unverändert. Nachweis: AC-2 (`update`, `alert`).

**Nachbefund Fix-Loop:** In Produktion erreichen `update`/`alert` `format_email` nicht mehr (zugestellte Alarm-Mails laufen seit #921 über `output/renderers/alert/`; Vorschau und Handversand erlauben nur morning/evening). Die Angleichung wirkt daher nur im CLI-/Direktpfad und ist für den Nutzer derzeit nicht sichtbar. Ob der eigene Alarm-Renderer der E-Mail-Auswahl folgen soll, ist nicht Teil von #3096 (Folge-Issue).

**F001 (Adversary):** Der `selectable`-Filter im Adapter `email_col_order` ist eine dritte, am Mail-Ergebnis redundante Sperre (Kaskade und Zeilenbildung filtern bereits). Er bleibt bewusst (Schritt 3 verlangt ihn; Schutz für künftige Aufrufer), Nachweis per Adapter-Unittest; die Sperre am Mail-Ergebnis ist mit CAPE-Daten belegt (`test_trip_mail_nicht_auswaehlbare_metrik_mit_daten_keine_spalte`).

### Designentscheidung: Format-Standard ohne Angabe bleibt

Ohne Format-Angabe nutzt Trip heute Katalog-Darstellung (aus `MetricConfig`: `format_mode`/`use_friendly_format`), Orte Roh. Das wird **bewusst beibehalten**. Begründung: Eine Vereinheitlichung würde die Golden-Mails ändern und widerspricht dem Auftrag „zugestellte Mail bleibt gleich"; sie ist eine Produktentscheidung mit sichtbarer Wirkung. Falls gewünscht, eigenes Folge-Issue, ausdrücklich außerhalb dieses Scopes.

## Expected Behavior

- **Input:** `display_config` eines Trips oder Orts-Vergleichs, `report_type`.
- **Output:** Trip-Mail (morning/evening) und Orte-Mail (HTML und Klartext) byte-gleich zum Stand vor der Änderung; Update-/Alarm-Mail folgt der E-Mail-Auswahl; Spaltenfolge und Stundenverlauf stammen aus dem Resolver.
- **Side effects:** keine; Resolver ist rein lesend, Eingabe wird nicht verändert.

## Acceptance Criteria

- **AC-1:** Given Trip- und Orte-Konfigurationen aus den Golden-Fixtures und allen Prüfkatalog-Fällen / When die E-Mail (HTML und Klartext) nach der Umstellung gerendert und zugestellt wird / Then ist sie Zeichen für Zeichen gleich den Golden-Mails, und die Fallliste-Tests laufen unverändert grün.
  - Test: `test_einstellung_gleich_mail_{trip,orte,fallliste,validatoren,runde7_katalog}.py`, `test_einstellung_gleich_auslieferung.py`, Ketten-Tests Orte (Versand und Alarm) einzeln, Golden-Dateien unverändert; Staging-Validatoren `briefing_mail_validator.py` und `email_spec_validator.py` gegen echt zugestellte Mail.

- **AC-2:** Given ein Trip mit enger E-Mail-Kanal-Liste, abgewählten Metriken und einer nicht auswählbaren Metrik im Katalog / When die Trip-Mail gerendert wird / Then folgt die Spaltenfolge der Resolver-E-Mail-Liste (Reihenfolge, nur aktive Metriken) und die nicht auswählbare Metrik erscheint nicht als Spalte.
  - Test: Rendern der Trip-Mail über `TripReportFormatter.format_email` (HTML und Klartext) und Prüfung der Spaltenköpfe im Ergebnis; Fälle morning, evening und ein weiterer `report_type`; Abgleich gegen Soll-Folge aus Resolver plus `selectable`-Filter.

- **AC-3:** Given ein Orts-Vergleich ohne eigene Stundenverlauf-Auswahl und ohne Grundauswahl, sowie einer mit Grundauswahl ohne Stundengröße / When die Orte-Mail (HTML und Klartext) gerendert wird / Then zeigt der Stundenverlauf dieselben neun Vorgabespalten wie bisher, und die Vorgabe wird nur an einer Stelle (`compare_hourly_metric_ids`) aufgelöst.
  - Test: Rendern der Orte-Mail ohne Einstellung, Spaltenköpfe gleich der Vorgabeliste und gleich Golden `orte_altbestand_ohne_grundauswahl`; Lesetest, dass der Renderer nie `None` bekommt, geprüft am Mail-Ergebnis mit direktem Aufruf der Render-Funktion mit konkreter Liste.

- **AC-4:** Given der Code nach der Umstellung / When nach dem Altpfad gesucht wird / Then existiert `resolve_metric_col_order` nicht mehr, `_visible_hour_metrics` kennt keinen `None`-Sonderpfad, und der Renderer führt keine zweite Vorgabeliste für den Stundenverlauf.
  - Test: `# doc-compliance-test` (einziger Dokumentations-Check dieser Spec): Import von `resolve_metric_col_order` schlägt fehl; `_visible_hour_metrics(None, ...)` wird nicht mehr akzeptiert; Allowlist in `test_resolution_loss_guard.py` verweist auf den Adapter.

- **AC-5:** Given Vorschau von Trip und Orte-Vergleich sowie Validator-Vorschau / When die Vorschau erzeugt wird / Then zeigt sie dieselben Spalten und dieselbe Spaltenfolge wie die zugestellte Mail.
  - Test: `test_compare_preview_hourly_parity.py` und Trip-Vorschau-Parität (`preview_service`) einzeln; Vergleich Vorschau gegen Versand-Render derselben Konfiguration; Validator-Vorschau ohne Auswahl zeigt neun Vorgabespalten.

- **AC-6:** Given zwei verschiedene Nutzer mit unterschiedlicher Metrik-Auswahl und Reihenfolge / When für beide hintereinander Trip- und Orte-Mail erzeugt werden / Then enthält jede Mail ausschließlich die Spaltenfolge des eigenen Nutzers, unabhängig von der Aufrufreihenfolge.
  - Test: Zwei Nutzer mit je eigener Konfiguration, beide Reihenfolgen des Aufrufs, Spaltenköpfe der Mail je Nutzer; kein Fallback auf `"default"`.

- **AC-7:** Given Trip-Konfigurationen mit Telegram-, SMS- und Premium-SMS-Auswahl / When das Briefing gerendert wird / Then bleiben diese Kanäle inhaltsgleich zum Stand vor der Änderung (keine Auswirkung der Mail-Umstellung).
  - Test: bestehende Kanal-Matrix `test_channel_metric_matrix.py` und Prüfkatalog-Fälle Telegram/SMS einzeln unverändert grün.

- **AC-8:** Given ADR-0121 / When die Umstellung ausgeliefert ist / Then enthält das ADR einen kurzen Nachtrag: Orte-`hourly` ist nie `None`; `None` bleibt nur Trip-`hourly` und kanalweise „kein Filter"; der ADR-Index bleibt konsistent.
  - Test: `tests/test_adr_index_drift.py` grün; Nachtrag vorhanden (`# doc-compliance-test`).

## Definition of Done

- AC-1 bis AC-8 durch benannte Tests grün; Golden-Mails und Prüfkatalog einzeln grün, Golden-Dateien unverändert.
- Mutations-Gegenprobe durch den Adversary (siehe Test Plan): jede Verfälschung lässt mindestens einen Test am Mail-Ergebnis rot werden.
- Vor dem ersten Code gegen `origin/main` abgeglichen.
- Alle 6 CI-Checks grün, Staging-Verifikation mit echt zugestellter Mail (Trip und Orte) unverändert, Prod-Selftest bestanden.

## Test Plan

### Automated Tests (TDD RED)

Zusicherungen werden am Mail-Ergebnis geprüft, nicht an Hilfsfunktionen; kein Mock-Theater (kein `Mock()`/`patch()`).

- [ ] Neu `tests/tdd/test_3096_mail_resolver.py`: GIVEN Trip-Konfiguration mit engem E-Mail-Layout und nicht auswählbarer Metrik WHEN `format_email` THEN Spaltenköpfe in HTML und Klartext entsprechen Resolver-Folge ohne nicht auswählbare Metrik (AC-2). Rot vor der Umstellung, wo sich die Folge am Resolver statt an der Altfunktion orientiert (Nachweis: Resolver-Folge mit gezielt abweichender E-Mail-Layout-Reihenfolge).
- [ ] Neu: GIVEN Orte ohne Stundenverlauf-Auswahl WHEN Orte-Mail HTML und Klartext THEN genau die neun Vorgabespalten; GIVEN Aufruf von `_visible_hour_metrics` mit `None` THEN schlägt er fehl, rot solange der Sonderpfad existiert (AC-3, AC-4).
- [ ] Neu: GIVEN zwei Nutzer mit unterschiedlicher Auswahl WHEN Mails beider erzeugt THEN je eigene Spaltenfolge, beide Aufrufreihenfolgen (AC-6).
- [ ] Neu: GIVEN Vorschau und Versand derselben Konfiguration WHEN beide gerendert THEN gleiche Spalten (AC-5).
- [ ] Umstellen auf Resolver/Adapter: `test_einstellung_gleich_mail_editor_standard.py` (:40,43,113,141), `test_channel_metric_matrix.py` (:121,248-256,569,715), `test_einstellung_gleich_mail_orte.py` (:104,594; Soll-Orakel ohne `HOURLY_DEFAULT_METRIC_IDS`-Direktzugriff im Renderer-Sinn), `tests/helpers/metrik_listen_scan.py` (:346), `tests/test_resolution_loss_guard.py` (:702,852; Allowlist auf `helpers.py::email_col_order`).
- [ ] Nur Kommentare korrigieren: `test_compare_preview_hourly_parity.py`, `test_compare_metric_order_and_wind_direction.py` (:169), `unit/test_compare_hourly_legacy_selection_bestandsschutz.py`.
- [ ] Unverändert grün (Regression, einzeln benannt): Golden- und Prüfkatalog-Tests aus AC-1, `test_3057_channel_list_resolver.py`, `test_3065_ausblick_stundenverlauf_resolver.py` (Orakel bleibt bis #3102).
- [ ] Mutations-Gegenprobe durch den Adversary (Kopie extern, String-Ersetzung, nie `git checkout/stash/reset`): Adapter ohne `selectable`-Filter; Adapter mit vertauschter Folge; Vorgabeliste im Renderer um eine Spalte gekürzt; Resolver-Aufruf auf kollabiertem statt unkollabiertem dc; `hourly_metrics` im Validator nicht aufgelöst. Jede Verfälschung muss mindestens einen Test rot machen, Prüfung am Mail-Ergebnis.
- Live-E2E: Staging-Mail-Validatoren gegen echt zugestellte Mail (Trip und Orte), Ergebnis unverändert.

## Out of Scope

- Telegram, SMS, Premium-SMS auf Resolver umstellen: #3098, #3099, #3100.
- Vokabular-Vereinheitlichung (Renderer-Kennung/Katalog-ID): #3101.
- Migration, Differenztest-Orakel und Import-Sperre, Löschung der Orakel aus #3057/#3065: #3102.
- Roh/Einfach im Stundenverlauf: #3097.
- Vereinheitlichung des Format-Standards ohne Angabe (Trip Katalog, Orte Roh): bewusst nicht Teil; bei Bedarf eigenes Folge-Issue mit Produktentscheidung.
- Jede sichtbare Änderung der zugestellten Mail in irgendeinem Kanal, außer der freigegebenen Angleichung von Update-/Alarm-Mail an die E-Mail-Auswahl.

## Affected Files

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `src/output/renderers/trip_report.py` | MODIFY | Resolver einmal vor Kollabierung, `view.email` an `render_email` durchreichen |
| `src/output/renderers/email/__init__.py` | MODIFY | neuer Parameter (E-Mail-Zeilen) an `render_html`/`render_plain` |
| `src/output/renderers/email/helpers.py` | MODIFY | `resolve_metric_col_order` löschen, Adapter `email_col_order` |
| `src/output/renderers/email/html.py` | MODIFY | Spaltenfolge aus Adapter, Rückfall über Resolver |
| `src/output/renderers/email/plain.py` | MODIFY | wie `html.py` |
| `src/output/renderers/compare_hourly_metric_ids.py` | MODIFY | `_standard_aus_grundauswahl` liefert konkrete Vorgabeliste |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_visible_hour_metrics` ohne None-Zweig, Import entfällt, `_should_merge_wind_dir` ohne `is None` |
| `src/output/renderers/comparison.py` | MODIFY (formal) | Klartext ruft denselben `_visible_hour_metrics` |
| `src/services/report_config_resolver.py` | MODIFY | `hourly_metrics` aus `view.hourly` |
| `src/services/validator_render_service.py` | MODIFY | `hourly_metrics` vor `render_compare_html` auflösen |
| `src/services/channel_list_resolver.py` | MODIFY | Docstrings (Orte-`hourly` nie `None`) |
| `docs/adr/0121-kanonische-kanal-liste.md` | MODIFY | Nachtrag |
| `tests/tdd/test_3096_mail_resolver.py` | CREATE | neue rote Tests (AC-2 bis AC-6) |
| `tests/tdd/test_einstellung_gleich_mail_editor_standard.py`, `tests/test_channel_metric_matrix.py`, `tests/tdd/test_einstellung_gleich_mail_orte.py`, `tests/helpers/metrik_listen_scan.py`, `tests/test_resolution_loss_guard.py` | MODIFY | auf Resolver/Adapter umstellen |
| `tests/test_compare_preview_hourly_parity.py`, `tests/test_compare_metric_order_and_wind_direction.py`, `tests/unit/test_compare_hourly_legacy_selection_bestandsschutz.py` | MODIFY | nur Kommentare |

## Known Limitations

- Format-Standard ohne Angabe bleibt zwischen Trip (Katalog) und Orte (Roh) verschieden (Designentscheidung, siehe oben).
- Differenztest-Orakel aus #3057/#3065 bestehen bis #3102 weiter; deshalb bleibt `resolve_hourly_metrics` erhalten.
- `hourlyDefault` im Frontend-Katalog bleibt als Anzeige für den Editor.
- Der Umfang liegt über der Schätzung (src rund +157/-98 statt rund +60/-60, 11 Code-Dateien), weil neben Trip- und Orte-Mail auch Vorschau-, Validator- und Konfig-Resolver auf den Adapter umgestellt wurden und mehrere Bestandstests auf den neuen Adapter zeigen mussten; keine Code-Datei liegt außerhalb der Datei-Tabelle der Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0121 (kurzer Nachtrag zu Nachtrag 2b Nr. 4)
- **Rationale:** Setzt die Adapter-Vorgabe (ADR-0121 Nr. 8) für die E-Mail um. Orte-`hourly` ist künftig nie `None`; keine bestehende Entscheidung wird still geändert, daher kein neues ADR.

## Changelog

- 2026-11-17: Initial spec created (Phase 3a, Issue #3096, Epic #3058)
- 2026-11-17: PO-Entscheidung nach Adversary-Finding: Update-/Alarm-Mail folgen der E-Mail-Auswahl (Scope, Schritt 2, Output, Out of Scope angepasst)
