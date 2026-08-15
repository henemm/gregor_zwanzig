# Context: fix-1849-ausblick-ampelfarben

## Request Summary
Issue #1849: Setzt ein Nutzer im Trip-Editor eine Spaltenauswahl für die
3-Tages-Vorschau, verliert die Ausblick-Tabelle in der Trip-Mail sämtliche
Ampelfarben (nicht nur bei Gewitter, bei jeder Spalte). PO-Entscheid
2026-08-15: Standard-Track, Ortsvergleich wird **mitgefärbt** (bisher schon
farblos, aber nicht absichtlich) — das löst `#1653` AC-6 ab, soweit AC-6
Farblosigkeit implizierte.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/outlook.py` | Enthält beide Zweige: Metrik-Zweig `render_outlook_table()` (`:128-152`, **kein** `bg=`, `return` vor jeder Färbelogik) und Altpfad (`:189-297`, färbt über `_outlook_cell_bg()`/`_catalog_thresholds()`/`_THUNDER_LEVEL_BG`). `build_outlook_row()` (`:609-618`) schreibt `row["cells"]` bereits als **fertig formatierte Strings** — die Rohwerte zum Einfärben existieren im Renderer danach nicht mehr, müssen zusätzlich mitgegeben werden. `_THUNDER_LEVEL_BG` (Gewitter-Sonderfarben, LOW bewusst kein `tone_css`-Ton) ist lokal in `render_outlook_table()` definiert, für den Metrik-Zweig aktuell nicht erreichbar. |
| `src/output/renderers/compare_outlook_metric_ids.py` | `outlook_columns()` (`:105-141`) baut die Spaltenbeschreibung aus der Auswahl — trägt aktuell `label`/`field`/`unit`/`decimals`/`kind`/`aggregation_label`, **kein** `metric_id` (würde für Schwellen-Lookup gebraucht). `format_outlook_value()` formatiert die Zellentexte. |
| `src/output/renderers/compare_metric_catalog.py` | Compare-Katalog-Zeilen tragen `metric_id`/`aggregation` (#1373) — `metric_id`-Werte (z.B. `"wind"`, `"gust"`, `"precipitation"`, `"rain_probability"`, `"thunder"`) sind identisch zu den Strings, die `_catalog_thresholds()` in `outlook.py` bereits benutzt. Keine Übersetzung nötig. |
| `src/app/metric_catalog.py` | `MetricDefinition.display_thresholds: dict` (`yellow`/`orange`/`red`). 10 von den relevanten Katalogeinträgen tragen Schwellen; `snow_depth` z.B. **nicht** (`display_thresholds == {}`) — bleibt dann farblos. **Korrektur:** `temperature` HAT Schwellen (`yellow:28/orange:31/red:34` + Kälte-Varianten) und wird korrekt gefärbt, ursprünglich fälschlich als schwellenloses Beispiel genannt. |
| `src/output/metric_format.py` | `thunder_ampel_band(level)` (`:265-275`, ADR-0025: **einzige Quelle** Stufe→Ampelband) liefert `green`/`yellow`/`orange`/`red`, `None` bei `None`. `NONE`-Stufe würde `"green"` liefern — der Altpfad zeigt bei `NONE` aber **keinen** Hintergrund (kein `_THUNDER_LEVEL_BG`-Eintrag für `NONE`). Muss beim Einfärben bewusst abgefangen werden, sonst neuer grüner Teppich. |
| `src/output/renderers/email/design_tokens.py` | `tone_css(band)` — einzige Quelle für die Hex-Werte je Ampelband (#1801 S1). |
| `src/output/renderers/email/compare_html.py:1242` | Ruft `render_outlook_table(rows, show_acc=False, metrics=outlook_metrics)` — derselbe Metrik-Zweig, jede Änderung dort wirkt automatisch auch hier (Ortsvergleich). |
| `docs/specs/modules/fix_1653_ausblick_tag_nacht_trennung.md` (AC-6, Z.337-345) | Verlangt „Compare-Ausgabe bleibt byte-identisch" — bezieht sich laut Testverweis (`test_trip_outlook_parity.py`/`test_compare_outlook*.py`) auf `cells`/`format_outlook_value` (Zellen-**Text**), nicht auf HTML-Hintergrundfarben. Kein bestehender Test prüft volle HTML-Byte-Gleichheit inkl. `background:`. AC-6 wird durch diesen Fix fachlich abgelöst (Farbe kommt jetzt dazu), der Text bleibt unverändert. |

## Existing Patterns
- **Geteilte Ampel-Quelle:** Numerische Spalten färben über `_outlook_cell_bg(val, thresholds)` + `_catalog_thresholds(metric_id)` (liest `MetricDefinition.display_thresholds`), Gewitter-Spalte über eine feste `_THUNDER_LEVEL_BG`-Tabelle (LOW = eigener heller Gelbton außerhalb des Ampel-Vokabulars, MED/HIGH aus `tone_css()`). Beide Wege existieren nur im Altpfad.
- **Trip/Compare-Teilung:** `render_outlook_table()`/`build_outlook_row()` sind der geteilte Baustein für Trip UND Ortsvergleich (Epic #1301 B4) — eine Änderung im Metrik-Zweig gilt automatisch für beide, wie von der Trip/Compare-Teilungs-Invariante gefordert (keine einseitige Sonderlocke ohne dokumentierte Begründung).
- **Katalog statt Hartcodierung:** #1377 Scheibe B hat den Altpfad bereits auf zentrale Katalog-Schwellen umgestellt (`_catalog_thresholds()`), das ist das Muster, das der Metrik-Zweig übernehmen sollte, statt eine zweite Schwellen-Quelle zu erfinden.

## Dependencies
- **Upstream:** `app.metric_catalog.get_metric().display_thresholds`, `output.metric_format.thunder_ampel_band()`, `output.renderers.email.design_tokens.tone_css()`, `output.renderers.compare_outlook_metric_ids.outlook_columns()`/`format_outlook_value()`.
- **Downstream:** `html.py` (Trip-Mail), `compare_html.py` (Ortsvergleich-Mail) — beide rufen `render_outlook_table()` mit `metrics=` sobald eine Auswahl gesetzt ist. `plain.py`/`comparison.py` rufen `render_outlook_plain()` — dort gibt es (ANSI-frei) ohnehin keine Farbe, betrifft dieses Issue nicht.

## Existing Specs
- `docs/specs/modules/epic_1301_b4_compare_outlook.md` — Ursprungsspec des geteilten Ausblick-Bausteins (AC-1..AC-3, AC-6, AC-8).
- `docs/specs/modules/fix_1653_ausblick_tag_nacht_trennung.md` — AC-6 betroffen (s.o.), Text bleibt unverändert.
- `docs/specs/modules/fix_1841_vorschau_metrik_tagesfenster.md` — jüngster Vorgänger-Fix im selben Modul (Gewitter-Datenquelle statt -Färbung), zeigt das etablierte Diskriminator-Muster `trip_display_config`.
- `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` — Ursprungsspec der Spaltenauswahl (`compare_outlook_metric_ids.py`).

## Analysis

### Type
Bug (nutzersichtbares Fehlverhalten, kein Feature).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | `outlook_columns()` (`:105-141`) Rückgabedict um `"metric_id"` ergänzen (additiv, ~1 Zeile). |
| `src/output/renderers/email/outlook.py` | MODIFY | Neue Modul-Helper `_metric_column_bg(col, raw)`; `build_outlook_row()` (`:609-618`) List-Comprehension → Schleife, füllt `row["cell_bg"]` parallel zu `row["cells"]`; `render_outlook_table()` Metrik-Zweig (`:128-152`) liest `stage.get("cell_bg")` und reicht es an `_otd(..., bg=...)` durch. Import von `severity_for`/`thunder_ampel_band` aus `output.metric_format`. Altpfad (`:60-98`, `:189-297`) bleibt unangetastet. ~30-40 LoC. |
| `tests/tdd/test_trip_outlook_metric_selection.py` bzw. `test_compare_outlook.py` | MODIFY | Neue Fälle: Farbzuweisung Trip UND Compare, NONE-Fall (kein grüner Teppich), fehlende Schwellen (snow_depth bleibt farblos), LOW-Sonderfarbe. ~60-120 LoC. |

### Scope Assessment
- Files: 2 Produktivdateien + 1-2 Testdateien
- Estimated LoC: Produktiv ~30-40 (Budget 250), Test ~60-120 (Budget 500)
- Risk Level: LOW — additive Dict-Keys (`metric_id`, `cell_bg`), gegrepte Aufrufer (`compare_html.py:1168`, `trip_report_scheduler.py:2313`, `outlook.py` intern) lesen selektiv, kein Volldict-Vergleich außer `test_trip_outlook_parity.py:177`, der im unveränderten `metrics is None`-Zweig läuft (kein Konflikt).

### Technical Approach
Bestätigt durch Plan/Sonnet-Subagent (unabhängige Prüfung, Dateien gelesen):

**Wiederverwendbare SSoT-Bausteine bereits vorhanden** (kein Neubau):
- `severity_for(metric_id, value)` (`src/output/metric_format.py:130`) — liest `get_metric(metric_id).display_thresholds`, liefert `"green"/"yellow"/"orange"/"red"/None`. Deckt „keine Schwellen im Katalog" (z.B. `snow_depth`) bereits über `None` ab — **besser als der ursprünglich erwogene `_catalog_thresholds()`/`_outlook_cell_bg()`-Nachbau**, weil es die echte SSoT ist (auch von `helpers._level_from_thresholds` genutzt, Issue #1377 Scheibe A).
- `thunder_ampel_band(level)` (`src/output/metric_format.py:265`, ADR-0025-SSoT) — `NONE` → `"green"`.

**Drei Änderungsschritte:**
1. `outlook_columns()`: `"metric_id": metric_id` zum Rückgabedict ergänzen.
2. `build_outlook_row()`: pro Spalte den ohnehin berechneten Rohwert an `_metric_column_bg(col, raw)` geben — `kind=="ordinal"` → `thunder_ampel_band(raw)` (Band `"green"`/NONE → `""` kein Hintergrund; `"yellow"`/LOW → eigener Hellgelbton `#fbe6c3` wie Altpfad, NICHT `tone_css('yellow')`; `"orange"/"red"` → `tone_css(band)[0]`); `kind=="enum"` (Niederschlagsart) → immer farblos; sonst → `severity_for(col["metric_id"], raw)`, `None`/`"green"` → `""`, sonst `tone_css(band)[0]`. Ergebnis parallel als `row["cell_bg"]`.
3. `render_outlook_table()` Metrik-Zweig: `cell_bg` konsumieren, an `_otd(..., bg=...)` reichen.

