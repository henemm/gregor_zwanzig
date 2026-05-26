---
entity_id: issue_362_score_toggle
type: module
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
issue: 362
tags: [frontend, sveltekit, go, compare, scoring, weather-config, locations, subscriptions]
---

# Issue #362 — ScoreToggle: Score-Zugehörigkeit pro Metrik im Orts-Vergleich

## Approval

- [ ] Approved

## Purpose

Ergänzt den `WeatherConfigDialog.svelte` (Editor für Orte und Abonnements) um einen Segmented-Toggle pro aktivierter Metrik, mit dem der User steuert ob eine Metrik in den 0–100-Compare-Score einfließt oder nur in der Anzeige erscheint. Die Go-Compare-Engine in `scoring.go` wird so erweitert, dass sie beim Score-Berechnen nur die Metriken berücksichtigt, die in allen verglichenen Locations als `score_member=true` (oder nicht gesetzt, Default `true`) markiert sind — mit automatischer Re-Normalisierung der Gewichte der verbleibenden Metriken.

## Source

**Frontend — geändert:**
- `frontend/src/lib/types.ts` — `WeatherConfigMetric` um `score_member?: boolean` erweitert
- `frontend/src/lib/components/WeatherConfigDialog.svelte` — `scoreMap`-State + ScoreToggle-UI + neue `entityType`-Prop
- `frontend/src/routes/locations/+page.svelte` — `entityType="location"` Prop-Übergabe
- `frontend/src/routes/subscriptions/+page.svelte` — `entityType="subscription"` Prop-Übergabe

**Go-Backend — geändert:**
- `internal/compare/scoring.go` — `ScoreRow()` bekommt `enabledKeys map[metricKey]bool` Parameter; `nil` = alle aktiv; Re-Normalisierung der Gewichte
- `internal/compare/engine.go` — Lädt Location-DisplayConfig, baut Intersection der `score_member`-Configs aller verglichenen Locations, übergibt als `enabledKeys` an `ScoreRow()`
- `internal/compare/scoring_test.go` — 2 neue Tests für `score_member=false`-Szenarien

> **Schicht-Hinweis:** WeatherConfigDialog und types.ts liegen unter `frontend/src/` (SvelteKit). Die Compare-Logik liegt unter `internal/compare/` (Go-API, Port 8090). Der Python-Backend-Layer (`src/`) ist nicht betroffen — er rendert Briefings, nicht Compare-Scores.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherConfigDialog.svelte` (`frontend/src/lib/components/`) | Frontend | Basis-Komponente — wird um `entityType`-Prop und `scoreMap`-State erweitert |
| `WeatherConfigMetric` (`frontend/src/lib/types.ts:127`) | TypeScript-Interface | Persistenz-Struct für Metrik-Konfiguration — `score_member?: boolean` wird additiv ergänzt |
| `Segmented` (`frontend/src/lib/components/ui/segmented`) | UI-Komponente | Bestehende Segmented-Toggle-Komponente — wird für „Im Score" / „Nicht im Score" wiederverwendet |
| `ScoreRow()` (`internal/compare/scoring.go`) | Go-Funktion | Berechnet normierten Score [0, 100] für eine Location — erhält neuen `enabledKeys`-Parameter |
| `profileMetrics()` (`internal/compare/scoring.go`) | Go-Funktion intern | Liefert Profil-Gewichtungen — deren Summe wird nach Filterung re-normalisiert |
| `engine.go` (`internal/compare/engine.go`) | Go | Orchestriert Compare-Run — lädt Location-DisplayConfig und baut `enabledKeys`-Intersection |
| `store.LoadLocation()` (`internal/store/store.go`) | Go | Lädt Location-Struct incl. gespeicherte DisplayConfig mit `metrics`-Array |
| `model.Location` (`internal/model/location.go`) | Go-Struct | Enthält `DisplayConfig` mit `metrics`-Array (`score_member`-Feld reist additiv mit) |
| `/api/metrics` (Python-Proxy via Go) | API | Metrik-Katalog — liefert alle Metriken nach Kategorie; unverändert |

## Implementation Details

### §1 `frontend/src/lib/types.ts` — WeatherConfigMetric erweitern

Additiver Schritt: `score_member?: boolean` an `WeatherConfigMetric` anhängen.

```typescript
export interface WeatherConfigMetric {
    metric_id: string;
    enabled: boolean;
    use_friendly_format?: boolean;
    horizons?: Horizons;
    bucket?: 'primary' | 'secondary';
    order?: number;
    score_member?: boolean;  // NEU: undefined / true = im Score (Default), false = nur Anzeige
}
```

Kein Breaking Change — `undefined` wird serverseitig als `true` interpretiert. Bestehende gespeicherte Configs ohne `score_member` bleiben rückwärtskompatibel.

### §2 `frontend/src/lib/components/WeatherConfigDialog.svelte` — entityType + scoreMap

**Neue Prop `entityType`:**

```typescript
interface Props {
    open: boolean;
    entityName: string;
    currentConfig: Record<string, unknown> | undefined;
    entityType?: 'location' | 'subscription' | 'trip';  // NEU, Default: 'trip'
    onsave: (config: Record<string, unknown>) => void;
    onclose: () => void;
}

