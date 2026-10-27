// E2E — Issue #1743 (docs/specs/modules/feat_1743_reiter_aufraeumen.md): auf
// /trips/new steht der Versand nicht mehr in einem eigenen Schritt, sondern
// unten im Schritt „Wetter-Metriken" (geteilter Baustein
// WetterMetrikenVersandPanel, Abschnitt `#versand`). Damit leben Metrik-Auswahl
// und Versand-Blob (`bind:reportConfig`) in EINEM Schritt — genau die Lage, in
// der #1552 eine Endlosschleife (`effect_update_depth_exceeded`) erzeugte.
//
// Warum E2E: die Unit-Harness ist SSR-only, `$effect` laeuft dort nie. Nur im
// echten Browser zeigt sich eine Effekt-Schleife als Konsolenfehler.
//
// Nutzerweg: Schritt Wetter-Metriken oeffnen → Metrik anhaken → Versandzeit
// aendern → Fensterbreite Mobil ↔ Desktop wechseln (Desktop-/Mobil-Instanz
// tauschen) → keine Konsolenfehler, kein pageerror, Reaktivitaet lebt.
//
// Ausfuehren (lokaler CI-Stack):
//   cd frontend && npx playwright test e2e/trip-new-versand-unter-metriken-konsole.spec.ts

import { test, expect, type Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };
const DESKTOP = { width: 1280, height: 900 };

async function oeffneWetterMetrikenMobil(page: Page): Promise<void> {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('E2E-GZ #1743 Versand unter Metriken');
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

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

test('#1743: Metrik anhaken, Versandzeit ändern, Breite wechseln — keine Konsolenfehler', async ({ page }) => {
	const consoleErrors: string[] = [];
	page.on('console', (msg) => {
		if (msg.type() === 'error') consoleErrors.push(msg.text());
	});
	const pageErrors: string[] = [];
	page.on('pageerror', (err) => pageErrors.push(err.message));

	await oeffneWetterMetrikenMobil(page);

	// Der Versand-Abschnitt steht im selben Schritt unter den Wetter-Metriken.
	const abschnitt = page.locator('[data-testid="versand-abschnitt"]:visible').first();
	await expect(abschnitt).toBeVisible({ timeout: 15_000 });

	// Metrik anhaken (Bewölkung ist nicht Teil der Standardauswahl).
	const bewoelkung = page.locator('.tn-mobile').getByTestId('wm2-grundauswahl').locator('button[title="Bewölkung"]');
	await bewoelkung.click();
	await page.waitForTimeout(300);

	// Versandzeit ändern.
	const morgen = abschnitt.locator('[data-testid="report-morning-time"]:visible').first();
	await expect(morgen).toBeVisible({ timeout: 10_000 });
	await morgen.selectOption('08:00');
	await expect(morgen).toHaveValue('08:00');

	// Breite wechseln: Mobil → Desktop → Mobil (Instanz-Tausch, #1552 Fix-Loop 4).
	await page.setViewportSize(DESKTOP);
	await page.waitForTimeout(800);
	await expect(page.locator('[data-testid="versand-abschnitt"]:visible').first()).toBeVisible({ timeout: 10_000 });
	await page.setViewportSize(MOBILE);
	await page.waitForTimeout(800);
	const abschnittNachher = page.locator('[data-testid="versand-abschnitt"]:visible').first();
	await expect(abschnittNachher).toBeVisible({ timeout: 10_000 });

	// Svelte meldet eine Effekt-Schleife erst nach wiederholten Zyklen.
	await page.waitForTimeout(1500);

	const alle = [...consoleErrors, ...pageErrors];
	expect(
		alle.filter((t) => t.includes('effect_update_depth_exceeded')),
		'Effekt-Endlosschleife im Schritt Wetter-Metriken + Versand'
	).toHaveLength(0);
	expect(alle, `Konsolenfehler/pageerror (erwartet: keine):\n${alle.join('\n')}`).toHaveLength(0);

	// Reaktivität lebt: die geänderte Versandzeit ist nach dem Breitenwechsel
	// noch da, und eine weitere Änderung kommt an.
	const morgenNachher = abschnittNachher.locator('[data-testid="report-morning-time"]:visible').first();
	await expect(morgenNachher).toHaveValue('08:00');
	await morgenNachher.selectOption('09:00');
	await expect(morgenNachher).toHaveValue('09:00');
});
