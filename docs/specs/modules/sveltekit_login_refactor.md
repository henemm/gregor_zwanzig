---
entity_id: sveltekit_login_refactor
type: module
created: 2026-04-15
updated: 2026-04-15
status: draft
version: "1.0"
tags: [sveltekit, auth, login, f13]
---

# F13 Phase 2b — SvelteKit Login-Umbau

## Approval

- [ ] Approved

## Purpose

Umbau der SvelteKit Login-Action von lokaler ENV-Credential-Pruefung auf einen API-Call an den Go-Backend-Endpoint `POST /api/auth/login`. Dadurch wird der Login-Flow zentralisiert: Go prueft Credentials (bcrypt), erstellt den Session-Cookie, und SvelteKit leitet ihn an den Browser weiter. Der hardcoded `userId = 'default'` entfaellt — der echte userId kommt aus der Go-Response.

## Scope

### In Scope

- `frontend/src/routes/login/+page.server.ts` — Login-Action Rewrite

### Out of Scope

- `hooks.server.ts` — keine Aenderung (validiert Cookie weiterhin)
- `auth.ts` — keine Aenderung (`verifySession` weiterhin gebraucht, `signSession` wird nicht geloescht aber nicht mehr importiert)
- Go-Backend — bereits implementiert (F13 Phase 2a)

## Source

- **File:** `frontend/src/routes/login/+page.server.ts` **(REWRITE)**
- **Identifier:** `actions.default`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/auth/login` | Go API endpoint | Credentials pruefen, Cookie erstellen |
| `$env/dynamic/private` | SvelteKit | `GZ_API_BASE` fuer Go-API-URL |
| `@sveltejs/kit` | SvelteKit | `fail`, `redirect` |

## Implementation Details

### Aktueller Code (wird ersetzt)

```typescript
// VORHER: ENV-Check + lokales signSession
const expectedUser = env.GZ_AUTH_USER ?? 'admin';
const expectedPass = env.GZ_AUTH_PASS ?? '';
if (username !== expectedUser || password !== expectedPass) { ... }
const userId = 'default';  // ← HARDCODED
const sessionValue = signSession(userId, secret);
cookies.set('gz_session', sessionValue, { ... });
```

### Neuer Code

```typescript
import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const actions = {
    default: async ({ request, cookies }) => {
        const data = await request.formData();
        const username = data.get('username')?.toString() ?? '';
        const password = data.get('password')?.toString() ?? '';

        if (!username || !password) {
            return fail(400, { error: 'Username and password required', username });
        }

        const resp = await fetch(`${API()}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (!resp.ok) {
            return fail(401, { error: 'Invalid credentials', username });
        }

        // Extract session cookie from Go response and set it for the browser
        const setCookie = resp.headers.get('set-cookie');
        if (setCookie) {
            const match = setCookie.match(/gz_session=([^;]+)/);
            if (match) {
                cookies.set('gz_session', match[1], {
                    path: '/',
                    httpOnly: true,
                    sameSite: 'lax',
                    secure: env.NODE_ENV === 'production',
                    maxAge: 86400,
                });
            }
        }

        redirect(302, '/');
    },
} satisfies Actions;
```

### Aenderungen im Detail

1. **Import:** `signSession` entfernt, `GZ_AUTH_USER`/`GZ_AUTH_PASS`/`GZ_SESSION_SECRET` nicht mehr gelesen
2. **API-Call:** `fetch()` an Go-Backend statt lokaler Vergleich
3. **Cookie-Weiterleitung:** `Set-Cookie` Header aus Go-Response parsen, Cookie via SvelteKit setzen
4. **userId:** Kommt implizit aus dem Cookie-Value (Go setzt `{userId}.{ts}.{sig}`)

## Expected Behavior

- **Input:** Formular-Submit mit `username` + `password`
- **Output:** Bei Erfolg: Cookie gesetzt, Redirect zu `/`. Bei Fehler: 401 mit Fehlermeldung.
- **Side effects:** Keine — Go-Backend macht die Arbeit

### Fehlerszenarien

| Szenario | Verhalten |
|----------|-----------|
| Leere Felder | 400 "Username and password required" |
| Falsche Credentials | 401 "Invalid credentials" (von Go: 401) |
| Go-Backend nicht erreichbar | 401 "Invalid credentials" (fetch wirft keinen Error bei non-ok status) |

## Known Limitations

- Wenn Go-Backend down ist, bekommt der User nur "Invalid credentials" statt einer aussagekraeftigen Fehlermeldung
- `signSession` in `auth.ts` wird nicht geloescht (wird ggf. spaeter fuer andere Zwecke gebraucht)

## Changelog

- 2026-04-15: Initial spec (F13 Phase 2b — SvelteKit Login-Umbau, GitHub Issue #12)
