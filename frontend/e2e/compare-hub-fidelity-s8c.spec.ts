// E2E (Staging) — Issue #1256 Scheibe S8c: Hub-Fidelity (R2 Layout-Tab-Rahmen
// + R3 SummaryCards-Copy/Orte-Tab-Rahmen/Breadcrumb/profileLabel/
// Mobile-Eyebrow/Mobile-Summary-Stack).
//
// Spec: docs/specs/modules/feat_1256_s8c_hub_fidelity.md (AC-1..AC-13)
//
// Ausführen (gegen Staging, aus frontend/, NACH Push+Staging-Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s8c.staging.config.ts
//
// Muster: compare-mobile-vervollstaendigung.spec.ts (S8) — echte Klickpfade
// statt goto() wo ein Klick gefordert ist, eindeutige Testdaten-Namen mit
// Date.now()-Suffix, afterEach-Cleanup. storageState-Login-Muster (kein
// per-Test-Login — s. reference_staging_e2e_storagestate_login_rate_limit,
// 429-Rate-Limit).

import { test, expect, type Page } from '@playwright/test';

let createdIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

// Preset mit einem Ort, Profil "wandern" (AC-6-Beleg "Wandern") und Kanal
// Email (Empfänger mit "@", AC-4-Beleg "Email" statt hartem Key).
async function createPresetWithLocation(page: Page, name: string, locationId: string): Promise<string> {
	return createPresetWithLocations(page, name, [locationId]);
}

// Fix-Loop 1 (F003, AC-3): Preset mit mehreren Orten (für den "+N weitere"-Beleg).
async function createPresetWithLocations(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com']
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

// Fix-Loop 1 (F003, AC-5/AC-8): Draft-Preset ohne Ort — deriveStatusFromPreset()
// liefert 'draft', sobald location_ids leer ist (subscriptionHelpers.ts:66).
async function createDraftPreset(page: Page, name: string): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: []
		}
	});
	expect(res.ok(), 'Draft-Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

test.describe('Issue #1256 S8c (AC-1): Layout-Tab Desktop-Rahmen', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('Section-Header, Kappungs-Hint und 3 Limit-Pillen sind sichtbar', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-D ${suffix}`, 47.1, 11.1);
		const id = await createPresetWithLocation(page, `E2E S8c Layout-D ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-layout"]').click();

		const panel = page.locator('[data-testid="compare-detail-panel-layout"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('Übersicht pro Kanal')).toBeVisible();
		await expect(
			panel.getByText('Metrik-Zeilen · Orte sind die Spalten — der Renderer kappt je Kanal')
		).toBeVisible();
		await expect(panel.getByText('Email · alle Spalten')).toBeVisible();
		await expect(panel.getByText('Telegram · max 8')).toBeVisible();
		await expect(panel.getByText('SMS · flach · 0')).toBeVisible();
	});
});

test.describe('Issue #1256 S8c (AC-2): Layout-Tab Mobil-Rahmen', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('mobiler Header, Kurz-Hint und kompakte Pillen (SMS ohne "· 0") sind sichtbar', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-M ${suffix}`, 47.15, 11.15);
		const id = await createPresetWithLocation(page, `E2E S8c Layout-M ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		const layoutTab = page.locator('[data-testid="compare-detail-tab-layout"]');
		await layoutTab.scrollIntoViewIfNeeded();
		await layoutTab.click();

		const panel = page.locator('[data-testid="compare-detail-panel-layout"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('Spalten pro Kanal')).toBeVisible();
		await expect(panel.getByText('Renderer kappt je Kanal')).toBeVisible();
		await expect(panel.getByText('SMS · flach', { exact: true })).toBeVisible();
	});
});

