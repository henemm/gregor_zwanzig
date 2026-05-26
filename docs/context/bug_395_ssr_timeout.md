# Context: Bug #395 — SSR-Loader Timeout fehlt

## Request Summary
Der Startseiten-SSR-Loader (`+page.server.ts`) hängt bis zu 57 Sekunden, weil der Wetter-Fetch für die Hero-Tour kein Timeout hat. Fix: `AbortSignal.timeout(~3500ms)` auf den Wetter-Fetch (und defensiv auf trips/subscriptions).

## Betroffene Datei
| Datei | Relevanz |
|-------|----------|
| `frontend/src/routes/+page.server.ts` | Primäre Fehlerquelle — Wetter-Fetch ohne Timeout |

## Ist-Zustand (Fehler)
```ts
const wRes = await fetch(`${API()}/api/trips/${hero.id}/stages/weather`, { headers });
// Kein Timeout → hängt bis HTTP-Timeout (~57s)
```

Trips + Subscriptions sind via `Promise.all` parallel, haben aber ebenfalls kein Timeout.

## Existing Patterns
- `AbortController` wird in `EmailIframe.svelte` und `SmsPhoneFrame.svelte` client-seitig genutzt
- SSR-Loader in anderen Routen (`trips/`, `compare/`, etc.) haben ebenfalls **kein** Timeout
- Node.js 18+ / SvelteKit unterstützt `AbortSignal.timeout(ms)` nativ (kein Polyfill nötig)

## Fail-Soft schon implementiert
- `heroWeather` wird bei Fehler/null auf `null` gesetzt → Hero rendert konditional (AC-3 aus #386)
- Trips/Subscriptions: `catch(() => null)` ist bereits da, aber beim Hängen greift das nicht

## Abhängigkeiten (Backend)
- `GET /api/trips/{id}/stages/weather` ruft per Goroutine parallel Open-Meteo-API
- Fetch kann hängen wenn Open-Meteo langsam antwortet (kein Backend-Timeout erkennbar)

## Fix-Strategie
1. Wetter-Fetch: `AbortSignal.timeout(3500)` hinzufügen
2. Trips- und Subscriptions-Fetches: `AbortSignal.timeout(3500)` als defensiver Schutz
3. Bei `AbortError` → catch greift → fail-soft (bereits implementiert)

## Risiken & Überlegungen
- Timeout von 3,5s ist aggressiv — sollte ausreichen da /api/trips schnell ist; Wetter kann fail-soft
- `AbortSignal.timeout()` wirft `DOMException` (name: "TimeoutError") — catch fängt alle Exceptions ab, kein Extra-Handling nötig
- Bei Trips/Subscriptions: Timeout-Fehler → leere Liste → User sieht leere Seite (aber keine 57s-Wartezeit)
- Kein Test für SSR-Timeout-Verhalten sinnvoll (würde echte Langsamkeit simulieren müssen)

## Vorhandene Tests
- `frontend/e2e/startseite.spec.ts` — prüft UI-Rendering, kein Timeout-Test
- `frontend/src/lib/issue_386_home_migration.test.ts` — prüft Cockpit-Logik, kein SSR-Test
