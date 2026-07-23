# Context: fix-1350-compare-metric-select (Teil 2 von #1350)

## Request Summary
Die **Auswahlliste** wählbarer Metriken im Vergleich-Editor (`WeatherMetricsTab.svelte`,
`context='vergleich'`) soll ihre Metriken aus dem in Teil 1 gebauten Backend-Endpoint
`GET /api/compare/metrics` beziehen — statt aus dem statischen Frontend-Import
`COMPARE_METRIC_DEFS`. Ziel: eine neue Backend-Metrik erscheint OHNE Frontend-Code-Änderung
auch im Vergleich. **Nur die Checkbox-Auswahlliste** — Schwellen-Slider/Pool/Winner-Box
bleiben Teil 3.

## Related Files
| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | **Ziel.** `{#if context==='vergleich'}` ab Z.701; Auswahlliste `{#each COMPARE_METRIC_DEFS}` Z.712–723 (nutzt nur `def.metric`+`def.label`); Import Z.56; Toggle `toggleCompareMetric()` Z.643–649; Trip-Fetch-Muster `load()` Z.310–320 (`api.get('/api/metrics')`) |
| `frontend/src/lib/api.ts` | API-Client `api.get<T>()` (Z.29) — Vorbild für neue `/api/compare/metrics`-Anbindung; **noch keine Client-Funktion dafür** |
| `frontend/src/lib/types.ts` | Typen; neuer Katalog-Eintrags-Typ nötig |
| `src/output/renderers/compare_metric_catalog.py` | Endpoint-Datenquelle, 25 Einträge, Felder `key/label/unit/decimals/higherIsBetter/kind(+rangeMin/Max/step\|ordinalLabels\|enumValues)` |
| `api/routers/compare.py:11` | FastAPI-Route → `{"metrics":[...]}` |
| `internal/router/router.go:155` | Go-Proxy `/api/compare/metrics` → Python-Core (existiert) |
| `frontend/.../corridor-editor/corridorEditorState.ts:219-289` | `CompareMetricDef` + `COMPARE_METRIC_DEFS` — **bleibt** (Schwellen/Pool, Teil 3) |
| `frontend/.../weather-metrics-tab/weatherMetricsCompareSave.ts:12,25` | Default-„alle Keys aktiv"-Fallback bei nie gespeichertem Preset — **bleibt** auf `COMPARE_METRIC_DEFS` (Persistenz-Hydration = Teil 3) |

## Existing Patterns
- **Katalog-Fetch (Trip):** `load()` → `api.get<MetricCatalog>('/api/metrics')` → State `catalog`, Gate `catalogLoaded`, Fehlerpfad `load-error-shell` + Retry-Button (Z.727–740). Der Vergleich-Zweig übernimmt genau dieses Muster für `/api/compare/metrics`.
- **Vergleich-Zweig fetcht heute NICHT** (Issue #1311 bewusst: `load()` nur für `context==='route'`, Z.344). Teil 2 führt den Fetch + Lade-/Fehlerzustand für den Vergleich ein.
- **Feld-Naming:** Backend liefert `key`, Frontend nutzt `metric` → Mapping `key → metric` beim Konsumieren.

## Dependencies
- **Upstream (was wir nutzen):** `/api/compare/metrics` (Teil 1, live seit a824a6cc), `api.get`.
- **Downstream (was betroffen ist):** nur die Anzeige der Checkbox-Liste im Vergleich-Editor (Edit-Hub + `/compare/new`, beide teilen `WeatherMetricsTab`). Persistenz (`display_config.active_metrics`, Keys `temp_max_c` …) **unverändert** — Keys sind bit-identisch zwischen Endpoint, `COMPARE_METRIC_DEFS` und `FRONTEND_TO_RENDERER_METRIC_ID`.

## Existing Specs
- `docs/specs/modules/compare_metric_catalog_endpoint.md` (Teil 1)
- Kontext Teil 1: `docs/context/fix-1350-compare-metric-catalog-source.md`

## Design-Entscheidungen (Analyse)
- **D1 Client-Anbindung:** Neue `api.get('/api/compare/metrics')` → `{metrics: [...]}`; neuer TS-Typ für den Katalog-Eintrag (`key`+`label` genügen der Liste, weitere Felder für Teil 3 mitgeführt/typisiert).
- **D2 Fetch-Ort & Zustand:** Vergleich-Zweig lädt den Katalog in eigenen State; Lade- und Fehlerzustand analog Route-Zweig (Retry). **Kein leerer Editor bei Fehler** — sichtbarer Fehler + Wiederholen.
- **D3 Listenquelle:** `{#each}` iteriert über den gefetchten Katalog (`key`→metric, `label`), Reihenfolge = Endpoint-Reihenfolge (= heutige `ALL_METRICS`-Reihenfolge, unverändert).
- **D4 Boundary zu Teil 3:** `COMPARE_METRIC_DEFS` und der Default-alle-Fallback in `weatherMetricsCompareSave.ts` bleiben unangetastet. Nur die Anzeige-Liste wechselt die Quelle.
- **D5 Persistenz/Reaktivität:** Toggle-Verhalten unverändert; genau ein Save pro Toggle; bestehende Presets laden unverändert (Keys identisch).

## Risks & Considerations
- **Svelte-5-Reaktivitäts-Race:** Neuer async-Fetch im bisher synchronen Vergleich-Zweig → Staging-PUT-Count-Prüfung Pflicht (kein Extra-PUT durch den Ladevorgang, kein „Ladevorgang als Nutzeränderung").
- **`createMode` (`/compare/new`):** Fetch muss auch beim Neu-Anlegen laufen (Hub + New teilen `WeatherMetricsTab`).
- **Fehlerpfad:** Endpoint-Ausfall darf nicht zu still leerer Liste führen (würde wie „keine Metriken" aussehen).
- **Scope-Disziplin:** Nicht in Teil-3-Terrain (Schwellen-Slider/Winner-Box/`compareMetricDefs.ts`-Abriss) laufen.
