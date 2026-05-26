---
entity_id: bug_395_ssr_timeout
type: bugfix
created: 2026-05-26
updated: 2026-05-26
status: draft
version: "1.0"
tags: [bugfix, ssr, timeout, performance, page-server, frontend, issue-395]
---

<!-- Issue #395 — Startseite lädt bis zu 57 Sekunden: +page.server.ts fehlt AbortSignal.timeout() auf Wetter-Fetch -->

# Issue #395 — Bug-Fix: SSR-Loader-Timeouts auf Startseite

## Approval

- [ ] Approved

## Zweck

Der SSR-Loader `+page.server.ts` ruft `fetch(…/stages/weather…)` ohne `AbortSignal.timeout()` auf, wodurch die Startseite beim Hängen des Backend-Calls bis zu 57 Sekunden auf eine Antwort warten kann. Der `catch`-Block ist bereits vorhanden und setzt `heroWeather = null` (fail-soft) — der Timeout fehlte bisher als Auslöser. Der Fix ergänzt `signal: AbortSignal.timeout(3500)` auf dem Wetter-Fetch und `signal: AbortSignal.timeout(5000)` defensiv auf den trips- und subscriptions-Fetches, sodass die Seite im Fehlerfall innerhalb weniger Sekunden lädt. Kein Polyfill nötig: Node.js 18+ stellt `AbortSignal.timeout()` nativ bereit.

## Quelle / Source

**Geänderte Datei:**
- `frontend/src/routes/+page.server.ts` — einzige Datei, die geändert wird

**Betroffene Stellen:**
- `fetch(…/api/trips/…/stages/weather…)` — erhält `signal: AbortSignal.timeout(3500)`
- `fetch(…/api/trips…)` — erhält defensiv `signal: AbortSignal.timeout(5000)`
- `fetch(…/api/subscriptions…)` — erhält defensiv `signal: AbortSignal.timeout(5000)`

**Neue Test-Datei:**
- `frontend/src/routes/page-server.bug395.test.ts`

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im SvelteKit-Frontend-Layer (`frontend/src/routes/`). Der Wetter-Fetch läuft serverseitig (SSR) im Node.js-Prozess, daher ist `AbortSignal.timeout()` ohne Browser-Polyfill verfügbar. Python-Backend und Go-API sind nicht betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/+page.server.ts` | SvelteKit Server-Load | Einzige geänderte Datei; enthält alle drei fetch-Aufrufe |
| `AbortSignal.timeout()` | Node.js 18+ Built-in | Liefert ein AbortSignal, das nach N ms automatisch abbricht — kein Polyfill nötig |
| `frontend/src/routes/page-server.bug395.test.ts` | Test-Datei | Source-Inspection-Sentinel, der nach dem Fix grün wird |

## Implementation Details

### 1. Wetter-Fetch — `signal: AbortSignal.timeout(3500)`

Der bestehende `try/catch`-Block um den heroWeather-Fetch wird um das Signal erweitert:

```ts
// Vorher:
const wRes = await fetch(`${API()}/api/trips/${hero.id}/stages/weather`, { headers });

// Nachher:
const wRes = await fetch(`${API()}/api/trips/${hero.id}/stages/weather`, {
    headers,
    signal: AbortSignal.timeout(3500)
});
```

Der vorhandene `catch`-Block fängt den `TimeoutError` transparent ab und setzt `heroWeather = null` — kein weiterer Umbau nötig.

### 2. trips- und subscriptions-Fetches — `signal: AbortSignal.timeout(5000)`

```ts
// Vorher:
const [tripsRes, subsRes] = await Promise.all([
    fetch(`${API()}/api/trips`, { headers }).catch(() => null),
    fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null)
]);

// Nachher:
const [tripsRes, subsRes] = await Promise.all([
    fetch(`${API()}/api/trips`, { headers, signal: AbortSignal.timeout(5000) }).catch(() => null),
    fetch(`${API()}/api/subscriptions`, { headers, signal: AbortSignal.timeout(5000) }).catch(() => null)
]);
```

Die inline-`catch(() => null)`-Pattern bleiben unverändert — sie fangen den `TimeoutError` bereits ab.

### 3. Source-Inspection-Test (Regressions-Sentinel)

Der Test liest `+page.server.ts` als String und prüft, dass `AbortSignal.timeout` in der Datei vorkommt. Damit wird verhindert, dass ein zukünftiger Refactor die Timeouts stillschweigend entfernt. Kein Mock, kein echtes Netzwerk — reine Quelltextinspektion analog `homeCockpit.test.ts`.

```ts
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(__dirname, '../routes/+page.server.ts'), 'utf-8');

