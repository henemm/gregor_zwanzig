# Context: Issue #235 — locations.spec.ts Strict-Mode-Locator-Konflikte

## Request Summary
Drei E2E-Tests in `frontend/e2e/locations.spec.ts` schlagen fehl. Ursache: Playwright Strict-Mode-Verletzungen (mehrfache Matches) und ein Page-Load-Problem. Fix: Präzisere Locatoren + ggf. `data-testid`-Ergänzungen.

## Failing Tests

| Test | Zeile | Fehler |
|------|-------|--------|
| `locations page loads and shows table or empty state` | 16 | Weder `table` noch `[data-testid="empty-state"]` sichtbar |
| `create location with coordinates` | 54 | `locator('text=E2E Testort')` → 2 Matches (Sidebar + Dialog-Label) |
| `activity profile badge shown after selection` | 136 | `locator('text=Profil Test')` → 4 Matches (Sidebar + UI-Elemente) |

## Kritischer Befund: /locations → /compare Redirect

`frontend/src/routes/locations/+page.server.ts` macht einen 301-Redirect auf `/compare`:
```typescript
export const load: PageServerLoad = async () => {
    redirect(301, '/compare');  // SvelteKit redirect() wirft intern, kein throw nötig
};
```

Das bedeutet: alle Tests navigieren zu `/locations` → landen auf `/compare`.

### Konsequenzen
- Die `locations/+page.svelte` (mit Tabelle + "Neuer Ort"-Button) wird **nicht** gerendert
- Die Compare-Seite hat **keinen** `table` initial sichtbar und kein `[data-testid="empty-state"]` → Test 1 schlägt fehl
- Die Compare-Seite hat **keinen** "Neuer Ort"-Button (nur `+ NEU` in LocationsRail) → Tests 2+3 könnten schon am Button-Klick scheitern
- `LocationsRail` zeigt Location-Namen in der Sidebar → erklärt Multiple-Matches nach dem Speichern

### Offene Frage (für Phase 2)
Ob Tests 2+3 tatsächlich bis zur Strict-Mode-Violation kommen (Location wird erstellt via NewLocationWizard → erscheint in Rail UND anderem Element), oder ob sie bereits am `getByRole('button', { name: 'Neuer Ort' })` scheitern — muss in Phase 2 mit Testlauf geklärt werden.

## Related Files

| File | Relevanz |
|------|----------|
| `frontend/e2e/locations.spec.ts` | Zu fixende Testdatei |
| `frontend/src/routes/locations/+page.server.ts` | Redirect-Quelle (301 → /compare) |
| `frontend/src/routes/locations/+page.svelte` | Locations-UI (wird nicht gerendert) |
| `frontend/src/routes/compare/+page.svelte` | Ziel des Redirects, hat LocationsRail |
| `frontend/src/lib/components/compare/LocationsRail.svelte` | Sidebar mit Location-Namen (ungrouped: `<span>{loc.name}</span>`) |
| `frontend/src/lib/components/compare/NewLocationWizard.svelte` | 3-Schritt-Wizard für neue Locations auf /compare |
| `frontend/e2e/helpers.ts` | Login-Helper, auth via storageState |

## Bekannte Bugs in locations/+page.svelte (relevant für Entscheidung)

`refetchLocations()` ruft sich selbst auf (unendliche Rekursion):
```js
async function refetchLocations() {
    refetching = true;
    try { await refetchLocations(); }  // BUG: selbst-aufrufend!
    finally { refetching = false; }
}
```
Diese Funktion ist auf der aktuell bedienten `/compare`-Seite irrelevant, aber muss mitberücksichtigt werden wenn `/locations` Page wieder aktiviert wird.

## Bestehende Patterns (wie andere E2E-Tests das lösen)

In `locations.spec.ts` selbst (Tests die bereits gut lokalisieren):
```js
// Gut: Container-Locator
const firstRow = page.locator('table tbody tr').first();
// Gut: hasText-Filter
const row = page.locator('table tbody tr', { hasText: 'Profil Test' });
```

In anderen Spec-Dateien: `data-testid`-Attribute werden häufig verwendet.

## Fix-Strategie (aus Issue #235)

**Option A (empfohlen):** Präzise Container-Locatoren statt freie Text-Suche:
- `page.locator('table').getByText('E2E Testort')` → auf Tabelle beschränkt
- `page.locator('table tbody tr', { hasText: '...' })` → Zeile direkt
- `getByTestId('location-row-...')` → wenn `data-testid` ergänzt werden

**Kernfrage für Phase 2:** Sollen die Tests die `/compare`-Page testen (mit NewLocationWizard), oder soll die Redirect-Logik geändert werden, damit `/locations` wieder direkt bedient wird?

## Risks & Considerations

- **Redirect**: Tests müssen entweder auf `/compare` umgestellt werden ODER die Redirect-Logik muss geändert werden. Beides ändert den Scope.
- **refetchLocations-Bug**: Wenn `/locations` wieder direkten Zugang erhält, muss dieser Bug gefixt werden (verhindert dass neu angelegte Locations sichtbar werden).
- **Scope-Warnung**: Issue sagt "Klein ~6-9 LoC". Mit Redirect-Problematik könnte der Scope größer werden.
- **data-testid-Ergänzungen**: Falls `data-testid="location-row-{id}"` in `Table.Row` in `+page.svelte` ergänzt wird — funktioniert nur wenn `/locations` Page tatsächlich bedient wird.
