import { test, expect } from '@playwright/test';

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
