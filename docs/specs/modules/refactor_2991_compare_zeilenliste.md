---
entity_id: refactor_2991_compare_zeilenliste
type: refactor
created: 2026-11-26
updated: 2026-11-26
status: draft
version: "1.0"
workflow: refactor-2991-compare-zeilenliste
tags: [compare, renderer, klartext, html, refactor, "#2991", "#1986"]
---

# Ortsvergleich-Mail: Klartext- und HTML-Uebersichtszeilen aus einer Zeilenliste (#2991)

## Approval

- [ ] Approved

## Purpose

Die Uebersichtszeilen der Ortsvergleich-Mail werden heute zweimal entschieden: der HTML-Teil waehlt sie aus `CV2_ZEILEN` (`_visible_metrics`), der Klartext-Teil fuehrt eine eigene Tabelle mit eigener Sortierung und eigenem Filter (`_PLAIN_ROWS_UNSORTED`, `_sort_by_cv2_order`, `_ordered_rows`). Dieses Refactoring macht `CV2_ZEILEN` samt einem gemeinsamen Filter zur einzigen Quelle fuer Zeilenmenge, Reihenfolge und Auswahl-Luecke; der Klartext behaelt nur noch eine reine Format-Zuordnung je Zeilenschluessel (PO-Auftrag #1986 NEU-10: kein doppelter Code fuer dieselbe Aufgabe). Fuer Nutzer aendert sich nichts Sichtbares, ausser dass der HTML-Teil eine doppelt gespeicherte Metrik nur noch einmal zeigt (wie Klartext, Telegram und SMS schon heute).

## Source

- **File:** `src/output/renderers/email/compare_html.py` (Zeilenliste und Filter), `src/output/renderers/comparison.py` (Klartext, Telegram-Sicht)
- **Identifier:** `select_cv2_rows()` (neu), `_visible_metrics()`, `_PLAIN_FMT` (neu), `_PLAIN_ROWS` (abgeleitet); entfallen: `_PLAIN_ROWS_UNSORTED`, `_DAILY_PLAIN_ROWS`, `_sort_by_cv2_order`, `_ordered_rows`

Schicht-Zuordnung: ausschliesslich Python-Core (`src/output/renderers/`). Go-API, Frontend und Datenmodell bleiben unberuehrt.

Querschnitts-Pruefpunkte:

- **Trip/Ortsvergleich-Teilung:** Keine neue Komponente; zwei Compare-eigene Renderer-Pfade werden auf eine Quelle zurueckgefuehrt (kein Pendant-Verstoss, #1170).
- **Mandantentrennung:** Reine Renderer-Logik ohne Nutzerdaten, keine `user_id` gelesen oder geschrieben; kein Zwei-Nutzer-Test noetig.
- **Kanaele:** Telegram, Compact-Mail, Orte-SMS und Premium-SMS bleiben unveraendert (AC-5, AC-6). Weder Briefing- noch Alarm-Inhalt aendert sich.

## Scope

**Drin:** gemeinsamer Zeilenfilter `select_cv2_rows`; Klartext nimmt dessen Zeilenliste; Klartext-Format als reine Zuordnung `_PLAIN_FMT` mit Import-Pruefung gegen die CV2-Schluessel; Auswahl-Luecke zaehlt in beiden Fassungen gegen dieselbe Schluesselmenge; Entfernen der Alt-Mechanik; abgeleitete Sichten `_PLAIN_ROWS`, `_PLAIN_ROWS_BY_ID`, `_NIE_EINGESTELLT_IDS` bleiben fuer Telegram, Compact, Orte-SMS und Placements bestehen.

**Nicht drin:** Format-Angleichung (`213°` im Klartext gegen `213 °` im HTML, `4h` gegen `4 h`, `-` gegen `–`); gemeinsame Stundenzellen-Schleife; Abschnitts-/Ueberschriftenlogik je Ort; Legenden-Bedingung; Einfach-Form-Doppel (`_friendly_overview_text`/`_friendly_overview_html`); Trip-Pfad. Siehe Known Limitations (Folge-Issue #3425).

## Estimated Scope

- **LoC:** ca. -60 bis -90 netto in Produktion, Tests ca. +80; deutlich innerhalb von +/-250
- **Files:** 2 Produktionsdateien, 1 neue und 1 angepasste Testdatei
- **Effort:** small bis medium

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | `select_cv2_rows(rows, enabled_metrics)` neu; `_visible_metrics` nutzt ihn und stellt die Warnzeile voran; Docstring von `rowless_count` auf neuen Filter angepasst |
| `src/output/renderers/comparison.py` | MODIFY | `_PLAIN_FMT` mit Import-Pruefung; `_PLAIN_ROWS` als abgeleitete Sicht; Zeilenwahl und `rowless_count` im Klartext ueber den gemeinsamen Filter; Alt-Mechanik geloescht |
| `tests/unit/test_compare_plaintext_html_rows_one_list.py` | CREATE | Kreuzvergleich Klartext gegen HTML, Duplikat, Auswahl-Luecke, Format-Zuordnung, abgeleitete Sichten |
| `tests/unit/test_compare_metric_default_order_ssot.py` | MODIFY | Tests auf `_sort_by_cv2_order` und `_PLAIN_ROWS_UNSORTED` auf die neue Import-Pruefung und die abgeleitete Sicht umstellen |

Falls Importe brechen (voraussichtlich nicht, die Sichten bleiben): `tests/helpers/compare_order.py` (liest `_PLAIN_ROWS`) und `tests/tdd/test_channel_metric_matrix.py`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CV2_ZEILEN` / `build_cv2_metrics` (`compare_html.py`) | Konstante/Funktion | SSOT der Uebersichtszeilen und ihrer Standardfolge (#1356) |
| `derive_row_labels` | Funktion | Zeilenbeschriftung, bereits geteilt |
| `rowless_count`, `selection_gap_notice` | Funktionen | Auswahl-Luecken-Hinweis, bereits geteilt |
| `_metric_value`, `_fmt_overview_cell` | Funktionen | Wertquelle und Zellformat, unveraendert |
| `tests/helpers/compare_order.py` | Test-Helfer | `klartext_uebersicht_labels`, `html_uebersicht_labels` (vorhanden) lesen Beschriftungen aus fertigen Ausgaben |
| Telegram `render_compare_telegram`, `compact_compare.py`, `orte_sms.py`, `placements_view_service.py` | Konsumenten | Lesen `_PLAIN_ROWS`/`_PLAIN_ROWS_BY_ID`/`_NIE_EINGESTELLT_IDS`; muessen unveraendert bleiben |
| ADR-0127, Spec `refactor_2989_compare_default_order_ssot.md`, `paritaets_bestandsaufnahme.md` | Doku | Leitentscheidung ein Katalog/eine Verarbeitung; Geschwister-Refactorings NEU-8/NEU-9 |

## Implementation Details

1. **Ein Filter.** `select_cv2_rows(rows, enabled_metrics)` in `compare_html.py`, herausgezogen aus `_visible_metrics`: `None` ergibt alle Zeilen (ohne `warn`), `[]` ergibt keine, `warn` wird entfernt, Duplikate fallen per `dict.fromkeys` weg, unbekannte IDs werden uebersprungen. Die Reihenfolge ist die von `enabled_metrics` (bei `None` die von `rows`).
2. **HTML.** `_visible_metrics` ruft den Filter auf und stellt die Warnzeile (sofern `alerts_enabled`) voran; Verhalten sonst unveraendert (Warnzeile immer erste Zeile, AC-7 aus #1359).
3. **Klartext-Zeilen.** An der Zeilenwahl (heute `_ordered_rows(_PLAIN_ROWS, ...)` plus `_CV2_BY_KEY`-Nachschlag) wird `select_cv2_rows(CV2_ZEILEN, enabled_metrics)` verwendet; Labels weiter ueber `derive_row_labels(..., form="long")`.
4. **Klartext-Format.** `_PLAIN_FMT: dict[str, formatter]` je Zeilenschluessel, ohne eigene Reihenfolge und ohne Label-Spalte. Beim Import wird geprueft, dass die Schluesselmenge genau den CV2-Schluesseln ohne `warn` entspricht; Abweichung wirft `ValueError` mit Nennung des Schluessels (ersetzt das fail-fast von `_sort_by_cv2_order`).
5. **Abgeleitete Sichten.** `_PLAIN_ROWS = tuple((k, f"vergleich.zeile.{k}", _PLAIN_FMT[k]) for k in CV2-Schluessel ohne warn)`; `_PLAIN_ROWS_BY_ID` und `_NIE_EINGESTELLT_IDS` werden daraus gebildet wie bisher. Telegram, Compact, Orte-SMS und Placements sehen dieselben Werte wie vorher.
6. **Auswahl-Luecke.** Beide Pfade zaehlen `rowless_count` gegen dieselbe Schluesselmenge (CV2 ohne `warn`).
7. **Entfernt:** `_PLAIN_ROWS_UNSORTED`, `_DAILY_PLAIN_ROWS` (als Teilliste), `_sort_by_cv2_order`, `_ordered_rows`.

**Dedup-Folge:** `_visible_metrics` dedupliziert heute nicht (`compare_html.py:903`), `_ordered_rows` schon. Durch den gemeinsamen Filter zeigt HTML eine doppelt gespeicherte Metrik nur noch einmal. Das ist die einzige sichtbare Aenderung; sie gleicht HTML an Klartext, Telegram, SMS und `rowless_count` an und ist kein Produkt-Zielkonflikt.

## Expected Behavior

- **Input:** `render_compare_email(...)` mit beliebigem `enabled_metrics` (`None`, `[]`, Teilmenge, Duplikate, unbekannte IDs, `warn`).
- **Output:** Klartext- und HTML-Uebersicht fuehren dieselben Zeilen in derselben Reihenfolge (HTML zusaetzlich die Warnzeile vorn); Zellwerte und Formate bleiben byte-gleich (Golden-Snapshot).
- **Side effects:** Keine. Keine Datenmigration, keine neuen Permissions, keine AppStorage-Keys, keine Kanal-Aenderung ausser der HTML-Dedup.

## Test Plan

### Automated Tests (TDD RED)

Neue Datei `tests/unit/test_compare_plaintext_html_rows_one_list.py` (Kern-Schicht, deterministisch, ohne Netz, echte Renderer, kein `Mock`/`patch`/`MagicMock`). Zeilenbeschriftungen werden ueber `klartext_uebersicht_labels` und `html_uebersicht_labels` aus `tests/helpers/compare_order.py` aus der fertig gerenderten Mail gelesen.

- [ ] Test 1: GIVEN eine gerenderte Vergleichsmail / WHEN `enabled_metrics` je `None`, `[]`, Teilmenge in eigener Reihenfolge, Duplikat, unbekannte ID und Liste mit `warn` ist / THEN sind Klartext- und HTML-Uebersichtsbeschriftungen (ohne Warnzeile) in Menge und Reihenfolge gleich (parametrisiert).
- [ ] Test 2: GIVEN `enabled_metrics` mit einer doppelt gespeicherten Metrik / WHEN die Mail gerendert wird / THEN kommt ihre Zeile in Klartext und HTML genau einmal vor (RED: HTML zeigt sie vorher zweimal).
- [ ] Test 3: GIVEN eine Auswahl mit nicht darstellbaren Eintraegen / WHEN beide Fassungen gerendert werden / THEN steht derselbe Auswahl-Luecken-Hinweis mit gleicher Zahl in beiden.
- [ ] Test 4: GIVEN `_PLAIN_FMT` und `CV2_ZEILEN` / WHEN die Schluesselmengen verglichen werden / THEN sind sie gleich (ohne `warn`); eine absichtlich abweichende Zuordnung, ueber die Pruef-Funktion injiziert (keine Mocks), bricht mit `ValueError` ab, der den Schluessel nennt.
- [ ] Test 5: GIVEN die abgeleiteten Sichten / WHEN `_PLAIN_ROWS`, `_PLAIN_ROWS_BY_ID`, `_NIE_EINGESTELLT_IDS` gelesen werden / THEN haben sie Reihenfolge, Label-Schluessel `vergleich.zeile.<key>` und Formate wie vorher, `_NIE_EINGESTELLT_IDS` entspricht den CV2-Schluesseln ohne `warn` mit `len >= 20`.
- [ ] Test 6: GIVEN der Compact-Mail-, Orte-SMS- und Placements-Pfad / WHEN sie ohne eingestellte Metriken laufen / THEN liefern sie dieselbe Menge wie vorher (ueber bestehende Tests, siehe Regressionsanker).
- [ ] Test 7: GIVEN die Alt-Mechanik / WHEN das Modul importiert und mit `enabled_metrics` mit Duplikaten gerendert wird / THEN verhalten sich Klartext und HTML ueber die eine Zeilenliste (Verhaltensnachweis ueber Test 1 und 2; ein Namensabgleich ist hoechstens als `# doc-compliance-test` markiert).

Regressionsanker (unveraendert gruen): `tests/test_compare_top_n_render_invariance.py` mit `tests/fixtures/compare_mail_structure_golden.json`, `tests/unit/test_compare_mail_plaintext_html_label_parity.py`, `tests/unit/test_compare_metric_parity.py`, `tests/tdd/test_channel_metric_matrix.py` (Telegram), `tests/tdd/test_issue_1125_plaintext_metrics.py`.

Hinweis zu RED: Test 2 und Test 4 schlagen vor der Umsetzung fehl (HTML-Dedup bzw. `_PLAIN_FMT` fehlt); Test 1 und 3 sind Wachter und koennen vorab gruen sein, bleiben aber als Regressionsschutz.

## Acceptance Criteria

- **AC-1:** Given eine Ortsvergleich-Mail mit `enabled_metrics` gleich `None`, `[]`, einer Teilmenge in eigener Reihenfolge, einer Liste mit Duplikat, einer unbekannten ID oder mit `warn` in der Liste / When Klartext- und HTML-Fassung gerendert werden / Then fuehren beide Uebersichten (HTML ohne die Warnzeile) dieselben Zeilen in derselben Reihenfolge.
  - Test: `tests/unit/test_compare_plaintext_html_rows_one_list.py::test_klartext_und_html_zeilen_gleich` (parametrisiert ueber die sechs Faelle, liest Beschriftungen mit `klartext_uebersicht_labels` und `html_uebersicht_labels`).

- **AC-2:** Given eine Auswahl, in der dieselbe Metrik doppelt gespeichert ist / When die Mail gerendert wird / Then erscheint die Zeile in Klartext und in HTML genau einmal (sichtbare Aenderung nur im HTML-Teil).
  - Test: `tests/unit/test_compare_plaintext_html_rows_one_list.py::test_duplikat_erscheint_einmal` zaehlt die Zeile in beiden Fassungen.

- **AC-3:** Given eine Auswahl mit Eintraegen ohne Zeilendefinition / When beide Fassungen gerendert werden / Then zeigen Klartext und HTML denselben Auswahl-Luecken-Hinweis mit derselben Anzahl.
  - Test: `tests/unit/test_compare_plaintext_html_rows_one_list.py::test_auswahl_luecke_zaehlt_gleich` vergleicht die Hinweiszeile beider Fassungen.

- **AC-4:** Given die Klartext-Format-Zuordnung und `CV2_ZEILEN` / When das Modul importiert bzw. die Pruefung ausgefuehrt wird / Then deckt die Zuordnung exakt die CV2-Schluessel ohne `warn` ab, und jede Abweichung bricht mit einem Fehler ab, der den betroffenen Schluessel nennt.
  - Test: `tests/unit/test_compare_plaintext_html_rows_one_list.py::test_format_zuordnung_deckt_cv2_schluessel` plus `::test_abweichung_nennt_schluessel` (absichtlich abweichende Eingabe, keine Mocks).

- **AC-5:** Given die Konsumenten Telegram, Compact-Mail, Orte-SMS und Placements / When sie nach dem Umbau laufen / Then sind ihre Ausgaben unveraendert, `_PLAIN_ROWS`, `_PLAIN_ROWS_BY_ID` und `_NIE_EINGESTELLT_IDS` sind abgeleitete Sichten mit gleichem Inhalt wie vorher, und `_NIE_EINGESTELLT_IDS` entspricht den CV2-Schluesseln ohne `warn` mit mindestens 20 Eintraegen.
  - Test: `tests/unit/test_compare_plaintext_html_rows_one_list.py::test_abgeleitete_sichten_unveraendert` und unveraendert gruen `tests/tdd/test_channel_metric_matrix.py`.

- **AC-6:** Given der bestehende Struktur-Snapshot und der Label-Paritaetstest / When der Umbau fertig ist / Then bleiben `tests/fixtures/compare_mail_structure_golden.json` (ausgewertet in `tests/test_compare_top_n_render_invariance.py`) und `tests/unit/test_compare_mail_plaintext_html_label_parity.py` ohne Aenderung gruen, d. h. Zellwerte und Formate (`213°`, `4h`, `-`) bleiben byte-gleich.
  - Test: beide bestehenden Testdateien ohne Anpassung der Fixture oder Erwartung.

- **AC-7:** Given die Mail wird mit Duplikaten oder fehlerhafter Eingabe gerendert / When die Uebersichtszeilen entstehen / Then stammen sie in beiden Fassungen aus derselben Zeilenliste, und die frueheren Sonderwege (eigene Klartext-Sortierung und eigener Klartext-Filter) liefern kein eigenes Ergebnis mehr.
  - Test: Verhaltensnachweis ueber AC-1 und AC-2 (unterschiedliches Dedup-Verhalten waere dort rot); kein Dateiinhalt-Check als Beweis.

## Definition of Done

- AC-1 bis AC-7 durch automatisierte Tests belegt, alle gruen; Kern-Testschicht gruen; alle 6 CI-Checks gruen.
- Renderer-Commit-Gate: Modus-Matrix-Test und Mail-Validator frisch gruen (Mail-Inhalt betroffen).
- Staging-Verifikation: echt zugestellte Ortsvergleich-Mail besteht `email_spec_validator.py`.
- Folge-Issue #3425 fuer die nicht umgesetzten Doppelungen angelegt.

## Known Limitations

- Bewusst nicht Teil dieses Umbaus (Folge-Issue #3425): Stundenzellen-Schleife (`comparison.py` gegen `_render_hour_row`), Abschnitts-/Ueberschriftenlogik je Ort, Legenden-Bedingung, Einfach-Form-Doppel (`_friendly_overview_text`/`_friendly_overview_html`) und die Format-Angleichung `°`/`h`/`-` gegen `NO_VALUE`.
- Die Formatunterschiede Klartext gegen HTML bleiben erhalten (Variante B, die sie angleicht, wurde verworfen: sie aendert Telegram-/Compact-Breite und den Golden-Snapshot).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt ADR-0127 (ein Katalog, eine Verarbeitung) um und aendert weder Kanaele, Provider, Datenmodell noch Auth. Verworfene Varianten: B (gemeinsamer Zellformatter, aendert sichtbare Formate und den Golden-Snapshot) und C (zusaetzlich Stundenzellen/Abschnitte, sprengt die Scope-Grenze).

## Changelog

- 2026-11-26: Initial spec created (Variante A aus `docs/context/refactor-2991-compare-zeilenliste.md`)
