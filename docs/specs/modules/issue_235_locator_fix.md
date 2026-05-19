---
entity_id: issue_235_locator_fix
type: bugfix
created: 2026-05-19
updated: 2026-05-19
status: draft
version: "1.0"
tags: [bugfix, frontend, e2e, sveltekit, playwright, locations, strict-mode, issue-235]
---

<!-- Issue #235 — Test-Drift: locations.spec.ts Strict-Mode-Locator-Konflikte + Page-Load -->

# Issue #235 — Bug-Fix: /locations-Seite wiederherstellen + Playwright Strict-Mode-Locatoren reparieren

## Approval

- [ ] Approved

## Zweck

Die E2E-Test-Suite `frontend/e2e/locations.spec.ts` schlaegt seit der Einfuehrung des Compare-Screens komplett fehl, weil `+page.server.ts` einen 301-Redirect auf `/compare` ausfuehrt und alle 9 Tests damit auf der falschen Seite landen. Zusaetzlich enthaelt `+page.svelte` einen Infinite-Recursion-Bug in `refetchLocations()`, der nach dem Speichern einer neuen Location den Dialog offen laesst und den Ort mehrfach in den DOM schreibt — was Playwrights Strict-Mode-Locatoren mit einem "found 2 elements" Fehler brechen laesst. Dieser Fix stellt die `/locations`-Route als eigenstaendige Seite wieder her, behebt den Recursion-Bug und korrigiert die betroffenen Locatoren.

## Quelle / Source

**Geaenderte Dateien:**
- `frontend/src/routes/locations/+page.server.ts` — 301-Redirect durch echten API-Load ersetzen
- `frontend/src/routes/locations/+page.svelte` — `refetchLocations()` Infinite-Recursion-Bug beheben
- `frontend/e2e/locations.spec.ts` — 2 Locatoren auf tabellenscoped Suche umstellen

> **Schicht-Hinweis:** Alle drei Dateien liegen im SvelteKit-Frontend-Layer (`frontend/src/` bzw. `frontend/e2e/`). Kein Go-API- oder Python-Backend-Code ist betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/compare/+page.server.ts` | SvelteKit Server-Load (Referenz) | Vorlage fuer den identischen API-Load-Block in der /locations-Route |
| `$env/dynamic/private` | SvelteKit Env-Modul | Liefert `GZ_API_BASE` fuer die Backend-URL im Server-Load |
| `$lib/types.ts` | TypeScript-Typen | `Location`-Interface; wird im Load-Typen und in `+page.svelte` genutzt |
| `frontend/e2e/compare-locations-rail.spec.ts` | Playwright-Spec (existierend) | Testet NewLocationWizard bereits vollstaendig auf `/compare`; darf NICHT dupliziert werden |

## Implementation Details

### 1. `frontend/src/routes/locations/+page.server.ts` — Redirect entfernen, API-Load ergaenzen

Den gesamten Datei-Inhalt durch einen echten `PageServerLoad`-Handler ersetzen, der identisch zum Compare-Loader funktioniert, jedoch nur `/api/locations` laedt:

```typescript
import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Location } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
    const session = cookies.get('gz_session');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (session) headers['Cookie'] = `gz_session=${session}`;
    const res = await fetch(`${API()}/api/locations`, { headers }).catch(() => null);
    const locations: Location[] = res?.ok ? await res.json() : [];
    return { locations: Array.isArray(locations) ? locations : [] };
};
```

### 2. `frontend/src/routes/locations/+page.svelte` — Infinite Recursion in refetchLocations() beheben

Die Funktion `refetchLocations()` ruft sich aktuell selbst rekursiv auf statt die API direkt abzufragen. Korrektur: direkter API-Call mit `fetch('/api/locations')` (clientseitig) und Zuweisung an die `locations`-Variable:

```typescript
// Vorher (Recursion):
async function refetchLocations() {
    await refetchLocations();
}

// Nachher (direkter API-Call):
async function refetchLocations() {
    const res = await fetch('/api/locations');
    if (res.ok) {
        locations = await res.json();
    }
}
```

Der genaue Variablenname richtet sich nach dem bestehenden Svelte-Store/`let`-Binding in `+page.svelte`. Kein neues Binding einfuehren — nur die Zuweisung korrigieren.

### 3. `frontend/e2e/locations.spec.ts` — 2 Strict-Mode-Locatoren einengen

Zwei `page.locator('text=...')`-Aufrufe, die 2+ DOM-Elemente matchen koennen, auf tabellenscoped Locatoren umstellen:

```typescript
// Vorher:
page.locator('text=E2E Testort')
page.locator('text=Profil Test')

