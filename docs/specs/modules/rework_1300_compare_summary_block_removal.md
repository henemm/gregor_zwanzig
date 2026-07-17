---
entity_id: rework_1300_compare_summary_block_removal
type: module
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [compare, email, renderer, rueckbau, issue-1300, epic-1273]
---

# Rework #1300 — Ortsvergleichs-Mail: Ort-Zusammenfassungssätze entfernen

## Approval

- [ ] Approved

**ADR-Nr.:** — (keine neue ADR; reiner Rückbau nach PO-Entscheid, keine Architektur-Wirkung. Der v2-Vertrag der Compare-Mail aus `issue_1110_compare_mail_v2.md` bleibt unberührt.)

## Purpose

Die mit #1278 (`cb9918b0`) eingeführte Kurz-Zusammenfassung je Ort unter der Vergleichs-Matrix wird ersatzlos aus der Ortsvergleichs-E-Mail entfernt — **PO-Entscheid 2026-07-17: „kein Mehrwert"**. Der Block wiederholt in Prosa, was die Matrix direkt darüber als Zahlen zeigt, und zwar unvollständiger (der Satz-Formulierer kennt nur 6 der 11 Matrix-Metriken). Für ein Briefing-Werkzeug, das unter Zeitdruck gelesen wird, ist das Füllmaterial zwischen Übersicht und Stundenverlauf.

Entfernt wird **die Platzierung, nicht die Maschinerie**: Der Satz-Formulierer ist ein geteilter Trip-Baustein und bleibt unverändert.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `_render_summary_block` (Definition `:483-501`, Aufruf `:966`, Einbau in Blockfolge `:990`)
- **File:** `src/output/renderers/comparison.py`
- **Identifier:** Summary-Block innerhalb `render_comparison_text` (`:165-172`)

> **Schicht-Hinweis:** Ausschließlich **Python-Core / Renderer** (`src/output/renderers/`). **Kein Frontend**, **kein Go**. Der Block war nie über die Oberfläche konfigurierbar — er hing an `display_config.active_metrics`, demselben Feld wie die Matrix-Zeilen. Es gibt daher kein UI-Feld zu entfernen und kein Persistenz-Feld zu erhalten.

## Estimated Scope

