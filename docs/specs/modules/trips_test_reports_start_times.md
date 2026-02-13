---
entity_id: trips_test_reports_start_times
type: module
created: 2026-02-12
updated: 2026-02-12
status: draft
version: "1.0"
tags: [trips, reports, ui, start-time, email]
---

# Trips: Test-Reports + Etappen-Startzeit

## Approval

- [ ] Approved

## Purpose

Zwei Erweiterungen der /trips Seite: (1) Test-Report-Buttons zum manuellen Versenden von Morning/Evening Reports pro Trip, (2) Startzeit-Eingabe pro Etappe (bisher nur Datum).

## Source

- **Files:**
  - `src/app/trip.py` (MODIFY) - `start_time` Feld auf Stage
  - `src/app/loader.py` (MODIFY) - Serialisierung start_time
  - `src/web/pages/trips.py` (MODIFY) - Time-Picker + Test-Report-Buttons
  - `src/services/trip_report_scheduler.py` (MODIFY) - Public API + start_time Fallback

## Dependencies

### Upstream Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Trip` / `Stage` | Model | Datenmodell fuer Trips und Etappen |
| `TripReportSchedulerService` | Service | Report-Pipeline (Segments, Weather, Format, Email) |
| `EmailOutput` | Service | SMTP-Versand mit Retry |
| `UnifiedWeatherDisplayConfig` | DTO | Metrik-Konfiguration pro Trip |

### Downstream Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_convert_trip_to_segments()` | Method | Nutzt stage.start_time fuer Segment-Zeiten |
| trips.py UI | WebUI | Zeigt Buttons und Time-Picker |
| Scheduler | Background | Nutzt gleiche Pipeline (keine Aenderung noetig) |

## Implementation Details

### Feature 1: Stage Start Time

#### 1.1 Stage Model: start_time Feld

**Datei:** `src/app/trip.py`, Klasse `Stage` (frozen dataclass)

```python
@dataclass(frozen=True)
class Stage:
    id: str
    name: str
    date: date
    waypoints: List[Waypoint]
    start_time: Optional[time] = None  # NEU: Default None → 08:00 in Business Logic
```

**Begruendung:** Optionales Feld, backward-kompatibel. None wird in der Business Logic als 08:00 interpretiert.

#### 1.2 Loader: Serialisierung

**Datei:** `src/app/loader.py`

**_parse_trip() erweitern (nach Zeile 94):**

```python
# Parse start_time if present
start_time_val = None
if "start_time" in stage_data:
    from datetime import time as _time
    start_time_val = _time.fromisoformat(stage_data["start_time"])

stage = Stage(
    id=stage_data["id"],
    name=stage_data["name"],
    date=date.fromisoformat(stage_data["date"]),
    waypoints=waypoints,
    start_time=start_time_val,
)
```

**_trip_to_dict() erweitern (nach Zeile 494):**

```python
stage_dict = {
    "id": stage.id,
    "name": stage.name,
    "date": stage.date.isoformat(),
    "waypoints": waypoints_data,
}
if stage.start_time is not None:
    stage_dict["start_time"] = stage.start_time.isoformat()
stages_data.append(stage_dict)
```

#### 1.3 UI: Time-Picker

**Datei:** `src/web/pages/trips.py`

Im Stage-Editor (sowohl Add- als auch Edit-Dialog), neben dem Datum-Input:

```python
with ui.row().classes("gap-2 items-end"):
    ui.input("Datum (YYYY-MM-DD)", value=stage["date"]).bind_value(stage, "date").classes("w-40")
    ui.input("Startzeit (HH:MM)", value=stage.get("start_time", "08:00")).bind_value(stage, "start_time").classes("w-28")
```

**Design-Entscheidung:** `ui.input` mit Text statt `ui.time` (NiceGUI Time-Picker), weil:
- Konsistent mit Datum-Input (auch Text)
- Einfacher, kein Popup noetig
- "08:00" als Default-Wert direkt sichtbar

#### 1.4 Segment-Konvertierung: start_time Fallback

**Datei:** `src/services/trip_report_scheduler.py`, Methode `_convert_trip_to_segments()`

**Zeile 311-315 ersetzen (time_window None-Check):**

```python
# Get time windows (use stage.start_time as fallback)
default_start = stage.start_time if stage.start_time else time(8, 0)

if wp1.time_window is None:
    # Fallback: use default_start for first waypoint,
    # skip for later waypoints without time_window
    if i == 0:
        wp1_start = default_start
    else:
        logger.warning(f"Waypoint {wp1.id} missing time_window, skipping")
        continue
else:
    wp1_start = wp1.time_window.start

if wp2.time_window is None:
    logger.warning(f"Waypoint {wp2.id} missing time_window, skipping")
    continue

wp2_start = wp2.time_window.start
```

Dann `wp1.time_window.start` durch `wp1_start` und `wp2.time_window.start` durch `wp2_start` ersetzen.

### Feature 2: Test Report Buttons

#### 2.1 Public API

**Datei:** `src/services/trip_report_scheduler.py`

Neue oeffentliche Methode (nach `send_reports_for_hour`):

