---
entity_id: feat_3237_altpfad_entfernen
type: module
created: 2026-11-22
updated: 2026-11-22
status: draft
version: "1.0"
workflow: altpfad-3237-entfernen
tags: [was-steht-wo, placements, rueckbau, epic-3122]
---

# Was steht wo B6b-0 + B6b-1: Erstanlage mit voller Tabelle, Altpfad im Backend entfernen

## Approval

- [ ] Approved

## Purpose

Nach der Migration (#3157, 21.11.: alle 21 Prod-Abos tragen `display_config.placements.rows`) bestimmt allein die Tabelle „Was steht wo“, welche Metrik in welchem Kanal und an welcher Stelle steht. Dieses Paket (#3275 = B6b-0, #3237 = B6b-1, Epic #3122) sorgt zuerst dafür, dass jedes neue Abo schon bei der Anlage die volle Tabelle aus der Grundauswahl bekommt, und löscht danach im Backend den Altpfad (Lese-Adapter, Differenz-Orakel, Kanal-Kaskade). Ein AST-Import-Wächter verhindert, dass der Altpfad zurückkehrt.

## Source

- **File:** `src/services/placements.py` (neue Funktion), `src/services/channel_list_resolver.py` (Löschung)
- **Identifier:** `placements_aus_grundauswahl` (neu); gelöscht: `legacy_view`, `legacy_lists`, `trip_channel_metrics`, `_trip_view`, `_compare_view`, `vm_lists`, `placements_from_legacy`, `erstanlage_begleitfelder`, `get_metrics_for_channel`, `cascade_source_for_channel`

> **Schicht-Hinweis:** Python-Core (`src/services/`, `src/app/`, `src/output/`, `api/`) trägt Quelle und Löschung; Go-API (`internal/handler/`) ruft bei der Anlage die Python-Quelle; `.claude/hooks/` ist das Prüfwerkzeug (Validator-Soll). **Kein Frontend in dieser Spec** (Schreibpfade = #3276).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Beide Anlagepfade (Trip, Orts-Vergleich) rufen dieselbe Python-Funktion; es entsteht keine zweite Quelle. Compare-eigen bleibt nur das, was bisher schon compare-eigen war (Orte-Tab, Compare-Mail-Template).
> - **Mandantentrennung:** Anlage und Lesen laufen mit der echten `user_id` aus dem Auth-Kontext, nie `"default"`; Tests mit zwei verschiedenen Nutzern, Schreiben per Read-Modify-Write mit Merge, nie Replace (#102).
> - **Kanäle:** E-Mail (HTML und Text), Telegram, SMS und Premium-SMS liefern für Abos mit Tabelle vor und nach der Löschung dieselbe Ausgabe.

## Estimated Scope

- **LoC:** B6b-0 ca. +250; B6b-1 netto ca. −1500 bis −2000
- **Files:** ca. 22 Produktionsdateien (inkl. Go) + ca. 15 Testdateien
- **Effort:** high (Risiko HIGH: zentraler Lesepfad aller vier Kanäle; gemildert, weil alle 21 Prod-Abos `rows` tragen)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/placements.py` | MODIFY | NEU `placements_aus_grundauswahl` (Grundauswahl → `rows` + `outlook_reports`, ohne Altfelder); `placements_from_legacy`, `legacy_placements`, `_legacy_rows`, `_output_changes`, `_legacy_outlook_reports` löschen; `anlage_outlook_reports` prüfen |
| `internal/handler/compare_preset.go`, `internal/handler/trip.go` (`CreateTripHandler`), `internal/handler/placements.go` (+ Go-Tests) | MODIFY | Anlage (Trip + Orts-Vergleich) schreibt volle `placements` aus der Python-Quelle; Begleitfeld `show_stability_off` entfällt; mitgeschickte `placements` bleiben unangetastet |
| `src/services/placements_view_service.py`, `api/routers/placements.py` | MODIFY | `erstanlage_begleitfelder` löschen; Karte ohne `rows` → `placements_aus_grundauswahl` |
| `src/services/channel_list_resolver.py` | MODIFY (großteils DELETE) | `legacy_view`, `legacy_lists`, `trip_channel_metrics`, `_trip_view`, `_compare_view`, `vm_lists`, `ALTBESTAND_UEBER_UMRECHNUNG` weg; ohne `rows` → Grundauswahl-Tabelle |
| `src/app/models.py` | MODIFY | `_cascade_source_for_channel`, `get_metrics_for_channel`, `cascade_source_for_channel` löschen; Loader/Serialisierung der Altfelder bleiben bis #3277 |
| `src/output/renderers/channel_layout.py` | MODIFY | `render_for_channel` ohne `dc.get_metrics_for_channel` (Aufrufer liefern die fertige Liste) |
| `compare_outlook_metric_ids.py` (`resolve_trip/compare_outlook_metrics/formats`), `compare_metric_ids.py` (`resolve_channel_enabled_metrics`, `resolve_channel_layout_rows`) | DELETE (Teile) | nur vom Resolver gerufen; `resolve_enabled_metrics(_report)` bleiben |
| `api/routers/validator.py` | MODIFY | Endpoint `metrics-for-channel`: `source` = `"placements"` \| `"grundauswahl"`, `metric_ids` aus der Tabelle |
| `src/services/report_config_resolver.py` | MODIFY | `_options_bisher`, `_legacy_outlook_reports`, Lesestellen `channel_active_metrics` weg |
| `src/services/validator_render_service.py` | MODIFY | Vorschau-`hourly_metrics` aus der Tabelle |
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | Altzweige raus; `orte_soll` liest die Tabelle zuerst; ohne `rows` → Grundauswahl; Hook-Importe von `_legacy_outlook_reports`/`_feld` ersetzen (#3273 beachten) |
| `scripts/migrate_3157_placements.py` | DELETE | Live-Migration erledigt (21.11.) |
| `tests/helpers/kanal_liste_orakel.py`, `test_3057_channel_list_resolver.py`, `test_3065_ausblick_stundenverlauf_resolver.py`, `test_einstellung_gleich_mail_trip_tabelle.py` (`_adapter_gegen_orakel`), `test_placements_umrechnung_altbestand.py`, `unit/test_compare_channel_metric_cascade.py`, `unit/test_trip_metric_cascade_single_source.py` | DELETE/MODIFY | Differenz-Orakel und Alt-Kaskaden-Tests |
| `test_channel_metric_matrix`, `test_sms_user_metric_order`, `integration/test_issue_448_validator_metrics_for_channel`, `test_ausblick_erbt_grundauswahl`, `test_compare_ausblick_erbt_grundauswahl`, `test_einstellung_gleich_mail_editor_standard`, `test_einstellung_gleich_mail_orte`, `test_outlook_*`, `test_3156_renderer_nachzug_roh_einfach` | MODIFY | auf Tabelle umschreiben |
| `tests/test_altpfad_import_sperre.py` | CREATE | AST-Import-Wächter (Muster `tests/test_mail_recipient_parity.py`) |
| `tests/` Golden-Schnappschuss + AC-38-Test | CREATE | Vier-Kanal-Ausgabe vor/nach Löschung und mit/ohne Altfelder |
| `docs/specs/modules/feat_3122_was_steht_wo.md`, `docs/specs/_archive/modules/issue_448_validator_metrics_for_channel.md`, `docs/reference/api_contract.md` | MODIFY | Nachtrag Erstanlage, `source`-Vertrag |

### Nicht in dieser Spec (Zuschnitt-Kommentar #3237, 22.11.)

- Frontend-Schreibpfade der Altfelder: **#3276** (B6b-2).
- Daten-/Modell-Bereinigung inklusive `show_outlook` und `multi_day_trend_reports`: **#3277** (B6b-3). Dort entfallen Altfelder in Loader, Serialisierung, Renderer-Parameter und Bestandsdaten.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `placements.read_placements` / `resolve_rows` / `metrics_at` / `resolve_outlook_reports` / `outlook_applies` | Python-Service | bleibende Quelle der Tabelle |
| `resolve_enabled_metrics` / `resolve_enabled_metrics_report` | Python | Grundauswahl `active_metrics` als Eingabe von `placements_aus_grundauswahl` |
| `feat_3122_was_steht_wo` | Spec | Teil A Nr. 8, AC-38, B6 |
| `feat_3157_migration_placements` | Spec | verweist Löschung an #3237 |
| `fix_3242_validator_soll_auswahl` | Spec | Validator-Soll-Hook |
| `issue_448_validator_metrics_for_channel` | Spec | Vertrag `{source, metric_ids}` |
| `tests/test_mail_recipient_parity.py` | Muster | AST-Wächter mit Selbstnachweis |
| Go-Handler `internal/handler/placements.go` | Go-API | ruft Python-Quelle bei der Anlage (Muster wie bisher `erstanlage_begleitfelder`, unter Briefing-Sperre) |
| #3164 | Issue | Abgleich der bewussten Verhaltensänderung (Ausblick-Vorbelegung) |
| #3273 | Issue | Validator-Soll-Hook, beachten |

## Implementation Details

**Schritt 1 (B6b-0), eine Quelle:** `placements_aus_grundauswahl` in `src/services/placements.py` erzeugt aus der Grundauswahl des Abos die volle Tabelle: Haken, Form je Stelle, die eine Reihenfolge und `outlook_reports` nach der Vorbelegung (ADR-0124, Spec #3122). Sie liest keine Altfelder. Die Go-Anlage (Trip und Orts-Vergleich) ruft sie über den internen Python-Endpunkt, speichert die volle `placements` per Read-Modify-Write mit Merge. Bereits mitgeschickte `placements` werden nicht überschrieben. Der Lesepfad ohne `rows` (Abo ohne Tabelle) und die Karte nutzen dieselbe Funktion; `erstanlage_begleitfelder` entfällt, `show_stability=false` entsteht aus der Grundauswahl-Tabelle selbst.

**Schritt 2, Golden-Schnappschuss:** Vor jeder Löschung wird die Ausgabe aller vier Kanäle (Mail HTML, Mail Text, Telegram, SMS, Premium-SMS) für repräsentative Abos mit Tabelle (Trip und Orts-Vergleich, mehrere Formen) mit echten Daten aufgenommen und festgeschrieben. Er ersetzt das Differenz-Orakel.

**Schritt 3, Löschung:** Backend-Altpfad, Validator-Endpoint, Validator-Soll-Hook, Vorschau und `report_config_resolver` wie in der Dateitabelle. Renderer bekommen die Liste von ihren Aufrufern (`narrow.py`, `comparison.py`, `placements_view_service.py`, `trip_report.py` liefern sie bereits).

**Schritt 4, Wächter:** `tests/test_altpfad_import_sperre.py` (`# doc-compliance-test`) prüft per `ast.walk`, dass kein Produktionscode die gelöschten Namen importiert oder aufruft. Erlaubnisliste als Daten mit Begründung und `EXPIRY`: `placements.resolve_outlook_reports`, ggf. `report_config_resolver._channel_unresolved_count`, `resolve_hourly_metrics(None)` in `comparison.py` und `email/compare_html.py`.

**Schritt 5, `show_outlook`:** bleibt Altfeld (wirkt mit Tabelle nicht, `report_config_resolver.py:144-147`). In diesem Paket entfällt nur die Lesestelle `_options_bisher`; Feld und Renderer-Parameter entfernt #3277.

**Bewusste Verhaltensänderung:** Ein neues Abo ohne Tabelle bekam bisher die Metriken und Formate des Assistenten-Ausblicks. Künftig erhält es von Anfang an die Tabelle aus der Grundauswahl (Abgleich mit #3164). In Prod haben alle 21 Abos `rows`, 0 Abos sind betroffen.

## Expected Behavior

- **Input:** Anlage eines Trips oder Orts-Vergleichs; Lesen/Rendern eines bestehenden Abos (mit oder ohne `rows`); Aufruf `metrics-for-channel`; Validator-Soll.
- **Output:** Jedes neue Abo trägt sofort volle `placements.rows`; alle vier Kanäle lesen nur die Tabelle (oder Grundauswahl-Tabelle bei fehlenden `rows`); `metrics-for-channel` liefert `source` `"placements"` oder `"grundauswahl"`.
- **Side effects:** Nutzerdaten werden bei der Anlage geschrieben (Merge, je Nutzer). Es werden keine Bestandsdaten gelöscht (Bereinigung = #3277).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer legt einen neuen Trip an / When die Anlage abgeschlossen ist / Then trägt der Trip sofort `placements.rows` aus der Grundauswahl (Haken, Form, Reihenfolge, `outlook_reports` nach Vorbelegung) und die Karte „Was steht wo“ zeigt diese Tabelle ohne vorheriges Speichern.
  - Test: Trip über die Anlage-Schnittstelle erzeugen, gespeicherte Datei und Karten-Antwort lesen, Tabelle gegen die Grundauswahl vergleichen.

- **AC-2:** Given ein Nutzer legt einen neuen Orts-Vergleich an / When die Anlage abgeschlossen ist / Then trägt er ebenfalls sofort volle `placements.rows` aus der Grundauswahl, erzeugt von derselben Python-Funktion wie beim Trip (Go ruft sie, es gibt keine zweite Berechnung).
  - Test: Orts-Vergleich anlegen, gespeicherte Tabelle prüfen; Gleichheit mit der Trip-Tabelle bei gleicher Grundauswahl; Go-Test belegt, dass Go keine eigene Zeilenbildung enthält, sondern die Python-Antwort speichert.

- **AC-3:** Given ein Abo ohne `placements.rows` (Altbestand ohne Tabelle) / When Karte, Briefing oder Validator die Tabelle lesen / Then wird sie über `placements_aus_grundauswahl` aufgelöst und nicht aus Altfeldern (`channel_layouts`, `outlook_metrics`, `channel_active_metrics`), auch wenn diese gesetzt sind.
  - Test: Abo ohne rows mit widersprüchlich gesetzten Altfeldern lesen; Ergebnis entspricht der Grundauswahl-Tabelle.

- **AC-4:** Given ein neuer Trip oder Orts-Vergleich ohne Stabilitäts-Wunsch / When er angelegt wird / Then bleibt `show_stability` wie bisher aus, ohne dass `erstanlage_begleitfelder` existiert oder ein Begleitfeld `show_stability_off` gesendet wird.
  - Test: Anlage ausführen, gespeicherten `show_stability`-Wert prüfen (Verhalten unverändert gegenüber Stand vor der Änderung); Aufrufe der entfernten Funktion fehlen im Quelltext (durch AC-9 bewacht).

- **AC-5:** Given Abos mit Tabelle (Trip und Orts-Vergleich, mehrere Formen) und fest aufgenommener Golden-Ausgabe / When der Altpfad gelöscht ist und das Briefing in allen vier Kanälen erzeugt wird / Then sind Mail (HTML und Text), Telegram, SMS und Premium-SMS zeichengleich zum Schnappschuss vor der Löschung.
  - Test: Golden-Vergleich je Kanal mit echten Wetterdaten aus Fixtures, kein Mock.

- **AC-6:** Given ein Abo mit Tabelle / When Altfelder (`channel_layouts`, `outlook_metrics`, `outlook_metrics_formats`, `channel_active_metrics`, `hourly_metrics`, `show_outlook`) nachträglich gesetzt oder geändert werden und das Briefing erzeugt wird / Then ist die Ausgabe aller vier Kanäle identisch zur Ausgabe ohne diese Altfelder (AC-38 aus #3122).
  - Test: dasselbe Abo einmal sauber, einmal mit gesetzten Altfeldern rendern; je Kanal Byte-Gleichheit.

- **AC-7:** Given der Validator-Endpoint `metrics-for-channel` / When er für ein Abo mit Tabelle und eines ohne `rows` abgefragt wird / Then liefert er `source` `"placements"` bzw. `"grundauswahl"` und `metric_ids` aus der Tabelle; die Werte `cascade`-Herkunft früherer Stände kommen nicht mehr vor.
  - Test: Endpoint für beide Abo-Arten aufrufen, `source` und `metric_ids` prüfen; Vertrag im `api_contract.md` und issue_448-Spec nachgezogen.

- **AC-8:** Given der Validator-Soll-Hook und die Vorschau / When sie das Soll für Orts-Vergleich oder Trip bestimmen / Then lesen sie ohne Altzweige zuerst die Tabelle (`orte_soll` Tabelle zuerst), ohne `rows` die Grundauswahl, und die Vorschau-`hourly_metrics` stammen aus der Tabelle.
  - Test: Soll-Hook gegen Abo mit Tabelle und Abo mit widersprüchlichen Altfeldern laufen lassen; Soll folgt der Tabelle; Mail-Validatoren bleiben grün.

- **AC-9:** Given der AST-Import-Wächter `tests/test_altpfad_import_sperre.py` / When er den Produktionscode prüft / Then findet er keine Importe oder Aufrufe der gelöschten Altpfad-Namen außer den Einträgen der Erlaubnisliste, die als Daten mit Begründung und `EXPIRY` geführt wird.
  - Test: Wächter läuft grün; Selbstnachweis mit synthetischem Quelltext, der einen verbotenen Import enthält, wird erkannt; Negativfall mit erlaubtem Aufruf besteht; abgelaufenes `EXPIRY` lässt den Test rot werden (`# doc-compliance-test`).

- **AC-10:** Given zwei verschiedene Nutzer mit je einem Abo / When für beide Abos angelegt, gelesen und gespeichert wird / Then bleiben Tabellen und Daten je Nutzer getrennt, die Anlage verwendet die echte `user_id` (nie `"default"`), und bestehende Felder des Abos bleiben durch Read-Modify-Write mit Merge erhalten.
  - Test: Nutzer A und B legen Abos an, jeweils fremde Daten bleiben unberührt; Abo mit vorhandenen Feldern behält diese nach der Anlage der Tabelle.

- **AC-11:** Given das Migrationsskript `scripts/migrate_3157_placements.py` / When der Rückbau abgeschlossen ist / Then existiert es nicht mehr und kein Produktionscode, Test oder Hook importiert es oder `placements_from_legacy`.
  - Test: Wächter AC-9 deckt Importe ab; Testlauf der Kernschicht bleibt ohne das Skript grün.

## Definition of Done

- AC-1 bis AC-11 durch Kern-Tests ohne Mock grün; Go-Tests der Anlage (Trip und Orts-Vergleich) grün.
- Golden-Schnappschuss aller vier Kanäle (Mail HTML/Text, Telegram, SMS, Premium-SMS) vor der Löschung erzeugt und danach zeichengleich.
- AST-Import-Wächter grün; kein Backend-Code liest mehr Altfelder außerhalb der begründeten Erlaubnisliste.
- Staging: neu angelegter Trip und neuer Orts-Vergleich tragen sofort volle Tabelle; Mail-Validatoren mit `--konfig` ohne SOLL-Verletzung.
- Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN neuer Trip WHEN Anlage THEN volle `placements.rows` aus der Grundauswahl (AC-1)
- [ ] Test 2: GIVEN neuer Orts-Vergleich WHEN Anlage THEN gleiche Quelle, volle `rows` (AC-2)
- [ ] Test 3: GIVEN Abo ohne `rows` mit Altfeldern WHEN Lesen THEN Grundauswahl-Tabelle (AC-3)
- [ ] Test 4: GIVEN Anlage WHEN `show_stability` prüfen THEN unverändert aus (AC-4)
- [ ] Test 5: GIVEN Golden-Schnappschuss WHEN Altpfad gelöscht THEN vier Kanäle identisch (AC-5)
- [ ] Test 6: GIVEN Altfelder gesetzt WHEN Rendern THEN gleiche Ausgabe wie ohne (AC-6, AC-38)
- [ ] Test 7: GIVEN Endpoint `metrics-for-channel` WHEN Abfrage THEN `source` `placements`/`grundauswahl` (AC-7)
- [ ] Test 8: GIVEN Soll-Hook und Vorschau WHEN Soll bestimmt THEN Tabelle zuerst (AC-8)
- [ ] Test 9: GIVEN AST-Wächter WHEN Selbstnachweis und Negativfall THEN erkennt Verstoß und lässt Erlaubnis zu (AC-9)
- [ ] Test 10: GIVEN zwei Nutzer WHEN Anlage THEN getrennt, Merge, kein `"default"` (AC-10)
- [ ] Test 11: GIVEN Codebasis nach der Löschung WHEN AST-Wächter läuft THEN existiert `scripts/migrate_3157_placements.py` nicht mehr und kein Modul importiert es oder `placements_from_legacy` (AC-11)

Test-Politik: kein Mock-Theater, echte Daten und Dateien, keine Dateiinhalt-Checks außer dem AST-Wächter (`# doc-compliance-test`). Die Kern-Schicht läuft deterministisch ohne Netz; die Live-Prüfung der Mail-Validatoren läuft in `/e2e-verify`.

## Known Limitations

- **Bis #3276** schreiben die alten Editoren im Frontend weiter Altfelder; diese sind nach diesem Paket wirkungslos (zwei Bedienwege, die Tabelle gewinnt). #3276 folgt direkt danach.
- Altfelder bleiben in Bestandsdaten, Loader und Serialisierung bis zur Bereinigung in **#3277** (inkl. `show_outlook`, `multi_day_trend_reports`).
- Verhaltensänderung für Abos ohne Tabelle (siehe Implementation Details); in Prod 0 betroffene Abos.
- Gate-Konfiguration wird nicht angefasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (Tabelle „Was steht wo“, Nachtrag 2026-11-22 Erstanlage und Altpfad-Rückbau)
- **Rationale:** ADR-0124 hat die Tabelle als einzige Quelle entschieden; dieses Paket vollzieht den vorgesehenen Rückbau und ändert keine frühere Entscheidung. Ein neues ADR ist nicht nötig; der Nachtrag hält die Erstanlage-Regel (volle Tabelle aus Grundauswahl, eine Quelle) fest.

## Changelog

- 2026-11-22: Initial spec created (Paket #3275 + #3237, Epic #3122).
