# Context: Issue #450 — Passkey als Anmelde-Methode (WebAuthn)

## Request Summary

Nutzer soll sich per Passkey (Face ID, Touch ID, Windows Hello — kurz: WebAuthn/FIDO2) anmelden können — ohne Passwort. Backend nutzt `github.com/go-webauthn/webauthn` (v0.17.4, aktiv gepflegt). Frontend nutzt die native Browser-API `navigator.credentials.create/get` (keine externe Bibliothek). Bestehende User können einen Passkey **zusätzlich** zum Passwort registrieren; reine Passkey-User bekommen User-ID `p-{8hex}`.

Begleit-Issue: #449 (Magic-Link per E-Mail) — gleiche Auth-Architektur, getrennt umzusetzen.

## Related Files

| File | Relevanz |
|------|----------|
| `internal/model/user.go` | User-Struct — wird um `PasskeyCredentials []WebAuthnCredential` (omitempty) erweitert. `PasswordHash` muss optional werden (Passkey-only-User haben keins). |
| `internal/handler/auth.go` | Bestehende Register/Login/Logout/Profile/Password-Handler — neue Handler kommen daneben (`PasskeyRegisterBeginHandler`, `PasskeyRegisterFinishHandler`, `PasskeyLoginBeginHandler`, `PasskeyLoginFinishHandler`). |
| `internal/middleware/auth.go` | `SignSession(userId, secret)` → erzeugt das HMAC-Session-Token nach erfolgreichem Passkey-Login (identisches Cookie-Format `gz_session`). |
| `internal/middleware/ratelimit.go` | IP-basiertes Rate-Limit-Pattern (Token-Bucket, `X-Real-IP`) — analog für Passkey-Begin-Endpoints anwenden. |
| `internal/store/user.go` | `LoadUser`/`SaveUser` → speichern Credentials direkt in `user.json` (additives Feld). Kein separates `passkeys.json` nötig — passt zum bestehenden Persistenz-Pattern. |
| `cmd/server/main.go` | Route-Registrierung (`/api/auth/register`, `/api/auth/login` etc.) — hier neue Routen für Passkey-Flows eintragen + Rate-Limiter. |
| `internal/config/config.go` | Config-Struct — neue ENV-Variablen für WebAuthn-RP (RPID, RPDisplayName, RPOrigins). |
| `frontend/src/routes/login/+page.svelte` | Login-UI — neuer Button "Mit Passkey anmelden". |
| `frontend/src/routes/login/+page.server.ts` | Server-Action — bisher nur Username/Passwort-POST. Passkey-Flow läuft eigenständig (siehe unten). |
| `frontend/src/routes/account/+page.svelte` | Account-Seite — Passkey-Verwaltung (Liste + "Passkey hinzufügen" + "Passkey entfernen"). |
| `frontend/src/lib/auth.ts` | TS-Pendant zum Go-Session-Code (Sign/Verify) — unverändert; Cookie-Format bleibt gleich. |
| `go.mod` | Neue Dependency `github.com/go-webauthn/webauthn v0.17.x`. |
| `docs/specs/modules/user_auth_endpoints.md` | F13-Phase-2a Spec (Username/Passwort) — Referenz-Pattern für die neue Passkey-Spec. |
| `docs/specs/modules/account_page.md` | Account-Page-Spec — neue Sektion "Passkeys verwalten" muss spiegelnd dokumentiert werden. |

## Existing Patterns

### Pattern 1 — Session-Cookie ist auth-methoden-agnostisch
Sowohl Username/Passwort-Login als auch der zukünftige Passkey-Login enden im gleichen Schritt: `middleware.SignSession(userId, secret)` setzt das Cookie `gz_session={userId}.{ts}.{hmac}`. SvelteKit + Go Middleware validieren identisch. → Passkey ändert nur den Weg ZUM Token, nicht das Token-Format.

