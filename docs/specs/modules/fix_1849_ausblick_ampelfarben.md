---
entity_id: fix_1849_ausblick_ampelfarben
type: bugfix
created: 2026-08-15
updated: 2026-08-15
status: approved
version: "1.0"
tags: [ausblick, ampelfarben, metrik-zweig, issue-1849]
---

# Ausblick-Ampelfärbung bei Spaltenauswahl (#1849)

## Approval

- [x] Approved

## Purpose

Setzt ein Nutzer im Trip-Editor oder Ortsvergleich-Editor eine Spaltenauswahl für die 3-Tages-Vorschau, verliert die Ausblick-Tabelle in der Mail sämtliche Ampelfarben (jede Spalte, nicht nur Gewitter). Dieser Fix bringt die Hintergrundfärbung des Metrik-Zweigs in `render_outlook_table()` auf Parität mit dem unveränderten Altpfad (feste sieben Spalten ohne Auswahl), für Trip **und** Ortsvergleich gleichermaßen (Trip/Compare-Teilungs-Invariante).

## Source

- **File:** `src/output/renderers/email/outlook.py`
- **Identifier:** `render_outlook_table()` (Metrik-Zweig, Z.128-152), `build_outlook_row()` (Z.609-618)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `severity_for(metric_id, value)` — `src/output/metric_format.py:130` | function | SSoT für numerisches Ampelband aus `MetricDefinition.display_thresholds`; liefert `None` bei fehlenden Schwellen |
| `thunder_ampel_band(level)` — `src/output/metric_format.py:265` | function | SSoT (ADR-0025) für Gewitterstufe → Ampelband (`green`/`yellow`/`orange`/`red`) |
| `tone_css(band)` — `src/output/renderers/email/design_tokens.py:88` | function | Einzige Quelle für Hex-Werte je Ampelband, liefert `(bg, fg)`-Tupel |
| `get_metric(metric_id)` — `src/app/metric_catalog.py` | function | Katalog-Zugriff, indirekt über `severity_for` |
| `outlook_columns(metrics)` — `src/output/renderers/compare_outlook_metric_ids.py:105` | function | Baut Spaltenbeschreibung aus der Auswahl, bekommt zusätzlich `metric_id` |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | `outlook_columns()` (Z.105-141): Rückgabedict um `"metric_id": metric_id` ergänzen (additiv, ~1 Zeile). |
| `src/output/renderers/email/outlook.py` | MODIFY | Neue Modul-Helper-Funktion `_metric_column_bg(col, raw)`; `build_outlook_row()` (Z.609-618): List-Comprehension für `row["cells"]` zu einer Schleife umbauen, die parallel `row["cell_bg"]` befüllt; `render_outlook_table()` Metrik-Zweig (Z.128-152): `stage.get("cell_bg")` lesen und an `_otd(..., bg=...)` durchreichen. Altpfad (Z.60-98, Z.189-297) bleibt unangetastet. ~30-40 LoC. |
| `tests/tdd/test_trip_outlook_metric_selection.py` bzw. `tests/tdd/test_compare_outlook.py` | MODIFY | Neue Testfälle: Farbzuweisung Trip UND Compare, NONE-Fall, fehlende Schwellen, LOW-Sonderfarbe, Niederschlagsart farblos, Altpfad-Parität. ~60-120 LoC. |

### Estimated Changes
- Files: 2 Produktivdateien + 1-2 Testdateien
- LoC: +90/-10 (Produktiv ~30-40, Test ~60-120)

## Implementation Details

`outlook_columns()` ergänzt pro Spalte `"metric_id": metric_id` im Rückgabedict (additive Erweiterung, bestehende Aufrufer wie `compare_html.py:1168` und `trip_report_scheduler.py:2313` lesen Dict-Keys selektiv).

`build_outlook_row()` baut `row["cells"]` bisher über eine List-Comprehension aus `format_outlook_value(raw, {**col, ...})`. Diese Comprehension wird zu einer Schleife, die zusätzlich `row["cell_bg"]` parallel füllt — je Spalte ein `_metric_column_bg(col, raw)`-Aufruf mit demselben `raw`-Rohwert, der ohnehin für `format_outlook_value()` berechnet wird (kein zweiter Rohwert-Zugriff nötig).

`_metric_column_bg(col, raw)` (neuer Modul-Helper in `outlook.py`, oberhalb von `build_outlook_row()`):

