# Context: bug-595-597-auth-weather

## Request Summary
Zwei Frontend-Bugs aus Playwright-Audit 2026-06-04: #595 `/reset-password` fehlt Wordmark + Token-Feld versteckt sich nicht bei URL-Auto-Fill; #597 `/weather` zeigt Compare-Content weil 301-Redirect zu `/compare` aktiv ist (Legacy-Cleanup #76).

## Related Files
| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/reset-password/+page.svelte` | Bug #595: kein Wordmark, Token-Feld immer sichtbar |
| `frontend/src/routes/reset-password/+page.server.ts` | Liest `?token` + `?user` aus URL, übergibt an Template |
| `frontend/src/routes/forgot-password/+page.svelte` | Referenz-Auth-Seite (gleiches Layout-Muster, kein Wordmark) |
| `frontend/src/routes/login/+page.svelte` | Referenz mit Wordmark-Komponente |
| `frontend/src/routes/+layout.svelte` | Line 59–65: publicPages-Liste schließt reset-password aus App-Shell aus (korrekt) |
| `frontend/src/routes/weather/+page.svelte` | Eigenständiger Forecast-Viewer — DEAD CODE wegen Redirect |
| `frontend/src/routes/weather/+page.server.ts` | `redirect(301, '/compare')` — intentional seit Commit 6b852544 (#76) |

## Befunde

### #595 — `/reset-password` zwei Bugs
1. **Wordmark fehlt**: `/login` und `/register` zeigen Wordmark-Komponente; `/forgot-password` und `/reset-password` nicht. Lösung: Wordmark in beide einbauen (Konsistenz).
2. **Token-Feld sichtbar**: `+page.server.ts` liest bereits `?token` aus URL und übergibt als `data.token`. Das Svelte-Template setzt `value={form?.token ?? data.token}` — füllt vor. Aber das `<input>` ist immer sichtbar. Fix: `type="hidden"` wenn Token gesetzt, sonst sichtbar + editierbar.

### #597 — `/weather` zeigt Compare-Content
- `+page.server.ts` macht seit Commit `6b852544` ("Alt-Routen aufräumen: 301 Redirects für 5 Legacy-Routes #76") einen 301-Redirect auf `/compare`.
- `+page.svelte` hat eigenständigen Forecast-per-Location-Viewer (Location-Dropdown, Stundenauswahl, Wettertabelle) — aber ist **unerreichbarer Dead Code**.
- Playwright sieht Compare-Content weil der Redirect greift.
- **Produkt-Frage**: Soll `/weather` dauerhaft Alias für `/compare` bleiben (Svelte löschen), oder soll die Seite als eigene Forecast-Ansicht aktiviert werden?

## Existierende Muster
- Auth-Seiten ohne App-Shell: via `publicPages`-Array in `+layout.svelte` L59
- Wordmark: `import Wordmark from '$lib/components/ui/wordmark/Wordmark.svelte'` (wie in `/login`)
- Hidden input bei gesetztem Wert: SvelteKit-Pattern `{#if token}<input type="hidden" ...>{:else}<input ...>{/if}`
