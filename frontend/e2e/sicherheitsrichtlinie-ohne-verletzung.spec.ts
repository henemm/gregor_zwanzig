// Issue #2961 (FE6) — die Content-Security-Policy ist auf den Kernseiten aktiv
// und die App verletzt sie nirgends.
//
// Spec: docs/specs/modules/security_haertung_2026_11_frontend.md (AC-4)
//
// Je Seite zwei Pruefungen:
//   1. Die Seitenantwort traegt die Richtlinie (sonst waere „keine Verletzung"
//      ein Bericht ueber nichts).
//   2. Waehrend Laden und Bedienen meldet der Browser keine Verletzung — weder
//      als `securitypolicyviolation`-Ereignis (in jedem Frame, auch im
//      srcdoc-iframe der Alarm-Vorschau) noch als Konsolenmeldung.
// Eine Positivkontrolle belegt, dass der Sammler eine echte Verletzung sieht.
//
// Ausfuehrung:
//   cd frontend && npx playwright test e2e/sicherheitsrichtlinie-ohne-verletzung.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { createTestComparePreset, createTestLocation, createTestTrip, registerForCleanup } from './helpers';

type Fenster = Window & { __gzCspVerletzungen?: string[] };

/** Haengt den Sammler in jedes Dokument (auch iframes) und liefert die Konsolen-Treffer. */
async function sammlerAnhaengen(page: Page): Promise<string[]> {
	const konsole: string[] = [];
	page.on('console', (meldung) => {
		if (/content security policy/i.test(meldung.text())) konsole.push(meldung.text());
	});
	await page.addInitScript(() => {
		const w = window as Window & { __gzCspVerletzungen?: string[] };
		w.__gzCspVerletzungen = [];
		document.addEventListener('securitypolicyviolation', (e) => {
			w.__gzCspVerletzungen!.push(`${e.violatedDirective} ${e.blockedURI}`);
		});
	});
	return konsole;
}

async function verletzungen(page: Page, konsole: string[]): Promise<string[]> {
	const ereignisse: string[] = [];
	for (const frame of page.frames()) {
		const liste = await frame
			.evaluate(() => (window as Fenster).__gzCspVerletzungen ?? [])
			.catch(() => [] as string[]);
		ereignisse.push(...liste);
	}
	return [...ereignisse, ...konsole];
}

async function richtlinieAktiv(page: Page, pfad: string): Promise<void> {
	const antwort = await page.goto(pfad);
	expect(antwort, `${pfad}: keine Antwort`).not.toBeNull();
	const csp = antwort!.headers()['content-security-policy'] ?? '';
	expect(csp, `${pfad}: Seitenantwort ohne Content-Security-Policy`).toContain("default-src 'self'");
	expect(csp).toContain("object-src 'none'");
	expect(csp).toContain("frame-ancestors 'none'");
	expect(csp, `${pfad}: script-src erlaubt Inline-Skripte pauschal`).not.toMatch(
		/script-src[^;]*'unsafe-(inline|eval)'/
	);
	expect(antwort!.headers()['x-content-type-options']).toBe('nosniff');
	expect(antwort!.headers()['x-frame-options']).toBe('DENY');
	await page.waitForLoadState('networkidle');
}

test('AC-4: Positivkontrolle — ein Inline-Skript wird blockiert und gemeldet', async ({ page }) => {
	const konsole = await sammlerAnhaengen(page);
	await richtlinieAktiv(page, '/trips');
	await page.evaluate(() => {
		const s = document.createElement('script');
		s.textContent = '(window).__gzInlineLief = 1;';
		document.head.appendChild(s);
	});
	await expect.poll(async () => (await verletzungen(page, konsole)).length).toBeGreaterThan(0);
	expect(await page.evaluate(() => (window as Window & { __gzInlineLief?: number }).__gzInlineLief)).toBeUndefined();
});

