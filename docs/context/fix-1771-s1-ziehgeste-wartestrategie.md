# Context: #1771 Scheibe 1 — Ziehgeste wartet auf Zustand statt auf Frist

## Request Summary

`dragDndZoneItem` (5× zeichengleich kopiert) simuliert die `svelte-dnd-action`-Ziehgeste per
Maus-Events und verlässt sich danach auf feste `waitForTimeout`-Fristen. Das echte
`finalize`-Ereignis der Bibliothek feuert nachweislich unzuverlässig (nie / sofort / nach
~1,9 s) — der Helfer merkt das nie und lässt den Aufrufer einen `consider`-Zwischenstand statt
des committeten Zustands prüfen. Scheibe 1 macht die Wartestrategie zustandsbasiert: nach dem
Ziehen auf das rohe `finalize`-CustomEvent warten, bei Ausbleiben laut scheitern. Ein zweiter,
unabhängiger Flake (Tab-Sichtbarkeit nach Klick) bekommt denselben Root-Cause-Fix wie an anderer
Stelle im Repo bereits bewährt.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/e2e/helpers.ts` | Bestehender geteilter Helfer-Ort (`login`, `fillStep1`, `createTestLocation`) — Zielort für den EINEN neuen `dragDndZoneItem`-Export, der die 5 Kopien ablöst |
| `frontend/e2e/layout-tab-route.spec.ts` | Eigene `dragDndZoneItem`-Kopie (Z.23-48); AC-3 ist der im Issue reproduzierte Flake. `openMetricsTab()` (Z.122-136) klickt den Wetter-Reiter OHNE vorheriges `networkidle` |
| `frontend/e2e/wetter-metriken-vorschau-entfernt.staging.spec.ts` | Eigene `dragDndZoneItem`-Kopie; AC-2 nutzt Ziehen. `openMetricsTab()` (Z.160-171) — Ziel des zweiten Issue-Kommentars: `weather-metrics-tab` wird 1/4 Läufen nicht binnen 10 s sichtbar. Auch hier fehlt `networkidle` vor dem Klick |
| `frontend/e2e/compare-hub-inline-edit.spec.ts` | Eigene `dragDndZoneItem`-Kopie; AC-14/15 wartet bereits per `page.waitForResponse(PUT)` — bereits vorhanden `networkidle` vor Tab-Klicks (Z.112 etc.) |
| `frontend/e2e/compare-metric-order.spec.ts` | Eigene `dragDndZoneItem`-Kopie; AC-3 nutzt `expect.poll` auf `puts.length` — bereits `networkidle` vor Tab-Klick (Z.144) |
| `frontend/e2e/compare-hourly-metric-order.spec.ts` | Eigene `dragDndZoneItem`-Kopie; nutzt bereits `Promise.all([page.waitForResponse(PUT), dragDndZoneItem(...)])` — das im Issue referenzierte „bereits umgesetzte" Vorbild, ABER als PUT-Wait am Aufrufer, nicht als `finalize`-Wait im Helfer selbst |
| `frontend/src/lib/components/shared/dnd/SortableList.svelte` | Produktcode (NICHT geändert) — bestätigt den Vertrag: `onconsider`/`onfinalize` sind auf `.sortable-zone` gebundene DOM-CustomEvents (`consider`/`finalize`), `onDndReorder` feuert ausschließlich bei `finalize` |

## Existing Patterns

- **`networkidle` vor Tab-Klick gegen Hydration-Race:** in `compare-hub-inline-edit.spec.ts` und
  `compare-metric-order.spec.ts` bereits etabliert, mit dokumentiertem Fund („Validator-Fund,
  staging, reproduzierbar ~2/3: SvelteKit liefert die Tab-Leiste server-gerendert VOR der
  Hydration aus — ein Klick, der vor dem Attachen der Event-Listener ankommt, geht spurlos
  verloren"). `layout-tab-route.spec.ts` und `wetter-metriken-vorschau-entfernt.staging.spec.ts`
  haben diesen Wait NICHT — plausibler Root Cause für den zweiten im Issue gemeldeten Flake.
- **Zustandsbasiertes Warten auf einen Netzwerk-Effekt:** `compare-hub-inline-edit.spec.ts` und
  `compare-hourly-metric-order.spec.ts` setzen `page.waitForResponse(PUT)` VOR dem Drag auf und
  awaiten das Ergebnis danach — ein echtes, kausal an die Aktion gekoppeltes Signal statt einer
  Frist. Dasselbe Prinzip (auf ein echtes Signal statt eine Frist warten) trägt S1, nur auf der
  Ebene des `finalize`-DOM-Ereignisses statt des resultierenden PUT — dadurch wirkt der Fix in
  allen 5 Dateien einheitlich, auch dort, wo (noch) kein PUT-Wait am Aufrufer existiert.
- **Geteilte Helfer-Datei `frontend/e2e/helpers.ts`:** bereits Ort für `login`, `fillStep1`,
  `createTestLocation` — kein neues Muster, nur ein fehlender Eintrag.

## Dependencies

- Upstream: `svelte-dnd-action` (Bibliothek) — Event-Namen `consider`/`finalize` sind ihr
  öffentlicher Vertrag, nicht app-eigener Code.
- Downstream: alle 5 Specs, die `dragDndZoneItem` heute je eigenständig definieren.

## Existing Specs

Keine Entity-Spec vorhanden — Testinfrastruktur, kein fachliches Modul. Referenz-Spec für den
AC-3-Flake-Kontext: `docs/specs/modules/layout_tab_route.md`.

## Risks & Considerations

- **Falsch-negativ vermeiden:** ein zu kurzes Zeitfenster für das `finalize`-Warten würde den
  Flake nur verlagern (Test schlägt jetzt am Helfer fehl statt an der Fach-Assertion). Gemessener
  Worst Case war ~1,9 s — Zeitfenster muss großzügig darüber liegen (Vorschlag: 5 s).
  **Bei den 3 Dateien mit vorhandenem PUT-Wait am Aufrufer (`compare-hub-inline-edit`,
  `compare-metric-order`, `compare-hourly-metric-order`) hat ausbleibendes `finalize` schon
  heute einen Timeout zur Folge — der Helfer-Fix macht das Scheitern nur früher und mit klarerer
  Meldung, ändert das Endergebnis (rot bei Ausbleiben) nicht.**
- **Mehrere `.sortable-zone`-Instanzen auf einer Seite:** der Helfer muss die zur `source`
  gehörende Zone auflösen (Ahnen-Suche via XPath), nicht global horchen — sonst wird ein
  `finalize` einer FREMDEN Zone fälschlich als Erfolg gewertet.
- **Deduplizierung ist Chance auf neues Drift-Risiko:** 5 Kopien → 1 Funktion heißt, alle 5
  Aufrufstellen müssen den Import umstellen; kleine API-Unterschiede zwischen den Kopien
  (`scrollIntoViewIfNeeded` fehlt z.B. in `compare-hub-inline-edit.spec.ts`, s.o.) werden durch
  die Vereinheitlichung bewusst angeglichen (immer scrollen — schadet nicht, wenn schon sichtbar).
- **`weather-metrics-tab`-Flake ist nicht bewiesen root-caused**, nur ein plausibles Muster aus
  einer anderen Datei übertragen — PO-Kommentar selbst sagt „sieht nach... aus, nicht nach einem
  Produktfehler", keine abschließende Diagnose. Fix bleibt dennoch risikoarm (rein additiv).
- **Scope-Grenze:** S1 fasst NICHT an: welche Specs in die CI-Ampel kommen (S3), Vollständigkeits-
  Bestandsaufnahme aller 157 Specs (S2), Playwright-Konfigurationsdateien (29 Stück, unberührt).

## Analysis

### Type
Bug (fälschlich blockierendes Gate — Testinfrastruktur, kein Produktfehler; #1771 Punkt 1 + Kommentar 1).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/e2e/helpers.ts` | MODIFY | Neue exportierte `dragDndZoneItem(page, source, target)` — Ahnen-Zonen-Auflösung + `finalize`-Warten via `page.waitForFunction` |
| `frontend/e2e/layout-tab-route.spec.ts` | MODIFY | Eigene Kopie entfernen, Import aus `helpers.ts`; `networkidle` vor `trip-detail-tab-weather`-Klick in `openMetricsTab()` ergänzen |
| `frontend/e2e/wetter-metriken-vorschau-entfernt.staging.spec.ts` | MODIFY | Eigene Kopie entfernen, Import aus `helpers.ts`; `networkidle` vor Tab-Klick in `openMetricsTab()` ergänzen |
| `frontend/e2e/compare-hub-inline-edit.spec.ts` | MODIFY | Eigene Kopie entfernen, Import aus `helpers.ts` (Aufrufstelle/Assertions unverändert) |
| `frontend/e2e/compare-metric-order.spec.ts` | MODIFY | Eigene Kopie entfernen, Import aus `helpers.ts` (Aufrufstelle/Assertions unverändert) |
| `frontend/e2e/compare-hourly-metric-order.spec.ts` | MODIFY | Eigene Kopie entfernen, Import aus `helpers.ts` (der bestehende `Promise.all([waitForResponse, dragDndZoneItem])`-Wrapper bleibt zusätzlich bestehen) |

