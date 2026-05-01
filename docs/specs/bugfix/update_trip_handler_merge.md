---
entity_id: update_trip_handler_merge
type: bugfix
created: 2026-04-30
updated: 2026-04-30
status: draft
version: "1.0"
tags: [backend, go, api, bugfix, trip, persistence]
---

# UpdateTripHandler Merge Fix

## Approval

- [ ] Approved

## Purpose

Fix the silent data loss in `PUT /api/trips/{id}`. The current handler does a full replace of the persisted trip with the request body, deleting any optional `omitempty` fields (`aggregation`, `report_config`, `weather_config`, `display_config`, `avalanche_regions`) that the body doesn't include. Replace this with a read-modify-write merge so a minimal-body PUT preserves fields the client did not send.

Maps the project anti-pattern documented in `CLAUDE.md` ("Backend Replace statt Merge") to a concrete fix.

## Source

- **File:** `internal/handler/trip.go`
- **Identifier:** `UpdateTripHandler` (lines 112-161)
- **Specific Issue:** Line 131 (`var trip model.Trip`) decodes into a fresh struct; line 151 (`s.SaveTrip(trip)`) persists it as-is, ignoring the `existing` trip loaded at line 117.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `model.Trip` | Struct | Domain model, unchanged |
| `store.LoadTrip` | Function | Loads existing trip from disk |
| `store.SaveTrip` | Function | Persists trip to disk (full marshal) |
| `validateTrip` | Function | Validates required fields (id, name, stages, waypoint coords) |

## Root Cause Analysis

### Current Implementation (BROKEN)

```go
func UpdateTripHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        existing, err := s.LoadTrip(id)              // loaded but only used for 404
        // ...
        var trip model.Trip                          // FRESH empty struct
        json.NewDecoder(r.Body).Decode(&trip)        // body fields → zero everywhere else
        trip.ID = id
        validateTrip(trip)
        s.SaveTrip(trip)                             // overwrites with omitempty fields gone
    }
}
```

A request body `{"id": "x", "name": "X", "stages": [...]}` decodes into a `model.Trip` with all map/slice fields nil. `SaveTrip` calls `json.MarshalIndent` which omits the nil `omitempty` fields entirely from the persisted JSON.

### Why JSON-decode alone cannot solve this

Encoding/json in Go cannot distinguish between "field absent" and "field set to null/zero" when the destination field is a value type (`map[string]interface{}`, `[]string`). Both end up as nil. A pointer-typed destination resolves the ambiguity: nil pointer = absent, non-nil pointer = explicit value.

## Implementation Strategy

### Solution: DTO with Pointer Fields + Merge

Introduce an unexported request type local to `internal/handler/trip.go`. Decode into the DTO, then merge each non-nil pointer into the loaded `existing` trip. The domain model `model.Trip` is unchanged.

```go
type tripUpdateRequest struct {
    Name             *string                 `json:"name"`
    Stages           *[]model.Stage          `json:"stages"`
    AvalancheRegions *[]string               `json:"avalanche_regions,omitempty"`
    Aggregation      *map[string]interface{} `json:"aggregation,omitempty"`
    WeatherConfig    *map[string]interface{} `json:"weather_config,omitempty"`
    DisplayConfig    *map[string]interface{} `json:"display_config,omitempty"`
    ReportConfig     *map[string]interface{} `json:"report_config,omitempty"`
}

func UpdateTripHandler(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        s = s.WithUser(middleware.UserIDFromContext(r.Context()))
        id := chi.URLParam(r, "id")

        existing, err := s.LoadTrip(id)
        // ... existing 404 / 500 handling unchanged ...

        var req tripUpdateRequest
        if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
            // 400 bad_request
        }

        // Merge: each non-nil pointer overrides existing
        if req.Name != nil {
            existing.Name = *req.Name
        }
        if req.Stages != nil {
            existing.Stages = *req.Stages
        }
        if req.AvalancheRegions != nil {
            existing.AvalancheRegions = *req.AvalancheRegions
        }
        if req.Aggregation != nil {
            existing.Aggregation = *req.Aggregation
        }
        if req.WeatherConfig != nil {
            existing.WeatherConfig = *req.WeatherConfig
        }
        if req.DisplayConfig != nil {
            existing.DisplayConfig = *req.DisplayConfig
        }
        if req.ReportConfig != nil {
            existing.ReportConfig = *req.ReportConfig
        }
        existing.ID = id

        if err := validateTrip(*existing); err != nil {
            // 400 validation_error (existing logic)
        }

        if err := s.SaveTrip(*existing); err != nil {
            // 500 store_error
        }

        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(existing)
    }
}
```

### Semantic Rules

| Body field | Behavior |
|-----------|----------|
| Field absent | `existing` value preserved (merge skip) |
| Field present, value `null` | Pointer non-nil but dereferences to zero — **explicit clear** is permitted by this contract. (Edge case; not blocked by current frontend.) |
| Field present, value provided | Replace `existing` field with body value (field-level replace, no deep merge of map keys) |