// Nachher:
page.locator('table').getByText('E2E Testort')
page.locator('table').getByText('Profil Test')
```

Nur diese zwei Locatoren aendern. Alle anderen Assertions und der Test-Aufbau bleiben unveraendert.

### LoC-Budget

| Datei | Delta LoC | Zaehlt |
|-------|-----------|--------|
| `frontend/src/routes/locations/+page.server.ts` | ~12 (Redirect raus, Load rein) | nein (Frontend-Asset) |
| `frontend/src/routes/locations/+page.svelte` | +2 / -2 (Funktionsrumpf) | nein (Frontend-Asset) |
| `frontend/e2e/locations.spec.ts` | +2 / -2 (Locator-Strings) | nein (E2E-Test) |
| **Gesamt (zaehlend)** | **0** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Playwright navigiert zu `/locations`; SvelteKit verarbeitet den Request serverseitig
- **Output:** Die `/locations`-Seite rendert mit der Locations-Tabelle (oder Empty-State) aus dem API-Response; kein Redirect nach `/compare`
- **Side effects:** Nach dem Speichern einer neuen Location schliesst der Dialog, `refetchLocations()` laedt die aktualisierte Liste ohne Rekursion, und der neue Ort erscheint genau einmal in der Tabelle

## Acceptance Criteria

- **AC-1:** Given ein Playwright-Test navigiert zu `/locations` / When die Seite geladen ist / Then antwortet die Route mit HTTP 200 und rendert eine `<table>` oder einen `[data-testid="empty-state"]`-Block — kein Redirect auf `/compare` findet statt
  - Test: (populated after /tdd-red)

- **AC-2:** Given die `/locations`-Seite ist offen und ein Benutzer speichert eine neue Location ueber den Dialog / When `refetchLocations()` nach dem API-Call zurueckkehrt / Then ist der Dialog geschlossen, die neue Location erscheint genau einmal in der Tabelle, und es gibt keinen JavaScript-Stack-Overflow
  - Test: (populated after /tdd-red)

- **AC-3:** Given `locations.spec.ts` enthaelt `page.locator('table').getByText('E2E Testort')` / When der Playwright-Test ausgefuehrt wird und die Location in der Tabelle vorhanden ist / Then gibt der Locator exakt ein Element zurueck und keine Strict-Mode-Violation wird ausgeloest
  - Test: (populated after /tdd-red)

- **AC-4:** Given `compare-locations-rail.spec.ts` testet den NewLocationWizard auf `/compare` / When `locations.spec.ts` separat ausgefuehrt wird / Then enthaelt `locations.spec.ts` keine doppelten Wizard-Test-Szenarien, die bereits in `compare-locations-rail.spec.ts` vorhanden sind
  - Test: (populated after /tdd-red)

## Known Limitations

- **Kein Server-Side-Redirect-Schutz:** Es gibt keine automatische Guard-Logik, die verhindert, dass `+page.server.ts` erneut durch einen Redirect ersetzt wird. Das Risiko liegt beim naechsten Entwickler, der die Datei bearbeitet.
- **Client-seitiger Fetch in refetchLocations():** Der direkte `fetch('/api/locations')`-Call in `+page.svelte` nutzt keine SvelteKit `invalidate()`-Mechanik. Falls der Server-Load-Cache genutzt wird, koennte es zu kurzem Flicker kommen. Fuer den MVP-Scope ist das akzeptabel.

## Out of Scope

- Umschreiben der `locations.spec.ts`-Tests auf die `/compare`-Route (wuerde Duplikate zu `compare-locations-rail.spec.ts` erzeugen)
- Einfuehren von `invalidate()` oder `goto()` fuer SvelteKit-konformes Re-Fetching
- Aenderungen am Go-API-Endpoint `/api/locations`

## Changelog

- 2026-05-19: Initial spec erstellt. Dokumentiert zwei Fehler-Schichten in Issue #235: 301-Redirect in +page.server.ts (Wurzel-Ursache fuer alle 9 failing Tests) und Infinite-Recursion in refetchLocations() (Strict-Mode-Locator-Quelle). Fix-Plan: Load wiederherstellen, Recursion korrigieren, 2 Locatoren einengen.
