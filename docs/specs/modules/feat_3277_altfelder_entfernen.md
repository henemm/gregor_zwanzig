---
entity_id: feat_3277_altfelder_entfernen
type: module
created: 2026-11-25
updated: 2026-11-25
status: draft
version: "1.0"
workflow: feat-3277-altfelder-entfernen
tags: [was-steht-wo, placements, rueckbau, epic-3122]
---

# Was steht wo B6b-3: Altfelder aus Datenmodell, Loader, Serialisierung und Renderern entfernen

## Approval

- [ ] Approved

## Purpose

Die Tabelle „Was steht wo“ (`placements`) ist seit #3237 und #3276 die einzige Quelle für Metriken, Formen und Ausblick. Dieses Paket (#3277, Epic #3122) entfernt im Backend (Python, Go-Modell, Soll-Hook) die zehn wirkungslosen Altfelder aus Modell, Loader, Serialisierung und Renderer-Signaturen. Zusätzlich sorgt es dafür, dass Speichern diese Namen aktiv verwirft und ein Feldnamen-Wächter ihre Rückkehr verhindert. Für den Nutzer ändert sich in keinem der vier Kanäle etwas Sichtbares.

## Source

- **File:** `src/app/models.py`, `src/app/loader.py`, `src/services/report_config_resolver.py`
- **Identifier:** `UnifiedWeatherDisplayConfig`, `TripReportConfig`, `_parse_display_config`, `_trip_to_dict`, `save_location`, `ReportRenderOptions`