test.describe('Issue #1256 S8c (AC-4/AC-6): SummaryCard-Texte auf der Übersicht (Desktop)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('Layout-Karte zeigt Kanal-Label statt hartem Key, Wertebereiche-Karte zeigt "Wandern"', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-Sum ${suffix}`, 47.2, 11.2);
		const id = await createPresetWithLocation(page, `E2E S8c Summary ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('Email').first()).toBeVisible();
		await expect(panel.getByText('Wandern')).toBeVisible();
		await expect(panel.getByText('Reihenfolge nach Priorität.')).toBeVisible();
	});
});

test.describe('Issue #1256 S8c (AC-7): mobiler Chevron-Summary-Stack', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('4 Chevron-Zeilen statt 2×2-Grid; Klick auf "Orte" wechselt sichtbar den Tab', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-Chev ${suffix}`, 47.3, 11.3);
		const id = await createPresetWithLocation(page, `E2E S8c Chevron ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const stack = page.locator('[data-testid="compare-detail-summary-mobile"]');
		await expect(stack).toBeVisible({ timeout: 10_000 });
		const rows = stack.locator('[data-testid="hub-summary-row-mobile"]');
		await expect(rows).toHaveCount(4);
		await expect(rows.nth(0)).toContainText('Orte');
		await expect(rows.nth(1)).toContainText('Wertebereiche');
		await expect(rows.nth(2)).toContainText('Layout');
		await expect(rows.nth(3)).toContainText('Versand');

		await rows.nth(0).click();
		await expect(page.locator('[data-testid="compare-detail-panel-orte"]')).toBeVisible({ timeout: 10_000 });
		await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]')).toHaveCount(0);
	});
});

test.describe('Issue #1256 S8c (AC-10): Breadcrumb genau 2 Krümel', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('Breadcrumb zeigt "ORTS-VERGLEICHE / Hub" ohne App-weiten Extra-Krümel', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-BC ${suffix}`, 47.4, 11.4);
		const id = await createPresetWithLocation(page, `E2E S8c Breadcrumb ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const crumb = page.locator('a.breadcrumb-link:visible');
		await expect(crumb).toHaveCount(1);
		await expect(crumb).toHaveText('ORTS-VERGLEICHE');
		await expect(page.getByText('WORKSPACE', { exact: true })).toHaveCount(0);
	});
});

test.describe('Issue #1256 S8c (AC-12): mobile Eyebrow im Header', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('Eyebrow "Orts-Vergleich · Hub" ist über dem Preset-Namen sichtbar', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-Eye ${suffix}`, 47.5, 11.5);
		const id = await createPresetWithLocation(page, `E2E S8c Eyebrow ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		await expect(page.getByText('Orts-Vergleich · Hub')).toBeVisible({ timeout: 10_000 });
	});
});

// Fix-Loop 1 (F003 HIGH): 5 zuvor fehlende AC-Nachweise ergänzt.

test.describe('Issue #1256 S8c (AC-3): Orte-SummaryCard "+N weitere" bei >3 Orten', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('4 Orte → Orte-Karte zeigt "+1 weitere"', async ({ page }) => {
		const suffix = Date.now();
		const locIds = await Promise.all([
			createLocation(page, `E2E S8c Ort-4a ${suffix}`, 47.61, 11.61),
			createLocation(page, `E2E S8c Ort-4b ${suffix}`, 47.62, 11.62),
			createLocation(page, `E2E S8c Ort-4c ${suffix}`, 47.63, 11.63),
			createLocation(page, `E2E S8c Ort-4d ${suffix}`, 47.64, 11.64)
		]);
		const id = await createPresetWithLocations(page, `E2E S8c VierOrte ${suffix}`, locIds);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('+1 weitere')).toBeVisible();
	});
});

test.describe('Issue #1256 S8c (AC-5): Versand-SummaryCard Draft-Sonderfall', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('frisch angelegtes Draft-Preset zeigt "Noch nicht geplant" + Festlegen-Copy', async ({ page }) => {
		const suffix = Date.now();
		const id = await createDraftPreset(page, `E2E S8c Draft-Versand ${suffix}`);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('Noch nicht geplant')).toBeVisible();
		await expect(panel.getByText('Briefing-Uhrzeiten im Tab Versand festlegen.')).toBeVisible();
	});

	test('aktiviertes Preset zeigt weiterhin die Zeiten-Copy statt des Draft-Texts', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-Aktiv ${suffix}`, 47.7, 11.7);
		const id = await createPresetWithLocation(page, `E2E S8c Aktiv-Versand ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('Noch nicht geplant')).toHaveCount(0);
		await expect(panel.getByText('nächster Versand')).toBeVisible();
	});
});

test.describe('Issue #1256 S8c (AC-8): mobile Status-Kurzform', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('Draft-Preset zeigt Status-Stat exakt "Entwurf"', async ({ page }) => {
		const suffix = Date.now();
		const id = await createDraftPreset(page, `E2E S8c Draft-Status ${suffix}`);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const monitoring = page.locator('[data-testid="compare-detail-monitoring-mobile"]');
		await expect(monitoring).toBeVisible({ timeout: 10_000 });
		await expect(monitoring.getByText('Entwurf', { exact: true })).toBeVisible();
	});

	test('aktives Preset zeigt Status-Stat exakt "Läuft autom."', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-Status ${suffix}`, 47.8, 11.8);
		const id = await createPresetWithLocation(page, `E2E S8c Aktiv-Status ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const monitoring = page.locator('[data-testid="compare-detail-monitoring-mobile"]');
		await expect(monitoring).toBeVisible({ timeout: 10_000 });
		await expect(monitoring.getByText('Läuft autom.', { exact: true })).toBeVisible();
	});
});

test.describe('Issue #1256 S8c (AC-9, Copy-Teil): Orte-Tab Desktop-Rahmen', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('Header "Verglichene Orte" + Desktop-Sortier-Hint sind sichtbar', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-Orte ${suffix}`, 47.9, 11.9);
		const id = await createPresetWithLocation(page, `E2E S8c Orte-Tab ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-orte"]').click();

		const panel = page.locator('[data-testid="compare-detail-panel-orte"]');
		await expect(panel).toBeVisible({ timeout: 10_000 });
		await expect(panel.getByText('Verglichene Orte')).toBeVisible();
		await expect(panel.getByText('Reihenfolge = Spalten im Briefing · ziehen zum Sortieren')).toBeVisible();
	});
});

test.describe('Issue #1256 S8c (AC-11): Desktop-Unterzeile Profil-Label', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('Unterzeile zeigt "Wandern" statt "wandern"', async ({ page }) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8c Ort-Sub ${suffix}`, 46.9, 10.9);
		const id = await createPresetWithLocation(page, `E2E S8c Unterzeile ${suffix}`, locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		// Desktop-Header ist ein eigener CSS-Container ("hidden desktop:block") —
		// scoped statt page-weit, weil der Mobile-Header dieselbe profileLabel-
		// Ableitung im (per CSS verborgenen) DOM ebenfalls rendert.
		const desktopHeader = page.locator('.hidden.desktop\\:block');
		await expect(desktopHeader).toContainText('Wandern');
	});
});
