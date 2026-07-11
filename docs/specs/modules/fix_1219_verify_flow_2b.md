---
entity_id: fix_1219_verify_flow_2b
type: feature
created: 2026-07-11
updated: 2026-07-11
status: draft
version: "1.0"
tags: [frontend, sveltekit, verification, double-opt-in, auth]
workflow: 1219-verify-flow-2b
---

<!-- Issue #1219, Scheibe 2b — Frontend-Bestätigungsseite /verify-email -->

# Fix #1219 (Scheibe 2b) — Frontend-Bestätigungsseite `/verify-email`

## Approval

- [x] Approved (PO 'go' 2026-07-11 — ACs 1–6 auf Deutsch freigegeben, inkl. Known Limitation zum Happy-Path-E2E)

## Purpose

Der Backend-Einlöse-Endpoint `POST /api/auth/verify-email` ist live (Scheibe
2a-ii), und die Bestätigungsmail (Scheibe 2a-i) verlinkt bereits auf
`{publicHost}/verify-email?user=<id>&token=<t>`. Diese Frontend-Route existiert
noch nicht — ein Klick auf den Mail-Link läuft ins Leere (404). Diese Scheibe
baut die SvelteKit-Seite: sie liest `user`/`token` aus der URL, zeigt einen
**Bestätigungs-Knopf** (bewusst kein Auto-Confirm beim Laden, damit
Mail-Prefetch/Link-Scanner den Token nicht versehentlich einlösen), ruft beim
Klick serverseitig den Endpoint auf und zeigt Erfolg bzw. eine
laienverständliche Fehlermeldung an. Damit ist der Self-Service-Double-Opt-In
end-to-end nutzbar und **Issue #1219 abgeschlossen**.

## Source

- **File:** `frontend/src/routes/verify-email/+page.server.ts` (NEU) — nach dem
  Muster von `reset-password/+page.server.ts`:
  - `load({ url })` gibt `{ user: url.searchParams.get('user') ?? '', token:
    url.searchParams.get('token') ?? '' }` zurück.
  - `actions.default({ request })`: liest `user`/`token` aus `formData`; bei
    fehlendem Wert `fail(400, { error: 'Ungültiger Bestätigungslink.', user,
    token })`; sonst SSR-`fetch(\`${API()}/api/auth/verify-email\`, {POST,
    JSON {user, token}, X-Real-IP})`. Bei `!resp.ok`: Body lesen, `token
    expired` → „Der Bestätigungslink ist abgelaufen. Bitte ändere deine
    Adresse erneut, um einen neuen Link zu erhalten." / sonst → „Der
    Bestätigungslink ist ungültig oder wurde bereits verwendet." →
    `fail(400, {error, user, token})`. Bei Erfolg `return { success: true }`
    (Frontend, SvelteKit-Route).
- **File:** `frontend/src/routes/verify-email/+page.svelte` (NEU) — nach dem
  Muster von `reset-password/+page.svelte`:
  - Zentriertes Auth-Layout mit `Wordmark`, `h1` „E-Mail-Adresse bestätigen".
  - `form?.success` → grüne Box „Deine E-Mail-Adresse wurde bestätigt. Du
    erhältst ab jetzt wieder Wetter-Briefings an diese Adresse." + Link „Zur
    App" (`/`).
  - Sonst, wenn `user` UND `token` (aus `form` bzw. `data`) vorhanden: `form`
    (`method="POST" use:enhance`) mit zwei Hidden-Fields (`user`, `token`) und
    genau EINEM sichtbaren Knopf „E-Mail-Adresse bestätigen"; darüber ggf.
    `form?.error` als rote Box.
  - Fehlt `user` oder `token` → rote Box „Dieser Bestätigungslink ist
    unvollständig. Bitte öffne den Link aus der E-Mail erneut." (kein
    Knopf).
  (Frontend, SvelteKit-Route).

> **Schicht-Hinweis:** Reines Frontend (SvelteKit unter
> `frontend/src/routes/verify-email/`). Kein Go, kein Python. Konsumiert nur
> den bereits live-deployten Endpoint `POST /api/auth/verify-email`.

## Estimated Scope

- **LoC:** ~+90 / -0 (zwei neue Dateien) plus ein `node --test`-Sentinel
- **Files:** 2 (`+page.server.ts` CREATE, `+page.svelte` CREATE) plus
  Testdatei `frontend/src/routes/verify-email/page-server.test.ts`
