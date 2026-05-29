---
entity_id: google_oauth_login
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [go, sveltekit, auth, oauth, google, issue-425]
---

# Issue #425 — Google OAuth Login

## Approval

- [ ] Approved

## Purpose

Ergänzt das bestehende Username/Passwort-Auth-System um eine Google-Sign-In-Option. Nutzer können sich über den Google Authorization Code Flow einloggen und registrieren, ohne ein separates Passwort anlegen zu müssen — das reduziert Hürden beim Onboarding und ermöglicht passwortloses Konto-Management für Google-Nutzer.

## Scope

### In Scope

- `go.mod` — Abhängigkeit `golang.org/x/oauth2` ergänzen
- `internal/config/config.go` — drei neue ENV-Variablen: `GZ_GOOGLE_CLIENT_ID`, `GZ_GOOGLE_CLIENT_SECRET`, `GZ_GOOGLE_REDIRECT_URL`
- `internal/model/user.go` — Felder `OAuthProvider` und `OAuthSub` (additive, omitempty)
- `internal/store/user.go` — Methode `FindUserByOAuthSub(provider, sub string)`
- `internal/middleware/auth.go` — neue Exempt-Pfade `/api/auth/google/init` und `/api/auth/google/callback`
- `internal/handler/auth.go` — Handler `GoogleOAuthInitHandler` und `GoogleOAuthCallbackHandler`
- `cmd/server/main.go` — zwei neue Routen registrieren
- `frontend/src/lib/auth.ts` — defensiver Fix in `verifySession` (Split auf `.` darf nicht bei `g-3a7f9c12`-IDs brechen)
- `frontend/src/routes/login/+page.svelte` — „Mit Google anmelden"-Button
- `frontend/src/routes/login/+page.server.ts` — `load()`-Funktion mit `googleEnabled`-Flag
- `frontend/src/routes/register/+page.svelte` — „Mit Google registrieren"-Button
- `frontend/src/routes/register/+page.server.ts` — `load()`-Funktion mit `googleEnabled`-Flag

### Out of Scope