> **Schicht-Hinweis:** Python-Core (`src/app/`, `src/services/`, `src/output/`, `api/`) trägt den Rückbau. Go-API nur `internal/model/compare_preset.go` (Feld `OutlookEnabled`). `.claude/hooks/_soll_aus_konfiguration.py` ist Prüfwerkzeug. **Kein Frontend** (#3297, #3298, #3301) und **kein Datenlauf** auf Bestandsdaten (#3351, schließt #3102; erledigt, #3102: Abschluss mit #3351).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Rückbau trifft beide Pfade gleich; es entsteht keine neue Komponente, keine einseitige Neuanlage.
> - **Mandantentrennung:** Speichern bleibt Read-Modify-Write mit Merge je Nutzer (ADR-0101, #102), `user_id` aus dem Auth-Kontext, nie `"default"`. Der Speicherpfad wird mit zwei verschiedenen Nutzern getestet (AC-4).
> - **Kanäle:** E-Mail (HTML und Text), Telegram, SMS und Premium-SMS liefern vor und nach dem Rückbau zeichengleiche Ausgabe, für Trip und Ortsvergleich (AC-1). Nur der E-Mail-Renderer hatte den Parameter `show_outlook`; die anderen drei Kanäle haben keinen und sind von der Signaturänderung nicht berührt.

## Estimated Scope

- **LoC:** ca. +300 / −900
- **Files:** ca. 25 Produktionsdateien (Python, Go, Hook, Skripte) + ca. 75 Testdateien + Doku
- **Effort:** high (Risiko MEDIUM: zentrale Lade-/Speicherpfade und E-Mail-Renderer; Ausgabe muss bytegleich bleiben)

## Scope

### Die zehn Altfelder (Spec #3122 Teil A Nr. 8, Nachtrag 21.11., ADR-0124 Nr. 6)

`channel_layouts`, `channel_layouts_per_report`, `channel_active_metrics`, `outlook_metrics`, `outlook_metric_formats`, `hourly_metrics`, `hourly_metric_formats`, `show_outlook`, `multi_day_trend_reports`, `outlook_enabled`.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/models.py` | MODIFY | `UnifiedWeatherDisplayConfig`: `multi_day_trend_reports`, `per_channel_layouts`, `per_report_layouts`, `outlook_metrics`, `outlook_metric_formats` entfernen; `TripReportConfig`: `multi_day_trend_reports`, `show_outlook` entfernen |
| `src/app/loader.py` | MODIFY | Lesen (`_parse_display_config`, Report-Config-Lesen) und Schreiben (`save_location`, `_trip_to_dict`) der Altfelder entfernen; `save_trip`/`update_trip`/`save_location` verwerfen die zehn Namen aktiv aus `extra` und aus dem Merge-Ergebnis (`_deep_merge_preserve_unknown` bleibt für alle anderen Schlüssel) |
| `src/app/metric_catalog.py` | MODIFY | `normalize_outlook_metric_formats` löschen, falls ohne Produktionsaufrufer |
| `src/output/renderers/email/__init__.py`, `email/html.py`, `email/plain.py`, `trip_report.py` | MODIFY | Parameter `show_outlook` entfernen; Ausblick allein über `placements.outlook_reports`; Lesestelle `per_channel_layouts`/`per_report_layouts` in `trip_report.py` entfernen |
| `src/services/report_config_resolver.py` | MODIFY | `ReportRenderOptions.show_outlook`, Altfeld-Vermerke und `outlook_enabled`-Lesestelle entfernen |
| `src/services/placements_view_service.py`, `src/services/placements.py`, `src/services/channel_list_resolver.py` | MODIFY | Parameter `outlook_enabled` aus `placements_aus_grundauswahl` und Aufrufern entfernen |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | `resolve_hourly_metric_formats` (+ `__all__`) löschen |
| `api/routers/validator.py`, `src/services/validator_render_service.py` | PRÜFEN/MODIFY | Request-Felder `hourly_metrics`/`hourly_metric_formats`, Entscheidungsregel siehe Implementation Details Schritt 6 |
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | `outlook_enabled`-Lesestellen entfernen |
| `internal/model/compare_preset.go` + Go-Tests | MODIFY | Feld `OutlookEnabled` entfernen (Go-Tests auf Tabelle umstellen) |
| `scripts/migrate_2454_derived_children.py`, `scripts/backfill_display_config_issue111.py` | DELETE (nach Prüfung) | verbrauchte Einmal-Skripte, wenn kein Aufrufer und kein Test sie braucht |
| `scripts/send_gate_test_mails.py` | MODIFY | Altfeld-Fixtures auf `placements` umstellen |
| `tests/test_altpfad_import_sperre.py` | MODIFY | `resolve_hourly_metric_formats` (+ ggf. `normalize_outlook_metric_formats`) in `VERBOTEN` |
| `tests/test_altfeld_namen_sperre.py` | CREATE | Feldnamen-Wächter (`# doc-compliance-test`) mit ERLAUBT-Tabelle und Selbstnachweis |
| `tests/tdd/test_3237_golden_vier_kanaele.py` | MODIFY (nur Deutung) | bleibt bytegleich im Ergebnis; Altfelder im Eingang wirkungslos, Speichern entfernt sie |
| `tests/tdd/test_katalog_stellen_formen.py`, `tests/tdd/test_3156_renderer_nachzug_roh_einfach.py` | MODIFY | Tests der gelöschten `resolve_hourly_metric_formats` entfernen |
| ca. 60 Python- und ca. 15 Go-Testdateien mit Altfeld-Fixtures | MODIFY | Fixtures auf `placements` umstellen, nicht still löschen |
| `docs/reference/api_contract.md`, `docs/specs/modules/feat_3122_was_steht_wo.md` | MODIFY | Vertrag und Nachtrag |

### Nicht in dieser Spec

- Frontend-Schreibwege Trip (#3297), Typen, `outlook_enabled`-Round-Trip und Textscan (#3298), #3301.
- Datenlauf auf Bestandsdaten inkl. `compare_presets.json` des Nutzers `default` und Abschluss #3102 (#3351; erledigt, #3102). Reihenfolge: #3277, #3297, #3301/#3298, #3351.
- Kein serverseitiger Go-Strip auf Schreibwegen: er ließe noch schreibende Oberflächen stumm zurückspringen und wäre Wegwerfcode. Altfelder, die ein Client bis #3351 über Go-Schreibwege ablegt, bleiben wirkungslos auf der Platte; sobald das Abo über Python gespeichert wird, werden sie verworfen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_3122_was_steht_wo` | Spec | Teil A Nr. 6 und Nr. 8 (inkl. Nachträge 21./22.11.), AC-38 |
| `feat_3237_altpfad_entfernen` | Spec | Vorgänger; ließ Altfelder bis #3277 in Loader/Serialisierung |
| `feat_3276_vergleich_altfelder_entfernen` | Spec | Vorgänger Frontend-Schreibwege Ortsvergleich |
| ADR-0124 Nr. 6/8 | ADR | `outlook_reports` ersetzt `show_outlook`, `multi_day_trend_reports`, `outlook_enabled` |
| ADR-0101 | ADR | Read-Modify-Write mit Merge |
| `placements.placements_aus_grundauswahl` | Python-Service | Grundauswahl-Tabelle, künftig ohne `outlook_enabled` |
| `tests/test_altpfad_import_sperre.py` | Muster | AST-Wächter mit ERLAUBT-Tabelle (Grund + Ablaufdatum) |
| `tests/tdd/test_3237_golden_vier_kanaele.py` | Test | Nachweis Byte-Gleichheit aller vier Kanäle |
| Issues #3297, #3298, #3301, #3351, #3102 | Issues | Folgeschritte (außerhalb dieser Spec; #3102 erledigt) |

## Implementation Details

**Schritt 1, Modell, Loader, Serialisierung:** Die Modellfelder aus der Tabelle entfallen. Der Loader liest die Namen nicht mehr; `_trip_to_dict` und `save_location` schreiben sie nicht mehr. Weil `_deep_merge_preserve_unknown` unbekannte Schlüssel erhält, würde ein bloßes Entfernen der Felder Bestandswerte beim Speichern weitertragen. Deshalb wird in den Speicherfunktionen (Trip, Location, ggf. weitere Python-Speicherpfade der Ortsvergleiche) eine einzige zentrale Entfernung der zehn Namen aus `display_config`, `report_config` und Top-Level eingebaut, die nach dem Merge läuft. Alle anderen unbekannten Schlüssel bleiben erhalten (ADR-0101).

**Schritt 2, E-Mail-Renderer:** `show_outlook` war immer True (`report_config_resolver`). Der Parameter entfällt in `email/__init__.py`, `html.py`, `plain.py`, `trip_report.py`; der Ausblick erscheint allein, wenn `placements.outlook_reports` Berichte nennt. Telegram, SMS, Premium-SMS haben keinen solchen Parameter.

**Schritt 3, `outlook_enabled`:** Entfällt in `report_config_resolver`, `placements_view_service`, `placements.placements_aus_grundauswahl`, `channel_list_resolver`, Soll-Hook und Go-Modell. Begründung: ADR-0124 Nr. 6 ersetzt es durch `outlook_reports`; in Prod tragen alle Abos `placements.rows`/`outlook_reports`, alle Werte sind `true`, es gibt keine Bedienfläche, das Frontend sendet konstant `true`. Damit ändert sich für Bestand und Erstanlage nichts.

**Schritt 4, toter Code:** `resolve_hourly_metric_formats` (kein Produktionsaufrufer) wird samt Tests gelöscht und in `VERBOTEN` des Import-Wächters aufgenommen; `normalize_outlook_metric_formats` ebenso, falls nach Schritt 1 ohne Aufrufer. Die Skripte `migrate_2454_derived_children.py` und `backfill_display_config_issue111.py` werden auf Aufrufer geprüft (Grep in Code, Tests, Hooks, Cron) und bei null Aufrufern gelöscht; `send_gate_test_mails.py` nutzt danach `placements`.

**Schritt 5, Feldnamen-Wächter:** `tests/test_altfeld_namen_sperre.py` (`# doc-compliance-test`) prüft per `ast.walk` in Backend-Code (`src`, `api`, `.claude/hooks`, `scripts`) und per Textsuche der Go-Quellen (`internal`, `cmd`, ohne `_test.go`), dass keiner der zehn Namen als Schlüssel-Literal, Attribut oder Parameter auftaucht. Ausnahmen stehen in der Tabelle `ERLAUBT` (Datei, Name) mit Grund (mindestens 20 Zeichen) und Ablaufdatum; abgelaufene Einträge lassen den Test rot werden. Zulässige Dauerausnahme ist allein die zentrale Entfernungsliste aus Schritt 1 (sie muss die Namen nennen) sowie nachweislich Request-Parameter ohne Store-Bezug (Schritt 6). Selbstnachweis mit synthetischem Quelltext (Verstoß wird erkannt, erlaubter Eintrag besteht, Ablauf schlägt an).

**Schritt 6, Prüfschritt Validator-Request-Schema:** `api/routers/validator.py` (Request-Felder `hourly_metrics`, `hourly_metric_formats`, Zeilen ca. 620-623) und `validator_render_service.py` (ca. 481-491) werden gelesen. Entscheidungsregel: Liest der Code diese Werte nur aus dem Request-Body und gibt sie an den Renderer weiter, ohne ein Abo aus dem Store zu laden oder zu schreiben, ist es ein Request-Parameter ohne Store-Bezug. Dann bleibt es, mit ERLAUBT-Eintrag samt Begründung im Feldnamen-Wächter. Liest oder schreibt der Pfad dagegen `display_config.hourly_metrics`/`hourly_metric_formats` eines Abos, wird er auf die Tabelle umgestellt und die Felder entfallen aus dem Request-Schema.

**Schritt 7, Tests und Doku:** Fixtures wechseln auf `placements` (Ausgabe soll gleich bleiben, also umstellen statt löschen). Der Golden-Test bleibt unverändert im Erwartungswert. `api_contract.md` verzeichnet die zehn Namen als entfernt; Nachtrag in der #3122-Spec.

## Expected Behavior

- **Input:** Laden, Rendern und Speichern von Trips und Ortsvergleichen, auch mit Bestandsdateien, die noch Altfelder tragen.
- **Output:** Jede Ausgabe in allen vier Kanälen ist zeichengleich zum Stand vor dem Rückbau. Gespeicherte Dateien enthalten nach einem Python-Speichern keinen der zehn Namen mehr.
- **Side effects:** Beim Speichern über Python verschwinden vorhandene Altfelder aus der Datei; alle anderen Felder bleiben unverändert (Merge). Es gibt keinen Datenlauf über Bestandsdaten.

## Acceptance Criteria

- **AC-1:** Given ein Trip und ein Ortsvergleich mit Tabelle, einmal ohne und einmal mit gesetzten Altfeldern (alle zehn Namen) im Eingang / When das Briefing in E-Mail (HTML und Text), Telegram, SMS und Premium-SMS erzeugt wird / Then ist die Ausgabe jedes Kanals zeichengleich, und sie ist zeichengleich zum bisherigen Golden-Stand.
  - Test: `tests/tdd/test_3237_golden_vier_kanaele.py` läuft unverändert im Erwartungswert grün; je Kanal Byte-Vergleich sauber gegen mit Altfeldern, ohne Mock.

- **AC-2:** Given ein gespeicherter Trip und ein gespeicherter Ortsvergleich, deren Datei noch Altfelder in `display_config`, `report_config` und auf oberster Ebene trägt / When sie geladen und über den Speicherpfad erneut gespeichert werden / Then enthält die gespeicherte Datei keinen der zehn Namen mehr, und alle übrigen Felder (auch unbekannte Zusatzfelder, `placements`, Empfänger, Orte) sind unverändert erhalten.
  - Test: Datei mit allen zehn Altfeldern plus einem Zusatzfeld anlegen, über `save_trip`/`update_trip`/`save_location` speichern, JSON neu lesen und Namen sowie Erhalt der übrigen Schlüssel prüfen.

- **AC-3:** Given Modell und Lader nach dem Rückbau / When ein Abo mit Altfeldern geladen wird / Then trägt das Modellobjekt keine Attribute `multi_day_trend_reports`, `show_outlook`, `outlook_metrics`, `outlook_metric_formats`, `per_channel_layouts`, `per_report_layouts`, und die Alt-Werte beeinflussen weder Anzeige noch Rendern.
  - Test: Abo mit gesetzten Altfeldern laden, Attribute am Objekt abfragen (nicht vorhanden) und Ausgabe gegen das Abo ohne Altfelder vergleichen.

- **AC-4:** Given zwei verschiedene Nutzer mit je einem Trip und einem Ortsvergleich mit Altfeldern in den Dateien / When für Nutzer A gespeichert wird / Then sind nur A's Dateien bereinigt, B's Dateien sind byteweise unverändert, und die Speicherung nutzt die echte `user_id` (nie `"default"`).
  - Test: Zwei Nutzerordner anlegen, A speichern, Dateien beider Nutzer vorher/nachher vergleichen; Zugriff mit `user_id="default"` trifft keine der beiden Dateien.

- **AC-5:** Given die E-Mail-Renderer (HTML und Text) / When sie ohne Parameter `show_outlook` aufgerufen werden / Then erscheint der Ausblick genau dann, wenn `placements.outlook_reports` Berichte nennt, und fehlt bei leerer Liste; die Signatur der Funktionen enthält `show_outlook` nicht mehr.
  - Test: Trip-Briefing mit `outlook_reports` gefüllt und leer rendern, Ausblick-Abschnitt in der Mail prüfen; Signaturprüfung per `inspect.signature` auf Abwesenheit des Parameters.

- **AC-6:** Given Ortsvergleiche mit und ohne `rows` / When die Tabelle über Karte, Briefing und Grundauswahl aufgelöst wird / Then gibt es keinen Parameter und keine Lesestelle `outlook_enabled` mehr (Resolver, Placements-View, `placements_aus_grundauswahl`, Soll-Hook, Go-Modell), und das Ergebnis ist für alle Bestandsabos mit `outlook_enabled=true` unverändert; die Tabelle eines Abos ohne `rows` trägt `outlook_reports` nach Grundauswahl.
  - Test: Abo ohne `rows` und Abo mit `rows` auflösen; Vergleich mit Golden-Wert; Go-Test lädt und schreibt ein Preset-JSON mit `outlook_enabled` ohne Fehler und ohne das Feld im Struct; Soll-Hook liefert dasselbe Soll wie zuvor.

- **AC-7:** Given der Feldnamen-Wächter `tests/test_altfeld_namen_sperre.py` / When er Backend-Code (`src`, `api`, `internal`, `cmd`, `.claude/hooks`, `scripts`) prüft / Then findet er keinen der zehn Namen außer den Einträgen der ERLAUBT-Tabelle, jeder Eintrag trägt Grund (mindestens 20 Zeichen) und Ablaufdatum.
  - Test: Wächter grün auf dem Repo; Selbstnachweis mit synthetischem Quelltext (Verstoß erkannt, erlaubter Eintrag besteht, abgelaufenes Datum lässt den Test rot werden, zu kurzer Grund wird abgelehnt) (`# doc-compliance-test`).

- **AC-8:** Given der Import-Wächter `tests/test_altpfad_import_sperre.py` / When er den Produktionscode prüft / Then enthalten `VERBOTEN` zusätzlich `resolve_hourly_metric_formats` (und `normalize_outlook_metric_formats`, falls gelöscht), und kein Produktionscode importiert oder ruft sie auf.
  - Test: Wächter grün; Selbstnachweis mit synthetischem Aufruf der gelöschten Funktion wird erkannt (`# doc-compliance-test`).

- **AC-9:** Given das Request-Schema der Validator-Vorschau mit `hourly_metrics`/`hourly_metric_formats` / When die Entscheidungsregel aus Implementation Details Schritt 6 angewendet wird / Then bleibt das Schema mit begründetem ERLAUBT-Eintrag, wenn es nur Request-Parameter ohne Store-Bezug ist, andernfalls ist es auf die Tabelle umgestellt und die Felder sind entfernt; in beiden Fällen liefert die Vorschau dieselbe Mail wie zuvor.
  - Test: Vorschau-Endpunkt mit und ohne die Request-Felder aufrufen und Ausgabe gegen den bisherigen Stand vergleichen; Wächter AC-7 belegt den Eintrag oder die Abwesenheit.

- **AC-10:** Given die Skripte `migrate_2454_derived_children.py`, `backfill_display_config_issue111.py` und `send_gate_test_mails.py` / When der Rückbau abgeschlossen ist / Then sind die beiden Einmal-Skripte gelöscht (oder mit Aufrufer-Nachweis in der Spec-Notiz begründet behalten), und `send_gate_test_mails.py` baut seine Test-Abos mit `placements` und enthält keinen der zehn Namen.
  - Test: Import und Trockenlauf von `send_gate_test_mails.py` (ohne Versand) erzeugt Abos ohne Altfelder; Wächter AC-7 deckt `scripts/` ab; Kernschicht bleibt ohne die gelöschten Skripte grün.

- **AC-11:** Given Tests, die bisher Altfelder als Fixtures setzten / When sie auf `placements` umgestellt sind / Then bleibt die Kernschicht (Python-Dateien einzeln benannt, `go test ./...`) grün, und es wurde kein Test nur gelöscht, um Rot zu vermeiden (Löschung nur bei gelöschten Funktionen).
  - Test: Kernschicht-Läufe der betroffenen Testdateien und `go test ./internal/...` grün; Diffstatistik in der Validierung weist gelöschte Tests je einer gelöschten Funktion zu.

## Definition of Done

- AC-1 bis AC-11 durch Kern-Tests ohne Mock grün; `go test ./internal/...` grün.
- Golden-Vier-Kanal-Test (Mail HTML/Text, Telegram, SMS, Premium-SMS) für Trip und Ortsvergleich zeichengleich mit und ohne Altfelder.
- Feldnamen-Wächter und Import-Wächter grün, Selbstnachweise grün.
- Staging: Trip und Ortsvergleich speichern, Briefing-Mails über die Mail-Validatoren ohne SOLL-Verletzung.
- Live auf Produktion, Selftest Exit 0. Keine Änderung an Gate-Konfiguration.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Abo mit und ohne Altfelder WHEN vier Kanäle rendern THEN zeichengleich und gleich Golden-Stand (AC-1)
- [ ] Test 2: GIVEN Datei mit allen zehn Altfeldern plus Zusatzfeld WHEN speichern THEN Altfelder weg, Rest erhalten (AC-2)
- [ ] Test 3: GIVEN Abo mit Altfeldern WHEN laden THEN Modell ohne Alt-Attribute, Ausgabe unverändert (AC-3)
- [ ] Test 4: GIVEN zwei Nutzer WHEN A speichert THEN nur A bereinigt, B byteweise gleich, kein `"default"` (AC-4)
- [ ] Test 5: GIVEN E-Mail-Renderer WHEN `outlook_reports` gefüllt/leer THEN Ausblick an/aus, Signatur ohne `show_outlook` (AC-5)
- [ ] Test 6: GIVEN Ortsvergleich mit/ohne `rows` WHEN auflösen THEN ohne `outlook_enabled` gleiches Ergebnis; Go-Preset-Roundtrip ohne Feld (AC-6)
- [ ] Test 7: GIVEN Feldnamen-Wächter WHEN Repo und Selbstnachweis THEN Verstoß erkannt, ERLAUBT-Regeln greifen (AC-7)
- [ ] Test 8: GIVEN Import-Wächter WHEN gelöschte Funktion aufgerufen THEN erkannt (AC-8)
- [ ] Test 9: GIVEN Validator-Vorschau WHEN mit/ohne Request-Felder THEN gleiche Mail (AC-9)
- [ ] Test 10: GIVEN `send_gate_test_mails.py` WHEN Trockenlauf THEN Abos ohne Altfelder (AC-10)
- [ ] Test 11: GIVEN umgestellte Fixtures WHEN Kernschicht und Go-Tests THEN grün, keine stillen Löschungen (AC-11)

Test-Politik: kein Mock-Theater, echte Daten und Dateien, keine Dateiinhalt-Checks außer den Wächtern (`# doc-compliance-test`). Die Kern-Schicht läuft deterministisch ohne Netz; die Live-Prüfung der Mail-Validatoren läuft in `/e2e-verify`.

## Known Limitations

- Das Trip-Frontend schreibt bis #3297/#3298 weiter Altfelder an die API; sie bleiben wirkungslos, und Python-Speichern entfernt sie wieder. Über reine Go-Schreibwege (ohne Python) bleiben sie bis zum Datenlauf #3351 auf der Platte. Das ist bewusst (Schnitt-Entscheidung 25.11.).
- Bestandsdaten (Prod: u. a. `multi_day_trend_reports` 10 Fundstellen, `outlook_enabled` 4, `show_outlook` 3) und `default/compare_presets.json` bleiben bis #3351 unverändert.
- Gate-Konfiguration und menschliche Sperren (override) werden nicht angefasst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (ADR-0124 Nr. 6 und Nr. 8)
- **Rationale:** ADR-0124 hat entschieden, dass `outlook_reports` die Altfelder `show_outlook`, `multi_day_trend_reports` und `outlook_enabled` ersetzt und die Tabelle die einzige Quelle ist. Dieses Paket vollzieht den Rückbau im Backend ohne Verhaltensänderung und widerspricht keiner früheren Entscheidung; der Verzicht auf einen Go-Strip ist eine Umsetzungsentscheidung dieser Spec, kein Architekturwechsel.

## Changelog

- 2026-11-25: Initial spec created (B6b-3, Issue #3277, Epic #3122; Schnitt: Code-Rückbau ohne Frontend und Datenlauf).
