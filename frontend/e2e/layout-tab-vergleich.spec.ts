// E2E — Epic #1301 Scheibe F2a: Layout-Tab der Anlege-Seite /compare/new.
//
// Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md § AC-7, AC-11
//
// Umgeschrieben von der alten channel_layouts-Attrappe (channel-tab-*/
// compare-step4-layout-preview/SMS-Budget/Top-N) auf den NEUEN Layout-Tab-Inhalt:
// ausschließlich die Stundenverlauf-Steuerung (compare-layout-hourly-*), geliefert
// von der geteilten Komponente CompareHourlyLayoutControls. Begründung der
// Löschung der Attrappen-Blöcke: `display_config.channel_layouts` (Top-N-Ranking,
// SMS-Budget-DnD, Channel-Tabs) wurde vom Compare-Renderpfad NIE gelesen
// (#1301-Grundbefund) — die neue Seite bildet diese Funktion bewusst nicht nach.
//
// Ausführen:
//   cd frontend && npx playwright test e2e/layout-tab-vergleich.spec.ts

import { test, expect, type Page } from '@playwright/test';

async function createLocation(page: Page, name: string): Promise<string> {
	const res = await page.request.post('/api/locations', {
		data: { name, lat: 47.0 + Math.random(), lon: 12.0 + Math.random() }
	});
	expect(res.ok(), `Location-Anlage fehlgeschlagen: ${name}`).toBeTruthy();
	const body = await res.json();
	return body.id as string;
}

// Neue Freischalt-Kette (F2a): Name → ≥2 Orte → Wetter-Metriken → Wertebereiche →
// Layout. Der Layout-Tab zeigt nur noch die Stundenverlauf-Steuerung.
async function openLayoutTab(page: Page, orteNamen: string[]): Promise<void> {
	await page.goto('/compare/new');
	await page.waitForLoadState('networkidle');
	await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();

	await page.locator('[data-testid="compare-editor-name"]').fill('LayoutTab E2E ' + Date.now());
	await page.locator('[data-testid="compare-editor-profile-wintersport"]:visible').first().click();

	await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
	const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await lib.waitFor({ timeout: 8_000 });
	for (const n of orteNamen) {
		await lib.getByText(n, { exact: true }).click();
	}

	// Wetter-Metriken besuchen → Wertebereiche frei; Wertebereiche besuchen →
	// Layout frei; dann Layout öffnen.
	await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').first().click();
	await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
	const layoutTab = page.locator('[data-testid="compare-editor-tab-layout"]:visible').first();
	await expect(async () => {
		await layoutTab.click();
		await expect(
			page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible').first()
		).toBeVisible({ timeout: 5_000 });
	}).toPass({ timeout: 30_000 });
}

test.describe('F2a: Layout-Tab (/compare/new) = Stundenverlauf-Steuerung', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-7: Layout-Tab zeigt Stundenverlauf-Toggle + Metrik-Auswahl ──────────
	test('AC-7: Layout-Tab rendert Stundenverlauf-Toggle und Metrik-Checkboxen', async ({ page }) => {
		const nameA = 'LT-Ort-A ' + Date.now();
		const nameB = 'LT-Ort-B ' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);
		await openLayoutTab(page, [nameA, nameB]);

		await expect(
			page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible').first()
		).toBeVisible();
		await expect(
			page.locator('[data-testid="compare-layout-hourly-metrics"]:visible').first()
		).toBeVisible();
		// Mindestens eine Metrik-Checkbox aus dem Katalog (z.B. Temperatur).
		await expect(
			page.locator('[data-testid="compare-layout-hourly-metric-temp_c"]:visible').first()
		).toBeVisible();
	});

	// ── AC-7: Eine Metrik umschalten bleibt bedienbar (kein Crash) ─────────────
	test('AC-7: Metrik-Checkbox lässt sich umschalten', async ({ page }) => {
		const nameA = 'LT-Toggle-A ' + Date.now();
		const nameB = 'LT-Toggle-B ' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);
		await openLayoutTab(page, [nameA, nameB]);

		const metric = page
			.locator('[data-testid="compare-layout-hourly-metric-wind_kmh"]:visible input')
			.first();
		await expect(metric).toBeVisible({ timeout: 8_000 });
		await metric.click();
		// Klick darf den Editor nicht wegwerfen — der Layout-Tab bleibt aktiv.
		await expect(
			page.locator('[data-testid="compare-editor-tab-layout"]:visible').first()
		).toHaveAttribute('data-active', 'true');
	});

	// ── AC-11: Die alte channel_layouts-Attrappe ist verschwunden ──────────────
	test('AC-11: kein Channel-Tab / kein Layout-Preview / kein SMS-Budget mehr', async ({ page }) => {
		const nameA = 'LT-NoAttrappe-A ' + Date.now();
		const nameB = 'LT-NoAttrappe-B ' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);
		await openLayoutTab(page, [nameA, nameB]);

		await expect(page.locator('[data-testid="channel-tab-email"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="channel-tab-sms"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="compare-step4-layout-preview"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="sms-budget-display"]')).toHaveCount(0);
	});

	// ── AC-4: Ohne ≥2 Orte bleibt der Layout-Tab gesperrt (nicht erreichbar) ────
	test('AC-4: ohne Orte bleibt der Layout-Tab gesperrt', async ({ page }) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();
		await page.locator('[data-testid="compare-editor-name"]').fill('LayoutTab Empty ' + Date.now());

		const layoutTab = page.locator('[data-testid="compare-editor-tab-layout"]:visible').first();
		await expect(layoutTab).toHaveAttribute('data-locked', 'true', { timeout: 8_000 });
		await layoutTab.click();
		await expect(
			page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible')
		).toHaveCount(0);
	});

	// ── AC-8: Mobile — Layout-Tab ohne horizontales Scrollen ───────────────────
	test('AC-8: Mobile-Ansicht scrollt nicht horizontal', async ({ page }) => {
		const nameA = 'LT-Mobile-A ' + Date.now();
		const nameB = 'LT-Mobile-B ' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);

		await openLayoutTab(page, [nameA, nameB]);
		await page.setViewportSize({ width: 390, height: 844 });

		await expect(
			page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible').first()
		).toBeVisible({ timeout: 8_000 });
		const overflowsX = await page.evaluate(
			() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4
		);
		expect(overflowsX, 'Seite scrollt horizontal auf Mobile-Viewport').toBeFalsy();
	});
});
