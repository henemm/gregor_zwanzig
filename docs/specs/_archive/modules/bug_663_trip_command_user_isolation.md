---
entity_id: bug_663_trip_command_user_isolation
type: module
created: 2026-06-08
updated: 2026-06-08
status: draft
version: "1.0"
tags: [bug, multi-user, trip-commands, mandantentrennung]
---

# Bug #663 — Trip-Command Mandantentrennung im Schreibpfad

## Approval

- [ ] Approved

## Purpose

Verändernde Trip-Befehle (`ruhetag`, `startdatum`, `abbruch`) müssen Trip,
Wetter-Snapshot und Idempotenz-Log **im Verzeichnis des befehlenden Nutzers**
schreiben/löschen. Aktuell ignoriert der gesamte Schreibpfad die `user_id` und
fällt auf `"default"` zurück — ein Cross-User-Datenleck und Datenverlust.

## Source

- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `TripCommandProcessor._apply_ruhetag`, `._shift_start`,
  `._cancel_trip`, `._delete_snapshot`, `._append_command_log`,
  `._is_already_applied`, `._get_command_log_path`

## Estimated Scope

- **LoC:** ~30
- **Files:** 1 (`src/services/trip_command_processor.py`) + 1 Testdatei
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `app.loader.save_trip(trip, user_id)` | function | nutzergetrenntes Speichern |
| `app.loader.get_snapshots_dir(user_id)` | function | nutzergetrennter Snapshot-Pfad |
| `app.loader.get_data_dir(user_id)` | function | nutzergetrenntes command_log.json |
| `InboundMessage.user_id` | field | Quelle der Nutzer-Kennung (existiert) |

## Implementation Details

`process()` besitzt `msg.user_id` und reicht es bereits an `_find_trip` und
`_trigger_report`. Dieselbe `user_id` muss durch die verändernden Handler
gereicht werden:

```
process()
  ├─ _apply_ruhetag(trip, value, command_date, user_id)
  │     ├─ _is_already_applied(trip.id, "ruhetag", command_date, user_id)
  │     ├─ save_trip(new_trip, user_id)
  │     ├─ _delete_snapshot(trip.id, user_id)            # get_snapshots_dir(user_id)
  │     └─ _append_command_log(trip.id, "ruhetag", command_date, user_id)
  ├─ _shift_start(trip, value, user_id)
  │     ├─ save_trip(new_trip, user_id)
  │     └─ _delete_snapshot(trip.id, user_id)
  └─ _cancel_trip(trip, user_id)
        └─ save_trip(new_trip, user_id)

_get_command_log_path(user_id) -> get_data_dir(user_id) / "command_log.json"
```

Default-Argument `user_id="default"` bleibt zur Rückwärtskompatibilität
erhalten (bestehende Aufrufer/Tests ohne user_id bleiben grün).

## Expected Behavior

- **Input:** `InboundMessage` mit `user_id="userA"`, Befehl `ruhetag`/`startdatum`/`abbruch`.
- **Output:** unveränderte Bestätigungs-Antwort (CommandResult).
- **Side effects:** Trip-Datei, Snapshot und command_log werden **ausschließlich**
  unter `data/users/userA/` geschrieben/gelöscht; `data/users/default/` und andere
  Nutzer mit gleicher `trip_id` bleiben unberührt.

## Acceptance Criteria

- **AC-1:** Given Nutzer A und Default-Nutzer haben je einen Trip mit derselben
  `trip_id` und je einen Wetter-Snapshot / When A per Inbound-Message (`user_id="A"`)
  `ruhetag` schickt / Then **nur** As Snapshot ist gelöscht und der Default-Snapshot
  mit gleicher `trip_id` bleibt erhalten.
  - Test: zwei reale Nutzerverzeichnisse anlegen, Snapshot-Dateien vor/nach prüfen.

- **AC-2:** Given Nutzer A hat einen Trip mit zukünftigen Etappen / When A
  `ruhetag` schickt / Then As Trip-Datei unter `data/users/A/trips/` enthält die
  verschobenen Etappen-Daten und unter `data/users/default/trips/` entsteht/ändert
  sich **keine** Trip-Datei.
  - Test: Trip nach Befehl aus As Verzeichnis laden, neue Daten prüfen; Default-Verzeichnis unberührt.

- **AC-3:** Given Nutzer A schickt `startdatum: <Datum>` / When der Befehl
  verarbeitet wird / Then As Trip wird unter `data/users/A/` mit neuem Startdatum
  gespeichert und As Snapshot gelöscht; Default-Nutzer-Daten bleiben unberührt.
  - Test: zwei Nutzer, Startdatum-Verschiebung von A prüfen, Default-Bestand vergleichen.

- **AC-4:** Given Nutzer A hat heute bereits `ruhetag` ausgeführt / When ein
  Default-Nutzer mit gleicher `trip_id` `ruhetag` schickt / Then der Default-Befehl
  wird **nicht** durch As Idempotenz-Log blockiert (Logs sind nutzergetrennt) und
  greift auf den Default-Trip.
  - Test: A loggt ruhetag; Default schickt ruhetag → success (nicht „bereits eingetragen").

- **AC-5:** Given bestehende Aufrufer/Tests ohne explizite `user_id` / When der
  Default-Nutzer Befehle ausführt / Then das Verhalten ist bit-identisch zu vorher
  (Rückwärtskompatibilität via `user_id="default"`-Default).
  - Test: bestehende `test_trip_command_processor.py`-Suite bleibt grün.

## Known Limitations

- Reiner Schreibpfad des `TripCommandProcessor`; read-only Handler
  (`_handle_query`, `_show_status`) reichen `user_id` bereits korrekt durch.

## Changelog

- 2026-06-08: Initial spec created
