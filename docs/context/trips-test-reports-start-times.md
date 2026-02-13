# Context: Trips Test Reports + Stage Start Times

## Request Summary
1. Auf /trips Testberichte (Morning/Evening) per Button versenden
2. Pro Etappe nicht nur Datum, sondern auch Startzeit eingeben

## Related Files

| File | Relevance |
|------|-----------|
| `src/web/pages/trips.py` | Trip-UI, Edit/New Dialog, Stage-Datum-Input |
| `src/web/pages/report_config.py` | Report-Einstellungen Dialog (Zeitplan, Kanaele) |
| `src/services/trip_report_scheduler.py` | `_send_trip_report(trip, report_type)` - Pipeline |
| `src/formatters/trip_report.py` | HTML/Plaintext Formatter |
| `src/outputs/email.py` | SMTP Versand mit Retry |
| `src/app/trip.py` | Trip/Stage/Waypoint Datenmodell |
| `src/app/loader.py` | Trip JSON laden/speichern |
| `src/app/models.py` | TripSegment, TripReportConfig DTOs |

## Ist-Zustand

### Test-Reports
- Kein "Testbericht senden" Button existiert
- "Reports" Button oeffnet report_config.py (Zeitplan-Einstellungen)
- `TripReportSchedulerService._send_trip_report(trip, type)` orchestriert Pipeline
- Pipeline: Trip → Segments → Weather Fetch → Format → Email

### Stage Start Time
- Stage hat nur `date: date` (kein time)
- Startzeit implizit in erstem Waypoint `time_window.start`
- UI: "Datum (YYYY-MM-DD)" Text-Input, kein Time-Picker
- GPX-Import hat `start_hour` Picker (0-23), setzt time_windows

## Existing Patterns
- Factory Pattern fuer alle Buttons (Safari-Kompatibilitaet)
- Dialoge nutzen `ui.dialog()` + `ui.card()` + ScrollArea
- Trip-Daten als JSON in `data/users/default/trips/`
- NiceGUI `ui.time()` fuer Time-Picker (report_config nutzt es bereits)

## Dependencies
- Upstream: OpenMeteo Provider, WeatherMetricsService, WeatherCache
- Downstream: Email Empfaenger, Scheduler (nutzt gleiche _send_trip_report)

## Risks
- Test-Reports koennten bei fehlender SMTP-Config crashen
- Stage-Startzeit muss in alle Waypoint time_windows propagiert werden
- Bestehende Trips ohne Startzeit brauchen Fallback (default 08:00)
