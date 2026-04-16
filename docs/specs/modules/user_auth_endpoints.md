---
entity_id: user_auth_endpoints
type: module
created: 2026-04-15
updated: 2026-04-15
status: draft
version: "1.0"
tags: [go, multi-user, auth, bcrypt, session, register, login, f13]
---

# F13 Phase 2a — Go User-Store + Auth-Endpoints

## Approval

- [ ] Approved

## Purpose

Implementiert User-Registrierung, Login und persistente Speicherung von User-Daten im Go-API-Layer, damit der Service echte passwortbasierte Authentifizierung unabhaengig vom Python-Layer durchfuehren kann. Diese Komponenten bilden die Grundlage fuer Multi-User-Betrieb (F13), indem sie Session-Cookies im gemeinsam genutzten Format `{userId}.{timestamp}.{hmacSig}` ausstellen, das SvelteKit und Go gleichermaassen validieren koennen.

## Scope

### In Scope

- `internal/model/user.go` — neues User-Struct
- `internal/store/user.go` — neue Methoden `UserDir`, `LoadUser`, `SaveUser`, `UserExists`
- `internal/middleware/auth.go` — neue Funktion `SignSession`
- `internal/handler/auth.go` — neue Handler `RegisterHandler` und `LoginHandler`
- `cmd/server/main.go` — Route-Registrierung + Seed-User-Logik beim Startup

### Out of Scope

- Logout-Endpoint (separates Issue)
- Session-Invalidierung / Token-Rotation
- Aenderungen an Python-Layern oder SvelteKit-Authentifizierung
- Anlegen von `locations.json`, `trips.json` etc. fuer neue User

## Architecture

```
POST /api/auth/register
    │
    ▼
RegisterHandler
    ├── Validierung (nicht leer, Laenge, Sonderzeichen)
    ├── s.UserExists(username) → 409 Conflict falls vorhanden
    ├── bcrypt.GenerateFromPassword(password, cost)
    └── s.SaveUser(User{...}) → data/users/{id}/user.json
            └── 201 {"id": username}

POST /api/auth/login
    │
    ▼
LoginHandler
    ├── s.LoadUser(username) → 401 falls nicht gefunden
    ├── bcrypt.CompareHashAndPassword → 401 bei Mismatch
    ├── middleware.SignSession(username, secret)
    └── Set-Cookie: gz_session={token}; HttpOnly; SameSite=Lax; MaxAge=86400
            └── 200 {"id": username}

Startup (main.go)
    └── if !s.UserExists(cfg.UserID) && cfg.AuthPass != ""
            └── bcrypt-Hash + s.SaveUser → Seed-User
```

## Source

- **File:** `internal/handler/auth.go` **(NEU)**
- **Identifier:** `RegisterHandler`, `LoginHandler`

### Weitere betroffene Dateien

- **File:** `internal/model/user.go` **(NEU)** — User-Struct
- **File:** `internal/store/user.go` **(NEU)** — Persistenz-Methoden
- **File:** `internal/middleware/auth.go` **(ERWEITERT)** — `SignSession()`
- **File:** `cmd/server/main.go` **(ERWEITERT)** — Routen + Seed-User

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `golang.org/x/crypto/bcrypt` | go external | Password-Hashing und -Verifikation |
| `crypto/hmac` | go stdlib | HMAC-SHA256 fuer Session-Signatur |
| `crypto/sha256` | go stdlib | Hash-Funktion fuer HMAC |
| `encoding/hex` | go stdlib | Hex-Encoding der HMAC-Signatur |
| `internal/store/store.go` | go package | `Store`-Struct als Receiver fuer neue User-Methoden |
| `internal/middleware/auth.go` | go package | `SignSession()` wird von `LoginHandler` aufgerufen |
| `internal/model/user.go` | go package | `User`-Struct wird in Store-Methoden und Handlern verwendet |
| `net/http` | go stdlib | HTTP-Handler-Signaturen, Cookie-Setzen |
| `encoding/json` | go stdlib | Request-Decoding und Response-Encoding |
| `os` | go stdlib | `MkdirAll`, `WriteFile`, `Stat` fuer Datei-Persistenz |
| `time` | go stdlib | `CreatedAt`-Feld und Session-Timestamp |

## Implementation Details

### Step 1: User-Struct (`internal/model/user.go` — NEU, ~15 LoC)

```go
package model

import "time"

type User struct {
    ID           string    `json:"id"`
    Email        string    `json:"email,omitempty"`
    PasswordHash string    `json:"password_hash"`
    CreatedAt    time.Time `json:"created_at"`
}
```

### Step 2: User-Store-Methoden (`internal/store/user.go` — NEU, ~60 LoC)

`UserDir(id string) string` — gibt `filepath.Join(s.DataDir, "users", id)` zurueck. Verwendet expliziten `id`-Parameter, NICHT `s.UserID` — User-Verzeichnisse sind global, nicht per-session.

`LoadUser(id string) (*model.User, error)` — liest `data/users/{id}/user.json`, deserialisiert JSON. Gibt `nil, nil` zurueck wenn Datei nicht existiert (kein Fehler), damit `LoginHandler` sauber 401 zurueckgeben kann.

`SaveUser(user model.User) error` — `os.MkdirAll(UserDir(user.ID), 0755)` + `os.WriteFile` mit JSON-Serialisierung. Ueberschreibt existierende Datei ohne Fehler.

`UserExists(id string) bool` — `os.Stat(filepath.Join(UserDir(id), "user.json"))` — gibt `true` zurueck wenn kein Fehler.

