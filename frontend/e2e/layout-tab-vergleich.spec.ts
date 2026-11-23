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
// #3276 (Spec feat_3276_vergleich_altfelder_entfernen.md AC-3/AC-6): auch die
// Stundenverlauf-Steuerung (compare-layout-hourly-*, CompareHourlyLayoutControls)
// ist entfernt; AC-7 sichert jetzt ihr Fehlen zu, Bereitschafts-Marker ist der
// aktive Schritt Zustellung.
//
// Ausführen:
//   cd frontend && npx playwright test e2e/layout-tab-vergleich.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';

async function createLocation(page: Page, name: string): Promise<string> {
	// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts) —
	// diese Datei hatte zuvor GAR kein Cleanup (garantierter Leak, Kontext-Dok.).
	const loc = await createTestLocation(page.request, {
		name,
		lat: 47.0 + Math.random(),
		lon: 12.0 + Math.random()
	});
	return loc.id;
}

// Neue Freischalt-Kette (F2a): Name → ≥2 Orte → Wetter-Metriken → Wertebereiche →
// Layout. Der Layout-Tab zeigt nur noch die Stundenverlauf-Steuerung.
async function openLayoutTab(page: Page, orteNamen: string[]): Promise<void> {
	await page.goto('/compare/new');
	await page.waitForLoadState('networkidle');
	await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();

	await page.locator('[data-testid="compare-editor-name"]').fill('LayoutTab E2E ' + Date.now());
	// #3198 (S4b-3): keine Aktivitaetsprofil-Kachel mehr; der Fall braucht keine bestimmte Vorlage.

	await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
	const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await lib.waitFor({ timeout: 8_000 });
	for (const n of orteNamen) {
		await lib.getByText(n, { exact: true }).click();
	}

	// Wetter-Metriken besuchen → Wertebereiche frei; Wertebereiche besuchen →
	// Layout frei; dann Layout öffnen.
	// #2794 S3a: Wetter besuchen → Zustellung frei; der Stundenverlauf steht im Schritt Zustellung.
	await page.locator('[data-testid="compare-editor-tab-wetter"]:visible').first().click();
	const layoutTab = page.locator('[data-testid="compare-editor-tab-zustellung"]:visible').first();
	await expect(async () => {
		await layoutTab.click();
		await expect(layoutTab).toHaveAttribute('data-active', 'true', { timeout: 5_000 });
	}).toPass({ timeout: 30_000 });
}

test.describe('F2a: Layout-Tab (/compare/new), seit #3276 ohne Stundenverlauf-Steuerung', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-7 (#3276): keine Stundenverlauf-Steuerung mehr im Vergleich ─────────
	test('AC-7 (#3276): Schritt Zustellung zeigt weder Stundenverlauf-Schalter noch Metrik-Auswahl', async ({ page }) => {
		const nameA = 'E2E-GZ-LT-Ort-A-' + Date.now();
		const nameB = 'E2E-GZ-LT-Ort-B-' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);
		await openLayoutTab(page, [nameA, nameB]);

		await expect(page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="compare-layout-hourly-metrics"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="weather-metrics-stundenverlauf"]')).toHaveCount(0);
	});

	// ── AC-11: Die alte channel_layouts-Attrappe ist verschwunden ──────────────
	test('AC-11: kein Channel-Tab / kein Layout-Preview / kein SMS-Budget mehr', async ({ page }) => {
		const nameA = 'E2E-GZ-LT-NoAttrappe-A-' + Date.now();
		const nameB = 'E2E-GZ-LT-NoAttrappe-B-' + Date.now();
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

		const layoutTab = page.locator('[data-testid="compare-editor-tab-zustellung"]:visible').first();
		await expect(layoutTab).toHaveAttribute('data-locked', 'true', { timeout: 8_000 });
		// #2880: gesperrte Reiter tragen aria-disabled="true" — Playwright klickt sie nur mit force
		// (der Nutzer kann sie weiterhin antippen; der Klick wechselt nicht).
		await layoutTab.click({ force: true });
		await expect(layoutTab).not.toHaveAttribute('data-active', 'true');
	});

	// ── AC-8: Mobile — Layout-Tab ohne horizontales Scrollen ───────────────────
	test('AC-8: Mobile-Ansicht scrollt nicht horizontal', async ({ page }) => {
		const nameA = 'E2E-GZ-LT-Mobile-A-' + Date.now();
		const nameB = 'E2E-GZ-LT-Mobile-B-' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);

		await openLayoutTab(page, [nameA, nameB]);
		await page.setViewportSize({ width: 390, height: 844 });

		await expect(
			page.locator('[data-testid="compare-editor-tab-zustellung"]').first()
		).toHaveAttribute('data-active', 'true', { timeout: 8_000 });
		const overflowsX = await page.evaluate(
			() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4
		);
		expect(overflowsX, 'Seite scrollt horizontal auf Mobile-Viewport').toBeFalsy();
	});
});
