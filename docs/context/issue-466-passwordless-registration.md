# Context: Issue #466 — Passkey V2: Passwordless-Neuregistrierung

## Request Summary

Ein neuer User kann sich mit Passkey statt Passwort registrieren: Er gibt nur einen Benutzernamen ein, der Browser öffnet den OS-Passkey-Dialog, und das Konto wird ohne PasswordHash angelegt. Magic Link (#449, ✅ live) dient als Recovery-Pfad bei Geräteverlust.

## Related Files

| Datei | Relevanz |
|-------|----------|
| `internal/handler/passkey.go` | Bestehende Passkey-Handler (V1, auth-geschützt). Zwei neue „public"-Varianten nötig |
| `internal/handler/auth.go` | `RegisterHandler` — Referenz für Registrierungs-Validierung (Username 3–50 Zeichen) |
| `internal/handler/auth_magic.go` | Magic-Link-Referenz: createMagicLinkUser-Muster für neuen User ohne Passwort |
| `internal/middleware/auth.go` | `AuthMiddleware` — Exempt-Pfade; neue public-Endpoints müssen hinein |
| `internal/middleware/ratelimit.go` | `IPRateLimiter` — Rate-Limiter-Pattern (5 Req/Stunde wie `/api/auth/register`) |
| `internal/model/user.go` | `User.PasswordHash` ist bereits `omitempty` → passwordless-User sind modellseitig fertig |
| `internal/handler/challenge_store.go` | `ChallengeStore` — In-Memory mit TTL 5 Min + Take() |
| `cmd/server/main.go` | Routing, Rate-Limiter-Setup — neuen public-Endpoint registrieren |
| `frontend/src/routes/register/+page.svelte` | Aktuelle Registrierungs-Page (nur Passwort-Formular) |
| `frontend/src/routes/register/+page.server.ts` | Server-Action für Passwort-Registrierung |
| `frontend/src/lib/passkey.ts` | Frontend-Passkey-Client — neue Funktion `registerPasskeyPublic()` nötig |
| `internal/handler/passkey_test.go` | Test-Authenticator-Infrastruktur (ECDSA-P-256, "none"-Attestation) |

## Existing Patterns

- **Passkey-Register (auth-geschützt):** `PasskeyRegisterBeginHandler` + `PasskeyRegisterFinishHandler` — Challenge in ChallengeStore mit `UserID`, dann User laden + Credential anhängen
- **Neue User anlegen ohne Passwort:** `createMagicLinkUser` in `auth_magic.go` — `s.NewUserID()` + `store.SaveUser(model.User{ID: ..., Email: ..., CreatedAt: ...})`
- **Rate-Limiting:** `authmw.NewIPRateLimiter(5, time.Hour)` für Register-Endpoint — gleich für public-Passkey-Register
- **Username-Validierung:** `len(req.Username) < 3 || len(req.Username) > 50` in `RegisterHandler`
- **Auth-Middleware Exemption:** String-Vergleich auf `r.URL.Path` in `AuthMiddleware`
- **Lock-out-Schutz:** `PasskeyDeleteCredentialHandler` verweigert Löschen des letzten Passkeys wenn `user.PasswordHash == ""`

## Dependencies

- **Upstream:** `go-webauthn/webauthn` Library, `ChallengeStore`, `store.Store` (SaveUser/LoadUser/UserExists), `middleware.IPRateLimiter`
- **Downstream:** Frontend-Register-Page, `AuthMiddleware` (neue Exempt-Pfade), `cmd/server/main.go` (Routing)

## Existing Specs

- `docs/specs/modules/issue_449_magic_link.md` — Magic Link als Recovery-Pfad (live)
- Passkey V1 Spec: war Issue #450, kein separates Spec-Dokument vorhanden

## Key Architectural Decision

**Public-Endpoint-Paar:** Anstatt die bestehenden `/api/auth/passkey/register/begin|finish` zu erweitern (die Session voraussetzen), werden zwei neue Endpoints angelegt:
- `POST /api/auth/passkey/register/public/begin` — nimmt `{"username": "..."}`, prüft Verfügbarkeit, legt temporären User im ChallengeStore ab (noch kein DB-Eintrag!)
- `POST /api/auth/passkey/register/public/finish` — liest den User aus ChallengeStore, verifiziert Attestation, legt User dauerhaft an, setzt `gz_session`-Cookie

Vorteil: Kein User-Eintrag ohne fertigen Passkey. Kein Rollback nötig bei User-Abbruch.

## Risks & Considerations

1. **Username-Reservation:** Zwischen Begin und Finish könnte ein anderer Request den gleichen Username registrieren. `store.UserExists()` vor `SaveUser` absichern.
2. **ChallengeStore-Missbrauch:** Public-Begin ohne Finish hinterlässt eine Challenge (TTL 5 Min automatisch). Gleiches Pattern wie Login-Begin.
3. **Passwordless-User + Lock-out:** `PasskeyDeleteCredentialHandler` hat bereits den Guard (`user.PasswordHash == ""`). Kein Änderungsbedarf.
4. **Recovery-Pfad:** Magic Link (#449) funktioniert über E-Mail. Bei der Passkey-Registrierung sollte eine E-Mail optional erfasst werden (für Magic Link als Fallback).
5. **Frontend-Toggle:** Die Register-Page muss einen sauberen Wechsel zwischen Passwort- und Passkey-Modus zeigen. Der aktuelle Passwort-Flow bleibt unverändert.
