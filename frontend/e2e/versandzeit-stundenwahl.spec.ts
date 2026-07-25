// E2E — Issue #1379: Versandzeit wird als volle Stunde aus einer Auswahlliste
// gewaehlt (kein eintippbares Uhrzeit-Feld mehr). Echter Klick-Pfad gegen das
// laufende Backend, kein Mock.
//
// Spec: docs/specs/modules/versandzeit_stundenwahl.md (AC-1, AC-2, AC-4).
// AC-3 (Ortsvergleich) deckt versand-tab-vergleich.spec.ts ab — derselbe
// geteilte Baustein VTSchedulePlan.
//
// Ausfuehren: cd frontend && npx playwright test e2e/versandzeit-stundenwahl.spec.ts

import { test, expect, type Locator } from '@playwright/test';
import * as path from 'node:path';

const TRIP_ID = 'e2e-gz-versandzeit-stundenwahl';
const TRIP_NAME = 'E2E-GZ-Versandzeit Stundenwahl';
const MOBILE = { width: 390, height: 844 };

const seedBody = {
	id: TRIP_ID,
	name: TRIP_NAME,
	region: 'Korsika',
	stages: [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01',
		  waypoints: [{ id: 'a', name: 'Start', lat: 42.0, lon: 9.0, elevation_m: 800 }] }
	],
	report_config: {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00',
		send_email: true
	}
};

/** Alle Options-Werte der Auswahlliste — Grundlage der AC-1-Pruefung. */
async function optionValues(select: Locator): Promise<string[]> {
	// `?? []`: ist das Feld (noch) ein <input>, soll die Zusicherung beim
	// Aufrufer sprechen ("0 statt 24") statt ein TypeError zu fliegen.
	return select.evaluate((el) => Array.from((el as HTMLSelectElement).options ?? []).map((o) => o.value));
}

test.describe('Issue #1379: Versandzeit nur als volle Stunde waehlbar', () => {
	test.beforeAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`);
		const res = await request.post('/api/trips', { data: seedBody });
		expect([200, 201], `Trip-Seed fehlgeschlagen: HTTP ${res.status()}`).toContain(res.status());
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`);
	});

	test('AC-1/AC-2: Stunden-Auswahl im Versand-Reiter uebersteht Speichern + Reload', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}?tab=briefings`);
		const morning = page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(morning).toBeVisible({ timeout: 15_000 });

		// AC-1: genau die 24 vollen Stunden, kein Eintrag mit Minuten.
		const values = await optionValues(morning);
		expect(values.length, `Auswahlliste muss 24 Eintraege haben, hat ${values.length}`).toBe(24);
		expect([values[0], values[23]]).toEqual(['00:00', '23:00']);
		expect(values.every((v) => /^\d{2}:00$/.test(v))).toBeTruthy();

		// AC-1: es gibt kein frei beschreibbares Uhrzeit-Feld mehr.
		await expect(page.locator('input[type="time"][data-testid="report-morning-time"]')).toHaveCount(0);

		// AC-2: Stunde waehlen → Auto-Save → Reload → derselbe Wert.
		await morning.selectOption('09:00');
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		await page.reload();
		const morningAfter = page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(morningAfter).toHaveValue('09:00', { timeout: 15_000 });
	});

	// Bug-Reproduktion aus Nutzersicht (#1379): "Ich trage 05:30 ein, es sagt
	// gespeichert — nach dem Neuladen steht 05:00." Bewusst auf BEIDEN Staenden
	// lauffaehig: die Oberflaeche nimmt eine Minuten-Eingabe entweder gar nicht
	// erst an, ODER der Wert haelt. Alter Stand (<input type="time">): 05:30 wird
	// angenommen und springt still auf 05:00 -> ROT. Neuer Stand: -> GRUEN.
	test('Bug #1379: die Oberflaeche nimmt keine Uhrzeit an, die sie danach still aendert', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}?tab=briefings`);
		const morning = page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(morning).toBeVisible({ timeout: 15_000 });

		const istEingabefeld = await morning.evaluate((el) => el.tagName.toLowerCase() === 'input');
		if (!istEingabefeld) {
			// Weg A: Minuten sind gar nicht anwaehlbar — der Bug kann nicht entstehen.
			const mitMinuten = (await optionValues(morning)).filter((v) => !/^\d{2}:00$/.test(v));
			expect(mitMinuten, `Auswahl bietet Eintraege mit Minuten an: ${mitMinuten}`).toEqual([]);
			return;
		}

		// Weg B: es gibt ein Eingabefeld — dann muss der eingegebene Wert halten.
		await morning.fill('05:30');
		await morning.blur();
		const eingegeben = await morning.inputValue();
		await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});
		await page.reload();
		const nachher = page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(
			nachher,
			`Nutzer stellte ${eingegeben} ein, die Oberflaeche bestaetigte "gespeichert" — nach dem Neuladen steht ein anderer Wert da (stiller Verlust, #1379)`
		).toHaveValue(eingegeben, { timeout: 15_000 });
	});

	test('AC-4: dieselbe Stunden-Auswahl beim Anlegen unter /trips/new', async ({ page }) => {
		// Pfad bis zum Zeitplan-Tab wie in issue-776-metrics-toggle.spec.ts.
		await page.setViewportSize(MOBILE);
		await page.goto('/trips/new');
		await page.getByTestId('trip-new-name-input-mobile').fill('E2E-GZ-Versandzeit neu');
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
		await tabbar.getByRole('tab', { name: /Zeitplan/ }).click({ force: true });

		const morning = page.locator('.tn-mobile [data-testid="report-morning-time"]').first();
		await expect(morning).toBeVisible({ timeout: 15_000 });
		const values = await optionValues(morning);
		expect(values.length).toBe(24);
		expect(values.every((v) => /^\d{2}:00$/.test(v))).toBeTruthy();

		// Bedienbar wie beim Bearbeiten — kein Unterschied Anlegen/Bearbeiten.
		await morning.selectOption('06:00');
		await expect(morning).toHaveValue('06:00');
	});
});
