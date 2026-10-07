// TDD RED — E2E, Issue #2124 AC-2/AC-3/AC-4: Versand-Auslöser teilen EINEN
// Laufzustand (`$lib/utils/sendOutcome.ts`) und zeigen bei 502 „Ergebnis unklar".
//
// Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md (§4, AC-2..AC-4)
//
// WARUM IM BROWSER: Der node-Test `src/lib/utils/sendOutcome.test.ts` bewacht das
// Modul. Ob die .svelte-Auslöser es WIRKLICH nutzen, zeigt nur der echte Klick
// (Dateiinhalt-Grep ist als Nachweis untersagt, die SSR-Harness sieht keine
// Klick-Handler). Zusatz, nicht einziger Beweis — E2E ist nicht in der CI-Ampel.
//
// Nicht vakuum: Jeder Auslöser sperrt sich heute schon SELBST (`disabled` während
// des eigenen Laufs). Deshalb wird der zweite Versuch über einen ANDEREN Auslöser
// für denselben Trip/Vergleich gemacht — heute geht dann ein zweiter Request ab.
//
// Der Versand wird per `page.route` abgefangen und erst auf ein Signal des Tests
// beantwortet (Promise, kein sleep). Es geht nichts an Python oder Empfänger.
//
// Ausführen (aus frontend/, lokaler E2E-Stack bzw. Staging-Config):
//   npx playwright test e2e/send-in-flight-guard.spec.ts
// NICHT in ci_e2e_specs.txt (Ratsche unberührt); läuft in /50 und /e2e-verify.

import { test, expect, type Page, type Route } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const DESKTOP = { width: 1440, height: 900 };
const UNCLEAR = 'Ergebnis unklar — Versand kann noch laufen, nicht erneut senden';

type Halter = { requests: string[]; freigeben: (status?: number, body?: string) => Promise<void> };

/** Hält jeden POST auf `pattern` offen, bis der Test `freigeben()` ruft. */
async function versandHalten(page: Page, pattern: string): Promise<Halter> {
	const requests: string[] = [];
	const offen: Route[] = [];
	await page.route(pattern, async (route) => {
		if (route.request().method() !== 'POST') return route.continue();
		requests.push(new URL(route.request().url()).pathname);
		offen.push(route);
	});
	return {
		requests,
		freigeben: async (status = 200, body = '{"status":"ok"}') => {
			for (const r of offen.splice(0)) {
				await r.fulfill({ status, contentType: 'application/json', body });
			}
		}
	};
}

// ---------------------------------------------------------------------------
// Trip
// ---------------------------------------------------------------------------

test.describe('#2124 Trip — geteilter Laufzustand', () => {
	test('AC-3/AC-4: Trip-Liste — Dialog schließen + erneut senden schickt keinen zweiten Request', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await login(page);
		const halter = await versandHalten(page, '**/api/trips/*/send*');

		await page.goto('/trips');
		const menuBtn = page.getByTestId('trip-card-menu-btn').first();
		await menuBtn.click();
		await page.getByTestId('trip-action-sheet').getByText('Test Morgen-Report').click();
		await expect.poll(() => halter.requests.length).toBe(1);

		// Dialog bleibt während des Laufs schließbar (AC-4).
		await page.getByRole('dialog').getByRole('button', { name: 'Schließen' }).click();
		await expect(page.getByRole('dialog')).toHaveCount(0);

		// Derselbe Trip, anderer Auslöser im Sheet: darf KEINEN zweiten Request schicken.
		await menuBtn.click();
		await page.getByTestId('trip-action-sheet').getByText('Test Abend-Report').click();
		await page.waitForTimeout(500); // nur Beobachtungsfenster für einen etwaigen Request
		expect(halter.requests, 'zweiter Versand während des ersten').toHaveLength(1);

		await halter.freigeben();
	});

	test('AC-2: Trip-Detail — 502 zeigt „Ergebnis unklar" statt „fehlgeschlagen"', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await login(page);
		const halter = await versandHalten(page, `**/api/trips/${TRIP_ID}/send*`);
		await page.goto(`/trips/${TRIP_ID}`);
		await expect(page.getByTestId('trip-detail-breadcrumb-bar')).toBeVisible({ timeout: 8000 });

		await page.getByTestId('test-briefing-menu-toggle').click();
		await page.getByTestId('test-briefing-option-evening').click();
		await expect.poll(() => halter.requests.length).toBe(1);
		await halter.freigeben(502, JSON.stringify({ error: 'upstream unreachable' }));

		const err = page.getByTestId('test-briefing-error');
		await expect(err).toBeVisible({ timeout: 8000 });
		await expect(err).toContainText(UNCLEAR);
		await expect(err).not.toContainText(/fehlgeschlagen/i);
	});
});

