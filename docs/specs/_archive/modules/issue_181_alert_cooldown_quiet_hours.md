---
entity_id: issue_181_alert_cooldown_quiet_hours
type: module
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
issue: 181
tags: [alerts, frontend, backend, trip-model, cooldown, quiet-hours, issue-181, epic-139]
---

# Issue #181 — Alert-Konfigurator: Cooldown + Stille Stunden

## Approval

- [ ] Approved

## Purpose

Nutzer können heute nicht konfigurieren, wie oft und zu welchen Zeiten Alert-E-Mails gesendet werden — der Python-Alert-Service verwendet einen globalen `throttle_hours=2`-Default, der für alle Trips gilt. Dieses Feature führt zwei neue, per Trip individuell konfigurierbare Parameter ein: einen **Cooldown** (Mindestabstand in Minuten zwischen zwei Alerts, 0 = kein Limit) und **Stille Stunden** (Zeitfenster "HH:MM"–"HH:MM", in dem keine Alerts gesendet werden, inkl. korrektem Mitternacht-Wrap). Beide Parameter werden im Trip-Datenmodell (Go + Python) als optionale Felder gespeichert und im Frontend über zwei neue Svelte-Karten in der Alerts-Tab-Ansicht konfiguriert.

## Source

### Backend (Go)
- **MODIFY:** `internal/model/trip.go` — 3 neue Felder in `Trip`-Struct
- **MODIFY:** `internal/handler/trip.go` — `tripUpdateRequest`-Struct (~Z.148) und `UpdateTripHandler` Read-Modify-Write-Block (~Z.201)

### Backend (Python)
- **MODIFY:** `src/app/trip.py` — `Trip`-Dataclass: 3 neue `Optional`-Felder
- **MODIFY:** `src/app/loader.py` — `_parse_trip()` und `_trip_to_dict()`: neue Felder lesen und serialisieren
- **MODIFY:** `src/services/trip_alert.py` — neue private Methode `_is_quiet_hours(trip, now: datetime) -> bool`; Anpassung von `check_and_send_alerts()` für Cooldown-Override und QuietHours-Check

### Frontend (TypeScript + Svelte)
- **MODIFY:** `frontend/src/lib/types.ts` — `Trip`-Interface: 3 neue optionale Felder
- **NEU:** `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` — Card mit Number-Input für Cooldown-Minuten
- **NEU:** `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` — Card mit zwei Time-Inputs (von/bis) und Aktivierungs-Toggle

