---
entity_id: issue_367_compare_sunny_hours
type: module
created: 2026-05-26
updated: 2026-05-26
status: active
version: "1.0"
tags: [compare-engine, go, sunny-hours, dni, wcag, unit-consistency, frontend, issue-367]
---

<!-- Issue #367 — Ortsvergleich: Go-Engine zeigt DNI-W/m², Python-Pfad Sonnenstunden — vereinheitlichen -->

# Issue #367 — Go-Compare-Engine: DNI-W/m² auf WMO-konforme Sonnenstunden umstellen

## Approval

- [x] Approved

## Zweck

Die Go-Compare-Engine (`POST /api/compare/run`) liefert Sonnenschein bisher als `dni_avg_wm2` in W/m², während alle anderen Ausgaben (Python-Compare-E-Mail, Trip-Summary) den Wert als `sunny_hours` in Stunden ausgeben. Das Frontend-Label lautet bereits "Sonnenstunden", die angezeigte Einheit ist jedoch fälschlicherweise W/m². Dieses Modul vereinheitlicht die Go-Engine auf WMO-konforme Sonnenstunden durch die gleiche DNI-Interpolationsformel wie der Python-Pfad, entfernt `DniAvgWm2` vollständig aus Datenmodell und API-Response und korrigiert den Frontend-Key und die Einheitsanzeige.

## Quelle / Source

**Geänderte Dateien:**
- `internal/model/segment.go:24` — Feld `DniAvgWm2 *float64 \`json:"dni_avg_wm2,omitempty"\`` → `SunnyHoursH *float64 \`json:"sunny_hours_h,omitempty"\``
- `internal/compare/engine.go:238-241` — DNI-Durchschnittsberechnung ersetzen durch WMO-Interpolations-Summierung (sunnyFractionSum)
- `internal/compare/scoring.go:17,48,233` — Konstante `metricDniAvg` → `metricSunnyHours`, Extraktion `.DniAvgWm2` → `.SunnyHoursH`
- `internal/compare/scoring_test.go` — Neuer Unit-Test: Location mit mehr Sonnenstunden gewinnt WINTERSPORT-Scoring
- `internal/handler/compare_run_test.go` — Neuer Handler-Test: `sunny_hours_h` erscheint in Response, `dni_avg_wm2` ist abwesend
- `frontend/src/lib/types.ts:276` — Interface-Feld `CompareMetrics.dni_avg_wm2: number` → `sunny_hours_h: number`
- `frontend/src/lib/components/compare/CompareMatrix.svelte:31` — Key `dni_avg_wm2` → `sunny_hours_h`, Label-Einheit `W/m²` → `h`

**NICHT ändern:**
- `src/services/weather_metrics.py` (Python-Referenzimplementierung, bleibt byte-gleich)
- `src/services/comparison_engine.py` (Python-Compare-Pfad, nicht betroffen)

> **Schicht-Hinweis:** Änderungen liegen im Go-API-Layer (`internal/`) und im Frontend-Layer (`frontend/src/lib/`). Der Python-Backend-Layer (`src/`) wird nicht angefasst.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/model/segment.go` | Go-Struct | Datenmodell für Compare-Segment; Feld-Umbenennung `DniAvgWm2` → `SunnyHoursH` |
| `internal/compare/engine.go` | Go-Service | Aggregiert Wetterpunkte pro Datum; ersetzt DNI-Durchschnitt durch Fraktions-Summierung |
| `internal/compare/scoring.go` | Go-Service | Bewertet Locations nach Metriken; Konstante und Extraktion auf neues Feld umstellen |
| `internal/compare/scoring_test.go` | Go-Test | Unit-Tests für Scoring-Logik; erhält neuen WINTERSPORT-Sonnenstunden-Test |
| `internal/handler/compare_run_test.go` | Go-Test | Handler-Integrations-Tests; erhält Assertion auf `sunny_hours_h` in Response-Body |
| `frontend/src/lib/types.ts` | TypeScript-Interface | `CompareMetrics`-Typ; Feld `dni_avg_wm2` → `sunny_hours_h` |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | Svelte-Komponente | Zeigt Vergleichs-Matrix; Key und Einheitstext korrigieren |
| `src/services/weather_metrics.py` | Python-Modul (Referenz, read-only) | Definiert `dni_to_sunny_fraction()` und `calculate_sunny_hours()` — Formel-Vorlage für Go-Port |

## Implementation Details

### 1. `internal/model/segment.go` — Feld-Umbenennung

Das Feld `DniAvgWm2` wird vollständig entfernt und durch `SunnyHoursH` ersetzt. Kein deprecated-Alias, da es sich um einen internen Endpoint ohne externe Clients handelt:

```go
// Vorher:
DniAvgWm2 *float64 `json:"dni_avg_wm2,omitempty"`

