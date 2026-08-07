import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

// E2E — Staging-Befund Fix-Loop 2 (Issue #1552): /trips/new stürzt beim
// Laden, ohne jede Interaktion, mit `effect_update_depth_exceeded` ab.
//
// Root Cause: WeatherMetricsTab.svelte hatte einen $effect, der
// buildWeatherPayload() aufrief -- diese Funktion liest `trip!.display_config`
// und macht damit den `trip`-Prop zur getrackten Abhängigkeit des Effects. Im
// Anlege-Modus ist `trip` (`stubTrip` in TripNewEditor.svelte) ein `$derived`
// über `weatherMetrics`, das derselbe Effect via `onWeatherMetricsChange`
// schreibt (neue Array-Referenz bei jedem Aufruf) -- Kreis: Effect liest
// `trip` -> ruft onWeatherMetricsChange -> weatherMetrics neu -> stubTrip
// rechnet neu -> trip-Prop ändert sich -> derselbe Effect feuert erneut.
//
// Danach ist die gesamte Reaktivität der Seite tot (Symptom auf Staging:
// Tippen im Tour-Name-Feld ändert den DOM sichtbar, der State kommt nie an,
// der Hinweis "Tour-Name fehlt" bleibt stehen).
//
// Kein bestehender Test hätte das gefangen: Frontend-Unit-Tests lesen nur
// Quelltext (kein Mount, kein $effect-Lauf), serverseitig gerenderte Tests
// führen $effect nie aus. Dieser Test lädt die Seite tatsächlich.
//
// RED vor dem Fix: `effect_update_depth_exceeded` als Konsolenfehler,
// zusätzlich bleibt der "Tour-Name fehlt"-Hinweis nach dem Ausfüllen stehen.
//
// Ausführen (lokal, gegen den per Vite-Proxy erreichbaren Staging-Go-Server,
// Vorbild: issue-932-activity-type-route-tab.spec.ts):
//   cd frontend && npx playwright test e2e/trip-new-loads-without-effect-loop.spec.ts

test('Staging-Befund #1552 Fix-Loop 2: /trips/new lädt ohne Konsolenfehler, Reaktivität bleibt lebendig', async ({ page }) => {
	const consoleErrors: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') consoleErrors.push(msg.text());
	});
	const pageErrors: string[] = [];
	page.on('pageerror', (err) => pageErrors.push(err.message));

	await page.goto('/trips/new');
	await expect(page.getByTestId('trip-new-editor')).toBeVisible();

	// Die gemeldete Schleife trat OHNE jede Interaktion beim Laden auf --
	// kurze Wartezeit, damit ein re-entrant $effect überhaupt Zeit hat, sich
	// als Konsolenfehler zu zeigen (Svelte wirft erst nach wiederholten
	// Zyklen `effect_update_depth_exceeded`).
	await page.waitForTimeout(1500);

	const allErrors = [...consoleErrors, ...pageErrors];
	expect(
		allErrors,
		`Konsolenfehler beim Laden von /trips/new (erwartet: keine):\n${allErrors.join('\n')}`
	).toHaveLength(0);

	// Reaktivitäts-Beweis (das eigentliche Nutzersymptom): Tippen im
	// Tour-Name-Feld muss den Hinweis "Tour-Name fehlt" verschwinden lassen.
	// Bei toter Reaktivität ändert sich der DOM des Inputs zwar (Browser-
	// Default-Verhalten), der Svelte-State kommt aber nie an -- der Hinweis
	// bleibt stehen und der Weiter-Button bleibt für immer deaktiviert.
	await expect(page.getByText('⊘ Tour-Name fehlt')).toBeVisible();
	await page.getByTestId('trip-new-name-input-desktop').fill('E2E Fix-Loop-2 Regressionstest');
	await expect(page.getByText('⊘ Tour-Name fehlt')).not.toBeVisible();
});