- **LoC:** ~-40 Produktivcode, ~-300 Testcode → netto deutlich negativ, weit unter dem 250-LoC-Limit
- **Files:** 2 Produktivdateien (MODIFY), 1 Testdatei (überwiegend DELETE, Rest überführen)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output/renderers/compact_summary.py::format_location_summary` | Geteilter Trip-Baustein | **Nur Import + Aufruf entfernen. Datei NICHT anfassen** — der Trip braucht den Formulierer weiter |
| `compare_html.py::_daily_summary` + `summaries`-Vorberechnung | Matrix-Datenquelle | **Bleibt vollständig unverändert** — speist 5 Matrix-Metriken (#1285), nicht den Summary-Block |
| `render_compare_email` (`comparison.py:196`) | Downstream | Baut `text_body` aus `render_comparison_text:244` — erbt den Rückbau automatisch |
| `render_compare_html` | Downstream | Von Versand (`scheduler_dispatch_service.py:317`) und Vorschau (`compare_preview_service.py:166`) genutzt — beide erben den Rückbau |

## Implementation Details

### 1. HTML-Teil (`compare_html.py`)

- `_render_summary_block` (`:483-501`) **löschen** — inkl. des lokalen `from output.renderers.compact_summary import format_location_summary`
- Aufruf `summary_html = _render_summary_block(locations, enabled_metrics)` (`:966`) **löschen**
- `summary_html` aus der Block-Tuple (`:990`) **entfernen** — nicht auf `""` setzen, sondern austragen

### 2. Text-Teil (`comparison.py`)

- Block `:165-172` **löschen** (Kommentar, Import, `summaries`-Comprehension, `lines.extend`, `lines.append("")`)
- **Leerraum prüfen:** Zwischen der letzten Orts-Übersichtszeile und `"STUNDENVERLAUF"` darf keine doppelte Leerzeile entstehen (der gelöschte Block endete auf `lines.append("")`, davor steht bereits eines aus der Orts-Schleife)

### 3. NICHT anfassen (Anti-Regressions-Liste)

| Symbol | Warum es bleibt |
|---|---|
| `compare_html.py::_daily_summary` (`:349`) | Live-Ableitung; laut `:343` beziehen 5 Matrix-Metriken ihren Wert **ausschließlich** hieraus (#1285) |
| `compare_html.py` `summaries`-Vorberechnung (`:464-469`) | Speist `_render_overview_row` → `_metric_value(loc, key, summaries.get(id(loc)))` (`:407`) |
| `summaries`-Parameter von `_render_overview_table` / `_render_overview_row` | s. o. |
| `compact_summary.py` (ganze Datei) | Geteilter Trip-Baustein |
| `render_compare_telegram` / `render_compare_sms` | Rufen `render_comparison_text` nicht auf — der Block erschien dort nie |

### 4. Tests

Die #1278-Suite `tests/unit/test_compare_location_summary.py` (563 Zeilen) prüft überwiegend das jetzt entfernte Verhalten. Diese Tests prüfen nach dem Rückbau überholtes Verhalten und werden **gelöscht**, nicht repariert (Test-Politik: „sofort fixen ODER löschen, wenn er veraltetes Verhalten prüft").

**Müssen überleben** (prüfen anderes Verhalten, nicht den Block):

| Test | Prüft | Verbleib |
|---|---|---|
| `test_trip_summary_text_unchanged_byte_identical` (`:497`) | Trip-Satz zeichengleich zur aufgezeichneten Ausgabe — der Schutz des geteilten Bausteins | In eine Trip-Summary-Suite überführen |
| `test_hourly_head_no_dead_time_window_string` (`:527`) | #1278-Nebenbefund: kein toter „09–16 Uhr"-String im Stunden-Kopf | In eine Compare-Mail-Suite überführen |
| `test_aggregate_matches_trip_path_same_hourly_data` (`:350`) | **Vor der Löschung prüfen:** Falls dieser Test die `_daily_summary`-Ableitung gegen den Trip-Pfad absichert, ist er Teil des #1285-Schutzes und **bleibt**. Prüft er dagegen den Summary-Satz, fliegt er mit. |

**Namensregel:** Zieldateien nach Verhalten benennen, nicht nach Issue-Nummer. Der issue-nummerierte Korpus wächst nicht weiter (`test_naming_gate.py` blockt neue issue-nummerierte Testdateien).

## Acceptance Criteria

- **AC-1:** Given eine Ortsvergleichs-Mail mit mehreren Orten, die Wetterdaten haben / When die HTML-Fassung gerendert wird / Then erscheint zwischen der Übersichts-Matrix und dem Stundenverlauf-Abschnitt **kein** Zusammenfassungssatz je Ort mehr — kein „Ortsname: 22–31°C, trocken, …"-Muster im gesamten Dokument.

- **AC-2:** Given dieselbe Ortsvergleichs-Mail / When die Klartext-Fassung gerendert wird (der `text_body` derselben multipart-Nachricht) / Then erscheint zwischen der Orts-Übersicht und der Überschrift „STUNDENVERLAUF" **kein** Zusammenfassungssatz und **keine** doppelte Leerzeile als Rückstand des entfernten Blocks.

- **AC-3:** Given ein Ort, dessen Matrix-Werte aus der Live-Ableitung `_daily_summary` stammen (die fünf mit #1285 reparierten Metriken) / When die Vergleichs-Mail nach dem Rückbau gerendert wird / Then zeigen diese Matrix-Zellen **unverändert** ihre Werte — der Rückbau darf die Datenquelle der Matrix nicht beschädigen. Regressionsschutz: #1285 hat genau diese fünf Metriken erst am 2026-07-17 repariert.

- **AC-4:** Given der geteilte Trip-Baustein `CompactSummaryFormatter` / When ein Trip-Zusammenfassungssatz erzeugt wird / Then ist er **zeichengleich** zur vor dem Rückbau aufgezeichneten Ausgabe — der Rückbau hat ausschließlich die Platzierung im Vergleich entfernt, nicht den Formulierer.

- **AC-5:** Given ein Ortsvergleich mit Telegram- und SMS-Ausgabe / When beide gerendert werden / Then ist ihre Ausgabe gegenüber dem Stand vor dem Rückbau **unverändert** — der Block erschien dort nie, und der Rückbau darf sie nicht berühren.

- **AC-6:** Given derselbe Ortsvergleich / When einmal über den Vorschau-Pfad (`compare_preview_service`) und einmal über den Versand-Pfad (`scheduler_dispatch_service`) gerendert wird / Then zeigt **keiner von beiden** den Zusammenfassungsblock — Vorschau und Versand bleiben deckungsgleich (Fehlerklasse #1297: Vorschau zeigt anderes als der Versand).

- **AC-7:** Given die #1278-Testsuite `tests/unit/test_compare_location_summary.py` / When der Rückbau abgeschlossen ist / Then sind alle Tests, die die Anwesenheit des entfernten Blocks prüfen, **gelöscht** (nicht auskommentiert, nicht übersprungen), und die Tests für davon unabhängiges Verhalten — Trip-Zeichengleichheit und der tote Zeitfenster-String — laufen unverändert **grün** in ihrer neuen, verhaltensbenannten Heimat.

## Known Limitations

- **Der Layout-Tab bietet weiterhin „Im Briefing als Detail" an.** Diese Bedienelement-Gruppe verliert mit diesem Rückbau ihr letztes Ziel — sie hat allerdings ohnehin nie gewirkt (schreibt nach `display_config.channel_layouts`, was der Compare-Renderpfad nie liest; verifiziert: `resolve_compare_render_options`, `report_config_resolver.py:166-231`). Ihre Entfernung ist Gegenstand von **#1299**, nicht dieser Scheibe. **Diese Scheibe fasst kein Frontend an.** Zwischenzustand: Die Gruppe ist über die Oberfläche seit S3 (`080e96d8`) ohnehin nicht mehr erreichbar — der Zwischenzustand ist damit für den Nutzer nicht sichtbar.
- **Die Matrix bleibt unvollständig gefärbt.** `sunny_hours`, `cloud_avg`, `snow_depth_cm`, `snow_new_cm` haben keine Severity-Einfärbung; CAPE ebenfalls nicht (→ #1298). Nicht Gegenstand dieses Rückbaus.
- **Der Kopf behauptet weiterhin „+48h".** Hartkodierter String (`compare_html.py:697`), den die Mail nicht einlöst (gerendert wird ein Tag). Bekannter toter Rest derselben Familie wie #1268; nicht Gegenstand dieser Scheibe.

## Verification

- **Kern-Tests:** deterministisch, ohne Netz — echte Render-Ausgabe von `render_compare_html` bzw. `render_comparison_text` gegen aufgezeichnete Fixtures. **Keine** Dateiinhalt-Checks auf den Renderer als Verhaltensnachweis.
- **Renderer-Commit-Gate (#811):** greift, weil `src/output/renderers/email/compare_html.py` gestaged wird. Vor dem Commit müssen frisch vorliegen: (1) `tests/tdd/test_issue_811_mode_matrix.py` grün, (2) erfolgreicher `briefing_mail_validator.py`-Lauf.
- **Fachlicher Mail-Nachweis vor „E2E bestanden":** `.claude/hooks/email_spec_validator.py` gegen eine **echt zugestellte Staging-Mail** aus dem Stalwart-Test-Postfach (`gregor-test@henemm.com`), Marker `X-GZ-Mail-Type: compare`. Nur bei Exit 0 gilt die Verifikation.