The "explicit null clears" semantics is documented but not actively used by any current client. It falls out naturally from the pointer pattern and avoids reintroducing ambiguity.

### Validation

`validateTrip(*existing)` is called *after* the merge. Required fields (`id`, `name`, `stages`, waypoint coords) are checked against the merged result, so a minimal-body request with no `name` field still passes if `existing.Name` is non-empty. Equally, an explicit `"name": ""` is rejected with 400 — same as before.

### Why not deep-merge maps

Sub-keys inside `aggregation`/`weather_config` etc. are opaque to the backend and never read by Go code (verified via grep over `internal/**/*.go`: no direct reads of `trip.Aggregation`, `trip.ReportConfig`, etc., outside of pass-through serialization). Field-level replace is sufficient and predictable. Deep-merge would require an unambiguous syntax for "delete this sub-key", which we do not need.

## Expected Behavior

### Before Fix (Current State — broken)
- Action: `PUT /api/trips/gr221-mallorca` with body `{"id":"gr221-mallorca","name":"GR221","stages":[...]}`
- Observed: HTTP 200 returned, file on disk now contains only `id`, `name`, `stages` — `aggregation` and `report_config` silently deleted.

### After Fix (Expected — green)
- Action: same PUT.
- Expected: HTTP 200, file on disk retains `aggregation` and `report_config` from the previous state.
- Action: PUT with body `{"id":"gr221-mallorca","name":"GR221","stages":[...],"aggregation":{"x":1}}`
- Expected: HTTP 200, `aggregation` replaced with `{"x":1}`, `report_config` still preserved.

## TDD Test Strategy

### Test File

`internal/handler/trip_write_test.go` — extend existing test file.

### New Test Cases (RED, then GREEN after fix)

1. `TestUpdateTripHandlerPreservesAggregation` — seed with `aggregation`; PUT minimal body; load and assert `aggregation` unchanged.
2. `TestUpdateTripHandlerPreservesReportConfig` — same pattern, `report_config`.
3. `TestUpdateTripHandlerPreservesWeatherConfig` — same pattern, `weather_config`.
4. `TestUpdateTripHandlerPreservesDisplayConfig` — same pattern, `display_config`.
5. `TestUpdateTripHandlerPreservesAvalancheRegions` — same pattern, `avalanche_regions`.
6. `TestUpdateTripHandlerReplacesAggregationWhenSent` — seed with `aggregation: {a:1}`, PUT with `aggregation: {b:2}`, assert replaced (not merged).
7. `TestUpdateTripHandlerKeepsAllConfigsOnNameOnlyUpdate` — seed with all 5 optional fields populated; PUT with only `{id, name, stages}` (no other fields); load and assert all 5 retained.

### Must-Stay-Green (Existing Tests)

- `TestUpdateTripHandler` — full body update, must still return 200.
- `TestUpdateTripHandlerNotFound` — 404 path unchanged.
- `TestCreateTripHandler*` — `CreateTripHandler` is untouched.

### Run

```bash
go test ./internal/handler/... -run TestUpdateTripHandler -v
```

## Files to Modify

| Path | Type | Change |
|------|------|--------|
| `internal/handler/trip.go` | Modify | Replace `UpdateTripHandler` body with DTO-merge pattern. Add unexported `tripUpdateRequest` type. |
| `internal/handler/trip_write_test.go` | Modify | Add 7 new test cases (see TDD Test Strategy). |

## Files NOT to Modify

- `internal/model/trip.go` — Domain model stays. No pointer fields in storage layer.
- `internal/handler/weather_config.go` — Independent endpoints, separate code path, not affected.
- `internal/store/store.go` — `SaveTrip`/`LoadTrip` unchanged.

## Known Limitations

- Field-level replace (no deep-merge): if a client wants to change one sub-key in `aggregation` without losing siblings, it must send the full merged object. This matches the current frontend behavior (`TripWizard.svelte:62-66` always spreads the full object).
- "Explicit null clears the field" semantics is technically possible via pointer-to-nil-map, but no client currently uses it. Documented in spec; not actively tested as a primary case.
- DTO is local to the handler package. If `CreateTripHandler` ever wants the same input contract, the DTO can be promoted later — not in scope here.

## Validation Checklist

After implementation (Phase 7):

- [ ] All 7 new tests pass (GREEN)
- [ ] All existing tests in `internal/handler/...` still pass
- [ ] `go build ./...` succeeds
- [ ] `go vet ./...` clean
- [ ] Manual reproduction with `gr221-mallorca` (curl PUT minimal body) shows preserved `aggregation`/`report_config`
- [ ] Issue #99 acceptance criteria all checked off

## Changelog

- 2026-04-30: Initial spec created from analysis in `docs/context/bug-99-update-trip-merge.md`
