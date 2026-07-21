---
entity_id: issue_674_aktivitaetstyp_fahrrad
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
parent_issue: 674
issues: [674]
tags: [frontend, go, naismith, activity-type, trip-wizard, cycling, arrival-times]
---

# Issue #674 — Fahrradtour als Aktivitätstyp (15 / 20 / 25 km/h)

## Approval

- [ ] Approved

## Purpose

Fahrradtouren als eigenen Aktivitätstyp mit drei Geschwindigkeitsstufen (15, 20, 25 km/h) anlegen, damit Briefings für Radreisen korrekte Wetterabruf-Zeitfenster liefern. Ohne diese Erweiterung berechnen alle Trips die Ankunftszeiten auf Basis der Wandergeschwindigkeit (4 km/h), was bei Radtouren Zeitfenster-Fehler von mehreren Stunden erzeugt und damit das Wetterbriefing für den falschen Tagesabschnitt abruft.

## Source

**Schicht: Frontend (SvelteKit) + Go-API (gemischt)**

- `frontend/src/lib/types.ts` — `ActivityType` Union: 3 neue Werte ergänzen
- `frontend/src/lib/components/trip-wizard/wizardHelpers.ts` — `mapActivityToProfile()`: neue Fahrrad-Fälle → `'allgemein'`; `ACTIVITY_TO_OPTION`-Record ergänzen
- `frontend/src/lib/components/trip-wizard/steps/Step3Weather.svelte` — `ACTIVITY_OPTIONS`, `OPTION_TO_ACTIVITY`, `ACTIVITY_TO_OPTION`: Fahrrad-Einträge
- `frontend/src/lib/utils/naismith.ts` — `computeArrivalTimes()`: neuer optionaler Parameter `speedFlatKmh?`; neue exportierte Hilfsfunktion `activityToSpeed(activity?: ActivityType)`
- `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` — neue Prop `activityType?: ActivityType`; wird an `computeArrivalTimes` weitergegeben
- `internal/model/naismith.go` — `naismithHours()` und `ComputeStageArrivals()`: Speed-Parameter statt hardcodierter Konstante; neue Hilfsfunktion `ActivitySpeed(activity string) ActivitySpeeds`
- `internal/handler/trip.go` — beide Aufruf-Stellen von `ComputeStageArrivals` (Zeilen ~225, ~375): Speed aus `trip.Activity` via `ActivitySpeed()` ableiten

**Identifier:** `ActivityType` (TS), `mapActivityToProfile` (TS), `activityToSpeed` (TS), `computeArrivalTimes` (TS), `ActivitySpeed` (Go), `ActivitySpeeds` (Go), `ComputeStageArrivals` (Go), `naismithHours` (Go)

## Estimated Scope

- **LoC:** ~90
- **Files:** 7
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/types.ts` `ActivityType` | file (edit) | String-Union erweitern — safe, kein exhaustiveness-check auf Aktivitäts-Union |
| `frontend/src/lib/utils/naismith.ts` `computeArrivalTimes` | file (edit) | Optionalen Speed-Parameter aufnehmen; `activityToSpeed` exportieren |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | file (edit) | `activityType`-Prop aufnehmen und an `computeArrivalTimes` weiterreichen |
| `internal/model/naismith.go` `ComputeStageArrivals` | file (edit) | Speed-Parameter statt Konstante; `ActivitySpeed` Hilfsfunktion |
| `internal/handler/trip.go` `UpdateTripHandler` | file (edit) | Beide Aufruf-Stellen auf `ActivitySpeed(trip.Activity)` umstellen |
| `src/app/models.py` `EtappenConfig` | reference | Bestehende Wanderkonstanten (Single Source: `speed_flat_kmh=4.0`); Python-Scope ist OUT OF SCOPE für diese Spec |

## Implementation Details

### §1 Neue ActivityType-Werte (types.ts)

```typescript
// Vorher
export type ActivityType = 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb';

// Nachher
export type ActivityType =
  | 'trekking' | 'skitour' | 'hochtour' | 'klettersteig' | 'mtb'
  | 'fahrrad_15' | 'fahrrad_20' | 'fahrrad_25';
