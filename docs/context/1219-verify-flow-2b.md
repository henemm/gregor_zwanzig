# Context: #1219 Scheibe 2b — Frontend-Bestätigungsseite (`/verify-email`)

**Workflow:** `1219-verify-flow-2b` · **Issue:** #1219 (schließt mit dieser Scheibe) · **Modus:** neue Frontend-Route

## Request Summary
Der Backend-Einlöse-Endpoint `POST /api/auth/verify-email` ist live (Scheibe 2a-ii). Der Bestätigungslink in der Mail (Scheibe 2a-i) zeigt auf `{publicHost}/verify-email?user=<id>&token=<t>` — diese Frontend-Route existiert noch nicht. Diese Scheibe baut die SvelteKit-Seite: liest `user`/`token` aus der URL, zeigt einen **Bestätigungs-Knopf** (PO: kein Auto-Confirm), ruft beim Klick den Endpoint auf und zeigt Erfolg/Fehler an. Damit ist der Double-Opt-In end-to-end nutzbar und #1219 abgeschlossen.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/routes/reset-password/+page.svelte` (58 LoC) | Nächstes Vorbild: liest `user`/`token` aus Query, Formular mit `use:enhance`, success/error-Zweige, Hidden-Fields, Wordmark. |
| `frontend/src/routes/reset-password/+page.server.ts` (43 LoC) | Vorbild `load` (Query→`{user,token}`) + `actions.default` (formData → `fetch(${API()}/api/auth/reset-password)` POST → `{success}`/`fail(400,{error})`, mappt `token expired`→„Token abgelaufen"). |
| `frontend/src/routes/magic-link/verify/+page.server.ts` | Zweites Vorbild für Action + Fehler-Mapping + `X-Real-IP`-Weiterleitung. |
| `frontend/src/lib/server/apiBase.ts` | `apiBase()` = Backend-Basis-URL für serverseitige Fetches. |
| `frontend/src/routes/page-server.bug395.test.ts` | Vorbild für `node --test`-Sentinel auf `+page.server.ts` (Source-Inspection, `# doc-compliance-test`). |
| `frontend/src/lib/components/ui/wordmark/Wordmark.svelte` | Logo-Komponente (Kopf der Auth-Seiten). |

## Existing Patterns
- **Auth-Seiten-Layout:** `flex min-h-screen items-center justify-center` → zentrierte Karte `max-w-sm`, `Wordmark`, `h1`, success-Box (`bg-green-50 text-green-800`) / error-Box (`bg-red-50 text-red-800` bzw. `border-destructive bg-destructive/10`).
- **Query→Action:** `load` gibt `user`/`token` aus `url.searchParams` zurück; `+page.svelte` trägt sie als Hidden-Fields; `actions.default` POSTet serverseitig an das Go-Backend (nie direkt aus dem Browser — SSR-Fetch über `apiBase()`), inkl. `X-Real-IP` für den Rate-Limiter.
- **`use:enhance`** für progressive Enhancement; Fehler kommen als `form.error` zurück, Erfolg als `form.success`.
- **Test-Runner:** `cd frontend && npm test` → `node --test --experimental-strip-types`. Reine `load`-Funktion ist mock-frei unit-testbar (Aufruf mit echtem `URL`). Voller Klick-Pfad → Playwright/staging-validator (FE hat keine Svelte-Component-Test-Infra, s. #1223).

## Design-Entscheidungen (aus 2a-i/2a-ii PO-Vorgaben + Analyse)
1. **Knopf statt Auto-Confirm** (PO 2026-07-10): Die Seite submittet NICHT automatisch beim Laden — der Nutzer klickt „E-Mail-Adresse bestätigen". Das verhindert, dass Mail-Prefetch/Link-Scanner den Token versehentlich einlösen (der Grund für POST statt GET war genau das).
2. **`user`/`token` als Hidden-Fields** aus der Query — kein sichtbares Eingabefeld nötig (anders als reset-password, das ein Passwortfeld braucht).
3. **Fehler-Mapping serverseitig:** Backend liefert `{"error":"token expired"}` / `"invalid token"` / `"invalid request"` → deutsche, laienverständliche Meldungen („Der Bestätigungslink ist abgelaufen…" / „…ungültig oder wurde bereits verwendet").
4. **Fehlende Query-Parameter:** Ist `user` oder `token` leer, kann nicht bestätigt werden → eigener Hinweis statt eines toten Knopfes.
5. **Erfolgs-Zustand:** grüne Bestätigung + Link zurück zur App/Login. Kein Auto-Redirect (der Nutzer ist evtl. unangemeldet — er soll die Bestätigung sehen).

## Dependencies
- **Upstream (konsumiert):** `POST /api/auth/verify-email` (2a-ii, live), `apiBase()`.
- **Downstream:** keine — Endpunkt der Feature-Kette. Schließt #1219.

## Existing Specs
- `docs/specs/modules/fix_1219_verify_flow_2a_ii.md` — Backend-Endpoint (Body `{user, token}`, 400-Fehlerprofil).
- `docs/specs/modules/fix_1219_verify_flow_2a.md` — Versand-Pfad + Link-Format `{publicHost}/verify-email?user=…&token=…`.

## Risks & Considerations
- **Token nicht in Klartext-Logs/Referrer:** Der Token steht in der URL-Query (unvermeidbar, kommt aus dem Mail-Link) und wird serverseitig als Hidden-Field weitergereicht; keine zusätzliche Preisgabe.
- **Rate-Limiter:** Der Backend-Endpoint hat einen IP-Limiter (10/h) — die Seite muss `X-Real-IP` weiterreichen (wie reset-password/magic-link), sonst zählt alles auf die Frontend-Server-IP.
- **Happy-Path-E2E braucht echten Token:** Ein gültiger Token entsteht nur durch eine Adressänderung (2a-i, verschickt Mail). Für die Staging-E2E ist der belastbar prüfbare Pfad der Fehler-Zustand (ungültiger Token → deutsche Fehlermeldung über den echten Backend-Roundtrip) + Rendering des Knopfes; der Erfolgsfall des Backends ist bereits in 2a-ii prod-verifiziert.
- **Frontend-only:** kein Go/Python. Deploy-Scope frontend-only → Staging-Validierung visuell/Playwright, kein Mailversand.