let { open, entityName, currentConfig, entityType = 'trip', onsave, onclose }: Props = $props();
```

`showScoreToggle` wird daraus abgeleitet:

```typescript
const showScoreToggle = $derived(entityType === 'location' || entityType === 'subscription');
```

**scoreMap-State:**

```typescript
let scoreMap: Record<string, boolean> = $state({});
```

`buildScoreMap()` initialisiert aus `currentConfig`:

```typescript
function buildScoreMap(cat: MetricCatalog, cfg: Record<string, unknown> | undefined) {
    const map: Record<string, boolean> = {};
    for (const metrics of Object.values(cat)) {
        for (const m of metrics) {
            map[m.id] = true;  // Default: im Score
        }
    }
    if (cfg && Array.isArray(cfg.metrics)) {
        for (const entry of cfg.metrics as Array<{ metric_id: string; score_member?: boolean }>) {
            map[entry.metric_id] = entry.score_member ?? true;
        }
    }
    return map;
}
```

Aufruf in `buildEnabledMap`/`buildFriendlyMap`-Parallel-Block (bei `loadCatalog()` und `$effect`).

**ScoreToggle im Template:**

Der Toggle erscheint nur bei aktivierten Metriken (`enabledMap[metric.id]`) und wenn `showScoreToggle`:

```svelte
{#if showScoreToggle && (enabledMap[metric.id] ?? false)}
    <Segmented
        options={[{ value: 'score', label: 'Im Score' }, { value: 'display', label: 'Nicht im Score' }]}
        selected={(scoreMap[metric.id] ?? true) ? 'score' : 'display'}
        onselect={(v) => { scoreMap = { ...scoreMap, [metric.id]: v === 'score' }; }}
    />
{/if}
```

**handleSave() — score_member mitserialieren:**

```typescript
function handleSave() {
    saving = true;
    const metricsArr = Object.entries(enabledMap).map(([metric_id, enabled]) => ({
        metric_id,
        enabled,
        use_friendly_format: friendlyMap[metric_id] ?? true,
        score_member: scoreMap[metric_id] ?? true,  // NEU
    }));
    const config: Record<string, unknown> = { metrics: metricsArr };
    onsave(config);
    saving = false;
}
```

### §3 `frontend/src/routes/locations/+page.svelte` + `subscriptions/+page.svelte`

In beiden Dateien: `entityType="location"` bzw. `entityType="subscription"` als neue Prop an `<WeatherConfigDialog>` übergeben. Einzeilige Änderung pro Datei.

### §4 `internal/compare/scoring.go` — ScoreRow mit enabledKeys

**Neue Signatur:**

```go
// ScoreRow returns a normalised score in [0, 100] for a single location.
// enabledKeys restricts which metrics are included; nil means all metrics active.
// Weights of the remaining metrics are re-normalised so they sum to 1.0.
func ScoreRow(loc model.SegmentWeatherSummary, profile ActivityProfile, allMetrics []model.SegmentWeatherSummary, enabledKeys map[metricKey]bool) int
```

**Re-Normalisierung der Gewichte:**

```go
specs := profileMetrics(profile)
// Filter auf enabledKeys
activeSpecs := specs
if enabledKeys != nil {
    activeSpecs = make([]metricSpec, 0, len(specs))
    for _, s := range specs {
        if enabledKeys[s.key] {
            activeSpecs = append(activeSpecs, s)
        }
    }
}
// Fallback: alle aktiv wenn Intersection leer
if len(activeSpecs) == 0 {
    activeSpecs = specs
}
// Re-Normalisierung
totalWeight := 0.0
for _, s := range activeSpecs {
    totalWeight += s.weight
}
// Im Score-Berechnen: spec.weight / totalWeight statt spec.weight
```

Wenn `enabledKeys == nil`, verhält sich `ScoreRow()` exakt wie bisher (alle Metriken, keine Re-Normalisierung nötig da Gewichte bereits 1.0 summieren).

### §5 `internal/compare/engine.go` — Intersection aller score_member-Configs

Nach dem parallelen Forecast-Fetch, vor dem `ScoreRow()`-Aufruf:

1. Für jede Location: Lade `display_config.metrics` aus dem gespeicherten Location-Store.
2. Baue `scoreMemberMap map[locationID]map[metricKey]bool` aus dem `score_member`-Feld der gespeicherten Configs.
3. Berechne Intersection: Eine Metrik ist im Score wenn ALLE Locations `score_member=true` (oder `score_member` nicht gesetzt, was `true` entspricht) für sie haben.
4. Wenn Intersection leer: `enabledKeys = nil` (Fallback auf alle aktiv).
5. Übergabe an `ScoreRow(..., enabledKeys)`.

**Frontend-ID zu Backend-metricKey Mapping** (statische Map in `engine.go`):

| Frontend-ID (metric_id) | Backend-metricKey |
|------------------------|-------------------|
| `precipitation` | `metricPrecipSum` |
| `wind` | `metricWindMax` |
| `gust` | `metricWindMax` (teilt Backend-Key mit `wind`) |
| `temperature` | `metricTempMax` |
| `snow_depth` | `metricSnowDepth` |
| `fresh_snow` | `metricSnowNew` |
| `sunshine` | `metricSunnyHours` |
| `cloud_total` | `metricCloudAvg` |
| `thunder` | `metricThunderProxy` |
| `visibility` | `metricVisibilityMin` |
| `uv_index` | `metricUvIndexMax` |
| alle anderen (z.B. `cape`, `rain_probability`, `humidity`, etc.) | kein Mapping nötig — nicht in `profileMetrics()`, daher kein Einfluss auf Score |

Hinweis: `gust` und `wind` teilen sich `metricWindMax` im Backend. Wenn der User `wind` auf `score_member=false` setzt, ist auch der Böen-Anteil ausgeschlossen. Das ist inhaltlich korrekt und vereinfacht das Mapping.

### §6 `internal/compare/scoring_test.go` — 2 neue Tests

**Test 1 — score_member=false schließt Metrik aus:**

```go
func TestScoreRow_WithEnabledKeys_ExcludesMetric(t *testing.T) {
    // Zwei Locations: A hat viel Regen, B hat wenig Regen.
    // enabledKeys schließt metricPrecipSum aus.
    // Erwartung: Score-Unterschied zwischen A und B kleiner als ohne Filter.
}
```

**Test 2 — leere Intersection fällt auf alle aktiv zurück:**

```go
func TestScoreRow_EmptyEnabledKeys_FallsBackToAll(t *testing.T) {
    // enabledKeys = leere Map (alle false).
    // Erwartung: ScoreRow verhält sich wie nil (alle Metriken aktiv).
}
```

## Expected Behavior

- **Input (Frontend):** User öffnet WeatherConfigDialog für eine Location (entityType="location"), aktiviert eine Metrik und setzt den ScoreToggle auf „Nicht im Score". User klickt „Speichern".
- **Output (Frontend):** Der gespeicherte `display_config.metrics`-Eintrag enthält `score_member: false` für diese Metrik. Alle anderen Metriken haben `score_member: true` (oder kein Feld, was denselben Effekt hat).
- **Input (Backend):** `POST /api/compare/run` mit zwei Location-IDs, bei denen eine Metrik in beiden Locations `score_member=false` hat.
- **Output (Backend):** `ScoreRow()` berechnet den Score ohne diese Metrik; die Gewichte der verbleibenden Metriken werden re-normalisiert (Summe = 1.0). Der Score liegt weiterhin in [0, 100].
- **Side effects:**
  - Der bestehende In-Memory-Cache cached Summary-Daten, nicht den Score. `ScoreRow()` wird nach dem Cache-Lookup aufgerufen — kein Cache-Invalidierungsproblem.
  - Bestehende Locations ohne `score_member`-Feld im gespeicherten JSON verhalten sich identisch zu bisher (Intersection enthält alle Score-Metriken des Profils).
  - Trip-Wetter-Metriken-Editor (WeatherMetricsTab) ist nicht betroffen — kein `entityType`-Prop, kein ScoreToggle sichtbar.
  - Keine Go-Struct-Änderungen, kein Migration-Script, kein API-Breaking-Change.

## Acceptance Criteria

**AC-1:** Given eine aktivierte Metrik im Location-Editor (`entityType="location"`), When der User „Nicht im Score" wählt und „Speichern" klickt, Then enthält das gespeicherte `display_config.metrics`-Array für diese Metrik `score_member: false`.
  - Test: (populated after /tdd-red)

**AC-2:** Given ein Compare-Run mit zwei Locations, When beide Locations eine Metrik auf `score_member=false` haben, Then geht diese Metrik nicht in `ScoreRow()` ein und die Gewichte der verbleibenden Metriken werden re-normalisiert (addieren sich wieder zu 1.0).
  - Test: (populated after /tdd-red)

**AC-3:** Given ein Compare-Run mit zwei Locations, When Location A hat Metrik X auf `score_member=false` und Location B hat kein `score_member`-Feld (Default=true), Then ist Metrik X per Intersection NICHT im Score (Location A schließt sie für den gesamten Compare-Run aus).
  - Test: (populated after /tdd-red)

**AC-4:** Given eine Location ohne gespeichertes `score_member`-Feld in irgendeiner Metrik, When ein Compare-Run gestartet wird, Then verhält sich die Engine wie bisher — alle Profil-Metriken im Score, Score identisch zu vor diesem Feature.
  - Test: (populated after /tdd-red)

**AC-5:** Given der Trip-Wetter-Metriken-Editor (WeatherMetricsTab.svelte, kein entityType-Prop), When er geöffnet wird, Then ist kein ScoreToggle sichtbar; `showScoreToggle` ist `false` wenn `entityType === 'trip'` (Default).
  - Test: (populated after /tdd-red)

**AC-6:** Given alle Metriken einer Location haben `score_member=false`, When der Compare-Run gestartet wird, Then fällt die Engine auf alle aktiv zurück (leere Intersection → `enabledKeys=nil` → normales Profil-Scoring); kein Fehler, kein 0-Score.
  - Test: (populated after /tdd-red)

**AC-7:** Given bestehende Locations ohne `score_member`-Feld im gespeicherten JSON, When sie in WeatherConfigDialog geladen werden, Then zeigt der ScoreToggle „Im Score" (Default `true`, kein Datenverlust, rückwärtskompatibel).
  - Test: (populated after /tdd-red)

## Known Limitations

- **wind + gust teilen Backend-metricKey:** Beide Frontend-IDs (`wind` und `gust`) werden auf `metricWindMax` gemappt. Wenn `wind` auf `score_member=false` gesetzt wird, hat das denselben Effekt wie wenn `gust` ausgeschlossen wird — sie können nicht unabhängig voneinander aus dem Score ausgeschlossen werden. Dokumentiertes Verhalten, da das Backend nur einen Wind-Max-Wert aggregiert.
- **ScoreToggle nur bei aktivierten Metriken:** Toggle ist nur sichtbar wenn `enabledMap[metric.id] === true`. Wenn eine Metrik deaktiviert wird, verschwindet der Toggle — der gespeicherte `score_member`-Wert bleibt im JSON aber erhalten und wird beim erneuten Aktivieren wieder angezeigt.
- **Kein Subscriptions-Backend-Score:** `score_member` in Subscriptions-DisplayConfig wird vom Frontend gespeichert, aber der Compare-Engine liefert `location_ids` (nicht Subscription-IDs) — Subscription-Configs fließen derzeit nicht in die Intersection ein. Das Feature ist trotzdem sinnvoll, da Subscriptions und Locations dieselbe Display-Config-Struktur teilen und das Feature für Locations voll wirksam ist.
- **LoC-Schätzung ~146 LoC, 7 Dateien:** Keine LoC-Override-Anpassung erforderlich wenn Workflow-Limit bei 250 steht.

## Changelog

- 2026-05-26: Initial spec — Issue #362. ScoreToggle im WeatherConfigDialog (entityType-Prop, scoreMap, Segmented-UI), score_member additiv in WeatherConfigMetric, ScoreRow() mit enabledKeys + Re-Normalisierung, Intersection-Logik in engine.go. ~146 LoC, 7 Dateien, rückwärtskompatibel, kein Migration-Script.