```

### §2 Aggregations-Profil-Mapping (wizardHelpers.ts)

Alle drei Fahrrad-Varianten mappen auf `'allgemein'` (identisch zu `'mtb'`):

```typescript
case 'fahrrad_15':
case 'fahrrad_20':
case 'fahrrad_25':
    return 'allgemein';
```

`ACTIVITY_TO_OPTION` erhält drei neue Einträge:
```typescript
fahrrad_15: 'fahrrad_15',
fahrrad_20: 'fahrrad_20',
fahrrad_25: 'fahrrad_25',
```

### §3 Aktivitäts-Dropdown (Step3Weather.svelte)

`ACTIVITY_OPTIONS` ergänzen:
```typescript
{ value: 'fahrrad_15', label: 'Fahrrad (15 km/h)' },
{ value: 'fahrrad_20', label: 'Fahrrad (20 km/h)' },
{ value: 'fahrrad_25', label: 'Fahrrad (25 km/h)' },
```

`OPTION_TO_ACTIVITY` ergänzen:
```typescript
fahrrad_15: 'fahrrad_15',
fahrrad_20: 'fahrrad_20',
fahrrad_25: 'fahrrad_25',
```

### §4 activityToSpeed + computeArrivalTimes (naismith.ts)

Neue exportierte Hilfsfunktion:
```typescript
// Wanderer-Default = 4.0 km/h, gespiegelt aus EtappenConfig.
// Fahrrad-Stufen nur in dieser Spec definiert — keine Python-Entsprechung (OUT OF SCOPE).
export function activityToSpeed(activity?: ActivityType): number {
    switch (activity) {
        case 'fahrrad_15': return 15.0;
        case 'fahrrad_20': return 20.0;
        case 'fahrrad_25': return 25.0;
        default:            return SPEED_FLAT_KMH; // 4.0 — Wandern, alle anderen
    }
}
```

`computeArrivalTimes` bekommt optionalen dritten Parameter:
```typescript
export function computeArrivalTimes(
    stage: Stage,
    startTime?: string,
    speedFlatKmh: number = SPEED_FLAT_KMH
): string[]
```

`naismithHours` erhält ebenfalls einen Speed-Parameter:
```typescript
function naismithHours(
    distKm: number,
    ascentM: number,
    descentM: number,
    speedFlat = SPEED_FLAT_KMH
): number {
    return distKm / speedFlat + ascentM / SPEED_ASCENT_MH + descentM / SPEED_DESCENT_MH;
}
```

### §5 EditStagesPanelNew.svelte — Prop weiterreichen

```typescript
// Neue Prop
let { activityType }: { activityType?: ActivityType } = $props();

// Bestehende Zeile (~80), Speed ableiten:
activeStage
  ? computeArrivalTimes(activeStage, activeStage.start_time, activityToSpeed(activityType))
  : []
```

Aufrufer (z.B. `/trips/new`, `/trips/[id]/edit`) übergeben `activityType={trip.activity}`. Fehlt der Wert, fällt `activityToSpeed(undefined)` auf 4.0 zurück — keine Breaking Change für bestehende Call-Sites.

### §6 ActivitySpeeds-Struct + ActivitySpeed + ComputeStageArrivals (naismith.go)

Neue öffentliche Struct und Hilfsfunktion (exportiert, da von `internal/handler/` aufgerufen):
```go
// ActivitySpeeds bündelt die drei Tempoparameter einer Aktivität.
type ActivitySpeeds struct {
    FlatKmh   float64
    AscentMh  float64
    DescentMh float64
}

