# Context: Ortsvergleich-Metrik-Auswahl auf geteilten /api/metrics-Katalog umstellen (#1324)

## Request Summary
Der Ortsvergleich pflegt einen eigenen, kürzeren Metrik-Katalog (`compareMetricDefs.ts`, 15 Einträge) statt des geteilten Trip-Katalogs (`metric_catalog.py`, 24 Einträge). Dadurch fehlen im Vergleich 8 Metriken (u. a. Windrichtung). Ziel: Vergleich bezieht Metriken aus derselben Quelle wie der Trip. `CompareEditor.svelte` (Legacy, fällt mit F2b weg) wird laut Tech-Lead-Entscheidung **nicht** migriert.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py` | Geteilter Katalog (24 Metriken), `MetricDefinition`-Dataclass, `get_all_metrics()` filtert `selectable=True` |
| `api/routers/config.py:30-33` | Route `GET /api/metrics` |
| `src/output/renderers/compare_metric_ids.py` | `FRONTEND_TO_RENDERER_METRIC_ID` (15 alte IDs), `RENDERER_TO_TRIP_METRIC_ID`, `CORRIDOR_METRIC_TO_HOUR_KEY` — muss um 8 Metriken erweitert werden |
| `src/services/weather_metrics.py` | `summarize_points()` (Compare-Pfad, l.985-1014) nutzt nur `compute_basis_metrics` + wenige Extras, **nicht** `compute_extended_metrics` — Aggregationslücke |
| `frontend/src/lib/components/compare/corridor-editor/corridorEditorState.ts` | Zentral betroffen: `COMPARE_METRIC_DEFS` (l.273) leitet sich aus `ALL_METRICS`/`PROFILE_METRICS_WITH_SCALES`/`IDEAL_DEFAULTS` ab — muss auf `/api/metrics` umgestellt werden |
| `frontend/src/lib/components/compare/corridor-editor/CorridorEditor.svelte`, `CorridorEditorMobile.svelte` | Konsumieren `ProfileKey`/`CompareMetricDef` aus `corridorEditorState.ts` — betroffen über Typwechsel |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherMetricsTab.svelte` | Geteilter Tab, `context="route"|"vergleich"` (l.72,85); lädt `/api/metrics` nur bei `context==='route'` (l.283,312), bei `vergleich` noch `COMPARE_METRIC_DEFS` (l.635-660) — hier ist die eigentliche Weiche |
| `frontend/src/lib/components/shared/alarme-tab/compareMetricMapping.ts` | Eigenes hartcodiertes Mapping `COMPARE_TO_ALERT_METRIC`, kein Import aus compareMetricDefs — nur betroffen falls sich Metrik-Keys ändern |
| `frontend/src/lib/components/compare/compareEditorSave.ts` | Read-Modify-Write für `display_config` (l.78-104) |
| `internal/handler/config_merge.go:8-11` | Backend-Merge für `DisplayConfig` — löscht nie Keys |

## Existing Patterns
- **Trip-Pfad als Vorbild:** Trip lädt Metriken bereits aus `/api/metrics` (`WeatherMetricsTab.svelte` mit `context==='route'`) — dasselbe Muster soll für `context==='vergleich'` gelten.
- **Read-Modify-Write für Presets** ist bereits etabliert (`compareEditorSave.ts`, `config_merge.go`) — keine neue Logik nötig, nur beachten (s. `reference_compare_display_config_merge_only_no_delete`).
- **Circular Mean für Windrichtung existiert bereits** (`_compute_wind_direction`, `_circular_mean_deg` in `weather_metrics.py`), wird aber im Compare-Aggregationspfad (`summarize_points`) nicht aufgerufen — reines Verdrahtungsproblem, keine neue Mathematik nötig.