- `col["kind"] == "ordinal"` (Gewitter): `band = thunder_ampel_band(raw)`. `band in (None, "green")` → `""` (kein Hintergrund; deckt sowohl "keine Aussage" als auch NONE-Stufe ab — Altpfad-Parität, kein grüner Teppich). `band == "yellow"` (LOW) → `"background:#fbe6c3;"` (identisch zum Altpfad-Hellgelbton, NICHT `tone_css('yellow')`). `band in ("orange", "red")` → `f"background:{tone_css(band)[0]};"`.
- `col["kind"] == "enum"` (Niederschlagsart): immer `""` — kein Altpfad-Vorbild für eine gefärbte Niederschlagsart-Spalte.
- sonst (numerische Spalten): `band = severity_for(col["metric_id"], raw)`. `band in (None, "green")` → `""` (deckt sowohl fehlende Katalog-Schwellen als auch den grünen Bereich ab). Sonst → `f"background:{tone_css(band)[0]};"`.

`render_outlook_table()` Metrik-Zweig konsumiert `stage.get("cell_bg")` (Liste parallel zu `stage["cells"]`) und reicht den Wert je Zelle an die bestehende `_otd(content, *, bg="", align="center")`-Funktion durch (Signatur existiert bereits, der Metrik-Zweig nutzt `bg` bisher nicht).

Der Altpfad (`metrics is None`, Z.60-98 Helper-Funktionen und Z.189-297 Zeilenbau) bleibt vollständig unangetastet — kein Import, keine Zeile wird dort geändert.

## Expected Behavior

- **Input:** Trip- oder Compare-Vorschau mit gesetzter Spaltenauswahl (`metrics` != `None` an `render_outlook_table()`), Rohwerte je Tag/Spalte aus `SegmentWeatherSummary`.
- **Output:** HTML-Ausblick-Tabelle, deren `<td>`-Zellen bei numerischen Spalten über Katalog-Schwelle, bei Gewitter ab LOW und niemals bei Niederschlagsart einen `background:`-Hintergrund tragen — analog zum Altpfad.
- **Side effects:** keine (reine Renderer-Funktionen, kein Netz-/Fetch-Zugriff).

## Acceptance Criteria

- **AC-1:** Given eine Trip-Vorschau mit gesetzter Spaltenauswahl, die eine numerische Metrik mit Katalog-Schwellen enthält (z.B. Wind) / When ein Tageswert die `orange`-Schwelle dieser Metrik überschreitet / Then trägt die zugehörige `<td>`-Zelle `background:{tone_css('orange')[0]}`.
  - Test: `render_outlook_table()` mit `metrics=[Wind-Auswahl]` und einem Tag mit Wind-Rohwert über der Katalog-`orange`-Schwelle aufrufen, HTML-Output auf `background:` im erwarteten Hex-Wert an der Windspalte prüfen (kein Dateiinhalt-Check, tatsächlicher Renderer-Output).

- **AC-2:** Given eine Ortsvergleich-Vorschau mit gesetzter Spaltenauswahl (identische Metrik wie AC-1) / When derselbe Tageswert über der Schwelle liegt / Then trägt die Ortsvergleich-Ausgabe dieselbe Hintergrundfarbe wie die Trip-Ausgabe.
  - Test: `render_outlook_table(rows, show_acc=False, metrics=[Wind-Auswahl])` (Compare-Aufrufweg über `compare_html.py`-Pfad) mit demselben Rohwert wie AC-1 aufrufen, Ergebnis-Hex mit AC-1 vergleichen — beweist die geteilte Code-Nutzung, nicht nur Parität durch Zufall.

- **AC-3:** Given eine Gewitterspalte in der Auswahl / When der Tageswert Stufe NONE ist / Then trägt die Zelle KEINEN Hintergrund (`bg=""`), obwohl `thunder_ampel_band(NONE)` technisch `"green"` liefert.
  - Test: `_metric_column_bg({"kind": "ordinal"}, ThunderLevel.NONE)` bzw. Renderer-Aufruf mit einem NONE-Tag prüfen, dass die Gewitterzelle keinen `background:`-Stil trägt.

- **AC-4:** Given eine Gewitterspalte in der Auswahl / When der Tageswert Stufe LOW ist / Then trägt die Zelle exakt `background:#fbe6c3;` (Altpfad-Hellgelbton), NICHT `tone_css('yellow')`.
  - Test: Renderer-Aufruf mit LOW-Tag, Hex-Wert der Gewitterzelle auf `#fbe6c3` prüfen und gegen den Rückgabewert von `tone_css('yellow')[0]` abgrenzen (muss ungleich sein).