Keine Änderung an Produktcode (`frontend/src/`), keine neuen Dateien, keine Playwright-Configs.

### Scope Assessment
- Files: 6 (1 Helfer-Datei, 5 Specs)
- Estimated LoC: −~110 (5 Kopien à ~20-25 Zeilen entfallen) / +~45 (1 gehärtete Funktion in helpers.ts) / +~10 (2× `networkidle`-Zeile + Kommentar) → netto **schrumpfend**
- Risk Level: LOW — reine Testinfrastruktur, kein Produktpfad; additiv/schärfer werdende Assertions, keine Verhaltensänderung der App

### Technical Approach

Zweitmeinung (Plan/Sonnet) eingeholt und bestätigt: `locator.evaluate()` zum Listener-Anhängen +
danach **`page.waitForFunction(fn, arg, options)`** mit `zone.elementHandle()` als Argument statt
handgebautem `setTimeout`-Polling — nutzt Playwrights eigene Timeout-/Polling-Mechanik statt
Eigenbau, liefert saubere `TimeoutError`. `__gzFinalizeCount`-Expando-Property auf dem echten
DOM-Knoten bleibt zwischen den beiden `evaluate`/`waitForFunction`-Aufrufen erhalten (Main-World,
kein Isolation-Fallstrick), solange der `.sortable-zone`-Container selbst nicht neu gemountet wird
(bestätigt: `SortableList.svelte` mountet nur die `.sortable-item`-Kinder neu, nicht die Zone).

