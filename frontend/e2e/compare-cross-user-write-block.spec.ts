// E2E (Staging) — Epic #1273 S4a: Mandantentrennung — PUT-Cross-User-Block.
//
// Migriert die einzige noch fehlende Assertion aus dem alten AC-5 von
// `compare-editor-edit.spec.ts` (entfällt mit S4a): Nutzer B darf per PUT
// NIEMALS ein fremdes Compare-Preset überschreiben.
//
// Spec: docs/specs/modules/epic_1273_s4a_test_migration.md § AC-1
//
// Rein API-basiert — KEINE UI-Navigation, KEINE Abhängigkeit von `/edit` oder
// der Hub-UI (die alte CompareEditor-Seite rendert seit S3 dort nicht mehr).
// Zwei echte Sessions (zwei Test-User, je eigener Browser-Kontext) — kein
// Mock.
//
// Ausführen (gegen Staging, aus frontend/):
//   npx playwright test e2e/compare-cross-user-write-block.spec.ts --config playwright.config.ts

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

test('Nutzer B kann per PUT NICHT das Preset von Nutzer A überschreiben (404, kein Cross-User-Write)', async ({
	page: pageA,
	browser
}) => {
	const suffix = Date.now();
	let presetA: string | null = null;
	let locA: string | null = null;
	let ctxB: Awaited<ReturnType<typeof browser.newContext>> | null = null;

	try {
		// ── Nutzer A (Default-Session der storageState-Fixture, admin) ──────
		locA = await createLocation(pageA, `E2E 1273-S4a A ${suffix}`, 47.2, 11.4);
		presetA = await createPresetWithLocation(pageA, `E2E 1273-S4a Preset-A ${suffix}`, locA);

		// ── Nutzer B: eigener Browser-Kontext, eigene Registrierung ──────────
		// WICHTIG: browser.newContext() OHNE explizite storageState erbt sonst
		// die Projekt-Default-storageState (playwright.config.ts, admin.json) —
		// B würde sonst mit As bereits authentifiziertem Admin-Cookie starten
		// und der PUT unten liefe fälschlich unter As Identität statt als
		// eigenständiger Cross-User-Versuch. Deshalb explizit leer starten und
		// nach der Registrierung eigens einloggen (register setzt selbst KEIN
		// Session-Cookie).
		ctxB = await browser.newContext({ storageState: undefined });
		const pageB = await ctxB.newPage();
		const userB = 'e2e1273s4a' + suffix;
		// E-Mail ist seit Issue #1226 Pflichtfeld bei der Registrierung.
		const reg = await pageB.request.post('/api/auth/register', {
			data: { username: userB, password: 'test1234', email: `${userB}@example.com` }
		});
		expect([200, 201].includes(reg.status()), 'Registrierung B fehlgeschlagen: ' + reg.status()).toBeTruthy();

		const loginB = await pageB.request.post('/api/auth/login', {
			data: { username: userB, password: 'test1234' }
		});
		expect(loginB.ok(), 'Login B fehlgeschlagen: ' + loginB.status()).toBeTruthy();

		// B versucht As Preset per PUT zu überschreiben → 404, kein Cross-User-Write.
		const putB = await pageB.request.put(`/api/compare/presets/${presetA}`, {
			data: {
				name: 'Hijack',
				location_ids: [],
				schedule: 'daily',
				profil: 'wandern',
				hour_from: 7,
				hour_to: 16,
				empfaenger: []
			}
		});
		expect(putB.status()).toBe(404);

		// As Preset bleibt bei nachfolgendem GET (aus As eigenem Kontext) unverändert.
		const afterRes = await pageA.request.get(`/api/compare/presets/${presetA}`);
		expect(afterRes.ok()).toBeTruthy();
		const after = await afterRes.json();
		expect(after.name).toBe(`E2E 1273-S4a Preset-A ${suffix}`);
	} finally {
		if (presetA) await pageA.request.delete(`/api/compare/presets/${presetA}`).catch(() => {});
		if (locA) await pageA.request.delete(`/api/locations/${locA}`).catch(() => {});
		if (ctxB) await ctxB.close();
	}
});
