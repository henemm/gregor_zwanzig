---
entity_id: day_comparison_service
type: module
created: 2026-06-11
updated: 2026-06-11
status: approved
version: "1.0"
tags: [service, weather, comparison, vortag-vergleich]
---

# DayComparisonService — Vortag-Delta-Berechnung

## Approval

- [x] Approved

## Purpose

`DayComparisonService` berechnet Delta-Werte zwischen zwei Listen von `SegmentWeatherData`
(heute vs. gestern) und gibt ein strukturiertes `DayComparison`-DTO zurück. Pro Segment
enthält das Ergebnis ein `DayComparisonEntry` mit absoluten Deltas und einem
Richtungs-Enum (`BETTER` / `WORSE` / `EQUAL`). Ausschließlich regelbasiert — keine KI.

## Source

- **File:** `src/services/day_comparison.py` (NEW)
- **Identifier:** `DayComparisonService`, `DayComparison`, `DayComparisonEntry`, `ComparisonDirection`

## Estimated Scope

- **LoC:** ~120
- **Files:** 2 (service + test)
- **Effort:** medium

## Dependencies

- `app.models.SegmentWeatherData` — Input-Typ
- `app.models.SegmentWeatherSummary` — Quell-Felder für Delta
- `app.models.ThunderLevel` — Ordinal-Vergleich (NONE=0, MED=1, HIGH=2)
- F1 #747 (WeatherSnapshotService.save_dated/load_dated) — liefert die yesterday-Liste

## Affected Files

| File | Change |
|------|--------|
| `src/services/day_comparison.py` | NEU — DTOs + Service |
| `tests/tdd/test_day_comparison_service.py` | NEU — TDD-Tests |

## Data Model

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List

class ComparisonDirection(str, Enum):
    BETTER = "BETTER"
    WORSE  = "WORSE"
    EQUAL  = "EQUAL"
    # Sonderfall: Segment existiert nur heute ODER nur gestern
    MISSING = "MISSING"

@dataclass
class MetricDelta:
    """Delta für eine einzelne Metrik."""
    delta: Optional[float]        # heute - gestern (None wenn Metrik fehlt)
    direction: ComparisonDirection

@dataclass
class DayComparisonEntry:
    """Vergleich für ein Segment (heute vs. gestern)."""
    segment_id: int
    temp_min:   MetricDelta
    temp_max:   MetricDelta
    wind_max:   MetricDelta
    gust_max:   MetricDelta
    precip_sum: MetricDelta
    thunder:    MetricDelta   # delta = ordinal-Differenz (int)

@dataclass
class DayComparison:
    entries: List[DayComparisonEntry] = field(default_factory=list)
```

## Richtungslogik

| Metrik | BETTER | WORSE | EQUAL |
|--------|--------|-------|-------|
| `temp_min_c` | — immer EQUAL (kein inhärentes besser/schlechter) | — | delta == 0 |
| `temp_max_c` | — immer EQUAL | — | delta == 0 |
| `wind_max_kmh` | delta < 0 | delta > 0 | delta == 0 |
| `gust_max_kmh` | delta < 0 | delta > 0 | delta == 0 |
| `precip_sum_mm` | delta < 0 | delta > 0 | delta == 0 |
| `thunder_level_max` | ordinal(heute) < ordinal(gestern) | ordinal(heute) > ordinal(gestern) | gleich |

**ThunderLevel-Ordinal:** `NONE=0`, `MED=1`, `HIGH=2`.

**EQUAL-Toleranz für Floats:** `abs(delta) < 0.01` gilt als EQUAL (Rundungsfehler).

## Segment-Matching

- Matching erfolgt per `segment_id` (`SegmentWeatherData.segment.segment_id`).
- Segment vorhanden heute, nicht gestern → `DayComparisonEntry` mit allen `direction=MISSING`.
- Segment vorhanden gestern, nicht heute → wird ignoriert (heutiger Tag ist Referenz).
- Fehlende Metrik (`None`) in einem der Tage → `MetricDelta(delta=None, direction=MISSING)`.

## Acceptance Criteria

**AC-1:** Given zwei identisch strukturierte Segment-Listen (je 2 Segmente) / When `compare(today, yesterday)` / Then gibt `DayComparison` mit 2 Einträgen zurück, delta für `precip_sum_mm` ist `heute - gestern`.

**AC-2:** Given gestern `precip_sum_mm=8.0`, heute `precip_sum_mm=2.0` / When `compare()` / Then `precip_sum.direction == BETTER` und `delta == -6.0`.

**AC-3:** Given gestern `thunder_level_max=ThunderLevel.HIGH`, heute `ThunderLevel.NONE` / When `compare()` / Then `thunder.direction == BETTER` und `delta == -2` (ordinal-Differenz).

**AC-4:** Given heute 3 Segmente, gestern nur 2 (Segment-ID 3 fehlt gestern) / When `compare()` / Then Segment 3 hat alle Directions `MISSING`; Segmente 1+2 werden normal berechnet.

**AC-5:** Given `temp_max_c` gestern `15.0`, heute `22.0` / When `compare()` / Then `temp_max.direction == EQUAL` (Temperatur ist neutral), `delta == +7.0`.

## Changelog

- v1.0 (2026-06-11): Initial spec, Issue #748
