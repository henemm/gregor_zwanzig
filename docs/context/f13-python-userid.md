# F13 Phase 3: Python user_id Integration

## Analyse-Ergebnis (2026-04-16)

### Ist-Zustand
- Go-Proxy leitet `?user_id=` an Python weiter (Phase 1)
- Python `api/routers/scheduler.py` ignoriert den Parameter
- Alle Loader-Calls nutzen Default `user_id="default"`
- Services (`TripReportSchedulerService`, `TripAlertService`) hardcoden "default"
- `TripAlertService.THROTTLE_FILE` hardcoded auf `data/users/default/alert_throttle.json`

### Soll-Zustand
- Scheduler-Endpoints lesen `user_id` aus Query-Param
- Loader-Calls erhalten `user_id`
- Services akzeptieren `user_id` Parameter

### Betroffene Dateien

| Datei | Änderung | LoC |
|-------|----------|-----|
| `api/routers/scheduler.py` | `user_id` Query-Param lesen, an Loader/Services weitergeben | ~20 |
| `src/services/trip_report_scheduler.py` | `user_id` Parameter in `__init__` und `send_reports_for_hour` | ~10 |
| `src/services/trip_alert.py` | `user_id` Parameter, THROTTLE_FILE dynamisch | ~10 |

**Gesamt: 3 Dateien, ~40 LoC**