// ActivitySpeed liefert die Tempoparameter für eine Trip.Activity.
// Unbekannte oder leere Werte → Wanderer-Default (gespiegelt aus EtappenConfig).
func ActivitySpeed(activity string) ActivitySpeeds {
    switch activity {
    case "fahrrad_15":
        return ActivitySpeeds{FlatKmh: 15.0, AscentMh: 600.0, DescentMh: 1000.0}
    case "fahrrad_20":
        return ActivitySpeeds{FlatKmh: 20.0, AscentMh: 600.0, DescentMh: 1000.0}
    case "fahrrad_25":
        return ActivitySpeeds{FlatKmh: 25.0, AscentMh: 600.0, DescentMh: 1000.0}
    default:
        return ActivitySpeeds{FlatKmh: speedFlatKmh, AscentMh: speedAscentMh, DescentMh: speedDescentMh}
    }
}
```

`naismithHours` und `ComputeStageArrivals` erhalten einen `ActivitySpeeds`-Parameter:
```go
func naismithHours(distKm, ascentM, descentM float64, sp ActivitySpeeds) float64 {
    return distKm/sp.FlatKmh + ascentM/sp.AscentMh + descentM/sp.DescentMh
}

func ComputeStageArrivals(stage *Stage, sp ActivitySpeeds) {
    // identisch zu heute, aber speedFlatKmh/speedAscentMh/speedDescentMh
    // durch sp.FlatKmh/sp.AscentMh/sp.DescentMh ersetzt
}
```

Die drei Paketkonstanten (`speedFlatKmh`, `speedAscentMh`, `speedDescentMh`) bleiben erhalten als Default-Werte in `ActivitySpeed("default")` und für etwaige interne Nutzung.

### §7 Aufrufer in trip.go anpassen

Beide Stellen (~225, ~375):
```go
// Vorher:
model.ComputeStageArrivals(&existing.Stages[i])

// Nachher:
model.ComputeStageArrivals(&existing.Stages[i], model.ActivitySpeed(existing.Activity))
```

`Trip.Activity` ist ein bestehendes `string`-Feld — kein Modell-Change nötig.

### §8 Fahrrad-Höhenmeter-Begründung

Fahrradfahrer überwinden Steigungen schneller als Fußgänger pro Höhenmeter:
- `AscentMh = 600` Hm/h (doppelt so schnell wie Wanderer mit 300 Hm/h)
- `DescentMh = 1000` Hm/h (doppelt so schnell wie Wanderer mit 500 Hm/h)

Begründung: Auf dem Rad wird Antriebskraft effizienter in Höhenmeter umgesetzt als zu Fuß; Abfahrten werden mit Schwung durchfahren. Werte sind konservative Schätzungen für Tourenradfahren (kein Rennrad).

## Expected Behavior

- **Input:** Wizard-Step 3: Nutzer wählt "Fahrrad (20 km/h)" als Aktivitätstyp. Trip wird gespeichert (PUT `/api/trips/:id` mit `activity: "fahrrad_20"`).
- **Output:** Jeder Wegpunkt erhält `arrival_calculated` basierend auf 20 km/h Flachgeschwindigkeit und 600/1000 Hm/h. Frontend-Editor zeigt live-berechnete Ankunftszeiten auf Basis 20 km/h.
- **Side effects:** `trip.json` trägt `"activity": "fahrrad_20"` und aktualisierte `arrival_calculated`-Werte. Bestehende Trips ohne Fahrrad-Activity sind unverändert (Default-Fallback 4.0 km/h / 300/500 Hm/h).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit `activity = "fahrrad_20"` und einer Stage mit 2 flachen Wegpunkten 20 km auseinander (gleiche Höhe, `start_time = "08:00"`) / When der Trip via PUT gespeichert wird / Then trägt Wegpunkt 2 `arrival_calculated == "09:00"` (20 km ÷ 20 km/h = 1 h)
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_Fahrrad20_Flat`

- **AC-2:** Given ein Trip mit leerem `activity`-Feld und denselben 2 Wegpunkten 20 km auseinander (`start_time = "08:00"`) / When gespeichert / Then trägt Wegpunkt 2 `arrival_calculated == "13:00"` (20 km ÷ 4 km/h = 5 h) — beweist, dass der Wanderer-Default unverändert greift
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_WanderDefaultUnchanged`

- **AC-3:** Given ein Trip mit `activity = "fahrrad_15"` und einer Stage mit +600 m Aufstieg bei ~0 km Horizontaldistanz (`start_time = "08:00"`) / When gespeichert / Then trägt der letzte Wegpunkt `arrival_calculated == "09:00"` (600 m ÷ 600 m/h = 1 h) — beweist die Fahrrad-Aufstiegs-Rate
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_Fahrrad15_Ascent`