// Nachher:
SunnyHoursH *float64 `json:"sunny_hours_h,omitempty"`
```

### 2. `internal/compare/engine.go` — WMO-Interpolation in `aggregateByDate()`

Ersetzt die bisherige DNI-Durchschnittsberechnung durch eine Fraktions-Summierung, die identisch zur Python-Referenzimplementierung (`dni_to_sunny_fraction()`) ist. Die Konstanten `dniMin=60.0` und `dniMax=180.0` werden als lokale Konstanten definiert:

```go
const dniMin, dniMax = 60.0, 180.0
var sunnyFractionSum float64
var sunnyAny bool

// Pro Datenpunkt in der Schleife:
if pt.DniWm2 != nil {
    v := *pt.DniWm2
    switch {
    case v >= dniMax:
        sunnyFractionSum += 1.0
    case v > dniMin:
        sunnyFractionSum += (v - dniMin) / (dniMax - dniMin)
    }
    sunnyAny = true
}

// Ergebnis am Ende von aggregateByDate():
if sunnyAny {
    rounded := math.Round(sunnyFractionSum*10) / 10 // 1 Dezimalstelle
    seg.SunnyHoursH = &rounded
}
```

### 3. `internal/compare/scoring.go` — Konstante und Extraktion

Konstante umbenennen und Extraktion auf neues Feld zeigen:

```go
// Vorher:
const metricDniAvg = "dni_avg"
// ...
if seg.DniAvgWm2 != nil { val = *seg.DniAvgWm2 }

// Nachher:
const metricSunnyHours = "sunny_hours"
// ...
if seg.SunnyHoursH != nil { val = *seg.SunnyHoursH }
```

Das Scoring-Prinzip bleibt populationsrelativ: die Location mit den meisten Sonnenstunden gewinnt. Keine absolute Stundenschwelle einführen.

### 4. `internal/compare/scoring_test.go` — Neuer WINTERSPORT-Test

```go
func TestSunnyHoursScoringWintersport(t *testing.T) {
    // Location A: 6.0 h, Location B: 3.0 h
    // WINTERSPORT-Profil — höhere Sonnenstunden soll gewinnen
    locA := buildSegmentWithSunnyHours(6.0)
    locB := buildSegmentWithSunnyHours(3.0)
    scoreA := scoreSegment(locA, ProfileWintersport)
    scoreB := scoreSegment(locB, ProfileWintersport)
    assert.Greater(t, scoreA, scoreB, "mehr Sonnenstunden muss höheren Score ergeben")
}
```

### 5. `internal/handler/compare_run_test.go` — Response-Assertion

```go
// Prüft:
// 1. sunny_hours_h ist in der Response vorhanden und > 0
// 2. dni_avg_wm2 ist NICHT in der Response
assert.Greater(t, metrics.SunnyHoursH, 0.0)
assert.NotContains(t, rawJSON, "dni_avg_wm2")
```

### 6. `frontend/src/lib/types.ts` — Interface-Feld

```typescript
// Vorher (Zeile 276):
dni_avg_wm2: number;

// Nachher:
sunny_hours_h: number;
```

### 7. `frontend/src/lib/components/compare/CompareMatrix.svelte` — Key und Einheit

```svelte
<!-- Vorher: -->
{ key: 'dni_avg_wm2', label: 'Sonnenstunden', unit: 'W/m²' }

