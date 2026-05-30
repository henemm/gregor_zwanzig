# Context: Issue #467 — Discoverable Credentials + Conditional UI

## Request Summary

Passkey-Login ohne Username-Eingabe: Der Browser zeigt beim Klick auf das Username-Feld automatisch
verfügbare Passkeys als Autofill-Vorschlag an (Conditional UI / `mediation: 'conditional'`). Der User
wählt seinen Account direkt aus dem Browser-Picker — keine manuelle Username-Eingabe nötig.

## Eltern-Feature

Issue #450 (Passkey V1 Add-on) ist live auf `main` (Commit `6d3969b`). V1 implementiert
Identifier-First-Flow (Username eingeben → Passkey-Button klicken). Issue #467 baut darauf auf.

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `internal/handler/passkey.go` | ERWEITERN: neuer Handler `PasskeyLoginDiscoverableBeginHandler` + `PasskeyLoginDiscoverableFinishHandler` |
| `internal/handler/passkey_test.go` | ERWEITERN: Tests für Discoverable-Login-Roundtrip + `makeAssertionResponseWithUserHandle()` |
| `internal/handler/challenge_store.go` | Keine Änderung — ChallengeStore passt ohne UserID-Vorbelegung |
| `internal/middleware/auth.go` | ERWEITERN: neuen Endpoint in Whitelist aufnehmen (`/api/auth/passkey/login/discoverable/begin`, `/finish`) |
| `cmd/server/main.go` | ERWEITERN: 2 neue Routen registrieren |
| `frontend/src/lib/passkey.ts` | ERWEITERN: `loginWithPasskeyConditional()`, `isConditionalMediationAvailable()` |
| `frontend/src/routes/login/+page.svelte` | ERWEITERN: `onMount`-Init für Conditional UI, `autocomplete="username webauthn"` am Username-Feld |

## Vorhandene Muster

### Backend — go-webauthn v0.17.4 API

```go
// 1. BeginDiscoverableLogin (kein User nötig):
assertion, sessionData, err := wa.BeginDiscoverableLogin()
// oder mit mediation:
assertion, sessionData, err := wa.BeginDiscoverableMediatedLogin(protocol.MediationConditional)

// 2. FinishDiscoverableLogin mit DiscoverableUserHandler-Callback:
type DiscoverableUserHandler func(rawID, userHandle []byte) (user webauthn.User, err error)
// → Library ruft Callback mit credentialID + userHandle auf; Handler muss User laden

// 3. Aktuelle PasskeyLoginFinishHandler-Besonderheit:
parsedResponse.Response.UserHandle = nil  // zeile 216 — MUSS für Discoverable ENTFERNT werden
// Bei Discoverable kommt UserHandle vom Authenticator (= UserID), nicht vom Server-State
```

**Wichtig:** `DiscoverableUserHandler` erhält `rawID` (Credential-ID) und `userHandle` (= `WebAuthnID()` = UserID als `[]byte`). Der Store muss User per UserID ladbar sein — `s.LoadUser(string(userHandle))` reicht.

### Frontend — Conditional UI Pattern

```typescript
// Feature-Detection (async!):
const available = await PublicKeyCredential.isConditionalMediationAvailable?.() ?? false;

// Conditional Get — löst beim Autofill aus, NICHT beim Button-Klick:
const credential = await get({
  publicKey: { ...options.publicKey },
  mediation: 'conditional'  // ← key difference
});

// Username-Feld braucht autocomplete:
<input autocomplete="username webauthn" />
```

### Existierende Test-Infrastruktur

`passkey_test.go` hat bereits:
- `testAuthenticator` — ECDSA-P-256, baut echte AttestationResponse + AssertionResponse
- `makeAssertionResponse()` — setzt `"userHandle": base64url("placeholder")` (muss für echte Tests UserID setzen)
- `newTestStore(t)`, `authedRequest()`, `newTestWebAuthn()` — alle wiederverwendbar

Für Discoverable-Tests muss `makeAssertionResponse` eine Variante mit korrektem `userHandle` (= echte UserID als `[]byte`, base64url-kodiert) haben, da `ValidatePasskeyLogin` den Callback mit dem UserHandle aufruft.

### ChallengeStore

`ChallengeEntry.UserID` wird bei Discoverable-Begin LEER gelassen (kein User bekannt). Die UserID
kommt erst beim Finish aus dem `DiscoverableUserHandler`-Callback.

## API-Unterschied V1 (Identifier-First) vs. V3 (Discoverable)

| Aspekt | V1 (Issue #450) | V3 (Issue #467) |
|--------|----------------|----------------|
| Begin-Endpoint | `/api/auth/passkey/login/begin` (POST, Username im Body) | `/api/auth/passkey/login/discoverable/begin` (POST, kein Body) |
| Library-Call | `wa.BeginLogin(user)` | `wa.BeginDiscoverableLogin()` oder `BeginDiscoverableMediatedLogin(MediationConditional)` |
| Finish-Endpoint | `/api/auth/passkey/login/finish` | `/api/auth/passkey/login/discoverable/finish` |
| Finish-Logik | `wa.ValidateLogin(user, ...)` + `UserHandle = nil` | `wa.ValidatePasskeyLogin(handler, ...)` — handler lädt User via userHandle |
| Frontend-Trigger | Button-Klick nach Username-Eingabe | Browser-Autofill am Username-Feld (onMount-Init) |
| mediation | implicit (default) | `'conditional'` |

## Abhängigkeiten

- **Upstream:** go-webauthn v0.17.4 (bereits vorhanden), `internal/store.LoadUser`, `internal/middleware.SignSession`
- **Downstream:** `cmd/server/main.go` Routing, `frontend/src/routes/login/+page.svelte`
- **Auth-Whitelist:** `internal/middleware/auth.go` Zeile 34–40 — neue Discoverable-Endpoints müssen aufgenommen werden

## Spec-Referenzen

- Bestehende Passkey-Spec: `docs/specs/modules/passkey_webauthn.md` (Status: draft, V1 Add-on)
- Eltern-Context: `docs/context/issue-450-passkey.md`

## Risiken & Hinweise

1. **UserHandle MUSS erhalten bleiben:** `parsedResponse.Response.UserHandle = nil` (Zeile 216 in passkey.go)
   ist für den Discoverable-Handler FATAL — der neue Handler darf das NICHT setzen.
   Der V1-Handler bleibt unverändert.

2. **Feature-Detection ist async:** `PublicKeyCredential.isConditionalMediationAvailable()` gibt ein Promise
   zurück — im `onMount` mit `await` verwenden, synchroner Check reicht nicht.

3. **Nur EIN Conditional-Get gleichzeitig pro Seite:** Browser erlaubt nur einen aktiven Conditional-Flow.
   Bestehender Passkey-Button (explizit, V1) und Conditional-Flow (onMount) müssen koexistieren — bei
   aktiven Conditional-Flow den Button deaktivieren oder die Flows gegenseitig abbrechen (`AbortController`).

4. **Browser-Support:** Chrome 108+, Safari 16+, Firefox 119+. IE/alte Browser: graceful degradation
   (Conditional-Feature fehlt → Standard-Flow bleibt verfügbar, kein Fehler).

5. **LoC-Schätzung:** ~120 LoC (Backend ~60, Frontend ~60) — innerhalb des Default-Limits von 250.
