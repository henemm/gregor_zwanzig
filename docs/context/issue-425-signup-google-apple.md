# Context: Issue #425 — Alternative Signup-Methoden (Google & Apple)

## Request Summary
Nutzer sollen sich neben Benutzername/Passwort auch über Google Sign-In und Apple Sign-In registrieren und anmelden können.

## Bestehende Auth-Architektur

### Session-Mechanismus
- HMAC-signiertes Cookie `gz_session` im Format `{userId}.{timestamp}.{sig}`
- Signierung: `SHA-256 HMAC` mit `GZ_SESSION_SECRET`
- TTL: 86.400 s (24 h)
- Blacklist im Speicher (Logout/Account-Delete)
- **Gleiche Logik in Go (`internal/middleware/auth.go`) und TypeScript (`frontend/src/lib/auth.ts`) — beide müssen synchron bleiben**

### Bestehende Endpunkte (Go-Backend `internal/handler/auth.go`)
| Route | Funktion |
|-------|----------|
| `POST /api/auth/register` | Username + Password, bcrypt |
| `POST /api/auth/login` | Username + Password prüfen, Cookie setzen |
| `POST /api/auth/logout` | Session blacklisten, Cookie löschen |
| `POST /api/auth/forgot-password` | Reset-Token per E-Mail |
| `POST /api/auth/reset-password` | Neues Passwort mit Token setzen |
| `DELETE /api/auth/account` | Account löschen |
| `GET/PUT /api/auth/profile` | Profil lesen/aktualisieren |
| `PUT /api/auth/password` | Passwort ändern |

### User-Modell (`internal/model/user.go`)
```go
type User struct {
    ID             string    // = Username (Primärschlüssel, Pfad data/users/<ID>/)
    Email          string
    PasswordHash   string    // bcrypt; leer bei OAuth-Usern
    CreatedAt      time.Time
    MailTo         string
    SignalPhone    string
    SignalAPIKey   string
    TelegramChatID string
}
```
**Wichtig:** `ID` = Username = Dateipfad. Bei OAuth-Usern brauchen wir eine stabile, eindeutige ID.

### Persistenz
- `data/users/<userId>/user.json` — User-Objekt
- `store.UserExists(id)` / `store.LoadUser(id)` / `store.SaveUser(user)`
- `store.ProvisionUserDirs(id)` — legt Unterordner an (locations, trips, gpx, …)

### Frontend-Auth-Flow
- Login-Seite: `frontend/src/routes/login/+page.svelte` + `+page.server.ts`
- Register-Seite: `frontend/src/routes/register/+page.svelte` + `+page.server.ts`
- Session-Guard: `frontend/src/hooks.server.ts` — alle Routen außer publicPaths sind gesperrt
- Öffentliche Pfade aktuell: `/login`, `/register`, `/logout`, `/forgot-password`, `/reset-password`, `/email-preview-dev`

## Relevante Dateien

| Datei | Relevanz |
|-------|----------|
| `internal/handler/auth.go` | Alle Auth-Handler — hier kommen OAuth-Handler hinzu |
| `internal/middleware/auth.go` | Session-Validierung — Exempt-Liste für OAuth-Callbacks nötig |
| `internal/model/user.go` | User-Struct — OAuthProvider/OAuthSub-Felder nötig |
| `internal/store/user.go` | Persistenz — kein Schema-Change außer neuen Feldern (additive) |
| `internal/config/config.go` | Env-Config — OAuth-Credentials (Client-ID/-Secret) |
| `cmd/server/main.go` | Route-Registrierung — OAuth-Routen eintragen |
| `frontend/src/hooks.server.ts` | OAuth-Callback-Pfad als publicPath eintragen |
| `frontend/src/routes/login/+page.svelte` | Buttons für Google/Apple hinzufügen |
| `frontend/src/routes/register/+page.svelte` | Buttons für Google/Apple hinzufügen |
| `go.mod` | Evtl. OAuth-Lib hinzufügen |

## Technische Entscheidung: Wie OAuth-Login implementieren?

### Optionen

**A) PKCE-Flow selbst implementieren (kein externe Lib)**
- Nur `golang.org/x/oauth2` als Standard-Lib (gut supported, Google-Paket inklusive)
- Callbacks unter `/api/auth/oauth/google/callback` und `/api/auth/oauth/apple/callback`
- State-Parameter: zufälliger Token in Cookie (CSRF-Schutz)
- Nach erfolgreichem OAuth: `SignSession` wie beim normalen Login → `gz_session`-Cookie

**B) Apple Sign-In ist komplexer als Google**
- Apple nutzt OIDC, aber mit eigenem JWT (RS256-signiert von Apple)
- Apple sendet User-Infos (Name, E-Mail) **nur beim ersten Login** per POST (nicht GET)
- Apple-App-ID + Service-ID + Key-ID + Private Key (.p8) nötig
- Ggf. separates Issue für Apple (scope-Risiko)

### Empfehlung
Google zuerst (einfacher), Apple als separates Issue. `golang.org/x/oauth2` ist bereits im Go-Ökosystem Standard.

## User-ID-Strategie bei OAuth
- Google: `google:<sub>` (Sub = stabile Google-User-ID)
- Apple: `apple:<sub>`
- Kein Passwort-Hash nötig (`PasswordHash: ""`)
- E-Mail aus OAuth-Profil setzen (wenn vorhanden)
- `UserExists` prüft gegen die gleiche ID → Idempotent bei wiederholtem Login

## Abhängigkeiten
- **Upstream:** Kein bestehender Code nutzt OAuth
- **Downstream:** Alle routes nach Login (die `userId` aus Session lesen) sind unberührt, da Session-Format gleich bleibt

## Risiken
1. **Apple Sign-In auf Web erfordert JavaScript** (AppleID.auth.signIn() SDK) — Server-side-only reicht nicht
2. **Apple-Credentials teuer/komplex:** Apple Developer Account benötigt, Service-ID anlegen, Private Key generieren
3. **User-ID-Kollision:** Wenn Nutzer sich erst per Username "peter" registriert und dann via Google als "peter" landet — Name muss anders generiert werden (Prefix `google:` schützt davor)
4. **E-Mail-Konflikte:** Gleiche E-Mail-Adresse per Username und per Google → zwei getrennte Accounts (kein Account-Linking in MVP)
5. **Schema-Migration:** Neue Felder (`OAuthProvider`, `OAuthSub`) im User-Struct sind additiv (bestehende Users haben leere Felder — kein Datenverlust)

## Existierende Specs
- `docs/specs/modules/user_auth_endpoints.md` — bestehende Auth-Spec
- `docs/specs/modules/external_validator_auth.md` — Validator-Auth
