---
entity_id: user_profile_channels
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [go, multi-user, profile, channels, f13]
---

# F13 Phase 4a — User-Profil mit Channel-Einstellungen

## Approval

- [ ] Approved

## Purpose

Erweitert das Go User-Model um individuelle Channel-Einstellungen (E-Mail-Empfaenger, Signal, Telegram) und stellt API-Endpoints bereit, um das eigene Profil zu lesen und zu aktualisieren. Registration erstellt zusaetzlich die User-Verzeichnisstruktur. Damit kann jeder User seine eigene Empfaenger-Adresse und Messaging-Konfiguration haben.

## Scope

### In Scope

- `internal/model/user.go` — Channel-Felder im User-Struct
- `internal/handler/auth.go` — `GET/PUT /api/auth/profile` Endpoints + Verzeichnis-Provisioning bei Register
- `internal/store/user.go` — `ProvisionUserDirs` Methode
- `cmd/server/main.go` — Route-Registrierung

### Out of Scope

- Python-Services lesen Channel-Settings aus user.json (Phase 4b)
- SvelteKit UI fuer Profil-Bearbeitung
- Aenderungen an bestehenden Output-Channels (email.py, signal.py, telegram.py)

## Architecture

```
GET /api/auth/profile
    │ (Auth-Middleware setzt userId in Context)
    ▼
ProfileHandler
    └── s.LoadUser(userId) → user.json
            └── 200 {id, email, mail_to, signal_phone, telegram_chat_id, ...}
                (password_hash wird NICHT zurueckgegeben)

PUT /api/auth/profile
    │
    ▼
UpdateProfileHandler
    ├── s.LoadUser(userId) → existierenden User laden
    ├── Channel-Felder aus Request-Body uebernehmen
    ├── password_hash bleibt unveraendert
    └── s.SaveUser(updated) → user.json
            └── 200 {id, email, mail_to, ...}

POST /api/auth/register (erweitert)
    └── nach SaveUser: s.ProvisionUserDirs(username)
            └── erstellt locations/, trips/, gpx/, weather_snapshots/
```

## Source

- **File:** `internal/model/user.go` **(ERWEITERT)**
- **File:** `internal/handler/auth.go` **(ERWEITERT)**
- **File:** `internal/store/user.go` **(ERWEITERT)**
- **File:** `cmd/server/main.go` **(ERWEITERT)**

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/middleware` | go package | `UserIDFromContext` fuer Profile-Endpoints |
| `internal/store` | go package | `LoadUser`, `SaveUser`, neues `ProvisionUserDirs` |
| `internal/model` | go package | Erweitertes `User`-Struct |

## Implementation Details

### Step 1: User-Model erweitern (`internal/model/user.go`)

```go
type User struct {
    ID              string    `json:"id"`
    Email           string    `json:"email,omitempty"`
    PasswordHash    string    `json:"password_hash"`
    CreatedAt       time.Time `json:"created_at"`
    MailTo          string    `json:"mail_to,omitempty"`
    SignalPhone     string    `json:"signal_phone,omitempty"`
    SignalAPIKey    string    `json:"signal_api_key,omitempty"`
    TelegramChatID  string    `json:"telegram_chat_id,omitempty"`
}
```

Alle neuen Felder sind `omitempty` — bestehende user.json Dateien ohne diese Felder bleiben valide.

### Step 2: ProvisionUserDirs (`internal/store/user.go`)

```go
func (s *Store) ProvisionUserDirs(id string) error {
    base := s.UserDir(id)
    for _, sub := range []string{"locations", "trips", "gpx", "weather_snapshots"} {
        if err := os.MkdirAll(filepath.Join(base, sub), 0755); err != nil {
            return err
        }
    }
    return nil
}
```

### Step 3: Profile-Endpoints (`internal/handler/auth.go`)

**GetProfileHandler(s \*store.Store) http.HandlerFunc:**
1. `userId := middleware.UserIDFromContext(r.Context())`
2. `s.LoadUser(userId)` → 404 falls nil
3. Response: User-Felder OHNE `password_hash`
4. HTTP 200

**UpdateProfileHandler(s \*store.Store) http.HandlerFunc:**
1. `userId := middleware.UserIDFromContext(r.Context())`
2. `s.LoadUser(userId)` → 404 falls nil
3. Decode JSON-Body mit erlaubten Feldern: `email`, `mail_to`, `signal_phone`, `signal_api_key`, `telegram_chat_id`
4. Uebernehme nur die gesendeten Felder (Partial Update)
5. `password_hash` und `id` bleiben unveraendert
6. `s.SaveUser(updated)`
7. HTTP 200 mit aktualisiertem Profil (ohne password_hash)

**Response-Format** (GET und PUT identisch):
```json
{
    "id": "alice",
    "email": "alice@example.com",
    "mail_to": "alice@example.com",
    "signal_phone": "+43...",
    "telegram_chat_id": "123456",
    "created_at": "2026-04-16T..."
}
```

**RegisterHandler erweitern:**
Nach `s.SaveUser(user)` zusaetzlich `s.ProvisionUserDirs(req.Username)` aufrufen.

### Step 4: Route-Registrierung (`cmd/server/main.go`)

```go
r.Get("/api/auth/profile", handler.GetProfileHandler(s))
r.Put("/api/auth/profile", handler.UpdateProfileHandler(s))
```

Diese Endpoints sind NICHT exempt von AuthMiddleware — nur eingeloggte User koennen ihr Profil sehen/aendern.

## Expected Behavior

- **GET /api/auth/profile:** Gibt eigenes Profil zurueck (200) oder 404 falls User nicht existiert
- **PUT /api/auth/profile:** Aktualisiert Channel-Felder, gibt aktualisiertes Profil zurueck (200)
- **POST /api/auth/register:** Erstellt jetzt zusaetzlich Unterordner fuer den neuen User

### Fehlerszenarien

| Szenario | HTTP Status | Response |
|----------|-------------|----------|
| GET ohne Auth | 401 | `{"error":"unauthorized"}` |
| PUT mit ungueltigem JSON | 400 | `{"error":"invalid request"}` |
| PUT mit `{}` (leeres Objekt) | 200 | Valider No-Op — nichts wird geaendert |
| PUT versucht password_hash zu aendern | Wird ignoriert — Feld nicht aktualisiert |

## Known Limitations

- Kein Passwort-Aenderungs-Endpoint (separates Feature)
- `signal_api_key` wird bewusst NICHT in der Profile-Response zurueckgegeben (Secret) — nur schreibbar via PUT, nicht lesbar via GET
- Keine Validierung von mail_to (E-Mail-Format) oder signal_phone (E.164) — wird in Phase 4b ergaenzt wenn noetig
- Python liest diese Felder noch nicht — das ist Phase 4b

## Changelog

- 2026-04-16: Initial spec (F13 Phase 4a — User-Profil mit Channel-Einstellungen, GitHub Issue #12)
