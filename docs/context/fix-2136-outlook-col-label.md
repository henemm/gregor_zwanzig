# Context: fix-2136-outlook-col-label

## Request Summary
Issue #2136: Der 3-Tagesausblick in der E-Mail (HTML + Klartext, Trip UND Ortsvergleich) soll dieselbe Spaltenüberschrift wie die Etappentabelle tragen (`MetricDefinition.col_label` aus dem zentralen Metrik-Katalog), statt zwei eigener, handgepflegter Namenslisten.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/outlook.py` | Kernstück: `render_outlook_table` (Z.82–296, HTML) und `render_outlook_plain` (Z.303–386, Klartext) — beide mit Pfad 1 (Standard/Fallback, hartkodierte Kürzel `Tag/N/D/R/PR/Wind/Böen/Gew`, HTML Z.206–218) und Pfad 2 (konfigurierbar, `c["label"]` aus `outlook_columns()`, HTML Z.160–166 / Klartext Z.331–344). `build_outlook_row()` (Z.480–744) nutzt dieselbe `outlook_columns()`-Quelle für die Werte — Kopf und Werte sind über den Listenindex verbunden. Datei ist laut eigenem Docstring geteilter Baustein für Trip UND Compare. |
| `src/app/metric_catalog.py` | `MetricDefinition`-Dataclass (Z.30ff) mit `col_label`, `label_de`, `compact_label` u. a. `get_col_defs()` (Z.1498–1505) liefert `(col_key, col_label, col_key)`-Tupel — Basis der „richtig gemachten" Kette für die Etappentabelle. **`col_label` ist nur je Größe eindeutig, nicht je Aggregation** (z. B. `temperature` min/max/avg → immer `"Temp"`). |
| `src/output/renderers/compare_outlook_metric_ids.py` | `outlook_columns(metrics, formats=None)` (Z.298–360ff) — heutige Quelle von Pfad 2. Header-Kommentar (Z.310–315) begründet explizit, warum NICHT `col_label` verwendet wird (Temperatur-Kollision + englische Kürzel). Wird zusätzlich von `email/compact.py` und `narrow.py` (Telegram) genutzt — eine Änderung hier wirkt kanalübergreifend. |
| `src/output/renderers/email/helpers.py:308` (`visible_cols`), `src/app/metric_catalog.py:1406ff` (`get_col_defs`) | Vorbild „richtig gemacht" — nur für die Stundentabelle, nicht für den Ausblick. |
| `src/output/renderers/email/helpers.py:560–581` (`build_column_legend`) | Löst NICHT generisch für die ganze Mail auf, sondern nur für `seg_tables` (Etappentabelle). Ausblick-Spalten (`multi_day_trend`) sind darin **nicht** enthalten → AC-5 aus dem Issue ist heute nicht erfüllt, Legende müsste erweitert werden. Aufrufer: `email/html.py:1673–1675`, `email/plain.py:384`. |
| `tests/tdd/test_compare_outlook_metric_selection.py` | `_FIXED_SEVEN_HEADERS` (Z.31) hart geprüft in **einem** Test (Z.374–399, AC-9-Regressionsschutz für Pfad 1). `_ALLOWED_LABELS` (Z.45–48) ist bereits tolerant gegenüber beiden Label-Quellen — 1 von 6 Tests hart betroffen. |
| `tests/tdd/test_outlook_columns_from_metric_ids.py` | `FESTE_SIEBEN` (Z.47) nur als Gegenprobe genutzt (bricht nicht). `_katalog_label()`-Helper (Z.50–57) bindet Erwartungswerte an `compare_metric_catalog` — müsste bei Umstellung mitgezogen werden. |
| `src/output/renderers/email/compact.py`, `src/output/renderers/narrow.py` | Konsumieren `outlook_columns()` ebenfalls (Kurzform-Mail, Telegram) — erben Änderungen automatisch. Alt-Zweig ohne Auswahl druckt dort keine Kopfzeile, daher keine zusätzliche Kürzel-Liste zu ändern. |
| `src/output/renderers/comparison.py:368`, `src/output/renderers/email/compare_html.py:1176,1257` | Compare-Seite ruft dieselben `outlook.py`-Funktionen wie der Trip auf — **strukturell geteilt**, keine Trip-exklusive Datei. |
| `docs/adr/0037-datengetriebener-ausblick-aus-metrik-katalog.md` | **Nicht im Issue erwähnt, aber zentral:** Diese ADR hat die heutige Lösung beschlossen UND im Abschnitt „Verworfene Alternativen" bereits `col_label` als Kopfquelle geprüft und **explizit verworfen** — Begründung: Temperatur-Kollision (min/max/avg → „Temp") + englische Kürzel. Teil-abgelöst durch ADR-0055. |
| `docs/adr/0042-namensform-folgt-der-platzgrenze.md` | Ordnet den 3-Tages-Ausblick der Klasse „voll" (`label_de`, deutsch) zu — im Issue bereits als abzulösen benannt. |
| `docs/adr/0059-compare-ausblick-erbt-grundauswahl.md` | Bestätigt: Trip- und Compare-Ausblick funktionieren seit 2026-08-21 identisch (gemeinsame `compare_outlook_metric_ids.py`) — stützt die Architektur-Einschätzung. |
| `docs/adr/README.md`, `tests/test_adr_index_drift.py` | Ablösungs-Format: neue ADR-Datei + alte Datei bekommt `**Status:** Abgelöst durch ADR-XXXX` + README-Index-Zeile beider Dateien muss übereinstimmen (`# doc-compliance-test` erzwingt das automatisch). |
| `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md:194–205` | PO-Entscheidung 27.07., zitiert dieselbe Begründung wie ADR-0037 — muss laut CLAUDE.md mit „abgelöst durch dieses Issue" fortgeschrieben werden, keine stille Rücknahme. |
| `docs/reference/metric_output_matrix.md` | Führt alle abgeleiteten/handgepflegten Ausgabeorte; Ausblick-Zeile nach Fix fortzuschreiben. Bestätigt: Telegram/Kompaktmail hängen seit #1720 S2 an derselben `outlook_columns()`-Auflösung. |

