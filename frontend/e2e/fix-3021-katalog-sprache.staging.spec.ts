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
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 11/14): die Stundenverlauf-Liste des Reiters
// Zustellung ist entfernt. Im Hub steht die Begruendung an der gesperrten Zelle „Stundenverlauf“ der
// Sonnenstunden in der Karte „Was steht wo“ (Reiter Wetter). Die Karte uebersetzt den Grund-Code der
// Endpoint-Antwort (`reason`) ueber den Katalog `wetter.wsw.grund.*`; Soll ist der Katalogtext der Kontosprache.
// Gegenprobe gegen den Endpoint: der Grund-Code der Antwort ist in beiden Sprachen derselbe.
//
// Zwei Sprachstaende nacheinander mit demselben Testkonto (Muster
// hub-kopf-c2-mockup.staging.spec.ts); afterEach stellt Deutsch wieder her.

import { test, expect, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { createTestLocation, createTestComparePreset, cleanupTracked } from './helpers';
import { folge, oeffneKarte, zelle } from './was-steht-wo.helpers';

type Lang = 'de' | 'en';

test.describe.configure({ mode: 'serial' });

async function sprache(page: Page, lang: Lang): Promise<void> {
	const res = await page.request.put('/api/auth/profile', { data: { language: lang } });
	expect(res.ok(), `Sprache ${lang} setzen: HTTP ${res.status()}`).toBeTruthy();
}

const SOLL: Record<Lang, string> = { de: 'kein Stundenwert', en: 'no hourly value' };

async function vergleichAnlegen(page: Page): Promise<string> {
	const s = Date.now();
	const a = await createTestLocation(page.request, { name: `3021-A-${s}` });
	const b = await createTestLocation(page.request, { name: `3021-B-${s}` });
	const preset = await createTestComparePreset(page.request, { name: `3021-${s}`, locationIds: [a.id, b.id] });
	const voll = await (await page.request.get(`/api/compare/presets/${preset.id}`)).json();
	const put = await page.request.put(`/api/compare/presets/${preset.id}`, {
		data: { ...voll, display_config: { ...(voll.display_config ?? {}), active_metrics: ['temp_max_c', 'sunny_hours_h'] } }
	});
	expect(put.ok(), `Grundauswahl setzen: HTTP ${put.status()}`).toBeTruthy();
	return preset.id;
}

/** Zeile der Sonnenstunden laut Endpoint und ihr Grund-Code an der Stelle Stundenverlauf. */
async function sonnenZeile(page: Page, id: string): Promise<{ metrik: string; reason: string }> {
	const a = await (await page.request.get(`/api/briefings/${id}/placements?kind=vergleich`)).json();
	const row = (a.rows as Array<{ metric_id: string; cells: Record<string, { reason: string | null }> }>).find((r) => /sun/.test(r.metric_id));
	expect(row, 'Messaufbau: keine Sonnenstunden-Zeile').toBeTruthy();
	expect(row!.cells.hourly?.reason, 'Messaufbau: Stundenverlauf der Sonnenstunden ist nicht begruendet gesperrt').toBeTruthy();
	return { metrik: row!.metric_id, reason: row!.cells.hourly.reason! };
}

async function grundImEditor(page: Page, id: string, metrik: string): Promise<string> {
	const karte = await oeffneKarte(page, 'vergleich', id);
	const grund = zelle(karte, metrik, 'hourly').locator('[data-slot="haken-grund"]');
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

test.describe('Issue #3021: Begruendung in Nutzersprache (Karte „Was steht wo“)', () => {
	test('AC-1: englischer Nutzer sieht die Sonnenstunden-Begruendung englisch', async ({ page }) => {
		const id = await vergleichAnlegen(page);
		await sprache(page, 'en');
		const { metrik, reason } = await sonnenZeile(page, id);
		expect(await grundImEditor(page, id, metrik), 'Begruendung steht nicht auf Englisch').toBe(SOLL.en);
		await page.screenshot({ path: '../docs/artifacts/fix-3021-katalog-sprache/ac-1-en-begruendung.png' });
		await sprache(page, 'de');
		expect((await sonnenZeile(page, id)).reason, 'Grund-Code sprachunabhaengig').toBe(reason);
	});

	test('AC-2: deutscher Nutzer sieht die Sonnenstunden-Begruendung wie bisher deutsch', async ({ page }) => {
		const id = await vergleichAnlegen(page);
		await sprache(page, 'de');
		const { metrik } = await sonnenZeile(page, id);
		expect(await grundImEditor(page, id, metrik)).toBe(SOLL.de);
		await page.screenshot({ path: '../docs/artifacts/fix-3021-katalog-sprache/ac-2-de-begruendung.png' });
	});

	test('AC-6: Sprachwechsel aendert nur die Begruendung, die Metrik-Zeilen bleiben dieselben', async ({ page }) => {
		const id = await vergleichAnlegen(page);
		await sprache(page, 'de');
		const { metrik } = await sonnenZeile(page, id);
		const deGrund = await grundImEditor(page, id, metrik);
		const deZeilen = await folge(page.locator('[data-testid="was-steht-wo"]:visible').first());
		await sprache(page, 'en');
		const enGrund = await grundImEditor(page, id, metrik);
		const enZeilen = await folge(page.locator('[data-testid="was-steht-wo"]:visible').first());
		expect(enZeilen).toEqual(deZeilen);
		expect([deGrund, enGrund]).toEqual([SOLL.de, SOLL.en]);
	});
});
