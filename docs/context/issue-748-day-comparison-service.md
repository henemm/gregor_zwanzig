# Context: Issue #748 — DayComparisonService

## Request Summary
Neuer Service `DayComparisonService` berechnet Delta-Werte zwischen zwei Listen von `SegmentWeatherData` (heute vs. gestern) und gibt ein strukturiertes `DayComparison`-DTO mit Richtungs-Enums (BETTER/WORSE/EQUAL) zurück. F2 aus der 6-teiligen Vortag-Vergleich-Story.

## Related Files
| File | Relevanz |
|------|---------|
| `src/app/models.py:332` | `SegmentWeatherSummary` — alle 6 Target-Metriken definiert |
| `src/app/models.py:387` | `SegmentWeatherData` — Input-Typ für compare() |
| `src/app/models.py:28` | `ThunderLevel` Enum: NONE / MED / HIGH (nicht LOW!) |
| `src/services/weather_snapshot.py` | F1 (#747) — save_dated/load_dated bereits implementiert |
| `src/services/weather_change_detection.py:31` | `_THUNDER_ORDINAL = {NONE:0, MED:1, HIGH:2}` — Muster für Ordinalvergleich |
| `tests/tdd/test_issue_747_dated_snapshot.py` | Referenz-Testmuster: _make_segment_weather() Helper |

## Existing Patterns
- Ordinal-Mapping für ThunderLevel: `{ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}` (weather_change_detection.py)
- Segment-Matching per `segment_id` auf `TripSegment`
- `@dataclass` für DTOs (models.py-Stil)

## Dependencies
- Upstream: `SegmentWeatherData` (models.py), ThunderLevel/PrecipType Enums
- Downstream: F3 #749 (Renderer), F4 #750 (Scheduler) — noch nicht implementiert

## Important Finding
ThunderLevel hat NUR 3 Werte: NONE, MED, HIGH — kein LOW. Issue-Text nennt "LOW", meint aber den Enum-Wert MED.

## New Files
- `src/services/day_comparison.py` (NEU)
- `tests/tdd/test_day_comparison_service.py` (NEU)
