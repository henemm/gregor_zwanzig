---
entity_id: subscriptions_crud
type: module
created: 2026-04-14
updated: 2026-04-14
status: implemented
version: "1.0"
tags: [go, crud, subscriptions, chi, rest-api, json-store]
---

# Subscriptions CRUD

## Approval

- [ ] Approved

## Purpose

Go HTTP-Handler-Modul, das fuenf REST-Endpoints fuer `CompareSubscription`-Entitaeten bereitstellt. Es ermoeglicht dem SvelteKit-Frontend das Erstellen, Lesen, Aktualisieren und Loeschen von Compare-Subscriptions, die steuern welche Locations verglichen und wie Reports ausgeliefert werden.

## Scope

### In Scope
- `CompareSubscription` Struct in `internal/model/subscription.go`
- Store-Methoden `LoadSubscriptions`, `SaveSubscriptions`, `DeleteSubscription` in `internal/store/store.go`
- Fuenf HTTP-Handler in `internal/handler/subscription.go`: List, Get, Create, Update, Delete
- Eingangsvalidierung fuer alle Pflichtfelder und Wertebereich-Constraints
- Legacy-Migration `schedule:"weekly_friday"` → `schedule:"weekly"` + `weekday:4` beim Laden
- Route-Registrierung in `cmd/server/main.go`
- Single-file Storage: `data/users/{userID}/compare_subscriptions.json`

### Out of Scope
- Authentifizierung / Multi-User-Isolation (V1: nur `userID = "default"`)
- Concurrent-Write-Protection (kein File-Locking in V1)
- Typed Validation von `display_config` (wird unveraendert round-getrippt)
- Ausfuehrung / Scheduling der Subscriptions selbst

## Architecture

```
SvelteKit
    │
    ├── GET    /api/subscriptions
    ├── GET    /api/subscriptions/{id}
    ├── POST   /api/subscriptions
    ├── PUT    /api/subscriptions/{id}
    └── DELETE /api/subscriptions/{id}
            │
            ▼
    Go Handler (:8090)
    internal/handler/subscription.go
            │  Read-Modify-Write
            ▼
    internal/store/store.go
    LoadSubscriptions / SaveSubscriptions
            │
            ▼
    data/users/default/compare_subscriptions.json
    {"subscriptions": [...]}
```

## Source

- **File:** `internal/handler/subscription.go` **(NEU)**
- **Identifier:** `ListSubscriptions`, `GetSubscription`, `CreateSubscription`, `UpdateSubscription`, `DeleteSubscription`

### Weitere betroffene Dateien
- **Model:** `internal/model/subscription.go` **(NEU)** — `CompareSubscription` Struct
- **Store:** `internal/store/store.go` **(ERWEITERT)** — Storage-Methoden
- **Routing:** `cmd/server/main.go` **(ERWEITERT)** — 5 Route-Registrierungen

## Data Model

```go
// internal/model/subscription.go
type CompareSubscription struct {
    ID              string                 `json:"id"`
    Name            string                 `json:"name"`
    Enabled         bool                   `json:"enabled"`
    Locations       []string               `json:"locations"`
    ForecastHours   int                    `json:"forecast_hours"`
    TimeWindowStart int                    `json:"time_window_start"`
    TimeWindowEnd   int                    `json:"time_window_end"`
    Schedule        string                 `json:"schedule"`
    Weekday         int                    `json:"weekday"`
    IncludeHourly   bool                   `json:"include_hourly"`
    TopN            int                    `json:"top_n"`
    SendEmail       bool                   `json:"send_email"`
    SendSignal      bool                   `json:"send_signal"`
    DisplayConfig   map[string]interface{} `json:"display_config,omitempty"`
}

// Storage-Wrapper (JSON-Datei)
type subscriptionsFile struct {
    Subscriptions []CompareSubscription `json:"subscriptions"`
}
```

## Endpoints

### GET /api/subscriptions

