// E2E (Staging, nur /e2e-verify) — Onboarding S3, Issue #2521:
// „Mit Standardwerten speichern" + Hilfeseite /hilfe.
// Spec: docs/specs/modules/onboarding_standardwerte_hilfe.md
//
//   AC-6   Trip: Standardwerte-Knopf == unveraendertes Durchklicken aller Reiter
//          (zwei Trips anlegen, beide per GET lesen, ohne id/Name/Zeitstempel vergleichen)
//   AC-7   Ortsvergleich: dasselbe gegen den Bestandsweg ueber alle Reiter
//   AC-9   nach dem Standardwerte-Speichern wegnavigieren => genau EIN neuer Trip
//   AC-11  Detailseite + Standardwerte; zweiter Nutzer sieht den Eintrag nicht
//   AC-12  mobil 375 px: Knopf in der unteren Leiste (Ortsvergleich: auf jedem Reiter vor Versand)
//   AC-15  /hilfe: vier Abschnitte in der Reihenfolge Briefing, Alarme, Kanaele, Befehle
//   AC-18  Hilfelink aus der Startklar-Checkliste (frischer Nutzer)
//   AC-20  ohne Sitzung => /login, kein Hilfeinhalt
//
// Test-Kennungen (Vertrag aus den Kern-Tests):
//   trip-new-standardwerte-btn · tn-mobile-standardwerte ·
//   compare-editor-standardwerte · cm-mobile-standardwerte ·
//   hilfe-briefing · hilfe-alarme · hilfe-kanaele · hilfe-befehle
//
// Testdaten tragen das Praefix E2E-GZ- und werden in afterEach geraeumt.
//
//   cd frontend && npx playwright test e2e/standardwerte-und-hilfe.spec.ts --config playwright.config.ts

import { test, expect, type Locator, type Page, type APIRequestContext } from '@playwright/test';
import {
	anlegenPflicht,
	cleanupTracked,
	createTestLocation,
	login,
	registerForCleanup,
	registriereBestaetigtenZweitnutzer
} from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const MOBILE = { width: 375, height: 812 };
// Issue #1743: kein Anlege-Schritt Versand mehr (Abschnitt im Schritt Wetter-Metriken).
const TRIP_KETTE = [/Wetter/, /Wertebereiche/, /Alarme/];
const VERGLEICH_KETTE = ['wetter-metriken', 'wertebereiche', 'alarme'] as const;

test.beforeEach(async ({ page }) => {
	await login(page);
});
test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

// ── Vergleichsform: ohne Kennungen, Namen und Zeitstempel ───────────────────
function normalisiert(wert: unknown, tiefe = 0): unknown {
	if (Array.isArray(wert)) return wert.map((w) => normalisiert(w, tiefe + 1));
	if (wert && typeof wert === 'object') {
		const aus: Record<string, unknown> = {};
		for (const [k, v] of Object.entries(wert as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))) {
			if (k === 'id' || k.endsWith('_at') || k === 'etag' || k === 'version') continue;
			if (tiefe === 0 && k === 'name') continue;
			aus[k] = normalisiert(v, tiefe + 1);
		}
		return aus;
	}
	return wert;
}

// ── Trip ────────────────────────────────────────────────────────────────────
function tripTab(page: Page, mobil: boolean, name: RegExp): Locator {
	const leiste = mobil ? page.getByTestId('tn-mobile-tabbar') : page.locator('.tn-desktop');
	return leiste.getByRole('tab', { name });
}

/** /trips/new: Name, Startdatum, je Etappe eine GPX (Pflichtangaben) — seit #2347 S4 aus helpers.ts. */
async function tripPflicht(page: Page, mobil: boolean, name: string, datum: string): Promise<void> {
	await anlegenPflicht(page, 'route', { name, datum, mobil, viewport: mobil ? MOBILE : DESKTOP });
}

