---
entity_id: issue_449_magic_link
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [go, sveltekit, auth, magic-link, otp, email, issue-449]
---

# Issue #449 — Magic Link / OTP Login per E-Mail

## Approval

- [ ] Approved

## Purpose

Ergänzt das Auth-System um einen passwortlosen Login-Weg via E-Mail-OTP: Der Nutzer gibt seine E-Mail-Adresse ein und erhält einen 6-stelligen Code, den er anschließend auf einer zweiten Seite eingibt, um sich einzuloggen. Existiert noch kein Konto mit dieser E-Mail, wird automatisch ein neues Konto angelegt — damit sinkt die Einstiegshürde und das System bleibt selbst ohne Google-OAuth zugänglich.

## Scope

### In Scope

- `internal/handler/auth_magic.go` — zwei neue Handler: `MagicLinkRequestHandler`, `MagicLinkVerifyHandler`; package-level `sync.Map` als OTP-Store
- `internal/handler/auth_magic_test.go` — Tests ohne Mocks (realer Store, SMTP gegen geschlossenen Port)
- `internal/handler/export_test.go` — `ResetOTPStoreForTest()` — Zugriff auf unexPortierten OTP-Store für Tests
- `internal/mail/magic.go` — OTP-E-Mail über Resend SMTP versenden
- `internal/store/user.go` — neue Methode `FindUserByEmail(email string) (*model.User, error)`
- `internal/middleware/auth.go` — zwei neue Exempt-Pfade
- `cmd/server/main.go` — zwei neue Routen + IP-Rate-Limiter registrieren
- `frontend/src/routes/magic-link/+page.svelte` — E-Mail-Eingabeformular
- `frontend/src/routes/magic-link/+page.server.ts` — Server-Action POST an Backend
- `frontend/src/routes/magic-link/verify/+page.svelte` — 6-stellige Code-Eingabe
- `frontend/src/routes/magic-link/verify/+page.server.ts` — Verify + Cookie-Extraktion + Redirect
- `frontend/src/hooks.server.ts` — zwei neue publicPaths
- `frontend/src/routes/login/+page.svelte` — Link „Mit E-Mail-Code anmelden" → `/magic-link`

### Out of Scope

- SMS-OTP oder Push-OTP (nur E-Mail in v1)
- Account-Linking (Magic-Link-Konto + Passwort-Konto zusammenführen)
- Persistenter OTP-Store (Neustart löscht alle laufenden Codes — akzeptabel für TTL von 15 Min)
- Admin-seitige OTP-Konto-Verwaltung

## Source

- **Schicht:** Go-Backend (`internal/`) + SvelteKit-Frontend (`frontend/src/routes/`)
- **Datei (neu):** `internal/handler/auth_magic.go`, `internal/mail/magic.go`
- **Identifier (Backend):** `MagicLinkRequestHandler`, `MagicLinkVerifyHandler`, `FindUserByEmail`, `ResetOTPStoreForTest`
- **Identifier (Frontend):** `+page.server.ts` (magic-link + verify), publicPaths in `hooks.server.ts`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `crypto/rand` | Go-Stdlib | Kryptografisch sichere Zufallszahlen für OTP-Generierung |
| `sync.Map` | Go-Stdlib | Thread-sicherer package-level OTP-Store (kein externes Dependency) |
| `internal/config/config.go` | Go-Config (vorhanden) | `SMTPHost`, `SMTPUser`, `SMTPPass` für Resend-SMTP-Versand |
| `internal/model/user.go` | Go-Struct (vorhanden) | `User`-Struct; Felder `ID`, `Email` werden genutzt/gesetzt |
| `internal/store/user.go` | Go-Store (vorhanden, erweitert) | `FindUserByEmail` (neu), `SaveUser`, `LoadUser`, `ProvisionUserDirs` |
| `internal/middleware/auth.go` | Go-Middleware (vorhanden, erweitert) | Exempt-Pfade für `/api/auth/magic-link` und `/api/auth/magic-link/verify` |
| `internal/middleware/auth.go` (SignSession) | Go-Middleware (vorhanden) | `middleware.SignSession(userID, secret)` — Session-Cookie ausstellen |
| `cmd/server/main.go` (IPRateLimiter) | Go-Handler (vorhanden) | `IPRateLimiter` — 5 req/15 min (Request), 10 req/15 min (Verify) |
| Resend SMTP (`cfg.SMTPHost`) | Externer Dienst | OTP-E-Mail versenden (smtp.resend.com:587) |
| `frontend/src/hooks.server.ts` | SvelteKit (vorhanden, erweitert) | publicPaths — verhindert Redirect-Loop für unauthentifizierte Besucher |
| `frontend/src/routes/login/+page.svelte` | SvelteKit (vorhanden, erweitert) | Link-Ergänzung im links-Bereich unterhalb „Passwort vergessen?" |