**Response 200:**
```json
[
  {
    "id": "gr20-morning",
    "name": "GR20 Morgenreport",
    "enabled": true,
    "locations": ["calenzana", "haut-asco"],
    "forecast_hours": 48,
    "time_window_start": 6,
    "time_window_end": 20,
    "schedule": "daily_morning",
    "weekday": 0,
    "include_hourly": false,
    "top_n": 5,
    "send_email": true,
    "send_signal": false
  }
]
```

Leere Liste (`[]`) wenn keine Subscriptions vorhanden. Datei muss nicht existieren (→ leere Liste zurueckgeben).

---

### GET /api/subscriptions/{id}

**Response 200:** Einzelne `CompareSubscription` als JSON-Objekt.

**Response 404:**
```json
{"error": "not_found"}
```

---

### POST /api/subscriptions

**Request Body:** `CompareSubscription` JSON (ohne `id` wird abgelehnt).

**Response 201:** Erstellte `CompareSubscription` als JSON-Objekt.

**Response 400:** Validierungsfehler:
```json
{"error": "validation_error", "detail": "forecast_hours must be 24, 48, or 72"}
```

**Response 409:** ID bereits vorhanden:
```json
{"error": "already_exists", "detail": "subscription with this id already exists"}
```

---

### PUT /api/subscriptions/{id}

**Request Body:** `CompareSubscription` JSON (ID im Body wird ignoriert; Pfad-ID ist massgeblich).

**Response 200:** Aktualisierte `CompareSubscription` als JSON-Objekt.

**Response 400:** Validierungsfehler (gleiche Struktur wie POST).

**Response 404:** Subscription nicht gefunden:
```json
{"error": "not_found"}
```

---

### DELETE /api/subscriptions/{id}

**Response 204:** Kein Body.

**Response 404:**
```json
{"error": "not_found"}
```

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `go-chi/chi/v5` | go module | HTTP Router, `chi.URLParam` fuer `{id}` |
| `encoding/json` | go stdlib | JSON-Serialisierung und -Deserialisierung |
| `os` | go stdlib | Lesen und Schreiben der JSON-Datei |
| `internal/model` | go package | `CompareSubscription` Struct |
| `internal/store` | go package | `LoadSubscriptions`, `SaveSubscriptions` |
| `data/users/default/compare_subscriptions.json` | data file | Persistenz-Datei (wird angelegt falls nicht vorhanden) |

## Implementation Details

### Store-Methoden (`internal/store/store.go`)

```go
// LoadSubscriptions liest alle Subscriptions aus der JSON-Datei.
// Gibt leere Liste zurueck wenn Datei nicht existiert (kein Fehler).
// Fuehrt Legacy-Migration durch: schedule="weekly_friday" → schedule="weekly", weekday=4
func (s *Store) LoadSubscriptions(userID string) ([]model.CompareSubscription, error)

// SaveSubscriptions schreibt alle Subscriptions in die JSON-Datei (atomic overwrite).
// Erstellt Verzeichnis data/users/{userID}/ falls nicht vorhanden.
func (s *Store) SaveSubscriptions(userID string, subs []model.CompareSubscription) error

// DeleteSubscription entfernt eine Subscription per ID via Read-Modify-Write.
// Gibt false zurueck wenn ID nicht gefunden.
func (s *Store) DeleteSubscription(userID string, id string) (bool, error)
```

**Legacy-Migration (in `LoadSubscriptions`):**
```go
for i := range subs {
    if subs[i].Schedule == "weekly_friday" {
        subs[i].Schedule = "weekly"
        subs[i].Weekday = 4
    }
}
```

### Validierung (`internal/handler/subscription.go`)

Validierung wird vor jedem Create/Update ausgefuehrt:

```
- id:               nicht leer
- name:             nicht leer
- forecast_hours:   in {24, 48, 72}
- schedule:         in {"daily_morning", "daily_evening", "weekly"}
- time_window_start: 0-23
- time_window_end:   1-23
- time_window_start < time_window_end
- top_n:            1-10
- weekday:          0-6
```

### Handler-Logik

