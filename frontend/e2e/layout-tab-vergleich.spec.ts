// E2E — Issue #1232 Scheibe 3a: geteilter LayoutTab-Organism (context="vergleich")
//
// Spec: docs/specs/modules/layout_tab_vergleich.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen echten
// Compare-Preset (kein Mock). Deckt AC-1..AC-4 + AC-8 ab. AC-5/AC-6/AC-7
// bleiben in compare-editor-slice4.spec.ts (Bestandssuite, angepasst).
//
// Ausführen:
//   cd frontend && npx playwright test e2e/layout-tab-vergleich.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

async function createLocation(page: Page, name: string): Promise<string> {
	const res = await page.request.post('/api/locations', {
		data: { name, lat: 47.0 + Math.random(), lon: 12.0 + Math.random() }
	});
	expect(res.ok(), `Location-Anlage fehlgeschlagen: ${name}`).toBeTruthy();
	const body = await res.json();
	return body.id as string;
}

// Epic #1273 S4c: Der Layout-Preview lebt nur im Create-Wizard (view-only Hub);
// Einstieg ab /compare/new, Layout-Tab erst ab ≥2 Orten frei.
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

	// Wertebereiche besuchen schaltet Layout frei, dann Layout öffnen.
	await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
	const layoutTab = page.locator('[data-testid="compare-editor-tab-layout"]:visible').first();
	await expect(async () => {
		await layoutTab.click();
		await expect(
			page.locator('[data-testid="compare-step4-layout-preview"]:visible').first()
		).toBeVisible({ timeout: 5_000 });
	}).toPass({ timeout: 30_000 });
}

