---
entity_id: issue_1324_compare_metric_parity
type: feature
created: 2026-07-19
updated: 2026-07-19
status: implemented
version: "1.0"
tags: [compare, metrics, mapping, weather-metrics, catalog]
workflow: 1324-compare-metric-catalog
---

# Ortsvergleich: fehlende Wetter-Metriken additiv nachtragen (#1324)

## Approval

- [x] Approved (PO-Freigabe 2026-07-19)

## Purpose

Im Ortsvergleich fehlen zehn Wetter-Metriken, die im Trip-Editor längst
wählbar sind: Windrichtung, gefühlte Temperatur (Wind Chill), Luftfeuchtigkeit,
Taupunkt, Schneefallgrenze, Niederschlagsart, drei einzelne Wolkenschichten
(tief/mittel/hoch) und Luftdruck. Nutzer, die im Compare-Editor eine dieser
Größen für ihre Entscheidung (z. B. Ski- oder Wandertourenplanung) heranziehen
wollen, können sie dort nicht auswählen — nur der Trip-Editor bietet sie an.
Diese Spec trägt die Lücke additiv nach, im bereits zweimal bewährten Muster
aus #1285 und #1296 (neue `MetricDef`-Einträge + Mapping-Einträge +
Aggregations-Verdrahtung), **nicht** durch einen Wechsel des Compare-Editors
auf den geteilten Trip-Katalog `/api/metrics`.

**Hinweis zur Zahl:** Das GitHub-Issue zählt die fehlenden Größen umgangs­sprachlich
als "8 Metriken" (ein Aufzählungspunkt "Wolkenschichten tief/mittel/hoch"
bündelt dort drei Werte in einem Satz). Diese Spec führt die drei Wolkenschichten
als drei einzeln wählbare `MetricDef`-Einträge — wie im Trip-Katalog auch
(`cloud_low_pct`/`cloud_mid_pct`/`cloud_high_pct` sind dort ebenfalls getrennt
wählbar, s. `src/app/metric_catalog.py`). Die tatsächliche Zahl neuer
`MetricDef`-Einträge in dieser Arbeit ist daher **10**, nicht 8.

### Kurskorrektur gegenüber Issue-Text