Zwei vom Zweitmeinungs-Agent gefundene Korrekturen gegenüber dem ursprünglichen Entwurf:
1. Ahnen-Zonen-Locator mit **`.last()`** statt `.first()` — bei mehreren `.sortable-zone`-Treffern
   in der XPath-Ahnenkette liefert `ancestor::*` Knoten in Dokumentreihenfolge von der Wurzel nach
   unten; `.last()` trifft die NÄCHSTGELEGENE (innerste) Zone. Aktuell keine Verschachtelung
   bekannt, aber defensiv korrekt.
2. **`page.waitForFunction`** statt manueller In-Page-Promise mit `setTimeout`-Schleife (s.o.).

Umsetzung in `frontend/e2e/helpers.ts`:
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

Reihenfolge: Härtung UND Deduplizierung in einem Schritt (nicht getrennt) — eine gehärtete Kopie
als Zwischenstand anzulegen und danach zu deduplizieren wäre doppelte Arbeit an denselben Zeilen.
Der `networkidle`-Fix (2. Finding) ist unabhängig und wird im selben Commit mitgezogen (beide
Findings sind Teil desselben Issues und derselben Scheibe, keine Notwendigkeit für Trennung).

### Dependencies
Keine neuen. `svelte-dnd-action`s `finalize`-Event ist bereits stabil in Produktion genutzt.

### Open Questions
Keine blockierenden — Ansatz ist durch Zweitmeinung bestätigt.