## Dependencies
- **Upstream:** `src/app/metric_catalog.py` (Datenquelle), `weather_metrics.py` (Aggregation)
- **Downstream:** `email/compare_html.py` (Mail-Rendering, **Renderer-Mail-Gate #811 greift**), `compact_summary.py`, `report_config_resolver.py`, `compare_hourly_metric_ids.py` (separates Vokabular, nicht betroffen)

## Existing Specs
- `docs/specs/modules/compare_weather_metrics_tab.md` — WeatherMetricsTab, direkte Vorlage
- `docs/specs/modules/issue_1296_compare_metrics_dropped.md`, `issue_1298_compare_metric_guard_cape_label.md`, `issue_1105_compare_snow_metric.md` — verwandte Compare-Metrik-Bugs, Anti-Pattern-Referenzen

## Risks & Considerations
- **Aggregationslücke:** Für `snowfall_limit` und `cloud_low/mid/high` gibt es im Compare-Pfad noch **keine** Tages-Kennzahl-Funktion (nur Rohdaten für Nachthimmel-Logik). Diese 4 Metriken brauchen zusätzliche Aggregationsarbeit — die anderen 4 (`wind_direction`, `wind_chill`, `dewpoint`, `pressure`, `precip_type` — humidity ist bereits im Pfad) sind reines Verdrahten.
- **Renderer-Mail-Gate #811:** `email/compare_html.py` ist gate-pflichtig — vor Commit `briefing_mail_validator.py` + `tests/tdd/test_issue_811_mode_matrix.py` grün.
- **Legacy-Ausschluss:** `CompareEditor.svelte` bleibt bewusst beim alten Katalog (Tech-Lead-Entscheidung, wird mit F2b gelöscht) — keine Migration dort, aber sicherstellen, dass Typänderungen in `corridorEditorState.ts` `CompareEditor.svelte` nicht kaputt kompilieren lassen (falls es dieselben Typen importiert).
- **Rote Tests erwartet:** `corridorEditorState.test.ts`, `compareEditorSlice3.test.ts`, `issue_718_idealwert_validation.test.ts`, `compare_matrix_dead_code.test.ts` — müssen aktualisiert werden, nicht nur grün geprügelt.
- **Keine stille Metrik-Verwerfung** für Bestandspresets (Daten-Schema-Rework-Pflicht).

## Analysis

### Type
Feature

### Kurskorrektur gegenüber Issue-Text (kritischer Befund)

Der im Issue #1324 vorgeschlagene Lösungsweg — Compare komplett auf `/api/metrics`
(Trip-Katalog) umstellen, `compareMetricDefs.ts` entfällt — wurde **einen Tag vorher**
(2026-07-18) im eng verwandten Spec `docs/specs/modules/compare_weather_metrics_tab.md`
(Epic #1301 C1, ADR-0026) bereits erprobt und noch vor Fertigstellung explizit
zurückgenommen (Changelog-Eintrag „GREEN"-Korrektur, Zeile 416-419 der Spec).
**Grund:** Trip-Namensraum (`temperature`, `gust`, …) und Compare-Namensraum
(`temp_max_c`, `gust_max_kmh`, …) sind nicht 1:1 kompatibel; nur der
Compare-Namensraum erzeugt über `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID`
tatsächliche Mail-Wirkung (dortiges AC-2/AC-8). Unbekannte IDs werden von
`resolve_enabled_metrics()` bewusst **verworfen statt zu crashen** (Guard aus
#1296, Zeile 97-105 `compare_metric_ids.py`) — ein Wechsel auf rohe
`/api/metrics`-IDs würde also nicht crashen, sondern die betroffenen Metriken
still aus der Mail verschwinden lassen (derselbe Bug-Typ wie #1285/#1296, den
der Guard gerade verhindern soll).

**Korrigierter technischer Ansatz (Tech-Lead-Entscheidung):** Ziel bleibt
identisch (Windrichtung u. a. im Vergleich wählbar), Mechanismus ändert sich:

1. `compareMetricDefs.ts::ALL_METRICS` um 8 neue `MetricDef`-Einträge im
   bestehenden Compare-Namensraum erweitern (analog den 2026-07-16/17 bereits
   nachgetragenen 9 Einträgen aus #1285/#1296 — etabliertes Muster, kein
   Neuland). `compareMetricDefs.ts` bleibt bestehen, wird NICHT gelöscht.
2. `compare_metric_ids.py::FRONTEND_TO_RENDERER_METRIC_ID` um die 8
   entsprechenden Einträge erweitern.
3. `weather_metrics.py::summarize_points()` so erweitern, dass die Tages-Kennzahl
   für alle 8 Metriken im Compare-Pfad berechnet wird:
   - **Reines Verdrahten** (Funktion existiert bereits, wird nur nicht aufgerufen):
     `wind_direction` (Circular Mean, bereits für Kompakt-Zusammenfassung
     genutzt), `wind_chill`, `dewpoint`, `pressure`, `precip_type`.
   - **Neue Aggregation nötig** (noch keine Tages-Kennzahl-Funktion im
     Compare-Pfad): `snowfall_limit` (existiert bisher nur in
     `src/services/aggregation.py`, anderes Modul für Trip-Aggregation —
     muss für den Compare-Pfad nachgebaut oder wiederverwendet werden),
     `cloud_low/mid/high` (bisher nur Rohdaten für Nachthimmel-Emoji-Logik,
     keine Tages-Aggregation).
4. `CorridorEditor.svelte`/`CorridorEditorMobile.svelte`/`WeatherMetricsTab.svelte`
   (context='vergleich') bleiben bei `COMPARE_METRIC_DEFS` als Quelle — **keine**
   Umstellung auf `/api/metrics` in diesen Dateien.
5. `CompareEditor.svelte` (Legacy) unverändert (Tech-Lead-Entscheidung, s. o.).

**GitHub-Issue #1324 wird per Kommentar um diese Kurskorrektur ergänzt**, damit
der Issue-Text nicht in die Irre führt (Kern-Regel: Issues sind Single Source
of Truth).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/compare/compareMetricDefs.ts` | MODIFY | 8 neue `MetricDef`-Einträge in `ALL_METRICS` |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | 8 neue Einträge in `FRONTEND_TO_RENDERER_METRIC_ID` |
| `src/services/weather_metrics.py` | MODIFY | `summarize_points()`: 5 bestehende Aggregationsfunktionen verdrahten + 2 neue (snowfall_limit, cloud_low/mid/high) |
| `src/output/renderers/email/compare_html.py` | VERIFY/MODIFY | Rendert Übersichtszeile générisch über Mapping — ggf. keine Änderung nötig, Gate #811 prüft das |
| `tests/unit/test_compare_metric_catalog_consistency.py` | MODIFY | Konsistenz-Guard auf 23 Metriken erweitern |
| `tests/unit/test_compare_extra_daily_metrics.py` | MODIFY | Neue Aggregationstests (Vorbild für Muster #1285/#1296) |
| `tests/tdd/test_compare_outlook.py`, `test_compare_cape_severity_ambel.py` | VERIFY | ggf. betroffen falls sie feste Metrik-Zählungen prüfen |
| `frontend/src/lib/components/compare/compareEditorSlice3.test.ts`, `issue_718_idealwert_validation.test.ts` | MODIFY | neue Metriken in Testdaten |
| **NICHT geändert:** `corridorEditorState.ts`, `CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `WeatherMetricsTab.svelte`, `CompareEditor.svelte` | — | Bleiben bei `COMPARE_METRIC_DEFS`-Quelle bzw. Legacy-Ausschluss |

### Scope Assessment
- Files: ~10 (deutlich kleiner als der ursprünglich im Issue skizzierte Ansatz, da kein Katalog-Austausch nötig ist)
- Estimated LoC: +80/-5 (überwiegend neue MetricDef-Einträge + Mapping-Zeilen + 2 neue Aggregationsfunktionen)
- Risk Level: MEDIUM (Renderer-Mail-Gate #811 greift; Aggregationslücke bei 3 Metriken erfordert echte neue Logik, nicht nur Verdrahtung)

### Technical Approach
Additiv statt ersetzend: bestehendes, bereits zweimal bewährtes Muster (#1285,
#1296) — neue `MetricDef`-Einträge + Mapping-Einträge + Aggregations-Verdrahtung.
Kein Bruch der Trip/Compare-Namensraum-Trennung, keine Regression der erst
gestern gehärteten Guard-Logik.

### Dependencies
- Upstream: `weather_metrics.py` Rohdaten-Funktionen (Windrichtung, Wolkenschichten bereits vorhanden für andere Zwecke)
- Downstream: `email/compare_html.py` (Gate #811), `compact_summary.py` (nur falls RENDERER_TO_TRIP_METRIC_ID ergänzt werden soll — optional, da Fließtext-Baustein laut Doku bewusst nicht alle Metriken abdeckt)

### Open Questions
- [ ] Für `snowfall_limit` im Compare-Pfad: eigene Aggregationsfunktion in `weather_metrics.py` oder Wiederverwendung/Import aus `src/services/aggregation.py`? → Wird in Spec-Phase entschieden.