- **AC-4:** Given der Trip-Wizard Step 3 auf Staging als eingeloggter Nutzer / When das Aktivitätstyp-Dropdown geöffnet wird / Then sind die drei Einträge "Fahrrad (15 km/h)", "Fahrrad (20 km/h)" und "Fahrrad (25 km/h)" sichtbar und auswählbar
  - Test: `tests/tdd/test_issue_674_fahrrad.py::test_activity_dropdown_shows_fahrrad_options` (Playwright gegen Staging)

- **AC-5:** Given ein neuer Trip wird im Wizard mit Aktivitätstyp "Fahrrad (25 km/h)" angelegt, gespeichert und der Trip-Editor öffnet die Stage-Ansicht / When die Ankunftszeiten neben den Wegpunkten abgelesen werden / Then weichen sie von den Ankunftszeiten eines identischen Trips mit Wandertempo messbar ab (früher bei gleichem Startpunkt)
  - Test: `tests/tdd/test_issue_674_fahrrad.py::test_editor_arrival_times_reflect_fahrrad_speed` (Playwright gegen Staging, DB-Roundtrip mit zwei Trips)

- **AC-6:** Given `ActivitySpeed("fahrrad_25")` in naismith.go / When aufgerufen / Then liefert die Struct `FlatKmh=25.0, AscentMh=600.0, DescentMh=1000.0`; `ActivitySpeed("")` liefert `FlatKmh=4.0, AscentMh=300.0, DescentMh=500.0`
  - Test: `internal/model/naismith_test.go::TestActivitySpeed_AllVariants`

- **AC-7:** Given `activityToSpeed('fahrrad_25')` in naismith.ts / When aufgerufen / Then wird 25.0 zurückgegeben; `activityToSpeed(undefined)` gibt 4.0 zurück (Wanderer-Default bleibt erhalten)
  - Test: `tests/tdd/test_issue_674_fahrrad.py::test_ts_activity_to_speed_mapping` (Node-Subprozess oder vitest)

- **AC-8:** Given ein bestehender Trip ohne `activity`-Feld in der JSON-Datei / When Go `LoadTrip` und `ComputeStageArrivals` ihn verarbeiten / Then sind alle `arrival_calculated`-Werte bitidentisch zu den Werten vor diesem Umbau (kein Wanderer-Zeitfenster ändert sich durch die Refaktorierung)
  - Test: `internal/model/naismith_test.go::TestComputeStageArrivals_BackwardsCompat`

## Known Limitations

- **Python EtappenConfig OUT OF SCOPE:** Die Fahrrad-Geschwindigkeiten (15/20/25 km/h, 600/1000 Hm/h) werden nur in Go und TypeScript definiert. Python `EtappenConfig` wird nicht erweitert, weil kein Activity-Kontext zum GPX-Upload-Zeitpunkt verfügbar ist. Ohne persistierte `arrival_calculated`-Werte fällt der Python-Scheduler auf den 4 km/h-Fallback zurück — separates Issue nötig.
- **Konstanten-Drift:** Fahrrad-Geschwindigkeiten sind in Go (`naismith.go`) und TypeScript (`naismith.ts`) doppelt definiert. Für 6 Floats akzeptabel; Querverweis-Kommentare pflicht. Echte SSOT = Folge-Issue.
- **MTB bleibt unverändert:** `mtb` ist als versteckter ActivityType vorhanden (PO-Entscheidung). MTB-Speed bleibt bei 4.0 km/h Wandertempo — explizite MTB-Speeds sind separates Issue.
- **Höhenmeter-Schätzung via Haversine** (lat/lon-Distanz, keine echte GPX-Spur) → leichte Unterschätzung. Konsistent mit bestehender Pipeline.

## Changelog

- 2026-06-09: Initiale Spec. 3 neue ActivityType-Werte (fahrrad_15/20/25), `ActivitySpeeds`-Struct in Go, Speed-Parameter in `ComputeStageArrivals` und `computeArrivalTimes`, Fahrrad-Höhenmeter-Raten 600/1000 Hm/h, 8 Acceptance Criteria. Issue #674.
