# F13 Phase 2a: Go User-Store + Auth-Endpoints

## Analyse-Ergebnis (2026-04-15)

### Ist-Zustand
- SvelteKit Login hardcoded `userId = 'default'`, prüft ENV-Credentials
- Go middleware validiert Session-Cookie (HMAC-SHA256), kann aber keine erstellen
- Kein User-Model in Go, kein bcrypt, kein Registration-Endpoint
- `data/users/default/` existiert mit echten Daten

### Architektur-Entscheidung

Minimal vertical slice — keine neuen Packages, folgt bestehendem Pattern:
- `model/user.go` — User struct (wie location.go, trip.go)
- `store/user.go` — LoadUser/SaveUser/UserExists (wie store.go Pattern)
- `handler/auth.go` — RegisterHandler + LoginHandler
- `middleware/auth.go` — SignSession() als Inverse von validateSession()
- `main.go` — Route-Registration + Seed-User beim Start

### Entscheidung: Seed-User

Seed-User wird mit `cfg.UserID` (= "default") als ID angelegt, nicht `cfg.AuthUser` (= "admin").
Grund: Bestehende Daten liegen unter `data/users/default/` — User muss nach Login sofort Zugriff haben.
Passwort kommt aus `cfg.AuthPass` (ENV), wird bcrypt-gehasht gespeichert.

### Betroffene Dateien (5 Go-Source + go.mod)

| Datei | Typ | LoC |
|-------|-----|-----|
| `internal/model/user.go` | NEU | ~15 |
| `internal/store/user.go` | NEU | ~60 |
| `internal/middleware/auth.go` | ERWEITERT | +15 |
| `internal/handler/auth.go` | NEU | ~120 |
| `cmd/server/main.go` | ERWEITERT | +20 |

**Gesamt: ~230 LoC**

### Risiken
1. AuthMiddleware Exemption-Liste wächst — pragmatisch OK, Refactor später
2. bcrypt in Tests langsam — MinCost für Tests verwenden
3. Seed-User: userId = "default" (nicht "admin") — damit bestehende Daten sofort zugänglich
