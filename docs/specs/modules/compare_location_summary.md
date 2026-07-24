---
entity_id: compare_location_summary
type: module
created: 2026-07-16
updated: 2026-07-16
status: draft
version: "2.1"
workflow: feat-1278-compare-ort-zusammenfassung
tags: [formatter, email, compare, shared-with-trip, data-model]
---

# Vergleichs-Mail: Kurz-Zusammenfassung je Ort + fehlende Tages-Aggregate (#1278 + #1285)

## Approval

- [ ] Approved

## Purpose

**PO-Entscheid 2026-07-16: #1278 und #1285 werden in EINER Arbeit umgesetzt**,
weil beide exakt dieselben Tages-Aggregate je Ort brauchen. Getrennt zu bauen
hieße, denselben Ableitungscode zweimal anzufassen — und #1278 würde
zwischenzeitlich eine Zusammenfassung ohne Regen/Gewitter liefern, obwohl die
Wurzelursache dieselbe ist.

**Teil A — #1278:** Die Vergleichs-Mail bekommt je Ort einen kurzen,
natürlichsprachigen Zusammenfassungssatz — **exakt im Stil und mit der
exakten Formatierungslogik der Trip-Zusammenfassung**
(`CompactSummaryFormatter`, F2), platziert unterhalb der Vergleichs-Matrix.
Kein neues Frontend-UI-Element, nichts einstellbar. Der Trip-Baustein wird
**geteilt, nicht nachgebaut** (Trip/Compare-Teilungs-Invariante, CLAUDE.md;
Anti-Pattern-Referenz #1170).

**Teil B — #1285 (Wurzel-Fix, nicht "out of scope"):** Wählt ein Nutzer im
Vergleichs-Editor **Regen, Gewitter, UV oder Sicht**, wird die Auswahl beim
Rendern der Vergleichs-Mail **still verworfen** — keine Zeile in der
Übersichts-Matrix, keine Meldung. Root Cause: `LocationResult`
(`src/app/user.py:117`) führt für diese vier Größen **kein Tages-Aggregat**.
Die Werte existieren nur stündlich in `LocationResult.hourly_data`
(`ForecastDataPoint`: `precip_1h_mm`, `thunder_level`, `uv_index`,
`visibility_m`) und werden dort in der Stundentabelle derselben Mail auch
korrekt angezeigt — nur die Tages-Ebene fehlt. Diese Spec schließt die Lücke,
damit die Compare-Matrix dieselben Tages-Aggregate führt wie der Trip-Pfad
(`SegmentWeatherSummary`).

**Nachtrag PO-Entscheid 2026-07-16 (v2.1): Regenwahrscheinlichkeit kommt
dazu.** Aus "vier Metriken" werden **fünf**: Regen, Gewitter, UV, Sicht +
**Regenwahrscheinlichkeit** (`pop_max_pct`). Begründung des PO: In
`comparison_engine.py:181` wird `pop_max_pct` — exakt wie `thunder_level` —
bereits berechnet und beim Bau von `LocationResult` verworfen; exakt
dieselbe Codestelle, quasi kein berechnungsseitiger Mehraufwand. Einen
bekannten stillen Fehler an einer Stelle stehenzulassen, die ohnehin
angefasst wird, wäre nicht vertretbar. **Wichtiger Unterschied zu den
anderen vier, der beim Fact-Check auffiel:** Anders als Regen/Gewitter/UV/
Sicht hat Regenwahrscheinlichkeit als **Tages-Matrix-Metrik** heute noch
**keine Frontend-Auswahlmöglichkeit** — sie ist nicht im getesteten
Compare-Metrik-Katalog (`frontend/src/lib/components/compare/
compareMetricDefs.ts::ALL_METRICS`, aktuell 14 Einträge, mit Test
`compareEditorSlice3.test.ts`) enthalten. Die einzige heute existierende
`pop`-Frontend-ID ist `pop_pct` in `compareHourlyMetricDefs.ts:26` — das ist
jedoch ein **eigenständiges Vokabular für die STUNDEN-Spaltenauswahl**
(funktioniert dort bereits korrekt), nicht die Tages-Übersichtsauswahl. Der
"quasi kein Mehraufwand"-Rahmen gilt daher exakt für die
Backend-Verdrahtung, aber **nicht** ohne eine zusätzliche, additive
Katalog-Zeile in `compareMetricDefs.ts` — ohne sie wäre die neue Matrix-Zeile
über explizite Auswahl unerreichbar und würde stattdessen nur über den
`enabled_metrics=None`-Fallback ungefragt bei allen Bestandsvergleichen
erscheinen (Verstoß gegen AC-16/Bestandsschutz). Diese eine Zeile ist mit
"kein neues UI-Element" vereinbar, weil sie keinen neuen Bildschirm/Schalter
erzeugt, sondern einen bestehenden, bereits generisch iterierenden Katalog
um einen Eintrag erweitert — exakt das Muster, nach dem die anderen vier
Metriken dort bereits stehen. Details: s. Implementation Details,
"Sonderfall Regenwahrscheinlichkeit".

**Folge für Teil A:** Weil Teil B die Lücke schließt, gilt der ursprüngliche
PO-Entscheid für die Zusammenfassung jetzt sauber und ohne Sonderregel: **Die
Zusammenfassung nennt genau die Metriken, die im Vergleich gewählt sind** —
Regen und Gewitter erscheinen dort automatisch, sobald sie in der Matrix
wählbar sind und gewählt wurden. Keine "immer-anzeigen"-Ausnahme mehr, keine
Known Limitation zum fehlenden Regen.

Mitgefixter Nebenbefund (unverändert aus v1.0): der Kopf der STUNDEN-Sektion
in der Vergleichs-Mail zeigt aktuell fest verdrahtet "09–16 Uhr"
(`compare_html.py:851`) — ein toter Rest des mit #1268 abgeschafften
Zeitfensters (Bewertung läuft seit #1268 über den ganzen Tag; das Feld
`time_window` existiert strukturell in `ComparisonResult` weiter, wird aber
nicht mehr als Anzeige-Einschränkung interpretiert).

## Source

- **File:** `src/output/renderers/compact_summary.py` (`CompactSummaryFormatter`
  — wird um einen `context`-Parameter bzw. einen zweiten dünnen Wrapper
  erweitert; kein neuer, paralleler Formatierungscode)
- **File:** `src/output/renderers/email/compare_html.py`
  (`render_compare_html()` — Body-Komposition um den neuen Zusammenfassungs-
  Block erweitert; `CV2_METRICS` bekommt neue Zeilen für Regen/Gewitter/
  Sicht/Regenwahrscheinlichkeit; Nebenbefund-Fix in
  `_render_section_head("STUNDEN", ...)` Aufruf, aktuell Zeile 851)
- **File:** `src/output/renderers/comparison.py`
  (`render_comparison_text()` — Plaintext-Pendant, Body um den neuen Block
  erweitert)
- **File:** `src/output/renderers/compare_metric_ids.py`
  (`FRONTEND_TO_RENDERER_METRIC_ID` — bekommt fünf neue Einträge:
  `visibility_min_m`, `precip_sum_mm`, `uv_index_max`, `thunder_level_max`,
  `pop_max_pct`; der Kommentar Zeile 18–19 "bewusst nicht gemappt" wird
  entfernt/korrigiert)
- **File:** `src/services/comparison_engine.py` (`ComparisonEngine.run()`,
  `dict_to_comparison_result()` — Tages-Aggregate für Regen/Gewitter/UV/
  Sicht/Regenwahrscheinlichkeit berechnen und an `LocationResult`
  durchreichen; `thunder_level` und `pop_max_pct` werden dort bereits
  berechnet, aber **nicht** an den `LocationResult`-Konstruktor
  weitergegeben, s. Implementation Details)
- **File:** `src/app/user.py` (`LocationResult` — neue optionale
  Tages-Aggregatfelder; **schema-relevant**, löst `data_schema_backup.py`
  aus, s. Datenschema-Abschnitt)
- **File (NEU, additiv, v2.1):**
  `frontend/src/lib/components/compare/compareMetricDefs.ts`
  (`ALL_METRICS` — ein neuer `MetricDef`-Eintrag für Regenwahrscheinlichkeit,
  analog den vier bestehenden Einträgen für Regen/Gewitter/UV/Sicht; ohne
  diesen Eintrag ist die neue Matrix-Zeile über explizite Auswahl
  unerreichbar, s. Purpose/Implementation Details "Sonderfall
  Regenwahrscheinlichkeit")
- **Identifier:** `CompactSummaryFormatter.format_stage_summary()` (Kern,
  bleibt für den Trip-Pfad unverändert aufrufbar) + neuer Ort-Wrapper
  (Name/Signatur ist Implementierungsdetail, s. Implementation Details)

> Schicht-Hinweis: reiner Python-Core-Renderer/-Service (`src/output/renderers/`,
> `src/services/comparison_engine.py`, `src/app/user.py` — Teil des FastAPI-/
> CLI-Versandpfads). Für vier der fünf Metriken **kein Frontend-Code
> betroffen** (PO-Vorgabe: kein neues UI-Element; die Frontend-Metrik-
> Definitionen für Regen/Gewitter/UV/Sicht — `compareMetricDefs.ts`,
> `CompareMatrix.svelte` — existieren bereits und erwarten diese Felder, sie
> greifen nur endlich, sobald das Backend sie liefert). Für
> Regenwahrscheinlichkeit ist **eine additive Zeile** im bestehenden
> Frontend-Katalog nötig (s. o.) — kein neuer Screen, kein neuer Schalter,
> nur ein Datensatz mehr in einer bereits generisch iterierenden Liste.

## Estimated Scope

- **LoC:** geschätzt **≈230–330** (Kern-Produktionscode, ohne Tests/Docs) —
  gegenüber v2.0 (~220–320) nur geringfügig gestiegen: die fünfte Metrik
  (Regenwahrscheinlichkeit) kostet backend-seitig kaum mehr als das
  Gewitter-Pendant (ein weiterer Verdrahtungs-Fix an derselben Codestelle,
  eine weitere `CV2_METRICS`-Zeile, ein weiterer Mapping-Eintrag), zusätzlich
  **+1 Zeile** im Frontend-Katalog (`compareMetricDefs.ts::ALL_METRICS`).
  Aufteilung unverändert: ~120–180 für Teil A (Formatter-Erweiterung + zwei
  Renderer-Integrationen) + ~110–150 für Teil B (Tages-Aggregat-Berechnung in
  `comparison_engine.py`, neue `LocationResult`-Felder, vier neue
  `CV2_METRICS`-Zeilen, fünf neue Mapping-Einträge, ggf. Plaintext-Übersicht,
  1 Frontend-Zeile). **PO hat `loc_limit_override 500` bereits freigegeben**
  (ausgelöst durch die v2.0-Schätzung) — damit ist auch diese leicht höhere
  v2.1-Schätzung abgedeckt, keine erneute Freigabe nötig.
- **Files:** 5 Kern-Backend-Dateien (`compact_summary.py`, `compare_html.py`,
  `comparison.py`, `compare_metric_ids.py`, `comparison_engine.py`) +
  `app/user.py` (Datenmodell-Erweiterung) + **1 Frontend-Datei**
  (`compareMetricDefs.ts`, additive Katalog-Zeile, NEU seit v2.1)
- **Effort:** medium-high (zwei zusammenhängende Bugfixes/Features mit
  gemeinsamer Datenbasis; die Metrik-Vokabular-Übersetzung UND die
  Tages-Aggregat-Herleitung sind die zentralen Design-Entscheidungen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompactSummaryFormatter.format_stage_summary()` (`compact_summary.py:40`) | Method | Geteilter Formatierungs-Kern — MUSS wiederverwendet werden, nicht dupliziert |
| `LocationResult` (`src/app/user.py:117`) | Dataclass | Ortsdaten je Vergleichs-Ort, inkl. `hourly_data: list[ForecastDataPoint]`; bekommt neue optionale Tages-Aggregatfelder (#1285) |
| `SavedLocation.timezone` (`src/app/user.py:64`) | Field | Optionale Zeitzonen-Angabe je Ort für die zeitliche Qualifizierung (Regen-/Böen-Zeiten) |
| `ComparisonEngine.run()` (`src/services/comparison_engine.py:42`) | Method | Berechnet die Ort-Metriken aus `filtered_data`; berechnet `thunder_level` (Z. 178) und `pop_max_pct` (Z. 179–181) bereits intern, gibt beide aber **nicht** an `LocationResult` weiter (Z. 202–221) — bereits vorhandene, aber verworfene Zwischenwerte |
| `WeatherMetricsService.compute_basis_metrics()` (`weather_metrics.py:397`) | Method | Kanonische **Level-1**-Rechenregel je Segment (SUM Regen `:533`, MAX Gewitter-Ordinal `:586`, MIN Sicht `:607`) — Referenz für die Compare-Tages-Aggregation. **Nicht** `aggregate_stage()` (`:985`, Level-2, kombiniert bereits aggregierte Segmente) |
| `WeatherMetricsService._compute_pop()` (`weather_metrics.py:848`) | Method | MAX-Regel für Regenwahrscheinlichkeit (`pop_max_pct = round(max(dp.pop_pct für alle dp)`) — kanonische Trip-Referenz für die fünfte Metrik |
| `WeatherMetricsService._compute_uv_index()` (`weather_metrics.py:873`) | Method | MAX-Regel für UV — Referenz; `_metric_value()` (`compare_html.py:294`) berechnet den UV-Tageswert für die Matrix-Zeile `uv_max` **bereits heute live** aus `hourly_data` mit identischer MAX-Regel — dieser Teil ist rechnerisch korrekt, nur unerreichbar (s. Implementation Details, "Sonderfall UV") |
| `CV2_METRICS` (`compare_html.py:122`) | Const | Renderer-Metrik-IDs der Vergleichs-Matrix (`enabled_metrics`-Vokabular); bekommt vier neue Zeilen (Regen/Gewitter/Sicht/Regenwahrscheinlichkeit), `uv_max` existiert bereits |
| `resolve_enabled_metrics()` (`src/output/renderers/compare_metric_ids.py:47`) | Function | Löst Frontend-Auswahl auf das `enabled_metrics`-Set auf, das auch die Zusammenfassung filtert; verwirft aktuell nicht-gemappte IDs still (Root Cause #1285) |
| `sort_locations_alphabetically()` (`compare_html.py:772`) | Function | Bestehender Sortier-Helfer — Zusammenfassungs-Reihenfolge MUSS identisch sein (kein neues Sortieren) |
| `render_official_alerts_plain()` (`src/output/renderers/alert/official_alerts.py`) | Function | Vorbild für "gemeinsamer Renderer statt Copy-Paste" bei Compare-Klartext |
| `ALL_METRICS` (`frontend/src/lib/components/compare/compareMetricDefs.ts:49-53`) | Const (Frontend) | Vollständiger, getesteter Katalog wählbarer Compare-Metriken (aktuell 14 `MetricDef`-Einträge, `compareEditorSlice3.test.ts`); enthält **keinen** Eintrag für Regenwahrscheinlichkeit — muss um einen fünfzehnten Eintrag ergänzt werden, sonst ist die neue Matrix-Zeile nicht explizit wählbar (s. "Sonderfall Regenwahrscheinlichkeit") |
| `ALL_HOURLY_METRICS` (`frontend/src/lib/components/compare/compareHourlyMetricDefs.ts:18-28`) | Const (Frontend) | **Eigenständiges** Vokabular für die Stunden-Spaltenauswahl; enthält bereits `{key: 'pop_pct', label: 'Regenwahrscheinlichkeit'}` (Zeile 26) — das ist NICHT dasselbe wie die Tages-Matrix-Auswahl und funktioniert bereits korrekt; nicht verwechseln |

## Implementation Details

### Teil B zuerst: fehlende Tages-Aggregate nachrüsten (#1285)

**Ist-Zustand, präzise:**

- **Regen (`precip_sum_mm`), Sicht (`visibility_min_m`):** Werden im
  Compare-Pfad **überhaupt nicht** berechnet — weder in
  `ComparisonEngine.run()` noch sonst irgendwo für `LocationResult`. Müssen
  neu berechnet werden.
- **Gewitter (`thunder_level_max`):** Wird in `ComparisonEngine.run()`
  bereits berechnet (`metrics["thunder_level"] = max(...)`, Z. 174–178) —
  aber beim Bau von `LocationResult` (Z. 202–221 und 258–276) **nicht**
  übergeben. Reiner Verdrahtungs-Fix an dieser Stelle plus Umbenennung/
  Übernahme des Feldnamens.
- **Regenwahrscheinlichkeit (`pop_max_pct`) — v2.1, PO-Entscheid
  2026-07-16:** Exakt derselbe Fund wie beim Gewitter: Wird in
  `ComparisonEngine.run()` bereits berechnet (`metrics["pop_max_pct"] =
  max(pops)`, Z. 179–181) — aber beim Bau von `LocationResult` (Z. 202–221
  und 258–276) **nicht** übergeben. Reiner Verdrahtungs-Fix, identisches
  Muster zum Gewitter-Fund, keine neue Berechnung nötig. Kanonische
  Trip-Regel: `WeatherMetricsService._compute_pop()` (`weather_metrics.py:
  848–851`, MAX über `dp.pop_pct`, gerundet). **Backend-seitig** also
  "quasi kein Mehraufwand" — anders als bei den anderen vier fehlt hier
  jedoch zusätzlich die Frontend-Auswahlmöglichkeit, s. eigener Abschnitt
  unten.
- **UV (`uv_index_max`) — Sonderfall:** Die Matrix-Zeile `uv_max` **existiert
  bereits** in `CV2_METRICS` und ihr Wert wird **bereits heute korrekt live**
  aus `hourly_data` berechnet (`_metric_value()`, `compare_html.py:294–297`,
  MAX über `dp.uv_index` — identische Regel wie `_compute_uv_index`). Der
  Fehler liegt ausschließlich in `FRONTEND_TO_RENDERER_METRIC_ID`: keine
  Frontend-ID mappt auf `"uv_max"`. Folge: Wählt ein Nutzer UV **zusammen
  mit** mindestens einer anderen mappbaren Metrik, wird `"uv_max"` beim
  Resolving verworfen und die Zeile verschwindet — wählt er **nur** UV,
  bildet `resolve_enabled_metrics()` das leere Ergebnis auf `None` ab (=
  "kein Filter", alles sichtbar), und die Zeile erscheint zufällig doch.
  Dieses inkonsistente Verhalten (mal sichtbar, mal nicht, je nach
  Kombination) ist der eigentliche Bug — **keine neue Aggregatberechnung
  nötig**, nur der Mapping-Eintrag.
- Alle vier reinen Backend-Ableitungen (Regen, Gewitter, Sicht,
  Regenwahrscheinlichkeit — UV ist bereits korrekt) MÜSSEN derselben
  Rechenregel folgen wie `WeatherMetricsService.compute_basis_metrics()`
  bzw. `_compute_pop()` (SUM/MAX-Ordinal/MIN/MAX), sonst beschreibt dieselbe
  Wetterlage im Vergleich einen anderen Wert als im Trip-Briefing (AC-15,
  ex-AC-6).
- **Nicht Teil von #1285 (bleibt Known Limitation):** **Windrichtung**
  (`wind_direction`) ist weiterhin keine über `enabled_metrics` wählbare
  Matrix-Zeile — sie ist nicht Gegenstand von Issue #1285 (das Issue nennt
  explizit nur Regen/Gewitter/UV/Sicht; Regenwahrscheinlichkeit wurde per
  eigenem PO-Entscheid am 2026-07-16 ergänzt, s. o. — Windrichtung nicht).
  Windrichtung hat außerdem, wie ursprünglich Regenwahrscheinlichkeit, keinen
  Eintrag im Frontend-Matrix-Katalog — auch das spricht dafür, sie in dieser
  Arbeit nicht mitzuziehen. Bei Bedarf eigener Nebenbefund-Eintrag (#1199)
  oder Issue.

### Sonderfall Regenwahrscheinlichkeit: fehlende Frontend-Auswahlmöglichkeit (v2.1)

Anders als bei Regen/Gewitter/UV/Sicht — für die alle vier bereits ein
`MetricDef`-Eintrag in `compareMetricDefs.ts::ALL_METRICS` existiert —
**gibt es für Regenwahrscheinlichkeit als Tages-Matrix-Metrik heute keine
Frontend-ID**. Geprüft (nicht geraten):

- `frontend/src/lib/components/compare/compareMetricDefs.ts::ALL_METRICS`
  (Zeilen 30–53) — der einzige getestete Katalog wählbarer Compare-Metriken
  (`compareEditorSlice3.test.ts`: "ALL_METRICS ist ein Array mit mindestens
  10 Einträgen", tatsächlich 14) — enthält `visibility_min_m`,
  `precip_sum_mm`, `uv_index_max`, `thunder_level_max`, aber **keinen**
  `pop_max_pct`-Eintrag.
- `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts:26` hat
  zwar `{key: 'pop_pct', label: 'Regenwahrscheinlichkeit'}` — das ist aber
  laut Datei-Kopfkommentar ausdrücklich ein **"Eigenstaendiges Vokabular,
  kein Reuse von compareMetricDefs.ts"**: die Stunden-Spaltenauswahl, nicht
  die Tages-Übersichtsauswahl. Dieser Pfad ist nicht kaputt und bleibt
  unverändert.
- Konsequenz: Ohne eine zusätzliche, additive Zeile in `ALL_METRICS` kann
  kein Nutzer Regenwahrscheinlichkeit für die Tages-Matrix auswählen — die
  neue `enabled_metrics`-ID würde nie über explizite Auswahl gesetzt.
  Stattdessen würde die Zeile nur über den `enabled_metrics=None`-Fallback
  (keine Auswahl getroffen = "alles sichtbar") bei **allen** Bestandsvergleichen
  ungefragt neu auftauchen — ein Verstoß gegen AC-16 (Bestandsschutz) und
  gegen die Ganze-Zusammenfassungs-Prämisse "Nutzer wählt es aktiv".
- **Anforderung:** `ALL_METRICS` bekommt einen fünfzehnten Eintrag, analog
  den vier bestehenden (`label: 'Regenwahrscheinlichkeit'`, `key:
  'pop_max_pct'` — empfohlen, weil er 1:1 den Trip-Feldnamen
  `SegmentWeatherSummary.pop_max_pct` trifft, exakt dieselbe Konvention wie
  bei den anderen vier Einträgen, die alle ihren Backend-Feldnamen
  verwenden; `pop_max_pct` selbst ist aktuell **nirgends** als Frontend-ID
  belegt — das ist eine Empfehlung, keine bereits bestehende Tatsache).
  Diese eine Katalog-Zeile ist Teil des Wiring-Fixes, nicht optional, und
  mit "kein neues UI-Element" vereinbar (s. Purpose).

### Teil A: Geteilter Kern, zwei dünne Wrapper (`context="route"|"vergleich"`)

`format_stage_summary()` reduziert intern bereits auf zwei Größen — ein
Aggregat (`SegmentWeatherSummary`) und eine Stundenliste
(`list[ForecastDataPoint]`). Alle `_format_*`-Methoden arbeiten nur auf
diesen beiden. Das ist die natürliche Teilungs-Naht:

```
kontextneutraler Kern:  (summary, hourly, titel, dc, tz) -> Fließtext
  |                                              |
  Wrapper "route" (Trip, bestehend)     Wrapper "vergleich" (NEU)
  Eingabe: SegmentWeatherData[]         Eingabe: LocationResult
  Titel: Etappenname (gekürzt)          Titel: Ortsname (NICHT gekürzt)
  Metrik-Quelle: dc.metrics             Metrik-Quelle: enabled_metrics (übersetzt)
```

Der Ort-Wrapper darf `_shorten_stage_name()` (Etappen-Kürzungsregel
"von X nach Y" → "X → Y") **nicht** auf den Ortsnamen anwenden — ein Ortsname
ist kein Etappenname und darf syntaktisch nicht danach aussehen, als wäre er
einer.

### Metrik-Vokabular-Übersetzung (zentrale Design-Entscheidung, jetzt vollständig)

Drei Vokabulare treffen aufeinander: **Frontend-ID** (Auswahl im Editor,
`compareMetricDefs.ts`/`CompareMatrix.svelte`), **Compare Renderer-ID**
(`enabled_metrics`, `CV2_METRICS`-Keys) und **Trip Metrik-ID**
(`dc.metrics[].metric_id`, konsumiert vom Fließtext-Kern). Nur Zeilen mit
Trip-Pendant landen im Zusammenfassungssatz:

| Frontend-ID | Compare Renderer-ID | Trip Metrik-ID | Im Fließtext-Satz? |
|---|---|---|---|
| `temp_max_c` | `temp_max` | `temperature` | ja |
| `wind_max_kmh` | `wind_max` | `wind` | ja (inkl. Böen-Peak-Logik) |
| `cloud_avg_pct` | `cloud_avg` | `cloud_total` | ja |
| `precip_sum_mm` | **neu** (#1285) | `precipitation` | ja — **neu automatisch**, sobald wählbar+gewählt |
| `thunder_level_max` | **neu** (#1285) | `thunder` | ja — **neu automatisch** |
| `uv_index_max` | `uv_max` (Mapping-Fix, Zeile existiert bereits) | — | nein (kein Fließtext-Pendant) |
| `visibility_min_m` | **neu** (#1285) | — | nein (kein Fließtext-Pendant) |
| `pop_max_pct` (**neu anzulegen** in `compareMetricDefs.ts::ALL_METRICS` — noch nicht belegt, s. "Sonderfall Regenwahrscheinlichkeit") | **neu** (#1285) | `rain_probability` | ja — **aber gemeinsam mit `precipitation`**: der Trip-Formatter behandelt beide im selben `_format_precipitation`-Zweig (`compact_summary.py:66`: `if "precipitation" in enabled or "rain_probability" in enabled`). Wählt der Nutzer NUR Regenwahrscheinlichkeit (ohne Niederschlagsmenge), erscheint trotzdem der kombinierte Niederschlags-Satz — bestehendes Trip-Verhalten, keine neue Compare-Sonderregel |
| `sunny_hours_h` | `sunny_hours` | — | nein |
| `snow_depth_cm` | `snow_depth_cm` | — | nein |
| `snow_new_sum_cm` | `snow_new_cm` | — | nein |
| — (keine Frontend-ID/Matrix-Zeile) | — | `wind_direction` | nein (kein Compare-Pendant; nicht Teil von #1285) |
| `warn` (immer sichtbare Zeile) | `warn` | — | nein (kein Metrik-Wert) |

Die genauen neuen Renderer-ID-Strings für Regen/Gewitter/Sicht/
Regenwahrscheinlichkeit (z. B. `precip_sum`/`thunder_max`/`visibility_min`/
`pop_max`) sind Implementierungsdetail — sie müssen nur eindeutig,
konsistent mit dem bestehenden Namensschema (`*_max`/`*_avg`/`*_sum`/
`*_min`) und in `FRONTEND_TO_RENDERER_METRIC_ID` korrekt gemappt sein.
`enabled_metrics=None` (heutiger Default, keine Auswahl getroffen) verhält
sich weiterhin wie "alle mappbaren Metriken aktiv" — konsistent mit dem
bestehenden Verhalten der Matrix bei `None`.

### Datenschema-Sicherheit (`LocationResult`)

`src/app/user.py` ist laut CLAUDE.md **schema-relevant** — jede Änderung
löst automatisch den Pre-Snapshot-Hook `data_schema_backup.py` aus. Faktisch
ist `LocationResult` jedoch ein **rein transientes, pro Request neu
berechnetes Objekt** (`ComparisonEngine.run()` baut es bei jedem Aufruf neu
auf; kein `json.dump`/keine Persistenz, keine Datei wird zurückgelesen —
verifiziert durch Code-Suche, kein Treffer für Serialisierung von
`LocationResult`/`ComparisonResult`). Die klassische
Bestandsdaten-Verlust-Gefahr (BUG-DATALOSS-GR221, #102) besteht hier daher
nicht in der Form "gespeicherte Datei verliert Felder beim Neu-Schreiben".

Trotzdem gilt als Anforderung: die neuen Felder werden als **zusätzliche,
optionale Felder mit Default `None`** ergänzt (additive Dataclass-Erweiterung,
kein Feld wird umbenannt oder entfernt), damit jeder bestehende Aufrufer, der
`LocationResult` ohne die neuen Keyword-Argumente konstruiert (z. B.
`dict_to_comparison_result()`, `validator_render_service.py:159`), unverändert
funktioniert. Sollte im Zuge der Implementierung doch eine persistierte
Struktur berührt werden (z. B. falls die Wahl fiele, den Aggregat-Wert in
einem gespeicherten Preset zwischenzuspeichern), gilt zwingend Read-Modify-
Write mit Merge — niemals Replace.

### Platzierung (Teil A)

- **HTML** (`compare_html.py`): neuer Block zwischen `overview_html`
  (ÜBERSICHT-Tabelle) und `hourly_head_html` (STUNDEN-Kopf) in der
  Body-Komposition (aktuell Zeilen 864–870). Ein Ort ohne Daten
  (`error is not None` oder leere `hourly_data`) erzeugt **keinen** Block
  (Anti-Erosion-Muster, wie bereits für die übrigen Blöcke etabliert).
- **Plaintext** (`comparison.py`, `render_comparison_text()`): analoger
  Block nach der Orts-Übersicht (Metrik-Zeilen + amtliche Warnungen je Ort),
  vor dem `"STUNDENVERLAUF"`-Abschnitt.
- Reihenfolge: identisch zur Matrix — `sort_locations_alphabetically()`,
  kein Score/Ranking (v2-Vertrag, PO 2026-07-08).

### Nebenbefund-Fix: totes Zeitfenster im STUNDEN-Kopf

`compare_html.py` (aktuell Zeile 851) übergibt `_render_section_head(
"STUNDEN", "Stundenverlauf · alle Orte", "09–16 Uhr")` — die dritte Angabe
ist ein statischer Text-Rest aus der Zeit vor #1268. Seit #1268 gilt
`time_window=(0, 23)` (ganzer Tag), das Feld `time_window` existiert im
`ComparisonResult` zwar noch strukturell, wird aber nicht mehr als
einschränkendes Anzeige-Fenster interpretiert. Die dritte Angabe muss entweder
entfallen (analog zur bereits entfernten Zeitfenster-Zeile im Klartext-Header,
`comparison.py:77`) oder durch eine Angabe ersetzt werden, die keinen falschen
Eindruck einer Uhrzeit-Einschränkung erweckt.

## Expected Behavior

- **Input:** `ComparisonResult` mit `locations: list[LocationResult]`
  (inkl. `hourly_data` UND — nach Teil B — den Tages-Aggregaten für
  Regen/Gewitter/Sicht/Regenwahrscheinlichkeit, UV weiterhin live
  berechnet), `enabled_metrics` (aus dem Compare-Preset, identisch zur
  Matrix-Filterung, jetzt inkl. der fünf bisher verworfenen/unerreichbaren
  IDs)
- **Output:** Übersichts-Matrix mit bis zu fünf zusätzlichen Zeilen, wenn
  gewählt; HTML-Zusammenfassungs-Block + Klartext-Zusammenfassungs-Block, je
  ein Satz pro Ort mit Daten, in der vom Nutzer konfigurierten Reihenfolge
  (siehe Ablösungs-Vermerk bei AC-10), unterhalb der Übersicht,
  inhaltlich beschränkt auf die tatsächlich gewählten Metriken
- **Side effects:** keine (rein formatierend/berechnend, pure functions wie
  der restliche Compare-Renderer-Pfad; `LocationResult` bleibt transient)

## Acceptance Criteria

- **AC-1:** Given die Vergleichs-Mail wird für mehrere Orte gerendert, When
  die Kurz-Zusammenfassung je Ort erzeugt wird, Then nutzt das System
  denselben Formatierungs-Baustein wie die Trip-Zusammenfassung — es gibt
  keinen eigenen, für den Vergleich neu geschriebenen Text-Formatierungscode.
  - Test: Code-Review-Nachweis + ein Test, der beweist, dass Compare- und
    Trip-Zusammenfassung bei identischer Wetterlage denselben Formatierungspfad
    durchlaufen (gemeinsame Methode aufgerufen, kein Duplikat).

- **AC-2:** Given eine Vergleichs-Mail mit mindestens zwei Orten, When die
  HTML-Mail geöffnet wird, Then erscheint unterhalb der Vergleichs-Matrix für
  jeden Ort mit Daten ein eigener Zusammenfassungssatz, bevor der
  Stundenverlauf-Abschnitt beginnt.
  - Test: Gerenderte HTML-Ausgabe enthält den neuen Block zwischen ÜBERSICHT-
    Tabelle und STUNDEN-Kopf, mit einer Zeile je Ort.

- **AC-3:** Given dieselbe Vergleichs-Mail wird als Klartext erzeugt, When der
  Empfänger die Nur-Text-Version liest, Then enthält auch sie je Ort denselben
  Zusammenfassungssatz an der analogen Stelle (nach der Orts-Übersicht, vor
  dem Stundenverlauf-Abschnitt).
  - Test: Plaintext-Ausgabe von `render_comparison_text()` enthält den Block
    an der erwarteten Stelle, Wortlaut deckungsgleich mit dem HTML-Satz.

- **AC-4:** Given ein Nutzer öffnet die Wertebereiche-/Layout-/Versand-
  Konfiguration eines Vergleichs im Frontend, When er alle Einstellungen
  durchgeht, Then findet er keinen Schalter, keine Metrik-Auswahl und keine
  Option für diese Zusammenfassung — sie erscheint unabhängig von jeder
  Konfiguration automatisch, sobald Ortsdaten vorliegen.
  - Test: Kein neues Frontend-Element **für die Zusammenfassung** vorhanden
    (Diff-Review) — kein Toggle, keine Metrik-Auswahl, keine Option, die auf
    den Zusammenfassungsblock wirkt; Zusammenfassung erscheint in der Mail
    auch bei unverändertem Preset. Einzige im Frontend zulässige Änderung
    dieser Arbeit ist die additive Katalog-Zeile für die
    Regenwahrscheinlichkeit in `compareMetricDefs.ts::ALL_METRICS`
    (PO-Entscheid 2026-07-16, s. Purpose/Implementation Details) — sie
    betrifft die Matrix-Metrikauswahl, nicht die Zusammenfassung, und ist
    damit kein Verstoß gegen dieses AC.

- **AC-5:** Given ein Vergleich zeigt in der Matrix nur Temperatur und Wind
  (weil Wolken/Sonne/UV/Schnee in der Konfiguration abgewählt sind), When die
  Zusammenfassung erzeugt wird, Then nennt der Satz je Ort ausschließlich
  Temperatur und Wind — keine Metrik, die in der Matrix darüber nicht
  sichtbar ist.
  - Test: `enabled_metrics={"temp_max", "wind_max"}` → Zusammenfassungssatz
    enthält keinen Wolken-Anteil, obwohl die Wetterdaten Bewölkung enthalten.

- **AC-6:** Given ein Ort im Vergleich wählt zusätzlich Regen und Gewitter
  (jetzt möglich durch die Behebung von #1285), When die Zusammenfassung
  erzeugt wird, Then nennt der Satz auch Regen- bzw. Gewitter-Anteile, sofern
  die Wetterdaten dafür Anlass geben — ohne Sonderregel "Regen immer
  anzeigen" oder "Regen nie anzeigen".
  - Test: `enabled_metrics` enthält die neue Regen- und Gewitter-Renderer-ID,
    Wetterdaten enthalten Niederschlag → Zusammenfassungssatz nennt Regen.

- **AC-7:** Given ein Ort im Vergleich hat identische stündliche Wetterdaten
  wie eine Etappe im Trip-Briefing für denselben Tag, When beide
  Zusammenfassungen erzeugt werden, Then stimmen die berechneten
  Aggregatwerte (Temperaturspanne, Regenmenge, Windspitze, Gewitterstufe)
  überein — dieselbe Wetterlage wird im Vergleich nicht anders beschrieben
  als im Trip-Briefing.
  - Test: Gleiche `ForecastDataPoint`-Liste einmal über den Trip-Pfad, einmal
    über den Compare-Pfad aggregiert → identische Zahlen im Ergebnissatz.

- **AC-8:** Given ein Ort im Vergleich heißt z. B. "Sóller", When die
  Zusammenfassungszeile für diesen Ort erzeugt wird, Then beginnt sie mit
  dem vollständigen Ortsnamen "Sóller" — nicht mit einer für Etappennamen
  gedachten "X → Y"-Kürzung oder einem daraus verstümmelten Text.
  - Test: Ortsname mit Leerzeichen/Sonderzeichen, der zufällig wie
    "von A nach B" beginnen könnte → Titel bleibt der volle Ortsname.

- **AC-9:** Given ein Ort im Vergleich konnte nicht geladen werden (Fehler)
  oder hat keine Stundendaten, When die Zusammenfassungs-Sektion gerendert
  wird, Then erscheint für diesen Ort keine leere oder kaputte Zeile — der Ort
  fehlt einfach in der Zusammenfassungs-Sektion.
  - Test: `LocationResult(error="...")` bzw. `hourly_data=[]` → kein Eintrag,
    keine leere Zeile, kein Crash.

> **⚠️ AC-10 abgelöst am 2026-07-24 durch
> [`compare_location_order.md`](compare_location_order.md) (Issue #1359,
> Scheibe 2).** Die Orts-Reihenfolge ist **nicht mehr alphabetisch**, sondern
> folgt der vom Nutzer im Orte-Tab konfigurierten Preset-Reihenfolge. Der
> zweite Halbsatz (keine Score-Sortierung, keine Gewinner-Hervorhebung) gilt
> unverändert weiter. Die folgende Fassung beschreibt den Stand **vor** dieser
> Änderung und ist nur noch historisch zu lesen.

- **AC-10 (HISTORISCH, abgelöst durch #1359 Scheibe 2):** Given ein Vergleich
  mit mehreren Orten, When die Zusammenfassungs-Sektion erscheint, Then sind
  die Orte in der vom Nutzer konfigurierten Reihenfolge geordnet, identisch
  zur Reihenfolge in der Matrix darüber — es gibt keine Sortierung nach Score
  und keine optische Hervorhebung eines "Gewinner"-Orts.
  - Test: Orte in bewusst nicht-alphabetischer Reihenfolge im Input →
    Zusammenfassungs-Reihenfolge folgt der Eingabe und deckt sich mit der
    Matrix-Kopfzeile.

- **AC-11:** Given eine bestehende Trip-Briefing-Mail (HTML und Klartext),
  When sie nach dieser Änderung erneut erzeugt wird, Then ist der
  Zusammenfassungstext je Etappe zeichengleich mit dem Text vor dieser
  Änderung — und auch die Trip-Mail insgesamt bleibt unverändert, obwohl
  `weather_metrics`/Modell-Dateien in dieser Arbeit berührt werden.
  - Test: Regressionstest mit vorher aufgezeichnetem Trip-Fixture — Text
    vorher/nachher byte-identisch (HTML + Klartext).

- **AC-12:** Given eine Vergleichs-Mail wird als HTML gerendert, When der
  Kopf der Stundenverlauf-Sektion angezeigt wird, Then steht dort keine feste
  Uhrzeitangabe "09–16 Uhr" mehr — der Bewertungszeitraum wird nicht mehr als
  auf einen Vormittags-/Mittags-Ausschnitt begrenzt dargestellt.
  - Test: Gerenderte HTML-Ausgabe enthält den String "09–16 Uhr" nicht mehr
    im STUNDEN-Kopf.

- **AC-13:** Given eine Zusammenfassung wird für einen beliebigen Ort
  erzeugt, When der Text gelesen wird, Then taucht darin keine
  Vorhersage-Verlässlichkeits-/Confidence-Angabe auf.
  - Test: Confidence-Werte im Input gesetzt → erscheinen in keinem
    erzeugten Zusammenfassungssatz (Referenz: ADR-0005, Issue #710).

- **AC-14:** Given ein Nutzer wählt in der Vergleichs-Konfiguration Regen,
  Gewitter, UV, Sicht oder Regenwahrscheinlichkeit aus, When die
  Vergleichs-Mail (HTML und Klartext) gerendert wird, Then erscheint für
  jede gewählte dieser fünf Metriken eine eigene Zeile in der
  Übersichts-Matrix mit einem Tageswert je Ort — keine der fünf Metriken
  wird mehr stillschweigend übersprungen, unabhängig davon, mit welchen
  anderen Metriken sie kombiniert gewählt wurde.
  - Test: `enabled_metrics` enthält die fünf neuen/reparierten Renderer-IDs
    (einzeln und in Kombination) → alle fünf Zeilen erscheinen mit einem
    echten Wert (kein durchgängiges "—"), auch wenn UV zusammen mit
    Temperatur gewählt wird (heutiger Bruch).

- **AC-15:** Given ein Ort im Vergleich hat stündliche Regen-/Gewitter-/UV-/
  Sicht-/Regenwahrscheinlichkeits-Werte in `hourly_data`, When der Tageswert
  für diese fünf Metriken berechnet wird, Then entspricht er derselben
  Rechenregel wie im Trip-Pfad (Regen = Summe, Gewitter = höchste
  aufgetretene Stufe, Sicht = Minimum, UV = Maximum, Regenwahrscheinlichkeit
  = Maximum) — dieselbe Wetterlage ergibt im Vergleich denselben Tageswert
  wie im Trip-Briefing für dieselben Stundendaten.
  - Test: Gleiche `ForecastDataPoint`-Liste einmal über
    `WeatherMetricsService.compute_basis_metrics()`/`_compute_pop()`
    (Trip-Pfad), einmal über die neue Compare-Ableitung aggregiert →
    identische Werte für alle fünf Größen.

- **AC-16:** Given ein bestehender Vergleich, in dem der Nutzer **bewusst
  eine Metrik-Auswahl getroffen** hat, die keine der fünf Metriken enthält
  (`enabled_metrics` ist gesetzt und nicht `None`), When die Vergleichs-Mail
  nach dieser Änderung erneut erzeugt wird, Then ist die Übersichts-Matrix
  inhaltlich unverändert — eine bewusste Abwahl wird respektiert, es
  erscheint keine ungefragte Zeile.
  - Test: Regressionstest mit vorher aufgezeichnetem Compare-Fixture, bei dem
    `enabled_metrics` explizit gesetzt ist und die fünf neuen Metriken nicht
    enthält → Matrix-Zeilen vorher/nachher identisch.

- **AC-17:** Given ein Vergleich, in dem **nie eine Metrik-Auswahl getroffen**
  wurde (`enabled_metrics=None`, heutiger Default = "alle Zeilen zeigen"),
  When die Vergleichs-Mail nach dieser Änderung erzeugt wird, Then erscheinen
  auch die fünf neuen/reparierten Zeilen — "nie ausgewählt" bedeutet "alles
  zeigen", und Regen gehört zu allem.
  - Test: `enabled_metrics=None` → Matrix enthält zusätzlich zu den
    bisherigen Zeilen Regen, Gewitter, Sicht und Regenwahrscheinlichkeit mit
    echten Werten (UV war bereits sichtbar).
  - **PO-Entscheid 2026-07-16 (RED-Phase):** Der Developer-Agent deckte in der
    RED-Phase auf, dass die v2.1-Fassung von AC-16 ("kein bestehender
    Vergleich zeigt plötzlich neue Zeilen") mit dem in den Implementation
    Details festgeschriebenen `None`-Verhalten ("alle mappbaren Metriken
    aktiv") **nicht gleichzeitig erfüllbar** war. Der PO hat die Auflösung
    entschieden: `None` zeigt alles inklusive der neuen Zeilen; der
    Bestandsschutz aus AC-16 gilt ausschließlich für eine bewusst getroffene
    Auswahl. Damit entfällt eine dauerhafte Sonderregel im Code.

## Known Limitations

- **Sonnenstunden, Schneehöhe, Neuschnee** haben im geteilten Fließtext-
  Baustein (`CompactSummaryFormatter`) weiterhin **kein Text-Pendant** —
  auch wenn sie in der Vergleichs-Matrix aktiviert sind, erscheinen sie
  nicht im Zusammenfassungssatz. Grund: der Trip-Formatter kennt schlicht
  keine `_format_sunshine`/`_format_snow`-Methode; das ist unabhängig von
  #1285 und bleibt offen (eigenes Issue bei Bedarf).
- **Windrichtung** ist weiterhin **keine über `enabled_metrics` wählbare
  Matrix-Zeile** — sie ist nicht Gegenstand von Issue #1285 (das Issue nennt
  explizit nur Regen/Gewitter/UV/Sicht) und der PO-Nachtrag zur
  Regenwahrscheinlichkeit vom 2026-07-16 erstreckt sich nicht auf sie. Bei
  Bedarf eigener Nebenbefund-Eintrag (#1199) oder Issue.
- **Zeitzone je Ort:** Die zeitliche Qualifizierung (Regen-Start/-Ende,
  Böen-Peak-Zeit) braucht eine Zeitzone. `SavedLocation.timezone` ist
  optional — fehlt sie, fällt der Ort-Wrapper wie der Trip-Pfad auf UTC
  zurück (keine neue Fehlerklasse, bestehendes Verhalten übernommen).
- Diese Spec deckt die Text-Zusammenfassung (#1278) und die fünf fehlenden
  Tages-Aggregate (#1285 + PO-Nachtrag Regenwahrscheinlichkeit) ab — sie
  ändert nicht die Stundentabellen inhaltlich (außer dem benannten
  Nebenbefund-Fix am STUNDEN-Kopf). Vier der fünf Metriken brauchen keine
  neuen Frontend-Metrik-Definitionen (die existieren bereits);
  Regenwahrscheinlichkeit braucht **eine** additive Katalog-Zeile
  (`compareMetricDefs.ts::ALL_METRICS`) — s. Implementation Details.

## Test Plan

Kern-Schicht (deterministisch, keine Mocks, echte aufgezeichnete
`ForecastDataPoint`-Fixtures — Test-Dateien nach Verhalten benannt, nicht
nach Issue-Nummer):

| Test | Datei | Deckt |
|---|---|---|
| `test_shared_formatter_used_by_both_contexts` | `tests/unit/test_compare_location_summary.py` | AC-1 |
| `test_html_summary_block_position` | `tests/unit/test_compare_location_summary.py` | AC-2 |
| `test_plaintext_summary_block_position` | `tests/unit/test_compare_location_summary.py` | AC-3 |
| `test_no_frontend_toggle_summary_appears_unconditionally` | `tests/unit/test_compare_location_summary.py` | AC-4 |
| `test_summary_respects_enabled_metrics_filter` | `tests/unit/test_compare_location_summary.py` | AC-5 |
| `test_summary_includes_rain_and_thunder_when_selected` | `tests/unit/test_compare_location_summary.py` | AC-6 |
| `test_aggregate_matches_trip_path_same_hourly_data` | `tests/unit/test_compare_location_summary.py` | AC-7 |
| `test_location_title_not_shortened_like_stage_name` | `tests/unit/test_compare_location_summary.py` | AC-8 |
| `test_error_location_produces_no_empty_block` | `tests/unit/test_compare_location_summary.py` | AC-9 |
| `test_empty_hourly_data_produces_no_empty_block` | `tests/unit/test_compare_location_summary.py` | AC-9 |
| `test_summary_order_alphabetical_no_score` | `tests/unit/test_compare_location_summary.py` | AC-10 |
| `test_trip_summary_text_unchanged_byte_identical` | `tests/unit/test_compare_location_summary.py` | AC-11 |
| `test_hourly_head_no_dead_time_window_string` | `tests/unit/test_compare_location_summary.py` | AC-12 |
| `test_summary_never_contains_confidence` | `tests/unit/test_compare_location_summary.py` | AC-13 |
| `test_selected_rain_metric_appears_in_overview_matrix` (**rot vor Fix** — reproduziert die stille Verwerfung aus Nutzersicht: Auswahl gesetzt, Zeile fehlt) | `tests/unit/test_compare_matrix_metric_selection.py` | AC-14 |
| `test_selected_thunder_metric_appears_in_overview_matrix` | `tests/unit/test_compare_matrix_metric_selection.py` | AC-14 |
| `test_selected_visibility_metric_appears_in_overview_matrix` | `tests/unit/test_compare_matrix_metric_selection.py` | AC-14 |
| `test_uv_metric_appears_regardless_of_combination` (**rot vor Fix** — UV + Temp gemeinsam gewählt → UV-Zeile verschwindet heute) | `tests/unit/test_compare_matrix_metric_selection.py` | AC-14 |
| `test_selected_rain_probability_metric_appears_in_overview_matrix` (**rot vor Fix** — reproduziert die stille Verwerfung aus Nutzersicht: `pop_max_pct` in `enabled_metrics` gesetzt, Zeile fehlt) | `tests/unit/test_compare_matrix_metric_selection.py` | AC-14 |
| `test_daily_aggregate_matches_trip_path_computation` | `tests/unit/test_compare_matrix_metric_selection.py` | AC-15 |
| `test_unselected_new_metrics_leave_existing_matrix_unchanged` | `tests/unit/test_compare_matrix_metric_selection.py` | AC-16 |

## Validierung

- **Renderer-Commit-Gate #811:** `compact_summary.py` und
  `output/renderers/email/*.py` (also `compare_html.py`) sind
  gate-pflichtig — vor Commit MUSS `tests/tdd/test_issue_811_mode_matrix.py`
  grün sein UND ein `briefing_mail_validator.py`-Lauf gegen eine echt
  zugestellte Trip-Mail (Staging) vorliegen (Trip-Regression, AC-11).
- **Compare-Mail-Validierung:** `email_spec_validator.py`
  (Marker-Header `X-GZ-Mail-Type: compare`) gegen eine echt zugestellte
  Staging-Mail — deckt AC-2/AC-3/AC-6/AC-9/AC-10/AC-12/AC-14 auf Ebene der
  tatsächlich ausgelieferten Mail ab. `comparison.py` (Plaintext-Compare-
  Renderer) ist selbst nicht in der Gate-Dateiliste von #811 enthalten
  (nur `compact_summary.py`/`email/*.py`) — die Plaintext-Regression wird
  daher zusätzlich über den Compare-Mail-Validator abgesichert, nicht über
  das Renderer-Gate.
- `comparison_engine.py`/`app/user.py` sind nicht Teil des Renderer-Gates,
  aber `app/user.py` triggert automatisch `data_schema_backup.py`
  (Pre-Snapshot vor jedem Edit).
- **Frontend-Katalog-Ergänzung (`compareMetricDefs.ts`):** deckt sich mit
  dem bestehenden `compareEditorSlice3.test.ts` (prüft u. a. "ALL_METRICS
  enthält alle Profile-Metriken", Mindestanzahl Einträge, keine doppelten
  Keys) — der neue Eintrag muss diesen bestehenden Test weiterhin grün
  halten, kein separates neues Test-Gate nötig.

## Querverweis: `docs/specs/modules/compact_summary.md`

Diese Arbeit erweitert den dort spezifizierten Baustein
(`CompactSummaryFormatter`) um einen zweiten Aufrufkontext. Die
Vertragsergänzung, die dort (nicht hier) nachgetragen werden sollte:
- Neuer `context`-Parameter bzw. zweiter öffentlicher Einstiegspunkt für den
  Vergleichs-Aufrufer, inkl. der Regel "Titel wird bei `context="vergleich"`
  nicht durch `_shorten_stage_name()` gekürzt".
- Die vollständige Metrik-Vokabular-Übersetzungstabelle (Frontend-ID →
  Renderer-ID → Trip-`metric_id`) aus diesem Dokument, damit
  `compact_summary.md` als Single Source of Truth für beide Aufrufer aktuell
  bleibt.

Diese Spec ändert `compact_summary.md` **nicht selbst** — das ist Aufgabe der
Implementierung/Doku-Nachpflege (`docs-updater`), nicht des Spec-Writers.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0026 (Stand nach Rebase auf `origin/main` @ 22269cba).
  Vergabe-Historie dieser Spec: zuerst 0024 (falsch — durch #1272 belegt,
  Commit 450d9e6f, geteilter Sortier-Baustein), dann 0025 — beim Rebase
  stellte sich heraus, dass **0025 in `main` bereits doppelt vergeben** ist:
  `docs/adr/0025-e2e-prod-network-unreachable-admin-loses-never-delete.md`
  (#1284) und `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md`
  (#1275) — zwei parallele Sessions haben dieselbe Nummer gezogen. Diese Spec
  weicht daher auf 0026 aus. Die Doppelvergabe von 0025 in `main` ist ein
  Nebenbefund (nicht Gegenstand dieser Arbeit) und zeigt, dass die
  ADR-Nummernvergabe bei parallelen Sessions keine Kollisionssicherung hat.
- **Rationale:** Diese Arbeit führt das `context="route"|"vergleich"`-Muster
  erstmals im Python-Renderer-Code ein (bisher nur im Frontend als
  `LayoutTab`/`VersandTab`-Pendant bekannt) und legt eine dauerhafte, jetzt
  **vollständige** Übersetzungstabelle zwischen drei unterschiedlichen
  Metrik-Vokabularen an (Frontend-ID, Compare-Renderer-ID, Trip-`metric_id`).
  Beides ist eine wiederverwendbare, strukturelle Entscheidung mit Tragweite
  für die laufende Trip/Compare-Konvergenz (Epic #1230) — kein einmaliger
  Implementierungsdetail-Trade-off, daher ADR statt "keine".

## Changelog

- 2026-07-17: v2.3 — **ADR-Nummer auf ADR-0026** (dritte Korrektur). Beim
  Rebase auf `origin/main` @ 22269cba zeigte sich, dass 0025 dort inzwischen
  **doppelt** vergeben ist (#1284 und #1275, zwei parallele Sessions). Kein
  inhaltlicher Änderung an ACs oder Umfang.
- 2026-07-16: v2.2 — **AC-16 aufgeteilt, neues AC-17** (PO-Entscheid während
  der RED-Phase). Der Developer-Agent wies nach, dass AC-16 in der Fassung
  "kein bestehender Vergleich zeigt plötzlich neue Zeilen" zusammen mit dem
  `None`-Verhalten der Implementation Details ("alle mappbaren Metriken
  aktiv") **nicht erfüllbar** war: sobald die neuen Zeilen in `CV2_METRICS`
  stehen, zeigt jeder Vergleich ohne getroffene Auswahl sie ungefragt.
  Auflösung durch den PO: `enabled_metrics=None` ("nie ausgewählt") zeigt
  alles inklusive der neuen Zeilen (AC-17); der Bestandsschutz (AC-16) gilt
  nur noch für eine bewusst getroffene Auswahl. Vermeidet eine dauerhafte
  Sonderregel im Code. AC-4-Testbeschreibung präzisiert: das Verbot neuer
  Frontend-Elemente bezieht sich auf die Zusammenfassung; die additive
  Katalog-Zeile für die Regenwahrscheinlichkeit ist davon ausgenommen
  (PO-Entscheid, s. Purpose).
- 2026-07-16: v2.1 — PO-Entscheid: Regenwahrscheinlichkeit (`pop_max_pct`)
  kommt zur Metrik-Liste von #1285 dazu (aus "vier" werden "fünf"),
  Begründung: exakt derselbe Verdrahtungs-Befund wie beim Gewitter
  (`comparison_engine.py:181`), dieselbe Codestelle, kaum berechnungsseitiger
  Mehraufwand — einen bekannten stillen Fehler an einer ohnehin angefassten
  Stelle stehenzulassen wäre nicht vertretbar. Fact-Check-Ergänzung: anders
  als bei den anderen vier fehlt für Regenwahrscheinlichkeit als
  Tages-Matrix-Metrik heute die Frontend-Auswahlmöglichkeit
  (`compareMetricDefs.ts::ALL_METRICS` hat keinen Eintrag; die existierende
  `pop_pct`-ID in `compareHourlyMetricDefs.ts` ist ein anderes, bereits
  korrekt funktionierendes Vokabular für die Stundenspalten) — eine additive
  Katalog-Zeile ist daher Teil dieses Fixes, kein neues UI-Element. AC-14/
  AC-15/AC-16 auf fünf Metriken erweitert. Übersetzungstabelle um
  `rain_probability`/`pop_max_pct`-Zeile ergänzt (Fließtext-Sonderregel:
  teilt sich den `_format_precipitation`-Zweig mit `precipitation`, bestehendes
  Trip-Verhalten). Known Limitations: Regenwahrscheinlichkeit gestrichen, nur
  Windrichtung bleibt als Ausschluss stehen. LoC-Schätzung leicht auf
  ≈230–330 erhöht — durch bereits erteilte `loc_limit_override 500`
  weiterhin abgedeckt, keine erneute PO-Freigabe nötig.
- 2026-07-16: v2.0 — Scope-Erweiterung um Issue #1285 (PO-Entscheid:
  gemeinsame Arbeit mit #1278, da beide dieselben Tages-Aggregate brauchen).
  ADR-Nummer auf ADR-0025 korrigiert (0024 war bereits durch #1272 vergeben).
  Neue ACs 14–16 für die Tages-Aggregate. AC-Nummerierung ab AC-8
  verschoben (alte AC-6 "identische Wetterdaten" wurde AC-7 usw.), weil eine
  neue AC-6 für Regen/Gewitter im Fließtext eingefügt wurde. Known
  Limitations bereinigt: fehlender Regen/Gewitter ist keine Limitation mehr;
  Windrichtung/Regenwahrscheinlichkeit bleiben explizit außerhalb des
  Scopes, mit Begründung.
- 2026-07-16: v1.0 Initial spec (Issue #1278, Context-Doc
  `docs/context/feat-1278-compare-ort-zusammenfassung.md`)