### Tests
- **NEU:** `tests/tdd/test_alert_cooldown_quiet.py` — Python-Tests für `_is_quiet_hours()` und Cooldown-Auflösung

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripAlertService.check_and_send_alerts()` | Python-Methode (`src/services/trip_alert.py`) | Einstiegspunkt, der Cooldown und QuietHours vor dem Versand prüft |
| `TripAlertService._is_throttled(trip_id)` | Python-Methode (`src/services/trip_alert.py`) | Bleibt unverändert (Signatur stabil); wird erst nach QuietHours-Check aufgerufen |
| `Trip` | Python-Dataclass (`src/app/trip.py`) | Trägt die 3 neuen Optional-Felder als Single Source of Truth im Python-Layer |
| `_parse_trip()` / `_trip_to_dict()` | Python-Funktionen (`src/app/loader.py`) | Serialisierung/Deserialisierung der neuen Felder; backward-compatible (None wenn fehlt) |
| `Trip` | Go-Struct (`internal/model/trip.go`) | Trägt die 3 neuen Pointer-Felder mit `omitempty` für backward-kompatible JSON-Persistenz |
| `tripUpdateRequest` | Go-Struct (`internal/handler/trip.go`) | Empfängt die 3 neuen Felder vom Frontend-PUT und übergibt sie an den Read-Modify-Write-Handler |
| `PUT /api/trips/{id}` | Go-HTTP-Endpoint | Persistiert die neuen Felder über den bestehenden Update-Handler |
| `Trip.alert_rules: AlertRule[]` | Datenfeld (Go + Python + TS) | Parallel vorhandene Alert-Konfiguration (unberührt von diesem Issue) |

## Implementation Details

### 1. `internal/model/trip.go` — Go-Struct erweitern

3 neue Pointer-Felder mit `omitempty`-Tag, damit Bestandsdaten ohne diese Felder weiterhin fehlerfrei gelesen werden:

```go
AlertCooldownMinutes *int    `json:"alert_cooldown_minutes,omitempty"`
AlertQuietFrom       *string `json:"alert_quiet_from,omitempty"`  // "HH:MM"
AlertQuietTo         *string `json:"alert_quiet_to,omitempty"`    // "HH:MM"
```

Pointer statt Werttyp: `nil` bedeutet "nicht gesetzt" (Fallback auf globalen Default). Kein Migrationsskript nötig — `omitempty` + Pointer ist backward-compatible.

### 2. `internal/handler/trip.go` — Handler erweitern

**`tripUpdateRequest`-Struct** (~Z.148): Die gleichen 3 Felder (Pointer + `omitempty`) hinzufügen.

**`UpdateTripHandler`** (~Z.201): Read-Modify-Write-Muster — das bestehende Trip-Objekt laden, dann die 3 neuen Felder selektiv überschreiben:

```go
if req.AlertCooldownMinutes != nil {
    existing.AlertCooldownMinutes = req.AlertCooldownMinutes
}
if req.AlertQuietFrom != nil {
    existing.AlertQuietFrom = req.AlertQuietFrom
}
if req.AlertQuietTo != nil {
    existing.AlertQuietTo = req.AlertQuietTo
}
```

Pattern ist identisch zu den bestehenden Read-Modify-Write-Blöcken für `alert_rules` und `display_config` im selben Handler.

### 3. `src/app/trip.py` — Python-Dataclass erweitern

3 neue Optional-Felder mit Default `None`:

```python
alert_cooldown_minutes: Optional[int] = None
alert_quiet_from: Optional[str] = None  # "HH:MM"
alert_quiet_to: Optional[str] = None    # "HH:MM"
```

### 4. `src/app/loader.py` — Serialisierung

**`_parse_trip()`**: Die 3 neuen Felder aus dem JSON-Dict lesen (mit `.get(key)` → None wenn fehlt):

```python
alert_cooldown_minutes=data.get("alert_cooldown_minutes"),
alert_quiet_from=data.get("alert_quiet_from"),
alert_quiet_to=data.get("alert_quiet_to"),
```

**`_trip_to_dict()`**: Die 3 neuen Felder serialisieren, aber nur wenn nicht `None` (um Bestandsdaten nicht mit `null`-Feldern zu befüllen):

```python
if trip.alert_cooldown_minutes is not None:
    d["alert_cooldown_minutes"] = trip.alert_cooldown_minutes
if trip.alert_quiet_from is not None:
    d["alert_quiet_from"] = trip.alert_quiet_from
if trip.alert_quiet_to is not None:
    d["alert_quiet_to"] = trip.alert_quiet_to
```

### 5. `src/services/trip_alert.py` — Alert-Logik

**Neue private Hilfsmethode `_is_quiet_hours(trip, now: datetime) -> bool`:**

```python
def _is_quiet_hours(self, trip: Trip, now: datetime) -> bool:
    if not trip.alert_quiet_from or not trip.alert_quiet_to:
        return False
    from_time = datetime.time.fromisoformat(trip.alert_quiet_from)
    to_time   = datetime.time.fromisoformat(trip.alert_quiet_to)
    current   = now.time()
    if from_time > to_time:
        # Mitternacht-Wrap: z.B. 22:00 → 07:00
        return current >= from_time or current < to_time
    else:
        # Normales Fenster: z.B. 08:00 → 22:00
        return from_time <= current < to_time
