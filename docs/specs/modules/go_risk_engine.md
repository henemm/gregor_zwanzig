---
entity_id: go_risk_engine
type: module
created: 2026-04-13
updated: 2026-04-13
status: draft
version: "1.0"
tags: [migration, go, risk-engine]
---

# M3: Risk Engine nach Go portieren

## Approval

- [ ] Approved

## Purpose

Die Python Risk Engine (221 LOC) als Go-Package portieren. Bewertet Wetter-Risiken fuer Wandersegmente anhand von 9 Regeln mit Schwellenwerten. Rein funktional, kein I/O, kein State.

## Scope

### In Scope

- RiskType, RiskLevel Enums (Go string constants)
- Risk und RiskAssessment Structs
- SegmentWeatherSummary Struct (aggregierte Wetterdaten)
- Risk Engine mit 9 Regeln (Thunder, CAPE, Wind, Gust, Precipitation, Rain Probability, Wind Chill, Visibility, Wind Exposition)
- Schwellenwerte als Go-Konstanten
- Deduplizierung per RiskType (hoechstes Level gewinnt)
- Sortierung HIGH -> MODERATE -> LOW
- Wind Exposition mit ExposedSection Overlap-Check
- 14+ Go Tests (1:1 Port der Python Integration Tests)

### Out of Scope

- Segment-Aggregation (MIN/MAX/SUM aus Forecast-Daten) — eigenes Feature
- MetricCatalog Port — nicht noetig, Schwellenwerte als Konstanten
- API Handler fuer Risk Endpoints — spaeterer Meilenstein
- Formatter-Integration — M4

## Architecture

```
internal/model/
  risk.go          <- RiskType, RiskLevel, Risk, RiskAssessment
  segment.go       <- SegmentWeatherSummary

internal/risk/
  thresholds.go    <- Konstanten (wind=50/70, gust=50/70, etc.)
  engine.go        <- Assess(), deduplicate(), levelOrder()
  engine_test.go   <- 14 Tests (Rules 1-8)
  exposition.go    <- ExposedSection, AssessWithExposition()
  exposition_test.go <- 4 Tests (Rule 9)
```

### Datenfluss

```
SegmentWeatherSummary (aggregierte Werte)
  |
  v
risk.Assess(summary) -> RiskAssessment
  |
  +-- Rule 1: ThunderLevelMax -> THUNDERSTORM
  +-- Rule 2: CapeMaxJkg > 1000/2000 -> THUNDERSTORM
  +-- Rule 3: WindMaxKmh > 50/70 -> WIND
  +-- Rule 4: GustMaxKmh > 50/70 -> WIND
  +-- Rule 5: PrecipSumMm > 20 -> RAIN
  +-- Rule 6: PopMaxPct > 80 -> RAIN
  +-- Rule 7: WindChillMinC < -20 -> WIND_CHILL (invertiert)
  +-- Rule 8: VisibilityMinM < 100 -> POOR_VISIBILITY (invertiert)
  |
  +-- deduplicate(risks) -> per RiskType hoechstes Level
  +-- sort(risks) -> HIGH first
  |
  v
RiskAssessment { Risks: []Risk }
```

## Source

### Neue Dateien

| Datei | Zweck | LOC (ca.) |
|-------|-------|-----------|
| `internal/model/risk.go` | RiskType, RiskLevel, Risk, RiskAssessment | ~50 |
| `internal/model/segment.go` | SegmentWeatherSummary | ~40 |
| `internal/risk/thresholds.go` | Schwellenwert-Konstanten | ~25 |
| `internal/risk/engine.go` | Assess(), Rules 1-8, deduplicate | ~110 |
| `internal/risk/engine_test.go` | 14 Tests | ~120 |
| `internal/risk/exposition.go` | ExposedSection, AssessWithExposition, Rule 9 | ~60 |
| `internal/risk/exposition_test.go` | 4 Tests | ~60 |

### Keine bestehenden Dateien geaendert

ThunderLevel aus forecast.go wird importiert, nicht modifiziert.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| internal/model/forecast.go | Model | ThunderLevel Enum (ThunderNone, ThunderMed, ThunderHigh) |
| src/services/risk_engine.py | Reference | Python-Logik als Vorlage |
| src/app/metric_catalog.py | Reference | Schwellenwerte extrahieren |

## Implementation Details

### Phase M3a: DTOs (~90 LOC, 2 Dateien)

`internal/model/risk.go`:
```go
type RiskType string

const (
    RiskThunderstorm    RiskType = "thunderstorm"
    RiskRain            RiskType = "rain"
    RiskWind            RiskType = "wind"
    RiskAvalanche       RiskType = "avalanche"
    RiskSnowfall        RiskType = "snowfall"
    RiskWindChill       RiskType = "wind_chill"
    RiskPoorVisibility  RiskType = "poor_visibility"
    RiskFreezingRain    RiskType = "freezing_rain"
    RiskWindExposition  RiskType = "wind_exposition"
)

type RiskLevel string

const (
    RiskLow      RiskLevel = "low"
    RiskModerate RiskLevel = "moderate"
    RiskHigh     RiskLevel = "high"
)

type Risk struct {
    Type         RiskType   `json:"type"`
    Level        RiskLevel  `json:"level"`
    AmountMm     *float64   `json:"amount_mm,omitempty"`
    GustKmh      *float64   `json:"gust_kmh,omitempty"`
    FeelsLikeC   *float64   `json:"feels_like_c,omitempty"`
    VisibilityM  *float64   `json:"visibility_m,omitempty"`
}

type RiskAssessment struct {
    Risks []Risk `json:"risks"`
}
```

