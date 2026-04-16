---
entity_id: register_page
type: module
created: 2026-04-16
updated: 2026-04-16
status: implemented
version: "1.0"
tags: [sveltekit, auth, register, f62]
---

# F62 — SvelteKit Registrierungsseite

## Approval

- [x] Approved

## Purpose

Neue `/register`-Route im SvelteKit-Frontend, die Nutzern die Selbstregistrierung ermoeglicht. Die Seite schickt Formular-Daten an den bestehenden Go-Backend-Endpoint `POST /api/auth/register` und leitet bei Erfolg zu `/login?registered=1` weiter, wo ein Erfolgsbanner angezeigt wird.

## Scope

### In Scope

- `frontend/src/routes/register/+page.svelte` — Registrierungsformular (NEU)
- `frontend/src/routes/register/+page.server.ts` — Form Action (NEU)
- `frontend/src/hooks.server.ts` — `/register` zu `publicPaths` hinzufuegen (EDIT)
- `frontend/src/routes/login/+page.svelte` — "Konto erstellen"-Link + Erfolgsbanner (EDIT)

### Out of Scope

- Go-Backend (`POST /api/auth/register`) — bereits implementiert, keine Aenderungen
- Auto-Login nach Registrierung — Go setzt keinen Session-Cookie bei Register
- E-Mail-Bestaetigung — nicht Teil dieses Features

## Source

- **File:** `frontend/src/routes/register/+page.svelte` **(NEU)**
- **File:** `frontend/src/routes/register/+page.server.ts` **(NEU)**
- **File:** `frontend/src/hooks.server.ts` **(EDIT)**
- **File:** `frontend/src/routes/login/+page.svelte` **(EDIT)**
- **Identifier:** `actions.default` (in `+page.server.ts`)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `POST /api/auth/register` | Go API endpoint | Username/Passwort validieren, User anlegen |
| `$env/dynamic/private` | SvelteKit | `GZ_API_BASE` fuer Go-API-URL |
| `@sveltejs/kit` | SvelteKit | `fail`, `redirect` |
| `hooks.server.ts` | SvelteKit | `publicPaths` — `/register` muss ohne Session erreichbar sein |

## Implementation Details

### Step 1: `frontend/src/routes/register/+page.server.ts` (NEU, ~40 LoC)

```typescript
import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const actions = {
    default: async ({ request }) => {
        const data = await request.formData();
        const username = data.get('username')?.toString() ?? '';
        const password = data.get('password')?.toString() ?? '';
        const confirmPassword = data.get('confirmPassword')?.toString() ?? '';

        if (password !== confirmPassword) {
            return fail(400, { error: 'Passwoerter stimmen nicht ueberein', username });
        }

        const resp = await fetch(`${API()}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });

        if (resp.ok) {
            redirect(302, '/login?registered=1');
        }

        if (resp.status === 409) {
            return fail(409, { error: 'Benutzername bereits vergeben', username });
        }
        if (resp.status === 400) {
            return fail(400, {
                error: 'Benutzername (3\u201350 Zeichen) und Passwort (mind. 8 Zeichen) erforderlich',
                username,
            });
        }
        return fail(500, { error: 'Registrierung fehlgeschlagen', username });
    },
} satisfies Actions;
```

### Step 2: `frontend/src/routes/register/+page.svelte` (NEU, ~65 LoC)

Formularfelder:
- `username` (text, required) — Wert bei Fehler aus `form?.username` wiederhergestellt
- `password` (password, required) — NICHT wiederhergestellt (Sicherheit)
- `confirmPassword` (password, required) — NICHT wiederhergestellt (Sicherheit)
- Submit-Button "Konto erstellen"
- Fehler-Alert wenn `form?.error` gesetzt
- Link zu `/login` ("Bereits registriert? Anmelden")

Struktur analog zu `frontend/src/routes/login/+page.svelte`.

### Step 3: `frontend/src/hooks.server.ts` (EDIT, +1 Zeile)

```typescript
// VORHER:
const publicPaths = ['/login', '/forgot-password', '/reset-password'];

// NACHHER:
const publicPaths = ['/login', '/register', '/forgot-password', '/reset-password'];
```

### Step 4: `frontend/src/routes/login/+page.svelte` (EDIT, ~+6 Zeilen)

1. Erfolgsbanner: Wenn URL-Parameter `?registered=1` gesetzt, Hinweisbox anzeigen:
   "Konto erfolgreich erstellt. Bitte melde dich an."
   Umsetzen via SvelteKit `$page.url.searchParams.get('registered')`.

2. Link unterhalb des Formulars: "Noch kein Konto? Konto erstellen" → `/register`

## Expected Behavior

- **Input:** Formular mit `username`, `password`, `confirmPassword`
- **Output bei Erfolg:** Redirect zu `/login?registered=1`, Erfolgsbanner auf Login-Seite
- **Output bei Fehler:** `fail(...)` mit deutschsprachiger Fehlermeldung, Formular bleibt sichtbar, `username` wiederhergestellt
- **Side effects:** Go-Backend legt neuen User an und provisioniert Verzeichnisse

### Fehlerszenarien

| Szenario | HTTP Status | Fehlermeldung |
|----------|-------------|---------------|
| Passwoerter stimmen nicht ueberein | 400 | "Passwoerter stimmen nicht ueberein" |
| Validation failed (Username/Passwort zu kurz) | 400 | "Benutzername (3–50 Zeichen) und Passwort (mind. 8 Zeichen) erforderlich" |
| Username bereits vergeben | 409 | "Benutzername bereits vergeben" |
| Go-Backend Fehler | 500 | "Registrierung fehlgeschlagen" |

### Passwortfelder bei Fehler

Passwortfelder werden NICHT wiederhergestellt — sicherheitshalber leer gelassen. Nur `username` wird via `form?.username` wiederhergestellt.

## Known Limitations

- Kein Rate-Limiting fuer Registrierungsversuche
- Kein CAPTCHA oder Anti-Bot-Schutz
- Keine E-Mail-Bestaetigung (direkter Zugang nach Registrierung nach manuellem Login)

## Changelog

- 2026-04-16: Initial spec (F62 — SvelteKit Registrierungsseite, GitHub Issue #62)
- 2026-04-16: Implemented — `/register` route, form action, hooks update, login success banner. GitHub Issue #62.
