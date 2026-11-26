// E2E — Issue #2988 S4 (AC-16, AC-17): die Übersichten nutzen die Auflösung des Servers.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Echte Server (Staging in /e2e-verify); nur der Abbruch
// der Auflösung entsteht im Browser-Netz (page.route).
//   AC-16 Trip: Alarm-Zeile „—" bei gescheiterter Auflösung, sonst dieselbe Zahl wie der Reiter Wetter;
//         genau ein Aufruf der Auflösung beim Öffnen.
//   AC-17 Ortsvergleich: Übersicht ohne Aufruf der Auflösung.
//
//   cd frontend && npx playwright test e2e/rework-2988-uebersicht.spec.ts --workers=1 --trace off

import { test, expect, type Locator, type Page } from '@playwright/test';
import { cleanupTracked, openHub } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter, type Json } from './s3a2794-teil3.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';
const istAufloesung = (url: URL) => url.pathname === AUFLOESUNG;
/** Abweichungen, die die Zahl gegenüber der Vorlage ändern. */
const ABW = { metrics: { gust: { alarm_ab: 'never' }, wind: { alarm_ab: 'red' } } };

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

function aufloesungen(page: Page): Json[] {
	const liste: Json[] = [];
	page.on('request', (r) => {
		if (istAufloesung(new URL(r.url()))) liste.push(r.postDataJSON());
	});
	return liste;
}

/** Zeit-Feld der Zeile „Alarm-Auslöser" in der Karte „Briefings laufen" der Trip-Übersicht. */
function alarmZeit(page: Page): Locator {
	const karte = page
		.locator('[data-testid="hub-overview"]:visible div')
		.filter({ has: page.getByText('Briefings laufen', { exact: true }) })
		.last();
	return karte.getByText('Alarm-Auslöser', { exact: true }).locator('xpath=..').locator(':scope > span').nth(2);
}

test('AC-16 (Trip): Alarm-Zeile zeigt die Zahl des Reiters Wetter, ein Aufruf der Auflösung', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const hub = await seedWetter(page.request, 'route', { vorlageId: 'wandern', ampel: ABW });
	try {
		const reiter = await oeffneWetter(page, 'route', hub.id);
		const soll = /^(\d+) von (\d+) Metriken/.exec((await reiter.getByTestId(WT.zaehler).innerText()).trim());
		expect(soll, 'Messaufbau: der Reiter zeigt einen Zähler').not.toBeNull();

		const fragen = aufloesungen(page);
		await openHub(page, 'route', hub.id);
		await expect(alarmZeit(page)).toHaveText(new RegExp(`^${soll![1]} von ${soll![2]} Metriken`), { timeout: 15_000 });
		await page.waitForTimeout(1000);
		expect(fragen.length, `AC-16: Aufrufe der Auflösung ${JSON.stringify(fragen)}`).toBe(1);
		expect(fragen[0].eintraege[0]).toMatchObject({ ampel: { template: 'wandern', ...ABW } });
	} finally {
		await hub.aufraeumen();
	}
});

for (const [art, abbruch] of [
	['Netzabbruch', (r: Json) => r.abort('connectionfailed')],
	['HTTP 503', (r: Json) => r.fulfill({ status: 503, contentType: 'application/json', body: '{"error":"upstream_unreachable"}' })]
] as const) {
	test(`AC-16 (Trip, ${art}): Alarm-Zeile „—"`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, 'route', { vorlageId: 'wandern', ampel: ABW });
		try {
			const fragen = aufloesungen(page);
			await page.route(istAufloesung, abbruch);
			await openHub(page, 'route', hub.id);
			await expect.poll(() => fragen.length, { timeout: 15_000 }).toBeGreaterThanOrEqual(1);
			await page.waitForTimeout(500);
			await expect(alarmZeit(page)).toHaveText('—');
		} finally {
			await page.unroute(istAufloesung).catch(() => {});
			await hub.aufraeumen();
		}
	});
}

test('AC-17 (Ortsvergleich): Übersicht ohne Aufruf der Auflösung, Karte „Wetter" mit Zahl', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const hub = await seedWetter(page.request, 'vergleich', { vorlageId: 'wandern', ampel: ABW });
	try {
		const fragen = aufloesungen(page);
		await openHub(page, 'vergleich', hub.id);
		await expect(page.getByText(/\d+ Metriken im Briefing/).first()).toBeVisible({ timeout: 15_000 });
		await page.waitForTimeout(1500);
		expect(fragen, 'AC-17: die Vergleichs-Übersicht fragt die Auflösung').toEqual([]);
	} finally {
		await hub.aufraeumen();
	}
});
