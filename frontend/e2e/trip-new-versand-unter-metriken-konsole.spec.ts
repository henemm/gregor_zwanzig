// E2E — Issue #1743 (docs/specs/modules/feat_1743_reiter_aufraeumen.md), umgestellt mit #3332
// (docs/specs/modules/feat_3332_zustellung_anlegen_trip.md, AC-1/AC-6): auf /trips/new steht im
// Schritt Zustellung der Reiter Zustellung (wie im Hub) statt des Alt-Panels mit `bind:reportConfig`.
// Der Reiter meldet seinen Stand an den Editor, der ihn in `reportConfig` mischt — dieselbe Lage
// (Rueckkanal in den Anlege-Blob, aus dem der Eintrittstrip abgeleitet ist), in der #1552 eine
// Endlosschleife (`effect_update_depth_exceeded`) erzeugte.
//
// Warum E2E: die Unit-Harness ist SSR-only, `$effect` laeuft dort nie. Nur im
// echten Browser zeigt sich eine Effekt-Schleife als Konsolenfehler.
//
// Nutzerweg: Schritt Wetter oeffnen → Metrik anhaken → Schritt Zustellung → Versandzeit
// aendern → Fensterbreite Mobil ↔ Desktop wechseln (Desktop-/Mobil-Instanz
// tauschen) → keine Konsolenfehler, kein pageerror, Stand bleibt, Reaktivitaet lebt.
//
// Ausfuehren (lokaler CI-Stack):
//   cd frontend && npx playwright test e2e/trip-new-versand-unter-metriken-konsole.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { tippeDatum, tippeUhrzeit } from './helpers';
import { angezeigteZeit } from './s3b2795-zustellung.helpers';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };

async function oeffneWetterMobil(page: Page): Promise<void> {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('E2E-GZ #1743 Versand unter Metriken');
	await tippeDatum(page, page.getByTestId('trip-new-date-input'), new Date().toISOString().slice(0, 10));

	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	const stageCount = await page.locator('.tn-mobile input[type="file"][accept=".gpx"]').count();
	for (let i = 0; i < stageCount; i++) {
		const input = page.locator('.tn-mobile input[type="file"][accept=".gpx"]').first();
		await Promise.all([
			page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
			input.setInputFiles(gpx)
		]);
		await page.waitForTimeout(600);
	}

	await tabbar.getByRole('tab', { name: /Wetter/ }).click({ force: true });
	await expect(page.locator('.tn-mobile').getByTestId('wm2-grundauswahl')).toBeVisible({ timeout: 15_000 });
}

const reiter = (page: Page) => page.locator('[data-testid="zustellung-tab"][data-context="route"]:visible').first();
const morgenZeit = (page: Page) => reiter(page).locator('[data-testid="zustellung-morgen-zeit"]');

test('#1743/#3332: Metrik anhaken, Versandzeit im Reiter Zustellung ändern, Breite wechseln — keine Konsolenfehler', async ({ page }) => {
	const consoleErrors: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') consoleErrors.push(msg.text());
	});
	const pageErrors: string[] = [];
	page.on('pageerror', (err) => pageErrors.push(err.message));

	await oeffneWetterMobil(page);

	// Metrik anhaken (Bewölkung ist nicht Teil der Standardauswahl).
	const bewoelkung = page.locator('.tn-mobile').getByTestId('wm2-grundauswahl').locator('button[title="Bewölkung"]');
	await bewoelkung.click();
	await page.waitForTimeout(300);

	// Schritt Zustellung: der Reiter Zustellung, kein Alt-Panel (#3332 AC-1).
	await page.getByTestId('tn-mobile-tabbar').getByRole('tab', { name: /Zustellung/ }).click({ force: true });
	await expect(reiter(page)).toBeVisible({ timeout: 15_000 });
	await expect(page.locator('[data-testid="versand-abschnitt"]:visible')).toHaveCount(0);

	// Versandzeit ändern.
	await expect(morgenZeit(page)).toBeVisible({ timeout: 10_000 });
	await tippeUhrzeit(page, morgenZeit(page), '08:00');
	await page.keyboard.press('Tab');
	expect(await angezeigteZeit(morgenZeit(page))).toBe('08:00');

	// Breite wechseln: Mobil → Desktop → Mobil (Instanz-Tausch, #1552 Fix-Loop 4; #3332 AC-6).
	await page.setViewportSize(DESKTOP);
	await page.waitForTimeout(800);
	await expect(reiter(page)).toBeVisible({ timeout: 10_000 });
	expect(await angezeigteZeit(morgenZeit(page)), '#3332 AC-6: Stand nach Wechsel auf Desktop verloren').toBe('08:00');
	await page.setViewportSize(MOBILE);
	await page.waitForTimeout(800);
	await expect(reiter(page)).toBeVisible({ timeout: 10_000 });

	// Svelte meldet eine Effekt-Schleife erst nach wiederholten Zyklen.
	await page.waitForTimeout(1500);

	const alle = [...consoleErrors, ...pageErrors];
	expect(
		alle.filter((t) => t.includes('effect_update_depth_exceeded')),
		'Effekt-Endlosschleife im Schritt Zustellung'
	).toHaveLength(0);
	expect(alle, `Konsolenfehler/pageerror (erwartet: keine):\n${alle.join('\n')}`).toHaveLength(0);

	// Reaktivität lebt: die geänderte Versandzeit ist nach dem Breitenwechsel
	// noch da, und eine weitere Änderung kommt an.
	expect(await angezeigteZeit(morgenZeit(page))).toBe('08:00');
	await tippeUhrzeit(page, morgenZeit(page), '09:00');
	await page.keyboard.press('Tab');
	expect(await angezeigteZeit(morgenZeit(page))).toBe('09:00');
});