### Step 3: SignSession (`internal/middleware/auth.go` — ERWEITERT, +15 LoC)

```go
func SignSession(userId, secret string) string {
    ts := time.Now().Unix()
    mac := hmac.New(sha256.New, []byte(secret))
    mac.Write([]byte(fmt.Sprintf("%s:%d", userId, ts)))
    sig := hex.EncodeToString(mac.Sum(nil))
    return fmt.Sprintf("%s.%d.%s", userId, ts, sig)
}
```

Format identisch mit SvelteKit-Session-Validierung. `secret` kommt aus `cfg.SessionSecret`.

### Step 4: Auth-Handler (`internal/handler/auth.go` — NEU, ~120 LoC)

**RegisterHandler(s \*store.Store, bcryptCost int) http.HandlerFunc:**

1. Decode JSON-Body `{"username": string, "password": string}`
2. Validierung: beide nicht leer; `len(username)` zwischen 3 und 50; `len(password)` >= 8
3. `s.UserExists(username)` → HTTP 409 `{"error": "user already exists"}` falls true
4. `bcrypt.GenerateFromPassword([]byte(password), bcryptCost)` → Hash
5. `s.SaveUser(model.User{ID: username, PasswordHash: string(hash), CreatedAt: time.Now()})`
6. HTTP 201 `{"id": username}`
7. Setzt KEINEN Session-Cookie (Register ist nicht dasselbe wie Login)

**LoginHandler(s \*store.Store, secret string) http.HandlerFunc:**

1. Decode JSON-Body `{"username": string, "password": string}`
2. `s.LoadUser(username)` → HTTP 401 `{"error": "invalid credentials"}` falls nil
3. `bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password))` → HTTP 401 bei Fehler
4. `middleware.SignSession(username, secret)` → Cookie-Value
5. Secure-Flag: `true` wenn `r.Header.Get("X-Forwarded-Proto") == "https"` oder `r.TLS != nil`
6. `http.SetCookie(w, &http.Cookie{Name: "gz_session", Value: token, HttpOnly: true, SameSite: http.SameSiteLaxMode, MaxAge: 86400, Path: "/", Secure: secure})`
7. HTTP 200 `{"id": username}`

Alle Fehlerresponses geben bei Authentication-Fehlern immer `"invalid credentials"` zurueck (kein Hinweis ob User existiert oder Passwort falsch).

### Step 5: Route-Registrierung + Seed-User (`cmd/server/main.go` — ERWEITERT, +20 LoC)

Neue Routen:
```go
mux.Handle("/api/auth/register", handler.RegisterHandler(s, bcrypt.DefaultCost))
mux.Handle("/api/auth/login",    handler.LoginHandler(s, cfg.SessionSecret))
```

AuthMiddleware-Exemptionliste erhaelt `/api/auth/register` und `/api/auth/login`.

Seed-User-Logik direkt nach Store-Initialisierung:
```go
if !s.UserExists(cfg.UserID) && cfg.AuthPass != "" {
    hash, _ := bcrypt.GenerateFromPassword([]byte(cfg.AuthPass), bcrypt.DefaultCost)
    s.SaveUser(model.User{
        ID:           cfg.UserID,
        PasswordHash: string(hash),
        CreatedAt:    time.Now(),
    })
}
```

`cfg.UserID` (Wert: `"default"`) wird verwendet, NICHT `cfg.AuthUser` — damit bleiben existierende Daten unter `data/users/default/` zugaenglich.

## Expected Behavior

- **Input (Register):** `POST /api/auth/register` mit JSON `{"username": "alice", "password": "geheim123"}` — kein Auth-Cookie erforderlich
- **Output (Register):** HTTP 201 `{"id": "alice"}` — kein Cookie gesetzt; `data/users/alice/user.json` angelegt
- **Input (Login):** `POST /api/auth/login` mit JSON `{"username": "alice", "password": "geheim123"}`
- **Output (Login):** HTTP 200 `{"id": "alice"}` + `Set-Cookie: gz_session=alice.{ts}.{sig}; HttpOnly; SameSite=Lax; MaxAge=86400; Path=/`
- **Side effects:** Seed-User wird einmalig beim Startup angelegt wenn `cfg.AuthPass` gesetzt und User noch nicht existiert; `data/users/{id}/user.json` wird bei Register angelegt

### Fehlerszenarien

| Szenario | HTTP Status | Response |
|----------|-------------|----------|
| Register: username < 3 Zeichen | 400 | `{"error": "validation failed"}` |
| Register: password < 8 Zeichen | 400 | `{"error": "validation failed"}` |
| Register: User existiert bereits | 409 | `{"error": "user already exists"}` |
| Login: User nicht gefunden | 401 | `{"error": "invalid credentials"}` |
| Login: Falsches Passwort | 401 | `{"error": "invalid credentials"}` |
| Malformed JSON | 400 | `{"error": "invalid request"}` |

## Known Limitations

- `bcryptCost`-Parameter in `RegisterHandler` ist notwendig fuer Tests mit `bcrypt.MinCost` — in Produktion immer `bcrypt.DefaultCost` uebergeben
- AuthMiddleware-Exemptionliste waechst manuell — Refactoring fuer spaetere Phases vorgesehen
- Kein Logout-Endpoint in dieser Phase — Cookie laeuft nach `MaxAge=86400` (24h) ab
- Seed-User-Fehler beim bcrypt werden mit `_` ignoriert — unkritisch da Startup-Logik

## Changelog

- 2026-04-15: Initial spec (F13 Phase 2a — Go User-Store + Auth-Endpoints, GitHub Issue #12)
