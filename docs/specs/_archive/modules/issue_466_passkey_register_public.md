---
entity_id: issue_466_passkey_register_public
type: module
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
tags: [go, sveltekit, auth, passkey, webauthn, passwordless, issue-466]
---

# Issue #466 — Passkey V2: Passwortlose Registrierung für neue Nutzer

## Approval

- [ ] Approved

## Purpose

Ermöglicht neuen Nutzern, sich ausschließlich per WebAuthn/FIDO2-Passkey zu registrieren, ohne ein Passwort anzulegen. Der Nutzer gibt Benutzername und E-Mail-Adresse ein; der Browser öffnet den OS-Passkey-Dialog; bei Erfolg wird das Konto ohne `PasswordHash` angelegt und der Nutzer ist sofort eingeloggt. Die E-Mail-Adresse ist Pflicht, weil sie als Magic-Link-Wiederherstellungspfad (#449, bereits live) dient — passwortlose Konten müssen auch ohne funktionierende Authenticator-Hardware zugänglich bleiben.

## Scope

### In Scope

- `internal/handler/passkey.go` — zwei neue Handler: `PasskeyRegisterPublicBeginHandler`, `PasskeyRegisterPublicFinishHandler` (~130 LoC)
- `internal/handler/challenge_store.go` — Feld `Email string` zu `ChallengeEntry` hinzufügen (+1 Feld)
- `internal/middleware/auth.go` — zwei neue Exempt-Pfade in der Exempt-Liste (+2 Zeilen)
- `cmd/server/main.go` — zwei neue Routen mit Rate-Limiter registrieren (+6 Zeilen)
- `frontend/src/lib/passkey.ts` — neue Funktion `registerPasskeyPublic(username, email, label)` (~50 LoC)
- `frontend/src/routes/register/+page.svelte` — Toggle zwischen Passwort- und Passkey-Modus (~60 LoC)

### Out of Scope

- Passkey-Login für bestehende Nutzer (bereits in `PasskeyLoginBeginHandler` / `PasskeyLoginFinishHandler`)
- Passkey-Verwaltung eingeloggter Nutzer (bereits via `/api/auth/passkey/*` in Issue #450)
- SMS- oder Push-Fallback bei fehlender WebAuthn-Unterstützung
- Admin-seitige Verwaltung passwortloser Konten

## Source

- **Schicht:** Go-Backend (`internal/`) + SvelteKit-Frontend (`frontend/src/routes/register/`, `frontend/src/lib/`)
- **Datei (erweitert):** `internal/handler/passkey.go`, `internal/handler/challenge_store.go`
- **Datei (erweitert):** `frontend/src/lib/passkey.ts`, `frontend/src/routes/register/+page.svelte`
- **Identifier (Backend):** `PasskeyRegisterPublicBeginHandler`, `PasskeyRegisterPublicFinishHandler`, `ChallengeEntry.Email`
- **Identifier (Frontend):** `registerPasskeyPublic`, Passkey-Toggle in `+page.svelte`

## Estimated Scope

- **LoC:** ~370 (Produktion ~250, Tests ~120)
- **Files:** 6 Dateien geändert
- **Effort:** medium
- **LoC-Override:** 400 (vor Phase 6 ausführen: `workflow.py set-field loc_limit_override 400`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `go-webauthn/webauthn v0.17.4` | Go-Bibliothek (vorhanden in go.mod) | WebAuthn-Protokoll: `BeginRegistration`, `CreateCredential`, Attestation-Verifikation |
| `internal/handler/challenge_store.go` — `ChallengeStore.Put/Take` | Go-Store (vorhanden, erweitert) | TTL-gesicherter Challenge-Store (5 Min TTL, GC vorhanden); `Email`-Feld wird ergänzt |
| `internal/middleware/ratelimit.go` — `IPRateLimiter` | Go-Middleware (vorhanden) | Rate-Limiting: 5 req/h/IP für beide neuen Endpunkte |
| `internal/store/user.go` — `UserExists`, `SaveUser`, `ProvisionUserDirs` | Go-Store (vorhanden) | Duplikat-Prüfung, Nutzer persistieren, Verzeichnisse anlegen |
| `internal/model/user.go` — `User` | Go-Struct (vorhanden) | `PasswordHash` ist bereits `omitempty`, `PasskeyCredentials` bereits als Liste — kein Schema-Change |
| `internal/middleware/auth.go` — `AuthMiddleware` + `SignSession` | Go-Middleware (vorhanden, erweitert) | Exempt-Pfade ergänzen; `SignSession(userID, secret)` setzt gz_session-Cookie |
| `cmd/server/main.go` | Go-Entrypoint (vorhanden, erweitert) | Routen-Registrierung der zwei neuen Endpunkte |
| Issue #449 Magic Link (live) | Feature (vorhanden) | Wiederherstellungspfad für passwortlose Konten bei verlorenem Authenticator |
| `frontend/src/lib/passkey.ts` — `isWebAuthnSupported` | TypeScript (vorhanden, erweitert) | Feature-Detection vor Anzeige des Passkey-Toggles |

## Implementation Details

### Step 1: `internal/handler/challenge_store.go` — `Email`-Feld (+1 Feld)

```go
type ChallengeEntry struct {
    SessionData *webauthn.SessionData
    UserID      string
    Email       string        // NEU: E-Mail aus Begin-Request, für Finish-Handler
    ExpiresAt   time.Time
}
```

Kein Breaking Change — bestehende `Put`-Aufrufe setzen `Email` implizit auf `""`.

### Step 2: `PasskeyRegisterPublicBeginHandler` (~70 LoC, in `internal/handler/passkey.go`)

Endpunkt: `POST /api/auth/passkey/register/public/begin`

Ablauf:
1. JSON-Body parsen: `{"username": "...", "email": "..."}` — Fehler → HTTP 400 `{"error":"invalid_request"}`
2. Validierung:
   - `username`: 3–50 Zeichen, nur alphanumerisch + Bindestrich + Unterstrich → Fehler: HTTP 400 `{"error":"validation_failed"}`
   - `email`: muss `@` enthalten → Fehler: HTTP 400 `{"error":"validation_failed"}`
3. `s.UserExists(username)` → true: HTTP 409 `{"error":"user_already_exists"}`
4. Temporären WebAuthn-User bauen (wird NICHT persistiert):

```go
tmpUser := &webauthnUser{
    id:          []byte(username),
    name:        username,
    displayName: username,
    credentials: nil, // leer — noch keine Credentials
}
```

5. `wa.BeginRegistration(tmpUser)` → `options, sessionData`
6. `cs.Put(challenge, ChallengeEntry{SessionData: sessionData, UserID: username, Email: email, ExpiresAt: time.Now().Add(5*time.Minute)})`
7. HTTP 200 `{"publicKey": options}`

### Step 3: `PasskeyRegisterPublicFinishHandler` (~60 LoC, in `internal/handler/passkey.go`)

Endpunkt: `POST /api/auth/passkey/register/public/finish`

Ablauf:
1. Body-Größe auf 64 KB begrenzen: `http.MaxBytesReader(w, r.Body, 64*1024)`
2. Attestation-Response parsen via WebAuthn-Bibliothek: `parsedResponse, err := protocol.ParseCredentialCreationResponseBody(r.Body)`
3. Challenge aus `parsedResponse.Response.CollectedClientData.Challenge` extrahieren
4. `cs.Take(challenge)` → `nil` oder abgelaufen: HTTP 400 `{"error":"challenge_expired_or_missing"}`
5. Race-Schutz: `s.UserExists(entry.UserID)` → true: HTTP 409 `{"error":"user_already_exists"}`
6. Temporären User für Verifikation rekonstruieren (gleicher Aufbau wie in Begin, leere Credentials)
7. `wa.CreateCredential(tmpUser, entry.SessionData, parsedResponse)` — verifiziert Attestation; Fehler → HTTP 400 `{"error":"attestation_failed"}`
8. User anlegen:

```go
user := model.User{
    ID:                 entry.UserID,
    Email:              entry.Email,
    PasskeyCredentials: []webauthn.Credential{*credential},
    CreatedAt:          time.Now(),
    // PasswordHash: nicht gesetzt — omitempty
}
```

9. `s.SaveUser(user)`, `s.ProvisionUserDirs(entry.UserID)`
10. `gz_session`-Cookie setzen — identisch zu `PasskeyLoginFinishHandler` (HttpOnly, SameSite=Lax, MaxAge=86400, Secure bei HTTPS via `X-Forwarded-Proto`-Header)
11. HTTP 201 `{"id": entry.UserID}`

### Step 4: `internal/middleware/auth.go` — Exempt-Pfade (+2 Zeilen)

Beide Pfade zur bestehenden Exempt-Liste hinzufügen:
```
/api/auth/passkey/register/public/begin
/api/auth/passkey/register/public/finish
```

### Step 5: `cmd/server/main.go` — Routen + Rate-Limiter (+6 Zeilen)

```go
passkeyRegPubLimiter := authmw.NewIPRateLimiter(5, time.Hour)

r.Post("/api/auth/passkey/register/public/begin",
    passkeyRegPubLimiter(handler.PasskeyRegisterPublicBeginHandler(cfg, wa, cs, s)))
r.Post("/api/auth/passkey/register/public/finish",
    passkeyRegPubLimiter(handler.PasskeyRegisterPublicFinishHandler(cfg, wa, cs, s)))
```

Rate-Limit 5 req/h/IP entspricht dem bestehenden Limit von `/api/auth/register`.

### Step 6: `frontend/src/lib/passkey.ts` — `registerPasskeyPublic` (+50 LoC)

```typescript
export async function registerPasskeyPublic(
  username: string,
  email: string,
  label: string = username
): Promise<{ id: string }> {
  // 1. Begin: POST /api/auth/passkey/register/public/begin
  const beginRes = await fetch('/api/auth/passkey/register/public/begin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email }),
  });
  if (!beginRes.ok) throw new Error((await beginRes.json()).error);

  const { publicKey } = await beginRes.json();
  // 2. Base64url-dekodieren (challenge, user.id, excludeCredentials)
  const decodedOptions = decodePublicKeyCredentialCreationOptions(publicKey);
  // 3. Browser-Dialog öffnen
  const credential = await navigator.credentials.create({ publicKey: decodedOptions });
  if (!credential) throw new Error('no_credential');
  // 4. Finish: POST /api/auth/passkey/register/public/finish
  const finishRes = await fetch('/api/auth/passkey/register/public/finish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(encodeCredentialForTransmission(credential)),
  });
  if (!finishRes.ok) throw new Error((await finishRes.json()).error);
  return finishRes.json(); // { id: string }
}
```

`decodePublicKeyCredentialCreationOptions` und `encodeCredentialForTransmission` sind bestehende Hilfsfunktionen aus `passkey.ts` (analog zu Login-Flow).

### Step 7: `frontend/src/routes/register/+page.svelte` — Passkey-Toggle (+60 LoC)

Logik:
- State-Variable `passkeyMode = false`; WebAuthn-Feature-Detection via `isWebAuthnSupported()` (bereits in `passkey.ts`) beim Mount
- Wenn WebAuthn nicht unterstützt: Toggle-Button nicht anzeigen, nur Passwort-Registrierung
- Toggle-Button zeigt: "Stattdessen mit Passkey registrieren" / "Stattdessen mit Passwort registrieren"
- Im Passkey-Modus: Passwort-Felder ausgeblendet (`hidden`), `username`- und `email`-Felder bleiben sichtbar
- Button-Label im Passkey-Modus: "Mit Passkey registrieren"
- On submit im Passkey-Modus: kein Form-POST, stattdessen direkter JS-Aufruf:

```typescript
const result = await registerPasskeyPublic(username, email);
// Bei Erfolg: redirect zu /
window.location.href = '/';
```

- Fehlermeldungen aus geworfenen Errors anzeigen (`user_already_exists` → "Benutzername bereits vergeben", `validation_failed` → Feldfehler, sonstige → generischer Fehlertext)

### LoC-Budget

| Datei | Δ LoC |
|-------|-------|
| `internal/handler/passkey.go` | +130 |
| `internal/handler/challenge_store.go` | +1 |
| `internal/middleware/auth.go` | +2 |
| `cmd/server/main.go` | +6 |
| `frontend/src/lib/passkey.ts` | +50 |
| `frontend/src/routes/register/+page.svelte` | +60 |
| **Produktion gesamt** | **~249 LoC** |
| Tests | ~120 LoC |
| **Gesamt** | **~369 LoC** (LoC-Override auf 400 nötig) |

## Expected Behavior

- **Input (Begin):** `POST /api/auth/passkey/register/public/begin` mit `{"username":"alice","email":"alice@example.com"}`
- **Output (Begin, Erfolg):** HTTP 200 `{"publicKey": <WebAuthn-Credential-Creation-Options>}`; Challenge in ChallengeStore (TTL 5 Min) gespeichert, kein User angelegt
- **Input (Finish):** `POST /api/auth/passkey/register/public/finish` mit serialisiertem `PublicKeyCredential`-Objekt (max 64 KB)
- **Output (Finish, Erfolg):** HTTP 201 `{"id":"alice"}`; neues `user.json` in `data/users/alice/` ohne `PasswordHash`; `gz_session`-Cookie gesetzt (HttpOnly, SameSite=Lax, MaxAge=86400, Secure bei HTTPS); Challenge aus Store entfernt
- **Side effects:** `ProvisionUserDirs` legt Nutzer-Verzeichnisstruktur an; ChallengeStore-Eintrag wird nach Finish oder Ablauf (5 Min) durch bestehende GC entfernt

### Fehlerszenarien

| Szenario | HTTP | Error-Code |
|----------|------|------------|
| username < 3 oder > 50 Zeichen | 400 | `validation_failed` |
| email ohne `@` | 400 | `validation_failed` |
| username bereits vergeben (Begin) | 409 | `user_already_exists` |
| username zwischen Begin und Finish belegt (Race) | 409 | `user_already_exists` |
| Challenge nicht gefunden oder abgelaufen | 400 | `challenge_expired_or_missing` |
| Attestation-Verifikation schlägt fehl | 400 | `attestation_failed` |
| Body > 64 KB | 400 | `invalid_request` |
| Mehr als 5 req/h/IP | 429 | (IPRateLimiter) |

## Acceptance Criteria

**AC-1:** Given ein gültiger Benutzername (3–50 Zeichen) und eine gültige E-Mail-Adresse, und der Benutzername existiert noch nicht / When `POST /api/auth/passkey/register/public/begin` aufgerufen wird / Then antwortet der Server mit HTTP 200 und einem JSON-Body mit dem Schlüssel `publicKey`, der WebAuthn-Credential-Creation-Options enthält, und kein User-Objekt wurde persistiert.
  - Test: (populated after /tdd-red)

**AC-2:** Given ein Benutzername, der bereits als User-Verzeichnis in `data/users/` existiert / When `POST /api/auth/passkey/register/public/begin` aufgerufen wird / Then antwortet der Server mit HTTP 409 `{"error":"user_already_exists"}` und es wird kein Challenge-Eintrag im Store angelegt.
  - Test: (populated after /tdd-red)

**AC-3:** Given ein Benutzername mit weniger als 3 oder mehr als 50 Zeichen / When `POST /api/auth/passkey/register/public/begin` aufgerufen wird / Then antwortet der Server mit HTTP 400 `{"error":"validation_failed"}` ohne Seiteneffekte.
  - Test: (populated after /tdd-red)

**AC-4:** Given eine E-Mail-Adresse ohne `@`-Zeichen (z.B. `"noemail"`) / When `POST /api/auth/passkey/register/public/begin` aufgerufen wird / Then antwortet der Server mit HTTP 400 `{"error":"validation_failed"}` ohne Seiteneffekte.
  - Test: (populated after /tdd-red)

**AC-5:** Given eine gültige Attestation-Response, deren Challenge einem aktiven (nicht abgelaufenen) ChallengeEntry entspricht / When `POST /api/auth/passkey/register/public/finish` aufgerufen wird / Then wird ein neues `user.json` ohne `PasswordHash`-Feld angelegt, der Challenge-Eintrag aus dem Store entfernt, ein gültiger `gz_session`-Cookie gesetzt und HTTP 201 `{"id": username}` zurückgegeben.
  - Test: (populated after /tdd-red)

**AC-6:** Given eine Finish-Anfrage, deren Challenge nicht im Store vorhanden ist oder deren TTL von 5 Minuten abgelaufen ist / When `POST /api/auth/passkey/register/public/finish` aufgerufen wird / Then antwortet der Server mit HTTP 400 `{"error":"challenge_expired_or_missing"}` und es wird kein User angelegt.
  - Test: (populated after /tdd-red)

**AC-7:** Given der Benutzername aus einem gültigen ChallengeEntry wurde zwischen Begin und Finish von einem anderen Request belegt (Race Condition) / When `POST /api/auth/passkey/register/public/finish` aufgerufen wird / Then antwortet der Server mit HTTP 409 `{"error":"user_already_exists"}` und es wird kein zweiter User angelegt.
  - Test: (populated after /tdd-red)

**AC-8:** Given ein Besucher öffnet die Registrierungsseite in einem Browser mit WebAuthn-Unterstützung / When die Seite geladen wird / Then ist ein Toggle-Element sichtbar, das zwischen Passwort- und Passkey-Modus wechselt; im Passkey-Modus sind Passwort-Felder ausgeblendet und nur Benutzername sowie E-Mail-Adresse werden angezeigt.
  - Test: (populated after /tdd-red)

## Known Limitations

- **Keine sofortige Passkey-Geräteverknüpfung:** Abandonierte Begin-Aufrufe hinterlassen einen ChallengeStore-Eintrag, der nach 5 Minuten durch die bestehende ChallengeStore-GC aufgeräumt wird — kein gesonderter Cleanup-Goroutine nötig.
- **Kein persistenter Challenge-Store:** Bei Server-Neustart gehen offene Challenges verloren. Bei TTL von 5 Minuten ist das tolerierbar.
- **Browser-Kompatibilität:** WebAuthn wird ab iOS 16+, Android 9+ und allen modernen Desktop-Browsern unterstützt. Feature-Detection via `isWebAuthnSupported()` (bereits in `passkey.ts`) sorgt dafür, dass der Toggle nur bei kompatibler Umgebung erscheint.
- **LoC-Override nötig:** Produktions- + Test-Code überschreitet das Standard-250er-Limit; vor Phase 6 `workflow.py set-field loc_limit_override 400` ausführen.

## Changelog

- 2026-05-30: Initial spec erstellt für Issue #466 (Passkey V2 — passwortlose Registrierung für neue Nutzer). Scope: zwei neue Go-Endpunkte (Begin/Finish), `Email`-Feld in `ChallengeEntry`, Exempt-Pfade, Rate-Limiter, neue `registerPasskeyPublic`-Funktion in `passkey.ts`, Passkey-Toggle auf der Registrierungsseite. AC-1 bis AC-8 nach PO-Vorgabe im Given/When/Then-Format.