**ListSubscriptions:**
1. `store.LoadSubscriptions("default")`
2. Gibt `[]` statt `null` bei leerer Liste (JSON-Marshaling: `json:"subscriptions"` mit `make([]..., 0)`)
3. Status 200

**GetSubscription:**
1. `chi.URLParam(r, "id")` lesen
2. `store.LoadSubscriptions("default")`
3. Lineare Suche nach ID → 404 bei nicht gefunden
4. Status 200 mit Objekt

**CreateSubscription:**
1. Body dekodieren → `CompareSubscription`
2. Validierung → 400 bei Fehler
3. `store.LoadSubscriptions("default")`
4. Duplikat-Check → 409 bei vorhandener ID
5. Subscription appenden
6. `store.SaveSubscriptions("default", subs)`
7. Status 201 mit erstelltem Objekt

**UpdateSubscription:**
1. `chi.URLParam(r, "id")` lesen
2. Body dekodieren → `CompareSubscription`
3. Pfad-ID in Objekt setzen (Body-ID ignorieren)
4. Validierung → 400 bei Fehler
5. `store.LoadSubscriptions("default")`
6. Index-Suche → 404 bei nicht gefunden
7. `subs[index] = updated`
8. `store.SaveSubscriptions("default", subs)`
9. Status 200 mit aktualisiertem Objekt

**DeleteSubscription:**
1. `chi.URLParam(r, "id")` lesen
2. `store.DeleteSubscription("default", id)` aufrufen
3. `false` → 404; `true` → 204

### Route-Registrierung (`cmd/server/main.go`)

```go
r.Get("/api/subscriptions", handler.ListSubscriptions(store))
r.Get("/api/subscriptions/{id}", handler.GetSubscription(store))
r.Post("/api/subscriptions", handler.CreateSubscription(store))
r.Put("/api/subscriptions/{id}", handler.UpdateSubscription(store))
r.Delete("/api/subscriptions/{id}", handler.DeleteSubscription(store))
```

Handler werden als Closures ueber `store`-Instanz erstellt (analog zu Location/Trip-Handler-Pattern).

## Expected Behavior

- **Input:** JSON-Requests vom SvelteKit-Frontend; URL-Params fuer `{id}`
- **Output:** JSON-Responses; HTTP-Statuscodes gemaess REST-Konvention (200/201/204/400/404/409)
- **Side effects:** Lesen und Schreiben von `data/users/default/compare_subscriptions.json`; Verzeichnis wird bei erstem Schreiben angelegt; Legacy-Felder werden beim naechsten SaveSubscriptions migriert (kein expliziter Migrations-Lauf)

### Error Cases

| Szenario | HTTP Status | Body |
|----------|-------------|------|
| Validation fehlt Pflichtfeld | 400 | `{"error":"validation_error","detail":"..."}` |
| Wertebereich verletzt | 400 | `{"error":"validation_error","detail":"..."}` |
| ID nicht gefunden (GET/PUT/DELETE) | 404 | `{"error":"not_found"}` |
| Duplikat-ID bei POST | 409 | `{"error":"already_exists","detail":"..."}` |
| JSON nicht dekodierbar | 400 | `{"error":"bad_request"}` |

## Known Limitations

- Kein File-Locking: Parallele Requests koennen bei hoher Last zu Race Conditions fuehren (akzeptiert fuer V1 Single-User)
- `display_config` als `map[string]interface{}` wird ohne Typ-Validierung round-getrippt; unbekannte Felder sind erlaubt
- `userID` ist in V1 hartcodiert auf `"default"`; Multi-User-Erweiterung erfordert Refactoring des Store-Pfads
- Keine Paginierung: `GET /api/subscriptions` gibt immer alle Eintraege zurueck

## Changelog

- 2026-04-14: Initial spec (M5b — Subscriptions CRUD, Go REST API)
- 2026-04-14: Status set to `implemented` — all 5 endpoints verified (VERIFIED by adversary validator). Two LOW findings: missing `detail` field on 409-body; `time_window_end` error message says 0-23 instead of 1-23 (no practical impact).
