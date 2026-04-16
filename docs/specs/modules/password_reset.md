---
entity_id: password_reset
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [go, auth, password-reset, f15]
---

# F15 Phase 2 — Password Reset

## Approval

- [ ] Approved

## Purpose

Passwort-Reset-Flow: User gibt Username ein, bekommt einen zeitlich begrenzten Reset-Token. Mit diesem Token kann ein neues Passwort gesetzt werden. Token wird als Datei persistiert (`data/users/{id}/password_reset.json`).

Da die App self-hosted ist und der Admin physischen Zugriff auf den Server hat, wird der Reset-Link vorerst in den Server-Logs ausgegeben statt per E-Mail verschickt. E-Mail-Versand kann spaeter ergaenzt werden.

## Scope

### In Scope

- `POST /api/auth/forgot-password` — Reset-Token generieren + loggen
- `POST /api/auth/reset-password` — Neues Passwort mit Token setzen
- Token-Persistenz in `data/users/{id}/password_reset.json`
- Token-Ablauf nach 30 Minuten
- SvelteKit Forgot-Password-Seite + Reset-Seite

### Out of Scope

- E-Mail-Versand des Reset-Links (spaetere Erweiterung)
- Rate-Limiting fuer Forgot-Password-Requests

## Architecture

```
POST /api/auth/forgot-password {"username": "alice"}
    ├── User existiert? → wenn nicht: 200 (kein Hinweis ob User existiert)
    ├── crypto/rand Token generieren (32 Bytes hex)
    ├── Speichern: data/users/alice/password_reset.json
    │       {"token_hash": bcrypt(token), "expires_at": now+30min}
    ├── Log: "Password reset token for alice: {token}"
    └── 200 {"status": "ok"}

POST /api/auth/reset-password {"username": "alice", "token": "abc123", "new_password": "..."}
    ├── password_reset.json laden
    ├── Abgelaufen? → 400
    ├── bcrypt.CompareHashAndPassword(token_hash, token) → 400
    ├── Neues Passwort bcrypt-hashen
    ├── user.json aktualisieren
    ├── password_reset.json loeschen
    └── 200 {"status": "ok"}
```

## Source

- **File:** `internal/handler/auth.go` **(ERWEITERT)** — ForgotPasswordHandler, ResetPasswordHandler
- **File:** `internal/store/user.go` **(ERWEITERT)** — SaveResetToken, LoadResetToken, DeleteResetToken
- **File:** `internal/model/user.go` **(ERWEITERT)** — PasswordResetToken struct
- **File:** `cmd/server/main.go` **(ERWEITERT)** — Routen
- **File:** `frontend/src/routes/forgot-password/+page.svelte` **(NEU)** — Formular
- **File:** `frontend/src/routes/forgot-password/+page.server.ts` **(NEU)** — Action
- **File:** `frontend/src/routes/reset-password/+page.svelte` **(NEU)** — Formular
- **File:** `frontend/src/routes/reset-password/+page.server.ts` **(NEU)** — Action

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `crypto/rand` | go stdlib | Sicheren Token generieren |
| `encoding/hex` | go stdlib | Token als Hex-String |
| `golang.org/x/crypto/bcrypt` | go external | Token-Hash + Passwort-Hash |
| `time` | go stdlib | Token-Ablaufzeit |

## Implementation Details

### Step 1: PasswordResetToken Model (`internal/model/user.go`, +5 LoC)

```go
type PasswordResetToken struct {
    TokenHash string    `json:"token_hash"`
    ExpiresAt time.Time `json:"expires_at"`
}
```

### Step 2: Store-Methoden (`internal/store/user.go`, +35 LoC)

```go
func (s *Store) SaveResetToken(userId string, token PasswordResetToken) error
func (s *Store) LoadResetToken(userId string) (*PasswordResetToken, error)
func (s *Store) DeleteResetToken(userId string) error
```

Pfad: `data/users/{userId}/password_reset.json`

### Step 3: Handler (`internal/handler/auth.go`, +60 LoC)

**ForgotPasswordHandler(s \*store.Store, bcryptCost int):**
1. Decode `{"username": string}`
2. `s.LoadUser(username)` — wenn nicht gefunden: trotzdem 200 (kein User-Enumeration)
3. Token: `crypto/rand` 32 Bytes → hex
4. Hash: `bcrypt.GenerateFromPassword(token)`
5. `s.SaveResetToken(username, {TokenHash: hash, ExpiresAt: now+30min})`
6. `log.Printf("Password reset link: /reset-password?user=%s&token=%s", username, token)`
7. 200 `{"status": "ok"}`

**ResetPasswordHandler(s \*store.Store, bcryptCost int):**
1. Decode `{"username": string, "token": string, "new_password": string}`
2. Validierung: `new_password` >= 8 Zeichen
3. `s.LoadResetToken(username)` → 400 wenn nicht gefunden
4. Ablauf pruefen: `time.Now().After(token.ExpiresAt)` → 400
5. `bcrypt.CompareHashAndPassword(token.TokenHash, token)` → 400
6. Neues Passwort hashen, User laden, PasswordHash aktualisieren, speichern
7. `s.DeleteResetToken(username)`
8. 200 `{"status": "ok"}`

### Step 4: Routen (`cmd/server/main.go`, +2 LoC)

Beide exempt von AuthMiddleware:
```go
r.Post("/api/auth/forgot-password", handler.ForgotPasswordHandler(s, bcrypt.DefaultCost))
r.Post("/api/auth/reset-password", handler.ResetPasswordHandler(s, bcrypt.DefaultCost))
```

### Step 5: SvelteKit Seiten (je ~20 LoC)

**`/forgot-password`:** Formular mit Username-Feld. Action ruft Go-API auf. Zeigt Erfolgsmeldung.
**`/reset-password`:** Formular mit Token + neues Passwort. Token kommt aus URL-Query oder Eingabefeld.

## Expected Behavior

- **Forgot Password:** Immer 200 (egal ob User existiert) — kein User-Enumeration
- **Reset Password:** 200 bei Erfolg, 400 bei ungueltigem/abgelaufenem Token
- **Token:** 30 Minuten gueltig, einmalig verwendbar (wird nach Reset geloescht)
- **Log:** Reset-Link wird in Server-Logs ausgegeben (self-hosted Admin-Zugriff)

### Fehlerszenarien

| Szenario | HTTP Status | Response |
|----------|-------------|----------|
| Forgot: User existiert nicht | 200 | `{"status": "ok"}` (kein Hinweis!) |
| Reset: Token abgelaufen | 400 | `{"error": "token expired"}` |
| Reset: Token falsch | 400 | `{"error": "invalid token"}` |
| Reset: Passwort zu kurz | 400 | `{"error": "validation failed"}` |
| Reset: Kein Token vorhanden | 400 | `{"error": "invalid token"}` |

## Known Limitations

- Reset-Link nur in Server-Logs (kein E-Mail-Versand in dieser Phase)
- Kein Rate-Limiting fuer forgot-password Requests
- Token wird nicht automatisch bereinigt wenn nicht genutzt (bleibt bis Ablauf als Datei)

## Changelog

- 2026-04-16: Initial spec (F15 Phase 2 — Password Reset, GitHub Issue #53)