`internal/model/segment.go`:
```go
type SegmentWeatherSummary struct {
    TempMinC         *float64     `json:"temp_min_c,omitempty"`
    TempMaxC         *float64     `json:"temp_max_c,omitempty"`
    TempAvgC         *float64     `json:"temp_avg_c,omitempty"`
    WindMaxKmh       *float64     `json:"wind_max_kmh,omitempty"`
    GustMaxKmh       *float64     `json:"gust_max_kmh,omitempty"`
    PrecipSumMm      *float64     `json:"precip_sum_mm,omitempty"`
    CloudAvgPct      *int         `json:"cloud_avg_pct,omitempty"`
    HumidityAvgPct   *int         `json:"humidity_avg_pct,omitempty"`
    ThunderLevelMax  ThunderLevel `json:"thunder_level_max,omitempty"`
    VisibilityMinM   *float64     `json:"visibility_min_m,omitempty"`
    WindChillMinC    *float64     `json:"wind_chill_min_c,omitempty"`
    PopMaxPct        *int         `json:"pop_max_pct,omitempty"`
    CapeMaxJkg       *float64     `json:"cape_max_jkg,omitempty"`
    PressureAvgHpa   *float64     `json:"pressure_avg_hpa,omitempty"`
    DewpointAvgC     *float64     `json:"dewpoint_avg_c,omitempty"`
    UvIndexMax       *float64     `json:"uv_index_max,omitempty"`
    SnowNewSumCm     *float64     `json:"snow_new_sum_cm,omitempty"`
}
```

### Phase M3b: Engine Core (~255 LOC, 3 Dateien)

`internal/risk/thresholds.go`:
```go
const (
    windModerate    = 50.0  // km/h
    windHigh        = 70.0
    gustModerate    = 50.0
    gustHigh        = 70.0
    precipModerate  = 20.0  // mm
    popModerate     = 80    // %
    capeModerate    = 1000.0 // J/kg
    capeHigh        = 2000.0
    windChillHighLt = -20.0 // C (invertiert: HIGH wenn < Wert)
    visHighLt       = 100.0 // m (invertiert: HIGH wenn < Wert)
)
```

`internal/risk/engine.go` — Kern-Algorithmus:
```go
func Assess(agg model.SegmentWeatherSummary) model.RiskAssessment {
    var risks []model.Risk

    // Rule 1: Thunder enum
    checkThunder(agg, &risks)
    // Rule 2: CAPE
    checkNormal(agg.CapeMaxJkg, capeModerate, capeHigh, model.RiskThunderstorm, &risks, nil)
    // Rule 3: Wind
    checkNormal(agg.WindMaxKmh, windModerate, windHigh, model.RiskWind, &risks,
        withGust(agg.GustMaxKmh))
    // Rule 4: Gust
    checkNormal(agg.GustMaxKmh, gustModerate, gustHigh, model.RiskWind, &risks,
        withGust(agg.GustMaxKmh))
    // Rule 5: Precipitation
    checkModerateOnly(agg.PrecipSumMm, precipModerate, model.RiskRain, &risks,
        withAmount(agg.PrecipSumMm))
    // Rule 6: Rain Probability
    checkModerateOnlyInt(agg.PopMaxPct, popModerate, model.RiskRain, &risks, nil)
    // Rule 7: Wind Chill (invertiert)
    checkInverted(agg.WindChillMinC, windChillHighLt, model.RiskWindChill, &risks,
        withFeelsLike(agg.WindChillMinC))
    // Rule 8: Visibility (invertiert)
    checkInvertedFloat(agg.VisibilityMinM, visHighLt, model.RiskPoorVisibility, &risks,
        withVisibility(agg.VisibilityMinM))

    return model.RiskAssessment{Risks: deduplicate(risks)}
}
```

Schwellenwert-Check Pattern:
```go
// Normal: value >= high -> HIGH, value >= medium -> MODERATE
func checkNormal(val *float64, medium, high float64, rt model.RiskType,
    risks *[]model.Risk, extras func(*model.Risk)) {
    if val == nil { return }
    var level model.RiskLevel
    if *val >= high {
        level = model.RiskHigh
    } else if *val >= medium {
        level = model.RiskModerate
    } else {
        return
    }
    r := model.Risk{Type: rt, Level: level}
    if extras != nil { extras(&r) }
    *risks = append(*risks, r)
}

// Invertiert: value < threshold -> HIGH
func checkInverted(val *float64, highLt float64, rt model.RiskType,
    risks *[]model.Risk, extras func(*model.Risk)) {
    if val == nil { return }
    if *val >= highLt { return }
    r := model.Risk{Type: rt, Level: model.RiskHigh}
    if extras != nil { extras(&r) }
    *risks = append(*risks, r)
}
```