async function postId(page: Page, pfad: string, aktion: () => Promise<void>): Promise<string> {
	const antwort = page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === pfad, {
		timeout: 30_000
	});
	await aktion();
	const r = await antwort;
	expect(r.ok(), `POST ${pfad} -> ${r.status()}`).toBeTruthy();
	return ((await r.json()) as { id: string }).id;
}

async function tripMitStandardwerten(page: Page, name: string, datum: string): Promise<string> {
	await tripPflicht(page, false, name, datum);
	const knopf = page.getByTestId('trip-new-standardwerte-btn');
	await expect(knopf).toBeEnabled({ timeout: 15_000 });
	const id = await postId(page, '/api/trips', () => knopf.click());
	registerForCleanup('trip', id);
	return id;
}

async function tripDurchgeklickt(page: Page, name: string, datum: string): Promise<string> {
	await tripPflicht(page, false, name, datum);
	for (const reiter of TRIP_KETTE) await tripTab(page, false, reiter).click();
	const knopf = page.getByTestId('trip-new-save-btn');
	await expect(knopf).toBeEnabled({ timeout: 15_000 });
	const id = await postId(page, '/api/trips', () => knopf.click());
	registerForCleanup('trip', id);
	return id;
}

async function lies(request: APIRequestContext, pfad: string): Promise<Record<string, unknown>> {
	const r = await request.get(pfad);
	expect(r.ok(), `GET ${pfad} -> ${r.status()}`).toBeTruthy();
	return (await r.json()) as Record<string, unknown>;
}

test.describe('Teil A: Trip /trips/new', () => {
	test('AC-6: Standardwerte-Trip == durchgeklickter Trip (GET, ohne id/Name/Zeitstempel)', async ({ page }) => {
		const s = Date.now();
		const datum = new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10);
		const a = await tripMitStandardwerten(page, `E2E-GZ-Std-A ${s}`, datum);
		const b = await tripDurchgeklickt(page, `E2E-GZ-Std-B ${s}`, datum);
		const ta = await lies(page.request, `/api/trips/${a}`);
		const tb = await lies(page.request, `/api/trips/${b}`);
		expect(normalisiert(ta)).toEqual(normalisiert(tb));
		const rc = ta.report_config as Record<string, unknown>;
		expect(rc.multi_day_trend_reports, 'kein Mehrtages-Trend im Abend-Briefing').toEqual([]);
	});

	test('AC-9 + AC-11: Detailseite mit Standardwerten, genau EIN Trip nach Wegnavigieren, Nutzer B sieht ihn nicht', async ({ page, browser }) => {
		const s = Date.now();
		const name = `E2E-GZ-Std-Einmal ${s}`;
		const id = await tripMitStandardwerten(page, name, new Date(Date.now() + 7 * 86_400_000).toISOString().slice(0, 10));
		await expect(page).toHaveURL(new RegExp(`/trips/${id}`), { timeout: 15_000 });
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');
		const liste = (await (await page.request.get('/api/trips')).json()) as Array<{ id: string; name: string }>;
		expect(liste.filter((t) => t.name === name)).toHaveLength(1);

		const trip = await lies(page.request, `/api/trips/${id}`);
		const rc = trip.report_config as Record<string, unknown>;
		expect(rc.send_email).toBe(true);
		expect(((trip.display_config as Record<string, unknown>).metrics as unknown[]).length).toBeGreaterThan(0);
		expect(trip.alert_channels ?? (trip.display_config as Record<string, unknown>).alert_channels).toBeTruthy();

		const ctxB = await browser.newContext({ storageState: { cookies: [], origins: [] } });
		try {
			const userB = 'e2estdb' + s;
			await registriereBestaetigtenZweitnutzer(page.request, ctxB.request, userB, 'E2e-Passwort-' + s);
			const fremd = await ctxB.request.get(`/api/trips/${id}`);
			expect(fremd.ok(), 'Nutzer B darf den Trip von A nicht lesen').toBeFalsy();
			const listeB = (await (await ctxB.request.get('/api/trips')).json()) as Array<{ id: string }>;
			expect(listeB.some((t) => t.id === id)).toBeFalsy();
		} finally {
			await ctxB.close();
		}
	});

	test('AC-12: mobil 375 px — Standardwerte-Knopf in der unteren Leiste', async ({ page }) => {
		await tripPflicht(page, true, `E2E-GZ-Std-Mobil ${Date.now()}`, new Date().toISOString().slice(0, 10));
		const knopf = page.locator('[data-testid="tn-mobile-footer"] [data-testid="tn-mobile-standardwerte"]');
		await expect(knopf).toBeVisible();
		await expect(knopf).toBeEnabled({ timeout: 15_000 });
	});
});

