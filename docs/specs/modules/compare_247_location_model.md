---
entity_id: compare_247_location_model
type: module
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
issue: 247
tags: [compare, go, location, model, crud]
---

# Issue #247 — Location-Datenmodell Erweiterung (EPIC 2 #246)

## Approval

- [x] Approved

## Purpose

Erweitert das bestehende `Location`-Go-Struct um drei Felder, die die Compare-Engine (Issue #250) und der Smart-Import (Issue #248) benötigen: `CreatedAt *time.Time` (wird automatisch beim POST gesetzt), `Timezone string` und `DataSource string`. Das Basis-CRUD (4 Endpoints, Store-Methoden, Router-Registrierung) ist bereits vollständig implementiert — diese Spec deckt ausschließlich die additive Modell-Erweiterung sowie die Handler-Anpassungen für verlustfreies `CreatedAt`-Handling ab.

## Source

- **EDIT:** `internal/model/location.go` — 3 neue Felder im `Location`-Struct + `import "time"`
- **EDIT:** `internal/handler/location.go` — `CreateLocationHandler`: `CreatedAt` auto-setzen; `UpdateLocationHandler`: `CreatedAt` aus `existing` übernehmen
- **EDIT:** `internal/store/store_location_write_test.go` — 2 neue Testfälle (Roundtrip neue Felder + Legacy-Kompatibilität)
- **EDIT:** `internal/handler/location_write_test.go` — 2 neue Testfälle (CreatedAt auto-gesetzt, Timezone/DataSource Roundtrip)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Location` Go-Struct (`internal/model/location.go`) | intern | Trägt die 3 neuen Felder; `*time.Time` + `omitempty` sichert Backward-Compatibility mit bestehenden JSON-Dateien |
| `CreateLocationHandler` (`internal/handler/location.go`) | intern | Setzt `CreatedAt` automatisch auf `time.Now().UTC()` nach Validierung, vor `SaveLocation()` |
| `UpdateLocationHandler` (`internal/handler/location.go`) | intern | Übernimmt `CreatedAt` aus dem geladenen `existing`-Objekt per Read-Modify-Write — verhindert Datenverlust beim PUT |
| `SaveLocation()` / `LoadLocation()` (`internal/store/store.go`) | intern | Store-Methoden bleiben unverändert — Full-JSON-Replace; neue Struct-Felder werden automatisch persistiert/geladen |
| `store_location_write_test.go` (`internal/store/`) | intern | Bestehende Store-Tests; erhalten 2 neue Fälle für Roundtrip der neuen Felder |
| `location_write_test.go` (`internal/handler/`) | intern | Bestehende Handler-Tests; erhalten 2 neue Fälle für CreatedAt-Auto-Setzung und Timezone/DataSource-Roundtrip |
| `time` (Go-Stdlib) | extern | `time.Now().UTC()` in `CreateLocationHandler`; `*time.Time`-Typ im Struct |

## Implementation Details

### §1 `internal/model/location.go` — Struct erweitern

`import "time"` ergänzen (falls noch nicht vorhanden). Drei neue Felder am Ende des Structs, nach `DisplayConfig`:

```go
Timezone   string     `json:"timezone,omitempty"`
DataSource string     `json:"data_source,omitempty"`
CreatedAt  *time.Time `json:"created_at,omitempty"`
```

`CreatedAt` ist zwingend `*time.Time` mit `omitempty`: `encoding/json` unterdrückt den Zero-Value von `time.Time` nicht — ohne Pointer würde `0001-01-01T00:00:00Z` in bestehende Location-JSONs geschrieben. Pattern identisch zu `Trip.PausedAt`. `Timezone` und `DataSource` als plain `string` mit `omitempty` — leerer String wird im JSON weggelassen, Bestandsdaten bleiben sauber.

### §2 `internal/handler/location.go` — CreateLocationHandler

Nach der Validierung (Name/Lat/Lon), vor dem Aufruf von `s.SaveLocation(loc)`:

```go
now := time.Now().UTC()
loc.CreatedAt = &now
```

Kein Request-Body-Feld für `CreatedAt` — der Client kann diesen Wert nicht überschreiben. Der Timestamp ist server-seitig kanonisch.

### §3 `internal/handler/location.go` — UpdateLocationHandler

Das bestehende Read-Modify-Write-Muster (erst `LoadLocation`, dann Merge, dann `SaveLocation`) wird um eine Zeile ergänzt — direkt nach dem Laden von `existing`, vor dem Speichern:

```go
loc.CreatedAt = existing.CreatedAt
```

Diese eine Zeile stellt sicher, dass `CreatedAt` bei jedem PUT erhalten bleibt, unabhängig davon, ob der Client das Feld mitschickt oder nicht. `Timezone` und `DataSource` werden hingegen aus dem Request-Body übernommen (Client darf sie setzen/aktualisieren) — kein gesondertes Merge nötig, da sie im Struct direkt per JSON-Decode landen.

### §4 `internal/store/store_location_write_test.go` — 2 neue Tests

**Test 1 — Roundtrip neue Felder:** Erstellt eine Location mit `Timezone: "Europe/Vienna"`, `DataSource: "icon_d2"` und einem gesetzten `CreatedAt`-Pointer. Speichert via `SaveLocation`, lädt via `LoadLocation`, prüft alle 3 Felder auf korrekte Werte.

**Test 2 — Legacy-Kompatibilität:** Schreibt eine Location-JSON-Datei manuell ohne die 3 neuen Felder (simuliert Bestandsdaten). Lädt via `LoadLocation`, prüft: kein Fehler, `CreatedAt == nil`, `Timezone == ""`, `DataSource == ""`.

### §5 `internal/handler/location_write_test.go` — 2 neue Tests

**Test 1 — CreatedAt auto-gesetzt:** POST mit Name/Lat/Lon (ohne `created_at`). Prüft, dass die Response ein nicht-nil `created_at` enthält und der Zeitstempel innerhalb der letzten 5 Sekunden liegt.

**Test 2 — Timezone/DataSource Roundtrip:** POST mit `timezone: "Europe/Berlin"` und `data_source: "dwd_icon"`. GET der erstellten Location. Prüft, dass beide Felder korrekt in der Response erscheinen.

### §6 LoC-Schätzung

| Datei | Änderung | LoC |
|-------|----------|-----|
| `internal/model/location.go` | 3 neue Struct-Felder + import | +4 |
| `internal/handler/location.go` | 2 Zeilen CreateHandler + 1 Zeile UpdateHandler | +3 |
| `internal/store/store_location_write_test.go` | 2 neue Testfälle | ~+35 |
| `internal/handler/location_write_test.go` | 2 neue Testfälle | ~+40 |
| **Summe** | | **~82 LoC** |

Kein LoC-Override nötig (82 LoC << 250-Limit).

## Expected Behavior

- **Input:**
  - POST `/api/locations` mit `name`, `lat`, `lon` (+ optionale Felder `timezone`, `data_source`): Handler setzt `CreatedAt` server-seitig.
  - PUT `/api/locations/{id}` mit beliebigem Body: Handler übernimmt `CreatedAt` aus dem gespeicherten Datensatz — Client-seitiger `created_at`-Wert im Body wird ignoriert/überschrieben.
  - Bestehende Location-JSON-Datei ohne die 3 neuen Felder: `LoadLocation` gibt eine Location mit `CreatedAt == nil`, `Timezone == ""`, `DataSource == ""` zurück — kein Fehler.

- **Output:**
  - GET `/api/locations/{id}` nach POST: Response enthält `"created_at"` als RFC3339-Timestamp (UTC), optional `"timezone"` und `"data_source"` wenn gesetzt.
  - GET nach PUT: `"created_at"` ist unverändert (gleicher Wert wie nach dem POST).
  - Locations ohne die neuen Felder: `"created_at"`, `"timezone"`, `"data_source"` fehlen im JSON vollständig (durch `omitempty`).

- **Side effects:**
  - Keine Datenmigration nötig — alle 3 Felder sind additiv mit `omitempty`-Tags; bestehende JSON-Dateien werden beim nächsten Schreibzugriff (PUT) nicht um diese Felder ergänzt, wenn sie nicht gesetzt sind.
  - `encoding/json` schreibt `"created_at": null` nicht (Pointer + `omitempty` unterdrückt `nil`-Pointer).

## Acceptance Criteria

- **AC-1:** Given eine neue Location via POST (Name, Lat, Lon) / When der Handler antwortet / Then enthält die Response ein gesetztes `created_at` (nicht null, nicht Zero-Value `0001-01-01T00:00:00Z`), und der Timestamp liegt innerhalb der letzten 5 Sekunden.
  - Test: (populated after /tdd-red)

- **AC-2:** Given eine Location mit `timezone: "Europe/Vienna"` und `data_source: "icon_d2"` via POST / When GET `/api/locations/{id}` aufgerufen wird / Then enthält die Response `"timezone": "Europe/Vienna"` und `"data_source": "icon_d2"`.
  - Test: (populated after /tdd-red)

- **AC-3:** Given eine gespeicherte Location mit gesetztem `created_at` / When sie via PUT aktualisiert wird (ohne `created_at` im Request-Body) / Then bleibt `created_at` im gespeicherten Datensatz unverändert erhalten (der POST-Zeitstempel bleibt kanonisch).
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine bestehende Location-JSON-Datei ohne `created_at`, `timezone`, `data_source` / When sie via `LoadLocation` geladen wird / Then schlägt das Laden nicht fehl, und die fehlenden Felder haben Zero-Values (`nil`, `""`).
  - Test: (populated after /tdd-red)

## Known Limitations

- **Client kann `timezone` und `data_source` per PUT überschreiben:** Diese Felder haben keine server-seitige Canonical-Semantik wie `CreatedAt` — der Smart-Import (#248) und die Compare-Engine (#250) sind die primären Schreiber, ein versehentliches PUT vom Frontend könnte Werte überschreiben. Kein Guard in diesem Scope.
- **Python-Seite liest Location-JSON direkt:** `api/routers/compare.py` liest `data/users/*/locations/*.json` — neue Felder (`timezone`, `data_source`, `created_at`) landen automatisch im JSON und sind ohne Python-seitige Änderung lesbar. Falls Python-Loader (`src/app/loader.py`) explizite Location-Deserialisierung hat, muss er gesondert angepasst werden (nicht Scope dieser Spec).
- **`created_at` ist Server-Zeit (UTC):** Es gibt keine Möglichkeit für den Client, einen eigenen Timestamp zu setzen. Der Wert ist beim PUT unveränderbar — auch bei einem Import-Szenario kann das Ursprungsdatum nicht nachträglich gesetzt werden.

## Changelog

- 2026-05-19: Initial spec — Issue #247 / EPIC 2 #246. Additive Modell-Erweiterung (3 Felder: CreatedAt, Timezone, DataSource), Handler-Anpassungen für CreatedAt-Persistenz (POST auto-setzen, PUT aus existing übernehmen), 4 Testfälle (2 Store + 2 Handler), ~82 LoC. Backward-compatible via Pointer/*string + omitempty.
