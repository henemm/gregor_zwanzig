// E2E (Staging) — Issue #1256 Scheibe 8: Mobile-Vervollständigung Orts-
// Vergleich (AC-21 Liste dense+Chevron, AC-22 geteilter Hub mit 4-Stat-2×2-
// Monitoring statt Bespoke-Block, AC-23 Lifecycle-Bottom-Sheet, AC-24 Editor
// Lock-Toast + floating CTA).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 8
//
// Ausführen (gegen Staging, aus frontend/, NACH Push+Staging-Deploy):
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.1256-s8.staging.config.ts
//
// Muster: compare-flow-navigation.spec.ts (S2) — echte Klickpfade statt
// goto() wo ein Klick gefordert ist, :visible-Disambiguierung wo Desktop-
// und Mobile-DOM gleichzeitig existieren (Seiten-Chrome-Ebene), eindeutige
// Testdaten-Namen mit Date.now()-Suffix (S2-Lehre: 409-Kollision bei
// Koordinaten-Defaultnamen), Staging-Hygiene via afterEach-Cleanup.

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

async function createPreset(page: Page, name: string): Promise<string> {
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
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdIds.push(id);
	return id;
}

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
	expect(res.ok(), 'Location-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	const id = body.id as string;
	createdLocationIds.push(id);
	return id;
}

async function createPresetWithLocation(
	page: Page,
	name: string,
	schedule: 'daily' | 'manual',
	locationId: string
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: [locationId],
			schedule,
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

test.describe('Issue #1256 Scheibe 8 (AC-21): mobile Liste — Chevron statt Kebab', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('AC-21: dense-Kachel zeigt Chevron, keinen Kebab, und navigiert per Tipp auf das Detail', async ({
		page
	}) => {
		const name = `E2E S8 Chevron ${Date.now()}`;
		const id = await createPreset(page, name);

		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		const tile = page.locator(`[data-testid="compare-tile-${id}"]:visible`);
		await expect(tile).toBeVisible({ timeout: 10_000 });

		// AC-21: Chevron (CompareTile.svelte dense-Zweig, lucide chevron-right)
		// ist die einzige Trailing-Affordance — kein Kebab mehr in der Kachel.
		await expect(tile.locator('svg.lucide-chevron-right')).toBeVisible({ timeout: 5_000 });
		await expect(tile.locator('button[aria-label="Weitere Aktionen"]')).toHaveCount(0);

		await tile.click();
		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });
	});

	test('AC-21: kein Kebab-Trigger sichtbar irgendwo im mobilen Kachel-Stack (Desktop-Grid bleibt CSS-verborgen)', async ({
		page
	}) => {
		const name = `E2E S8 Chevron-Liste ${Date.now()}`;
		await createPreset(page, name);

		await page.goto('/compare');
		await page.waitForLoadState('networkidle');

		// Der Desktop-Kachel-Grid (CompareGrid) rendert weiterhin einen Kebab pro
		// Kachel, ist aber unter 900px per `hidden desktop:block` aus dem
		// sichtbaren Baum genommen — :visible filtert ihn korrekt heraus.
		await expect(page.locator('button[aria-label="Weitere Aktionen"]:visible')).toHaveCount(0);
	});
});

