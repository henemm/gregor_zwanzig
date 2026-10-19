// E2E (Live, Staging) — Issue #2283 (Epic #2345 P3): EIN Vorschau-Reiter, gleiche
// Anordnung in Trip-Hub und Ortsvergleich-Hub.
//
// Spec: docs/specs/modules/shared_preview_tab.md — AC-8 (Trip), AC-9 (genau ein
// Abruf an /api/briefings/{id}/preview, kein Abruf vor dem Oeffnen, keiner beim
// Kanal-/Ansichtswechsel), AC-10 (Morgen/Abend + Demo nur im Trip), AC-12
// (Vergleich), AC-13 (kein Sende-Knopf im Reiter).
// Workflow: feat-2283-vorschau-baustein
//
// Echte Abrufe gegen Staging (kein page.route-Ersatz) — die Vergleichs-Vorschau
// braucht bis zu 70 s. Echter Klickpfad: Reiter-Klick, Kanal-Klick, Ansicht-Klick.
// Markup-Vertrag (data-testid) wie im Kerntest
// frontend/src/lib/components/shared/__tests__/previewTab.test.ts.
//
// Laeuft NUR ueber /e2e-verify gegen Staging.

import { test, expect, type Page, type Locator } from '@playwright/test';
import {
	cleanupTracked,
	createTestComparePreset,
	createTestLocation,
	createTestTrip,
	login
} from './helpers.js';

const VORSCHAU = /\/api\/briefings\/[^/?]+\/preview\?/;

function zaehleVorschauAbrufe(page: Page): { anzahl: () => number; urls: string[] } {
	const urls: string[] = [];
	page.on('request', (req) => {
		if (VORSCHAU.test(req.url())) urls.push(req.url());
	});
	return { anzahl: () => urls.length, urls };
}

async function tripMitEtappe(page: Page): Promise<string> {
	const suffix = Date.now();
	const trip = await createTestTrip(page.request, {
		name: `Vorschau-Anordnung ${suffix}`,
		stages: [
			{
				id: `s-${suffix}`,
				name: 'Etappe 1',
				date: new Date(Date.now() + 86_400_000).toISOString().slice(0, 10),
				waypoints: [
					{ id: `w1-${suffix}`, name: 'Start', lat: 47.2692, lon: 11.4041, elevation_m: 574 },
					{ id: `w2-${suffix}`, name: 'Ziel', lat: 47.3, lon: 11.45, elevation_m: 900 }
				]
			}
		]
	});
	return trip.id;
}

async function vergleichMitZweiOrten(page: Page): Promise<string> {
	const s = Date.now();
	const a = await createTestLocation(page.request, { name: `Anordnung-A-${s}`, lat: 47.5, lon: 10.3 });
	const b = await createTestLocation(page.request, { name: `Anordnung-B-${s}`, lat: 47.55, lon: 10.35 });
	const preset = await createTestComparePreset(page.request, { locationIds: [a.id, b.id] });
	return preset.id;
}

/** Gemeinsame Anordnung — fuer beide Hubs IDENTISCH geprueft. */
async function pruefeAnordnung(panel: Locator, ctx: 'route' | 'vergleich', abrufe: { anzahl: () => number }) {
	const tab = panel.getByTestId('preview-tab');
	await expect(tab).toBeVisible({ timeout: 10_000 });
	await expect(tab).toHaveAttribute('data-context', ctx);

	// E-Mail (Start): iframe mit Inhalt, Desktop/Mobil-Umschalter
	const iframe = panel.getByTestId('email-iframe');
	await expect(iframe).toBeVisible({ timeout: 90_000 });
	expect((await iframe.getAttribute('srcdoc'))?.length ?? 0).toBeGreaterThan(100);
	const wrapper = panel.getByTestId('email-iframe-wrapper');
	await panel.getByTestId('preview-email-view-mobile').click();
	await expect(wrapper).toHaveAttribute('data-email-view', 'mobile');
	await panel.getByTestId('preview-email-view-desktop').click();
	await expect(wrapper).toHaveAttribute('data-email-view', 'desktop');

	// SMS im Telefonrahmen
	await panel.getByRole('button', { name: /^SMS/ }).click();
	const bubble = panel.getByTestId('sms-phone-wrapper').getByTestId('sms-token-bubble');
	await expect(bubble).toBeVisible();
	expect(((await bubble.textContent()) ?? '').trim().length).toBeGreaterThan(0);

	// Telegram als Chat-Blase
	await panel.getByRole('button', { name: /^Telegram/ }).click();
	const tg = panel.getByTestId('preview-telegram');
	await expect(tg).toBeVisible();
	expect(((await tg.textContent()) ?? '').trim().length).toBeGreaterThan(0);

	await panel.getByRole('button', { name: /^(E-Mail|Email)/ }).click();
	await expect(iframe).toBeVisible();

	// AC-9: genau EIN Abruf trotz Kanal- und Ansichtswechseln
	expect(abrufe.anzahl(), 'Kanal-/Ansichtswechsel hat die Vorschau neu geladen').toBe(1);

	// AC-13: kein Sende-Knopf im Reiter
	await expect(panel.getByRole('button', { name: /senden/i })).toHaveCount(0);
}

