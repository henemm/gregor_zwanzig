---
entity_id: alert_config_gaps
type: bugfix
created: 2026-02-10
updated: 2026-02-10
status: done
version: "1.0"
tags: [bugfix, story-3, feature-3.4, alert, config]
---

# Bugfix: Alert Config-Lücken

## Approval

- [x] Approved

## Purpose

Behebt zwei Config-Lücken in Feature 3.4 (Alert bei Änderungen):
1. Alert-Email-Subject steht auf Englisch ("Weather Alert") statt deutsch ("WETTER-ÄNDERUNG") wie in Story 3 Spec definiert
2. `alert_on_changes`-Flag aus TripReportConfig wird nie geprüft — Alerts werden gesendet auch wenn User sie im UI deaktiviert hat

## Source

### Bug A: Englischer Alert-Subject

- **File:** `src/formatters/trip_report.py`
- **Identifier:** `TripReportFormatter._generate_subject()` (Zeile 101)
- **Ist:** `"alert": "Weather Alert"`
- **Soll:** `"alert": "WETTER-ÄNDERUNG"` (Story 3 Spec, Feature 3.4 Acceptance Criteria)

### Bug B: alert_on_changes wird ignoriert

- **File:** `src/services/trip_alert.py`
- **Identifier:** `TripAlertService.check_and_send_alerts()` (Zeile 58-116)
- **Ist:** Prüft nur SMTP-Config und Throttling, nicht `trip.report_config.alert_on_changes`
- **Soll:** Early-Return wenn `trip.report_config` existiert und `alert_on_changes == False`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` | DTO | models.py:380 — enthält `alert_on_changes: bool` |
| `Trip` | Model | trip.py:184 — hat `report_config: Optional[TripReportConfig]` |
| `TripReportFormatter` | Class | Generiert Email-Subject |
| `TripAlertService` | Class | Prüft und sendet Alerts |

## Implementation Details

### Fix A: Subject deutsch (1 Zeile)

```python
# src/formatters/trip_report.py, Zeile 98-102
# ALT:
type_label = {
    "morning": "Morning Report",
    "evening": "Evening Report",
    "alert": "Weather Alert",
}.get(report_type, report_type.title())

# NEU:
type_label = {
    "morning": "Morning Report",
    "evening": "Evening Report",
    "alert": "WETTER-ÄNDERUNG",
}.get(report_type, report_type.title())
```

### Fix B: alert_on_changes prüfen (~5 Zeilen)

```python
# src/services/trip_alert.py, nach Zeile 77 (nach SMTP-Check) einfügen:

# 1b. Check if alerts are disabled for this trip
if trip.report_config and not trip.report_config.alert_on_changes:
    logger.debug(f"Alerts disabled for trip {trip.id}")
    return False
```

Logik:
- `trip.report_config is None` → Alerts AKTIV (Default-Verhalten, kein Config = alles an)
- `trip.report_config.alert_on_changes == True` → Alerts AKTIV
- `trip.report_config.alert_on_changes == False` → Alerts DEAKTIVIERT, early return

## Expected Behavior

### Bug A:
- **Input:** `report_type="alert"`, `trip_name="GR20 Etappe 3"`, Datum 10.02.2026
- **Output (vorher):** `[GR20 Etappe 3] Weather Alert - 10.02.2026`
- **Output (nachher):** `[GR20 Etappe 3] WETTER-ÄNDERUNG - 10.02.2026`

### Bug B:
- **Input:** Trip mit `report_config.alert_on_changes = False`, signifikante Wetter-Änderung
- **Output (vorher):** Alert-Email wird trotzdem gesendet
- **Output (nachher):** `return False`, keine Email, Debug-Log "Alerts disabled for trip X"

## Tests

### Neuer Test: Alert-Subject deutsch
```python
# tests/integration/test_trip_alert.py
def test_alert_subject_is_german():
    """Alert subject must use German 'WETTER-ÄNDERUNG'."""
    formatter = TripReportFormatter()
    report = formatter.format_email(segments, "TestTrip", "alert")
    assert "WETTER-ÄNDERUNG" in report.email_subject
    assert "Weather Alert" not in report.email_subject
```

### Neuer Test: alert_on_changes respektiert
```python
# tests/integration/test_trip_alert.py
def test_alerts_disabled_returns_false():
    """Should not send alert when alert_on_changes is False."""
    service = TripAlertService()
    trip = _create_test_trip()
    trip.report_config = TripReportConfig(
        trip_id=trip.id, alert_on_changes=False
    )
    result = service.check_and_send_alerts(trip, cached_weather)
    assert result is False
```

## Scope

- **Dateien geändert:** 2 (`trip_report.py`, `trip_alert.py`)
- **Dateien für Tests:** 1 (`test_trip_alert.py`)
- **LoC Änderungen:** ~8 (Produktion) + ~20 (Tests)
- **Keine Seiteneffekte** außerhalb der genannten Dateien

## Known Limitations

- Keine: Einfacher, isolierter Bugfix

## Changelog

- 2026-02-10: Initial spec created