test.describe('Issue #1256 Scheibe 8 (AC-22): mobiler Hub — geteilte CompareTabs statt Bespoke-Block', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('AC-22: Übersicht-Tab zeigt genau 4 Stat-Karten im 2×2-Grid, kein "Briefings"-Stat', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8 Ort ${suffix}`, 47.12, 11.22);
		const name = `E2E S8 Monitoring ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'daily', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		const monitoring = page.locator('[data-testid="compare-detail-monitoring-mobile"]:visible');
		await expect(monitoring).toBeVisible({ timeout: 10_000 });

		// Genau 4 Stat-Karten (Status / Nächster Versand / Zuletzt raus / Kanäle) —
		// keine 5. Karte ("Briefings", bleibt Desktop-exklusiv).
		await expect(monitoring.locator('[data-slot="card"]')).toHaveCount(4);
		await expect(monitoring).toContainText('Status');
		await expect(monitoring).toContainText('Nächster Versand');
		await expect(monitoring).toContainText('Zuletzt raus');
		await expect(monitoring).toContainText('Kanäle');
		await expect(monitoring).not.toContainText('Briefings');

		// Die Desktop-exklusive Briefings-Stat existiert im mobilen DOM-Baum gar
		// nicht (Svelte {#if isMobileViewport}, kein CSS-Hide zweier Bäume).
		await expect(page.locator('[data-testid="compare-detail-stat-briefings"]')).toHaveCount(0);
	});

	test('AC-22: Tab-Leiste ist per echtem Klick bedienbar (Orte-Tab wechselt den Inhalt)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8 Ort-Tabwechsel ${suffix}`, 47.08, 11.18);
		const name = `E2E S8 Tabwechsel ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'daily', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]')).toBeVisible({
			timeout: 10_000
		});

		const orteTab = page.locator('[data-testid="compare-detail-tab-orte"]');
		await expect(orteTab).toBeVisible({ timeout: 10_000 });
		await orteTab.click();

		await expect(page.locator('[data-testid="compare-detail-panel-orte"]')).toBeVisible({
			timeout: 10_000
		});
		// Übersicht-Panel (inkl. Mobile-Monitoring-Grid) ist nach dem Tab-Wechsel
		// nicht mehr im DOM (ein Tab-Inhalt ist jeweils gemountet, kein CSS-Hide).
		await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]')).toHaveCount(0);
	});

	// Fix-Loop 1 (Fresh-Eyes-Fund, blockierend): die Tab-Leiste war mobil NICHT
	// scrollbar — "Versand"/"Vorschau" waren auf 390px unerreichbar
	// (Inline-Edit-Paritäts-Verletzung). Wächter-Test (S5-Lehre: neue Mechanik
	// braucht sofort einen eigenen Wächter): erreicht den letzten Tab
	// ("Vorschau") per Wisch-Äquivalent (scrollIntoViewIfNeeded) + echtem Klick.
	test('AC-22 Fix-Loop 1: letzter Tab ("Vorschau") ist per Wisch + Klick erreichbar (Tab-Leiste scrollbar)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8 Ort-Scroll ${suffix}`, 47.02, 11.28);
		const name = `E2E S8 Tab-Scroll ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'daily', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]')).toBeVisible({
			timeout: 10_000
		});

		const vorschauTab = page.locator('[data-testid="compare-detail-tab-vorschau"]');
		// Vor dem Scrollen liegt der letzte Tab außerhalb des sichtbaren
		// 390px-Ausschnitts der Tab-Leiste — scrollIntoViewIfNeeded() ist das
		// Playwright-Äquivalent zum Nutzer-Wisch (horizontales Scrollen).
		await vorschauTab.scrollIntoViewIfNeeded();
		await expect(vorschauTab).toBeInViewport({ timeout: 5_000 });
		await vorschauTab.click();

		await expect(page.locator('[data-testid="compare-detail-panel-vorschau"]')).toBeVisible({
			timeout: 10_000
		});
	});
});

test.describe('Issue #1256 Scheibe 8 (AC-23): mobiles Bottom-Sheet — Lifecycle-Aktionsliste', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('AC-23: ⋯-Button öffnet Bottom-Sheet mit genau Aktivieren/Archivieren/Löschen (pausierter Vergleich)', async ({
		page
	}) => {
		const suffix = Date.now();
		const locId = await createLocation(page, `E2E S8 Ort-Sheet ${suffix}`, 46.95, 11.05);
		const name = `E2E S8 Sheet-Paused ${suffix}`;
		const id = await createPresetWithLocation(page, name, 'manual', locId);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');

		// Mobile TopBar-⋯-Button teilt sich das aria-label mit dem Desktop-
		// Header-Kebab (S7-Ist-Befund) — auf mobilem Viewport ist nur der
		// TopBar-Button :visible (Desktop-Header per CSS verborgen).
		const moreBtn = page.locator('button[aria-label="Weitere Aktionen"]:visible');
		await expect(moreBtn).toBeVisible({ timeout: 10_000 });
		await moreBtn.click();

		const sheet = page.locator('[data-snap="half"]:visible');
		await expect(sheet).toBeVisible({ timeout: 5_000 });

		// Lifecycle-Vertrag (compareLifecycleActions, paused → Aktivieren):
		// genau 3 Aktionen, deckungsgleich mit dem Desktop-Hub-Kebab (S3).
		await expect(sheet.getByText('Aktivieren', { exact: true })).toBeVisible({ timeout: 5_000 });
		await expect(sheet.getByText('Archivieren', { exact: true })).toBeVisible({ timeout: 5_000 });
		await expect(sheet.getByText('Löschen', { exact: true })).toBeVisible({ timeout: 5_000 });

		// Listen-/Editor-exklusive Aktionen dürfen im mobilen Sheet NICHT mehr
		// auftauchen (AC-23 — Umstellung von compareActions() weg).
		await expect(sheet.getByText('Briefing jetzt senden', { exact: true })).toHaveCount(0);
		await expect(sheet.getByText('Vorschau öffnen', { exact: true })).toHaveCount(0);
		await expect(sheet.getByText('Bearbeiten', { exact: true })).toHaveCount(0);

		// Nur öffnen/lesen/schließen — keine Aktion tatsächlich auslösen.
		await page.locator('button[aria-label="Schliessen"]:visible').click();
		await expect(sheet).not.toBeVisible({ timeout: 5_000 });
	});
});

test.describe('Issue #1256 Scheibe 8 (AC-24): mobiler Editor — Lock-Toast + floating CTA', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
	});

	test('AC-24: Tipp auf gesperrten Tab (Create-Modus, Name leer) zeigt Lock-Toast, floating CTA bleibt sichtbar', async ({
		page
	}) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');

		// Floating-CTA existiert nur im Create-Modus (CompareEditor.svelte,
		// `{#if !isEdit}` um data-testid="cm-mobile-cta") — vor jeder Interaktion
		// bereits sichtbar.
		const cta = page.locator('[data-testid="cm-mobile-cta"]:visible');
		await expect(cta).toBeVisible({ timeout: 10_000 });

		// Frischer Create-Flow: Name-Feld leer → "Orte"-Tab ist gesperrt
		// (unlockedTabs() lässt 'orte' erst nach nicht-leerem Namen zu).
		const orteTab = page.locator('[data-testid="cm-mobile-tab-orte"]:visible');
		await expect(orteTab).toBeVisible({ timeout: 10_000 });
		await expect(orteTab).toHaveAttribute('data-locked', 'true');
		await orteTab.click();

		const toast = page.locator('[role="status"]:visible');
		await expect(toast).toBeVisible({ timeout: 5_000 });
		await expect(toast).toContainText('erst Vergleich benennen');

		// Kein Tab-Wechsel ausgelöst (weiterhin auf dem Start-Tab "Vergleich"),
		// die floating CTA bleibt fixiert sichtbar.
		await expect(page.locator('[data-testid="cm-mobile-tab-vergleich"]:visible')).toHaveAttribute(
			'data-active',
			'true'
		);
		await expect(cta).toBeVisible({ timeout: 5_000 });
	});
});