// ---------------------------------------------------------------------------
// Ortsvergleich — Wegwerf-Preset (nie PO-Daten)
// ---------------------------------------------------------------------------

async function seedPreset(page: Page): Promise<{ presetId: string; locIds: string[] }> {
	const suffix = Date.now();
	const locIds: string[] = [];
	for (const [name, lat, lon] of [
		[`E2E 2124 A ${suffix}`, 47.05, 11.05],
		[`E2E 2124 B ${suffix}`, 46.5, 11.35]
	] as const) {
		const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
		expect(res.ok(), `Location-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
		locIds.push((await res.json()).id as string);
	}
	const presetRes = await page.request.post('/api/compare/presets', {
		data: {
			name: `E2E 2124 ${suffix}`,
			location_ids: locIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			morning_time: '07:00'
		}
	});
	expect(presetRes.ok(), `Preset-Anlage fehlgeschlagen: ${presetRes.status()}`).toBeTruthy();
	return { presetId: (await presetRes.json()).id as string, locIds };
}

async function cleanup(page: Page, presetId: string, locIds: string[]) {
	await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
	for (const id of locIds) await page.request.delete(`/api/locations/${id}`).catch(() => {});
}

test.describe('#2124 Ortsvergleich — geteilter Laufzustand', () => {
	test('AC-3: Kopf „Test senden" + Versand-Tab-Knopf für dasselbe Preset → genau 1 Request', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await login(page);
		const { presetId, locIds } = await seedPreset(page);
		try {
			const halter = await versandHalten(page, `**/api/compare/presets/${presetId}/send*`);
			await page.goto(`/compare/${presetId}?tab=versand`);

			await page.getByRole('button', { name: 'Test senden', exact: true }).click();
			await expect.poll(() => halter.requests.length).toBe(1);

			// Anderer Auslöser (CompareTabs, Versand-Tab) für dasselbe Preset.
			await page.getByTestId('compare-hub-activation-testsend').click();
			await page.waitForTimeout(500); // nur Beobachtungsfenster für einen etwaigen Request
			expect(halter.requests, 'zweiter Versand während des ersten').toHaveLength(1);

			await halter.freigeben();
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});

	test('AC-2: Compare-Detail — 502 zeigt „Ergebnis unklar" statt „Fehler beim Senden"', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await login(page);
		const { presetId, locIds } = await seedPreset(page);
		try {
			const halter = await versandHalten(page, `**/api/compare/presets/${presetId}/send*`);
			await page.goto(`/compare/${presetId}`);

			await page.getByRole('button', { name: 'Test senden', exact: true }).click();
			await expect.poll(() => halter.requests.length).toBe(1);
			await halter.freigeben(502, JSON.stringify({ error: 'upstream unreachable' }));

			await expect(page.getByText(UNCLEAR)).toBeVisible({ timeout: 8000 });
			await expect(page.getByText(/Fehler beim Senden|fehlgeschlagen/)).toHaveCount(0);
		} finally {
			await cleanup(page, presetId, locIds);
		}
	});
});
