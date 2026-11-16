// gz-eigenstaendig: Die Begruendung „stuendlich nicht waehlbar" steht nur im Stundenverlauf-Block des Ortsvergleichs (COMPARE_ONLY_SECTIONS); der Trip-Wertebereiche-Reiter zeigt keinen Server-Begruendungstext -- kein Trip-Pendant
// Staging-Validierung — Issue #3021 (Epic #2644, ADR-0104): der Vergleichs-
// Metrik-Katalog wird in der Nutzersprache geladen.
//
// Spec: docs/specs/modules/i18n_katalog_sprache_3021.md (AC-1, AC-2, AC-6)
// Workflow: fix-3021-katalog-sprache
//
// Nachweis am Wirkort: die Begruendung bei Sonnenstunden
// (testid `compare-layout-hourly-reason-sunshine`) muss in der Kontosprache
// erscheinen. Der Soll-Text kommt direkt vom Endpoint je Sprache
// (`/api/compare/metrics?lang=…`), nicht aus einer Frontend-Konstante.
//
// RED-Hinweis: vor dem Fix ruft der Lader den Katalog ohne `lang` ab ⇒ der
// englische Nutzer sieht den deutschen Text ⇒ der EN-Test ist rot.
//
// Zwei Sprachstaende nacheinander mit demselben Testkonto (Muster
// hub-kopf-c2-mockup.staging.spec.ts); afterEach stellt Deutsch wieder her.

import { test, expect, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { createTestLocation, createTestComparePreset, cleanupTracked } from './helpers';

type Lang = 'de' | 'en';
type Eintrag = { metric_id?: string; hourlyNotSelectableReason?: string };

test.describe.configure({ mode: 'serial' });

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

async function sollGrund(page: Page, lang: Lang): Promise<string> {
	const res = await page.request.get(`/api/compare/metrics?lang=${lang}`);
	expect(res.ok(), `GET /api/compare/metrics?lang=${lang}: HTTP ${res.status()}`).toBeTruthy();
	const body = (await res.json()) as { metrics: Eintrag[] };
	const e = body.metrics.find((m) => m.metric_id === 'sunshine' && m.hourlyNotSelectableReason);
	expect(e, 'Katalog liefert keine Sonnenstunden-Begruendung').toBeTruthy();
	return e!.hourlyNotSelectableReason!;
}

async function vergleichAnlegen(page: Page): Promise<string> {
	const s = Date.now();
	const a = await createTestLocation(page.request, { name: `3021-A-${s}` });
	const b = await createTestLocation(page.request, { name: `3021-B-${s}` });
	const preset = await createTestComparePreset(page.request, {
		name: `3021-${s}`,
		locationIds: [a.id, b.id]
	});
	return preset.id;
}

async function grundImEditor(page: Page, id: string): Promise<string> {
	await page.goto(`/compare/${id}?tab=zustellung`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-zustellung"]:visible').click();
	const block = page.locator('[data-testid="weather-metrics-stundenverlauf"]:visible');
	await expect(block, 'Stundenverlauf-Block fehlt').toBeVisible({ timeout: 15_000 });
	const grund = block.locator('[data-testid="compare-layout-hourly-reason-sunshine"]');
	await expect(grund).toBeVisible({ timeout: 10_000 });
	return (await grund.textContent())?.trim() ?? '';
}

test.beforeEach(async ({ baseURL, page }) => {
	assertNotProdBaseURL(baseURL ?? '');
	await page.setViewportSize({ width: 1280, height: 900 });
});

test.afterEach(async ({ page }) => {
	await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
	await cleanupTracked(page.request);
});

test.describe('Issue #3021: Vergleichs-Katalog in Nutzersprache (Staging)', () => {
	test('AC-1: englischer Nutzer sieht die Sonnenstunden-Begruendung englisch', async ({ page }) => {
		const id = await vergleichAnlegen(page);
		const soll = await sollGrund(page, 'en');
		const deutsch = await sollGrund(page, 'de');
		expect(soll, 'Vorbedingung: Endpoint liefert je Sprache verschiedene Texte').not.toBe(deutsch);
		await sprache(page, 'en');
		const ist = await grundImEditor(page, id);
		expect(ist, 'Begruendung steht nicht auf Englisch').toBe(soll);
		await page.screenshot({ path: '../docs/artifacts/fix-3021-katalog-sprache/ac-1-en-begruendung.png' });
	});

	test('AC-2: deutscher Nutzer sieht die Sonnenstunden-Begruendung wie bisher deutsch', async ({ page }) => {
		const id = await vergleichAnlegen(page);
		const soll = await sollGrund(page, 'de');
		await sprache(page, 'de');
		const ist = await grundImEditor(page, id);
		expect(ist).toBe(soll);
		await page.screenshot({ path: '../docs/artifacts/fix-3021-katalog-sprache/ac-2-de-begruendung.png' });
	});

	test('AC-6: Sprachwechsel aendert nur die Begruendung, die Metrik-Zeilen bleiben dieselben', async ({ page }) => {
		const id = await vergleichAnlegen(page);
		const zeilen = async () =>
			page
				.locator('[data-testid="weather-metrics-stundenverlauf"]:visible [data-testid^="compare-layout-hourly-metric-"]')
				.evaluateAll((els) => els.map((e) => e.getAttribute('data-testid')));
		await sprache(page, 'de');
		const deGrund = await grundImEditor(page, id);
		const deZeilen = await zeilen();
		await sprache(page, 'en');
		const enGrund = await grundImEditor(page, id);
		const enZeilen = await zeilen();
		expect(enZeilen).toEqual(deZeilen);
		expect(enGrund).toBe(await sollGrund(page, 'en'));
		expect(deGrund).toBe(await sollGrund(page, 'de'));
	});
});