- Apple Sign-In (auf Issue #426 verschoben; `OAuthProvider`/`OAuthSub`-Felder sind bereits kompatibel)
- Account-Linking (ein Google-Konto mit bestehendem Passwort-Konto zusammenführen) — in v1 sind separate Konten akzeptiert
- Admin-seitige OAuth-Konto-Verwaltung

## Source

- **Schicht:** Go-Backend (`internal/`) + SvelteKit-Frontend (`frontend/src/routes/`)
- **Datei (neu):** Kein neues File — ausschließlich Ergänzungen in bestehenden Dateien
- **Identifier (Backend):** `GoogleOAuthInitHandler`, `GoogleOAuthCallbackHandler`, `FindUserByOAuthSub`
- **Identifier (Frontend):** `load` (in `+page.server.ts`), `verifySession` (in `auth.ts`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `golang.org/x/oauth2` | Go-Bibliothek (NEU) | Authorization Code Flow: Token-Exchange und OAuth2-Config |
| `golang.org/x/oauth2/google` | Go-Bibliothek (NEU) | Google-spezifischer Endpoint (`google.Endpoint`) |
| `https://www.googleapis.com/oauth2/v3/userinfo` | Externer HTTP-Endpoint | Liefert `sub`, `email`, `name` nach Token-Exchange |
| `internal/store/user.go` | Go-Store (vorhanden, erweitert) | `FindUserByOAuthSub` — User per `OAuthProvider`+`OAuthSub` suchen |
| `internal/model/user.go` | Go-Struct (vorhanden, erweitert) | Neue Felder `OAuthProvider`, `OAuthSub` (omitempty) |
| `internal/config/config.go` | Go-Config (vorhanden, erweitert) | Neue Felder `GoogleClientID`, `GoogleClientSecret`, `GoogleRedirectURL` |
| `internal/middleware/auth.go` | Go-Middleware (vorhanden, erweitert) | Exempt-Pfade für `/api/auth/google/*` |
| `internal/handler/auth.go` | Go-Handler (vorhanden, erweitert) | Bestehende Session-Issuance-Logik wiederverwenden |
| `$env/dynamic/private` | SvelteKit | `GZ_GOOGLE_CLIENT_ID` — Frontend prüft ob Feature aktiv ist |
| `frontend/src/lib/auth.ts` | SvelteKit-Lib (vorhanden, gefixt) | `verifySession` — defensiver Split-Fix für neue User-ID-Präfix `g-` |

## Implementation Details

### Step 1: `internal/model/user.go` — Felder ergänzen (~+4 LoC)

```go
type User struct {
    // ... bestehende Felder unverändert ...
    OAuthProvider string `json:"oauth_provider,omitempty"`
    OAuthSub      string `json:"oauth_sub,omitempty"`
}
```

Bestehende Nutzer sind vollständig unberührt — `omitempty` verhindert Schreibzugriffe auf vorhandene `user.json`-Dateien.

### Step 2: `internal/config/config.go` — ENV-Variablen (~+6 LoC)

```go
GoogleClientID     string // GZ_GOOGLE_CLIENT_ID
GoogleClientSecret string // GZ_GOOGLE_CLIENT_SECRET
GoogleRedirectURL  string // GZ_GOOGLE_REDIRECT_URL (z. B. https://gregor20.henemm.com/api/auth/google/callback)
```

Wenn `GoogleClientID` leer ist, gibt `/api/auth/google/init` HTTP 501 zurück — Feature ist dann deaktiviert.

### Step 3: `internal/store/user.go` — `FindUserByOAuthSub` (~+15 LoC)

```go
func (s *Store) FindUserByOAuthSub(provider, sub string) (*model.User, error)
```

Iteriert über alle `data/users/*/user.json`-Dateien, lädt jeden User und vergleicht `OAuthProvider` + `OAuthSub`. Gibt den ersten Treffer zurück, `nil, nil` bei keinem Fund (kein Fehler — neuer User wird angelegt).

### Step 4: `internal/handler/auth.go` — `GoogleOAuthInitHandler` (~+30 LoC)

```go
func GoogleOAuthInitHandler(cfg *config.Config) http.HandlerFunc
```

Ablauf:
1. `cfg.GoogleClientID` leer → HTTP 501
2. 16 zufällige Bytes generieren → hex-kodierter `state`-Token
3. Cookie `gz_oauth_state` setzen: HttpOnly, SameSite=Lax, MaxAge=600, Secure nur bei HTTPS
4. `oauth2.Config` mit Scopes `openid email profile` aufbauen
5. HTTP 302 zu `oauth2Config.AuthCodeURL(state)`

### Step 5: `internal/handler/auth.go` — `GoogleOAuthCallbackHandler` (~+70 LoC)

```go
func GoogleOAuthCallbackHandler(cfg *config.Config, s *store.Store) http.HandlerFunc
```

Ablauf:
1. `gz_oauth_state`-Cookie lesen; `subtle.ConstantTimeCompare` gegen URL-Parameter `state`
2. Cookie löschen (MaxAge=-1)
3. Mismatch → Redirect zu `/login?error=oauth_failed`
4. `oauth2Config.Exchange(ctx, r.FormValue("code"))` — Code gegen Token tauschen
5. Userinfo-Endpoint abrufen: `https://www.googleapis.com/oauth2/v3/userinfo`
6. `email_verified`-Claim prüfen — `false` → Redirect zu `/login?error=oauth_failed`. Hinweis: `aud`-Validierung entfällt, da `v3/userinfo` kein `aud`-Feld liefert; Client-ID-Bindung erfolgt implizit durch den Code-Exchange.
7. `store.FindUserByOAuthSub("google", sub)`:
   - **Gefunden:** `gz_session`-Cookie ausstellen, Redirect zu `/`
   - **Nicht gefunden:** Neue User-ID generieren: `g-` + 8 Hex-Zeichen (Kleinbuchstaben). Eindeutigkeit prüfen mit `store.LoadUser(id)` — bis zu 3 Versuche. `User{ID, OAuthProvider:"google", OAuthSub:sub, Email:email, CreatedAt:now}` anlegen, `SaveUser` aufrufen, `ProvisionUserDirs` aufrufen, `gz_session` ausstellen, Redirect zu `/`
8. Jeder Fehler (Netzwerk, Validierung, Store) → Redirect zu `/login?error=oauth_failed`

User-ID-Format `g-` + 8 Hex-Zeichen (z. B. `g-3a7f9c12`) enthält bewusst keinen Punkt, da `verifySession` in `auth.ts` die Session auf `.` splittet (`{userId}.{timestamp}.{sig}`).

### Step 6: `cmd/server/main.go` — Routen registrieren (~+2 LoC)

```go
r.Get("/api/auth/google/init",     handler.GoogleOAuthInitHandler(cfg))
r.Get("/api/auth/google/callback", handler.GoogleOAuthCallbackHandler(cfg, s))
```

### Step 7: `frontend/src/lib/auth.ts` — defensiver Fix in `verifySession` (~+3 LoC)

Der aktuelle Split `session.split('.')` zerlegt `{userId}.{timestamp}.{sig}` in genau 3 Teile. Mit dem Präfix `g-` enthält die User-ID keinen Punkt — kein Bruch. Zur Absicherung gegen künftige Präfixe wird der Split auf maximal 3 Teile begrenzt:

```typescript
// VORHER:
const [userId, timestamp, sig] = session.split('.');

// NACHHER (defensiv):
const parts = session.split('.');
const sig = parts.pop()!;
const timestamp = parts.pop()!;
const userId = parts.join('.');
```

### Step 8: Frontend-Seiten — Google-Button (~+20 LoC gesamt)

`frontend/src/routes/login/+page.server.ts` und `register/+page.server.ts` geben `googleEnabled: !!env.GZ_GOOGLE_CLIENT_ID` zurück.

In den jeweiligen `.svelte`-Seiten erscheint der Button nur wenn `data.googleEnabled`:

```svelte
{#if data.googleEnabled}
  <a href="/api/auth/google/init" class="btn-secondary w-full">
    Mit Google anmelden
  </a>
{/if}
```

`register/+page.svelte` erhält analog einen „Mit Google registrieren"-Button.

### LoC-Budget

| Datei | Δ LoC |
|-------|-------|
| `internal/model/user.go` | +4 |
| `internal/config/config.go` | +6 |
| `internal/store/user.go` | +15 |
| `internal/middleware/auth.go` | +5 |
| `internal/handler/auth.go` | +100 |
| `cmd/server/main.go` | +2 |
| `frontend/src/lib/auth.ts` | +3 |
| `frontend/src/routes/login/*` | +15 |
| `frontend/src/routes/register/*` | +15 |
| **Produktion gesamt** | **~165 LoC** |
| Tests | ~65 LoC |
| **Gesamt** | **~230 LoC** (innerhalb 250er-Limit) |

## Expected Behavior

- **Input (init):** Browser ruft `/api/auth/google/init` auf (plain `<a>`-Link, kein JavaScript nötig)
- **Output (init):** HTTP 302 zu Google OAuth-Consent-Seite; `gz_oauth_state`-Cookie gesetzt (MaxAge=600s)
- **Input (callback):** Google sendet `?code=...&state=...` an `/api/auth/google/callback`
- **Output (callback, bestehender User):** `gz_session`-Cookie gesetzt, HTTP 302 zu `/`
- **Output (callback, neuer User):** User in `data/users/g-{hex}/user.json` angelegt, `gz_session`-Cookie gesetzt, HTTP 302 zu `/`
- **Output (Fehlerfall):** HTTP 302 zu `/login?error=oauth_failed` — kein Stacktrace, keine sensiblen Daten im Browser
- **Side effects:** Neues `user.json` für erstmalig einloggende Google-Nutzer; bestehende Nutzer-Dateien bleiben unverändert

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| `GZ_GOOGLE_CLIENT_ID` nicht gesetzt | `/api/auth/google/init` → HTTP 501; Buttons im Frontend ausgeblendet |
| State-Mismatch (CSRF-Versuch) | Redirect zu `/login?error=oauth_failed` |
| `email_verified: false` in Userinfo | Redirect zu `/login?error=oauth_failed` |
| Google Userinfo-Endpoint nicht erreichbar | Redirect zu `/login?error=oauth_failed` |
| ID-Kollision nach 3 Versuchen | Redirect zu `/login?error=oauth_failed` (extrem unwahrscheinlich) |
| Gleiche E-Mail, verschiedene Auth-Methoden | Zwei getrennte Konten — kein Account-Linking in v1 |

## Acceptance Criteria

**AC-1:** Given `GZ_GOOGLE_CLIENT_ID` ist konfiguriert und der User ruft `/login` auf / When die Seite gerendert wird / Then ist ein „Mit Google anmelden"-Link sichtbar, der auf `/api/auth/google/init` zeigt — und der Link erscheint nicht wenn `GZ_GOOGLE_CLIENT_ID` leer ist.
  - Test: (populated after /tdd-red)

**AC-2:** Given ein Nutzer folgt dem Google-OAuth-Flow mit einem Google-Konto, das noch nicht in der Anwendung existiert / When der Callback mit gültigem `code` und korrektem `state` aufgerufen wird / Then wird ein neues `user.json` mit `oauth_provider: "google"` und der `oauth_sub` des Google-Kontos angelegt, und der Browser erhält einen `gz_session`-Cookie plus Redirect zu `/`.
  - Test: (populated after /tdd-red)

**AC-3:** Given ein Nutzer hat sich bereits per Google eingeloggt (User-Eintrag mit `oauth_sub` existiert) / When er erneut den Google-OAuth-Flow durchläuft / Then wird kein zweites Konto angelegt — der bestehende User wird per `FindUserByOAuthSub` gefunden und eine neue Session ausgestellt.
  - Test: (populated after /tdd-red)

**AC-4:** Given eine eingehende Callback-Anfrage enthält einen `state`-Parameter, der nicht mit dem `gz_oauth_state`-Cookie übereinstimmt (CSRF-Angriff) / When `GoogleOAuthCallbackHandler` den Vergleich via `subtle.ConstantTimeCompare` ausführt / Then wird kein Token-Exchange durchgeführt und der Browser wird zu `/login?error=oauth_failed` weitergeleitet.
  - Test: (populated after /tdd-red)

**AC-5:** Given die Google OAuth Userinfo enthält `email_verified: false` (unverifizierte E-Mail) / When `GoogleOAuthCallbackHandler` die Userinfo auswertet / Then wird der Login abgebrochen und der Browser zu `/login?error=oauth_failed` weitergeleitet — kein User-Objekt wird angelegt. Hinweis: aud-Claim-Validierung entfällt, da `v3/userinfo` keinen `aud`-Claim liefert; die Client-ID-Validierung erfolgt implizit durch den OAuth2-Code-Exchange auf Google-Seite.
  - Test: (populated after /tdd-red)

**AC-6:** Given `GZ_GOOGLE_CLIENT_ID` ist nicht konfiguriert / When `/api/auth/google/init` aufgerufen wird / Then antwortet der Endpoint mit HTTP 501 und führt keinen OAuth-Redirect durch.
  - Test: (populated after /tdd-red)

**AC-7:** Given eine `gz_session` wurde für einen Google-OAuth-User mit ID `g-3a7f9c12` ausgestellt / When `verifySession` in `auth.ts` die Session verarbeitet / Then wird die `userId` korrekt als `g-3a7f9c12` extrahiert — kein Split-Fehler durch den Bindestrich-Präfix.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein Account-Linking in v1:** Wer sich mit Google einloggt und schon ein Passwort-Konto mit gleicher E-Mail-Adresse hat, erhält ein separates Konto. Zusammenführung ist für eine spätere Version vorgesehen.
- **`FindUserByOAuthSub` iteriert alle User:** Bei sehr vielen Nutzern (>10.000) könnte die lineare Suche spürbar werden. Für die aktuelle Nutzerzahl ist das unbedenklich.
- **Apple Sign-In verschoben:** Das Datenmodell (`OAuthProvider`/`OAuthSub`) ist bereits Apple-kompatibel; die Implementierung folgt in Issue #426.
- **Keine E-Mail-Verifikation:** Die E-Mail aus dem Google-Userinfo-Endpoint wird ohne eigene Verifikation übernommen. Google garantiert bereits, dass die E-Mail verifiziert ist (`email_verified: true` im Claim muss geprüft werden).

## Changelog

- 2026-05-29: Initial spec erstellt für Issue #425 (Google OAuth Login). Scope: Go Authorization Code Flow (init + callback), User-ID-Strategie `g-{8hex}`, additives User-Modell, defensiver `verifySession`-Fix, Frontend-Buttons mit `googleEnabled`-Flag. Apple (#426) explizit ausgeklammert.
- 2026-05-29: AC-5 korrigiert: aud-Validierung via v3/userinfo nicht möglich (Endpoint liefert kein aud-Feld); ersetzt durch email_verified-Pflichtprüfung. email_verified=false führt zu /login?error=oauth_failed.
