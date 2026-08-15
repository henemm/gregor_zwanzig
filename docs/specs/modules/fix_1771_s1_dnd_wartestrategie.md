---
entity_id: fix_1771_s1_dnd_wartestrategie
type: bugfix
created: 2026-08-13
updated: 2026-08-13
status: draft
workflow: fix-1771-s1-ziehgeste-wartestrategie
tags: [testing, e2e, playwright, flake]
---

# Ziehgeste wartet auf Zustand statt auf Frist (#1771 Scheibe 1)

- **Issue:** #1771 (Titel: „E2E-Klickpfade sind unbewacht: Ziehhelfer flackert, und kein
  Playwright-Spec laeuft in der CI-Ampel") · Scheibe 1 von mehreren
- **Scope dieser Scheibe:** NUR Punkt 1 des Issues (Ziehhelfer-Flake) + der erste Kommentar
  (`weather-metrics-tab`-Sichtbarkeits-Flake). Punkt 2 des Issues (kein Playwright-Spec in der
  CI-Ampel) und der zweite Kommentar (157/16-Bestandsmessung) sind AUSDRÜCKLICH NICHT Teil
  dieser Scheibe — spätere Scheiben (S2/S3).
- **Typ:** Bugfix an Testinfrastruktur — kein Produktcode betroffen (`frontend/src/` bleibt
  unverändert), reine Playwright-E2E-Helfer (`frontend/e2e/`)

## Approval

- [ ] Approved

## Purpose

`dragDndZoneItem` — der Playwright-Helfer, der die `svelte-dnd-action`-Ziehgeste per
Maus-Events simuliert — existiert 5× zeichengleich (oder mit kleinen Varianten) kopiert und
verlässt sich nach dem Drop auf feste `waitForTimeout`-Fristen statt auf das tatsächliche
`finalize`-CustomEvent der Bibliothek. Das echte `finalize` feuert nachweislich unzuverlässig
(nie / sofort / nach ~1,9 s, siehe Diagnose in
`wetter-metriken-vorschau-entfernt.staging.spec.ts`) — der Helfer merkt das nie und lässt den
Aufrufer fälschlich einen `consider`-Zwischenstand (nur lokal sichtbar, nie committet) statt des
tatsächlich gespeicherten Zustands prüfen. Diese Scheibe macht die Wartestrategie
zustandsbasiert (auf das rohe `finalize`-Ereignis warten, bei Ausbleiben laut mit klarer
Fehlermeldung scheitern) UND dedupliziert die 5 Kopien zu einem einzigen exportierten Helfer in
`frontend/e2e/helpers.ts`. Ein zweiter, unabhängiger Flake (Wetter-Reiter wird nach Klick nicht
zuverlässig sichtbar, weil vor dem Klick nicht auf `networkidle` gewartet wird) bekommt in
denselben zwei betroffenen Dateien denselben Root-Cause-Fix, der an anderer Stelle im Repo
(`compare-hub-inline-edit.spec.ts`, `compare-metric-order.spec.ts`) bereits bewährt ist.

## Source

- **Files:**
  - `frontend/e2e/helpers.ts` — MODIFY (neuer Export)
  - `frontend/e2e/layout-tab-route.spec.ts` — MODIFY
  - `frontend/e2e/wetter-metriken-vorschau-entfernt.staging.spec.ts` — MODIFY
  - `frontend/e2e/compare-hub-inline-edit.spec.ts` — MODIFY
  - `frontend/e2e/compare-metric-order.spec.ts` — MODIFY
  - `frontend/e2e/compare-hourly-metric-order.spec.ts` — MODIFY
- **Identifier:** `export async function dragDndZoneItem(page: Page, source: Locator, target: Locator): Promise<void>` (neu, `helpers.ts`); je Aufrufstelle: lokale Funktionsdefinition `async function dragDndZoneItem(...)` entfällt zugunsten von `import { dragDndZoneItem } from './helpers.js'` (bzw. `.ts`, je Datei-Konvention)

> **Schicht-Hinweis:** Alle betroffenen Dateien liegen unter `frontend/e2e/` — Playwright-E2E-
> Testinfrastruktur, kein Produktcode (`frontend/src/`), keine Go-API, kein Python-Core.
> `frontend/src/lib/components/shared/dnd/SortableList.svelte` wurde zur Vertragsbestätigung
> gelesen (bestätigt: `finalize` ist ein auf `.sortable-zone` gebundenes DOM-CustomEvent,
> `onDndReorder` feuert ausschließlich bei `finalize`, nie bei `consider`), aber NICHT geändert.