## Implementation Details

### Step 1: `internal/store/user.go` — `FindUserByEmail` (~+15 LoC)

```go
func (s *Store) FindUserByEmail(email string) (*model.User, error)
```

Iteriert über alle `data/users/*/user.json`-Dateien, lädt jeden User per `LoadUser` und vergleicht `User.Email` (case-insensitive `strings.EqualFold`). Gibt den ersten Treffer zurück; bei keinem Fund `nil, nil` (kein Fehler — neuer User folgt). Analog zu `FindUserByOAuthSub`.

### Step 2: `internal/handler/auth_magic.go` — OTP-Store und `MagicLinkRequestHandler`

#### OTP-Store (package-level)

```go
type otpEntry struct {
    code      string
    userID    string
    expiresAt time.Time
    attempts  int
}

var otpStore sync.Map // key: normalizedEmail (strings.ToLower), value: *otpEntry
```

Der Wert im Store ist ein Pointer `*otpEntry`, damit `attempts`-Mutationen ohne erneutes `Store()` wirksam sind.

#### OTP-Generierung

```go
b := make([]byte, 4)
_, _ = rand.Read(b)
n := binary.BigEndian.Uint32(b)
code := fmt.Sprintf("%06d", n%1_000_000)
```

Code wird als String gespeichert (z. B. `"048392"`) — kein int-Cast, der führende Nullen verlieren würde.

#### `MagicLinkRequestHandler` (~+60 LoC)

Ablauf:
1. JSON-Body parsen: `{"email": "..."}` — Fehler → HTTP 400
2. Email normalisieren: `strings.ToLower(strings.TrimSpace(email))`
3. `store.FindUserByEmail(normalizedEmail)`: gefunden → `userID = user.ID`; nicht gefunden → neuen User anlegen (siehe Step 3)
4. OTP generieren, `*otpEntry{code, userID, time.Now().Add(15*time.Minute), 0}` in `otpStore.Store(normalizedEmail, entry)`
5. OTP-Versand in Goroutine starten (10 s Context-Timeout via `context.WithTimeout`): `mail.SendMagicLinkEmail(cfg, normalizedEmail, code)`
6. Immer HTTP 200 `{"status":"ok"}` zurückgeben — kein User-Enumeration

#### `MagicLinkVerifyHandler` (~+50 LoC)

Ablauf:
1. JSON-Body parsen: `{"email": "...", "code": "..."}` — Fehler → HTTP 400
2. Email normalisieren
3. `otpStore.Load(normalizedEmail)` — nicht gefunden → HTTP 400 `{"error":"invalid_or_expired_code"}`
4. `entry.attempts >= 3` → HTTP 400 `{"error":"max_attempts_exceeded"}` (vor Code-Vergleich!)
5. `time.Now().After(entry.expiresAt)` → `otpStore.Delete(normalizedEmail)`, HTTP 400 `{"error":"invalid_or_expired_code"}`
6. `entry.code != submittedCode` → `entry.attempts++`, HTTP 400 `{"error":"invalid_or_expired_code"}`
7. Valider Code: `otpStore.Delete(normalizedEmail)`, `middleware.SignSession(entry.userID, cfg.SessionSecret)` aufrufen, Cookie setzen (HttpOnly, SameSite=Lax, MaxAge=86400, Secure wenn `r.Header.Get("X-Forwarded-Proto") == "https"`), HTTP 200 `{"id": entry.userID}`

### Step 3: Neuen User anlegen (m-{8hex}) (~+20 LoC, in auth_magic.go)

