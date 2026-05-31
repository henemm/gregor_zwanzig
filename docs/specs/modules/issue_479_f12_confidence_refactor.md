---
entity_id: issue_479_f12_confidence_refactor
type: module
created: 2026-05-31
updated: 2026-05-31
status: approved
version: "1.0"
tags: [refactor, weather_pattern, sms, email, F12]
---

# Issue #479 — F12 WL-Block aus Konfidenz-Daten ableiten

## Approval

- [x] Approved (PO bestätigt, Issue #479)

## Purpose

Vereinfacht F12 (Großwetterlage / Stabilitäts-Label) komplett: Entfernt den
separaten Z500-API-Call (`_fetch_ensemble_with_z500`) und leitet das Label
(STABIL / WECHSELHAFT / FRAGIL) stattdessen aus den **bereits vorhandenen**
`confidence_pct_min`-Werten der Folge-Etappen ab. Der WL-Token wird zudem
aus dem SMS-Output entfernt (C+/C~/C? deckt den Use-Case dort ab); der
farbige WL-Block in der E-Mail bleibt erhalten.

## Source

- **File:** `src/services/weather_pattern.py`
- **Identifier:** `compute_stability`, `WeatherPatternService`
- **Sekundär:** `src/app/models.py::StabilityResult`,
  `src/output/tokens/builder.py`, `src/output/tokens/render.py`,
  `src/providers/openmeteo.py`, `src/services/trip_report_scheduler.py`,
  `docs/reference/sms_format.md`

## Estimated Scope

- **LoC:** ~−250 / +60 (netto ca. −190)
- **Files:** 7 produktiv + 2 Tests + 1 Doku
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `SegmentWeatherSummary.confidence_pct_min` | Eingabe | Bereits berechnete Konfidenz pro Segment |
| `Trip.get_future_stages()` | Eingabe | Liefert Folge-Etappen ab `target_date` |
| `StabilityResult.label` | Ausgabe | Bleibt erhalten (E-Mail-Block) |

## Implementation Details

```python
# Vereinfachtes StabilityResult — keine Z500-Score-Felder mehr.
@dataclass(frozen=True)
class StabilityResult:
    label: Literal["STABIL", "WECHSELHAFT", "FRAGIL"]
    confidence_pct: int   # min(confidence_pct_min) der Folge-Etappen

# Pure Funktion: Liste von Konfidenz-Werten → StabilityResult oder None.
def compute_stability(values: list[Optional[int]]) -> Optional[StabilityResult]:
    valid = [v for v in values if v is not None]
    if not valid:
        return None
    agg = min(valid)
    if agg >= 75:   label = "STABIL"
    elif agg >= 50: label = "WECHSELHAFT"
    else:           label = "FRAGIL"
    return StabilityResult(label=label, confidence_pct=agg)
```

Im SMS-Builder wird der WL-Token entfernt (Symbol-Liste, Priorität, Emit-
Block). Render.py entfernt den `_drop_first(tokens, "WL")`-Truncation-Schritt.
OpenMeteoProvider verliert `_fetch_ensemble_with_z500`. Scheduler übergibt
die bereits berechneten `segment_weather`-Daten direkt an
`WeatherPatternService().compute_for_trip(...)` — kein Provider mehr nötig.

## Expected Behavior

- **Input:** Liste der `confidence_pct_min`-Werte aus den Folge-Segmenten
- **Output:** `StabilityResult(label, confidence_pct)` oder `None`
- **Side effects:** Keine API-Calls mehr in F12; kein WL-Token im SMS

## Acceptance Criteria

- **AC-1:** Given `StabilityResult` / When inspiziert / Then **kein** `score`-
  und **kein** `component_scores`-Feld, aber **ein** `confidence_pct`-Feld
  vorhanden.
  - Test: `test_stability_result_has_no_score_field`

- **AC-2:** Given Konfidenz-Werte `[80, 90, 75]` / When `compute_stability`
  aufgerufen / Then Label = `STABIL`, confidence_pct = 75.
  - Test: `test_stability_from_high_confidence`

- **AC-3:** Given Konfidenz-Werte `[80, 60, 55]` / When `compute_stability`
  aufgerufen / Then Label = `WECHSELHAFT`, confidence_pct = 55.
  - Test: `test_stability_from_medium_confidence`

- **AC-4:** Given Konfidenz-Werte `[80, 45]` / When `compute_stability`
  aufgerufen / Then Label = `FRAGIL`, confidence_pct = 45.
  - Test: `test_stability_from_low_confidence`

- **AC-5:** Given Werte `[None, 80, None]` / When `compute_stability`
  aufgerufen / Then None-Werte werden ignoriert, Label = `STABIL`.
  - Test: `test_stability_none_values_ignored`

- **AC-6:** Given Werte `[None, None]` / When `compute_stability` aufgerufen
  / Then Rückgabe ist `None`.
  - Test: `test_stability_all_none_returns_none`

- **AC-7:** Given leere Liste `[]` / When `compute_stability` aufgerufen /
  Then Rückgabe ist `None`.
  - Test: `test_stability_empty_list_returns_none`

- **AC-8:** Given SMS-Builder / When `STD_SYMBOLS` inspiziert / Then `"WL"`
  ist **nicht** enthalten.
  - Test: `test_wl_token_not_in_sms_output`

- **AC-9:** Given `OpenMeteoProvider` / When inspiziert / Then Methode
  `_fetch_ensemble_with_z500` existiert **nicht** mehr.
  - Test: `test_z500_method_removed_from_provider`

- **AC-10:** Given `WeatherPatternService.__init__` / When Signatur inspiziert
  / Then Parameter `provider` existiert **nicht** mehr.
  - Test: `test_weather_pattern_service_no_provider_param`

## Known Limitations

- Die Aggregation ist `min(...)` über die Folge-Etappen — eine einzelne
  unsichere Etappe drückt das Gesamt-Label auf FRAGIL. PO-bestätigt:
  konservatives Verhalten ist gewünscht.
- Maximal die ersten 5 Folge-Etappen werden berücksichtigt
  (analog `MAX_FUTURE_DAYS = 5` in der bisherigen Logik).

## Changelog

- 2026-05-31: Initial spec für Issue #479 (Refactor)
