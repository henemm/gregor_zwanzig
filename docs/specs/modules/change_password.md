---
entity_id: change_password
type: module
created: 2026-04-16
updated: 2026-04-16
status: draft
version: "1.0"
tags: [go, sveltekit, auth, account, password, f71]
---

# F71 — Passwort ändern (Account-Seite + Go-Endpoint)

## Approval

- [ ] Approved

## Purpose

Ermoeglicht authentifizierten Nutzern, ihr Passwort direkt auf der `/account`-Seite zu aendern, indem sie ihr aktuelles und ein neues Passwort eingeben. Das Feature besteht aus einem neuen Go-Endpoint `PUT /api/auth/password` sowie einer neuen Formular-Sektion auf dem Frontend, die zwischen den bestehenden "Kanaele"- und "Gefahrenzone"-Cards erscheint.

## Source

- **File (Backend):** `internal/handler/auth.go` **(EDIT, +35 LoC)**
- **Identifier (Backend):** `ChangePasswordHandler`
- **File (Route):** `cmd/server/main.go` **(EDIT, +1 LoC)**
- **File (Frontend):** `frontend/src/routes/account/+page.svelte` **(EDIT, +40 LoC)**
- **Identifier (Frontend):** `changePassword` (neue Funktion)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/middleware` — `UserIDFromContext` | Go middleware | Liest die authentifizierte User-ID aus dem Request-Kontext |
| `internal/store.Store` — `LoadUser` | Go store method | Laedt den Nutzer-Datensatz anhand der User-ID |
| `internal/store.Store` — `SaveUser` | Go store method | Schreibt den aktualisierten Nutzer-Datensatz (mit neuem Passwort-Hash) zurueck |
| `golang.org/x/crypto/bcrypt` | Go library | `CompareHashAndPassword` zur Verifikation des alten Passworts; `GenerateFromPassword` zum Hashen des neuen Passworts; bereits in `auth.go` importiert |
| `PUT /api/auth/password` | Go API endpoint | Wird vom Frontend aufgerufen; validiert und persistiert die Passwortaenderung |
| `$lib/api.ts` — `api.put()` | SvelteKit helper | Sendet den authenticated PUT-Request mit `old_password` und `new_password` |

## Implementation Details

### Backend: `ChangePasswordHandler` in `internal/handler/auth.go`

Pattern folgt dem bestehenden `ResetPasswordHandler` in derselben Datei.

**Request-Struktur:**
```go
type changePasswordRequest struct {
    OldPassword string `json:"old_password"`
    NewPassword string `json:"new_password"`
}
```

**Handler-Logik (sequenzielle Schritte):**
```
1. UserIDFromContext(r.Context()) → userId; fehlt userId → 401
2. json.NewDecoder(r.Body).Decode(&req) → Fehler → 400 {"error":"invalid request"}
3. len(req.NewPassword) < 8 → 400 {"error":"validation failed"}
4. store.LoadUser(userId) → Fehler → 500 {"error":"internal error"}
5. bcrypt.CompareHashAndPassword(user.PasswordHash, req.OldPassword) → Mismatch → 403 {"error":"wrong password"}
6. bcrypt.GenerateFromPassword(req.NewPassword, bcrypt.DefaultCost) → Fehler → 500 {"error":"internal error"}
7. user.PasswordHash = newHash; store.SaveUser(user) → Fehler → 500 {"error":"internal error"}
8. 200 {"status":"ok"}
```

**Route-Registrierung in `cmd/server/main.go`:**
```go
mux.Handle("PUT /api/auth/password", authMiddleware(handler.ChangePasswordHandler(store)))
```

### Frontend: Passwort-Sektion in `frontend/src/routes/account/+page.svelte`

Die neue Card wird nach der "Kanaele"-Card und vor der "Gefahrenzone"-Card eingefuegt.

**Neuer Svelte-5-State (isoliert vom Profil-Speichern):**
```typescript
let oldPassword = $state('');
let newPassword = $state('');
let confirmPassword = $state('');
let pwSuccessMsg = $state<string | null>(null);
let pwErrorMsg = $state<string | null>(null);
```

**Markup-Block:**
```html
<Card.Root>
  <Card.Header>
    <Card.Title>Passwort ändern</Card.Title>
  </Card.Header>
  <Card.Content class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700">Aktuelles Passwort</label>
      <input type="password" bind:value={oldPassword}
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm ..." />
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700">Neues Passwort</label>
      <input type="password" bind:value={newPassword}
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm ..." />
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700">Neues Passwort bestätigen</label>
      <input type="password" bind:value={confirmPassword}
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm ..." />
    </div>
    {#if pwSuccessMsg}
      <p class="text-sm text-green-600">{pwSuccessMsg}</p>
    {/if}
    {#if pwErrorMsg}
      <p class="text-sm text-red-600">{pwErrorMsg}</p>
    {/if}
    <button onclick={changePassword}
      class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md">
      Passwort ändern
    </button>
  </Card.Content>
</Card.Root>
```

**`changePassword()`-Funktion:**
```typescript
async function changePassword() {
    pwSuccessMsg = null;
    pwErrorMsg = null;

    if (newPassword !== confirmPassword) {
        pwErrorMsg = 'Die neuen Passwörter stimmen nicht überein';
        return;
    }

    try {
        await api.put('/api/auth/password', {
            old_password: oldPassword,
            new_password: newPassword,
        });
        pwSuccessMsg = 'Passwort geändert';
        oldPassword = '';
        newPassword = '';
        confirmPassword = '';
    } catch (e: unknown) {
        const body = (e as { status?: number; error?: string });
        if (body?.status === 403) {
            pwErrorMsg = 'Aktuelles Passwort ist falsch';
        } else {
            pwErrorMsg = body?.error ?? 'Passwort ändern fehlgeschlagen';
        }
    }
}
```

## Expected Behavior

- **Input:** Authentifizierter Nutzer gibt aktuelles Passwort, neues Passwort und Bestaetigung ein und klickt "Passwort aendern".
- **Output (Erfolg):** Gruener Banner "Passwort geaendert", alle drei Felder werden geleert. Backend gibt `200 {"status":"ok"}` zurueck und persistiert den neuen bcrypt-Hash.
- **Output (Fehler):** Roter Banner mit spezifischer Fehlermeldung; Felder bleiben befuellt.
- **Side effects:** Der neue bcrypt-Hash wird in der Nutzerdatenbank gespeichert. Bestehende Sessions anderer Geraete bleiben aktiv (kein erzwungenes Logout aller Sessions — ausserhalb des Scopes).

### Fehlerszenarien

| Szenario | Frontend | Backend |
|----------|----------|---------|
| Neue Passwoerter stimmen nicht ueberein | "Die neuen Passwörter stimmen nicht überein" (kein API-Call) | — |
| Neues Passwort zu kurz (< 8 Zeichen) | Fehlermeldung aus API-Response | 400 `{"error":"validation failed"}` |
| Aktuelles Passwort falsch | "Aktuelles Passwort ist falsch" | 403 `{"error":"wrong password"}` |
| Malformed JSON | Fehlermeldung aus API-Response | 400 `{"error":"invalid request"}` |
| bcrypt- oder Store-Fehler | Fehlermeldung aus API-Response | 500 `{"error":"internal error"}` |
| Nicht authentifiziert | Fehlermeldung aus API-Response | 401 |

## Known Limitations

- Bestehende Sessions anderer Geraete werden nach Passwortaenderung nicht invalidiert. Ein vollstaendiges Session-Revoke waere sicherer, ist aber nicht Teil dieses Scopes.
- Kein Passwort-Staerke-Indikator im Frontend — nur Mindestlaenge 8 Zeichen wird geprueft.
- Client-seitiger Check (Passwoerter stimmen ueberein) verhindert vermeidbare API-Calls, ersetzt aber nicht die Server-seitige Validierung.

## Changelog

- 2026-04-16: Initial spec (F71 Passwort aendern, GitHub Issue #71)
