# Context: Bug #349 — normalizeMetricsPayload überschreibt 'horizons alle false'

## Request Summary

`normalizeMetricsPayload()` in `internal/handler/metric_preset.go` kann nicht unterscheiden,
ob das JSON-Feld `horizons` fehlt (Go Zero-Value `{false,false,false}`) oder ob es explizit
auf `{today:false,tomorrow:false,day_after:false}` gesetzt wurde. Die aktuelle Heuristik
überschreibt beide Fälle mit `{true,true,true}`.

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `internal/handler/metric_preset.go:54-106` | Enthält `normalizeMetricsPayload()` mit dem Bug (Zeilen 77-83) |
| `internal/model/metric_preset.go` | `Horizons`-Struct (plain bool fields, kein Pointer) |
| `internal/handler/metric_preset_test.go` | Bestehende Tests; kein Test für #349 vorhanden |

## Bug-Ort

```go
// metric_preset.go:77-83 — FEHLERHAFT
for i := range asStructs {
    if !asStructs[i].Horizons.Today &&
        !asStructs[i].Horizons.Tomorrow &&
        !asStructs[i].Horizons.DayAfter {
        asStructs[i].Horizons = allTrue  // überschreibt auch explicit {false,false,false}
    }
}
```

## Lösungsstrategie

Lokaler Decode-Struct mit `*model.Horizons` (Pointer):
- `nil` → Feld fehlt im JSON → Default `{true,true,true}`
- `non-nil` → explizit gesetzt → Wert übernehmen (auch `{false,false,false}`)

`model.Horizons` selbst bleibt unverändert (kein breaking change).

## Bestehende Patterns

- `PatchMetricPresetHandler` in derselben Datei nutzt bereits `*string` / `*bool` für optionale Patch-Felder — identisches Muster.
- `createPresetRequest.Metrics` nutzt `json.RawMessage` für polymorphes Decoding — bereits etabliert.

## Abhängigkeiten

- Upstream: `json.Unmarshal` → `model.DisplayMetric`
- Downstream: `CreateMetricPresetHandler` ruft `normalizeMetricsPayload()` auf
- PATCH-Handler (`PatchMetricPresetHandler`) bekommt `[]DisplayMetric` direkt — betrifft ihn NICHT

## Scope

Nur `normalizeMetricsPayload()` in `metric_preset.go`. Kein Modell-Change, kein Store-Change, kein Frontend-Change. ~10 Zeilen.