test('AC-1: weather fetch hat AbortSignal.timeout(3500)', () => {
    assert.ok(src.includes('AbortSignal.timeout(3500)'));
});

test('AC-2: trips/subscriptions-Fetches haben AbortSignal.timeout(5000)', () => {
    const matches = src.match(/AbortSignal\.timeout\(5000\)/g) ?? [];
    assert.ok(matches.length >= 2, `Erwartet >=2 × AbortSignal.timeout(5000), gefunden: ${matches.length}`);
});

test('AC-3: AbortSignal.timeout kommt mindestens 3x vor', () => {
    const matches = src.match(/AbortSignal\.timeout\(/g) ?? [];
    assert.ok(matches.length >= 3, `Erwartet >=3 × AbortSignal.timeout, gefunden: ${matches.length}`);
});
```

### LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/routes/+page.server.ts` | +3 (je 1 Zeile pro Fetch) | ja |
| `frontend/src/routes/page-server.bug395.test.ts` | ~20 (neu) | ja |
| **Gesamt (zählend)** | **~23** | **weit unter 250 LoC-Limit** |

## Expected Behavior

- **Input:** SSR-Load-Aufruf der Startseite `/` unter normalen Bedingungen und wenn das Backend hängt
- **Output:**
  - Wetter-Fetch: bricht nach 3500 ms ab; `heroWeather = null`; Hero rendert ohne Wetter-Daten (bestehende fail-soft-Logik aus AC-3 Issue #386)
  - trips/subscriptions-Fetches: brechen nach 5000 ms ab; `.catch(() => null)` greift; Seite lädt mit leerer Trip-Liste
- **Side effects:** Bei normalem Backend (Antwort < 3500 ms / < 5000 ms) ist das Verhalten identisch zu vorher — `AbortSignal.timeout()` ist ein No-op, wenn der Fetch früher abgeschlossen wird

## Acceptance Criteria

- **AC-1:** Given der Wetter-Fetch-Aufruf im SSR-Loader / When das Backend länger als 3500 ms nicht antwortet / Then bricht der Fetch mit `TimeoutError` ab, `heroWeather` wird `null` und die Seite antwortet ohne Wetter-Daten innerhalb von ~3,5 Sekunden
  - Test: (populated after /tdd-red)

- **AC-2:** Given die trips- und subscriptions-Fetches im SSR-Loader / When das Backend länger als 5000 ms nicht antwortet / Then brechen beide Fetches ab, `.catch(() => null)` liefert `null`, und die Seite lädt mit leerem Zustand innerhalb von ~5 Sekunden
  - Test: (populated after /tdd-red)

- **AC-3:** Given die Quelldatei `frontend/src/routes/+page.server.ts` / When der Source-Inspection-Test ausgeführt wird / Then enthält die Datei `AbortSignal.timeout(3500)` einmal und `AbortSignal.timeout(5000)` mindestens zweimal (trips + subscriptions), und `AbortSignal.timeout` kommt insgesamt mindestens 3-mal vor
  - Test: `page-server.bug395.test.ts` — 3 Assertions

## Known Limitations

- **Kein echter Netzwerk-Test:** Der Source-Inspection-Test prüft nur Quelltextvorkommen. Ein echter Integrationstest gegen einen hängenden Mock-Server wäre aussagekräftiger, würde aber Mocking voraussetzen, das in diesem Projekt verboten ist. Der Sentinel verhindert Regressionen; die funktionale Korrektheit folgt aus der Node.js-Semantik von `AbortSignal.timeout()`.
- **Timeout-Werte sind Heuristiken:** 3500 ms (Wetter) und 5000 ms (trips/subscriptions) basieren auf bekanntem P99-Verhalten des Backends. Bei sehr langsamer Server-Hardware oder vollem Cache-Miss könnten legitime Requests abgebrochen werden. Die Werte sind im Source direkt anpassbar.

## Out of Scope

- Retry-Logik nach Timeout (wäre separates Feature)
- Timeout-Konfiguration über ENV-Variable oder `config.ini`
- Änderungen am Python-Backend oder Go-API
- Anpassung der Fehler-UI beim Hero-Widget (bestehende fail-soft-Logik aus Issue #386 reicht aus)

## Changelog

- 2026-05-26: Initial spec erstellt. Ergänzt `AbortSignal.timeout(3500)` auf heroWeather-Fetch und `AbortSignal.timeout(5000)` defensiv auf trips/subscriptions-Fetches in `+page.server.ts`. Regressions-Sentinel als Source-Inspection-Test. Behebt Ladezeit von bis zu 57 Sekunden bei hängendem Backend.