```

Zeitformat: `datetime.time.fromisoformat("HH:MM")` — kein Sekunden-Teil, kein Offset.

**Anpassung von `check_and_send_alerts()`:**

Reihenfolge der Guards:
1. **QuietHours-Check zuerst** (vor Throttle): `if self._is_quiet_hours(trip, now): return`
2. **Cooldown-Override**: Wenn `trip.alert_cooldown_minutes` gesetzt ist (nicht None), wird dieser Wert anstelle von `self._throttle_hours * 60` für den Throttle-Vergleich verwendet. `alert_cooldown_minutes=0` bedeutet "kein Limit" — der `_is_throttled()`-Aufruf wird übersprungen.

```python
# Cooldown bestimmen
if trip.alert_cooldown_minutes is not None:
    cooldown_minutes = trip.alert_cooldown_minutes
else:
    cooldown_minutes = self._throttle_hours * 60  # globaler Default (120)

# QuietHours-Check (vor Throttle)
if self._is_quiet_hours(trip, now):
    return  # kein Alert während stiller Stunden

# Throttle-Check (0 = kein Limit → überspringen)
if cooldown_minutes > 0 and self._is_throttled(trip.id, cooldown_minutes):
    return
```

`_is_throttled(trip_id)` — Signatur bleibt unverändert; internes Verhalten (Zeitstempel prüfen) wird ggf. auf `cooldown_minutes`-Parameter erweitert, falls nötig. Wenn die Signatur nicht erweiterbar ist, wird der Zeitstempel-Vergleich direkt in `check_and_send_alerts()` inline durchgeführt.

### 6. `frontend/src/lib/types.ts` — Trip-Interface erweitern

```typescript
alert_cooldown_minutes?: number;
alert_quiet_from?: string; // "HH:MM"
alert_quiet_to?: string;   // "HH:MM"
```

### 7. `AlertCooldownCard.svelte` — NEU

Card mit einem Number-Input für den Cooldown-Wert. Input akzeptiert Werte ≥ 0 (Integer). `0` wird als "kein Limit" interpretiert und im Label entsprechend angezeigt ("Kein Limit" statt "0 Minuten"). Die Komponente emittiert `onSave(minutes: number)` wenn der User speichert. Integration in die bestehende Alerts-Tab-Ansicht des Trip-Details als eigener Card-Block.

```typescript
let { cooldown_minutes = $bindable<number | undefined>(undefined) }: {
    cooldown_minutes?: number;
} = $props();
```

Hinweistext: "Globaler Standard: 120 Minuten" wenn `cooldown_minutes === undefined`.

### 8. `AlertQuietHoursCard.svelte` — NEU

Card mit:
- **Aktivierungs-Toggle** (`<input type="checkbox">`) — wenn deaktiviert, werden beide Time-Inputs ausgegraut und der Trip-Save sendet `alert_quiet_from=undefined, alert_quiet_to=undefined`
- **Zwei Time-Inputs** (`<input type="time">`) für Von-Uhrzeit und Bis-Uhrzeit
- **Hinweistext bei Mitternacht-Wrap**: Wenn `von > bis` (z.B. 22:00 → 07:00), zeigt die Card "Stille Stunden über Mitternacht (22:00 bis 07:00 des nächsten Tages)"

```typescript
let {
    quiet_from = $bindable<string | undefined>(undefined),
    quiet_to   = $bindable<string | undefined>(undefined),
}: {
    quiet_from?: string;
    quiet_to?: string;
} = $props();