```go
for attempt := 0; attempt < 3; attempt++ {
    b := make([]byte, 4)
    rand.Read(b)
    id := "m-" + hex.EncodeToString(b) // z. B. "m-a3f19c2d"
    if _, err := s.LoadUser(id); err != nil { // err != nil = nicht gefunden
        user := &model.User{ID: id, Email: normalizedEmail, CreatedAt: time.Now()}
        s.SaveUser(user)
        s.ProvisionUserDirs(id)
        return id, nil
    }
}
return "", errors.New("id collision after 3 attempts")
```

Kein `PasswordHash`, kein `OAuthProvider`, kein `OAuthSub` — reines Magic-Link-Konto.

### Step 4: `internal/mail/magic.go` (~+30 LoC)

```go
func SendMagicLinkEmail(cfg *config.Config, to, code string) error
```

Aufbau:
1. `cfg.SMTPHost` leer → `log.Warn("SMTP not configured, skipping OTP email")`, return nil (kein Panic)
2. SMTP-Verbindung via `net/smtp` zu `cfg.SMTPHost:587` (oder als konfiguriertes Port)
3. Auth: `smtp.PlainAuth("", cfg.SMTPUser, cfg.SMTPPass, host)`
4. E-Mail: Von `gregor_zwanzig@henemm.com`, An `to`, Subject `Dein Gregor-Zwanzig-Code`, Body enthält `code` klar leserlich
5. Fehler werden an den Aufrufer zurückgegeben (Goroutine loggt sie, ignoriert für die HTTP-Response)

### Step 5: `internal/middleware/auth.go` — Exempt-Pfade (~+2 LoC)

Beide Pfade zur bestehenden Exempt-Liste hinzufügen:
```
/api/auth/magic-link
/api/auth/magic-link/verify
```

### Step 6: `cmd/server/main.go` — Routen + Rate-Limiter (~+6 LoC)

```go
magicLinkLimiter := NewIPRateLimiter(5, 15*time.Minute)
magicVerifyLimiter := NewIPRateLimiter(10, 15*time.Minute)

r.Post("/api/auth/magic-link",        magicLinkLimiter(handler.MagicLinkRequestHandler(cfg, s)))
r.Post("/api/auth/magic-link/verify", magicVerifyLimiter(handler.MagicLinkVerifyHandler(cfg, s)))
```

### Step 7: `internal/handler/export_test.go` — Test-Helper (~+5 LoC)

```go
package handler_test  // ODER: package handler mit //go:build test

func ResetOTPStoreForTest() {
    otpStore.Range(func(k, _ any) bool { otpStore.Delete(k); return true })
}
```

Jeder Test ruft `t.Cleanup(handler.ResetOTPStoreForTest)` auf, damit Tests sich nicht gegenseitig beeinflussen. Alternativ: Tests verwenden jeweils eine einzigartige E-Mail-Adresse.

### Step 8: Frontend — `/magic-link` (+page.svelte + +page.server.ts)

`+page.server.ts` definiert eine `default` Form-Action:
1. `email` aus FormData lesen
2. `fetch(BACKEND_URL + "/api/auth/magic-link", {method:"POST", body: JSON.stringify({email})})` 
3. Immer: `return { sent: true }` — Backend gibt immer 200, kein Fehlerfall für den User

`+page.svelte`:
- Zustand `sent = false` initial; nach Submit: `sent = true`
- Bei `sent = false`: E-Mail-Eingabefeld + Absenden-Button
- Bei `sent = true`: Erfolgstext „Ein Code wurde an deine E-Mail-Adresse gesendet." + Hinweistext: „Falls du bereits ein Konto hast, stelle sicher, dass deine E-Mail-Adresse in deinem Profil hinterlegt ist." + Link zu `/magic-link/verify`

### Step 9: Frontend — `/magic-link/verify` (+page.svelte + +page.server.ts)

`+page.server.ts` definiert eine `default` Form-Action:
1. `email` + `code` aus FormData lesen
2. `fetch(BACKEND_URL + "/api/auth/magic-link/verify", {method:"POST", body: JSON.stringify({email, code})})`
3. Fehlerfall (400) → `return fail(400, {error: responseBody.error})`
4. Erfolg (200): `gz_session`-Cookie-Wert aus `set-cookie`-Header extrahieren (gleicher Regex wie `/login`-Handler), Cookie auf Browser setzen, `throw redirect(302, "/")`