### Pattern 2 — Persistenz via JSON-Datei pro User
`data/users/{userId}/user.json` enthält das ganze User-Objekt. Neue Felder sind additiv mit `omitempty` (siehe `Email`, `MailTo`, `SignalPhone` etc.). → `PasskeyCredentials []WebAuthnCredential` passt nahtlos rein, keine Migration nötig.

### Pattern 3 — Rate-Limit per IP-Token-Bucket
`NewIPRateLimiter(N, time.Hour).Limit(handler)` ist die Standard-Wrapper-Funktion (siehe `main.go:64–80`). Werte: Register 5/h, Login 30/h. → Passkey-Begin sollte ebenfalls limitiert sein (Empfehlung: 30/h analog Login).

### Pattern 4 — Frontend: SvelteKit-Server-Action ruft Go-API + extrahiert Set-Cookie
`/login/+page.server.ts` macht `fetch → POST /api/auth/login`, parst `set-cookie`-Header von Go und setzt es selbst via `cookies.set(...)`. → Beim Passkey-Login muss der Browser DIREKT mit dem Go-Backend reden (`navigator.credentials.get()` braucht Browser-Kontext), das Set-Cookie kommt vom Go-Endpoint und SvelteKit lädt anschließend neu (`window.location = '/'`).

### Pattern 5 — Auth-Endpoints sind in `r.Group(...)` aufgeteilt
Öffentliche Routen (`/api/auth/login` etc.) sind VOR der `AuthMiddleware` registriert. Geschützte Routen (`/api/auth/profile`, `/api/auth/password`) NACH der Middleware-Aktivierung. → Passkey-Login-Endpoints sind öffentlich; Passkey-Registrierung für eingeloggte User ist geschützt.

### Pattern 6 — Mock-frei testen (CLAUDE.md PFLICHT)
Tests in `tests/` und `internal/handler/*_test.go` benutzen echte HTTP-Roundtrips gegen einen `httptest.NewServer`. → WebAuthn-Tests müssen mit echtem `webauthn.New(...)` und einer Test-RP-Config arbeiten (Challenge/Response-Roundtrip im Go-Test simulierbar via `go-webauthn/webauthn/testdata` oder selbstgebauter ECDSA-Schlüsselpaare).

## Dependencies

### Upstream (was Passkey-Auth nutzt)
- `golang.org/x/crypto` (schon vorhanden, für ECDSA-Verifikation)
- **NEU:** `github.com/go-webauthn/webauthn` (~v0.17.4)
- `crypto/rand` (Challenges)
- `internal/middleware.SignSession` (Cookie-Generierung)
- `internal/store.LoadUser/SaveUser` (Credential-Persistenz)

### Downstream (was Passkey-Auth braucht / produziert)
- Session-Cookie `gz_session` (gleiches Format wie Username/Passwort-Login)
- `/api/auth/profile` muss `has_passkey: bool` ausgeben (für Account-UI)
- Wenn `PasswordHash == ""` UND `len(PasskeyCredentials) > 0` → reiner Passkey-User; UI muss Passwort-Block ausblenden
- Account-Löschung (`DELETE /api/auth/account`) muss Credentials mit-löschen → bereits gegeben (`DeleteUser` entfernt das ganze Verzeichnis)

## Existing Specs

