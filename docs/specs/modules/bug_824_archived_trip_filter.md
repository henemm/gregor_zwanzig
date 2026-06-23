---
entity_id: bug_824_archived_trip_filter
type: bugfix
created: 2026-06-23
updated: 2026-06-23
status: draft
version: "1.0"
tags: [trips, archive, scheduler, alert, telegram, email, stage-id, epic-825]
---

<!-- Issue #824 — Archivierte Trips aus Python-Services herausfiltern + Stage-ID-Roundtrip prüfen -->

# Bug #824 — Archivierte Trips filtern + Stage-ID-Roundtrip

## Approval

- [ ] Approved

## Purpose

Archivierte Trips werden vom Python-Backend weiterhin für Briefings, Alerts und
Inbound-Routing (Telegram/E-Mail) berücksichtigt, weil `load_all_trips()` das
`archived_at`-Feld ignoriert. Diese Spec beschreibt den Filter-Fix sowie die
Verifikation des Stage-ID-Roundtrips (Epic #825 Ebene 2), der sicherstellt, dass
gespeicherte Stage-IDs beim PUT nicht verloren gehen und durch neu vergebene IDs
ersetzt werden.

## Source

- **File:** `src/app/loader.py` — `load_all_trips()` (Zeile 944)
- **File:** `src/services/trip_report_scheduler.py` — `_get_active_trips()` (Zeile 275)
- **File:** `src/services/trip_alert.py` — `check_all()` (Zeilen 273, 610)
- **File:** `src/services/inbound_telegram_reader.py` — `_find_active_trip()` (Zeile 284)
- **File:** `src/services/inbound_email_reader.py` — `_find_trip_id()` (Zeile 243)
- **File:** `src/services/trip_command_processor.py` — `_find_trip()` (Zeile 360)
- **File:** `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` — Stage-PUT-Pfad (VERIFY)

## Estimated Scope

- **LoC:** ~40
- **Files:** 7
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/trip.py` — `Trip.archived_at: Optional[str]` | datamodel | Feld existiert bereits (Issue #805), kein Schema-Change nötig |
| `src/app/loader.py` — `load_trip()` | function | Lädt `archived_at` bereits korrekt aus JSON (Zeile 427) |
| Go-Backend `internal/store` — `ArchivedAt` | Go-Modul | Setzt `archived_at` korrekt beim Archivieren; Python-Seite liest es nur |
| `internal/handler` — `ensureStageIDs` | Go-Funktion | Vergibt Stage-IDs nur wenn keine vorhanden; Roundtrip-Verhalten zu prüfen |

## Implementation Details

### 1. `load_all_trips()` — neuer Parameter `include_archived`

```python
def load_all_trips(
    user_id: str = "default",
    include_archived: bool = False,
) -> List[Trip]:
    ...
    trips = []
    for path in trips_dir.glob("*.json"):
        try:
            trip = load_trip(path)
            if not include_archived and trip.archived_at is not None:
                continue
            trips.append(trip)
        except Exception as e:
            ...
```

Alle bisherigen Caller ohne `include_archived`-Argument erben `False` —
kein Breaking Change. Der einzige Caller der archivierten Trips bewusst
laden muss (`shortcode.py` zur Deduplizierung) erhält `include_archived=True`.

### 2. Caller-Anpassungen (alle erhalten Default — keine Code-Änderung nötig)

Folgende Caller rufen `load_all_trips(user_id)` auf ohne den neuen Parameter
zu setzen und bekommen durch den Default automatisch das korrekte Verhalten:

| Datei | Funktion | Zeile |
|-------|----------|-------|
| `src/services/trip_report_scheduler.py` | `_get_active_trips()` | 275 |
| `src/services/trip_alert.py` | `check_all()` | 273 |
| `src/services/trip_alert.py` | Radar-Check-Loop | 610 |
| `src/services/inbound_telegram_reader.py` | `_find_active_trip()` | 284 |
| `src/services/inbound_email_reader.py` | `_find_trip_id()` | 243 |
| `src/services/trip_command_processor.py` | `_find_trip()` | 360 |

Kein Caller muss geändert werden — der Default-Parameter-Mechanismus reicht aus.

### 3. `shortcode.py` — explizit `include_archived=True` setzen

`shortcode.py` Zeile 16 ruft `load_all_trips(user_id)` auf um bestehende
Shortcodes zu deduplizieren. Hier müssen archivierte Trips eingeschlossen
bleiben, damit keine Shortcode-Kollisionen entstehen:

```python
existing = {t.shortcode for t in load_all_trips(user_id, include_archived=True) if t.shortcode}
```

### 4. Stage-ID-Roundtrip (Verifikation `EditStagesPanelNew.svelte`)

Prüfung: Wenn der Frontend-PUT-Handler Stage-Daten sendet, werden die
vorhandenen Stage-IDs aus dem Store übergeben oder werden neue IDs im
Frontend erzeugt?

- Wenn IDs aus dem Store kommen → kein Problem; `ensureStageIDs` im Go-Backend
  erkennt vorhandene IDs und überspringt die Neuvergabe.
- Wenn IDs weggelassen oder leer übergeben werden → `ensureStageIDs` vergibt
  neue UUIDs → Alert-State-Keys zeigen auf veraltete IDs → Alerts feuern
  dauerhaft nicht.

Ergebnis der Verifikation bestimmt ob ein Fix in `EditStagesPanelNew.svelte`
nötig ist. Falls ja: Stage-Objekte beim PUT mit ihrer bestehenden `id` senden.

## Expected Behavior

- **Input:** `load_all_trips("user_id")` ohne Argument
- **Output:** Liste aller Trips bei denen `archived_at is None`
- **Side effects:** Archivierte Trips werden von Scheduler, Alert-Service,
  Telegram-Reader, E-Mail-Reader und Command-Processor nicht mehr verarbeitet.
  Shortcode-Deduplizierung schließt archivierte Trips weiterhin ein.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat zwei Trips (Trip A aktiv, Trip B archiviert mit `archived_at` gesetzt) / When `load_all_trips(user_id)` ohne Parameter aufgerufen wird / Then gibt die Funktion genau einen Trip zurück und Trip B ist nicht enthalten

- **AC-2:** Given ein Nutzer hat einen aktiven und einen archivierten Trip / When `_find_active_trip(user_id)` in `inbound_telegram_reader.py` aufgerufen wird / Then wird nur der aktive Trip zurückgegeben; ein eingehender Telegram-Befehl mit dem Namen des archivierten Trips wird nicht gematcht

- **AC-3:** Given ein Nutzer hat einen aktiven und einen archivierten Trip / When `_get_active_trips(user_id)` im Scheduler für einen Morgen- oder Abend-Report aufgerufen wird / Then enthält die Rückgabeliste nur den aktiven Trip; der archivierte Trip erscheint in keiner Scheduler-Runde

- **AC-4:** Given ein Nutzer hat einen aktiven und einen archivierten Trip / When `TripAlertService.check_all()` für diesen Nutzer aufgerufen wird / Then werden Alert-Checks ausschließlich für den aktiven Trip durchgeführt; für den archivierten Trip werden keine Weather-Requests abgesetzt und keine Alert-Mails versendet

- **AC-5:** Given ein Trip mit mindestens zwei Etappen und gesetzten Stage-IDs in der Datenbank / When der Nutzer die Etappen ohne Änderungen speichert (PUT ohne Modifikationen) / Then sind die Stage-IDs nach dem PUT identisch mit den Stage-IDs vor dem PUT; `ensureStageIDs` vergibt keine neuen UUIDs

- **AC-6:** Given `load_all_trips(user_id, include_archived=True)` / When aufgerufen / Then enthält die Rückgabeliste sowohl aktive als auch archivierte Trips; die Shortcode-Deduplizierung in `shortcode.py` schließt archivierte Trips ein

## Known Limitations

- Archivierte Trips bleiben in der Datenbank erhalten — dieser Fix ist ein reiner
  Lese-Filter, kein Lösch-Mechanismus. Ein explizites Lösch-Feature für archivierte
  Trips ist nicht Teil dieses Scopes.
- Der Stage-ID-Roundtrip-Check (AC-5) deckt nur den PUT-Pfad über
  `EditStagesPanelNew.svelte` ab. Andere Frontend-Komponenten die Etappen
  schreiben (falls vorhanden) sind nicht Teil dieses Scopes.
- `shortcode.py` benötigt `include_archived=True` — wird in dieser Spec
  explizit adressiert, aber falls weitere Caller für Deduplizierungszwecke
  entdeckt werden, müssen diese separat bewertet werden.

## Changelog

- 2026-06-23: Initial spec erstellt — Issue #824, Epic #825
