# Context: Compare-Backend #247 — Location CRUD

## Request Summary
Issue #247 fordert das `Location`-Entity: Datenmodell, Persistenz und CRUD-API (`GET /api/locations`, `POST`, `PUT /:id`, `DELETE /:id`). Sub-Issue von EPIC 2 (#246, Orts-Vergleich).

## Schlüsselerkenntnis: Fast bereits fertig

**Die gesamte CRUD-Infrastruktur ist schon implementiert.** #247 ist kein Greenfield-Feature, sondern eine **Modell-Erweiterung**.

| Komponente | Status | Datei |
|------------|--------|-------|
| Location-Struct | ✅ vorhanden, **3 Felder fehlen** | `internal/model/location.go` |
| Store CRUD | ✅ vollständig | `internal/store/store.go` |
| HTTP-Handler (4 Stück) | ✅ vollständig | `internal/handler/location.go` |
| Router-Registrierung | ✅ alle 4 Endpoints | `cmd/server/main.go:82–85` |
| Store-Tests | ✅ vorhanden | `internal/store/store_location_write_test.go` |
| Handler-Tests | ✅ vorhanden | `internal/handler/location_write_test.go` |

## Delta: Was noch fehlt

Issue verlangt diese Felder im Modell — sie fehlen im bestehenden `Location`-Struct:

| Feld | Issue-Typ | Aktuell | Aktion |
|------|-----------|---------|--------|
| `CreatedAt` | `time.Time` | nicht vorhanden | hinzufügen, beim POST auto-setzen |
| `Timezone` | `string` | nicht vorhanden | hinzufügen (optional, für Compare-Engine) |
| `DataSource` | `string` | nicht vorhanden | hinzufügen (optional, für Compare-Engine) |
| `ActivityProfile` | `ActivityProfile` (Enum) | `*string` | **nicht ändern** — konsistent mit Subscription |

Bestehende Felder im Modell, die erhalten bleiben müssen:
- `BergfexSlug *string` — für bestehende Location-Daten
- `DisplayConfig map[string]interface{}` — für bestehende Configs
- `Group *string`, `Region *string`, `ElevationM *int` — als Pointer (omitempty)

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/model/location.go` | Struct erweitern (CreatedAt, Timezone, DataSource) |
| `internal/store/store.go` | LoadLocations, LoadLocation, SaveLocation, DeleteLocation — fertig |
| `internal/handler/location.go` | CreateLocationHandler: CreatedAt beim POST setzen |
| `cmd/server/main.go:82–85` | Router — fertig |
| `internal/store/store_location_write_test.go` | Store-Tests — fertig |
| `internal/handler/location_write_test.go` | Handler-Tests — ggf. um neue Felder ergänzen |

## Existing Patterns

- **Store-Pattern:** JSON-Dateien in `data/users/{userID}/locations/{id}.json` — identisch wie Trips
- **ID-Generierung:** `toKebab(name)` wenn ID leer (in `CreateLocationHandler`)
- **ActivityProfile:** wird in Subscription und Location als `*string` gehalten (kein Go-Enum-Typ) — so beibehalten
- **Read-Modify-Write:** In `UpdateLocationHandler` wird erst `LoadLocation` aufgerufen, dann gespeichert — DRY-Pattern

## Dependencies

- **Upstream:** `internal/model`, `internal/store`, `go-chi/chi`
- **Downstream:** 
  - #248 (Smart-Import) — befüllt Location-Modell
  - #250 (Compare-Engine) — liest `DataSource`, `ActivityProfile`, `Timezone`
  - Python-Seite: `api/routers/compare.py` liest JSON-Files aus `data/users/*/locations/`

## Existing Specs

- `docs/specs/modules/go_location_write.md` — Ursprüngliche Spec für CRUD (status: draft, bereits implementiert)
- `docs/specs/modules/generic_locations.md` — Ältere Konzept-Spec
- `docs/specs/modules/sveltekit_locations.md` — Frontend-Spec (nicht Scope dieser Phase)

## Acceptance Criteria aus Issue

- **AC-1:** POST mit Name/Lat/Lon → gespeichert → per GET abrufbar ✅ bereits erfüllt
- **AC-2:** Group-Feld via GET korrekt ✅ bereits erfüllt
- **AC-3:** DELETE → nicht mehr in GET ✅ bereits erfüllt

## Analyse-Ergebnisse (Phase 2)

### Implementierungsplan

**2 Produktionsdateien + 2 Testdateien, ~80 LoC gesamt**

| Datei | Änderung |
|-------|----------|
| `internal/model/location.go` | +`import "time"`, +3 Felder (CreatedAt, Timezone, DataSource) |
| `internal/handler/location.go` | CreatedAt auto-setzen in CreateHandler; CreateAt aus existing in UpdateHandler übernehmen |
| `internal/store/store_location_write_test.go` | 2 neue Tests (Roundtrip neue Felder + Legacy-Kompatibilität) |
| `internal/handler/location_write_test.go` | 2 neue Tests (CreatedAt auto-gesetzt, Timezone/DataSource roundtrip) |

### Kritische Entscheidungen

- **`CreatedAt` → `*time.Time` mit `omitempty`** (nicht `time.Time`): `encoding/json` unterdrückt Zero-Value nur bei Pointer — sonst würde `0001-01-01T00:00:00Z` in bestehende JSONs geschrieben. Pattern: wie `Trip.PausedAt`.
- **UpdateHandler muss `CreatedAt` aus `existing` übernehmen**: Sonst geht es bei PUT verloren, wenn Client es nicht mitschickt. 1-Zeilen-Fix: `loc.CreatedAt = existing.CreatedAt`.
- **`ActivityProfile` bleibt `*string`**: Nicht auf Go-Enum umstellen — Subscription nutzt dasselbe Pattern.

## Risiken & Überlegungen

1. **Daten-Schema-Rework-Pflicht:** `CreatedAt` hinzufügen ist additiv (omitempty) → Bestandsdaten bleiben valide, kein Migration-Script nötig
2. **ActivityProfile als *string:** Nicht auf den Go-Enum-Typ umstellen — würde Subscription-Konsistenz brechen und erfordert Migration
3. **Python-Seite liest Location-JSON direkt:** `api/routers/compare.py` + `app/loader.py` lesen `data/users/*/locations/*.json` — neue Felder landen automatisch im JSON, Python-Loader muss ggf. angepasst werden