Deduplizierung:
```go
func deduplicate(risks []model.Risk) []model.Risk {
    best := map[model.RiskType]model.Risk{}
    for _, r := range risks {
        if existing, ok := best[r.Type]; !ok || levelOrder(r.Level) > levelOrder(existing.Level) {
            best[r.Type] = r
        }
    }
    result := make([]model.Risk, 0, len(best))
    for _, r := range best { result = append(result, r) }
    sort.Slice(result, func(i, j int) bool {
        return levelOrder(result[i].Level) > levelOrder(result[j].Level)
    })
    return result
}

func levelOrder(l model.RiskLevel) int {
    switch l {
    case model.RiskHigh: return 2
    case model.RiskModerate: return 1
    default: return 0
    }
}
```

### Phase M3c: Wind Exposition (~120 LOC, 2 Dateien)

`internal/risk/exposition.go`:
```go
const (
    windExpoModerate = 30.0 // km/h
    windExpoHigh     = 50.0
    gustExpoModerate = 40.0 // km/h
    gustExpoHigh     = 60.0
)

type ExposedSection struct {
    StartKm       float64 `json:"start_km"`
    EndKm         float64 `json:"end_km"`
    MaxElevationM float64 `json:"max_elevation_m"`
    ExpositionType string  `json:"exposition_type"` // "GRAT" | "PASS"
}

func AssessWithExposition(agg model.SegmentWeatherSummary,
    segStartKm, segEndKm float64, sections []ExposedSection) model.RiskAssessment {
    assessment := Assess(agg)
    // Overlap-Check + Exposition-Schwellenwerte
    // ... append WIND_EXPOSITION risk if applicable
    return assessment
}
```

Overlap-Check:
```go
overlaps := segStartKm < es.EndKm && segEndKm > es.StartKm
```

## Expected Behavior

- **Ruhiges Wetter** (alle Werte niedrig): Leere RiskAssessment (keine Risks)
- **Thunder HIGH**: 1 Risk THUNDERSTORM/HIGH
- **Wind 55 + Gust 82**: 1 Risk WIND/HIGH (dedupliziert, Gust gewinnt)
- **Precipitation 25mm**: 1 Risk RAIN/MODERATE
- **Visibility 50m**: 1 Risk POOR_VISIBILITY/HIGH (invertiert)
- **Wind Chill -25C**: 1 Risk WIND_CHILL/HIGH (invertiert)
- **Alle nil**: Leere RiskAssessment (nil-safe)
- **Multi-Risk**: Sortiert HIGH vor MODERATE

## Testbarkeit

### Go Tests (14 Kern-Tests + 4 Exposition)

| Test | Input | Expected |
|------|-------|----------|
| NoRisks_CalmWeather | wind=20, gust=30, precip=2, vis=10000, wc=5, cape=200 | risks=[] |
| ThunderHigh | thunder=HIGH | 1x THUNDERSTORM/HIGH |
| ThunderMedium | thunder=MED | 1x THUNDERSTORM/MODERATE |
| WindHigh | wind=75, gust=90 | 1x WIND/HIGH |
| WindModerate | wind=55, gust=45 | 1x WIND/MODERATE |
| GustOverridesWind | wind=55, gust=82 | 1x WIND/HIGH (dedupliziert) |
| PrecipitationModerate | precip=25 | 1x RAIN/MODERATE |
| VisibilityInverted | vis=50 | 1x POOR_VISIBILITY/HIGH |
| WindChillInverted | wc=-25 | 1x WIND_CHILL/HIGH |
| MultipleRisksSorted | thunder=HIGH, wind=55 | >=2, first=HIGH |
| Deduplication | wind=55, gust=82 | 1x WIND/HIGH |
| NoneValuesSkipped | alles nil | risks=[] |
| CapeHigh | cape=2500 | 1x THUNDERSTORM/HIGH |
| CapeModerate | cape=1500 | 1x THUNDERSTORM/MODERATE |
| ExpoModerateWind | wind=35, exposed | 1x WIND_EXPOSITION/MODERATE |
| ExpoHighWind | wind=55, exposed | 1x WIND_EXPOSITION/HIGH |
| ExpoNoOverlap | wind=55, not overlapping | no WIND_EXPOSITION |
| ExpoLowWind | wind=20, exposed | no WIND_EXPOSITION |

## Known Limitations

- Schwellenwerte sind Kompilier-Zeit-Konstanten (keine Runtime-Config)
- Precipitation und Rain Probability haben nur MODERATE, kein HIGH
- Kein assess_segments() Batch-Methode (triviale for-Schleife im Caller)
- ExposedSection Detection (aus GPX) ist nicht Teil dieses Ports

## Changelog

- 2026-04-13: Initial spec created
