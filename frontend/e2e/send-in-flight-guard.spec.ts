// E2E, Issue #2124 AC-2/AC-3/AC-4: Versand-Auslöser teilen EINEN
// Laufzustand (`$lib/utils/sendOutcome.ts`) und zeigen bei 502 „Ergebnis unklar".
//
// Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md (§4, AC-2..AC-4)
//
// WARUM IM BROWSER: Der node-Test `src/lib/utils/sendOutcome.test.ts` bewacht das
// Modul. Ob die .svelte-Auslöser es WIRKLICH nutzen, zeigt nur der echte Klick
// (Dateiinhalt-Grep ist als Nachweis untersagt, die SSR-Harness sieht keine
// Klick-Handler). Läuft seit dem Fix-Loop F001 in der CI-Ampel (`e2e`-Job,
// Positivliste `.github/ci_e2e_specs.txt`). Alle fünf Auslöser kommen vor:
//   Trip-Liste, Trip-Detail, Compare-Liste, Compare-Hub (Kopf), Compare-Tabs.
//
// Nicht vakuum: Jeder Auslöser sperrt sich heute schon SELBST (`disabled` während
// des eigenen Laufs). Deshalb wird der zweite Versuch über einen ANDEREN Auslöser
// für denselben Trip/Vergleich gemacht — umgeht ein Auslöser den Helfer (direkter
// `fetch`), geht entweder ein zweiter Request ab oder der Laufzustand wird nie
// gesetzt; beides macht den zugehörigen Test rot.
//
// Der Versand wird per `page.route` abgefangen und erst auf ein Signal des Tests
// beantwortet (Promise, kein sleep). Es geht nichts an Python oder Empfänger.
//
// Kein Beobachtungsfenster mit fester Wartezeit (Filter A der Positivliste): der zweite
// Versuch wartet auf die sichtbare Antwort „Versand läuft bereits" des ZWEITEN
// Auslösers und prüft erst DANACH, dass nur ein Request abging.
//
// Seitenwechsel NUR per Klick (clientseitige Navigation), nie `page.goto`: der
// Laufzustand lebt im JS-Modul, ein Neuladen würde ihn (und den gehaltenen
// Request) verwerfen.
//
// Ausführen (aus frontend/, lokaler E2E-Stack):
//   npx playwright test e2e/send-in-flight-guard.spec.ts

import { test, expect, type Page, type Route } from '@playwright/test';
import { login, registriereBestaetigtenZweitnutzer } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const DESKTOP = { width: 1440, height: 900 };
const LAEUFT = 'Versand läuft bereits';
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

/** Karte des Seed-Trips in der mobilen Trip-Liste (andere Specs legen weitere Trips an). */
function tripKarte(page: Page) {
	return page.getByTestId('trip-card').filter({ hasText: 'E2E Cockpit Test Trip' }).first();
}

// ---------------------------------------------------------------------------
// Trip
// ---------------------------------------------------------------------------

