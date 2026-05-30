---
entity_id: passkey_webauthn
type: module
created: 2026-05-30
updated: 2026-05-30
status: draft
version: "1.0"
tags: [go, sveltekit, multi-user, auth, webauthn, fido2, passkey, security]
---

<!-- Issue #450 — Passkey als Anmelde-Methode (WebAuthn) — V1 Add-on -->

# Passkey-Anmeldung (WebAuthn/FIDO2) — V1 Add-on

## Approval

- [ ] Approved

## Purpose

Bestehende, eingeloggte User können auf der Account-Seite einen Passkey (Face ID, Touch ID, Windows Hello — kurz: FIDO2-Credential) registrieren und sich danach ohne Passwort anmelden. Das klassische Username/Passwort-Login bleibt parallel vollständig erhalten und dient als Fallback bei Geräteverlust. Reine Passkey-Neuregistrierung (User ohne Passwort von Anfang an) und Discoverable Credentials (Login ohne Username) sind explizit Folge-Issues und nicht Teil dieser Spec.

## Source

- **File:** `internal/handler/passkey.go` **(NEU)** — Begin/Finish-Handler für Register und Login plus Credential-Delete
- **Identifier:** `PasskeyRegisterBeginHandler`, `PasskeyRegisterFinishHandler`, `PasskeyLoginBeginHandler`, `PasskeyLoginFinishHandler`, `PasskeyDeleteCredentialHandler`

### Weitere betroffene Dateien

- **File:** `internal/model/user.go` (ERWEITERT, +25 LoC) — `PasskeyCredentials []WebAuthnCredential` additiv; `PasswordHash` wird `omitempty`; neuer Sub-Struct `WebAuthnCredential`
- **File:** `internal/config/config.go` (ERWEITERT, +10 LoC) — neue ENV-Felder `WebAuthnRPID`, `WebAuthnRPDisplayName`, `WebAuthnRPOrigins`
- **File:** `internal/handler/auth.go` (ERWEITERT, +5 LoC) — Profile-Response erhält `has_passkey: bool` (Anzahl Credentials > 0)
- **File:** `cmd/server/main.go` (ERWEITERT, +25 LoC) — `webauthn.New(cfg)`-Instanz, 5 neue Routen, Rate-Limiter, Challenge-Store-Init
- **File:** `internal/handler/challenge_store.go` **(NEU, ~40 LoC)** — In-Memory `sync.Map` mit 5-Min-TTL für `webauthn.SessionData` zwischen Begin/Finish
- **File:** `internal/handler/passkey_test.go` **(NEU, ~220 LoC)** — Mock-freier Roundtrip mit Test-Authenticator (ECDSA-P-256)
- **File:** `go.mod` / `go.sum` (generiert) — neue Dependency `github.com/go-webauthn/webauthn` v0.17.x
- **File:** `frontend/package.json` (ERWEITERT, +1 Zeile) — `@github/webauthn-json` ~3 KB minified
- **File:** `frontend/src/lib/passkey.ts` **(NEU, ~80 LoC)** — Browser-API-Wrapper, Feature-Detection, Fehler-Handling
- **File:** `frontend/src/routes/login/+page.svelte` (ERWEITERT, +40 LoC) — Button „Mit Passkey anmelden"
- **File:** `frontend/src/routes/account/+page.svelte` (ERWEITERT, +80 LoC) — Sektion „Passkeys" mit Liste + Add + Remove
- **File:** `frontend/e2e/passkey.spec.ts` **(NEU, ~60 LoC)** — Playwright-E2E mit Virtual Authenticator (CDP)