`+page.svelte`:
- Verstecktes Feld `email` (aus URL-Param oder Session-Storage) + Sichtbares Feld `code` (`maxlength="6"`, `pattern="[0-9]{6}"`, `inputmode="numeric"`)
- Fehlermeldung bei `form?.error`

### Step 10: `frontend/src/hooks.server.ts` — publicPaths (~+2 LoC)

```typescript
const publicPaths = [
  // ... bestehende Pfade ...
  '/magic-link',
  '/magic-link/verify',
]
```

### Step 11: `/login` — Link ergänzen (~+3 LoC)

Im links-Bereich unterhalb „Passwort vergessen?" in `frontend/src/routes/login/+page.svelte`:
```svelte
<a href="/magic-link">Mit E-Mail-Code anmelden</a>
```

### LoC-Budget

| Datei | Δ LoC |
|-------|-------|
| `internal/store/user.go` | +15 |
| `internal/handler/auth_magic.go` | +130 |
| `internal/handler/export_test.go` | +5 |
| `internal/mail/magic.go` | +30 |
| `internal/middleware/auth.go` | +2 |
| `cmd/server/main.go` | +6 |
| `frontend/src/routes/magic-link/*` | +40 |
| `frontend/src/routes/magic-link/verify/*` | +35 |
| `frontend/src/hooks.server.ts` | +2 |
| `frontend/src/routes/login/+page.svelte` | +3 |
| **Produktion gesamt** | **~268 LoC** |
| Tests (`auth_magic_test.go`) | ~80 LoC |
| **Gesamt** | **~348 LoC** (LoC-Override auf 400 nötig) |

## Expected Behavior

- **Input (Request):** `POST /api/auth/magic-link` mit `{"email":"user@example.com"}`
- **Output (Request):** Immer HTTP 200 `{"status":"ok"}`; OTP-E-Mail wird asynchron via Resend versendet
- **Input (Verify):** `POST /api/auth/magic-link/verify` mit `{"email":"user@example.com","code":"483921"}`
- **Output (Verify, Erfolg):** HTTP 200 `{"id":"m-a3f19c2d"}`; `gz_session`-Cookie gesetzt (HttpOnly, SameSite=Lax, MaxAge=86400, Secure bei HTTPS)
- **Output (Verify, Fehler):** HTTP 400 `{"error":"invalid_or_expired_code"}` oder `{"error":"max_attempts_exceeded"}`
- **Side effects:** Neues `user.json` in `data/users/m-{hex}/` für erstmalig einloggende Nutzer; bestehende Nutzer-Dateien bleiben unverändert; OTP-Eintrag wird bei Erfolg oder Ablauf aus `sync.Map` gelöscht

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| E-Mail nicht im System | Neues Konto mit ID `m-{8hex}` anlegen, OTP normal versenden |
| Falscher Code (1.–3. Versuch) | HTTP 400 `invalid_or_expired_code`, `attempts++` |
| Falscher Code nach 3 Fehlversuchen | HTTP 400 `max_attempts_exceeded` ohne Code-Vergleich |
| OTP abgelaufen (>15 Min) | Eintrag löschen, HTTP 400 `invalid_or_expired_code` |
| `SMTPHost` leer | Log-Warnung, HTTP 200 — kein Panic, kein Fehler an Client |
| ID-Kollision nach 3 Versuchen | HTTP 500 (extrem unwahrscheinlich) |
| Mehr als 5 Requests/15 Min (Request-Endpoint) | HTTP 429 via IPRateLimiter |
| Mehr als 10 Requests/15 Min (Verify-Endpoint) | HTTP 429 via IPRateLimiter |

## Acceptance Criteria

**AC-1:** Given a valid email address is submitted / When `POST /api/auth/magic-link` is called / Then the response is always HTTP 200 `{"status":"ok"}` regardless of whether the email belongs to an existing user or not — no user enumeration possible.
  - Test: (populated after /tdd-red)

