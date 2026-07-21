---
entity_id: bug_349_horizons_zero_value
type: bugfix
created: 2026-05-29
updated: 2026-05-29
status: implemented
version: "1.0"
tags: [bug, go-api, metric-presets, horizons, zero-value]
---

# Bug #349 — normalizeMetricsPayload überschreibt explizit alle-false horizons mit alle-true

## Approval

- [x] Approved (implemented 2026-05-29)

## Purpose

`normalizeMetricsPayload()` in `internal/handler/metric_preset.go` kann nicht
unterscheiden, ob das Feld `horizons` im JSON-Payload fehlt (Zero-Value durch
`json.Unmarshal`) oder ob der Client es explizit mit allen drei Flags auf `false`
gesendet hat — beides ergibt denselben Go-Struct-Wert `{false, false, false}`.
Die aktuelle Heuristik interpretiert diesen Zustand als „nicht gesetzt" und setzt
alle drei Flags auf `true`, was eine explizite Nutzer-Eingabe `{false, false, false}`
lautlos überschreibt und damit unbrauchbar macht.

## Source

- **File:** `internal/handler/metric_preset.go`
- **Identifier:** `func normalizeMetricsPayload(raw json.RawMessage, friendlyIDs []string) []model.DisplayMetric` (Z. 54-106, Bug an Z. 77-83)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `model.DisplayMetric` | Go-Struct | Enthält das `Horizons`-Feld vom Typ `model.Horizons` |
| `model.Horizons` | Go-Struct | `{Today, Tomorrow, DayAfter bool}` — Zero-Value ist identisch mit explizit alle-false |
| `encoding/json` | stdlib | `Unmarshal` setzt fehlende Felder auf Zero-Value, kein Nil-Signal für Pointer |

## Implementation Details

Einführung eines lokalen Decode-Structs ausschließlich für den Unmarshal-Schritt in
`normalizeMetricsPayload`. Das Feld `Horizons` wird darin als `*model.Horizons`
(Pointer) deklariert.

Nach dem Unmarshal gilt:
- Pointer ist `nil` → Feld fehlte im JSON → Default `{true, true, true}` anwenden
- Pointer ist non-nil → Feld war explizit gesetzt → Wert direkt übernehmen (auch wenn alle drei false sind)

```go
type displayMetricInput struct {
    MetricID string          `json:"metric_id"`
    Horizons *model.Horizons `json:"horizons"`
    // weitere Felder nach Bedarf
}
```

Nach dem Decode:
```go
if entry.Horizons == nil {
    normalized.Horizons = model.Horizons{Today: true, Tomorrow: true, DayAfter: true}
} else {
    normalized.Horizons = *entry.Horizons
}
```

Scope: ausschließlich `normalizeMetricsPayload()` — kein Modell-Change, kein Store-Change,
kein Frontend-Change.

## Expected Behavior

- **Input:** JSON-Payload für POST/PUT `/api/metric-presets` mit einem `metrics`-Array
  dessen Einträge ein `horizons`-Objekt haben können oder nicht.
- **Output:** `[]model.DisplayMetric` mit korrekt normalisierten `Horizons`-Werten:
  - `horizons` fehlt im JSON → `{Today: true, Tomorrow: true, DayAfter: true}`
  - `horizons` explizit auf alle false → `{Today: false, Tomorrow: false, DayAfter: false}`
  - `horizons` teilweise gesetzt → exakt der gesendete Wert
- **Side effects:** Keine. Store, Modell und Frontend bleiben unverändert.

## Acceptance Criteria

- **AC-1:** Given ein POST `/api/metric-presets`-Payload mit `"horizons":{"today":false,"tomorrow":false,"day_after":false}` für eine MetricEntry / When der Handler die Anfrage verarbeitet / Then enthält der gespeicherte Preset die Horizons `{Today: false, Tomorrow: false, DayAfter: false}` und NICHT `{Today: true, Tomorrow: true, DayAfter: true}`.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein POST `/api/metric-presets`-Payload in dem für eine MetricEntry das `horizons`-Feld komplett fehlt / When der Handler die Anfrage verarbeitet / Then enthält der gespeicherte Preset die Default-Horizons `{Today: true, Tomorrow: true, DayAfter: true}`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein POST `/api/metric-presets`-Payload mit `"horizons":{"today":true,"tomorrow":false,"day_after":false}` für eine MetricEntry / When der Handler die Anfrage verarbeitet / Then enthält der gespeicherte Preset exakt die gesendeten Horizons `{Today: true, Tomorrow: false, DayAfter: false}` ohne Modifikation.
  - Test: (populated after /tdd-red)

## Known Limitations

- Der Fix betrifft nur den Eingangs-Normalisierungsschritt. Bereits gespeicherte Presets
  mit fälschlich überschriebenen Horizons werden nicht migriert — das ist für den
  gemeldeten Bug nicht erforderlich, da Nutzer ihre Presets nach dem Fix neu anlegen können.

## Changelog

- 2026-05-29: Implementation complete. Bug-Fix deployed:
  - `normalizeMetricsPayload()` nutzt lokalen Decode-Struct mit `*Horizons` Pointer
  - nil-Check unterscheidet jetzt sicher zwischen fehlendem Feld (Default) und explizit false
  - Tests AC-1/2/3 validieren alle Szenarien (Payload-Varianten)
  - Scope: nur Handler, kein Modell/Store/Frontend-Change
  - Test-Dateien: `internal/handler/metric_preset_test.go` Zeilen 524–561
