---
entity_id: user_scoped_store
type: module
created: 2026-04-15
updated: 2026-04-15
status: draft
version: "1.0"
tags: [go, multi-user, store, auth, context, f13]
---

# F13 Phase 1 — User-Scoped Go Store

## Approval

- [ ] Approved

## Purpose

Erweiterung des Go-Stores um eine `WithUser()`-Methode, damit alle 20 HTTP-Handler den userId aus dem Request-Kontext verwenden, anstatt immer `"default"` zu nutzen. Damit bildet dieses Modul die Grundlage fuer echtes Multi-User-Datenzugriffs-Routing im Go-API-Layer, ohne Handler-Signaturen oder `main.go` zu aendern.

## Scope

### In Scope

- `WithUser(userId string) *Store` Methode in `internal/store/store.go`
- UserId-Extraktion per `middleware.UserIDFromContext()` am Anfang jedes Handlers in:
  - `internal/handler/location.go` (4 Handler)
  - `internal/handler/trip.go` (5 Handler)
  - `internal/handler/subscription.go` (5 Handler)
  - `internal/handler/weather_config.go` (6 Handler)
- UserId-Forwarding als `user_id` Query-Parameter in `internal/handler/proxy.go`

### Out of Scope

- Login-UI / Session-Management (F13 Phase 2+)
- Anlegen neuer User-Verzeichnisse oder -Daten
- Aenderungen an `cmd/server/main.go`
- Aenderungen an den Python-Loader-Signaturen (akzeptieren `user_id` bereits)

## Architecture

```
HTTP Request (Cookie: session=<userId>)
    │
    ▼
Auth Middleware
    └── setzt userId in context.Context
            │
            ▼
Handler (z.B. ListLocations)
    s = s.WithUser(middleware.UserIDFromContext(r.Context()))
            │
            ▼
    Store (UserID = userId)
    └── data/users/{userId}/locations.json

Proxy Handler
    └── forwardet ?user_id={userId} an Python (:8000)
            │
            ▼
    Python Loader (user_id=userId)
    └── data/users/{userId}/*.json
```

## Source

- **File:** `internal/store/store.go` **(ERWEITERT)**
- **Identifier:** `WithUser(userId string) *Store`

### Weitere betroffene Dateien

- **File:** `internal/handler/location.go` **(ERWEITERT)** — 4 Handler
- **File:** `internal/handler/trip.go` **(ERWEITERT)** — 5 Handler
- **File:** `internal/handler/subscription.go` **(ERWEITERT)** — 5 Handler
- **File:** `internal/handler/weather_config.go` **(ERWEITERT)** — 6 Handler
- **File:** `internal/handler/proxy.go` **(ERWEITERT)** — userId-Forwarding

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/middleware/auth.go` | go package | `UserIDFromContext()` — liest userId aus `context.Context` |
| `internal/store/store.go` | go package | `Store` Struct — Basis fuer `WithUser()`-Kopie |
| `context` | go stdlib | Zugriff auf Request-Kontext in Handlers |
| `net/http` | go stdlib | `r.Context()` in HTTP-Handlern |
| Python Loader-Funktionen | python module | Akzeptieren `user_id`-Parameter bereits (Default: `"default"`) |

## Implementation Details

### Step 1: `WithUser()` in `internal/store/store.go`

```go
// WithUser gibt eine flache Kopie des Store mit geaenderter UserID zurueck.
// Leerer userId-String ist ein No-op: der originale Store wird unveraendert zurueckgegeben.
// Dadurch bestehen bestehende Tests ohne Kontext weiterhin unveraendert.
func (s *Store) WithUser(userId string) *Store {
    if userId == "" {
        return s
    }
    copy := *s
    copy.UserID = userId
    return &copy
}
```

Voraussetzung: `Store` hat ein exportiertes oder intern gesetztes `UserID string`-Field. Falls es noch nicht existiert, wird es als `UserID string` hinzugefuegt und beim Erstellen des Store in `main.go` mit `cfg.UserID` (Wert: `"default"`) initialisiert.

### Step 2: UserId-Extraktion in jedem Handler

Muster (gleich fuer alle 20 Handler):

```go
func ListLocations(s *store.Store) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        s = s.WithUser(middleware.UserIDFromContext(r.Context()))
        // ... restliche Handler-Logik unveraendert ...
    }
}
```

Die Zeile `s = s.WithUser(...)` wird als **erste Anweisung** im inneren `func(w, r)` Block eingefuegt — vor jedem Zugriff auf `s`.

**Betroffene Handler nach Datei:**

`internal/handler/location.go`:
- `ListLocations`, `GetLocation`, `CreateLocation`, `DeleteLocation`

`internal/handler/trip.go`:
- `ListTrips`, `GetTrip`, `CreateTrip`, `UpdateTrip`, `DeleteTrip`

`internal/handler/subscription.go`:
- `ListSubscriptions`, `GetSubscription`, `CreateSubscription`, `UpdateSubscription`, `DeleteSubscription`

`internal/handler/weather_config.go`:
- Alle 6 vorhandenen Handler

### Step 3: Proxy-Handler userId-Forwarding (`internal/handler/proxy.go`)

Beim Weiterleiten an Python wird `user_id` als Query-Parameter angehaengt:

```go
func ProxyHandler(target string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        userId := middleware.UserIDFromContext(r.Context())

        proxyURL, _ := url.Parse(target)
        q := proxyURL.Query()
        if userId != "" {
            q.Set("user_id", userId)
        }
        proxyURL.RawQuery = q.Encode()

        // ... HTTP-Proxy-Logik mit proxyURL ...
    }
}
```

Leerer `userId` fuegt keinen Parameter hinzu — Python-Default bleibt `"default"`, was identisches Verhalten wie bisher ergibt.

## Expected Behavior

- **Input:** HTTP-Request mit Session-Cookie; Auth Middleware setzt `userId` in Context
- **Output:** Store-Methoden lesen/schreiben unter `data/users/{userId}/`; Proxy-Requests erhalten `?user_id={userId}`
- **Side effects:** Keine strukturellen Aenderungen an Dateiformat oder Response-Schema; bei `userId == ""` (z.B. in Tests ohne Middleware) unveraendertes Verhalten

### Rueckwaertskompatibilitaet

| Szenario | Erwartetes Verhalten |
|----------|----------------------|
| Test-Code erstellt `Store` ohne Context | `WithUser("")` ist No-op → `UserID = "default"` bleibt gesetzt → alle bestehenden Tests bestehen |
| Health-/Status-Endpoints ohne Auth | Verwenden Store nicht → nicht betroffen |
| Proxy-Request ohne userId im Context | Kein `user_id` Query-Param → Python nutzt Default `"default"` |
| Eingeloggter User `"alice"` | Store liest/schreibt `data/users/alice/`; Python erhaelt `?user_id=alice` |

## Known Limitations

- Kein automatisches Anlegen von `data/users/{userId}/`-Verzeichnissen — User-Verzeichnisse muessen existieren (F13 Phase 2 regelt User-Anlage)
- Kein Fallback auf `"default"` wenn `data/users/{userId}/` nicht existiert — fuehrt zu `file not found`-Fehlern fuer unbekannte User
- `WithUser()` erstellt eine flache Kopie des Store — falls `Store` Pointer-Fields mit gemeinsamem Zustand hat, teilen sich Original und Kopie diesen Zustand (akzeptiert fuer V1)
- Concurrent-Write-Protection weiterhin nicht vorhanden (unveraendert aus V1)

## Changelog

- 2026-04-15: Initial spec (F13 Phase 1 — User-Scoped Go Store, GitHub Issue #12)
