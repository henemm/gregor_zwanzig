---
entity_id: trip_command_processor
type: module
created: 2026-02-17
updated: 2026-02-17
status: draft
version: "2.0"
tags: [f6, trip, command, rescheduling, channel-agnostic]
---

# Trip Command Processor

## Approval

- [x] Approved

## Purpose

Channel-agnostischer Befehlsprozessor fuer Remote-Trip-Steuerung per `### key: value` Syntax.
Empfaengt geparste Befehle von beliebigen Inbound-Channels (Email, SMS) und fuehrt Trip-Modifikationen aus.
Sendet Bestaetigungen ueber einen abstrakten Reply-Callback zurueck auf dem gleichen Kanal.

## Source

- **File:** `src/services/trip_command_processor.py` (NEW)
- **Identifier:** `TripCommandProcessor`, `CommandResult`, `InboundMessage`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/trip.py` | module | Trip, Stage Dataclasses |
| `src/app/loader.py` | module | load_all_trips, save_trip, get_snapshots_dir |
| `src/app/config.py` | module | Settings |
| `dataclasses` (stdlib) | module | dataclasses.replace() fuer frozen Stage |
| `json` (stdlib) | module | Lesen/Schreiben command_log.json |

## Architecture

```
InboundMessage (channel-agnostic DTO)
    |
    v
TripCommandProcessor.process(msg: InboundMessage) -> CommandResult
    |
    +-- 1. Parse: _parse_command(msg.body) → (key, value)
    +-- 2. Lookup: _find_trip(msg.trip_name) → Trip
    +-- 3. Validate: _validate_command(key, value, trip)
    +-- 4. Dispatch:
    |       "ruhetag"    → _apply_ruhetag(trip, value, msg.received_at)
    |       "ruhetag: N" → _apply_ruhetag(trip, N, msg.received_at)
    |       "report"     → _trigger_report(trip, value)
    |       "startdatum" → _shift_start(trip, value)
    |       "abbruch"    → _cancel_trip(trip)
    |       unknown      → CommandResult(error="Unbekannter Befehl")
    +-- 5. Persist: save_trip(), delete_snapshot(), append_log()
    +-- 6. Return: CommandResult (mit Bestaetigungs-Text)

Caller (Email/SMS Reader) empfaengt CommandResult
    → sendet Bestaetigung ueber den gleichen Kanal zurueck
```

**Wichtig:** Der Processor sendet NICHT selbst — er gibt ein `CommandResult` mit
Bestaetigungstext zurueck. Der Caller (Channel-Reader) ist fuer den Versand
auf dem Antwort-Kanal verantwortlich.

## Implementation Details

### 1. Datentypen

```python
@dataclass
class InboundMessage:
    """Channel-agnostisches Eingangs-DTO."""
    trip_name: str          # aus Subject/Context extrahiert
    body: str               # roher Nachrichtentext
    sender: str             # Email-Adresse oder Telefonnummer
    channel: str            # "email" oder "sms"
    received_at: datetime   # Empfangszeitpunkt

@dataclass
class StageShift:
    """Einzelne Etappen-Verschiebung fuer Bestaetigung."""
    stage_name: str
    old_date: date
    new_date: date

@dataclass
class CommandResult:
    """Ergebnis der Befehlsverarbeitung."""
    success: bool
    command: str            # kanonischer Key (z.B. "ruhetag")
    confirmation_subject: str  # fuer Email-Subject / SMS-Header
    confirmation_body: str     # konkrete Bestaetigung was passiert ist
    trip_name: str | None = None
    shifts: list[StageShift] | None = None
```

### 2. Command-Syntax: `### key: value`

Angelehnt an das `weather_email_autobot` Projekt. Erste nicht-leere Zeile
des Nachrichtentexts muss dem Format entsprechen:

