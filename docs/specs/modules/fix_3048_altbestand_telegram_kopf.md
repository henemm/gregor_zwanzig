---
entity_id: fix_3048_altbestand_telegram_kopf
type: bugfix
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
issue: 3048
workflow: fix-3048-altbestand-telegram-kopf
tags: [loader, trip, metrics, telegram, i18n, epic-3047]
---

# Altbestand-Trip ohne Metriken und Telegram-Kopf in Nutzersprache (#3048, #3052)

## Approval

- [ ] Approved

## Purpose

Ein Trip, dessen Anzeige-Konfiguration keine Metriken enthält (Altbestand oder Import ohne `metrics`), zeigt heute im Überblick der Mail den Standardsatz, in den Etappen- und Nachttabellen derselben Mail aber keine Wertspalten. Der Loader ergänzt künftig den Standardsatz, sodass beide Stellen übereinstimmen. Zusätzlich zeigt der Telegram-Kopf eines Trip-Briefings die Briefing-Art in der Sprache des Nutzers („Abend 15.07.2026“ statt „Evening 15.07.2026“), über denselben Katalog wie die Mail.

## Source

- **File:** `src/app/loader.py`, `src/output/renderers/narrow.py`, `src/output/renderers/email/html.py`
- **Identifier:** `_parse_display_config` (neuer Parameter `trip_standard_bei_leer`), Telegram-Kopf in `render_telegram_bubbles`, Helfer `_briefing_typ` (wandert in ein neutrales Modul, z. B. `src/output/renderers/briefing_typ.py`)