## Estimated Scope

- **LoC:** −~110 (5 Kopien à ~20–25 Zeilen entfallen) / +~45 (1 gehärtete Funktion in
  `helpers.ts`) / +~10 (2× `networkidle`-Zeile + Kommentar) → netto schrumpfend
- **Files:** 6 (1 Helfer-Datei, 5 Specs)
- **Effort:** low — reine Testinfrastruktur, additiv/schärfer werdende Assertions, keine
  Verhaltensänderung der App

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `svelte-dnd-action` (npm-Bibliothek) | upstream library | Liefert die DOM-CustomEvents `consider`/`finalize` auf `.sortable-zone` — ihr öffentlicher Vertrag, nicht app-eigener Code. Diese Scheibe ändert nichts an der Bibliothek, nur an der Simulation ihrer Bedienung |
| `frontend/src/lib/components/shared/dnd/SortableList.svelte` | product component (nur gelesen) | Bestätigt den Event-Vertrag (`onconsider`/`onfinalize`, `onDndReorder` nur bei `finalize`) — Grundlage für die Wartestrategie, selbst nicht geändert |
| `frontend/e2e/layout-tab-route.spec.ts`, `wetter-metriken-vorschau-entfernt.staging.spec.ts`, `compare-hub-inline-edit.spec.ts`, `compare-metric-order.spec.ts`, `compare-hourly-metric-order.spec.ts` | tests (downstream) | Alle 5 definieren `dragDndZoneItem` heute eigenständig und müssen auf den Import aus `helpers.ts` umgestellt werden |
| `docs/specs/modules/layout_tab_route.md` | module (Referenz) | Enthält den ursprünglichen `dragDndZoneItem`-Kommentar-Kontext (Pointer-Simulation statt natives HTML5-Drag) — bleibt inhaltlich gültig, nur der Wartestrategie-Teil ändert sich |

## Implementation Details

### 1. Neue geteilte Funktion in `frontend/e2e/helpers.ts`

Zweitmeinung (Plan/Sonnet) eingeholt und bestätigt: `locator.evaluate()` zum Anhängen des
`finalize`-Listeners am echten DOM-Knoten der Zone, danach **`page.waitForFunction(fn, arg,
options)`** mit `zone.elementHandle()` als Argument statt handgebautem `setTimeout`-Polling —
nutzt Playwrights eigene Timeout-/Polling-Mechanik statt Eigenbau und liefert eine saubere
`TimeoutError`. Das `__gzFinalizeCount`-Expando auf dem DOM-Knoten bleibt zwischen den beiden
`evaluate`/`waitForFunction`-Aufrufen erhalten (Main-World, kein Isolation-Fallstrick), solange
der `.sortable-zone`-Container selbst nicht neu gemountet wird — bestätigt: `SortableList.svelte`
mountet nur die `.sortable-item`-Kinder neu, nicht die Zone selbst.

Zwei von der Zweitmeinung gefundene Korrekturen gegenüber dem allerersten Entwurf:

1. Ahnen-Zonen-Locator mit **`.last()`** statt `.first()` — bei mehreren `.sortable-zone`-
   Treffern in der XPath-Ahnenkette liefert `ancestor::*` Knoten in Dokumentreihenfolge von der
   Wurzel nach unten; `.last()` trifft die NÄCHSTGELEGENE (innerste) Zone. Aktuell keine
   Verschachtelung bekannt, aber defensiv korrekt.
2. **`page.waitForFunction`** statt manueller In-Page-Promise mit `setTimeout`-Schleife (s.o.).

