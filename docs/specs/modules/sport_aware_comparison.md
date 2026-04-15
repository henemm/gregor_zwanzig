---
entity_id: sport_aware_comparison
type: module
created: 2026-04-15
status: draft
version: "1.0"
tags: [comparison, scoring, activity-profile, wandern, wintersport]
---

# Sport-Aware Comparison

## Approval

- [ ] Approved

## Purpose

Sport-abhängiges Scoring für den Wetter-Vergleich. Was "gutes Wetter" ist, hängt von der Aktivität ab: Neuschnee ist gut für Skifahrer, schlecht für Wanderer. Gewitter ist irrelevant für Skifahrer, aber lebensbedrohlich für Wanderer auf Graten.

## Scope

### In Scope
- `calculate_score()` refactoring: Accept profile parameter, dispatch to profile-specific scorer
- 3 Scoring-Funktionen: `_score_wintersport` (existing logic), `_score_wandern` (new), `_score_allgemein` (new)
- New metric extraction in ComparisonEngine: `thunder_level`, `cape_jkg`, `pop_pct`
- `activity_profile` field on `CompareSubscription` (Python, Go, Frontend)
- `activity_profile` query parameter on `/api/compare` endpoint
- Profile selector in SvelteKit compare page and subscription form
- Email subject rename: "Ski Resort Comparison" → "Wetter-Vergleich"

### Out of Scope
- Risk Engine changes (stays activity-neutral)
- New activity profiles (klettern, radfahren)
- Trip report scoring (only compare)
- Weather Config Dialog (metric toggles)

## Source

- **File:** `src/web/pages/compare.py` — `calculate_score()`, `ComparisonEngine.run()`
- **File:** `src/app/user.py` — `CompareSubscription` model
- **File:** `src/app/loader.py` — subscription parsing
- **File:** `src/services/compare_subscription.py` — scheduler subscription runner
- **File:** `api/routers/compare.py` — compare API endpoint
- **File:** `internal/model/subscription.go` — Go subscription model
- **File:** `internal/handler/subscription.go` — Go validation
- **File:** `frontend/src/lib/types.ts` — Subscription type
- **File:** `frontend/src/lib/components/SubscriptionForm.svelte` — form
- **File:** `frontend/src/routes/compare/+page.svelte` — compare page

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `LocationActivityProfile` | enum | `wintersport`, `wandern`, `allgemein` |
| `PROFILE_METRIC_IDS` | dict | metric sets per profile |
| `ComparisonEngine` | class | runs comparison |
| `ForecastDataPoint` | dataclass | has `thunder_level`, `cape_jkg`, `pop_pct` |

## Implementation Details

### 1. Scoring Function Refactoring

```python
def calculate_score(
    metrics: Dict[str, Any],
    profile: Optional[LocationActivityProfile] = None,
) -> int:
    effective = profile or LocationActivityProfile.ALLGEMEIN
    if effective == LocationActivityProfile.WINTERSPORT:
        return _score_wintersport(metrics)
    elif effective == LocationActivityProfile.WANDERN:
        return _score_wandern(metrics)
    else:
        return _score_allgemein(metrics)
```

### 2. Wandern Scoring Weights

Base score: **50**

Design-Prinzip: Maximale Einzelstrafe -25, damit selbst der schlimmste Einzelfaktor
den Score nicht unter 25 drückt. Erst KOMBINIERTE schlechte Bedingungen ergeben Score <20.

| Factor | Max Impact | Threshold |
|--------|-----------|-----------|
| Thunder HIGH | -25 | `thunder_level == "HIGH"` |
| Thunder MED | -15 | `thunder_level == "MED"` |
| Heavy rain (>5mm) | -20 | `precip_mm > 5` |
| Light rain (>1mm) | -10 | `precip_mm > 1` |
| Rain probability >80% | -10 | `pop_max_pct > 80` |
| Visibility <200m | -20 | Navigation impossible |
| Visibility <1000m | -10 | Difficult |
| Wind >60 km/h | -20 | Ridge danger |
| Wind 40-60 km/h | -10 | Unpleasant |
| Cloud >90% | -5 | Overcast |
| Sunshine 7+h | +20 | Excellent |
| Sunshine 5-7h | +12 | Good |
| Sunshine 3-5h | +5 | Acceptable |
| Temp 10-20°C | +10 | Ideal hiking |
| Temp 5-10°C | +5 | Cool but fine |
| Temp <0°C | -10 | Hypothermia risk |
| Visibility >5km | +5 | Orientation bonus |