Der im Issue #1324 ursprünglich vorgeschlagene Lösungsweg — Compare komplett
auf `/api/metrics` (Trip-Katalog) umstellen, `compareMetricDefs.ts` entfällt —
wurde einen Tag vorher (2026-07-18) in `docs/specs/modules/compare_weather_metrics_tab.md`
(Epic #1301 C1) bereits erprobt und noch vor Fertigstellung explizit
zurückgenommen (dortiger Changelog-Eintrag, Zeile 416-419): Trip-Namensraum
(`temperature`, `gust`, …) und Compare-Namensraum (`temp_max_c`,
`gust_max_kmh`, …) sind nicht 1:1 kompatibel; nur der Compare-Namensraum
erzeugt über `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`
tatsächliche Mail-Wirkung. Unbekannte IDs werden von `resolve_enabled_metrics()`
bewusst **verworfen statt zu crashen** (Guard aus #1296) — ein Wechsel auf
rohe `/api/metrics`-IDs würde die betroffenen Metriken also nicht zum Absturz
bringen, sondern still aus der Mail verschwinden lassen (derselbe Bug-Typ wie
#1285/#1296, den der Guard gerade verhindern soll). Diese Spec folgt deshalb
dem additiven Ansatz; `compareMetricDefs.ts` bleibt bestehen und wird NICHT
gelöscht.

### Eigene Verifikation über die Analyse hinaus (wichtige Korrekturen)

Beim Nachvollziehen der tatsächlichen Aggregationspfade ergaben sich drei
Abweichungen von der ursprünglichen Analyse (`docs/context/1324-compare-metric-catalog.md`):

1. **Fünf der zehn Metriken sind bereits heute Klasse A** (reines Mapping,
   `LocationResult`-Feld existiert und wird von BEIDEN Erzeuger-Pfaden befüllt) —
   nicht "reines Verdrahten über `weather_metrics.py`" wie ursprünglich
   angenommen: `wind_direction_avg`, `wind_chill_min`, `cloud_low_avg`,
   `cloud_mid_avg`, `cloud_high_avg` existieren bereits als `LocationResult`-Felder
   (`src/app/user.py:131-137`) und werden sowohl von `ComparisonEngine.run()`
   als auch von `dict_to_comparison_result()` befüllt
   (`src/services/comparison_engine.py:243-249` bzw. `307-313`, dortige
   Circular-Mean-/Cloud-Layer-Berechnung aus den Rohstunden). Für diese fünf
   ist **keine** Änderung an `weather_metrics.py::summarize_points()`
   nötig — nur Katalog- und Mapping-Eintrag, analog dem etablierten
   `temp_min_c`/`gust_max_kmh`-Muster aus #1296.
2. **Luftfeuchtigkeit ist bereits im Compare-Aggregationspfad vorhanden**
   (bestätigt): `summarize_points()` ruft `compute_basis_metrics()` auf, das
   `humidity_avg_pct` bereits füllt (`weather_metrics.py:435/455`). Auch hier
   ist keine neue Aggregationsfunktion nötig, nur der Mapping-Eintrag
   (Klasse B, da `LocationResult` kein `humidity`-Feld führt).
3. **`src/output/renderers/comparison.py` (Klartext-Renderer) ist zusätzlich
   betroffen** — im ursprünglichen Analyse-Context nicht gelistet, aber nach
   demselben Muster wie in #1296 zwingend: `CV2_METRICS`/`_DAILY_AGGREGATE_FIELD`
   (HTML, `compare_html.py`) und `_DAILY_PLAIN_ROWS`/die direkten
   `_metric_visible(...)`-Zeilen (Klartext, `comparison.py`) sind getrennte
   Renderer-Zeilenlisten, die beide gepflegt werden müssen — sonst zeigt die
   HTML-Mail die neue Zeile, die Klartext-Mail nicht (HTML/Text-Asymmetrie,
   exakt die Falle, die in `docs/specs/_archive/modules/issue_1296_compare_metrics_dropped.md`
   dokumentiert ist). `frontend/src/lib/components/compare/compareEditorSlice3.test.ts`
   und `issue_718_idealwert_validation.test.ts` (im Context als MODIFY
   gelistet) haben nach eigener Prüfung **keine** feste Metrik-Zahl/-Liste,
   die durch 10 neue Einträge bricht (`compareEditorSlice3.test.ts` prüft nur
   `length >= 10` und Duplikat-Freiheit) — beide bleiben VERIFY, nicht MODIFY.

## Source

- **File:** `frontend/src/lib/components/compare/compareMetricDefs.ts` —
  `ALL_METRICS` (Zeile 54-58) um 10 neue `MetricDef`-Konstanten erweitern,
  exakt im Stil der bestehenden 15 Einträge (Zeile 30-51).
- **File:** `src/output/renderers/compare_metric_ids.py` —
  `FRONTEND_TO_RENDERER_METRIC_ID` (Zeile 15-41) um 10 neue Einträge
  erweitern; `resolve_enabled_metrics()` (Zeile 85-111) bleibt unverändert
  (Guard aus #1296 gilt bereits generisch für alle Keys).
- **File:** `src/services/weather_metrics.py` — `summarize_points()`
  (Zeile 985-1015) um vier neue Zuweisungen erweitert (dewpoint, pressure,
  precip_type, snowfall_limit — s. Implementation Details); neue Methode
  `_compute_snowfall_limit()` analog `_compute_freezing_level()` (Zeile 841-846).
- **File:** `src/app/models.py` — `SegmentWeatherSummary` (Zeile 339-393)
  bekommt ein neues Feld `snowfall_limit_m: Optional[int] = None`.
- **File:** `src/output/renderers/email/compare_html.py` — `CV2_METRICS`
  (Zeile 198-224) bekommt 10 neue Zeilen; `_DAILY_AGGREGATE_FIELD`
  (Zeile 340-352) bekommt 5 neue Einträge (nur Klasse B: humidity, dewpoint,
  pressure, precip_type, snowfall_limit).
- **File:** `src/output/renderers/comparison.py` — `_DAILY_PLAIN_ROWS`
  (Zeile 42-52) bekommt 5 neue Einträge (Klasse B); im Zeilen-Block
  (Zeile 113-158) 5 neue direkte `_metric_visible(...)`-Blöcke (Klasse A,
  analog `temp_min`/`gust_max`, Zeile 125-130).
- **Identifier:** `ALL_METRICS`, `FRONTEND_TO_RENDERER_METRIC_ID`,
  `summarize_points()`, `_compute_snowfall_limit()`, `SegmentWeatherSummary`,
  `CV2_METRICS`, `_DAILY_AGGREGATE_FIELD`, `_DAILY_PLAIN_ROWS`.

> **Schicht-Hinweis:** Diese Arbeit betrifft ausschließlich Frontend-Katalog
> (`frontend/src/lib/components/compare/compareMetricDefs.ts`, SvelteKit) und
> Python-Core (`src/app/models.py`, `src/services/weather_metrics.py`,
> `src/output/renderers/`). **Kein** Go-/`internal/`-Code betroffen —
> `internal/handler/config_merge.go` ist ein generischer Key-für-Key-Merge
> (`mergeConfigMap`, verifiziert Zeile 11-22) ohne Kenntnis einzelner
> Metrik-Keys, braucht daher keine Änderung. **Deploy-Scope: Python-Core +
> Frontend-Build.**

## Estimated Scope

- **LoC:** Implementierung ~150-220 (10 `MetricDef`-Konstanten TS ~20 Zeilen,
  10 Mapping-Einträge Python ~15 Zeilen, 1 neues Modell-Feld, 1 neue
  Aggregationsfunktion ~10 Zeilen + 4 Wiring-Zeilen in `summarize_points()`,
  `compare_html.py` ~20 Zeilen [10 `CV2_METRICS`-Zeilen + 5
  `_DAILY_AGGREGATE_FIELD`-Einträge], `comparison.py` ~25 Zeilen [5 direkte
  Zeilen + 5 `_DAILY_PLAIN_ROWS`-Einträge]) + Tests ~300-450 (10 neue
  `test_selected_*`-Fälle in `test_compare_extra_daily_metrics.py`, je
  ~15-20 Zeilen, plus Regressions- und Konsistenz-Test-Anpassungen).
  **Geschätzt gesamt ~450-650 — voraussichtlich deutlich über dem
  250-LoC-Default-Limit.** Vor Implementierungsbeginn den User explizit nach
  `loc_limit_override` fragen (CLAUDE.md „Kein LoC-Override ohne
  Permission") — NICHT eigenmächtig setzen.
- **Files:** 6 MODIFY (`compareMetricDefs.ts`, `compare_metric_ids.py`,
  `models.py`, `weather_metrics.py`, `compare_html.py`, `comparison.py`),
  1 MODIFY Test (`test_compare_extra_daily_metrics.py`), 1 MODIFY Test
  (`test_compare_metric_catalog_consistency.py`, hartcodierte Zahl 15→25 in
  `test_ts_parser_finds_all_15_ids_on_real_file`), 2 VERIFY
  (`compareEditorSlice3.test.ts`, `issue_718_idealwert_validation.test.ts`),
  2 VERIFY (`corridorEditorState.test.ts`,
  `compare_matrix_dead_code.test.ts` — nach eigener Prüfung ohne
  Abhängigkeit von der Metrik-Zahl, da diese Dateien `COMPARE_METRIC_DEFS`
  bzw. Dead-Code-Prüfungen betreffen, nicht `ALL_METRICS`-Zählungen).
- **Effort:** medium-high (zehn additive Metriken statt vier wie bei #1296,
  aber kein neues Konzept — folgt 1:1 dem #1285/#1296-Muster; die größere
  Zahl treibt vor allem den Test-Umfang).

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | MODIFY | 10 neue `MetricDef`-Einträge in `ALL_METRICS` |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | 10 neue Einträge in `FRONTEND_TO_RENDERER_METRIC_ID` |
| `src/app/models.py` | MODIFY | `SegmentWeatherSummary`: neues Feld `snowfall_limit_m` |
| `src/services/weather_metrics.py` | MODIFY | `summarize_points()`: 3 bestehende Funktionen verdrahten (dewpoint, pressure, precip_type) + 1 neue Funktion (`_compute_snowfall_limit`, MIN-Regel wie Trip-Pfad) |
| `src/output/renderers/email/compare_html.py` | MODIFY | 10 neue `CV2_METRICS`-Zeilen; 5 neue `_DAILY_AGGREGATE_FIELD`-Einträge (nur Klasse B) |
| `src/output/renderers/comparison.py` | MODIFY | Klartext-Pendant: 5 direkte Zeilen (Klasse A) + 5 neue `_DAILY_PLAIN_ROWS`-Einträge (Klasse B) — sonst HTML/Text-Asymmetrie |
| `tests/unit/test_compare_extra_daily_metrics.py` | MODIFY | 10 neue Kern-Tests (rot vor Fix) für AC-2, Regressions-Erweiterung für AC-3 |
| `tests/unit/test_compare_metric_catalog_consistency.py` | MODIFY | `test_ts_parser_finds_all_15_ids_on_real_file`: erwartete Zahl 15→25 |
| `frontend/src/lib/components/compare/compareEditorSlice3.test.ts` | VERIFY | prüft nur `length >= 10` + Duplikat-Freiheit, keine harte Obergrenze — sollte unverändert grün bleiben |
| `frontend/src/lib/components/compare/issue_718_idealwert_validation.test.ts` | VERIFY | keine feste Metrik-Liste identifiziert — sollte unverändert grün bleiben |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.test.ts` | VERIFY | betrifft `COMPARE_METRIC_DEFS`-Ableitung, nicht `ALL_METRICS`-Zählung |
| `frontend/src/lib/components/compare/__tests__/compare_matrix_dead_code.test.ts` | VERIFY | Dead-Code-Prüfung auf `CompareMatrix.svelte`, unabhängig von Metrik-Zahl |
| **NICHT geändert:** `corridorEditorState.ts`, `WeatherMetricsTab.svelte`, `CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `CompareEditor.svelte` | — | Bleiben bei `COMPARE_METRIC_DEFS`-Quelle bzw. Legacy-Ausschluss (Tech-Lead-Entscheidung) |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ALL_METRICS` (`compareMetricDefs.ts:54-58`) | Const | Ziel der 10 neuen `MetricDef`-Einträge; Referenz-Katalog, den `test_all_frontend_metric_ids_have_renderer_mapping` per `_ts_metric_parser` live einliest |
| `FRONTEND_TO_RENDERER_METRIC_ID` / `resolve_enabled_metrics()` (`compare_metric_ids.py:15/85`) | Const/Function | Ziel der Mapping-Erweiterung; Guard-Funktion bleibt unverändert, deckt neue Keys automatisch mit ab |
| `LocationResult.wind_direction_avg` / `.wind_chill_min` / `.cloud_low_avg` / `.cloud_mid_avg` / `.cloud_high_avg` (`src/app/user.py:131-137`) | Field | Klasse A — bereits von `ComparisonEngine.run()` UND `dict_to_comparison_result()` befüllt (`comparison_engine.py:243-249`/`307-313`), reines Mapping ohne `weather_metrics.py`-Änderung |
| `WeatherMetricsService._compute_dewpoint()` (`weather_metrics.py:807`) / `._compute_pressure()` (812) / `._compute_precip_type()` (898) | Method | Kanonische Trip-Regeln, existieren bereits, werden nur in `summarize_points()` nicht aufgerufen |
| `WeatherMetricsService._compute_freezing_level()` (`weather_metrics.py:841`) | Method | Vorbild-Muster (AVG, gerundet) für die neue `_compute_snowfall_limit()` |
| `AggregationEngine`-Regel Schneefallgrenze (`src/services/aggregation.py:198-203`) | Reference | Kanonische Trip-Aggregationsregel: **MIN** ("niedrigste Grenze ist relevant") — `_compute_snowfall_limit()` übernimmt dieselbe Regel, damit Compare- und Trip-Pfad bei gleichen Stundendaten denselben Tageswert liefern |
| `ForecastDataPoint.wind_direction_deg` / `.wind_chill_c` / `.dewpoint_c` / `.pressure_msl_hpa` / `.snowfall_limit_m` / `.precip_type` / `.cloud_low_pct` / `.cloud_mid_pct` / `.cloud_high_pct` (`src/app/models.py:99-127`) | Field | Rohfelder, Quelle aller zehn neuen Ableitungen |
| `SegmentWeatherSummary.humidity_avg_pct` / `.dewpoint_avg_c` / `.pressure_avg_hpa` / `.wind_chill_min_c` / `.precip_type_dominant` (`models.py:349-371`) | Field | Bestehende Zielfelder, teils bereits über `compute_basis_metrics()` (humidity) gefüllt, teils Ziel der neuen Wiring-Zeilen |
| `CV2_METRICS` / `_DAILY_AGGREGATE_FIELD` / `_metric_value()` / `_daily_summary()` (`compare_html.py:198/340/369/355`) | Const/Function | Übersichts-Matrix-Renderer (HTML); `_daily_summary` wird bereits EINMAL je Ort gecacht (Issue #1296), neue Zeilen profitieren automatisch |
| `_DAILY_PLAIN_ROWS` / `render_comparison_text()` (`comparison.py:42/55`) | Const/Function | Klartext-Pendant der Übersichts-Matrix — eigene Verifikation ergab: zwingend Teil dieser Arbeit, s. Purpose |
| `test_compare_extra_daily_metrics.py` (`tests/unit/`) | Test-Vorbild | Fixture-/Assertion-Muster dieser Arbeit: echte `ForecastDataPoint`, `resolve_enabled_metrics()`, HTML/Text-Extraktion, Gleichheits-Assert gegen `WeatherMetricsService` |
| `_ts_metric_parser.parse_all_metrics_ids()` (`tests/unit/_ts_metric_parser.py`) | Test-Helper | Liest `ALL_METRICS`-Keys live aus der echten `compareMetricDefs.ts` — kein hartcodierter Abgleich mehr nötig (Härtung #1298) |
| `mergeConfigMap()` (`internal/handler/config_merge.go:11-22`) | Function | Read-Modify-Write-Merge, generisch über alle Keys — garantiert strukturell, dass Bestandspresets ohne die 10 neuen Keys keine Daten verlieren (AC-3) |

## Implementation Details

**1. `compareMetricDefs.ts` — 10 neue `MetricDef`-Konstanten**, exakt im Stil
der bestehenden Einträge (Zeile 30-51), danach in `ALL_METRICS` aufgenommen:

| Konstante | Frontend-Key | Einheit | kind | Bereich/Werte | higherIsBetter |
|---|---|---|---|---|---|
| WIND_DIRECTION | `wind_direction_deg` | ° | range | 0–360, step 10 | false (keine Vorzugsrichtung — s. Known Limitations) |
| WIND_CHILL_MIN | `wind_chill_min_c` | °C | range | -30–30, step 1 | true |
| HUMIDITY_AVG | `humidity_avg_pct` | % | range | 0–100, step 5 | false |
| DEWPOINT_AVG | `dewpoint_avg_c` | °C | range | -20–30, step 1 | false |
| SNOWFALL_LIMIT | `snowfall_limit_m` | m | range | 0–5000, step 100 | true |
| PRECIP_TYPE | `precip_type_dominant` | – | enum | `['RAIN','SNOW','MIXED','FREEZING_RAIN']` | false |
| CLOUD_LOW_AVG | `cloud_low_avg_pct` | % | range | 0–100, step 5 | false |
| CLOUD_MID_AVG | `cloud_mid_avg_pct` | % | range | 0–100, step 5 | false |
| CLOUD_HIGH_AVG | `cloud_high_avg_pct` | % | range | 0–100, step 5 | false |
| PRESSURE_AVG | `pressure_avg_hpa` | hPa | range | 950–1050, step 5 | true |

Labels auf Deutsch analog bestehendem Stil (z. B. "Windrichtung",
"Gefühlte Temp. min", "Luftfeuchtigkeit Ø", "Taupunkt Ø", "Schneefallgrenze",
"Niederschlagsart", "Wolken tief", "Wolken mittel", "Wolken hoch",
"Luftdruck Ø") — endgültige Formulierung in der Implementierung, keine
Abkürzungen, die mit bestehenden Labels kollidieren.

**2. `compare_metric_ids.py` — Mapping-Erweiterung.** Renderer-IDs für die
fünf Klasse-A-Metriken werden **identisch** zum jeweiligen `LocationResult`-Feldnamen
gewählt (`wind_direction_avg`, `wind_chill_min`, `cloud_low_avg`,
`cloud_mid_avg`, `cloud_high_avg`), damit `_metric_value()` sie über den
`field is None`-Zweig direkt per `getattr(loc, key)` liest — kein
`_DAILY_AGGREGATE_FIELD`-Eintrag nötig (identisches Muster zu
`temp_min_c`→`temp_min` aus #1296). Für die fünf Klasse-B-Metriken werden
eigene Renderer-IDs vergeben (`humidity_avg`, `dewpoint_avg`, `pressure_avg`,
`precip_type`, `snowfall_limit`), die in `_DAILY_AGGREGATE_FIELD` auf das
jeweilige `SegmentWeatherSummary`-Feld zeigen (`humidity_avg_pct`,
`dewpoint_avg_c`, `pressure_avg_hpa`, `precip_type_dominant`,
`snowfall_limit_m`).

**3. `weather_metrics.py::summarize_points()` erweitern** — analog dem
bestehenden Muster (Zeile 1011-1014):

```python
summary.humidity_avg_pct  # bereits gesetzt via compute_basis_metrics()
summary.dewpoint_avg_c = svc._compute_dewpoint(ts)
summary.pressure_avg_hpa = svc._compute_pressure(ts)
summary.precip_type_dominant = svc._compute_precip_type(ts)
summary.snowfall_limit_m = svc._compute_snowfall_limit(ts)
```

Neue Methode `_compute_snowfall_limit()` (nach demselben Muster wie
`_compute_freezing_level()`, Zeile 841-846, aber mit **MIN** statt AVG —
kanonische Trip-Regel aus `aggregation.py:198-203`): liest
`dp.snowfall_limit_m` über alle Punkte, gibt `min(...)` zurück oder `None`
bei leerer Liste.

**4. `compare_html.py` — 10 neue `CV2_METRICS`-Zeilen** (Label + Einheit,
ohne `sev`-Key, analog `temp_min`/`freezing_level` aus #1296 — keine
Severity-Ampel in dieser Arbeit, s. Known Limitations) + 5 neue
`_DAILY_AGGREGATE_FIELD`-Einträge (nur Klasse B, s. Implementation Details 2).

**5. `comparison.py` — Klartext-Pendant**, analog `temp_min`/`gust_max`
(Klasse A, Zeile 125-130) für die fünf `LocationResult`-Felder + analog
`cape_max`/`freezing_level` (Klasse B, `_DAILY_PLAIN_ROWS`) für die fünf
`SegmentWeatherSummary`-Felder. Formatierung als einfache Lambda-Funktionen
(`f"{v}°"` für Windrichtung, `f"{v}%"` für Feuchte/Wolken, `f"{v:.0f} hPa"`
für Luftdruck, `f"{v:.0f} m"` für Schneefallgrenze, deutschsprachiges Label
für `PrecipType`-Enum analog `_fmt_thunder`), da `output.metric_format.format_value()`
für keinen dieser zehn `metric_id`-Namen einen Formatierungspfad kennt
(verifiziert: kein Treffer in `src/output/metric_format.py`) — identisches
Vorgehen zu `cape_max`/`freezing_level` in #1296, kein neuer
`format_value()`-Zweig nötig.

## Expected Behavior

- **Input:** `display_config.active_metrics` enthält eine oder mehrere der
  zehn neuen Frontend-IDs (`wind_direction_deg`, `wind_chill_min_c`,
  `humidity_avg_pct`, `dewpoint_avg_c`, `snowfall_limit_m`,
  `precip_type_dominant`, `cloud_low_avg_pct`, `cloud_mid_avg_pct`,
  `cloud_high_avg_pct`, `pressure_avg_hpa`), einzeln oder in Kombination mit
  bestehenden Metriken.
- **Output:** Die zugestellte Vergleichs-Mail (HTML **und** Klartext) zeigt
  für jede gewählte dieser zehn Metriken eine eigene Übersichts-Zeile mit
  einem echten Tageswert je Ort. Der Compare-Editor bietet alle zehn als
  wählbare Optionen an (Ableitung aus `ALL_METRICS`, unverändertes
  `WeatherMetricsTab.svelte`). `enabled_metrics=None` (keine Auswahl
  getroffen) zeigt weiterhin alle mappbaren Zeilen — jetzt inklusive der
  zehn neuen.
- **Side effects:** `SegmentWeatherSummary` (neues Feld `snowfall_limit_m`
  in `src/app/models.py`) ist eine transiente Aggregations-Struktur, die
  NICHT in `data/users/<user_id>/…` persistiert wird (sie wird pro
  Mail-Rendering neu aus `hourly_data` abgeleitet). Der Pre-Snapshot-Hook
  `data_schema_backup.py` löst dennoch automatisch aus, weil `models.py`
  pauschal als schema-relevant gilt (CLAUDE.md) — reine Sicherheitsnetz-Auslösung
  ohne tatsächliches Datenverlust-Risiko, da kein Bestandsdatensatz dieses
  Feld je enthielt oder enthalten wird.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet den Wertebereiche-Tab im Compare-Editor,
  When die Metrik-Liste gerendert wird, Then erscheinen alle zehn neuen
  Metriken (Windrichtung, Wind Chill min, Luftfeuchtigkeit Ø, Taupunkt Ø,
  Schneefallgrenze, Niederschlagsart, Wolken tief/mittel/hoch, Luftdruck Ø)
  als eigenständig wählbare Optionen, zusätzlich zu den 15 bestehenden.
  - Test: `_ts_metric_parser.parse_all_metrics_ids()` liest die echte
    `compareMetricDefs.ts` und findet 25 eindeutige IDs (Kern-Test,
    `test_compare_metric_catalog_consistency.py`); da `WeatherMetricsTab.svelte`
    (`context='vergleich'`) generisch über `COMPARE_METRIC_DEFS` iteriert,
    das direkt aus `ALL_METRICS` abgeleitet wird, und diese Iteration nicht
    Teil dieser Änderung ist (Non-Goal), belegt der Katalog-Test die
    Sichtbarkeit strukturell — keine zusätzliche UI-Rendering-Prüfung nötig.

- **AC-2:** Given ein Nutzer hat eine der zehn neuen Metriken im
  Compare-Editor aktiviert, When die Vergleichs-Mail gerendert und an das
  Stalwart-Test-Postfach zugestellt wird, Then erscheint in der echt
  zugestellten Mail (HTML **und** Klartext) eine Zeile mit dieser Metrik und
  einem realen Tageswert je Ort — nicht nur in der Persistenz, sondern in der
  tatsächlichen Mail-Ausgabe.
  - Test: Kern-Schicht — `resolve_enabled_metrics([<Frontend-ID>])` →
    `render_compare_html(...)`/`render_comparison_text(...)` mit echten
    `ForecastDataPoint`-Fixtures zeigt die Zeile mit einem Wert, der für
    Klasse-B-Metriken gegen `WeatherMetricsService`-Referenzberechnung und
    für Klasse-A-Metriken gegen den `ComparisonEngine`-Referenzwert geprüft
    wird (je 1 `test_selected_*_metric_appears_in_overview_matrix`-Fall,
    zehnfach, in `test_compare_extra_daily_metrics.py`, rot vor Fix).
    Zusätzlich PFLICHT vor „E2E bestanden": `email_spec_validator.py`
    (Marker `X-GZ-Mail-Type: compare`) gegen eine echt zugestellte
    Staging-Mail (`gregor-test@henemm.com`) für mindestens eine
    Klasse-A- und eine Klasse-B-Metrik.

- **AC-3:** Given ein bestehendes Compare-Preset speichert `active_metrics`
  ohne die zehn neuen IDs, When der Nutzer eine andere Einstellung im Editor
  ändert und speichert (Read-Modify-Write über `compareEditorSave.ts` +
  `mergeConfigMap()`), Then bleiben alle zuvor gespeicherten Felder inklusive
  der (fehlenden) neuen Metrik-Keys unverändert erhalten — kein Datenverlust
  durch Replace.
  - Test: Regressionstest mit einem vorher aufgezeichneten `display_config`
    ohne die neuen Keys; nach einem simulierten Merge-Update eines
    unabhängigen Feldes bleiben alle ursprünglichen Keys/Werte identisch
    vorhanden (Kern-Test, analog `test_existing_eleven_metrics_unchanged_after_fix`
    aus #1296, hier auf `mergeConfigMap`-Ebene bzw. bestehende
    Merge-Testsuite erweitert).

- **AC-4 (struktureller Guard, Regressionsschutz #1296):** Given eine
  Metrik-ID ohne Renderer-Mapping wird an `resolve_enabled_metrics()`
  übergeben (simuliert eine künftige 26. Metrik ohne Nachpflege), When die
  Auswahl aufgelöst wird, Then wird sie defensiv verworfen (kein Crash) und
  ein sichtbares WARNING geloggt — und der bestehende Konsistenz-Test
  bestätigt, dass alle 25 aktuell wählbaren IDs (15 bestehende + 10 neue)
  ein Mapping besitzen.
  - Test: bestehende Tests `test_unmapped_metric_logs_warning_instead_of_silent_drop`
    und `test_all_frontend_metric_ids_have_renderer_mapping`
    (`test_compare_metric_catalog_consistency.py`) laufen unverändert grün
    (sie lesen `ALL_METRICS` live via Parser, s. Purpose Punkt 3);
    `test_ts_parser_finds_all_15_ids_on_real_file` wird auf die neue
    Gesamtzahl 25 angepasst.

- **AC-5 (Non-Goal-Test):** Given diese Arbeit ist abgeschlossen, When der
  Diff gegen `main` geprüft wird, Then enthält
  `frontend/src/lib/components/compare/CompareEditor.svelte` (Legacy) **keine**
  Änderung, ebenso `corridorEditorState.ts`, `WeatherMetricsTab.svelte`,
  `CorridorEditor.svelte`, `CorridorEditorMobile.svelte` — diese fünf Dateien
  bleiben bei `COMPARE_METRIC_DEFS` als Quelle bzw. Legacy-Ausschluss
  (Tech-Lead-Entscheidung, s. Purpose/Kurskorrektur).
  - Test: `git diff --stat origin/main...HEAD -- <die fünf Pfade>` liefert
    keine Zeilen (Review-/CI-Nachweis, kein pytest-Test — das Fehlen einer
    Code-Änderung lässt sich nicht sinnvoll als Unit-Test formulieren).

## Known Limitations

- **Windrichtung als Tagesmittel ist eine Näherung:** Der Circular-Mean-Wert
  (`_compute_wind_direction`/`ComparisonEngine`-Pendant) beschreibt die
  mittlere Richtung über den Tag, **nicht** eine "Haupt-Windrichtung" (z. B.
  bei zwei entgegengesetzten Starkwind-Phasen morgens/abends kann der
  Mittelwert eine Richtung zeigen, die zu keiner der beiden Phasen passt).
  Gilt identisch für den Trip-Pfad, keine neue Einschränkung dieser Arbeit.
- **Kein Zusammenfassungssatz-Pendant:** `RENDERER_TO_TRIP_METRIC_ID`
  (`compare_metric_ids.py:44-58`) bleibt für alle zehn neuen Metriken ohne
  Eintrag — der geteilte Fließtext-Baustein (`CompactSummaryFormatter`) kennt
  keine `_format_wind_direction`/`_format_humidity`/`_format_dewpoint`/etc.-Methode.
  Sie erscheinen in der Übersichts-Matrix, aber nicht im Zusammenfassungssatz
  je Ort. Kein Teil dieses Fixes (identische Einschränkung wie in #1296).
- **Korridor-Markierung (`CORRIDOR_METRIC_TO_HOUR_KEY`) unverändert:** Keine
  der zehn neuen Metriken wird dort ergänzt — Tages-Aggregat gegen
  Einzelstundenwert wäre für Ø-/Summen-Größen (Feuchte, Taupunkt, Druck,
  Wolkenschichten) fachlich falsch (identische Begründung wie bei
  `precip_sum_mm`/`uv_index_max` aus #1296).
- **Keine Severity-Färbung:** Keine der zehn neuen `CV2_METRICS`-Zeilen
  bekommt in dieser Arbeit einen `sev`-Key/eine Ampel-Farbe — konsistent mit
  ADR-0007 (Daten statt Empfehlungen) und dem #1296-Präzedenzfall für
  Metriken ohne AC-Anforderung an Färbung. Mögliche Folge-Arbeit, kein Teil
  dieser Spec.
- **`precip_type_dominant` ist eine Kategorie, keine Zahl:** Anzeige als
  deutschsprachiges Label (RAIN→Regen, SNOW→Schnee, MIXED→Mischniederschlag,
  FREEZING_RAIN→Eisregen), analog `_fmt_thunder`. `higherIsBetter` im
  Frontend-Katalog ist für diese Enum-Metrik semantisch ohne echte Bedeutung
  (wie bereits bei `THUNDER` im Bestandskatalog) — rein strukturelles Feld,
  keine funktionale Auswirkung.

## Test Plan

Kern-Schicht (deterministisch, keine Mocks, echte aufgezeichnete
`ForecastDataPoint`-Fixtures — Vorbild: `tests/unit/test_compare_extra_daily_metrics.py`):

| Test | Datei | Deckt |
|---|---|---|
| `test_selected_wind_direction_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse A) |
| `test_selected_wind_chill_min_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse A) |
| `test_selected_cloud_low_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse A) |
| `test_selected_cloud_mid_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse A) |
| `test_selected_cloud_high_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse A) |
| `test_selected_humidity_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse B) |
| `test_selected_dewpoint_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse B) |
| `test_selected_pressure_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse B) |
| `test_selected_precip_type_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse B) |
| `test_selected_snowfall_limit_metric_appears_in_overview_matrix` (rot vor Fix) | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klasse B) |
| `test_summarize_points_yields_dewpoint_pressure_precip_type_snowfall_limit` | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Aggregations-Nachweis ohne Renderer-Umweg) |
| `test_plaintext_shows_all_ten_new_rows` | `tests/unit/test_compare_extra_daily_metrics.py` | AC-2 (Klartext-Parität) |
| `test_existing_display_config_unaffected_by_merge_of_unrelated_field` | `tests/unit/test_compare_extra_daily_metrics.py` bzw. bestehende Merge-Testsuite | AC-3 |
| `test_unmapped_metric_logs_warning_instead_of_silent_drop` (unverändert grün) | `tests/unit/test_compare_metric_catalog_consistency.py` | AC-4 |
| `test_all_frontend_metric_ids_have_renderer_mapping` (unverändert grün) | `tests/unit/test_compare_metric_catalog_consistency.py` | AC-4 |
| `test_ts_parser_finds_all_15_ids_on_real_file` → Zahl auf 25 angepasst | `tests/unit/test_compare_metric_catalog_consistency.py` | AC-1/AC-4 |
| `test_existing_fifteen_metrics_unchanged_after_addition` (Regression) | `tests/unit/test_compare_extra_daily_metrics.py` | Bestandsschutz (analog AC-7 aus #1296) |

Bug-Nachweis (CLAUDE.md Test-Politik): Die zehn `test_selected_*`-Fälle
reproduzieren die fehlende Auswahl wörtlich aus Nutzersicht (Metrik im
Editor-Katalog nicht wählbar bzw. bei Wahl folgenlos) — rot vor Fix, grün
nach Fix, identisches Muster zu #1285/#1296.

## Validierung

- **Renderer-Commit-Gate #811:** `compare_html.py` liegt unter
  `src/output/renderers/email/*.py` und ist damit gate-pflichtig — vor
  Commit MUSS `tests/tdd/test_issue_811_mode_matrix.py` grün sein UND ein
  `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Trip-Mail
  (Staging) vorliegen (Trip-Regression-Nachweis). `compare_metric_ids.py`,
  `weather_metrics.py`, `models.py` und `comparison.py` liegen **nicht** in
  der Gate-Dateiliste von #811 (verifiziert gegen CLAUDE.md-Dateiliste).
- **Compare-Mail-Validierung (PFLICHT vor „E2E bestanden"):**
  `email_spec_validator.py` (Marker-Header `X-GZ-Mail-Type: compare`) gegen
  eine echt zugestellte Staging-Mail aus dem Stalwart-Test-Postfach
  (`gregor-test@henemm.com`) — deckt AC-2 auf Ebene der tatsächlich
  ausgelieferten Mail ab (HTML **und** Klartext-Teil prüfen, wegen der in
  Purpose dokumentierten HTML/Text-Asymmetrie-Gefahr).
- `src/app/models.py` ist schema-relevant (CLAUDE.md) — der
  Pre-Snapshot-Hook `data_schema_backup.py` löst beim Edit automatisch aus.
  Kein manuelles Eingreifen nötig, reine Sicherheitsnetz-Auslösung (s.
  Expected Behavior „Side effects").

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Arbeit folgt exakt dem mit #1285/#1296 etablierten
  additiven Muster (Katalog-Eintrag + Mapping-Eintrag + `CV2_METRICS`-/
  `_DAILY_PLAIN_ROWS`-Zeile + optionale Live-Ableitung via
  `summarize_points()` für Metriken ohne eigenes `LocationResult`-Feld). Die
  Kurskorrektur gegenüber dem ursprünglichen Issue-Vorschlag (Compare NICHT
  auf `/api/metrics` umstellen) ist bereits an anderer Stelle
  architekturrelevant entschieden und dokumentiert worden — in
  `docs/specs/modules/compare_weather_metrics_tab.md` (Epic #1301 C1,
  Changelog-Eintrag „GREEN"-Korrektur, 2026-07-18) — und wird hier nur
  angewendet, nicht neu getroffen. Diese Spec selbst führt kein neues
  Konzept, keine neue Abhängigkeit und keine strukturelle Entscheidung mit
  Tragweite ein: zehn weitere additive Einträge in bereits bestehenden
  Übersetzungstabellen, ein neues transientes Aggregat-Feld und eine neue
  Aggregationsfunktion nach etabliertem Muster.

## Changelog

- 2026-07-19: Initial spec created (Issue #1324). Eigene Verifikation über
  die Analyse hinaus ergab: (a) fünf der zehn Metriken (Windrichtung, Wind
  Chill, drei Wolkenschichten) sind bereits heute Klasse A —
  `LocationResult`-Felder existieren und werden von beiden Erzeuger-Pfaden
  befüllt, keine `weather_metrics.py`-Änderung nötig; (b) Luftfeuchtigkeit
  ist im Compare-Aggregationspfad bereits vorhanden (`compute_basis_metrics`),
  nur der Mapping-Eintrag fehlt; (c) `src/output/renderers/comparison.py`
  (Klartext-Renderer) ist zusätzlich zum ursprünglichen Context-Dokument als
  betroffene Datei identifiziert worden — sonst HTML/Text-Asymmetrie; (d) die
  tatsächliche Zahl neuer `MetricDef`-Einträge ist 10, nicht 8 (drei
  Wolkenschichten einzeln gezählt); (e) `compareEditorSlice3.test.ts` und
  `issue_718_idealwert_validation.test.ts` (im Analyse-Context als MODIFY
  vermutet) enthalten keine feste Metrik-Zahl/-Liste und bleiben VERIFY.