- **Effort:** small

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `reset-password/+page.server.ts` / `+page.svelte` | route | Strukturelles Vorbild (Query→Action, success/error-Zweige) |
| `magic-link/verify/+page.server.ts` | route | Vorbild Fehler-Mapping + `X-Real-IP`-Weiterleitung |
| `apiBase` (`frontend/src/lib/server/apiBase.ts`) | function | Backend-Basis-URL für den SSR-Fetch |
| `POST /api/auth/verify-email` (`internal/handler/auth.go`, Scheibe 2a-ii, live) | endpoint | Nimmt `{user, token}` entgegen, liefert 200/400 |
| `Wordmark` (`frontend/src/lib/components/ui/wordmark/Wordmark.svelte`) | component | Seitenkopf |

## Implementation Details

### 1. `verify-email/+page.server.ts`

```ts
import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';

export const load: PageServerLoad = async ({ url }) => ({
    user: url.searchParams.get('user') ?? '',
    token: url.searchParams.get('token') ?? '',
});

export const actions = {
    default: async ({ request }) => {
        const data = await request.formData();
        const user = data.get('user')?.toString() ?? '';
        const token = data.get('token')?.toString() ?? '';

        if (!user || !token) {
            return fail(400, { error: 'Ungültiger Bestätigungslink.', user, token });
        }

        const clientIP = request.headers.get('x-real-ip') ?? '';
        const resp = await fetch(`${API()}/api/auth/verify-email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
            body: JSON.stringify({ user, token }),
        });

        if (!resp.ok) {
            const body = await resp.json().catch(() => ({}));
            const msg = body.error === 'token expired'
                ? 'Der Bestätigungslink ist abgelaufen. Bitte ändere deine Adresse erneut, um einen neuen Link zu erhalten.'
                : 'Der Bestätigungslink ist ungültig oder wurde bereits verwendet.';
            return fail(400, { error: msg, user, token });
        }

        return { success: true };
    },
} satisfies Actions;
```

### 2. `verify-email/+page.svelte`

Analog `reset-password/+page.svelte`, aber ohne Passwortfeld — nur Hidden-Fields
`user`/`token` und ein Bestätigungs-Knopf. Success-Zweig zeigt die grüne
Bestätigung + Link „Zur App". Bei fehlendem `user`/`token` (aus `data`) wird
statt des Formulars der Unvollständig-Hinweis gezeigt.

### 3. Test-Sentinel (`node --test`)

`frontend/src/routes/verify-email/page-server.test.ts` — mock-frei:
- Importiert `load` und ruft es mit einem echten `URL`
  (`?user=alice&token=abc`) → erwartet `{user:'alice', token:'abc'}`; und mit
  leerer Query → `{user:'', token:''}`. (Echtes Verhalten, keine Mocks.)
- Source-Sentinel (`# doc-compliance-test`) auf `+page.server.ts`: der
  Action-Zweig POSTet an `/api/auth/verify-email` und mappt `token expired`.

## Expected Behavior

- **Input:** Aufruf von `/verify-email?user=<id>&token=<t>` (aus dem Mail-Link).
- **Output:** Seite mit Kopf „E-Mail-Adresse bestätigen" und genau einem Knopf
  „E-Mail-Adresse bestätigen" (kein automatischer Submit). Nach Klick:
  - Backend 200 → grüne Bestätigung + „Zur App"-Link.
  - Backend 400 `token expired` → „…abgelaufen…"-Meldung, kein Erfolg.
  - Backend 400 sonst → „…ungültig oder wurde bereits verwendet."-Meldung.
- **Fehlende Query-Parameter:** Unvollständig-Hinweis, kein Knopf.
- **Side effects:** genau ein POST an `/api/auth/verify-email` pro Klick (nie
  automatisch beim Laden), inkl. `X-Real-IP` für den Backend-Rate-Limiter.

## Acceptance Criteria

- **AC-1:** Given der Aufruf `/verify-email?user=alice&token=abc123` / When die
  Seite serverseitig geladen wird (`load`) / Then enthält `data`
  `user="alice"` und `token="abc123"` (aus den Query-Parametern), und ein
  Aufruf mit leerer Query liefert `user=""`, `token=""`.
  - Test: `load({ url: new URL('https://x/verify-email?user=alice&token=abc123') })`
    → `{user:'alice', token:'abc123'}`; `load({ url: new URL('https://x/verify-email') })`
    → `{user:'', token:''}`. (node --test, mock-frei)