```python
_COMMAND_PATTERN = re.compile(r"^###\s+(\S+?)(?::\s*(.*))?$")

def _parse_command(body: str) -> tuple[str | None, str | None]:
    """
    Parst erste nicht-leere Zeile nach ### key: value Format.
    Returns (key, value) oder (None, None).
    """
    first_line = next(
        (line.strip() for line in body.splitlines() if line.strip()),
        "",
    )
    match = _COMMAND_PATTERN.match(first_line)
    if not match:
        return None, None
    return match.group(1).lower(), (match.group(2) or "").strip() or None
```

### 3. Command-Whitelist

| Key | Value | Typ | Wirkung |
|-----|-------|-----|---------|
| `ruhetag` | _(leer)_ oder `N` (int) | Trip-Mod | Folge-Etappen +1 (oder +N) Tage verschieben |
| `report` | `morning` / `evening` | Trigger | Sofort Report fuer aktuelle/naechste Etappe senden |
| `startdatum` | `YYYY-MM-DD` | Trip-Mod | Alle Etappen-Dates relativ zum neuen Start verschieben |
| `abbruch` | _(leer)_ | Trip-Mod | Trip report_config.enabled = False setzen |

### 4. Ruhetag-Verschiebung (frozen Stage)

```python
def _apply_ruhetag(
    self,
    trip: Trip,
    value: str | None,
    command_date: date,
) -> CommandResult:
    """
    Verschiebt alle Stages nach command_date um +N Tage (default: 1).
    """
    shift_days = int(value) if value and value.isdigit() else 1

    # Idempotenz-Check
    if self._is_already_applied(trip.id, "ruhetag", command_date):
        return CommandResult(
            success=False,
            command="ruhetag",
            confirmation_subject=f"[{trip.name}] Ruhetag bereits eingetragen",
            confirmation_body=f"Ruhetag wurde heute bereits eingetragen.",
            trip_name=trip.name,
        )

    shifts: list[StageShift] = []
    new_stages: list[Stage] = []

    for stage in trip.stages:
        if stage.date > command_date:
            new_date = stage.date + timedelta(days=shift_days)
            new_stages.append(dataclasses.replace(stage, date=new_date))
            shifts.append(StageShift(stage.name, stage.date, new_date))
        else:
            new_stages.append(stage)

    if not shifts:
        return CommandResult(
            success=False,
            command="ruhetag",
            confirmation_subject=f"[{trip.name}] Keine Etappen",
            confirmation_body="Keine zukuenftigen Etappen zum Verschieben.",
            trip_name=trip.name,
        )

    new_trip = dataclasses.replace(trip, stages=new_stages)
    save_trip(new_trip)
    self._delete_snapshot(trip.id)
    self._append_command_log(trip.id, "ruhetag", command_date)

    # Bestaetigung mit konkreten Details
    tage_wort = "Tag" if shift_days == 1 else "Tage"
    lines = [f"Ruhetag eingetragen: +{shift_days} {tage_wort}.", ""]
    lines.append("Verschobene Etappen:")
    for s in shifts:
        lines.append(
            f"  {s.stage_name}: {s.old_date:%d.%m.%Y} -> {s.new_date:%d.%m.%Y}"
        )
    lines.append("")
    lines.append("Naechster Report kommt planmaessig.")

    return CommandResult(
        success=True,
        command="ruhetag",
        confirmation_subject=f"[{trip.name}] Ruhetag bestaetigt",
        confirmation_body="\n".join(lines),
        trip_name=trip.name,
        shifts=shifts,
    )
```

### 5. Report-Trigger

```python
def _trigger_report(self, trip: Trip, value: str | None) -> CommandResult:
    """Loest sofort einen Morning/Evening Report aus."""
    report_type = value or "morning"
    if report_type not in ("morning", "evening"):
        return CommandResult(
            success=False,
            command="report",
            confirmation_subject=f"[{trip.name}] Ungueltiger Report-Typ",
            confirmation_body=f"Report-Typ '{report_type}' unbekannt. Erlaubt: morning, evening",
            trip_name=trip.name,
        )

    from src.services.trip_report_scheduler import TripReportSchedulerService
    service = TripReportSchedulerService()
    service.send_test_report(trip, report_type)

    return CommandResult(
        success=True,
        command="report",
        confirmation_subject=f"[{trip.name}] Report gesendet",
        confirmation_body=f"{report_type.title()} Report wird jetzt gesendet.",
        trip_name=trip.name,
    )
```