```ts
export async function dragDndZoneItem(page: Page, source: Locator, target: Locator): Promise<void> {
	await source.scrollIntoViewIfNeeded();
	await target.scrollIntoViewIfNeeded();

	const zone = source
		.locator('xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " sortable-zone ")]')
		.last();
	const zoneHandle = await zone.elementHandle();
	if (!zoneHandle) throw new Error('dragDndZoneItem: keine .sortable-zone-Ahnenzone gefunden');

	const before = await zoneHandle.evaluate((el) => {
		const marker = el as HTMLElement & { __gzFinalizeCount?: number };
		if (marker.__gzFinalizeCount === undefined) {
			marker.__gzFinalizeCount = 0;
			el.addEventListener('finalize', () => {
				marker.__gzFinalizeCount = (marker.__gzFinalizeCount ?? 0) + 1;
			});
		}
		return marker.__gzFinalizeCount;
	});

	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) throw new Error('dragDndZoneItem: source/target ohne BoundingBox');

	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2);
	await page.mouse.down();
	await page.mouse.move(sourceBox.x + sourceBox.width / 2, sourceBox.y + sourceBox.height / 2 - 12, { steps: 6 });
	await page.waitForTimeout(120);
	await page.mouse.move(targetBox.x + targetBox.width / 2, targetBox.y + targetBox.height / 2, { steps: 15 });
	await page.waitForTimeout(120);
	await page.mouse.up();

	try {
		await page.waitForFunction(
			({ el, before }) =>
				((el as HTMLElement & { __gzFinalizeCount?: number }).__gzFinalizeCount ?? 0) > before,
			{ el: zoneHandle, before },
			{ timeout: 5_000, polling: 100 }
		);
	} catch {
		throw new Error(
			'dragDndZoneItem: kein finalize-Ereignis nach dem Ziehen (#1771) — svelte-dnd-action hat den Drag nicht committet'
		);
	}
}
```

Zeitfenster bewusst 5 s (großzügig über dem gemessenen Worst Case von ~1,9 s) — verhindert, dass
ein zu kurzes Fenster den Flake nur verlagert (Test schlägt am Helfer fehl statt an der
Fach-Assertion, obwohl `finalize` nur etwas später gefeuert hätte).

### 2. Deduplizierung der 5 Aufrufstellen

`layout-tab-route.spec.ts`, `wetter-metriken-vorschau-entfernt.staging.spec.ts`,
`compare-hub-inline-edit.spec.ts`, `compare-metric-order.spec.ts`,
`compare-hourly-metric-order.spec.ts`: jeweils die lokale `async function dragDndZoneItem(...)`
samt Kommentarblock entfernen, stattdessen `import { dragDndZoneItem } from './helpers.js'` (bzw.
projektübliche Import-Endung, siehe bestehender `login`-Import in `layout-tab-route.spec.ts:14`)
ergänzen. Aufrufstellen selbst (`await dragDndZoneItem(page, source, target)`) bleiben
unverändert — Signatur ist identisch zu allen 5 Kopien.

Bei `compare-hourly-metric-order.spec.ts` bleibt der bestehende
`Promise.all([page.waitForResponse(PUT), dragDndZoneItem(...)])`-Wrapper am Aufrufer zusätzlich
bestehen — der Helfer-Fix ändert nichts an diesem Muster, macht es nur robuster (das `finalize`-
Warten sitzt jetzt eine Ebene tiefer, im Helfer selbst, statt sich implizit auf den PUT zu
verlassen).

Bei den 3 Dateien mit bereits vorhandenem PUT-Wait am Aufrufer
(`compare-hub-inline-edit.spec.ts`, `compare-metric-order.spec.ts`,
`compare-hourly-metric-order.spec.ts`) hat ausbleibendes `finalize` schon heute einen Timeout zur
Folge — der Helfer-Fix macht das Scheitern nur früher und mit klarerer Meldung, ändert das
Endergebnis (rot bei Ausbleiben) nicht.

Vereinheitlichung bewusst angeglichen: `scrollIntoViewIfNeeded()` für `source` UND `target` läuft
jetzt in allen 5 Aufrufstellen (fehlte z.B. bisher in `compare-hub-inline-edit.spec.ts`) —
schadet nicht, wenn das Element schon sichtbar ist.

### 3. `networkidle` vor Wetter-Reiter-Klick (zweiter Flake, Issue-Kommentar 1)

In `layout-tab-route.spec.ts::openMetricsTab()` (aktuell Z. 122–136) und
`wetter-metriken-vorschau-entfernt.staging.spec.ts::openMetricsTab()` (aktuell Z. 160–171) wird
vor dem Klick auf `trip-detail-tab-weather` eine `await page.waitForLoadState('networkidle')`
ergänzt — analog zum bereits bewährten Muster in `compare-hub-inline-edit.spec.ts:112` (dort vor
dem Klick auf `compare-detail-tab-orte`). Dokumentierter Root Cause dieses Musters (Fund aus
`compare-hub-inline-edit.spec.ts`/`compare-metric-order.spec.ts`): SvelteKit liefert die
Tab-Leiste server-gerendert VOR der Hydration aus — ein Klick, der vor dem Attachen der
Event-Listener ankommt, geht spurlos verloren. Beispiel-Diff (`layout-tab-route.spec.ts`):