// ═══════════════════════════════════════════════════════════════════════
// Fix-Loop 4 (Staging-Befund, 4x reproduziert): der Absturz aus Fix-Loop 2
// kehrte zurueck, sobald im Anlege-Dialog EINE Checkbox im Wetter-Reiter
// geklickt wird -- der obige Test klickt keine einzige Checkbox und liess
// genau das durchrutschen, obwohl er gruen war.
//
// Root Cause (isoliert per Instanz-Markierung, s. docs/artifacts/
// fix-1552-neuanlage-metrikverlust/red_effect_loop_playwright.txt):
// TripNewEditor.svelte mountete WeatherMetricsTab ZWEIMAL (Desktop+Mobile,
// Issue #941). Ein Klick erreicht nur EINE der beiden Instanzen -- danach
// unterscheiden sich deren `buckets` DAUERHAFT (die beruehrte hat 8, die
// unberuehrte weiterhin 7). Beide schreiben ihren fuer sich stabilen, aber
// voneinander verschiedenen Inhalt in denselben Rueckkanal (weatherMetrics)
// -- unbegrenztes Wechselspiel. Fix: isMobileViewport-Gate (Vorbild
// activity-dropdown, Issue #932) haelt nur EINE Instanz im DOM.
//
// Reale Ziel-Oberflaeche des Klicks: /trips/new, Reiter „Wetter-Metriken",
// Grundauswahl-Kacheln (WeatherV2Grundauswahl.svelte, Buttons mit
// title=Metrik-Label). Navigationspfad (GPX-Upload je Etappe) 1:1 aus
// issue-774-metrics-summary-persist.spec.ts / issue-776-metrics-toggle.spec.ts
// uebernommen (bewaehrter, mobiler Pfad zum Wetter-Reiter).
// ═══════════════════════════════════════════════════════════════════════

async function openNewTripWetterTab(page: Page, name: string): Promise<void> {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill(name);
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	const stageCount = await page.locator('.tn-mobile input[type="file"][accept=".gpx"]').count();
	for (let i = 0; i < stageCount; i++) {
		const input = page.locator('.tn-mobile input[type="file"][accept=".gpx"]').first();
		await Promise.all([
			page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
			input.setInputFiles(gpx),
		]);
		await page.waitForTimeout(600);
	}

	await tabbar.getByRole('tab', { name: /Wetter/ }).click({ force: true });
	await expect(page.locator('.tn-mobile').getByTestId('wm2-grundauswahl')).toBeVisible({ timeout: 15_000 });
}

test('Staging-Befund #1552 Fix-Loop 4: ein Checkbox-Klick im Wetter-Reiter darf die Seite nicht in eine Endlosschleife schicken', async ({ page }) => {
	const consoleErrors: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') consoleErrors.push(msg.text());
	});
	const pageErrors: string[] = [];
	page.on('pageerror', (err) => pageErrors.push(err.message));

	await openNewTripWetterTab(page, 'E2E Fix-Loop-4 Regressionstest');

	// Eine Groesse anhaken (Bewölkung ist NICHT Teil der 7 Standardgroessen,
	// steht also aus), eine abwaehlen (Sichtweite ist Teil der 7 Standard-
	// groessen, steht also an) -- exakt der vom Team Lead beschriebene
	// Nutzerweg ("egal ob anhaken oder abwählen").
	const grundauswahl = page.locator('.tn-mobile').getByTestId('wm2-grundauswahl');
	await grundauswahl.locator('button[title="Bewölkung"]').click();
	await page.waitForTimeout(300);
	await grundauswahl.locator('button[title="Sichtweite"]').click();

	// Die gemeldete Schleife trat ~1s NACH dem Klick auf -- Wartezeit analog
	// zum Ladefall oben, aber grosszuegiger (der Staging-Befund nennt "etwa
	// eine Sekunde danach").
	await page.waitForTimeout(2000);

	const allErrors = [...consoleErrors, ...pageErrors];
	expect(
		allErrors,
		`Konsolenfehler nach Checkbox-Klick im Wetter-Reiter (erwartet: keine):\n${allErrors.join('\n')}`
	).toHaveLength(0);

	// (a) Reaktivitäts-Beweis Nr. 1 (Team-Lead-Symptom „Route-Tab lässt sich
	// nicht mehr befüllen"): zurück zum Route-Tab, Name-Feld neu befüllen,
	// muss ankommen.
	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: 'Route', exact: true }).click({ force: true });
	const nameInput = page.getByTestId('trip-new-name-input-mobile');
	await nameInput.fill('E2E Fix-Loop-4 nach Checkbox-Klick');
	await expect(nameInput).toHaveValue('E2E Fix-Loop-4 nach Checkbox-Klick');

	// (b) Reaktivitäts-Beweis Nr. 2 (Team-Lead-Symptom „Trip speichern bleibt
	// dauerhaft deaktiviert"): Zeitplan-Tab besuchen (setzt ztVisited, s.
	// tripNewLogic.ts canSave()), danach muss der Speichern-Button bedienbar
	// sein.
	await tabbar.getByRole('tab', { name: /Zeitplan/ }).click({ force: true });
	await expect(page.getByTestId('tn-mobile-save')).toBeEnabled({ timeout: 5000 });
});