test.describe('AC-4: keine Verletzung der Richtlinie', () => {
	test('Anmeldeseite (ohne Sitzung)', async ({ browser }) => {
		const kontext = await browser.newContext({ storageState: { cookies: [], origins: [] } });
		try {
			const page = await kontext.newPage();
			const konsole = await sammlerAnhaengen(page);
			await richtlinieAktiv(page, '/login');
			await expect(page.locator('input[name="username"]')).toBeVisible();
			expect(await verletzungen(page, konsole)).toEqual([]);
		} finally {
			await kontext.close();
		}
	});

	test('Startseite, Trip-Liste und Konto', async ({ page }) => {
		const konsole = await sammlerAnhaengen(page);
		for (const pfad of ['/', '/trips', '/account']) {
			await richtlinieAktiv(page, pfad);
			await expect(page.locator('main').first()).toBeVisible();
		}
		expect(await verletzungen(page, konsole)).toEqual([]);
	});

	test('Trip-Detail mit Karte', async ({ page }) => {
		const trip = await createTestTrip(page.request, {
			stages: [
				{
					id: `stage-${Date.now()}`,
					name: 'Etappe',
					date: new Date().toISOString().slice(0, 10),
					waypoints: [
						{ id: 'wp-1', name: 'Start', lat: 47.27, lon: 11.4, elevation_m: 600 },
						{ id: 'wp-2', name: 'Ziel', lat: 47.28, lon: 11.42, elevation_m: 900 }
					]
				}
			]
		});
		const konsole = await sammlerAnhaengen(page);
		await richtlinieAktiv(page, `/trips/${trip.id}`);
		await page.getByTestId('trip-detail-tab-etappen').click();
		const karte = page.locator('[data-testid="map-card"] [data-testid="map-canvas"]');
		await expect(karte.locator('.leaflet-marker-icon')).toHaveCount(2, { timeout: 15_000 });
		await expect(karte.locator('.leaflet-tile').first()).toBeAttached({ timeout: 15_000 });
		await karte.locator('.leaflet-marker-icon').nth(1).dispatchEvent('click');
		await expect(karte.locator('.leaflet-popup-content')).toHaveText('2. Ziel');
		expect(await verletzungen(page, konsole)).toEqual([]);
	});

	test('Vergleich', async ({ page }) => {
		const ort = await createTestLocation(page.request, {});
		const vergleich = await createTestComparePreset(page.request, { locationIds: [ort.id] });
		const konsole = await sammlerAnhaengen(page);
		await richtlinieAktiv(page, `/compare/${vergleich.id}`);
		await expect(page.locator('main').first()).toBeVisible();
		expect(await verletzungen(page, konsole)).toEqual([]);
	});

	test('Alarm-Vorschau (Mail im srcdoc-iframe)', async ({ page }) => {
		test.setTimeout(150_000);
		const tripId = `e2e-gz-2961-csp-${Date.now()}`;
		const res = await page.request.post('/api/trips', {
			data: {
				id: tripId,
				name: 'E2E-GZ-2961 Richtlinie Alarm-Vorschau',
				stages: [
					{
						id: `${tripId}-s1`,
						name: 'Etappe 1',
						date: new Date().toISOString().slice(0, 10),
						waypoints: [{ id: `${tripId}-wp1`, name: 'Start', lat: 47.27, lon: 11.4, elevation_m: 600 }]
					}
				],
				display_config: { metrics: [{ metric_id: 'gust', enabled: true }] },
				alert_rules: [
					{ id: 'r1', kind: 'absolute', metric: 'wind_gust', threshold: 50, severity: 'warning', enabled: true }
				]
			}
		});
		expect([200, 201]).toContain(res.status());
		registerForCleanup('trip', tripId);

		const konsole = await sammlerAnhaengen(page);
		await richtlinieAktiv(page, `/trips/${tripId}`);
		await page.getByTestId('trip-detail-tab-zustellung').first().click();
		const panel = page.getByTestId('trip-detail-panel-zustellung');
		await panel.getByTestId('alert-preview-load-btn').click();
		const iframe = panel.getByTestId('alert-preview-iframe');
		await expect(iframe, 'Alarm-Vorschau kam nicht').toBeVisible({ timeout: 120_000 });
		const inhalt = page.frameLocator('[data-testid="alert-preview-iframe"]').locator('body');
		await expect(inhalt).not.toBeEmpty();
		expect(await verletzungen(page, konsole)).toEqual([]);
	});
});