```ts
async function openMetricsTab(page: Page, id: string) {
	await page.goto(`/trips/${id}?tab=weather`);
	await page.waitForLoadState('networkidle'); // NEU — Hydration-Race, #1771
	const weatherTabBtn = page.getByTestId('trip-detail-tab-weather');
	await expect(weatherTabBtn).toBeVisible({ timeout: 10_000 });
	await weatherTabBtn.click();
	// ... unverändert
}
```

Reihenfolge: Härtung UND Deduplizierung des `dragDndZoneItem`-Helfers laufen in einem Schritt
(nicht getrennt) — eine gehärtete Kopie als Zwischenstand anzulegen und danach zu deduplizieren
wäre doppelte Arbeit an denselben Zeilen. Der `networkidle`-Fix ist unabhängig und wird im
selben Commit mitgezogen (beide Findings gehören zu demselben Issue und derselben Scheibe).

## Expected Behavior

- **Input:** Ein Playwright-Test ruft `dragDndZoneItem(page, source, target)` auf zwei
  `.sortable-zone`-Locators auf, ODER ein Test öffnet über `openMetricsTab()` den
  Wetter-Metriken-Tab eines Trips.
- **Output:**
  - `dragDndZoneItem` kehrt genau dann zurück, wenn das `finalize`-DOM-Ereignis auf der zur
    `source` gehörenden `.sortable-zone` tatsächlich gefeuert hat — nicht früher (kein
    `consider`-Zwischenstand mehr, kein fixes `waitForTimeout` als Ersatz für ein echtes Signal).
  - Bleibt `finalize` binnen 5 s aus, wirft `dragDndZoneItem` einen `Error` mit der Meldung
    „kein finalize-Ereignis nach dem Ziehen (#1771) — svelte-dnd-action hat den Drag nicht
    committet" statt lautlos zurückzukehren und den Aufrufer einen falschen Erfolg annehmen zu
    lassen.
  - `openMetricsTab()` in den beiden betroffenen Dateien klickt den Wetter-Reiter erst, nachdem
    `networkidle` erreicht ist — der Klick geht nicht mehr spurlos verloren, wenn er vor der
    Hydration ankommt.
- **Side effects:** Keine Änderung an Produktcode oder App-Verhalten. Alle Aufrufstellen (5
  Specs) verhalten sich für einen erfolgreichen Drag identisch zu vorher, nur robuster gegen den
  gemessenen Timing-Flake; bei tatsächlich ausbleibendem `finalize` scheitert der Test jetzt
  früher und mit eindeutigerer Fehlermeldung statt später an einer scheinbar unabhängigen
  Fach-Assertion.

## Acceptance Criteria

- **AC-1:** Given ein Playwright-Test ruft den geteilten `dragDndZoneItem`-Helfer aus
  `helpers.ts` mit `source`/`target`-Locators auf einer `.sortable-zone` auf, und
  `svelte-dnd-action` feuert nach dem simulierten Drop KEIN `finalize`-CustomEvent auf der
  zugehörigen Zone / When 5 Sekunden vergangen sind / Then wirft `dragDndZoneItem` einen `Error`
  mit einer Meldung, die „finalize" und „#1771" enthält, statt lautlos zurückzukehren.
  - Test: Ein Playwright-Test simuliert eine `.sortable-zone`, deren JavaScript das
    `finalize`-CustomEvent absichtlich NIE feuert (z.B. `page.addInitScript` unterdrückt den
    Listener oder eine präparierte Test-Fixture-Seite ohne `svelte-dnd-action`-Anbindung), ruft
    `dragDndZoneItem` auf und erwartet (`await expect(...).rejects.toThrow(...)`), dass der
    Aufruf mit genau dieser Fehlermeldung scheitert — nicht, dass irgendein anderer, späterer
    Test in derselben Datei rot wird.

- **AC-2:** Given `svelte-dnd-action` feuert nach dem simulierten Drop das `finalize`-Ereignis
  auf der `.sortable-zone` (real, in einer der 5 umgestellten Spec-Dateien gegen Staging oder
  eine reale Test-Trip-/Preset-Seite) / When `dragDndZoneItem` aufgerufen wird / Then kehrt die
  Funktion erst NACH dem `finalize`-Ereignis zurück, und der direkt danach gelesene Zustand
  (z.B. PUT-Body, DOM-Reihenfolge nach Reload) entspricht dem tatsächlich committeten Ergebnis,
  nicht einem `consider`-Zwischenstand.
  - Test: Bestehender Playwright-Test (z.B. `compare-hub-inline-edit.spec.ts` AC-14/15 „Ort per
    Drag umsortieren löst PUT mit neuer location_ids-Reihenfolge aus, überlebt Reload") läuft
    gegen Staging unverändert grün — der PUT-Request, der direkt nach `dragDndZoneItem` erwartet
    wird, enthält die tatsächlich vom Nutzer gezogene neue Reihenfolge, und ein Seiten-Reload
    bestätigt die Persistenz.

- **AC-3:** Given alle 5 betroffenen Spec-Dateien (`layout-tab-route.spec.ts`,
  `wetter-metriken-vorschau-entfernt.staging.spec.ts`, `compare-hub-inline-edit.spec.ts`,
  `compare-metric-order.spec.ts`, `compare-hourly-metric-order.spec.ts`) importieren
  `dragDndZoneItem` aus `helpers.ts` statt eine eigene lokale Kopie zu definieren / When die
  bestehenden Testsuiten dieser 5 Dateien ausgeführt werden / Then bleiben alle darin
  enthaltenen, vorher grünen Ziehgeste-Tests grün — kein Test schlägt durch die Deduplizierung
  neu fehl.
  - Test: Playwright-Läufe der 5 Dateien (bzw. der jeweils zugehörigen Staging-Config) nach der
    Umstellung — Regressionsnachweis über tatsächliches grünes Testverhalten (Drag-Ergebnis,
    PUT-Body, Persistenz nach Reload), nicht über einen bloßen Import-Zeilen-Check im
    Quelltext.

- **AC-4:** Given `layout-tab-route.spec.ts::openMetricsTab()` und
  `wetter-metriken-vorschau-entfernt.staging.spec.ts::openMetricsTab()` warten jetzt vor dem
  Klick auf `trip-detail-tab-weather` auf `networkidle` / When ein Test den Wetter-Metriken-Tab
  über diese Helferfunktion mehrfach hintereinander öffnet (Wiederholungslauf, z.B. 5×) / Then
  wird der `weather-metrics-tab` bei jedem Durchlauf sichtbar, ohne den bisher beobachteten
  Flake (Tab nicht binnen 10 s sichtbar, weil der Klick vor der Hydration ankam).
  - Test: Playwright-Test (oder Wiederholungslauf des bestehenden Tests mit `--repeat-each=5`
    o.ä.) ruft `openMetricsTab()` mehrfach auf und prüft bei jedem Durchlauf
    `await expect(tab).toBeVisible({ timeout: 10_000 })` — kein einziger Durchlauf timet aus.

## Known Limitations

- **KL-1 · `weather-metrics-tab`-Flake ist nicht abschließend root-caused**, nur ein plausibles
  Muster aus einer anderen Datei (`compare-hub-inline-edit.spec.ts`) übertragen — der PO-Kommentar
  im Issue selbst sagt „sieht nach... aus, nicht nach einem Produktfehler", keine abschließende
  Diagnose. Der Fix bleibt dennoch risikoarm, da rein additiv (ein zusätzliches Warten kann
  bestehendes Verhalten nicht verschlechtern, nur Race-Fenster schließen).
- **KL-2 · Mehrere `.sortable-zone`-Instanzen auf einer Seite** werden über die Ahnen-Suche mit
  `.last()` (innerste Zone) aufgelöst — aktuell keine Verschachtelung im Produktcode bekannt,
  aber die Annahme ist nicht durch einen eigenen Test abgesichert (kein bekannter Fall zum
  Nachstellen vorhanden).
- **KL-3 · Scope-Grenze:** Diese Scheibe fasst NICHT an: welche Specs in die CI-Ampel
  aufgenommen werden (spätere Scheibe), eine Vollständigkeits-Bestandsaufnahme aller Specs,
  Playwright-Konfigurationsdateien (bleiben unberührt).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testinfrastruktur-Härtung (zustandsbasiertes statt fristbasiertes Warten)
  und Deduplizierung eines bestehenden Hilfsmusters — keine neue Architekturentscheidung, keine
  Änderung an Produktcode, Datenmodell oder Kanälen.

## Changelog

- 2026-08-13: Initial spec created