**AC-2:** Given an email that does not match any existing user profile / When `POST /api/auth/magic-link` is called / Then a new user with ID format `m-{8hex}` is created with `Email` set to the submitted (normalized) address and `ProvisionUserDirs` is called for that user.
  - Test: (populated after /tdd-red)

**AC-3:** Given an existing user whose `Email` field matches the submitted address / When `POST /api/auth/magic-link` is called / Then no new user is created and the OTP entry is associated with the existing user's ID.
  - Test: (populated after /tdd-red)

**AC-4:** Given a correct 6-digit code is submitted within 15 minutes of issuance / When `POST /api/auth/magic-link/verify` is called / Then a `gz_session` cookie is set (HttpOnly, SameSite=Lax, MaxAge=86400) and HTTP 200 `{"id": userId}` is returned.
  - Test: (populated after /tdd-red)

**AC-5:** Given a wrong code is submitted and fewer than 3 previous wrong attempts have occurred / When `POST /api/auth/magic-link/verify` is called / Then HTTP 400 `{"error":"invalid_or_expired_code"}` is returned and the attempt counter increments by 1.
  - Test: (populated after /tdd-red)

**AC-6:** Given 3 wrong codes have already been submitted for the same email / When `POST /api/auth/magic-link/verify` is called again with any code / Then HTTP 400 `{"error":"max_attempts_exceeded"}` is returned without performing a code comparison.
  - Test: (populated after /tdd-red)

**AC-7:** Given an OTP entry was created more than 15 minutes ago / When `POST /api/auth/magic-link/verify` is called / Then HTTP 400 `{"error":"invalid_or_expired_code"}` is returned and the entry is removed from the OTP store.
  - Test: (populated after /tdd-red)

**AC-8:** Given the `/magic-link` success screen is displayed after submitting an email / When the page renders / Then the hint text "Falls du bereits ein Konto hast, stelle sicher, dass deine E-Mail-Adresse in deinem Profil hinterlegt ist." is visible on the page.
  - Test: (populated after /tdd-red)

**AC-9:** Given an unauthenticated user visits `/magic-link` or `/magic-link/verify` / When the SvelteKit hooks run / Then no redirect to `/login` occurs because both routes are listed in `publicPaths`.
  - Test: (populated after /tdd-red)

**AC-10:** Given SMTP is not configured (`SMTPHost` is empty) / When `POST /api/auth/magic-link` is called / Then the server returns HTTP 200 `{"status":"ok"}` and logs a warning without panicking or returning an error to the client.
  - Test: (populated after /tdd-red)

**AC-11:** Given a successful verify response with a `set-cookie` header containing `gz_session` / When the SvelteKit `+page.server.ts` on `/magic-link/verify` processes the response / Then the `gz_session` cookie value is extracted via the same regex pattern as the `/login` page and set as a browser cookie before redirecting to `/`.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein persistenter OTP-Store:** Bei Server-Neustart gehen alle laufenden OTPs verloren. Bei TTL von 15 Minuten ist das tolerierbar; für höhere Resilienz wäre Redis/DB nötig.
- **`FindUserByEmail` iteriert alle User:** Lineare Suche — bei sehr vielen Nutzern (>10.000) spürbar. Für aktuelle Nutzerzahl unbedenklich.
- **OTP per E-Mail:** Keine zusätzliche Verifikation des E-Mail-Besitzes — wer Zugriff auf das Postfach hat, kann sich einloggen. Das ist by design.
- **Keine Account-Linking-Logik:** Wer sich per Magic-Link und separat per Google einloggt, erhält zwei Konten falls unterschiedliche E-Mail-Adressen genutzt werden. Zusammenführung ist nicht geplant.
- **LoC-Override nötig:** Produktions- + Test-Code überschreitet Standard-250er-Limit; vor Phase 6 `workflow.py set-field loc_limit_override 400` ausführen.

## Changelog

- 2026-05-29: Initial spec erstellt für Issue #449 (Magic Link / OTP Login per E-Mail). Scope: Go-Backend mit sync.Map OTP-Store, neuer FindUserByEmail-Store-Methode, automatische Neuanlage von Konten mit m-{8hex}-ID, Resend-SMTP-Versand, zwei SvelteKit-Routen, publicPaths-Ergänzung, Login-Link. AC-1 bis AC-11 nach PO-Vorgabe.