// ── Ortsvergleich ───────────────────────────────────────────────────────────
function vergleichTab(page: Page, mobil: boolean, reiter: string): Locator {
	return page.locator(`[data-testid="${mobil ? 'cm-mobile-tab-' : 'compare-editor-tab-'}${reiter}"]:visible`);
}

type Ort = { name: string };
async function testOrte(page: Page): Promise<[Ort, Ort]> {
	const s = Date.now();
	const ortA = await createTestLocation(page.request, { name: `E2E-GZ-Std A ${s}`, lat: 47.1, lon: 11.2 });
	const ortB = await createTestLocation(page.request, { name: `E2E-GZ-Std B ${s}`, lat: 47.2, lon: 11.3 });
	return [ortA, ortB];
}

async function vergleichPflicht(page: Page, name: string, orte?: [Ort, Ort]): Promise<void> {
	const [ortA, ortB] = orte ?? (await testOrte(page));
	await page.setViewportSize(DESKTOP);
	await page.goto('/compare/new');
	await expect(page.getByTestId('compare-editor')).toBeVisible({ timeout: 15_000 });
	await page.getByTestId('compare-editor-name').fill(name);
	await vergleichTab(page, false, 'orte').click();
	const bibliothek = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await expect(bibliothek).toBeVisible({ timeout: 10_000 });
	for (const ort of [ortA, ortB]) await bibliothek.getByText(ort.name, { exact: true }).click();
}

async function vergleichMitStandardwerten(page: Page, name: string, orte?: [Ort, Ort]): Promise<string> {
	await vergleichPflicht(page, name, orte);
	const knopf = page.getByTestId('compare-editor-standardwerte');
	await expect(knopf).toBeEnabled({ timeout: 15_000 });
	const id = await postId(page, '/api/compare/presets', () => knopf.click());
	registerForCleanup('preset', id);
	return id;
}

async function vergleichDurchgeklickt(page: Page, name: string, orte?: [Ort, Ort]): Promise<string> {
	await vergleichPflicht(page, name, orte);
	for (const reiter of VERGLEICH_KETTE) await vergleichTab(page, false, reiter).click();
	const knopf = page.getByTestId('compare-editor-activate');
	await expect(knopf).toBeEnabled({ timeout: 15_000 });
	const id = await postId(page, '/api/compare/presets', () => knopf.click());
	registerForCleanup('preset', id);
	return id;
}