> **Schicht-Hinweis:** Authentifizierungs-Server-Code liegt ausschliesslich in der **Go-API** (`internal/`, `cmd/`). SvelteKit-Frontend interagiert direkt mit den Go-Endpoints (kein Python). Bestätigung per Grep auf `RegisterHandler` und `LoginHandler` (alleinig in `internal/handler/auth.go`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `github.com/go-webauthn/webauthn` | go external (NEU, v0.17.x) | WebAuthn-Protokoll-Implementierung: CBOR-Decoding, Attestation- und Assertion-Verifikation, COSE-Public-Key-Handling |
| `golang.org/x/crypto/bcrypt` | go external (bereits vorhanden) | Bleibt für Username/Passwort-Login parallel aktiv |
| `crypto/rand` | go stdlib | Challenge-Erzeugung (Library handhabt das intern, kein direkter Aufruf nötig) |
| `sync` | go stdlib | `sync.Map` für In-Memory Challenge-Store mit TTL |
| `internal/store/user.go` | go package | `LoadUser`/`SaveUser` werden durch zusätzliches Feld nicht angepasst (additiv via JSON-Tags) |
| `internal/middleware/auth.go` | go package | `SignSession()` wird nach erfolgreichem Passkey-Login aufgerufen — identisches Cookie-Format wie Passwort-Login |
| `internal/middleware/ratelimit.go` | go package | `NewIPRateLimiter(30, time.Hour)` analog `/api/auth/login` |
| `@github/webauthn-json` | npm external (NEU, ~3 KB) | Browser-API-Wrapper: konvertiert Base64URL ↔ ArrayBuffer automatisch — vermeidet eigene Krypto-Glue |
| `user_auth_endpoints` Spec | spec | Bestehende Auth-Architektur (Session-Cookie-Format `{userId}.{ts}.{hmac}`, das Passkey-Login wiederverwendet) |
| `logout_session_blacklist` Spec | spec | Logout-Mechanik bleibt identisch — Passkey-User loggen sich gleich aus wie Passwort-User |

## Implementation Details

### Step 1: User-Modell erweitern (`internal/model/user.go`, +25 LoC)

```go
package model

import (
    "time"
    "github.com/go-webauthn/webauthn/webauthn"
)

type User struct {
    ID                 string                `json:"id"`
    Email              string                `json:"email,omitempty"`
    PasswordHash       string                `json:"password_hash,omitempty"` // war Pflicht — wird omitempty
    PasskeyCredentials []WebAuthnCredential  `json:"passkey_credentials,omitempty"` // NEU
    CreatedAt          time.Time             `json:"created_at"`
    MailTo             string                `json:"mail_to,omitempty"`
    SignalPhone        string                `json:"signal_phone,omitempty"`
    SignalAPIKey       string                `json:"signal_api_key,omitempty"`
    TelegramChatID     string                `json:"telegram_chat_id,omitempty"`
}

type WebAuthnCredential struct {
    ID              []byte                  `json:"id"`               // Credential-ID (raw bytes)
    PublicKey       []byte                  `json:"public_key"`       // COSE-encoded
    AttestationType string                  `json:"attestation_type"`
    Transport       []string                `json:"transport,omitempty"`
    Flags           webauthn.CredentialFlags `json:"flags"`
    Authenticator   webauthn.Authenticator   `json:"authenticator"`  // AAGUID, SignCount, CloneWarning
    CreatedAt       time.Time               `json:"created_at"`
    LastUsedAt      time.Time               `json:"last_used_at,omitempty"`
    Label           string                  `json:"label,omitempty"` // optional: "MacBook", "iPhone"
}

// WebAuthn-User-Interface (von go-webauthn/webauthn erwartet)
func (u *User) WebAuthnID() []byte           { return []byte(u.ID) }
func (u *User) WebAuthnName() string         { return u.ID }
func (u *User) WebAuthnDisplayName() string  { return u.ID }
func (u *User) WebAuthnCredentials() []webauthn.Credential {
    out := make([]webauthn.Credential, 0, len(u.PasskeyCredentials))
    for _, c := range u.PasskeyCredentials {
        out = append(out, webauthn.Credential{
            ID:              c.ID,
            PublicKey:       c.PublicKey,
            AttestationType: c.AttestationType,
            Transport:       toAuthenticatorTransports(c.Transport),
            Flags:           c.Flags,
            Authenticator:   c.Authenticator,
        })
    }
    return out
}
```

Rückwärtskompatibilität: bestehende `user.json`-Dateien haben kein `passkey_credentials`-Feld → JSON-Unmarshal setzt `nil`-Slice, `WebAuthnCredentials()` gibt leere Liste zurück.

`PasswordHash → omitempty`: leerer String wird nicht serialisiert. Bestehende User haben einen Hash → keine Änderung im JSON. Neue Passkey-only-User (Folge-Issues, nicht in V1) hätten kein Feld.

### Step 2: Config erweitern (`internal/config/config.go`, +10 LoC)

```go
type Config struct {
    // ...bestehende Felder...
    WebAuthnRPID          string `envconfig:"WEBAUTHN_RP_ID"           default:"localhost"`
    WebAuthnRPDisplayName string `envconfig:"WEBAUTHN_RP_DISPLAY_NAME" default:"Gregor Zwanzig"`
    WebAuthnRPOrigins     string `envconfig:"WEBAUTHN_RP_ORIGINS"      default:"http://localhost:5173"` // Komma-getrennt
}
```

**Werte im Betrieb (gesetzt in den Systemd-Service-ENV-Files in `henemm-infra`):**

- Production (`gregor-api.service`): `WEBAUTHN_RP_ID=gregor20.henemm.com`, `WEBAUTHN_RP_ORIGINS=https://gregor20.henemm.com`
- Staging (`gregor-api-staging.service`): `WEBAUTHN_RP_ID=staging.gregor20.henemm.com`, `WEBAUTHN_RP_ORIGINS=https://staging.gregor20.henemm.com`
- Lokal: Defaults (`localhost` / `http://localhost:5173`)

Bewusste Entscheidung: NICHT `henemm.com` als RP-ID — Staging-Credentials sollen auf Prod nicht funktionieren (Datenkontamination vermeiden).

### Step 3: WebAuthn-Instanz initialisieren (`cmd/server/main.go`, +12 LoC)

```go
import "github.com/go-webauthn/webauthn/webauthn"

origins := strings.Split(cfg.WebAuthnRPOrigins, ",")
for i := range origins { origins[i] = strings.TrimSpace(origins[i]) }

webAuthn, err := webauthn.New(&webauthn.Config{
    RPID:          cfg.WebAuthnRPID,
    RPDisplayName: cfg.WebAuthnRPDisplayName,
    RPOrigins:     origins,
})
if err != nil { log.Fatalf("webauthn init: %v", err) }

challengeStore := handler.NewChallengeStore() // sync.Map mit 5-Min-TTL
```

### Step 4: Challenge-Store (`internal/handler/challenge_store.go` NEU, ~40 LoC)

```go
package handler

import (
    "sync"
    "time"
    "github.com/go-webauthn/webauthn/webauthn"
)

type ChallengeEntry struct {
    SessionData webauthn.SessionData
    UserID      string
    ExpiresAt   time.Time
}

type ChallengeStore struct {
    m sync.Map // key: challenge-base64url string → *ChallengeEntry
}

func NewChallengeStore() *ChallengeStore {
    cs := &ChallengeStore{}
    go cs.gc() // Hintergrund-Cleanup alle Minute
    return cs
}

func (cs *ChallengeStore) Put(challenge string, entry *ChallengeEntry) {
    cs.m.Store(challenge, entry)
}

func (cs *ChallengeStore) Take(challenge string) (*ChallengeEntry, bool) {
    v, ok := cs.m.LoadAndDelete(challenge)
    if !ok { return nil, false }
    e := v.(*ChallengeEntry)
    if time.Now().After(e.ExpiresAt) { return nil, false }
    return e, true
}

func (cs *ChallengeStore) gc() {
    for range time.Tick(time.Minute) {
        now := time.Now()
        cs.m.Range(func(k, v any) bool {
            if now.After(v.(*ChallengeEntry).ExpiresAt) {
                cs.m.Delete(k)
            }
            return true
        })
    }
}
```

Restart-Verlust akzeptabel: User wiederholt die Registrierung — Browser-Prompt taucht erneut auf.

### Step 5: Passkey-Handler (`internal/handler/passkey.go` NEU, ~180 LoC)

**PasskeyRegisterBeginHandler(s, wa, cs):** (Auth-pflichtig — eingeloggter User)

1. UserID aus Context (`middleware.UserIDFromContext`)
2. `s.LoadUser(userID)` → 404 falls nicht gefunden
3. `options, sessionData, err := wa.BeginRegistration(user)` — Library erzeugt Challenge + Options
4. `cs.Put(base64.URLEncoding.EncodeToString(sessionData.Challenge), &ChallengeEntry{SessionData: *sessionData, UserID: userID, ExpiresAt: time.Now().Add(5*time.Minute)})`
5. JSON-Response `{"publicKey": options.Response}` (Library liefert Base64URL-konformes Format)

**PasskeyRegisterFinishHandler(s, wa, cs):** (Auth-pflichtig)

1. UserID aus Context; `s.LoadUser(userID)`
2. Body lesen und mit `protocol.ParseCredentialCreationResponseBody(r.Body)` parsen
3. Challenge aus `parsedResponse.Response.CollectedClientData.Challenge` extrahieren
4. `entry, ok := cs.Take(challenge)` → 400 falls nicht vorhanden/abgelaufen oder `entry.UserID != userID`
5. `credential, err := wa.CreateCredential(user, entry.SessionData, parsedResponse)` → 400 bei Verifikations-Fehler
6. Neuer `model.WebAuthnCredential` mit `CreatedAt: time.Now()`, optionalem `Label` aus Request-Body, an `user.PasskeyCredentials` anhängen
7. `s.SaveUser(*user)` → 500 bei IO-Fehler
8. JSON 201 `{"id": base64url(credential.ID), "label": label, "created_at": time}`

**PasskeyLoginBeginHandler(s, wa, cs):** (öffentlich)

1. Body `{"username": string}`
2. `s.LoadUser(username)` — bei Nichtexistenz oder leerer `PasskeyCredentials`-Liste **trotzdem** mit gestellter Dummy-Challenge antworten? **Nein** — wir geben 401 `{"error":"invalid credentials"}` zurück (gleicher Code wie Passwort-Login). Akzeptiertes Trade-off: schwacher User-Enumeration-Vektor existiert bereits beim Passwort-Login (`bcrypt` braucht ~200ms auch bei fehlendem User → wir simulieren das hier nicht, da die Library schnell antwortet — Wartezeit-Padding über `time.Sleep` mit `cryptorand`-Jitter optional, NICHT in V1)
3. `options, sessionData, err := wa.BeginLogin(user)` (mit `allowCredentials` aus `user.WebAuthnCredentials()`)
4. `cs.Put(base64(sessionData.Challenge), &ChallengeEntry{SessionData: *sessionData, UserID: username, ExpiresAt: +5min})`
5. JSON `{"publicKey": options.Response}`

**PasskeyLoginFinishHandler(s, wa, cs, secret):** (öffentlich)

1. Body parsen mit `protocol.ParseCredentialRequestResponseBody(r.Body)`
2. Challenge extrahieren, `cs.Take(challenge)` → 401 falls weg
3. `s.LoadUser(entry.UserID)` → 401 falls weg
4. `credential, err := wa.ValidateLogin(user, entry.SessionData, parsedResponse)` → 401 bei Fehler
5. `SignCount` auf entsprechendem `WebAuthnCredential` aktualisieren, `LastUsedAt = time.Now()`, `s.SaveUser(*user)`
6. Cookie `gz_session = middleware.SignSession(entry.UserID, secret)` mit identischen Flags wie Passwort-Login
7. JSON 200 `{"id": entry.UserID}`

**PasskeyDeleteCredentialHandler(s):** (Auth-pflichtig)

1. UserID aus Context; URL-Param `?credential_id=<base64url>` oder Body
2. `s.LoadUser(userID)`; Credential mit passender ID aus `PasskeyCredentials` herausfiltern
3. **Sicherheits-Check:** Falls `user.PasswordHash == ""` UND es das letzte verbleibende Credential ist → 400 `{"error":"cannot_remove_last_passkey_without_password"}`. In V1 ist `PasswordHash` immer gesetzt → Check ist vorsorglich für Folge-Issues.
4. `s.SaveUser(*user)` → 200 `{"status":"deleted"}`

### Step 6: Profile-Erweiterung (`internal/handler/auth.go`, +5 LoC)

`GetProfileHandler` ergänzt Response-Feld `"has_passkey": len(user.PasskeyCredentials) > 0` und `"passkeys": [{id,label,created_at,last_used_at}, ...]` (ohne Public-Key — nicht für Client gedacht). Frontend nutzt das für UI-Status.

### Step 7: Route-Registrierung (`cmd/server/main.go`, +13 LoC)

```go
passkeyLimiter := authmw.NewIPRateLimiter(30, time.Hour)

// Öffentlich
r.Post("/api/auth/passkey/login/begin",
    passkeyLimiter.Middleware(handler.PasskeyLoginBeginHandler(s, webAuthn, challengeStore)))
r.Post("/api/auth/passkey/login/finish",
    passkeyLimiter.Middleware(handler.PasskeyLoginFinishHandler(s, webAuthn, challengeStore, cfg.SessionSecret)))

// In authentifizierter Gruppe (nach AuthMiddleware)
r.Group(func(r chi.Router) {
    r.Use(authmw.AuthMiddleware(cfg.SessionSecret))
    r.Post("/api/auth/passkey/register/begin",
        passkeyLimiter.Middleware(handler.PasskeyRegisterBeginHandler(s, webAuthn, challengeStore)))
    r.Post("/api/auth/passkey/register/finish",
        passkeyLimiter.Middleware(handler.PasskeyRegisterFinishHandler(s, webAuthn, challengeStore)))
    r.Delete("/api/auth/passkey/credentials/{id}",
        handler.PasskeyDeleteCredentialHandler(s))
})
```

### Step 8: Frontend-Wrapper (`frontend/src/lib/passkey.ts` NEU, ~80 LoC)

```typescript
import { create, get, parseCreationOptionsFromJSON, parseRequestOptionsFromJSON }
    from '@github/webauthn-json/browser-ponyfill';

export function isWebAuthnSupported(): boolean {
    return typeof window !== 'undefined' && !!window.PublicKeyCredential;
}

export async function registerPasskey(label: string): Promise<{ id: string; label: string }> {
    const beginRes = await fetch('/api/auth/passkey/register/begin', { method: 'POST', credentials: 'include' });
    if (!beginRes.ok) throw new Error('begin_failed');
    const options = parseCreationOptionsFromJSON(await beginRes.json());

    const credential = await create(options); // navigator.credentials.create()

    const finishRes = await fetch('/api/auth/passkey/register/finish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ ...credential.toJSON(), label })
    });
    if (!finishRes.ok) throw new Error('finish_failed');
    return finishRes.json();
}

export async function loginWithPasskey(username: string): Promise<void> {
    const beginRes = await fetch('/api/auth/passkey/login/begin', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username })
    });
    if (!beginRes.ok) throw new Error('invalid_credentials');
    const options = parseRequestOptionsFromJSON(await beginRes.json());

    const credential = await get(options); // navigator.credentials.get()

    const finishRes = await fetch('/api/auth/passkey/login/finish', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(credential.toJSON())
    });
    if (!finishRes.ok) throw new Error('invalid_credentials');
    window.location.assign('/'); // Cookie ist gesetzt, SvelteKit-Layout lädt neu
}
```

Fehler-Mapping: `NotAllowedError` (User-Abbruch) → UI zeigt "Anmeldung abgebrochen"; `TimeoutError` → "Zeitüberschreitung, bitte erneut versuchen"; Server-401 → "Kein passender Passkey gefunden".

### Step 9: Login-Seite erweitern (`frontend/src/routes/login/+page.svelte`, +40 LoC)

Bestehender Username/Passwort-Block bleibt unverändert. Darunter neuer Bereich:

```svelte
{#if webAuthnSupported}
  <div class="separator">oder</div>
  <button on:click={handlePasskey} disabled={!username}>
    🔑 Mit Passkey anmelden
  </button>
  {#if passkeyError}<p class="error">{passkeyError}</p>{/if}
{/if}
```

`onMount`-Hook setzt `webAuthnSupported = isWebAuthnSupported()`. `handlePasskey` ruft `loginWithPasskey(username)` — der Browser zeigt den Authenticator-Prompt.

### Step 10: Account-Seite erweitern (`frontend/src/routes/account/+page.svelte`, +80 LoC)

Neue Sektion zwischen „Persönliche Daten" und „Passwort ändern":

```svelte
<section>
  <h2>Passkeys</h2>
  <p>Sichere Anmeldung ohne Passwort — z.B. mit Face ID, Touch ID oder Windows Hello.</p>

  {#each passkeys as pk}
    <div class="passkey-row">
      <strong>{pk.label || 'Unbenanntes Gerät'}</strong>
      <small>registriert {formatDate(pk.created_at)}</small>
      {#if pk.last_used_at}<small>zuletzt verwendet {formatDate(pk.last_used_at)}</small>{/if}
      <button on:click={() => removePasskey(pk.id)}>Entfernen</button>
    </div>
  {/each}

  {#if webAuthnSupported}
    <input bind:value={newLabel} placeholder="z.B. MacBook" />
    <button on:click={addPasskey}>+ Passkey hinzufügen</button>
  {/if}
</section>
```

`addPasskey` ruft `registerPasskey(newLabel)`, danach Liste via `/api/auth/profile` aktualisieren. `removePasskey` ruft `DELETE /api/auth/passkey/credentials/{id}`.

### Step 11: Tests (`internal/handler/passkey_test.go` NEU, ~220 LoC)

Mock-freier Roundtrip — Test agiert als Authenticator:

1. **Setup:** `webauthn.New(&webauthn.Config{RPID:"localhost",RPOrigins:[]string{"http://localhost"}})`, `t.TempDir()`-Store, User mit ECDSA-P-256-Keypair
2. **Register-Test:**
   a. `PasskeyRegisterBeginHandler` aufrufen → Challenge aus Response extrahieren
   b. Test-Authenticator: ClientDataJSON konstruieren (`{type:"webauthn.create", challenge:<b64>, origin:"http://localhost"}`), AttestationObject mit „none"-Format und unserem ECDSA-Public-Key (COSE-encoded)
   c. `PasskeyRegisterFinishHandler` aufrufen mit JSON-Response des konstruierten Credentials
   d. Assert: HTTP 201, `s.LoadUser(id).PasskeyCredentials` enthält 1 Eintrag mit unserem Public-Key
3. **Login-Test:**
   a. `PasskeyLoginBeginHandler` mit Username → Challenge aus Response
   b. Test-Authenticator: AuthenticatorData + ClientDataJSON konstruieren, mit privKey signieren (ECDSA P-256)
   c. `PasskeyLoginFinishHandler` aufrufen mit JSON
   d. Assert: HTTP 200, `Set-Cookie: gz_session=alice.<ts>.<hmac>`
4. **Negative Tests:**
   a. Falsche Challenge → 401 (CT erfindet eigene)
   b. Abgelaufene Challenge (manuell `cs.Take` triggern, dann ablaufen lassen) → 401
   c. Fremder UserID-Mismatch bei Register-Finish → 400
   d. Rate-Limit: 31. Request gegen `/login/begin` aus selber IP → 429
5. **Credential-Delete:**
   a. User mit Passkey + Passwort → Delete erfolgreich
   b. User mit Passkey OHNE Passwort UND nur 1 Credential → 400 (Lock-out-Schutz)

`frontend/e2e/passkey.spec.ts` (60 LoC) nutzt Playwright `cdpSession.send('WebAuthn.enable')` + `addVirtualAuthenticator` für E2E mit echtem Browser-Roundtrip ohne Hardware-Authenticator.

## Expected Behavior

- **Input (Register Begin):** `POST /api/auth/passkey/register/begin` mit gültigem `gz_session`-Cookie, leerer Body
- **Output (Register Begin):** HTTP 200 `{"publicKey": {challenge:"<b64url>", user:{id,name,displayName}, pubKeyCredParams:[...], ...}}`
- **Input (Register Finish):** `POST /api/auth/passkey/register/finish` mit Cookie + JSON `{id, rawId, response:{clientDataJSON, attestationObject}, type, label?}`
- **Output (Register Finish):** HTTP 201 `{"id":"<b64url>","label":"MacBook","created_at":"2026-05-30T12:00:00Z"}`; `data/users/{id}/user.json` enthält neuen Eintrag in `passkey_credentials`
- **Input (Login Begin):** `POST /api/auth/passkey/login/begin` ohne Cookie, JSON `{"username":"alice"}`
- **Output (Login Begin):** HTTP 200 `{"publicKey": {challenge, allowCredentials:[{id:"<b64url>", type:"public-key"}, ...], ...}}`
- **Input (Login Finish):** `POST /api/auth/passkey/login/finish` ohne Cookie, JSON-Assertion vom Browser
- **Output (Login Finish):** HTTP 200 `{"id":"alice"}` + `Set-Cookie: gz_session=alice.{ts}.{hmac}; HttpOnly; SameSite=Lax; MaxAge=86400; Path=/; Secure (auf HTTPS)`
- **Input (Delete):** `DELETE /api/auth/passkey/credentials/{id}` mit Cookie
- **Output (Delete):** HTTP 200 `{"status":"deleted"}`
- **Side effects:** `user.json` wird bei Register-Finish und Delete und Login-Finish (SignCount-Update) neu geschrieben; Challenge-Store als In-Memory `sync.Map` mit 5-Min-TTL

### Fehlerszenarien

| Szenario | HTTP Status | Response |
|---|---|---|
| Register Begin: kein Cookie / abgelaufenes Session | 401 | (von `AuthMiddleware`) |
| Register Finish: Challenge nicht im Store | 400 | `{"error":"challenge_expired_or_missing"}` |
| Register Finish: Library-Verifikation fehlgeschlagen | 400 | `{"error":"attestation_invalid"}` |
| Login Begin: User existiert nicht oder hat keine Passkeys | 401 | `{"error":"invalid_credentials"}` |
| Login Finish: Signatur ungültig | 401 | `{"error":"invalid_credentials"}` |
| Login Finish: Challenge abgelaufen | 401 | `{"error":"invalid_credentials"}` |
| Delete: letzter Passkey eines Passwort-losen Users | 400 | `{"error":"cannot_remove_last_passkey_without_password"}` |
| Rate-Limit überschritten (alle Endpoints) | 429 | `{"error":"rate_limit_exceeded"}`, Header `Retry-After: <sec>` |

## Acceptance Criteria

- **AC-1:** Given ein eingeloggter User ohne registrierten Passkey / When er auf der Account-Seite den Begin-Endpoint aufruft, mit seinem Test-Authenticator die Challenge signiert und Finish aufruft / Then liefert die API HTTP 201, das User-Objekt enthält genau einen Eintrag in `passkey_credentials` mit dem gelieferten Public-Key, das Profile-Endpoint gibt `has_passkey: true` zurück, und `data/users/{id}/user.json` enthält das neue Credential persistiert
  - Test: (populated after /tdd-red)

- **AC-2:** Given ein User mit registriertem Passkey und ohne aktive Session / When er via `/api/auth/passkey/login/begin` mit seinem Username eine Challenge anfordert, mit seinem Authenticator signiert und Finish aufruft / Then liefert die API HTTP 200 mit Body `{"id":"<username>"}`, setzt einen `gz_session`-Cookie im Format `<userId>.<timestamp>.<hmacSig>` mit `HttpOnly`, `SameSite=Lax`, `MaxAge=86400` und `Secure` (bei HTTPS-Origin), und das Credential-Feld `last_used_at` ist auf jetzt aktualisiert
  - Test: (populated after /tdd-red)

- **AC-3:** Given ein bestehender User mit `password_hash`-Feld und keinem Passkey / When ein Passkey hinzugefügt wird und danach das User-JSON neu serialisiert wird / Then bleibt das `password_hash`-Feld unverändert vorhanden, das neue Feld `passkey_credentials` enthält genau einen Eintrag, kein anderes bestehendes Feld (Email, MailTo, SignalPhone, SignalAPIKey, TelegramChatID, CreatedAt) wurde entfernt oder verändert
  - Test: (populated after /tdd-red)

- **AC-4:** Given eine Challenge wurde via Begin ausgegeben / When 6 Minuten später (oder ohne Begin) Finish aufgerufen wird, oder wenn dieselbe Challenge zweimal eingelöst wird / Then liefert die API HTTP 400 (Register) bzw. 401 (Login) mit Error-Code `challenge_expired_or_missing` bzw. `invalid_credentials`, kein User-State wird verändert, kein Cookie wird gesetzt
  - Test: (populated after /tdd-red)

- **AC-5:** Given dieselbe IP-Adresse hat innerhalb einer Stunde 30 erfolgreiche Requests an einen Passkey-Endpoint gestellt / When der 31. Request erfolgt / Then liefert die API HTTP 429 mit Body `{"error":"rate_limit_exceeded"}` und Header `Retry-After` > 0, unabhängig davon ob der eigentliche Request gültig wäre
  - Test: (populated after /tdd-red)

- **AC-6:** Given ein User mit Passwort und einem registrierten Passkey / When er `DELETE /api/auth/passkey/credentials/{id}` mit gültiger Session aufruft / Then liefert die API HTTP 200, das User-Objekt enthält keinen Passkey mehr, das Profile-Endpoint gibt `has_passkey: false` zurück, das `password_hash` bleibt unverändert (Login per Passwort weiterhin möglich)
  - Test: (populated after /tdd-red)

- **AC-7:** Given die Frontend-Login-Seite wird in einem Browser ohne WebAuthn-Support geladen / When `isWebAuthnSupported()` `false` zurückgibt / Then ist der Button „Mit Passkey anmelden" NICHT im DOM sichtbar, das klassische Username/Passwort-Formular bleibt voll funktionsfähig, und es entstehen keine JavaScript-Konsolen-Fehler
  - Test: (populated after /tdd-red)

- **AC-8:** Given Production-Konfiguration `WEBAUTHN_RP_ID=gregor20.henemm.com` und Staging-Konfiguration `WEBAUTHN_RP_ID=staging.gregor20.henemm.com` / When ein User registriert einen Passkey auf Staging und versucht damit auf Production einzuloggen / Then schlägt der Login fehl (RP-ID-Mismatch in der Library-Validierung), und es wird HTTP 401 `invalid_credentials` zurückgegeben — Staging und Production sind isoliert
  - Test: (populated after /tdd-red) — als dokumentiertes Integrations-Verhalten; im Unit-Test über zwei `webauthn.Config`-Instanzen abgebildet

## Known Limitations

- **Restart-Verlust laufender Registrierungen:** Der In-Memory Challenge-Store überlebt keinen Server-Neustart. Ein User, der während eines Deploys gerade „+ Passkey hinzufügen" geklickt hat, bekommt einen Fehler und muss erneut starten. Akzeptabel im Vergleich zu Persistierungs-Aufwand.
- **Kein User-Enumeration-Padding bei Login-Begin:** Wir geben sofort 401 zurück wenn der User nicht existiert oder keine Passkeys hat. Antwortzeit unterscheidet sich messbar von einem erfolgreichen Begin (Library-Aufruf entfällt). Das ist konsistent mit dem bestehenden Passwort-Login (kein Padding bei `bcrypt`-Mismatch); bei Bedarf in eigenem Issue addressieren.
- **Kein Discoverable-Credentials-Pfad:** Login erfordert weiterhin Username-Eingabe (Identifier-First). Echter passwordless Flow mit Conditional UI ist explizit Folge-Issue.
- **Kein Recovery-Pfad ausserhalb Passwort:** V1 lebt davon, dass jeder User noch ein Passwort hat. Ein Passkey-only-User wäre bei Geräteverlust ausgeschlossen — daher V1 NICHT für Passkey-only-User. Folge-Issue „Passwordless-Registrierung" setzt voraus, dass #449 (Magic Link) als Recovery-Pfad live ist.
- ~~**AAGUID-Display nicht in V1:** Die Account-Liste zeigt nur das User-vergebene `Label`. Eine Übersetzung von AAGUID zu „YubiKey 5", „iCloud Keychain", „Windows Hello" etc. ist möglich (`go-webauthn/aaguid`-Mappings), aber nicht in V1 — UX-Verbesserung als Folge-Issue.~~ **RESOLVED in Issue #468:** AAGUID-Mapping lebt jetzt in `internal/handler/aaguid.go`; GET `/api/auth/profile` liefert Passkey-Felder mit optionalem `authenticator_name`. Frontend zeigt kombiniert `"{authenticator_name} · {label}"` an.
- **Browser-Support auf älteren iOS-Versionen:** WebAuthn ist auf iOS 16+ verfügbar, ältere Geräte zeigen den Button nicht (Feature-Detection greift). Akzeptable Einschränkung; das klassische Login bleibt.

## Changelog

- 2026-05-30: Known Limitation „AAGUID-Display" (zeile 461) marked RESOLVED: Issue #468 liefert Authenticator-Name-Mapping über `internal/handler/aaguid.go` + Profile-Response-Feld `authenticator_name`.
- 2026-05-30: Initial spec — V1 Add-on (PO-bestätigt), basierend auf Phase-1-Kontext + Phase-2-Analyse aus `docs/context/issue-450-passkey.md`
