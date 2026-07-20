// E2E (Staging) — Issue #1261 (b) AC-12: Compare-Editor Autospeichern —
// Mandantentrennung. Der neue Auto-Save-Ausloeser darf NIEMALS auf ein
// fremdes Preset schreiben — der PUT trifft ausschließlich
// `/api/compare/presets/{eigene_id}` des angemeldeten Nutzers.
//
// Spec: docs/specs/modules/issue_1261_compare_edit_autosave.md § AC-12
//
// Zwei echte Sessions (zwei Test-User, je eigener Browser-Kontext) — kein
// Mock. Nutzer A loest per echter Geste einen Auto-Save aus; Nutzer B's
// eigenes Preset wird per GET auf Unveraendertheit geprueft.
//
// Ausführen (gegen Staging, aus frontend/):
//   npx playwright test e2e/compare-editor-autosave-user-isolation.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts).
	const loc = await createTestLocation(page.request, { name, lat, lon });
	return loc.id;
}

async function createPresetWithLocation(page: Page, name: string, locationId: string): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [locationId],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return body.id as string;
}

test('AC-12: Autosave-Änderung bei Nutzer A ändert Nutzer Bs eigenes Preset NICHT', async ({
	page: pageA,
	browser
}) => {
	const suffix = Date.now();

	// ── Nutzer A (Default-Session der storageState-Fixture, admin) ──────────
	const locA = await createLocation(pageA, `E2E 1261 AC12 A ${suffix}`, 48.5, 12.5);
	const locA2 = await createLocation(pageA, `E2E 1261 AC12 A2 ${suffix}`, 48.55, 12.55);
	const presetA = await createPresetWithLocation(pageA, `E2E 1261 AC12 Preset-A ${suffix}`, locA);
	// Zweiter Ort NICHT im Preset (nur fuer die spaetere Abwahl-Geste noetig)
	// — API erlaubt nachtraegliches location_ids-Patchen ueber den Editor selbst,
	// daher direkt mit beiden Orten anlegen:
	const presetARes = await pageA.request.put(`/api/compare/presets/${presetA}`, {
		data: {
			name: `E2E 1261 AC12 Preset-A ${suffix}`,
			location_ids: [locA, locA2],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(presetARes.ok(), 'Vorbereitungs-PUT (A, 2 Orte) fehlgeschlagen').toBeTruthy();

	// ── Nutzer B: eigener Browser-Kontext, eigene Registrierung + eigenes Preset ──
	const ctxB = await browser.newContext();
	const pageB = await ctxB.newPage();
	const userB = 'e2e1261b' + suffix;
	const reg = await pageB.request.post('/api/auth/register', {
		// Issue #1226: E-Mail ist Pflichtfeld bei der Registrierung.
		data: { username: userB, password: 'test1234', email: `${userB}@example.com` }
	});
	expect([200, 201].includes(reg.status()), 'Registrierung B fehlgeschlagen: ' + reg.status()).toBeTruthy();
	// RegisterHandler setzt kein Session-Cookie — erst der Login etabliert die
	// zweite echte Nutzer-Session (sonst presetB nicht unter userB isoliert).
	const loginB = await pageB.request.post('/api/auth/login', {
		data: { username: userB, password: 'test1234' }
	});
	expect(loginB.ok(), 'Login B fehlgeschlagen: ' + loginB.status()).toBeTruthy();

	const locB = await createLocation(pageB, `E2E 1261 AC12 B ${suffix}`, 48.6, 12.6);
	const presetB = await createPresetWithLocation(pageB, `E2E 1261 AC12 Preset-B ${suffix}`, locB);
	const beforeB = await (await pageB.request.get(`/api/compare/presets/${presetB}`)).json();

	try {
		// Nutzer A: echte Geste im Editor (Ort abwählen) löst debounced Autosave aus.
		await pageA.setViewportSize({ width: 1280, height: 900 });
		// Epic #1273 S4c: Einstieg am Hub (Editor = 307-Redirect).
		await pageA.goto(`/compare/${presetA}`);
		await expect(pageA.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 10_000 });
		await pageA.getByTestId('compare-detail-tab-orte').click();

		const putA = pageA.waitForResponse(
			(r) => r.url().includes(`/api/compare/presets/${presetA}`) && r.request().method() === 'PUT',
			{ timeout: 10_000 }
		);
		// Hub-Orte-Tab: Ort abwählen.
		await pageA
			.locator(
				`[data-testid="hub-orte-row"][data-loc-id="${locA2}"] [data-testid="hub-orte-remove"]`
			)
			.click();
		const putARes = await putA;
		expect(putARes.ok(), 'Autosave-PUT (A) fehlgeschlagen: ' + putARes.status()).toBeTruthy();
		// KERN: der Autosave-PUT trifft ausschließlich das eigene Preset von A.
		expect(putARes.url()).toContain(`/api/compare/presets/${presetA}`);
		expect(putARes.url()).not.toContain(presetB);

		// Nutzer B's eigenes Preset bleibt vollständig unverändert.
		const afterB = await (await pageB.request.get(`/api/compare/presets/${presetB}`)).json();
		expect(afterB).toEqual(beforeB);

		// Nutzer A hat weiterhin KEINEN Zugriff auf Bs Preset (Mandantentrennung
		// gilt in beide Richtungen — Regressionsschutz analog compare-editor-edit.spec.ts AC-5).
		const crossGet = await pageA.request.get(`/api/compare/presets/${presetB}`);
		expect(crossGet.status()).toBe(404);
	} finally {
		await pageA.request.delete(`/api/compare/presets/${presetA}`).catch(() => {});
		await pageA.request.delete(`/api/locations/${locA}`).catch(() => {});
		await pageA.request.delete(`/api/locations/${locA2}`).catch(() => {});
		await pageB.request.delete(`/api/compare/presets/${presetB}`).catch(() => {});
		await pageB.request.delete(`/api/locations/${locB}`).catch(() => {});
		await ctxB.close();
	}
});