- **AC-2:** Given eine geladene Seite mit gültigem `user`/`token` / When sie
  gerendert wird / Then zeigt sie genau EINEN Bestätigungs-Knopf „E-Mail-Adresse
  bestätigen" und submittet NICHT automatisch beim Laden (die Verifikation
  passiert erst durch den Klick).
  - Test (Playwright/staging): Seite mit `?user=…&token=…` öffnen, prüfen dass
    der Knopf sichtbar ist und `email_verified_at`/eine Erfolgsmeldung erst
    NACH dem Klick erscheint, nicht beim bloßen Laden.

- **AC-3:** Given ein Klick auf den Bestätigungs-Knopf, während das Backend den
  Token als ungültig ablehnt (`400 invalid token`) / When die Server-Action
  antwortet / Then zeigt die Seite die deutsche Meldung „Der Bestätigungslink
  ist ungültig oder wurde bereits verwendet." und KEINE Erfolgsmeldung.
  - Test (Playwright/staging): `/verify-email?user=x&token=ungueltig` öffnen,
    Knopf klicken, prüfen dass die Ungültig-Meldung erscheint (echter
    Backend-Roundtrip, kein Erfolg).

- **AC-4:** Given ein Klick bei abgelaufenem Token (`400 token expired`) / When
  die Action antwortet / Then erscheint die Meldung „Der Bestätigungslink ist
  abgelaufen. Bitte ändere deine Adresse erneut, um einen neuen Link zu
  erhalten." — abgegrenzt von der Ungültig-Meldung.
  - Test: Fehler-Mapping in `+page.server.ts` bildet `body.error === 'token
    expired'` auf die Abgelaufen-Meldung ab (Source-Sentinel + Playwright,
    sofern ein abgelaufener Token verfügbar).

- **AC-5:** Given der Aufruf `/verify-email` OHNE `user` oder OHNE `token` /
  When die Seite gerendert wird / Then wird KEIN Bestätigungs-Knopf angezeigt,
  sondern der Hinweis „Dieser Bestätigungslink ist unvollständig. Bitte öffne
  den Link aus der E-Mail erneut." — es kann kein leerer POST ausgelöst
  werden.
  - Test (Playwright/staging): `/verify-email` (ohne Query) öffnen, prüfen
    dass kein Bestätigungs-Knopf, aber der Unvollständig-Hinweis erscheint.

- **AC-6:** Given ein erfolgreicher Klick (Backend 200) / When die Action
  `{success:true}` zurückgibt / Then zeigt die Seite die grüne Bestätigung
  „Deine E-Mail-Adresse wurde bestätigt…" und einen Link „Zur App" (`/`),
  und das Bestätigungs-Formular wird nicht mehr angezeigt.
  - Test (Playwright/staging, sofern gültiger Token seedbar): Erfolgszustand
    zeigt grüne Box + „Zur App"-Link, kein Knopf mehr. Andernfalls durch den
    prod-verifizierten Backend-200-Pfad (2a-ii) + Source-Struktur belegt.

## Known Limitations

- Der Happy-Path (gültiger Token → grüne Bestätigung) ist auf Staging nur mit
  einem echten, frisch erzeugten Token durchklickbar (entsteht durch eine
  Adressänderung, die eine Mail auslöst). Die belastbar per Playwright
  prüfbaren UI-Zustände sind das Knopf-Rendering (AC-2), der Ungültig-Pfad
  (AC-3, echter Backend-Roundtrip) und der Unvollständig-Hinweis (AC-5); der
  Backend-200-Zweig ist bereits in Scheibe 2a-ii prod-verifiziert.
- Die Seite fordert bei ungültigem/abgelaufenem Token keinen neuen Link an
  (kein „Resend"-Knopf) — der Nutzer löst einen neuen Link über eine erneute
  Adressänderung aus (konsistent mit dem Passwort-Reset-Flow). Bewusst außer
  Scope.
- Kein Auto-Redirect nach Erfolg: Der Klicker ist evtl. unangemeldet und soll
  die Bestätigung sehen; er navigiert selbst über „Zur App".

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Neue SvelteKit-Route strikt nach dem etablierten Muster der
  bestehenden Auth-Bestätigungsseiten (`reset-password`, `magic-link/verify`) —
  Query→Server-Action→Backend-Fetch. Kein neuer Architekturbaustein, keine neue
  Abhängigkeit.

## Changelog

- 2026-07-11: Initial spec erstellt — Issue #1219 Scheibe 2b, schließt die Feature-Kette