> **Schicht-Hinweis (Template-Pflicht):** Ausschließlich Python-Core (`src/app/`, `src/output/renderers/`) plus Tests/Fixtures unter `tests/`. Frontend und Go-API sind nicht betroffen. Der Ausblick-Hydrations-Fehler im Orte-Editor (F4 aus #3048) ist nach #3061 ausgelagert und nicht Teil dieser Spec.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orte-Teilung:** Die Normalisierung gilt bewusst nur für Trips (Parameter am gemeinsamen Parser); der Orte-Ladepfad (`loader.py` ca. Zeile 1592) bleibt unverändert, damit Orte-Ausgaben sich nicht ändern. Keine neue Komponente mit Pendant.
> - **Mandantentrennung:** Es werden keine Nutzerdaten geschrieben oder verschoben; der Loader liest weiter pro `user_id`. Die Kettentests laden Trips zweier verschiedener Nutzer.
> - **Kanäle:** E-Mail (Überblick und Tabellen, gleicher Standardsatz) und Telegram (Kopf in Nutzersprache) sind betroffen. SMS und Premium-SMS: keine Änderung; Protokoll-Token (Gefahrentypen, `sms_code`, Kürzel) werden ausdrücklich nicht übersetzt.

## Scope

- **Im Scope:** Loader-Normalisierung für Trips mit fehlender oder leerer Metrik-Liste (#3048); Telegram-Kopf eines Trip-Briefings in Nutzersprache über den Mail-Katalog (#3052); Umstellung der zugehörigen Bestandstests, Prüfkatalog-Fälle und der deutschen Telegram-Golden-Datei.
- **Nicht im Scope:** Datenmigration auf der Platte; Orte-Ladepfad; `get_metrics_for_channel`; SMS und Premium-SMS; weitere `.title()`-Stellen; F4 Orte-Editor-Hydration (#3061).

## Estimated Scope

- **LoC:** Quellcode ca. +30/-5, Tests ca. +120/-30
- **Files:** ca. 8 (2 bis 3 Quellcode, Rest Tests/Fixtures)
- **Effort:** low bis medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.trip_metric_ids.DEFAULT_TRIP_METRIC_IDS` | module | einzige Quelle des Standardsatzes (Import innerhalb der Funktion, Importzyklus vermeiden) |
| `auto_distribute` (Loader) | function | bucket/order der ergänzten Einträge |
| `src/i18n/messages/{de,en}/mail.json` (`mail.kopf.typ_*`) | catalog | Briefing-Art in Nutzersprache, bereits vorhanden, kein neuer Text |
| `app.models.get_metrics_for_channel` | function | bleibt unverändert (34 Matrix-Tests in `tests/tdd/test_channel_metric_matrix.py`) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,editor}.json` | fixture | Prüfkatalog: Fälle mit `ausnahme` und Verweis #3048 werden `gruen` |

## Implementation Details

**#3048 (Loader):** `_parse_display_config(..., trip_standard_bei_leer: bool = False)`. Der Trip-Zweig ruft mit `True`. Ist dann `metrics` nicht vorhanden oder eine leere Liste (Fall A laut Doku in `trip_metric_ids.py`), entstehen die Einträge aus `DEFAULT_TRIP_METRIC_IDS` (`enabled=True`, bucket/order per `auto_distribute`, Standard-Formatmodus). Sind Einträge vorhanden, aber alle `enabled=False` (Fall B, „bewusst leer“, #1394), bleibt die Liste leer. Der Orte-Ladepfad ruft ohne den Schalter und ändert sich nicht. `get_metrics_for_channel` bleibt unangetastet; die Korrektur liegt an der Eingangsgrenze, nicht in der Kanal-Auswahl. Dadurch stammen Überblick und Etappen-/Nachttabelle derselben Mail aus derselben Liste. Kein Rückschreiben und keine Migration: Prod und Staging haben 0 betroffene Trips; schreibt ein Python-Pfad einen geladenen Trip später zurück, wird der Standardsatz per Read-Modify-Write persistiert (gewollt).

**#3052 (Telegram-Kopf):** `_briefing_typ(report_type, lang)` zieht aus `email/html.py` in ein neutrales Modul um (eine Quelle für Mail und Telegram, kein Importzyklus). `narrow.py` (ca. Zeile 779, bisher `report_type.title()`) nutzt es. Für `morning`/`evening`/`alert` kommt der Text aus `mail.kopf.typ_*` in `lang`; unbekannte Typen fallen auf `.title()` zurück. Das Datum im Kopf bleibt unverändert. Weitere `.title()`-Stellen (Plain-Betreff-Rückfall, Debug-Text, Gefahrentyp-Tokens) sind nicht im Scope.

**Tests:** N1-Tests (`test_n1_altbestand_ohne_metrics`, Editor-Seite `test_python_seite_trip_tabellen_altbestand`) von Ist auf Soll umstellen (Spalten = Standard-Stundenspalten des Prüfkatalogs); Prüfkatalog-Fälle `ausnahme` mit Verweis #3048 auf `gruen`; deutsche Golden-Datei `tests/golden/telegram_briefing/briefing_normalstil.de.txt` („Morning“ wird „Morgen“), englische bleibt; `test_issue_1001_telegram_bubbles.py` auf die Sprache des Aufrufs prüfen.

## Definition of Done

- AC-1 bis AC-9 sind durch Tests gegen die echte Kette (ohne Mocks) abgedeckt und grün.
- Prüfkatalog führt die bisherigen #3048-Ausnahmen als `gruen`; die 34 Matrix-Tests in `tests/tdd/test_channel_metric_matrix.py` bleiben unverändert grün.
- Auf Staging zeigt ein deutsches Trip-Briefing per Telegram „Morgen …“ bzw. „Abend …“ im Kopf; die Mail bleibt unverändert korrekt.
- Ausgeliefert auf Produktion, Selbsttest grün, #3048 und #3052 geschlossen.

## Test Plan

- **Kern-Schicht (deterministisch, ohne Netz):** Loader-Tests für Fall A (Feld fehlt, leere Liste), Fall B (alle aus) und Orte unverändert, je mit zwei Nutzern; Mail-Kettentests N1 (Trip und Editor-Standard) auf Soll; Prüfkatalog-Fälle; Telegram-Renderer de/en/unbekannter Typ; Mail-/Telegram-Kopf-Gleichheit; Golden-Dateien Telegram de (angepasst) und en (unverändert); Bestandstests `tests/tdd/test_issue_1001_telegram_bubbles.py` und `tests/tdd/test_channel_metric_matrix.py`.
- **Live-E2E-Schicht (in `/e2e-verify`):** Trip-Briefing eines deutschen Testnutzers auf Staging per Telegram auslösen und Kopfzeile prüfen; Trip-Mail per Briefing-Validator gegen das Staging-Postfach.

## Expected Behavior

- **Input:** Trip-Datei mit `display_config` ohne `metrics` oder mit `metrics: []`; Trip-Briefing für Telegram mit `language=de` oder `en`.
- **Output:** Mail-Tabellen und Überblick zeigen denselben Standardsatz; Telegram-Kopf „Abend 15.07.2026“ (de) bzw. „Evening 15.07.2026“ (en).
- **Side effects:** keine; keine Datenmigration.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Anzeige-Konfiguration ohne Feld `metrics` / When die Trip-Mail über die echte Kette Loader und Renderer erzeugt wird / Then zeigen Etappen- und Nachttabelle die Standard-Wertspalten und stimmen mit dem Metriken-Überblick derselben Mail überein.
  - Test: Datei laden, Mail rendern (HTML und Klartext), Spaltenköpfe der Tabellen mit dem Überblick vergleichen; kein Mock, mit Trips zweier verschiedener Nutzer.

- **AC-2:** Given ein Trip mit Anzeige-Konfiguration und `metrics` als leerer Liste / When die Trip-Mail über die echte Kette erzeugt wird / Then zeigen Tabellen und Überblick denselben Standardsatz wie beim fehlenden Feld.
  - Test: wie AC-1 mit `metrics: []`; Ergebnis identisch zu AC-1.

- **AC-3:** Given ein Trip, dessen Metrik-Einträge vorhanden, aber alle ausgeschaltet sind (bewusst leer) / When die Trip-Mail erzeugt wird / Then bleiben die Tabellen ohne Wertspalten und der Standardsatz wird nicht ergänzt.
  - Test: Loader liefert weiter nur ausgeschaltete Einträge; gerenderte Mail enthält keine Standardspalten (Schutz von #1394).

- **AC-4:** Given ein Ort bzw. Orts-Vergleich mit Anzeige-Konfiguration ohne `metrics` / When der Ort geladen und der Vergleich ausgeliefert wird / Then ist die Ausgabe unverändert gegenüber dem bisherigen Stand (kein Standardsatz ergänzt).
  - Test: Orte-Ladepfad vor und nach der Änderung liefert dieselbe Metrik-Liste; der bestehende Orte-Prüfkatalog bleibt grün.

- **AC-5:** Given der Prüfkatalog zu Einstellung gleich Mail mit den bisherigen Ausnahme-Fällen zu #3048 / When die Katalog-Tests laufen / Then sind diese Fälle als `gruen` geführt und bestehen gegen die echte Kette (Trip und Editor-Standard).
  - Test: `fallliste_trip.json` und `fallliste_editor.json` ohne `ausnahme`-Verweis auf #3048; Fall-Tests grün; N1-Tests prüfen den Soll-Zustand.

- **AC-6:** Given ein Trip-Briefing am 15.07.2026 vom Typ Abend und ein Nutzer mit Sprache Deutsch / When die Telegram-Nachricht gerendert wird / Then lautet der Kopf der Briefing-Art „Abend 15.07.2026“.
  - Test: echter Telegram-Renderer mit `lang="de"`, Kopfzeile prüfen; deutsche Golden-Datei zeigt „Morgen“ statt „Morning“.

- **AC-7:** Given dasselbe Trip-Briefing und ein Nutzer mit Sprache Englisch / When die Telegram-Nachricht gerendert wird / Then lautet der Kopf „Evening 15.07.2026“, und die englische Golden-Datei bleibt unverändert.
  - Test: echter Telegram-Renderer mit `lang="en"`; englische Golden-Datei unverändert grün.

- **AC-8:** Given ein Briefing mit unbekanntem Typ (nicht morning, evening oder alert) / When die Telegram-Nachricht gerendert wird / Then fällt der Kopf auf den bisherigen Text in Großschreibung des ersten Buchstabens zurück und das Datum bleibt erhalten.
  - Test: Renderer mit einem unbekannten `report_type`; Kopf beginnt mit der `.title()`-Form, kein Fehler.

- **AC-9:** Given die Mail und die Telegram-Nachricht desselben Briefings / When beide in derselben Sprache gerendert werden / Then stammt die Briefing-Art aus derselben Quelle und ist in beiden identisch.
  - Test: Mail-Kopf und Telegram-Kopf für de und en vergleichen; die Mail-Tests aus #3047 (AC-17) bleiben grün.

## Known Limitations

- Kein Daten-Rückschreiben: Altbestand wird nur beim Laden ergänzt; auf der Platte bleibt er unverändert, bis ein Schreibpfad den Trip speichert.
- Weitere `.title()`-Stellen (Plain-Betreff-Rückfall, Debug-Text) sind nicht Teil dieser Spec; Gefahrentyp-Tokens sind Protokoll und bleiben untranslated.
- F4 (Ausblick-Hydration im Orte-Editor) liegt in #3061.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird keine bestehende Entscheidung geändert. ADR-0104 (Zweisprachigkeit, Katalog, Protokoll-Token nie übersetzen) wird angewendet; die Normalisierung folgt der in `trip_metric_ids.py` dokumentierten Unterscheidung Fall A (fehlt/leer ergibt Standard) und Fall B (alle aus ergibt leer).

## Changelog

- 2026-11-16: Initial spec created
- 2026-11-16: Sektionen Scope, Definition of Done und Test Plan ergänzt (CI-Spec-Gate)