let enabled = $state(quiet_from !== undefined && quiet_to !== undefined);
```

Browser-native `<input type="time">` liefert bereits "HH:MM"-Format — keine manuelle Formatierung nötig.

### 9. `tests/tdd/test_alert_cooldown_quiet.py` — NEU

Testfälle für `_is_quiet_hours()`:

| Test | Fenster | Jetzt | Erwartetes Ergebnis |
|------|---------|-------|---------------------|
| normales Fenster aktiv | 08:00–22:00 | 15:00 | True (unterdrückt) |
| normales Fenster inaktiv | 08:00–22:00 | 23:00 | False |
| Mitternacht-Wrap aktiv | 22:00–07:00 | 23:30 | True |
| Mitternacht-Wrap inaktiv | 22:00–07:00 | 07:01 | False |
| Grenzwert exakt bei `to` | 22:00–07:00 | 07:00 | False (< to, nicht <=) |
| kein QuietHours-Setting | None/None | beliebig | False |

Testfälle für Cooldown-Auflösung:

| Test | Szenario | Erwartetes Ergebnis |
|------|---------|---------------------|
| Default | `alert_cooldown_minutes=None`, `throttle_hours=2` | Cooldown = 120 Minuten |
| Override | `alert_cooldown_minutes=45` | Cooldown = 45 Minuten |
| Kein Limit | `alert_cooldown_minutes=0` | Throttle-Check wird übersprungen |

Keine Mocks — Tests instanziieren `TripAlertService` mit Test-Fixtures und rufen `_is_quiet_hours()` direkt auf.

## Expected Behavior

- **Input (Python):** `Trip`-Objekt mit optionalen Feldern `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`; `datetime`-Objekt für die aktuelle Zeit
- **Output (Python):** `check_and_send_alerts()` sendet Alert oder unterdrückt ihn (kein Return-Wert, Side-Effect: Alert-E-Mail)
- **Input (Go/Frontend):** PUT-Request mit optionalen JSON-Feldern `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`
- **Output (Go):** Persistiertes Trip-JSON mit den neuen Feldern (nur wenn nicht null)
- **Side effects:**
  - Bestandsdaten (Trips ohne die neuen Felder) werden ohne Crash geladen (`None` / `nil` als Fallback)
  - `alert_cooldown_minutes=0` schaltet den Throttle-Schutz vollständig aus — User bewusst möglich
  - Mitternacht-Wrap: Wenn `quiet_from > quiet_to`, prüft `_is_quiet_hours()` zwei Bereiche: `now >= quiet_from OR now < quiet_to`

## Acceptance Criteria

- **AC-1:** Given ein Trip ohne alert_cooldown_minutes / When der Python Alert-Service prüft ob ein Alert gesendet werden soll / Then wird der globale Default (throttle_hours=2, d.h. 120 Minuten) als Fallback verwendet.
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein Trip mit alert_cooldown_minutes=60 / When der Python Alert-Service 30 Minuten nach dem letzten Alert prüft / Then wird der Alert unterdrückt (60 Minuten noch nicht abgelaufen).
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein Trip mit alert_cooldown_minutes=0 / When der Python Alert-Service prüft / Then wird der Cooldown-Check übersprungen (0 = kein Limit).
  - Test: (populated after /tdd-red)

- **AC-4:** Given ein Trip mit alert_quiet_from="22:00" und alert_quiet_to="07:00" / When der Python Alert-Service um 23:30 Uhr prüft / Then wird der Alert unterdrückt (Stille Stunden aktiv, Mitternacht-Wrap).
  - Test: (populated after /tdd-red)

- **AC-5:** Given ein Trip mit alert_quiet_from="22:00" und alert_quiet_to="07:00" / When der Python Alert-Service um 07:01 Uhr prüft / Then wird der Alert NICHT unterdrückt (Stille Stunden beendet).
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein Trip mit alert_quiet_from="08:00" und alert_quiet_to="22:00" / When der Python Alert-Service um 15:00 Uhr prüft / Then wird der Alert unterdrückt (normales Fenster ohne Mitternacht-Wrap).
  - Test: (populated after /tdd-red)

- **AC-7:** Given der Go-Handler empfängt PUT /api/trips/{id} mit alert_cooldown_minutes=45 / When die Anfrage verarbeitet wird / Then wird das bestehende Trip-Objekt per Read-Modify-Write aktualisiert und das Feld alert_cooldown_minutes=45 persistiert.
  - Test: (populated after /tdd-red)

- **AC-8:** Given ein existierender Trip (Bestandsdaten) ohne alert_cooldown_minutes-Feld in der JSON-Datei / When der Python-Loader diesen Trip lädt / Then wird trip.alert_cooldown_minutes = None gesetzt (kein Crash, backward-compatible).
  - Test: (populated after /tdd-red)

- **AC-9:** Given die AlertCooldownCard im Frontend / When der Nutzer 60 eingibt und speichert / Then wird PUT /api/trips/{id} mit { alert_cooldown_minutes: 60 } gesendet.
  - Test: (populated after /tdd-red)

- **AC-10:** Given die AlertQuietHoursCard im Frontend / When der Nutzer "22:00" und "07:00" eingibt und speichert / Then wird PUT /api/trips/{id} mit { alert_quiet_from: "22:00", alert_quiet_to: "07:00" } gesendet.
  - Test: (populated after /tdd-red)

## Known Limitations

- **`_is_throttled()`-Signatur:** Wenn die interne Signatur von `_is_throttled()` keinen `cooldown_minutes`-Parameter annehmen kann (z.B. weil der Zeitstempel-Store statisch aufgebaut ist), wird der Cooldown-Vergleich inline in `check_and_send_alerts()` durchgeführt — `_is_throttled()` behält seine bestehende Signatur.
- **Zeitzone:** `_is_quiet_hours()` arbeitet auf der `now`-Zeit, die der Aufrufer übergibt. Der Aufrufer ist verantwortlich für die richtige Zeitzone (UTC vs. Lokalzeit). Dokumentation des Aufrufs ist Implementierungsdetail.
- **Kein UI-Schutz gegen `0`-Cooldown:** Ein Nutzer, der 0 eingibt, deaktiviert den Throttle vollständig. Es gibt keinen Frontend-Warnhinweis in diesem Scope.
- **Beide Felder Pflicht für QuietHours:** Wenn nur `alert_quiet_from` gesetzt ist, aber `alert_quiet_to` fehlt (oder umgekehrt), verhält sich `_is_quiet_hours()` wie "nicht konfiguriert" (gibt False zurück). Halbkonfiguration durch das Frontend sollte nicht entstehen (Toggle steuert beide Felder gemeinsam).

## Files to Change

| # | Datei | Schicht | Aktion | LoC (netto) |
|---|-------|---------|--------|-------------|
| 1 | `internal/model/trip.go` | Go-API | MODIFY — 3 neue Pointer-Felder in Trip-Struct | ~5 |
| 2 | `internal/handler/trip.go` | Go-API | MODIFY — tripUpdateRequest + Read-Modify-Write für 3 Felder | ~20 |
| 3 | `src/app/trip.py` | Python | MODIFY — 3 neue Optional-Felder in Trip-Dataclass | ~5 |
| 4 | `src/app/loader.py` | Python | MODIFY — _parse_trip() + _trip_to_dict() für 3 Felder | ~15 |
| 5 | `src/services/trip_alert.py` | Python | MODIFY — _is_quiet_hours() + check_and_send_alerts()-Anpassung | ~30 |
| 6 | `frontend/src/lib/types.ts` | Frontend | MODIFY — Trip-Interface: 3 optionale Felder | ~5 |
| 7 | `frontend/src/lib/components/alerts-tab/AlertCooldownCard.svelte` | Frontend | NEU — Card mit Number-Input für Cooldown | ~50 |
| 8 | `frontend/src/lib/components/alerts-tab/AlertQuietHoursCard.svelte` | Frontend | NEU — Card mit Time-Inputs + Toggle | ~70 |
| 9 | `tests/tdd/test_alert_cooldown_quiet.py` | Python/Test | NEU — 9 Testfälle (_is_quiet_hours + Cooldown) | ~80 |

**Gesamt:** ~280 LoC netto, 9 Dateien (2 neu, 7 geändert)

## Changelog

- 2026-05-18: Initial spec für Issue #181 (Alert-Konfigurator: Cooldown + Stille Stunden). Drei-Schichten-Änderung (Go, Python, Frontend) dokumentiert, Mitternacht-Wrap-Logik explizit spezifiziert, 10 AC-N-Kriterien, Backward-Compatibility via Pointer/Optional-Felder gesichert.