<!-- Nachher: -->
{ key: 'sunny_hours_h', label: 'Sonnenstunden', unit: 'h' }
```

### 8. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `internal/model/segment.go` | ~2 (Tausch) | ja |
| `internal/compare/engine.go` | ~12 (Ersetzen) | ja |
| `internal/compare/scoring.go` | ~4 (Konstante + 3 Stellen) | ja |
| `internal/compare/scoring_test.go` | ~15 (neuer Test) | ja |
| `internal/handler/compare_run_test.go` | ~12 (neuer Test) | ja |
| `frontend/src/lib/types.ts` | ~1 (Tausch) | ja |
| `frontend/src/lib/components/compare/CompareMatrix.svelte` | ~2 (Tausch) | ja |
| **Gesamt (zählend)** | **~48** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** `POST /api/compare/run` mit gültigen Location-IDs; OpenMeteo liefert stündliche `direct_normal_irradiance`-Werte (W/m²)
- **Output:** Response-JSON enthält pro Location `"sunny_hours_h": <float>` (1 Dezimalstelle, 0.0–24.0); `dni_avg_wm2` taucht nicht mehr auf
- **Side effects:** Frontend-Vergleichsmatrix zeigt Spalte "Sonnenstunden" mit Einheit `h` statt `W/m²`. Python-Compare-Pfad und Trip-Summary sind unverändert — beide nutzen `sunny_hours` (ohne `_h`-Suffix), was einen anderen JSON-Key darstellt und keine Konflikte erzeugt.

## Acceptance Criteria

- **AC-1:** Given ein laufender Go-Server mit Test-Fixtures für Innsbruck / When `POST /api/compare/run` mit einer gültigen Location-ID aufgerufen wird / Then enthält die Response `"sunny_hours_h"` mit einem Wert größer als 0 (Fixture enthält tagsüber DNI-Werte > 60 W/m²)
  - Test: `internal/handler/compare_run_test.go` — Handler-Test mit Fixture-Provider

- **AC-2:** Given eine vollständige Tages-Fixture mit ausschließlich DNI-Werten ≤ 24 Stunden DNI >= 180 W/m² / When die Aggregation läuft / Then ist `sunny_hours_h` nicht größer als 24.0 (physikalische Obergrenze: max. 24 Stunden pro Tag)
  - Test: `internal/compare/scoring_test.go` — Boundary-Test mit Maximalwert-Fixture

- **AC-3:** Given zwei Locations, Location A mit `sunny_hours_h=6.0` und Location B mit `sunny_hours_h=3.0` / When das WINTERSPORT-Scoring berechnet wird / Then erhält Location A einen höheren Score als Location B (mehr Sonne gewinnt)
  - Test: `internal/compare/scoring_test.go` — `TestSunnyHoursScoringWintersport`

- **AC-4:** Given eine gerenderte Compare-Matrix im Frontend / When die Zeile "Sonnenstunden" angezeigt wird / Then steht hinter dem Wert die Einheit `h` und nicht `W/m²`
  - Test: Source-Inspection via `grep` auf `CompareMatrix.svelte` — `unit: 'h'` vorhanden, `W/m²` absent

- **AC-5:** Given die Go-API-Response von `POST /api/compare/run` / When der rohe JSON-Body inspiziert wird / Then enthält er keinen Key `dni_avg_wm2` — weder auf oberster Ebene noch in verschachtelten Objekten
  - Test: `internal/handler/compare_run_test.go` — `assert.NotContains(t, rawJSON, "dni_avg_wm2")`

- **AC-6:** Given der Python-Quellcode in `src/services/comparison_engine.py` und `src/services/weather_metrics.py` / When nach dem Merge beide Dateien per `git diff origin/main` verglichen werden / Then ist die Ausgabe leer — beide Dateien sind byte-gleich (kein Python-Code verändert)
  - Test: CI-Diff-Check oder manuelles `git diff HEAD~1 src/services/`

## Known Limitations

- **Cloud-Fallback nicht portiert:** Der Python-Pfad hat einen Geosphere-Fallback für Bewölkung, der in Go nicht existiert. Go nutzt ausschließlich OpenMeteo — dies ist bewusste Scope-Begrenzung und bereits im Analyse-Ergebnis dokumentiert.
- **Kein Floating-Point-Präzisionstest:** Die 1-Dezimalstellen-Rundung (`math.Round(x*10)/10`) wird nicht separat unit-getestet; sie ist Teil der `aggregateByDate()`-Ausgabe und durch den Handler-Test implizit abgedeckt.
- **Kein Browser-Visual-Test:** Die Einheitskorrektur im Frontend (`W/m²` → `h`) wird per Source-Inspection geprüft, nicht durch einen Screenshot-Vergleich.

## Out of Scope

- Geosphere-Cloud-Fallback in der Go-Engine einführen
- Python-`comparison_engine.py` oder `weather_metrics.py` ändern
- Score-Schwellen für Sonnenstunden neu kalibrieren (Folgearbeit, dokumentiert in Memory #347)
- Weitere Compare-Metriken normalisieren

## Changelog

- 2026-05-26: Initial spec erstellt. Beschreibt Vereinheitlichung Go-Compare-Engine von `dni_avg_wm2` (W/m²) auf `sunny_hours_h` (h) durch WMO-konforme DNI-Interpolation nach Python-Vorbild; 7 Dateien, ~48 LoC, 6 Acceptance Criteria.