```python
def send_test_report(self, trip: "Trip", report_type: str) -> None:
    """
    Send a manual test report for a trip.

    Public wrapper around _send_trip_report for UI-triggered sends.
    Unlike scheduled reports, this ignores date checks and uses
    the first stage of the trip.

    Args:
        trip: Trip object
        report_type: "morning" or "evening"

    Raises:
        ValueError: If report_type is invalid
        Exception: If email sending fails
    """
    if report_type not in ("morning", "evening"):
        raise ValueError(f"Invalid report_type: {report_type}")
    self._send_trip_report(trip, report_type)
```

#### 2.2 UI: Test-Report-Buttons auf Trip-Card

**Datei:** `src/web/pages/trips.py`

Zwei neue Buttons pro Trip-Card (nach "Reports" Button, vor "Edit"):

```python
def make_test_report_handler(trip, report_type: str):
    """Factory: sends test report (Safari-safe)."""
    def do_send():
        ui.notify(f"Sende {report_type} Test-Report...", type="info")
        try:
            from services.trip_report_scheduler import TripReportSchedulerService
            service = TripReportSchedulerService()
            service.send_test_report(trip, report_type)
            ui.notify(f"{report_type.title()} Report gesendet!", type="positive")
        except Exception as e:
            ui.notify(f"Fehler: {e}", type="negative")
    return do_send

# In der Trip-Card:
ui.button("Test Morning", icon="send",
          on_click=make_test_report_handler(trip, "morning"),
).props("flat color=primary size=sm")
ui.button("Test Evening", icon="send",
          on_click=make_test_report_handler(trip, "evening"),
).props("flat color=primary size=sm")
```

**Safari Factory Pattern:** `make_test_report_handler(trip, report_type)` bindet beide Variablen korrekt.

## Expected Behavior

### Stage Start Time: Neue Etappe mit Startzeit
- **Given:** User erstellt neue Etappe mit Datum "2026-03-01" und Startzeit "09:00"
- **When:** Trip gespeichert und geladen
- **Then:** stage.start_time == time(9, 0)

### Stage Start Time: Backward-Kompatibilitaet
- **Given:** Bestehender Trip ohne start_time in JSON
- **When:** Trip geladen
- **Then:** stage.start_time == None (Business Logic nutzt default 08:00)

### Stage Start Time: Segment-Konvertierung mit start_time
- **Given:** Stage mit start_time=09:00, Waypoints ohne time_window
- **When:** _convert_trip_to_segments() aufgerufen
- **Then:** Erstes Segment beginnt um 09:00 UTC

### Stage Start Time: Segment-Konvertierung mit time_window
- **Given:** Stage mit start_time=09:00, Waypoints MIT time_window (08:00)
- **When:** _convert_trip_to_segments() aufgerufen
- **Then:** Waypoint time_window hat Vorrang (08:00), stage.start_time ignoriert

### Test Report: Morning erfolgreich
- **Given:** Trip mit gueltigem Stage fuer heute, SMTP konfiguriert
- **When:** User klickt "Test Morning"
- **Then:** Notification "Morning Report gesendet!", Email empfangen

### Test Report: Evening erfolgreich
- **Given:** Trip mit gueltigem Stage, SMTP konfiguriert
- **When:** User klickt "Test Evening"
- **Then:** Notification "Evening Report gesendet!", Email empfangen

### Test Report: SMTP-Fehler
- **Given:** SMTP nicht konfiguriert oder Server nicht erreichbar
- **When:** User klickt "Test Morning"
- **Then:** Notification "Fehler: [SMTP Fehlermeldung]" (rot)

### Test Report: Kein Stage fuer heute
- **Given:** Trip ohne Stage fuer heutiges Datum
- **When:** User klickt "Test Morning"
- **Then:** Notification mit Fehlermeldung (kein Crash)

## Files to Change

| # | File | Action | LoC |
|---|------|--------|-----|
| 1 | `src/app/trip.py` | MODIFY - start_time Feld auf Stage | ~3 |
| 2 | `src/app/loader.py` | MODIFY - Serialize/deserialize start_time | ~15 |
| 3 | `src/web/pages/trips.py` | MODIFY - Time-Picker + 2 Test-Buttons + Handler | ~50 |
| 4 | `src/services/trip_report_scheduler.py` | MODIFY - Public API + start_time Fallback | ~30 |

**Total:** ~98 LoC, 4 Dateien

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| SMTP-Fehler bei Test-Report | LOW | Exception catchen, Notification zeigen |
| Bestehende Trips ohne start_time | LOW | Optional field, default None → 08:00 |
| Safari Button-Binding | MEDIUM | Factory Pattern (make_test_report_handler) |
| Langer Request bei Test-Report (~10s Weather Fetch) | MEDIUM | "Sende..." Notification vor dem Fetch |
| Stage frozen dataclass | LOW | start_time als optionales Default-Feld am Ende |

## Standards Compliance

- Spec-first workflow (dieses Dokument)
- Safari Factory Pattern fuer alle Buttons
- Keine Mocked Tests
- Backward-kompatibel (start_time optional)

## Changelog

- 2026-02-12: v1.0 - Initial spec: Test-Reports + Stage Start Time