Altpfad bleibt komplett unangetastet (separater Codepfad, `metrics is None`) — Byte-Identitäts-Zusicherung (Docstring `outlook.py:10-14`) bleibt automatisch gewahrt.

**Reihenfolge:** `outlook_columns()` → `_metric_column_bg()` (isoliert testbar) → `build_outlook_row()` → `render_outlook_table()` Metrik-Zweig → Gate #811 (`test_issue_811_mode_matrix.py` + beide Mail-Validatoren).

### Dependencies
Bestätigt: `outlook_columns`/`build_outlook_row`/`format_outlook_value`/`display_thresholds` werden außerhalb von `outlook.py` nur von `compare_html.py:1168` und `trip_report_scheduler.py:2313` gelesen — beide selektiv (`c["label"]`, `col["field"]`, `col.get("kind")`), kein Konflikt mit additiven Keys.

### Open Questions
- [x] Ortsvergleich mitfärben? → Ja (PO-Entscheid 2026-08-15).
- [ ] LOW-Sonderfarbe (`#fbe6c3`) im Metrik-Zweig identisch zum Altpfad übernehmen, statt `tone_css('yellow')` zu nutzen? → Empfehlung: ja, für visuelle Konsistenz zwischen beiden Pfaden — als AC festhalten.

## Risks & Considerations
- **Rohwerte fehlen im Renderer.** `render_outlook_table()` bekommt nur `stage["cells"]` (fertige Strings). Um Schwellen anzuwenden, muss entweder `build_outlook_row()` zusätzlich Rohwerte/`metric_id` je Zelle mitgeben (z.B. `row["cell_bg"]` direkt vorberechnet) oder der Renderer bekommt Rohwerte separat. Vorberechnung in `build_outlook_row()` ist näher am Altpfad-Muster (dort passiert die Farbentscheidung auch beim Zeilenbau, nicht erst beim Rendern) — zu klären in der Spec.
- **`_THUNDER_LEVEL_BG` ist lokal.** Muss entweder auf Modulebene gehoben oder dupliziert werden, damit Metrik- und Altpfad dieselbe Farbzuordnung nutzen (ADR-0025 verlangt eine Quelle für Stufe→Band, nicht zwingend für Band→Hex, aber Konsistenz ist hier klar erwünscht).
- **NONE-Sonderfall:** `thunder_ampel_band(NONE)` liefert `"green"` — ohne Abfangen bekäme die Vorschau bei „kein Gewitter" plötzlich einen grünen Hintergrund, den der Altpfad nie hatte. Empfehlung: bei `NONE` keine `bg` setzen (Altpfad-Parität).
- **Fehlende Schwellen bleiben farblos.** Für `metric_id`s ohne `display_thresholds` (z.B. `snow_depth`) gibt es keine Ampelfarbe — das ist Bestandsverhalten (N/D im Altpfad auch immer `bg=""`), keine Regression, aber im AC explizit zu benennen, damit es nicht als Lücke gemeldet wird.
- **Renderer-Commit-Gate (#811):** `outlook.py` liegt unter den Mail-Inhalts-Pfaden — Commit braucht `test_issue_811_mode_matrix.py` grün + erfolgreichen `briefing_mail_validator.py`-Lauf.
- **Zwei Mail-Validatoren:** Trip-Briefing (`briefing_mail_validator.py`) UND Ortsvergleich (`email_spec_validator.py`) sind beide betroffen, weil derselbe Renderer beide Mail-Arten bedient — beide vor „E2E bestanden" laufen lassen (analog #1841-Lehre: „`helpers.py` ⇒ BEIDE Mail-Validatoren").