test.describe('Teil A: Ortsvergleich /compare/new', () => {
	test('AC-7: Standardwerte-Vergleich == Bestandsweg ueber alle Reiter (Wertebereiche vorbelegt, nicht leer)', async ({ page }) => {
		const s = Date.now();
		const orte = await testOrte(page);
		const a = await vergleichMitStandardwerten(page, `E2E-GZ-Std-Vgl-A ${s}`, orte);
		const b = await vergleichDurchgeklickt(page, `E2E-GZ-Std-Vgl-B ${s}`, orte);
		const pa = await lies(page.request, `/api/compare/presets/${a}`);
		const pb = await lies(page.request, `/api/compare/presets/${b}`);
		// Beide Vergleiche nutzen dieselben zwei Orte — verglichen wird das volle Objekt.
		expect(normalisiert(pa)).toEqual(normalisiert(pb));
		expect((pa.corridors as unknown[] | undefined)?.length ?? 0, 'Wertebereiche leer').toBeGreaterThan(0);
	});

	test('AC-11: Detailseite des Ortsvergleichs; Nutzer B sieht ihn nicht', async ({ page, browser }) => {
		const s = Date.now();
		const id = await vergleichMitStandardwerten(page, `E2E-GZ-Std-Vgl-Detail ${s}`);
		await expect(page).toHaveURL(new RegExp(`/compare/${id}`), { timeout: 15_000 });
		const ctxB = await browser.newContext({ storageState: { cookies: [], origins: [] } });
		try {
			const userB = 'e2estdvb' + s;
			await registriereBestaetigtenZweitnutzer(page.request, ctxB.request, userB, 'E2e-Passwort-' + s);
			expect((await ctxB.request.get(`/api/compare/presets/${id}`)).ok()).toBeFalsy();
			const listeB = (await (await ctxB.request.get('/api/compare/presets')).json()) as Array<{ id: string }>;
			expect(listeB.some((p) => p.id === id)).toBeFalsy();
		} finally {
			await ctxB.close();
		}
	});

	test('AC-12: mobil 375 px — Knopf auf jedem Reiter vor Versand in der unteren Leiste', async ({ page }) => {
		await vergleichPflicht(page, `E2E-GZ-Std-Vgl-Mobil ${Date.now()}`);
		await page.setViewportSize(MOBILE);
		for (const reiter of ['orte', 'wetter-metriken', 'wertebereiche', 'alarme']) {
			await vergleichTab(page, true, reiter).click({ force: true });
			await expect(page.locator('[data-testid="cm-mobile-cta"] [data-testid="cm-mobile-standardwerte"]:visible'), reiter).toBeVisible();
		}
	});
});

// ── Teil B: Hilfeseite ──────────────────────────────────────────────────────
test.describe('Teil B: /hilfe', () => {
	test('AC-15: Seite laedt, vier Abschnitte in der Reihenfolge Briefing, Alarme, Kanaele, Antwort-Befehle', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/hilfe');
		const ys: number[] = [];
		for (const id of ['hilfe-briefing', 'hilfe-alarme', 'hilfe-kanaele', 'hilfe-befehle']) {
			const el = page.getByTestId(id);
			await expect(el).toBeVisible();
			ys.push((await el.boundingBox())!.y);
		}
		expect([...ys].sort((a, b) => a - b)).toEqual(ys);
		await expect(page.getByTestId('hilfe-kanaele')).toContainText('Premium-SMS');
	});

	test('AC-18: Hilfelink aus der Startklar-Checkliste (frischer Nutzer) fuehrt auf /hilfe', async ({ page, browser }) => {
		const s = Date.now();
		const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
		try {
			await registriereBestaetigtenZweitnutzer(page.request, ctx.request, 'e2ehilfe' + s, 'E2e-Passwort-' + s);
			const neu = await ctx.newPage();
			await neu.goto('/');
			const checkliste = neu.getByTestId('startklar-checkliste');
			await expect(checkliste).toBeVisible({ timeout: 15_000 });
			await checkliste.locator('a[href="/hilfe"]').click();
			await expect(neu).toHaveURL(/\/hilfe$/);
			await expect(neu.getByTestId('hilfe-briefing')).toBeVisible();
		} finally {
			await ctx.close();
		}
	});

	test('AC-20: ohne Sitzung => Anmeldung, kein Hilfeinhalt', async ({ browser }) => {
		const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
		try {
			const p = await ctx.newPage();
			await p.goto('/hilfe');
			await expect(p).toHaveURL(/\/login/);
			await expect(p.getByTestId('hilfe-briefing')).toHaveCount(0);
		} finally {
			await ctx.close();
		}
	});
});
