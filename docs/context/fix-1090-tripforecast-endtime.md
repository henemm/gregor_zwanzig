# Context: fix-1090-tripforecast-endtime

## Analysis (Quelle: Adversary-Report zu #1005, verifiziert)
### Type
Bug (Regression aus #1005)

### Root Cause
`src/services/trip_forecast.py::_waypoint_time_window` (~Z.188-192): Endzeit des letzten Wegpunkts = `(datetime.combine(stage.date, wp_time) + timedelta(hours=2)).time()` — `.time()` verwirft Datumsüberlauf. Bei `wp_time >= 22:00` → `end < start` (invertiertes Fenster) → ungeprüft an Provider → GeoSphere-Fehler/leere Daten → CLI exit 1.

### Referenz (Produktivpfad macht es richtig)
`trip_segments.py:~231` volle Datetime-Arithmetik + `if end_dt <= start_dt: continue`-Guard (~166-177).

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| src/services/trip_forecast.py | MODIFY | Endzeit als volles Datetime rechnen (kein .time()-Truncate) + end<=start-Guard/Fallback |
| tests/tdd/test_issue_1090_trip_forecast_endtime.py | CREATE | Endzeit-Abdeckung: Spät-Ankunft >=22:00, letzter WP, end>start-Invariante |

### Scope / Risk
Backend, 1 src + 1 test, ~+25 LoC. Risk: LOW-MEDIUM (Legacy-CLI, aber Absturz).