### 6. Startdatum-Verschiebung

```python
def _shift_start(self, trip: Trip, value: str | None) -> CommandResult:
    """Verschiebt alle Etappen relativ zu neuem Startdatum."""
    if not value:
        return CommandResult(
            success=False, command="startdatum",
            confirmation_subject=f"[{trip.name}] Fehlendes Datum",
            confirmation_body="Bitte Datum angeben: ### startdatum: YYYY-MM-DD",
            trip_name=trip.name,
        )
    try:
        new_start = date.fromisoformat(value)
    except ValueError:
        return CommandResult(
            success=False, command="startdatum",
            confirmation_subject=f"[{trip.name}] Ungueltiges Datum",
            confirmation_body=f"'{value}' ist kein gueltiges Datum. Format: YYYY-MM-DD",
            trip_name=trip.name,
        )

    old_start = trip.stages[0].date
    delta = new_start - old_start
    shifts = []
    new_stages = []
    for stage in trip.stages:
        new_date = stage.date + delta
        new_stages.append(dataclasses.replace(stage, date=new_date))
        shifts.append(StageShift(stage.name, stage.date, new_date))

    new_trip = dataclasses.replace(trip, stages=new_stages)
    save_trip(new_trip)
    self._delete_snapshot(trip.id)

    lines = [f"Startdatum verschoben: {old_start:%d.%m.%Y} -> {new_start:%d.%m.%Y}", ""]
    lines.append("Neue Etappen-Daten:")
    for s in shifts:
        lines.append(f"  {s.stage_name}: {s.new_date:%d.%m.%Y}")

    return CommandResult(
        success=True, command="startdatum",
        confirmation_subject=f"[{trip.name}] Startdatum geaendert",
        confirmation_body="\n".join(lines),
        trip_name=trip.name, shifts=shifts,
    )
```

### 7. Trip-Abbruch

```python
def _cancel_trip(self, trip: Trip) -> CommandResult:
    """Deaktiviert Report-Scheduling fuer den Trip."""
    if trip.report_config:
        new_config = dataclasses.replace(trip.report_config, enabled=False)
        new_trip = dataclasses.replace(trip, report_config=new_config)
        save_trip(new_trip)

    return CommandResult(
        success=True, command="abbruch",
        confirmation_subject=f"[{trip.name}] Trip beendet",
        confirmation_body=f"Reports fuer '{trip.name}' deaktiviert. Gute Heimreise!",
        trip_name=trip.name,
    )
```

### 8. Idempotenz-Log

**Datei:** `data/users/default/command_log.json`

```json
[
  {
    "trip_id": "gr221-mallorca",
    "command": "ruhetag",
    "date": "2026-02-17",
    "channel": "email",
    "applied_at": "2026-02-17T08:33:00+00:00"
  }
]
```

Idempotenz gilt nur fuer `ruhetag` (gleicher Trip + gleiches Datum = Duplikat).
`report` und `startdatum` sind idempotent von Natur aus (gleiche Wirkung bei Wiederholung).

### 9. Snapshot-Invalidierung

```python
def _delete_snapshot(self, trip_id: str) -> None:
    snapshot_path = get_snapshots_dir() / f"{trip_id}.json"
    try:
        if snapshot_path.exists():
            snapshot_path.unlink()
            logger.info(f"Snapshot deleted: {snapshot_path}")
    except OSError as e:
        logger.error(f"Failed to delete snapshot {snapshot_path}: {e}")
```

Wird nach `ruhetag` und `startdatum` aufgerufen — beide aendern Stage-Dates.
Nicht nach `report` oder `abbruch` (keine Date-Aenderung).

### 10. Fehler-Antworten