| Spec | Relevanz |
|------|----------|
| `docs/specs/modules/user_auth_endpoints.md` | F13 Phase 2a — Pattern-Vorlage für Endpoints + Validierung + Cookie. |
| `docs/specs/modules/account_page.md` | Account-Page — wo Passkey-Verwaltung eingehängt wird. |
| `docs/specs/modules/account_page_extend.md` | Account-Page-Extensions (Kanäle). |
| `docs/specs/modules/register_page.md` | Register-Page — Passkey könnte als Alternative direkt in der Registrierung angeboten werden (Folge-Issue, nicht in #450). |
| `docs/specs/modules/sveltekit_login_refactor.md` | SvelteKit-Login-Refactor — Passkey-Button passt in den Login-Flow ein. |
| `docs/specs/modules/logout_session_blacklist.md` | Logout-Mechanik — Passkey-Logout läuft GLEICH wie Passwort-Logout (Session-Blacklist). |

## Risks & Considerations

### Risiko 1 — RP-ID-Bindung (Domain) ist immutable je Credential
**Was:** WebAuthn-Credentials sind an die RP-ID (Domain) gebunden, mit der sie registriert wurden. Wenn wir staging.gregor20.henemm.com und gregor20.henemm.com beide unterstützen wollen, müssen wir RP-ID = `henemm.com` (Top-Domain) wählen — sonst funktioniert ein auf Staging registrierter Passkey nicht auf Prod.
**Mitigation:** PO-Entscheidung in Phase 3 (Spec): RP-ID = `gregor20.henemm.com` (nur Prod-Kontext, Staging nutzt separates User-Verzeichnis) ODER `henemm.com` (Top-Domain, Cross-Subdomain-tauglich). **Empfehlung Tech-Lead:** `gregor20.henemm.com` — Staging-Credentials sollen NICHT auf Prod funktionieren (Datenkontamination vermeiden).

### Risiko 2 — User-ID-Schema für Passkey-only-User
**Was:** Issue #450 erwähnt `p-{8hex}` für reine Passkey-User. Aktuell ist `User.ID` der vom User gewählte Username. Wenn ein User OHNE Username startet (reiner Passkey-Flow), muss das Backend eine ID generieren.
**Mitigation:** In Phase 3 entscheiden: Bietet das Frontend (a) einen Username + Passkey-Flow (User wählt Namen, registriert Passkey statt Passwort) ODER (b) einen "nur Passkey"-Flow (User gibt nichts ein, Backend generiert `p-xxxxxxxx`)? — **Empfehlung Tech-Lead:** Erstmal NUR (a) für #450 → bestehende User fügen Passkey hinzu ODER ein neuer User registriert sich mit Username + Passkey (kein Passwort). Variante (b) als Folge-Issue, weil sie UX-Fragen aufwirft (wie heißt der User in der UI?).

### Risiko 3 — Challenge-State persistieren
**Was:** WebAuthn ist ein 2-Schritt-Flow (Begin → Finish). Zwischen den Schritten muss das Backend die Challenge + erwartete Daten merken.
**Mitigation:** In-Memory `sync.Map` mit TTL 5 Min (`crypto/rand`-Challenge als Key) — analog zur Magic-Link-Lösung in #449. Bei Server-Restart verlieren laufende Registrierungen ihren State; akzeptabel (User wiederholt). Alternativ: Challenge im verschlüsselten Cookie ablegen.

### Risiko 4 — `PasswordHash` darf nicht mehr Pflicht sein
**Was:** Aktuell setzt `RegisterHandler` `PasswordHash` immer. Ein reiner Passkey-User hat keins. `LoginHandler` ruft `bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), ...)` — wenn das leer ist, gibt bcrypt einen Fehler zurück und der User wird mit "invalid credentials" abgewiesen. Das ist EHER GUT (Passwort-Login funktioniert nicht für Passkey-only-User), aber wir müssen sicherstellen, dass das `password_hash`-Feld JSON-`omitempty` markiert wird, damit reine Passkey-User keine leere String-Property haben.
**Mitigation:** `PasswordHash string \`json:"password_hash,omitempty"\`` — JSON-Tag-Änderung. Bestandsdaten bleiben kompatibel (alle haben einen Hash).

### Risiko 5 — Mehrere Credentials pro User
**Was:** Ein User kann mehrere Passkeys haben (Laptop + Phone + Backup-USB-Key). Das Datenmodell muss eine **Liste** unterstützen, nicht ein Einzelfeld.
**Mitigation:** `PasskeyCredentials []WebAuthnCredential`. Account-Page zeigt Liste mit "letzte Verwendung", "Erstell-Datum", "Entfernen"-Button pro Credential. (Variante: nur 1 Credential in #450, Mehrfach-Verwaltung als Folge-Issue.) → PO-Entscheidung Phase 3.

### Risiko 6 — Frontend-Browser-API erfordert direkten Kontakt zu Go-API
**Was:** `navigator.credentials.get()` läuft im Browser, nicht im SvelteKit-Server. Der Browser muss DIREKT mit `/api/auth/passkey/login/begin` und `/api/auth/passkey/login/finish` reden — nicht über die SvelteKit-Server-Action.
**Mitigation:** Login-UI nutzt `<script>`-Block mit `fetch(...)`, danach `window.location.assign('/')` zum Reload. Das Set-Cookie kommt direkt von Go. → SvelteKit-Server-Action ist für Passkey **nicht** zuständig (nur für klassisches Passwort).

### Risiko 7 — Bibliotheks-Wahl: `go-webauthn/webauthn` ist die richtige
**Was:** Issue gibt `github.com/go-webauthn/webauthn` als PFLICHT vor. Bestätigt: aktiv gepflegt, v0.17.x (Mai 2026), 1200+ Stars, Standard im Go-Ökosystem. Keine bessere Alternative bekannt (duo-labs ist eingestellt → forked nach go-webauthn).
**Mitigation:** Akzeptiert. `go get github.com/go-webauthn/webauthn@latest` in Phase 6.

### Risiko 8 — Tests ohne Mocks (CLAUDE.md PFLICHT)
**Was:** WebAuthn-Tests OHNE Browser sind aufwendig. Echte Challenges/Signaturen brauchen ein ECDSA-Schlüsselpaar im Test.
**Mitigation:** `github.com/go-webauthn/webauthn` bietet eigene Test-Helper (siehe `protocol/credential_test.go`). Alternativ: ein Test-Authenticator im Go-Code (eigenes ECDSA-Paar, signiert Challenge-Daten im Test, ruft `webauthn.FinishLogin(...)` mit dem signierten Assertion-Objekt auf). → Phase 5 (TDD-RED): zuerst Roundtrip-Test schreiben, dann Implementation.

### Risiko 9 — Schema-Daten-Reworks-Pflicht (CLAUDE.md)
**Was:** Änderungen an `internal/model/user.go` sind schema-relevant. Hook `data_schema_backup.py` triggert automatisch ein tar.gz-Backup von `data/users/`.
**Mitigation:** Korrekt. Backup läuft automatisch. **Zusätzlich:** Roundtrip-Test schreiben (load alt user.json → marshal → unmarshal → assert keine Daten-Diff), damit bestehende User nicht beim ersten Save ihre Felder verlieren.

### Risiko 10 — Issue #449 (Magic Link) ist parallel offen
**Was:** Beide Issues erweitern die Auth-Architektur. #450 ist deutlich komplexer.
**Mitigation:** Issue selbst sagt "sinnvoll als letztes umzusetzen". Vorschlag an PO: **Zuerst #449 (Magic Link, einfacher), dann #450 (Passkey).** Beide schreiben ins gleiche User-Modell → Reihenfolge wichtig, damit Modell-Änderungen nicht kollidieren.

## Phase 2 — Analyse-Ergebnisse

### Entscheidung: V1 (Add-on) — PO-bestätigt 2026-05-30

Bestehende User können auf der Account-Seite einen Passkey hinzufügen. Login-Screen erhält Button „Mit Passkey anmelden". Klassische Neuregistrierung (Username/Passwort) bleibt unverändert. Reine Passkey-Neuregistrierung und Discoverable Credentials sind explizit Folge-Issues.

### Architektur-Plan

**Backend (Go):**

| Endpoint | Methode | Auth | Rate-Limit | Zweck |
|---|---|---|---|---|
| `/api/auth/passkey/register/begin` | POST | ✅ Session | 30/h | Erzeugt Challenge + Options, speichert SessionData in `sync.Map` mit 5-Min-TTL |
| `/api/auth/passkey/register/finish` | POST | ✅ Session | 30/h | Verifiziert Attestation, fügt Credential zu `user.PasskeyCredentials` hinzu, persistiert |
| `/api/auth/passkey/login/begin` | POST | ❌ | 30/h (analog Login) | Lädt User, gibt `allowCredentials` aus, speichert SessionData |
| `/api/auth/passkey/login/finish` | POST | ❌ | 30/h | Verifiziert Assertion, ruft `middleware.SignSession`, setzt Cookie `gz_session` |
| `/api/auth/passkey/credentials` | DELETE | ✅ Session | 30/h | Entfernt einzelnes Credential aus `user.PasskeyCredentials` |

**Datenmodell-Erweiterung `internal/model/user.go`:**

```go
type User struct {
    // ...bestehende Felder...
    PasswordHash       string                  `json:"password_hash,omitempty"` // war Pflicht — wird omitempty
    PasskeyCredentials []WebAuthnCredential    `json:"passkey_credentials,omitempty"` // NEU
}

type WebAuthnCredential struct {
    ID              []byte    `json:"id"`                 // Credential-ID
    PublicKey       []byte    `json:"public_key"`         // COSE-encoded
    AttestationType string    `json:"attestation_type"`
    Transport       []string  `json:"transport,omitempty"`
    Flags           webauthn.CredentialFlags `json:"flags"`
    Authenticator   webauthn.Authenticator   `json:"authenticator"` // AAGUID, SignCount
    CreatedAt       time.Time `json:"created_at"`
    LastUsedAt      time.Time `json:"last_used_at,omitempty"`
    Label           string    `json:"label,omitempty"` // optional User-Label "MacBook", "iPhone"
}
```

`PasswordHash → omitempty` ist eine schema-relevante Änderung (Hook `data_schema_backup.py` greift) — JSON-rückwärtskompatibel, weil leere Strings ohnehin nicht serialisiert werden müssen.

**Config-Erweiterung `internal/config/config.go`:**

| ENV | Default | Beschreibung |
|---|---|---|
| `WEBAUTHN_RP_ID` | `gregor20.henemm.com` | Relying Party ID — bewusst NICHT Top-Domain (Staging-Isolation) |
| `WEBAUTHN_RP_DISPLAY_NAME` | `Gregor Zwanzig` | Anzeigename im Browser-Prompt |
| `WEBAUTHN_RP_ORIGINS` | `https://gregor20.henemm.com` (Prod), `https://staging.gregor20.henemm.com` (Staging) | Erlaubte Origins für `clientDataJSON.origin`-Check |

**Frontend (SvelteKit):**

| Datei | Änderung |
|---|---|
| `frontend/package.json` | Neue Dependency `@github/webauthn-json` (~3 KB minified, übernimmt Base64URL ↔ ArrayBuffer) |
| `frontend/src/routes/login/+page.svelte` | Button „Mit Passkey anmelden"; `<script>`-Block ruft `/api/auth/passkey/login/begin|finish` direkt; nach Success `window.location = '/'` |
| `frontend/src/routes/account/+page.svelte` | Sektion „Passkeys" mit Liste + Add-Button + Remove-pro-Eintrag |
| `frontend/src/lib/passkey.ts` (NEU) | Helper für Browser-API + Feature-Detection + Fehler-Handling |

**Test-Strategie (mock-frei, CLAUDE.md PFLICHT):**

- `internal/handler/passkey_test.go` — Test-Authenticator mit echtem ECDSA-P-256-Schlüsselpaar:
  1. `BeginRegistration` → Test extrahiert Challenge
  2. Test signiert mit privKey → konstruiert AttestationObject (CBOR-encoded) → ruft `FinishRegistration`
  3. Assert: User-JSON enthält Credential
  4. `BeginLogin` → Test extrahiert Challenge
  5. Test signiert mit demselben privKey → ruft `FinishLogin`
  6. Assert: Response setzt `gz_session`-Cookie im erwarteten Format `{userId}.{ts}.{hmac}`
- `internal/middleware/auth_test.go` — bleibt unverändert (Session-Format ist identisch zu Username/Passwort-Login)
- `frontend/e2e/passkey.spec.ts` — Playwright mit `virtualauthenticator` (Chrome DevTools Protocol) für E2E

### Datei-Liste & LoC-Schätzung

| Datei | Geschätzt LoC | Typ |
|---|---|---|
| `internal/model/user.go` | +25 | Erweiterung |
| `internal/config/config.go` | +10 | Erweiterung |
| `internal/handler/passkey.go` (NEU) | +180 | Neu |
| `internal/handler/passkey_test.go` (NEU) | +220 | Neu (Test, zählt aber zu LoC) |
| `internal/handler/auth.go` | +5 | Profile-Handler `has_passkey: bool` |
| `internal/store/user.go` | 0 | Keine Änderung (User-Objekt-Serialisierung bleibt) |
| `cmd/server/main.go` | +20 | 5 neue Routen + Rate-Limiter + WebAuthn-Init |
| `go.mod` / `go.sum` | (generiert) | `go get github.com/go-webauthn/webauthn` |
| `frontend/package.json` | +1 | `@github/webauthn-json` |
| `frontend/src/lib/passkey.ts` (NEU) | +80 | Browser-API-Helper |
| `frontend/src/routes/login/+page.svelte` | +40 | Passkey-Button + Script |
| `frontend/src/routes/account/+page.svelte` | +80 | Passkey-Sektion |
| `frontend/e2e/passkey.spec.ts` (NEU) | +60 | E2E-Test |
| `docs/specs/modules/passkey_webauthn.md` (NEU, in `docs/` → zählt nicht) | — | Spec |
| **Summe** | **~720 LoC** | |

**LoC-Override notwendig:** Default-Limit ist 250. Selbst ohne Tests/Generierte ist Source-LoC ~440 — `workflow.py set-field loc_limit_override 800` in Phase 6.

### Risiken — Aktualisierung nach Analyse

| Risiko (Phase 1) | Status nach Analyse |
|---|---|
| 1. RP-ID-Bindung | ✅ Entschieden: `gregor20.henemm.com` (Staging-Isolation) |
| 2. User-ID-Schema | ✅ Entschieden: V1 — kein `p-{8hex}`, nur bestehende User |
| 3. Challenge-State | ✅ Plan: In-Memory `sync.Map` mit 5-Min-TTL; Restart-Verlust akzeptabel |
| 4. `PasswordHash`-Pflicht | ✅ Plan: JSON-Tag `omitempty`, Code-Compat unverändert |
| 5. Mehrere Credentials | ✅ Entschieden: Liste ab Tag 1 |
| 6. Frontend Browser-API | ✅ Plan: `@github/webauthn-json` übernimmt Konvertierung |
| 7. Library-Wahl | ✅ Bestätigt: `go-webauthn/webauthn` v0.17.x |
| 8. Mock-freie Tests | ✅ Plan: Test-Authenticator mit ECDSA-P-256 + echte Library |
| 9. Schema-Backup | ✅ Hook greift automatisch beim Edit von `user.go` |
| 10. Reihenfolge mit #449 | ✅ Operativ entschieden: #450 zuerst (sind drin), #449 danach; Modell additiv kompatibel |

### Folge-Issues (NACH #450 anlegen)

1. **„Passwordless-Registrierung mit Passkey"** — V2 aus dem Vergleich; setzt voraus, dass #449 (Magic Link) als Recovery-Pfad live ist
2. **„Discoverable Credentials / Conditional UI"** — V3; Login ohne Username
3. **„Passkey-Label umbenennen"** — kleine UX-Erweiterung der Account-Seite

## Nächster Schritt

`/3-write-spec` — Spezifikation mit AC-N-Format erstellen (Pflicht laut CLAUDE.md, Workflow-Tools v3).