test.describe('Issue #1232 Scheibe 3a: LayoutTab (context="vergleich")', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1/AC-2: Kanal-Wechsel Email→Telegram→SMS — Badge + Template-Wechsel ──
	test('AC-1/AC-2: Kanal-Wechsel zeigt Badges ∞/8/— und wechselt Vorschau-Template', async ({
		page
	}) => {
		const nameA = 'LT-Ort-A ' + Date.now();
		const nameB = 'LT-Ort-B ' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);
		await openLayoutTab(page, [nameA, nameB]);

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]:visible').first();
		await expect(preview).toBeVisible({ timeout: 8_000 });

		// Email: Badge ∞, Tabelle sichtbar
		const emailBtn = page.locator('[data-testid="channel-tab-email"]:visible').first();
		await emailBtn.click();
		await expect(emailBtn).toContainText('∞');
		await expect(preview.locator('table')).toBeVisible();

		// Telegram: Badge 8, weiterhin Tabelle
		const telegramBtn = page.locator('[data-testid="channel-tab-telegram"]:visible').first();
		await telegramBtn.click();
		await expect(telegramBtn).toContainText('8');
		await expect(preview.locator('table')).toBeVisible();

		// SMS: Badge —, Fließtext statt Tabelle
		const smsBtn = page.locator('[data-testid="channel-tab-sms"]:visible').first();
		await smsBtn.click();
		await expect(smsBtn).toContainText('—');
		await expect(preview.locator('table')).toHaveCount(0);
		await expect(
			page.locator('[data-testid="compare-step4-preview-sms"]:visible').first()
		).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-1: >8 gewählte Orte → Telegram-Overflow-Chip "−n" ──────────────────
	test('AC-1: >8 gewählte Orte zeigen Overflow-Chip am Telegram-Button', async ({ page }) => {
		const namen: string[] = [];
		for (let i = 0; i < 9; i++) {
			const n = `LT-Overflow-${i}-` + Date.now();
			await createLocation(page, n);
			namen.push(n);
		}
		await openLayoutTab(page, namen);
		await expect(
			page.locator('[data-testid="compare-step4-layout-preview"]:visible').first()
		).toBeVisible({ timeout: 8_000 });

		// 9 Orte + 1 Label-Spalte = 10 > Telegram-Budget 8 → Overflow-Chip "−2"
		const telegramBtn = page.locator('[data-testid="channel-tab-telegram"]:visible').first();
		await expect(telegramBtn).toContainText('−2');
	});

	// ── AC-4: Ohne gewählte Orte bleibt der Layout-Tab im Wizard gesperrt ─────
	// Epic #1273 S4c: Der frühere 0-Orte-Empty-State war nur im (abgeschafften)
	// Edit-Modus erreichbar. Der Create-Wizard schaltet den Layout-Tab erst ab
	// ≥2 Orten frei — der Test prüft daher jetzt genau diese Sperre (data-locked).
	test('AC-4: ohne Orte bleibt der Layout-Tab gesperrt (nicht erreichbar)', async ({ page }) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();
		await page.locator('[data-testid="compare-editor-name"]').fill('LayoutTab Empty ' + Date.now());

		const layoutTab = page.locator('[data-testid="compare-editor-tab-layout"]:visible').first();
		await expect(layoutTab).toHaveAttribute('data-locked', 'true', { timeout: 8_000 });
		// Ein Klick öffnet den gesperrten Tab nicht — der Layout-Preview bleibt aus.
		await layoutTab.click();
		await expect(
			page.locator('[data-testid="compare-step4-layout-preview"]:visible')
		).toHaveCount(0);
	});

	// ── AC-3: Vorschau ist neutral — kein Rang, kein Score, kein Empfehlungs-
	//         Banner, dafür der Hinweis "Kein Ranking" und Ortsname im th-Header ─
	test('AC-3: Vorschau neutral — kein Rang-Badge, kein Empfehlungs-Banner, "Kein Ranking" + Ortsname im th', async ({
		page
	}) => {
		const nameA = 'LT-Neutral-A ' + Date.now();
		const nameB = 'LT-Neutral-B ' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);
		await openLayoutTab(page, [nameA, nameB]);

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]:visible').first();
		await expect(preview).toBeVisible({ timeout: 8_000 });
		await page.locator('[data-testid="channel-tab-email"]:visible').first().click();

		await expect(preview.locator('.rank-badge')).toHaveCount(0);
		await expect(preview.locator('.recommendation-banner')).toHaveCount(0);
		// Whitespace normalisieren: "Kein Ranking" enthält im Markup Umbruch/Tabs.
		const text = ((await preview.textContent()) ?? '').replace(/\s+/g, ' ');
		expect(text).not.toContain('Empfehlung');
		expect(text).toContain('Kein Ranking');

		// Der Preview nutzt Demo-Orte (DUMMY_LOCATIONS in LTComparePreview.svelte) als
		// Spaltenköpfe — nicht die real gewählten Orte (Planungstool zeigt kein Live-Wetter).
		const headers = await preview.locator('thead th, th').allTextContents();
		expect(headers.some((h) => /Hintertux|Ischgl|Zermatt/i.test(h))).toBeTruthy();
	});

	// ── AC-8: Mobile — einspaltig ohne horizontales Scrollen ─────────────────
	// Epic #1273 S4c: Layout-Tab erst ab ≥2 Orten erreichbar → 2 Orte (statt 1).
	test('AC-8: Mobile-Ansicht stapelt einspaltig ohne horizontales Scrollen', async ({ page }) => {
		const nameA = 'LT-Mobile-A ' + Date.now();
		const nameB = 'LT-Mobile-B ' + Date.now();
		await createLocation(page, nameA);
		await createLocation(page, nameB);

		// Create-Klickpfad am Desktop (robuster), DANN auf Mobile umschalten und
		// den Layout-Preview auf horizontales Scrollen prüfen.
		await openLayoutTab(page, [nameA, nameB]);
		await page.setViewportSize({ width: 390, height: 844 });

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]:visible').first();
		await expect(preview).toBeVisible({ timeout: 8_000 });

		const overflowsX = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4);
		expect(overflowsX, 'Seite scrollt horizontal auf Mobile-Viewport').toBeFalsy();
	});
});