| Situation | confirmation_subject | confirmation_body |
|-----------|---------------------|-------------------|
| Kein `###` Format | `Unbekannter Befehl` | `Befehlsformat: ### key: value\nVerfuegbar: ruhetag, report, startdatum, abbruch` |
| Key nicht in Whitelist | `Unbekannter Befehl` | `'xyz' ist kein gueltiger Befehl.\nVerfuegbar: ruhetag, report, startdatum, abbruch` |
| Ruhetag-Duplikat | `Ruhetag bereits eingetragen` | `Ruhetag wurde heute bereits eingetragen.` |
| Alle Etappen vergangen | `Keine Etappen` | `Keine zukuenftigen Etappen zum Verschieben.` |
| Ungueltiges Datum | `Ungueltiges Datum` | `'xyz' ist kein gueltiges Datum. Format: YYYY-MM-DD` |
| Trip nicht gefunden | _(kein Result)_ | Wird vom Channel-Reader behandelt, nicht vom Processor |

## Expected Behavior

- **Input:** `InboundMessage` (trip_name, body, sender, channel, received_at)
- **Output:** `CommandResult` (success, command, confirmation_subject, confirmation_body, shifts)
- **Side effects (bei Trip-Mod Befehlen):**
  - Datei-Schreibzugriff: `data/users/default/trips/{trip_id}.json`
  - Datei-Loeschzugriff: `data/users/default/weather_snapshots/{trip_id}.json`
  - Datei-Schreibzugriff: `data/users/default/command_log.json`
- **Side effects (bei Report-Trigger):**
  - SMTP Email-Versand (via TripReportSchedulerService)

### Beispiel (GR221 Mallorca, 17.02.2026):

```
Eingang (Email oder SMS):
  ### ruhetag

Verarbeitung:
  T1: 2026-02-16 (Vergangenheit, unveraendert)
  T2: 2026-02-17 (heute, unveraendert)
  T3: 2026-02-18 → 2026-02-19
  T4: 2026-02-19 → 2026-02-20

Bestaetigung (auf gleichem Kanal):
  Subject: [GR221 Mallorca] Ruhetag bestaetigt
  Body:
    Ruhetag eingetragen: +1 Tag.

    Verschobene Etappen:
      Tag 3: 18.02.2026 -> 19.02.2026
      Tag 4: 19.02.2026 -> 20.02.2026

    Naechster Report kommt planmaessig.
```

## Files to Create/Modify

| File | Action | LOC |
|------|--------|-----|
| `src/services/trip_command_processor.py` | NEW | ~200 |

## Testing Strategy

### Integration Tests (No Mocks!)

```python
def test_ruhetag_shifts_future_stages()
def test_ruhetag_with_value_shifts_n_days()
def test_past_stages_unchanged()
def test_idempotency_prevents_double_shift()
def test_snapshot_deleted_after_ruhetag()
def test_all_stages_in_past_returns_error()
def test_unknown_command_returns_help()
def test_startdatum_shifts_all_stages()
def test_startdatum_invalid_date_returns_error()
def test_report_trigger_sends_report()
def test_abbruch_disables_report_config()
def test_parse_command_format()
```

## Known Limitations

- Single-User only (kein Multi-User-Auth)
- Kein Undo-Mechanismus (kein `### resume` Befehl)
- Keine Validierung ob verschobene Dates Konflikte mit anderen Trips erzeugen
- Idempotenz nur fuer `ruhetag` (nicht fuer `startdatum`)

## Error Handling

```python
try:
    result = processor.process(msg)
except Exception as e:
    logger.error(f"Command processing failed for {msg.trip_name}: {e}")
    result = CommandResult(
        success=False, command="error",
        confirmation_subject="Fehler",
        confirmation_body=f"Interner Fehler bei Befehlsverarbeitung.",
    )
```

Kein Fehler darf den APScheduler-Thread zum Absturz bringen.

## Changelog

- 2026-02-17: v2.0 Generisches ### key: value Framework, channel-agnostisch, 4 Befehle
- 2026-02-17: v1.0 Initial spec (nur RUHETAG, Email-only)
