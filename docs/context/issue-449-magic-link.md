# Context: Issue #449 — Magic Link / OTP per E-Mail

## Request Summary
Nutzer gibt seine E-Mail-Adresse ein und erhält einen 6-stelligen Einmal-Code per Mail. Nach Code-Eingabe ist er eingeloggt — kein Passwort nötig.

## Scope (aus Issue)
- **Backend (Go):** Code generieren (`crypto/rand`), in-memory mit TTL speichern (`sync.Map`), per Resend versenden, validieren + löschen
- **Frontend (SvelteKit):** E-Mail-Eingabe-Seite (`/magic-link`), Code-Eingabe-Seite (`/magic-link/verify`)
- **User-Modell:** Bestehende User (Passwort oder OAuth) per Magic Link einloggbar; neue User erhalten `m-{8hex}` als ID

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/handler/auth.go` | Bestehende Auth-Handler (Login, Register, ForgotPassword) — Muster übernehmen |
| `internal/handler/auth_oauth.go` | OAuth-Handler: `createOAuthUser()` Pattern für Magic-Link User-Anlage |
| `internal/model/user.go` | User-Struct: `OAuthProvider`, `OAuthSub`, `Email` bereits vorhanden |
| `internal/store/user.go` | `SaveUser`, `LoadUser`, `FindUserByOAuthSub`, `SaveResetToken` — Muster für OTP-Store |
| `internal/config/config.go` | Bestehende SMTP-Config (`SMTP_HOST`, `SMTP_FROM`) — nutzen wir für Magic-Link Mail |
| `internal/middleware/auth.go` | `AuthMiddleware` Exempt-Liste, `SignSession`, `validateSession` |
| `internal/middleware/ratelimit.go` | `IPRateLimiter` — bestehende Rate-Limit-Infrastruktur |
| `internal/mail/sender.go` | `Send(MailConfig, to, Mail)` — SMTP-Dispatch, direkt nutzbar |
| `internal/mail/reset.go` | `BuildResetMail()` — Muster für Magic-Link-Mail-Builder |
| `cmd/server/main.go` | Router-Registrierung, Auth-Exemptions, Rate-Limiter-Instanzen |
| `frontend/src/routes/login/+page.svelte` | Login-UI: Google-OAuth-Block als Muster für Magic-Link-Block |
| `frontend/src/routes/login/+page.server.ts` | Cookie-Handling-Muster für Session nach Verify |
| `frontend/src/routes/forgot-password/+page.svelte` | Zweistufige E-Mail-Eingabe-UI als visuelles Referenz-Muster |

## Existing Patterns

### Code-Generierung (Issue-Vorgabe)
```go
b := make([]byte, 4)
crypto/rand.Read(b)
code := fmt.Sprintf("%06d", binary.BigEndian.Uint32(b) % 1_000_000)
```

### User-Anlage (OAuth-Pattern in `createOAuthUser`)
- Retry-Loop für ID-Kollision (3 Versuche)
- `ProvisionUserDirs(id)` nach `SaveUser`
- ID-Format für Magic-Link: `m-{8hex}` (aus Issue-Spec)

### OTP-Speicherung (bestehender Ansatz: PasswordResetToken)
- `model.PasswordResetToken` hat bereits `TokenHash + ExpiresAt`
- Store nutzt `SaveResetToken(userId, token)` / `LoadResetToken(userId)` / `DeleteResetToken(userId)`
- **Problem:** OTP wird VOR User-Login angefordert → userId ist noch E-Mail, nicht User-ID
- **Lösung:** OTP keyed by E-Mail in `sync.Map` im Handler (In-Memory, TTL 15 Min, kein Disk-Hit nötig)

### Session-Abschluss (OAuth-Muster)
```go
sessionToken := middleware.SignSession(userId, cfg.SessionSecret)
http.SetCookie(w, &http.Cookie{Name: "gz_session", Value: sessionToken, ...})
http.Redirect(w, r, "/", http.StatusFound)
```

### E-Mail suchen
`FindUserByOAuthSub(provider, sub)` iteriert alle Users — gleiches Muster für `FindUserByEmail(email)` nötig

### Rate-Limit
`NewIPRateLimiter(burst, window)` — für `/api/auth/magic-link` und `/api/auth/magic-link/verify`

### Mail-Versand (Goroutine mit Timeout)
`ForgotPasswordHandler` nutzt Goroutine + 10s-Timeout-Select — gleiche Struktur für OTP-Mail

### AuthMiddleware Exemptions
Bestehend: `r.URL.Path == "/api/auth/..."` direkt verglichen. Neue Pfade müssen dort eingetragen werden.

## Neue Komponenten (zu implementieren)

### Backend
1. **`internal/handler/auth_magic.go`** (neuer Handler)
   - `MagicLinkRequestHandler(cfg, s)` — POST `/api/auth/magic-link` (E-Mail annehmen, Code generieren+senden)
   - `MagicLinkVerifyHandler(cfg, s)` — POST `/api/auth/magic-link/verify` (Code prüfen, Session anlegen)
   - In-Memory-OTP-Store als `sync.Map` im Package (key: E-Mail, value: struct{code, expiresAt, attempts})

2. **`internal/store/user.go`** — Ergänzung: `FindUserByEmail(email)` (lineare Suche wie `FindUserByOAuthSub`)

3. **`internal/mail/magic.go`** — `BuildMagicLinkMail(code string) Mail`

4. **`internal/config/config.go`** — keine neuen ENV-Variablen nötig (nutzt bestehende SMTP-Werte)

5. **`cmd/server/main.go`** — 2 neue Routes + Rate-Limiter + Exemptions

### Frontend
1. **`frontend/src/routes/magic-link/+page.svelte`** — E-Mail-Eingabe
2. **`frontend/src/routes/magic-link/+page.server.ts`** — POST an `/api/auth/magic-link`
3. **`frontend/src/routes/magic-link/verify/+page.svelte`** — Code-Eingabe (6 Ziffern)
4. **`frontend/src/routes/magic-link/verify/+page.server.ts`** — POST an `/api/auth/magic-link/verify`, Cookie setzen
5. **`frontend/src/routes/login/+page.svelte`** — "Per E-Mail-Code anmelden"-Link ergänzen

## Dependencies

### Upstream (was dieser Code nutzt)
- `internal/middleware.SignSession` — Session-Token erzeugen
- `internal/mail.Send` + `mail.MailConfig` — SMTP-Dispatch
- `internal/store.Store` — User laden/anlegen
- `internal/middleware.NewIPRateLimiter` — Rate-Limit
- `crypto/rand`, `encoding/binary`, `sync` — Code-Generierung + OTP-Map

### Downstream (was diesen Code nutzt)
- `cmd/server/main.go` — Router-Registrierung
- `frontend/src/routes/login/+page.svelte` — Magic-Link-Einstieg
- AuthMiddleware — muss neue Pfade exemptieren

## Risiken & Überlegungen

1. **User-Enumeration:** Response-Timing-Angriff möglich (E-Mail bekannt vs. nicht bekannt). Issue-Spec sagt: kein Hinweis geben — always 200 zurück, egal ob E-Mail bekannt.
2. **Neue User ohne E-Mail:** Magic-Link-User haben `Email` gesetzt (aus der Anfrage), aber kein Passwort-Hash. `FindUserByEmail` muss linear alle User durchsuchen (wie `FindUserByOAuthSub`).
3. **Rate-Limit per E-Mail vs. per IP:** Issue sagt "max 3 Versuche pro E-Mail pro 15 Min" für Verify. Für Request-Endpoint reicht IP-Limit (verhindert Spam). Verify braucht zusätzlich E-Mail-basierten Attempt-Counter (im OTP-Struct mitgeführt).
4. **In-Memory OTP-Verlust bei Neustart:** Laut Issue akzeptabler Trade-off. Kein Disk-Store nötig.
5. **Bestehende User mit Passwort:** Magic-Link loggt ein ohne Passwort zu ändern. Kein Konflikt.
6. **OTP-Store-Cleanup:** TTL-Einträge werden bei Ablauf-Check gelöscht. Zusätzlich periodischer Cleanup-Goroutine empfohlen (verhindert Memory-Leak bei vielen Anfragen).
7. **Bestehende SMTP-Config:** `SMTPHost` / `SMTPFrom` werden genutzt. Für Test-User (`mail.IsTestUser`) → Google SMTP — aber Magic-Link-User sind E-Mail-basiert, keine User-ID-basierte Test-Erkennung. Separater Prüfmechanismus nötig oder Test-User mit `IsTestUser` auf E-Mail-Adresse ausweiten.

## Existing Specs
- Kein eigener Spec für #449 — kommt in Phase 3
- Verwandter Spec: `docs/specs/modules/` (Login/Auth noch nicht als eigene Spec vorhanden)