test.describe('#2124 Trip — geteilter Laufzustand', () => {
	test('AC-3/AC-4: Trip-Liste — Dialog schließen + erneut senden schickt keinen zweiten Request', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await login(page);
		const halter = await versandHalten(page, '**/api/trips/*/send*');
		try {
			await page.goto('/trips');
			const menuBtn = tripKarte(page).getByTestId('trip-card-menu-btn');
			await menuBtn.click();
			await page.getByTestId('trip-action-sheet').getByText('Test Morgen-Report').click();
			await expect.poll(() => halter.requests.length).toBe(1);

			// Dialog bleibt während des Laufs schließbar (AC-4).
			await page.getByRole('dialog').getByRole('button', { name: 'Schließen' }).click();
			await expect(page.getByRole('dialog')).toHaveCount(0);

			// Derselbe Trip, anderer Eintrag im Sheet: darf KEINEN zweiten Request schicken.
			await menuBtn.click();
			await page.getByTestId('trip-action-sheet').getByText('Test Abend-Report').click();
			await expect(page.getByRole('dialog').getByText(LAEUFT)).toBeVisible({ timeout: 8000 });
			expect(halter.requests, 'zweiter Versand während des ersten').toHaveLength(1);
		} finally {
			await halter.freigeben();
		}
	});

	test('AC-3: Trip-Liste hält den Versand, Trip-Detail (per Klick erreicht) schickt keinen zweiten Request', async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		await login(page);
		const halter = await versandHalten(page, `**/api/trips/${TRIP_ID}/send*`);
		try {
			await page.goto('/trips');
			await tripKarte(page).getByTestId('trip-card-menu-btn').click();
			await page.getByTestId('trip-action-sheet').getByText('Test Morgen-Report').click();
			await expect.poll(() => halter.requests.length).toBe(1);
			await page.getByRole('dialog').getByRole('button', { name: 'Schließen' }).click();
			await expect(page.getByRole('dialog')).toHaveCount(0);

			// Clientseitig ins Trip-Detail (Modulzustand bleibt), dort anderer Auslöser.
			await tripKarte(page).getByTestId('trip-card-content-btn').click();
			await page.waitForURL(`**/trips/${TRIP_ID}*`);
			await page.setViewportSize(DESKTOP);
			await expect(page.getByTestId('trip-detail-breadcrumb-bar')).toBeVisible({ timeout: 8000 });
			await page.getByTestId('test-briefing-menu-toggle').click();
			await page.getByTestId('test-briefing-option-evening').click();

			await expect(page.getByTestId('test-briefing-error')).toContainText(LAEUFT, { timeout: 8000 });
			expect(halter.requests, 'zweiter Versand während des ersten').toHaveLength(1);
		} finally {
			await halter.freigeben();
		}
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
		const halter = await versandHalten(page, `**/api/compare/presets/${presetId}/send*`);
		try {
			await page.goto(`/compare/${presetId}?tab=versand`);

			await page.getByRole('button', { name: 'Test senden', exact: true }).click();
			await expect.poll(() => halter.requests.length).toBe(1);

			// Anderer Auslöser (CompareTabs, Versand-Tab) für dasselbe Preset.
			await page.getByTestId('compare-hub-activation-testsend').click();
			await expect(page.getByText(LAEUFT).first()).toBeVisible({ timeout: 8000 });
			expect(halter.requests, 'zweiter Versand während des ersten').toHaveLength(1);
		} finally {
			await halter.freigeben();
			await cleanup(page, presetId, locIds);
		}
	});

	// Der Bestätigungsdialog der Compare-Liste sperrt „Senden" ohne bestätigte Konto-
	// Adresse (`sendTargetLabel`). Der Seed-Admin des CI-Stacks hat keine ⇒ eigener,
	// sofort bestätigter Zweitnutzer (Muster: konto-loeschdialog-mobil-ueberlauf.spec.ts).
	test('AC-3: Compare-Liste hält den Versand, Hub-Kopf (per Klick erreicht) schickt keinen zweiten Request', async ({ page, browser }) => {
		const username = `e2e2124liste${Date.now()}`;
		const kennwort = 'Test1234!x';
		const ctx = await browser.newContext({ storageState: undefined, viewport: DESKTOP, serviceWorkers: 'block' });
		const gast = await ctx.newPage();
		let angelegt = false;
		let preset: { presetId: string; locIds: string[] } | null = null;
		let halter: Halter | null = null;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, username, kennwort);
			angelegt = true;
			preset = await seedPreset(gast);
			const { presetId } = preset;
			halter = await versandHalten(gast, `**/api/compare/presets/${presetId}/send*`);

			await gast.goto('/compare');
			const zeile = gast.getByTestId(`compare-tile-${presetId}`);
			await zeile.getByRole('button', { name: 'Briefing senden' }).click();
			await gast.getByRole('dialog', { name: 'Briefing jetzt senden?' }).getByRole('button', { name: 'Senden', exact: true }).click();
			await expect.poll(() => halter!.requests.length).toBe(1);

			// Clientseitig in den Hub (Modulzustand bleibt), dort anderer Auslöser.
			await zeile.getByText(/E2E 2124/).first().click();
			await gast.waitForURL(`**/compare/${presetId}*`);
			await gast.getByRole('button', { name: 'Test senden', exact: true }).click();

			await expect(gast.getByText(LAEUFT).first()).toBeVisible({ timeout: 8000 });
			expect(halter.requests, 'zweiter Versand während des ersten').toHaveLength(1);
		} finally {
			await halter?.freigeben();
			if (preset) await cleanup(gast, preset.presetId, preset.locIds);
			if (angelegt) {
				await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			}
			await ctx.close();
		}
	});

	test('AC-2: Compare-Detail — 502 zeigt „Ergebnis unklar" statt „Fehler beim Senden"', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await login(page);
		const { presetId, locIds } = await seedPreset(page);
		const halter = await versandHalten(page, `**/api/compare/presets/${presetId}/send*`);
		try {
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