test.describe('#2283 Vorschau-Reiter: gleiche Anordnung in beiden Hubs', () => {
	test.setTimeout(180_000);
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});
	test.afterEach(async ({ page }) => {
		await cleanupTracked(page.request);
	});

	test('AC-8/AC-9/AC-10: Trip-Hub — Anordnung, ein Abruf, Morgen/Abend + Demo-Hinweis', async ({ page }, testInfo) => {
		const id = await tripMitEtappe(page);
		const abrufe = zaehleVorschauAbrufe(page);
		await page.goto(`/trips/${id}`);
		await page.waitForLoadState('networkidle');
		expect(abrufe.anzahl(), 'die Vorschau wurde schon vor dem Oeffnen des Reiters geladen').toBe(0);

		await page.getByTestId('trip-detail-tab-vorschau').first().click();
		const panel = page.getByTestId('trip-detail-panel-vorschau');
		await expect(panel).not.toContainText('Inhalt folgt mit Issue #189');
		await pruefeAnordnung(panel, 'route', abrufe);
		expect(new URL(abrufe.urls[0]).searchParams.get('kind')).toBe('route');

		await expect(panel.getByTestId('preview-demo-banner')).toBeVisible();
		await expect(panel.getByTestId('preview-controls')).toBeVisible();
		await page.screenshot({ path: testInfo.outputPath('trip-vorschau.png'), fullPage: true });

		// Morgen/Abend wirkt wie bisher: Umschalten laedt genau einmal neu
		const abend = panel.getByTestId('preview-controls').locator('input[value="evening"]');
		const morgen = panel.getByTestId('preview-controls').locator('input[value="morning"]');
		await ((await abend.isChecked()) ? morgen : abend).check();
		await expect.poll(() => abrufe.anzahl()).toBe(2);
	});

	test('AC-12/AC-9/AC-10: Ortsvergleich-Hub — dieselbe Anordnung, ein Abruf, kein Morgen/Abend/Demo', async ({
		page
	}, testInfo) => {
		const id = await vergleichMitZweiOrten(page);
		const abrufe = zaehleVorschauAbrufe(page);
		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		expect(abrufe.anzahl(), 'die Vorschau wurde schon beim Oeffnen des Hubs geladen (AC-15)').toBe(0);

		await page.locator('[data-testid="compare-detail-tab-vorschau"]:visible').click();
		const panel = page.locator('[data-testid="compare-detail-panel-vorschau"]:visible');
		await pruefeAnordnung(panel, 'vergleich', abrufe);
		expect([...new URL(abrufe.urls[0]).searchParams.keys()]).toEqual(['kind']);
		expect(new URL(abrufe.urls[0]).searchParams.get('kind')).toBe('vergleich');

		await expect(panel.getByTestId('preview-demo-banner')).toHaveCount(0);
		await expect(panel.getByTestId('preview-controls')).toHaveCount(0);
		await page.screenshot({ path: testInfo.outputPath('vergleich-vorschau.png'), fullPage: true });
	});
});