## Existing Patterns
- **Katalog-getriebene Spaltenkopf-Ableitung** existiert bereits für die Etappentabelle (`get_col_defs()` → `visible_cols()`) — Referenzmuster für den Fix, aber löst NICHT das Aggregations-Kollisionsproblem, weil die Etappentabelle offenbar nicht dasselbe Mehrfach-Aggregations-Problem hat wie der Ausblick.
- **Geteilter Baustein Trip/Compare** (ADR-0059, CLAUDE.md-Vorgabe „möglichst viel Code teilen") — `outlook.py` und `compare_outlook_metric_ids.py` sind bereits das Umsetzungsbeispiel dieses Prinzips.
- **ADR-Ablösung**: Format ist im Repo etabliert (`0030 → 0060`, `0040 → 0043`, `0053 → teilweise 0059`), Index-Drift-Test erzwingt Konsistenz.

## Dependencies
- Upstream: `MetricDefinition`-Katalog (`src/app/metric_catalog.py`), `compare_metric_catalog` (`output/renderers/compare_metric_catalog.py`).
- Downstream: `email/html.py`, `email/plain.py`, `services/trip_report_scheduler.py` (Trip); `renderers/comparison.py`, `email/compare_html.py` (Compare); `email/compact.py`, `renderers/narrow.py` (Kurzform/Telegram) — alle über `outlook_columns()` verbunden.

## Existing Specs
- `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` — muss fortgeschrieben werden.
- Kein bestehender Spec-Eintrag für #2136 selbst.

## Risks & Considerations
1. **ADR-0037 hat exakt diesen Ansatz bereits geprüft und verworfen** (Temperatur-Kollision `temp min/max/avg → "Temp"`). Eine neue Spec MUSS eine technische Antwort auf genau dieses Gegenargument liefern (z. B. Aggregations-Suffix am `col_label`, neue Katalogspalte je Aggregation), sonst wiederholt der Fix einen bereits durchdachten Rückzieher ohne neue Begründung.
2. **Zwei ADRs müssen abgelöst/ergänzt werden** (0037 „Verworfene Alternativen" + 0042 Namensklassen-Tabelle), nicht nur eine wie im Issue-Text angenommen. ADR-Index-Drift-Test beachten.
3. **Ortsvergleich-Berührung ist strukturell unvermeidbar.** `outlook.py` ist vollständig geteilt zwischen Trip und Compare; Pfad 1 (Fallback bei fehlender Auswahl) und Pfad 2 (`outlook_columns()`) werden von beiden Mail-Arten genutzt. Die Projekt-Regel „Ortsvergleich-Themen sind zurückgestellt" (Ausnahme nur #1848) steht in Spannung dazu — **das muss vor/in der Analyse-Phase mit dem PO geklärt werden**, weil die Architektur eine Trip-only-Änderung an dieser Stelle nicht sauber zulässt, ohne die dokumentierte Trip/Compare-Teilungsinvariante zu verletzen.
4. **AC-5 (Legende) ist heute nicht erfüllt** — `build_column_legend` sieht nur `seg_tables`, nicht die Ausblick-Spalten. Muss im Fix mit erweitert werden.
5. Kollateral-Wirkung auf Kurzform-Mail (`compact.py`) und Telegram (`narrow.py`), da beide dieselbe `outlook_columns()`-Quelle lesen — Abgrenzung im Issue („nur Überschriften") sollte explizit auf diese Kanäle ausgeweitet/geprüft werden.
6. Testaufwand überschaubar: 1 Test hart gebunden (`test_missing_outlook_selection_keeps_the_seven_legacy_columns`), 1 Helper (`_katalog_label`) muss mitgezogen werden, Rest bereits tolerant.

## Analysis

### Type
Feature (Enhancement, PO-Ansage 2026-09-06, `[triage:po]`)

### Präzisierung Risiko 1 (Temperatur-Kollision) — Ergebnis der strategischen Analyse

Die `Night`/`DayMin`/`DayMax`-Katalogeinträge lösen die Kollision **nicht**, wie im Context-Dokument zunächst vermutet: Sie haben kein `summary_fields` (`metric_catalog.py:157`) und sind deshalb für den konfigurierbaren Ausblick über `available_aggregations()`/`derived_aggregations()` gar nicht wählbar — sie lösen nur das SMS/Kurzform-Problem (#1484/#1728). Die Kollisionsquelle bleibt `id="temperature"` mit `default_aggregations=("min","max","avg")` und einem `col_label="Temp"` für alle drei.

**Aber:** Seit dem ADR-0037-Datum (27.07.) ist neue, aus anderem Anlass gebaute Infrastruktur entstanden, die die damalige Ablehnung entkräftet:
- `_merge_min_max_pairs()` (`compare_outlook_metric_ids.py:375–426`, PO-Entscheid #1848 A1, 2026-08-20) verschmilzt Min+Max derselben Größe zu einer Spannen-Spalte.
- Der generische Duplikat-Check (`outlook_columns()` Z.366–371, aus #1401 A1) hängt bei Rest-Duplikaten `aggregation_label_de()` an (z. B. Avg neben gemergtem Min/Max).

Diese Mechanik arbeitet generisch auf `columns[i]["label"]`, unabhängig von der Label-Quelle. **Empfehlung:** nur die Quelle in `outlook_columns()` Z.346 von `catalog["label"]` auf `MetricDefinition.col_label` umstellen, Merge-/Dedup-Logik unverändert lassen — kein neues Katalogfeld nötig.

**Offener Wortentscheid (nicht technisch, braucht PO):** Im verbleibenden Restkollisionsfall (z. B. Avg zusätzlich zu Min/Max gewählt) hängt `aggregation_label_de()` deutsche Wörter („Mittel", „Summe") an ein sonst englisches `col_label` — Sprachmix („Temp Mittel"). Alternative wäre ein neues, kurzes Suffix-Vokabular — das würde aber laut ADR-0042 genau die „fünfte Namensliste" erzeugen, vor der die ADR warnt. Empfehlung des Agenten: Sprachmix akzeptieren (selten, nur bei ≥3 gewählten Temperatur-Aggregationen gleichzeitig) statt neuer Namensliste.

**Leitplanke:** `kuerzel_metric_id` (`compare_metric_catalog.py:35–40,129–143`, #2232) ist explizit als „nur SMS-Kürzel, nie Mail-Spaltenkopf" dokumentiert — darf für diesen Fix nicht zweckentfremdet werden.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | Z.310–315 Docstring anpassen, Z.346 Label-Quelle auf `col_label` umstellen (~10–20 LoC) |
| `src/output/renderers/email/outlook.py` (HTML, Z.206–218) | MODIFY | Pfad 1 auf Katalog-`col_label` umstellen (~10 LoC) |
| `src/output/renderers/email/outlook.py` (Klartext, Z.303–386) | MODIFY | Pfad 1 Klartext-Zweig analog (~10–15 LoC) |
| `src/output/renderers/email/helpers.py:560–581` (`build_column_legend`) + Aufrufer `email/html.py:1673–1675`, `email/plain.py:384` | MODIFY | AC-5: Legende auf Ausblick-Spalten erweitern (~20–40 LoC) |
| `tests/tdd/test_compare_outlook_metric_selection.py` | MODIFY | `_FIXED_SEVEN_HEADERS`-Test umschreiben (~10–20 LoC) |
| `tests/tdd/test_outlook_columns_from_metric_ids.py` | MODIFY | `_katalog_label()`-Helper nachziehen (~20–30 LoC) |
| Neue TDD-Datei/-Ergänzung | CREATE | Regressionstest Temperatur-Kollision (AC-4, Pflicht) (~30–50 LoC) |
| `docs/adr/00XX-*.md` (neu) + Statuszeile in 0037 + 0042 + README-Index | CREATE/MODIFY | Löst ADR-0037-Punkt „Verworfene Alternativen" UND ADR-0042-Zeile „3-Tages-Ausblick" ab, dokumentiert warum der 07/26-Einwand heute entkräftet ist (~120–180 LoC Doku) |
| `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md:194–205` | MODIFY | „abgelöst durch #2136" vermerken (~10–15 LoC) |
| `docs/reference/metric_output_matrix.md` | MODIFY | Ausblick-Zeile fortschreiben (~5 LoC) |

### Scope Assessment
- Files: 8–9
- Estimated LoC: ~250–400 (Code+Doku+Tests gemischt; reiner Produktionscode deutlich kleiner, Doku/ADR dominiert)
- Risk Level: MEDIUM (fachlich einfache Renderer-Änderung, aber Architektur-Entscheidungsfläche ADR + Compare-Mitbetroffenheit)

### Technical Approach
1. PO-Klärung Sprachform-Restfall (siehe oben) — vor der Spec.
2. Neues ADR zuerst (löst 0037-Punkt + 0042-Zeile ab, Begründung: nachträglich gebaute Merge-/Dedup-Infrastruktur entkräftet den ursprünglichen Einwand).
3. TDD-Red: neuer Kollisionstest (temperature min+max+avg im Ausblick) zuerst rot schreiben.
4. `outlook_columns()`-Labelquelle umstellen (Pfad 2), Merge-/Dedup-Logik unverändert.
5. Pfad 1 (`outlook.py` HTML + Klartext) — triviale Ersetzung.
6. Legende erweitern (AC-5).
7. Bestehende Tests nachziehen.
8. Spec- und Referenzmatrix-Fortschreibung zuletzt, mit Verweis auf neues ADR.

### Dependencies
Siehe Abschnitt „Dependencies" oben — zusätzlich: Reihenfolge ADR vor Code (Repo-Konvention).

### Open Questions
- [x] Sprachform im Temperatur-Restkollisionsfall (Avg zusätzlich zu Min/Max): **PO-Entscheid 2026-09-15 — Sprachmix akzeptieren** (deutsches `aggregation_label_de()`-Suffix an englisches `col_label`), keine neue Namensliste.
- [x] Ortsvergleich-Mitbetroffenheit: **PO-Entscheid 2026-09-15 — in Ordnung**, kein Konflikt mit „Ortsvergleich-Themen zurückgestellt" für dieses Ticket.