- **AC-5:** Given eine Gewitterspalte in der Auswahl / When der Tageswert Stufe MED oder HIGH ist / Then trägt die Zelle `background:{tone_css('orange')[0]}` bzw. `background:{tone_css('red')[0]}`.
  - Test: Renderer-Aufruf je einmal mit MED- und HIGH-Tag, Hex-Werte gegen `tone_css('orange')[0]`/`tone_css('red')[0]` prüfen.

- **AC-6:** Given eine numerische Spalte ohne `display_thresholds` im Katalog (z.B. `snow_depth`, Schneehöhe — `get_metric("snow_depth").display_thresholds == {}`) / When ein beliebiger Tageswert vorliegt / Then bleibt die Zelle farblos (`bg=""`) — kein Fehler, kein Absturz.
  - Test: `render_outlook_table()` mit `metrics=[Schneehöhe-Auswahl]` und beliebigem Wert (auch hohem, z.B. 150 cm) aufrufen, Ergebnis enthält keinen `background:`-Stil an der Schneehöhe-Spalte, kein Exception-Wurf.
  - **Korrektur (TDD-RED-Phase):** Die ursprüngliche Spec-Fassung nannte `temperature` als Beispiel — falsch, `temperature` trägt `display_thresholds={"yellow":28,"orange":31,"red":34,...}` und würde bei hohen Werten sehr wohl gefärbt. `snow_depth` (`display_thresholds == {}`) ist die tatsächlich schwellenlose Metrik; `severity_from_thresholds()` liefert dafür `None` (nicht `"green"`), s. `src/output/metric_format.py:141-174`.

- **AC-7:** Given eine Niederschlagsart-Spalte (`kind=="enum"`) in der Auswahl / When ein beliebiger Tageswert vorliegt / Then bleibt die Zelle immer farblos, unabhängig vom Wert.
  - Test: Renderer-Aufruf mit verschiedenen Niederschlagsart-Werten, Ergebnis prüft durchgängig `bg=""` an dieser Spalte.

- **AC-8:** Given eine Trip- oder Compare-Vorschau OHNE gesetzte Spaltenauswahl (`metrics=None`) / When `render_outlook_table()` gerendert wird / Then bleibt die HTML-Ausgabe byte-identisch zum Verhalten vor diesem Fix (Altpfad unverändert).
  - Test: bestehender Parity-Test (`test_trip_outlook_parity.py` bzw. äquivalent) mit `metrics=None` weiterhin grün; zusätzlich expliziter Vergleich der Ausgabe vor/nach diesem Fix bei identischem Input im Altpfad-Zweig.

## Known Limitations

- `docs/specs/modules/fix_1653_ausblick_tag_nacht_trennung.md` AC-6 verlangte „Compare-Ausgabe bleibt byte-identisch" bezogen auf den Metrik-Zweig. Diese Zusicherung galt nachweislich nur für den Zellen-**Text** (`cells`/`format_outlook_value`) — kein bestehender Test prüft volle HTML-Byte-Gleichheit inklusive `background:`-Stilen. Mit diesem Fix bekommt der Metrik-Zweig erstmals Hintergrundfarben; AC-6 wird dadurch fachlich abgelöst (Text bleibt unverändert, Hintergrund kommt neu dazu). Dieser Fix ist **keine** Regression von #1653 AC-6, falls er später fälschlich so gemeldet werden sollte.
- Metriken ohne `display_thresholds` im Katalog (z.B. `snow_depth`) bleiben dauerhaft farblos — Bestandsverhalten, keine Lücke dieses Fixes. `temperature` HAT Schwellen und wird bei hohen/niedrigen Werten korrekt gefärbt (Korrektur ggü. Erstfassung dieser Spec).
- `plain.py`/`comparison.py` (Klartext-Renderer über `render_outlook_plain()`) sind von diesem Fix nicht betroffen — dort gibt es ohnehin keine ANSI-/HTML-Farbe.
- **Renderer-Commit-Gate (#811):** `outlook.py` liegt unter den Mail-Inhalts-Pfaden. Vor Commit MÜSSEN `tests/tdd/test_issue_811_mode_matrix.py` grün sein UND ein erfolgreicher Lauf von `.claude/hooks/briefing_mail_validator.py` (Trip-Briefing) sowie `.claude/hooks/email_spec_validator.py` (Ortsvergleich) vorliegen, bevor „E2E bestanden" gesagt werden darf — beide Mail-Validatoren, weil derselbe Renderer beide Mail-Arten bedient.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner Bugfix, der bestehende SSoT-Bausteine (`severity_for`, `thunder_ampel_band`, `tone_css`, ADR-0025) auf einen zweiten, bisher ungefärbten Codepfad anwendet — keine neue Grundsatzentscheidung.

## Changelog

- 2026-08-15: Initial spec created
