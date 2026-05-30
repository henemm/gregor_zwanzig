---
entity_id: issue_467_discoverable_credentials
type: module
created: 2026-05-30
updated: 2026-05-30
status: implemented
version: "1.0"
tags: [go, sveltekit, auth, webauthn, fido2, passkey, conditional-ui, discoverable-credentials, security]
---

<!-- Issue #467 — Passkey V3: Discoverable Credentials + Conditional UI (Login ohne Username) -->

# Passkey V3: Discoverable Credentials + Conditional UI

## Approval

- [ ] Approved

## Purpose

Passkey-Login ohne vorherige Username-Eingabe. Der Browser zeigt beim Fokus auf das Username-Feld alle für diese Domain gespeicherten Passkeys als nativen Autofill-Vorschlag an (Conditional UI / `mediation: 'conditional'`); der User wählt seinen Account aus dem Browser-Picker ohne manuelle Eingabe. Dieser Ansatz setzt auf dem bestehenden V1-Passkey-Flow auf (Issue #450 live) und ergänzt zwei neue Backend-Endpoints sowie minimale Frontend-Änderungen, ohne den Identifier-First-Flow oder das Passwort-Login zu berühren.

## Source

- **File:** `internal/handler/passkey.go` (ERWEITERN) — 2 neue Handler-Funktionen: `PasskeyLoginDiscoverableBeginHandler` und `PasskeyLoginDiscoverableFinishHandler`
- **Identifier:** `PasskeyLoginDiscoverableBeginHandler`, `PasskeyLoginDiscoverableFinishHandler`

### Weitere betroffene Dateien

- **File:** `internal/handler/passkey_test.go` (ERWEITERN, +150–200 LoC) — Mock-freier Discoverable-Roundtrip mit dem vorhandenen ECDSA-P-256 Test-Authenticator
- **File:** `internal/middleware/auth.go` (ERWEITERN, ~+2 LoC) — 2 neue Pfade zur Auth-Whitelist (Zeile 40)
- **File:** `cmd/server/main.go` (ERWEITERN, ~+8 LoC) — 2 neue Routen mit `passkeyLimiter`
- **File:** `frontend/src/lib/passkey.ts` (ERWEITERN, ~+40 LoC) — neue Export-Funktion `loginWithDiscoverablePasskey`
- **File:** `frontend/src/routes/login/+page.svelte` (ERWEITERN, ~+20 LoC) — Conditional UI initialisieren via `onMount`, `autocomplete`-Attribut am Input

> **Schicht-Hinweis:** Der gesamte neue Server-Code liegt ausschliesslich in der **Go-API** (`internal/`, `cmd/`). SvelteKit-Frontend interagiert direkt mit den Go-Endpoints. Kein Python-Backend betroffen. Bestätigung per Grep: `PasskeyLoginBeginHandler` liegt in `internal/handler/passkey.go`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `github.com/go-webauthn/webauthn` v0.17.4 | go external (bereits vorhanden) | `BeginDiscoverableMediatedLogin`, `ValidatePasskeyLogin`, DiscoverableUserHandler-Callback |
| `internal/handler/challenge_store.go` | go package (bereits vorhanden) | `ChallengeStore.Put` / `ChallengeStore.Take` für destruktive Challenge-Einlösung mit 5-Min-TTL |
| `internal/middleware/auth.go` — `SignSession()` | go package (bereits vorhanden) | Session-Cookie nach erfolgreichem Login setzen — identisches Format wie V1 |
| `internal/store` — `LoadUser` / `SaveUser` | go package (bereits vorhanden) | User-Lookup per `userHandle` ([]byte → string) im DiscoverableUserHandler-Callback |
| `internal/middleware/ratelimit.go` — `passkeyLimiter` | go package (bereits vorhanden) | Rate-Limit 30/h pro IP, identisch zu V1-Endpunkten |
| `@github/webauthn-json` | npm (bereits vorhanden) | Browser-API-Wrapper für Base64URL ↔ ArrayBuffer; `mediation`-Feld-Weiterleitung prüfen (ggf. direkter `navigator.credentials.get`-Aufruf) |
| `passkey_webauthn` Spec | spec (Issue #450) | V1-Basisarchitektur: ChallengeEntry-Schema, Session-Cookie-Format, Test-Authenticator-Pattern |

## Implementation Details

### Schritt 1: Backend — `PasskeyLoginDiscoverableBeginHandler` (~25 LoC)

Kein Request-Body nötig (kein Username).

```go
func PasskeyLoginDiscoverableBeginHandler(wa *webauthn.WebAuthn, cs *ChallengeStore) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // BeginDiscoverableMediatedLogin setzt "mediation":"conditional" im JSON-Response
        assertion, sessionData, err := wa.BeginDiscoverableMediatedLogin(protocol.MediationConditional)
        if err != nil {
            http.Error(w, `{"error":"begin_failed"}`, http.StatusInternalServerError)
            return
        }

        // UserID LEER LASSEN — Library wirft Error wenn gesetzt
        cs.Put(base64URLEncode(sessionData.Challenge), &ChallengeEntry{
            SessionData: *sessionData,
            UserID:      "",
            ExpiresAt:   time.Now().Add(5 * time.Minute),
        })

        // VOLLSTÄNDIGES assertion-Objekt serialisieren (NICHT nur assertion.Response)
        // V1-Begin-Handler kodiert falsch nur map[string]any{"publicKey": assertion.Response}
        // — das würde "mediation":"conditional" kappen
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(assertion)
    }
}
```

**Kritischer Unterschied zu V1:** Das vollständige `assertion`-Objekt muss serialisiert werden, damit `"mediation":"conditional"` im JSON erhalten bleibt. Der V1-Handler für `PasskeyLoginBeginHandler` kodiert nur `map[string]any{"publicKey": assertion.Response}` — das ist für Conditional UI falsch.

### Schritt 2: Backend — `PasskeyLoginDiscoverableFinishHandler` (~55 LoC)

```go
func PasskeyLoginDiscoverableFinishHandler(s store.Store, wa *webauthn.WebAuthn, cs *ChallengeStore, secret string) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // 1. Body parsen
        parsedResponse, err := protocol.ParseCredentialRequestResponseBody(r.Body)
        if err != nil {
            http.Error(w, `{"error":"invalid_credentials"}`, http.StatusUnauthorized)
            return
        }

        // 2. Challenge extrahieren + Store-Lookup (destruktiv)
        challenge := base64URLEncode(parsedResponse.Response.CollectedClientData.Challenge)
        entry, ok := cs.Take(challenge)
        if !ok {
            http.Error(w, `{"error":"invalid_credentials"}`, http.StatusUnauthorized)
            return
        }

        // 3. KRITISCH: KEIN parsedResponse.Response.UserHandle = nil
        //    V1 setzt das bewusst für Identifier-First — hier wäre es fatal,
        //    da der Browser userHandle als einzigen Nutzeridentifier liefert

        // 4. DiscoverableUserHandler-Callback: User per userHandle laden
        discoverableHandler := func(rawID, userHandle []byte) (webauthn.User, error) {
            user, err := s.LoadUser(string(userHandle))
            if err != nil {
                return nil, fmt.Errorf("user not found")
            }
            return user, nil
        }

        // 5. Validierung
        user, credential, err := wa.ValidatePasskeyLogin(discoverableHandler, entry.SessionData, parsedResponse)
        if err != nil {
            http.Error(w, `{"error":"invalid_credentials"}`, http.StatusUnauthorized)
            return
        }

        // 6. SignCount + LastUsedAt aktualisieren
        updateCredential(user.(*model.User), credential)
        s.SaveUser(*user.(*model.User))

        // 7. Session-Cookie setzen — identisch zu V1
        userID := user.WebAuthnName()
        http.SetCookie(w, middleware.SignSession(userID, secret))
        w.Header().Set("Content-Type", "application/json")
        json.NewEncoder(w).Encode(map[string]string{"id": userID})
    }
}
```

### Schritt 3: Middleware-Whitelist (`internal/middleware/auth.go`, Zeile 40, +2 LoC)

```go
"/api/auth/passkey/discoverable/begin",
"/api/auth/passkey/discoverable/finish",
```

Diese Pfade müssen in der Auth-Whitelist stehen, da Discoverable-Login per Definition ohne aktive Session aufgerufen wird.

### Schritt 4: Route-Registrierung (`cmd/server/main.go`, nach Zeile 121, +8 LoC)

```go
// Discoverable Passkey (öffentlich, kein Auth-Middleware)
r.Post("/api/auth/passkey/discoverable/begin",
    passkeyLimiter.Middleware(handler.PasskeyLoginDiscoverableBeginHandler(webAuthn, challengeStore)))
r.Post("/api/auth/passkey/discoverable/finish",
    passkeyLimiter.Middleware(handler.PasskeyLoginDiscoverableFinishHandler(s, webAuthn, challengeStore, cfg.SessionSecret)))
```

Vorhandener `passkeyLimiter` (30/h) wird wiederverwendet — keine neue Limiter-Instanz nötig.

### Schritt 5: Frontend — `frontend/src/lib/passkey.ts` (~+40 LoC)

```typescript
export async function loginWithDiscoverablePasskey(signal?: AbortSignal): Promise<void> {
    // Begin: kein Body
    const beginRes = await fetch('/api/auth/passkey/discoverable/begin', { method: 'POST' });
    if (!beginRes.ok) throw new Error('begin_failed');
    const options = await beginRes.json();

    // Prüfen ob @github/webauthn-json das mediation-Feld weitergibt.
    // Falls nicht (Library-Version ohne mediation-Support), direkter API-Aufruf:
    const credential = await navigator.credentials.get({
        publicKey: options.publicKey,
        mediation: 'conditional' as CredentialMediationRequirement,
        signal,
    });

    // Finish
    const finishRes = await fetch('/api/auth/passkey/discoverable/finish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(credentialToJSON(credential as PublicKeyCredential)),
    });
    if (!finishRes.ok) throw new Error('invalid_credentials');
    window.location.assign('/');
}
```

### Schritt 6: Frontend — `frontend/src/routes/login/+page.svelte` (~+20 LoC)

**Zwingend: `autocomplete`-Attribut** am Username-Input (ohne dieses Attribut zeigt kein Browser den Autofill-Picker):

```svelte
<input
  type="text"
  name="username"
  bind:value={username}
  autocomplete="username webauthn"
/>
```

**`onMount`-Initialisierung mit AbortController-Pattern:**

```svelte
<script>
  import { onMount } from 'svelte';
  import { loginWithDiscoverablePasskey } from '$lib/passkey';

  let conditionalController: AbortController | null = null;

  async function startConditionalUI() {
    const available = await PublicKeyCredential.isConditionalMediationAvailable?.() ?? false;
    if (!available) return;
    conditionalController = new AbortController();
    try {
      await loginWithDiscoverablePasskey(conditionalController.signal);
    } catch (e) {
      if ((e as DOMException)?.name !== 'AbortError') {
        // echte Fehler loggen, AbortError bei Button-Klick ignorieren
        console.error('Conditional UI error:', e);
      }
    }
  }

  onMount(() => { startConditionalUI(); });

  async function handleV1PasskeyClick() {
    // V1-Button: erst Conditional abbrechen, dann Identifier-First-Flow
    conditionalController?.abort();
    await loginWithPasskey(username);
    // nach V1-Abschluss Conditional neu starten
    startConditionalUI();
  }
</script>
```

Feature-Detection via `PublicKeyCredential.isConditionalMediationAvailable?.()` ist async — nicht synchron über `isWebAuthnSupported()` ersetzen. Auf Browsern ohne Conditional UI (Firefox < 119, ältere Safari) ist `isConditionalMediationAvailable` nicht definiert — daher optionale Chaining + `?? false`.

### Schritt 7: Tests (`internal/handler/passkey_test.go`, +150–200 LoC)

Kein Mock — vorhandenen ECDSA-P-256 Test-Authenticator aus `passkey_test.go` wiederverwenden (Setup-Funktion extrahieren falls nötig). Test-Reihenfolge:

1. **Discoverable-Begin:** POST ohne Body → HTTP 200, Response enthält `"mediation":"conditional"`, Challenge ist im ChallengeStore
2. **Discoverable-Finish (Erfolg):** Test-Authenticator konstruiert AuthenticatorData mit userHandle = User-ID, signiert mit privKey → HTTP 200, `Set-Cookie: gz_session`, `user.json` hat aktualisiertes `LastUsedAt`
3. **Leerer userHandle:** parsedResponse liefert leeren `userHandle` → DiscoverableUserHandler gibt Fehler → HTTP 401
4. **Unbekannter userHandle:** `userHandle` zeigt auf nicht-existenten User → HTTP 401
5. **Challenge-Replay:** Gleiche Challenge zweimal einlösen → zweiter Aufruf HTTP 401 (ChallengeStore.Take ist destruktiv)
6. **Abgelaufene Challenge:** `entry.ExpiresAt` in Vergangenheit (manuell im Test manipulieren) → HTTP 401

**LoC-Override-Hinweis:** Tests sind 150–200 LoC. Wenn Workflow-Gate meldet, dass LoC-Limit überschritten ist: `workflow.py set-field loc_limit_override 400`.

## Expected Behavior

- **Input (Discoverable Begin):** `POST /api/auth/passkey/discoverable/begin` — kein Body, keine Auth
- **Output (Discoverable Begin):** HTTP 200 JSON mit vollständigem assertion-Objekt; Top-Level enthält `"mediation":"conditional"` und `"publicKey"` mit Challenge
- **Input (Discoverable Finish):** `POST /api/auth/passkey/discoverable/finish` — JSON `AuthenticatorAssertionResponse` mit `userHandle` vom Browser
- **Output (Discoverable Finish):** HTTP 200 `{"id":"<userID>"}` + `Set-Cookie: gz_session=<userId>.<ts>.<hmac>; HttpOnly; SameSite=Lax; MaxAge=86400; Path=/; Secure` (bei HTTPS)
- **Side effects:** `user.json` wird bei erfolgreichem Login (SignCount, LastUsedAt) neu geschrieben; ChallengeStore-Entry wird nach `Take()` gelöscht (Replay-Schutz)

### Fehlerszenarien

| Szenario | HTTP | Response |
|---|---|---|
| Discoverable Begin: Library-Fehler | 500 | `{"error":"begin_failed"}` |
| Discoverable Finish: Body nicht parsebar | 401 | `{"error":"invalid_credentials"}` |
| Discoverable Finish: Challenge nicht im Store / abgelaufen | 401 | `{"error":"invalid_credentials"}` |
| Discoverable Finish: userHandle leer oder User nicht gefunden | 401 | `{"error":"invalid_credentials"}` |
| Discoverable Finish: Signatur-Verifikation fehlgeschlagen | 401 | `{"error":"invalid_credentials"}` |
| Rate-Limit (30/h pro IP) überschritten | 429 | `{"error":"rate_limit_exceeded"}`, Header `Retry-After` |

## Acceptance Criteria

- **AC-1:** Given ein Browser mit registriertem Passkey für diese Domain und ein frisches Login-Formular / When der Discoverable-Begin-Endpoint ohne Body aufgerufen wird / Then antwortet die API HTTP 200 mit einem JSON-Objekt das auf Top-Level `"mediation":"conditional"` enthält und dessen `publicKey.challenge` eine gültige Base64URL-kodierte Challenge ist, die im ChallengeStore mit 5-Min-TTL abgelegt wurde

- **AC-2:** Given eine gültige Challenge wurde via Discoverable-Begin ausgegeben und ein Test-Authenticator hat AuthenticatorData mit korrektem `userHandle` und gültiger ECDSA-P-256-Signatur konstruiert / When der Discoverable-Finish-Endpoint aufgerufen wird / Then antwortet die API HTTP 200 mit `{"id":"<userID>"}`, setzt einen `gz_session`-Cookie im Format `<userId>.<timestamp>.<hmac>` mit Flags `HttpOnly; SameSite=Lax; MaxAge=86400`, und das Feld `last_used_at` des verwendeten Credentials in `user.json` ist auf den aktuellen Zeitpunkt aktualisiert

- **AC-3:** Given der Discoverable-Finish-Endpoint wird mit einem leeren `userHandle` (leer oder null) aufgerufen / When die API den DiscoverableUserHandler-Callback ausführt / Then gibt der Handler einen Fehler zurück, die API antwortet HTTP 401 mit `{"error":"invalid_credentials"}`, kein Cookie wird gesetzt, und `user.json` bleibt unverändert

- **AC-4:** Given eine Challenge wurde via Discoverable-Begin erfolgreich eingelöst (Finish HTTP 200) / When dieselbe Challenge ein zweites Mal an Discoverable-Finish gesendet wird / Then antwortet die API HTTP 401 (ChallengeStore.Take ist destruktiv: nach erstem Take ist der Eintrag gelöscht), kein Cookie wird gesetzt

- **AC-5:** Given ein Browser unterstützt `PublicKeyCredential.isConditionalMediationAvailable` und der User hat einen registrierten Passkey für diese Domain / When die Login-Seite geladen wird und `onMount` ausführt / Then wird `loginWithDiscoverablePasskey` mit einem AbortController-Signal aufgerufen, das Username-Input-Feld hat `autocomplete="username webauthn"`, und der Browser zeigt den Passkey-Autofill-Picker beim Fokussieren des Felds an

- **AC-6:** Given das Username-Input-Feld auf der Login-Seite / When der DOM-Quelltext geprüft wird / Then hat das Input-Element das Attribut `autocomplete="username webauthn"` — ohne dieses Attribut zeigt kein Browser den Conditional-UI-Picker an

## Known Limitations

- **Kein userHandle-Padding:** Bei unbekanntem userHandle wird sofort 401 zurückgegeben. Kein Timing-Padding gegenüber gültigem userHandle — konsistent mit V1-Verhalten (kein Padding).
- **Conditional UI nur auf unterstützten Browsern:** Chrome 108+, Safari 16+, Edge 108+. Firefox unterstützt Conditional UI erst ab Version 119 (experimentell). Feature-Detection greift, der Flow fällt auf V1 (Identifier-First) zurück.
- **AbortController-Koexistenz mit V1-Button:** Wenn der User den V1-Passkey-Button klickt während Conditional UI aktiv ist, wird der Conditional-Flow zuerst abgebrochen. Nach V1-Abschluss startet Conditional neu. Kurzes Race-Window zwischen Abort und Neustart ist akzeptabel.
- **Restart-Verlust laufender Discoverable-Sessions:** Identisch zu V1 — der In-Memory ChallengeStore überlebt keinen Server-Neustart. User startet erneut.

## Changelog

- 2026-05-30: Initial spec — V3 Discoverable Credentials + Conditional UI, aufbauend auf Issue #450 (V1 live), basierend auf Phase-2-Analyse