Score-Bereich bei typischen Bedingungen:
- Perfekter Wandertag (Sonne, kein Wind, mild): 50+20+10+5 = **85**
- Akzeptabel (leichte Wolken, kein Regen): 50+5+5 = **60**
- Grenzwertig (leichter Regen, Wind): 50-10-10+5 = **35**
- Gefaehrlich (Gewitter + Regen): 50-25-20 = **5**

### 3. Allgemein Scoring Weights

Base score: **55**

| Factor | Max Impact |
|--------|-----------|
| Heavy rain | -20 |
| Thunder HIGH | -20 |
| Wind >50 km/h | -15 |
| Cloud >80% | -6 |
| Temp <-10°C | -8 |
| Sunshine 6+h | +15 |
| Temp 5-25°C | +5 |

### 4. Wintersport Scoring (existing, unchanged)

Keep current logic from `_score_wintersport()` (lines 45–137 in `compare.py`). No changes.

### 5. New Metric Extraction in ComparisonEngine.run()

After existing metric extraction (~line 350), add:

```python
# Thunder level (max severity)
thunder_levels = [dp.thunder_level for dp in filtered_data if dp.thunder_level is not None]
if thunder_levels:
    level_rank = {"NONE": 0, "MED": 1, "HIGH": 2}
    metrics["thunder_level"] = max(thunder_levels, key=lambda x: level_rank.get(x, 0))

# CAPE (thunderstorm energy)
capes = [dp.cape_jkg for dp in filtered_data if dp.cape_jkg is not None]
if capes:
    metrics["cape_max_jkg"] = max(capes)

# Rain probability
pops = [dp.pop_pct for dp in filtered_data if dp.pop_pct is not None]
if pops:
    metrics["pop_max_pct"] = max(pops)
```

### 6. Data Model Changes

**Python** (`src/app/user.py`):
```python
activity_profile: Optional[LocationActivityProfile] = None
```

**Go** (`internal/model/subscription.go`):
```go
ActivityProfile *string `json:"activity_profile,omitempty"`
```

**Go validation** (`internal/handler/subscription.go`):
```go
if sub.ActivityProfile != nil {
    valid := map[string]bool{"wintersport": true, "wandern": true, "allgemein": true}
    if !valid[*sub.ActivityProfile] {
        return fmt.Errorf("activity_profile must be wintersport, wandern, or allgemein")
    }
}
```

**Frontend** (`frontend/src/lib/types.ts`):
```typescript
activity_profile?: 'wintersport' | 'wandern' | 'allgemein';
```

### 7. API Changes

`api/routers/compare.py` — add query parameter:
```python
activity_profile: Optional[str] = Query(None)
```

Pass to `ComparisonEngine.run(..., profile=profile)`.

### 8. UI Changes

**SubscriptionForm.svelte** — add dropdown with 3 options: Allgemein, Wintersport, Wandern. Field maps to `activity_profile`.

**Compare page** (`frontend/src/routes/compare/+page.svelte`) — add profile selector before "Vergleichen" button.

### 9. Email Subject

```python
# Old: f"Ski Resort Comparison: {sub.name} ({now.strftime('%d.%m.%Y')})"
# New: f"Wetter-Vergleich: {sub.name} ({now.strftime('%d.%m.%Y')})"
```

## Expected Behavior

- **Input:** Subscription with `activity_profile="wandern"`, 5 locations, time window 8–16
- **Output:** Comparison with wandern-weighted scores (thunder/rain penalized, sunshine rewarded)
- **Side effects:** Email with "Wetter-Vergleich" subject, scores reflecting hiking conditions

## Testing

1. `test_wintersport_deep_snow_high_score` — `snow_depth=100`, `snow_new=20` → score > 80
2. `test_wandern_thunderstorm_low_score` — `thunder_level=HIGH` → score < 20
3. `test_wandern_clear_sunny_high_score` — no rain, `sunshine=7`, `temp=15` → score > 75
4. `test_allgemein_ignores_snow` — `snow_depth=200` → no score change
5. `test_profile_none_defaults_allgemein` — `profile=None` behaves like allgemein
6. `test_wandern_metrics_extracted` — `thunder_level`, `cape`, `pop` in metrics dict
7. `test_subscription_activity_profile_roundtrip` — save with profile, load, verify

## Known Limitations

- Wandern scoring only available with OpenMeteo (thunder, CAPE not from Geosphere)
- Scores not comparable across profiles (wandern 70 ≠ wintersport 70)
- No per-location scoring in mixed-profile subscriptions

## Changelog

- 2026-04-15: v1.0 Initial spec
