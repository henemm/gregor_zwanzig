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

async function createPreset(
	page: Page,
	locationIds: string[]
): Promise<{ id: string }> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'LayoutTab E2E ' + Date.now(),
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wintersport',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['layouttab-test@example.com']
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id };
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
		const locA = await createLocation(page, 'LT-Ort-A ' + Date.now());
		const locB = await createLocation(page, 'LT-Ort-B ' + Date.now());
		const { id } = await createPreset(page, [locA, locB]);

		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-layout"]').click();

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]');
		await expect(preview).toBeVisible({ timeout: 8_000 });

		// Email: Badge ∞, Tabelle sichtbar
		const emailBtn = page.locator('[data-testid="channel-tab-email"]');
		await emailBtn.click();
		await expect(emailBtn).toContainText('∞');
		await expect(preview.locator('table')).toBeVisible();

		// Telegram: Badge 8, weiterhin Tabelle
		const telegramBtn = page.locator('[data-testid="channel-tab-telegram"]');
		await telegramBtn.click();
		await expect(telegramBtn).toContainText('8');
		await expect(preview.locator('table')).toBeVisible();

		// SMS: Badge —, Fließtext statt Tabelle
		const smsBtn = page.locator('[data-testid="channel-tab-sms"]');
		await smsBtn.click();
		await expect(smsBtn).toContainText('—');
		await expect(preview.locator('table')).toHaveCount(0);
		await expect(page.locator('[data-testid="compare-step4-preview-sms"]')).toBeVisible({
			timeout: 5_000
		});
	});

	// ── AC-1: >8 gewählte Orte → Telegram-Overflow-Chip "−n" ──────────────────
	test('AC-1: >8 gewählte Orte zeigen Overflow-Chip am Telegram-Button', async ({ page }) => {
		const ids: string[] = [];
		for (let i = 0; i < 9; i++) {
			ids.push(await createLocation(page, `LT-Overflow-${i}-` + Date.now()));
		}
		const { id } = await createPreset(page, ids);

		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-layout"]').click();
		await expect(page.locator('[data-testid="compare-step4-layout-preview"]')).toBeVisible({
			timeout: 8_000
		});

		// 9 Orte + 1 Label-Spalte = 10 > Telegram-Budget 8 → Overflow-Chip "−2"
		const telegramBtn = page.locator('[data-testid="channel-tab-telegram"]');
		await expect(telegramBtn).toContainText('−2');
	});

	// ── AC-4: 0 gewählte Orte → Empty-State statt Crash/leerer Tabelle ────────
	test('AC-4: 0 gewählte Orte zeigen Empty-State "Keine Orte ausgewählt"', async ({ page }) => {
		const { id } = await createPreset(page, []);

		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-layout"]').click();

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]');
		await expect(preview).toBeVisible({ timeout: 8_000 });
		await expect(preview).toContainText('Keine Orte ausgewählt');
		await expect(preview.locator('table')).toHaveCount(0);
	});

	// ── AC-3: Vorschau ist neutral — kein Rang, kein Score, kein Empfehlungs-
	//         Banner, dafür der Hinweis "Kein Ranking" und Ortsname im th-Header ─
	test('AC-3: Vorschau neutral — kein Rang-Badge, kein Empfehlungs-Banner, "Kein Ranking" + Ortsname im th', async ({
		page
	}) => {
		const locA = await createLocation(page, 'LT-Neutral-A ' + Date.now());
		const locB = await createLocation(page, 'LT-Neutral-B ' + Date.now());
		const { id } = await createPreset(page, [locA, locB]);

		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-layout"]').click();

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]');
		await expect(preview).toBeVisible({ timeout: 8_000 });
		await page.locator('[data-testid="channel-tab-email"]').click();

		await expect(preview.locator('.rank-badge')).toHaveCount(0);
		await expect(preview.locator('.recommendation-banner')).toHaveCount(0);
		const text = (await preview.textContent()) ?? '';
		expect(text).not.toContain('Empfehlung');
		expect(text).toContain('Kein Ranking');

		const headers = await preview.locator('thead th, th').allTextContents();
		expect(headers.some((h) => /Hintertux|Ischgl|Zermatt/i.test(h))).toBeTruthy();
	});

	// ── AC-8: Desktop UND Mobile — Doppel-Mount konsistent, kein horiz. Scroll ─
	test('AC-8: Mobile-Ansicht stapelt einspaltig ohne horizontales Scrollen', async ({ page }) => {
		const locA = await createLocation(page, 'LT-Mobile-A ' + Date.now());
		const { id } = await createPreset(page, [locA]);

		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').first().click();

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]:visible').first();
		await expect(preview).toBeVisible({ timeout: 8_000 });

		const overflowsX = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 4);
		expect(overflowsX, 'Seite scrollt horizontal auf Mobile-Viewport').toBeFalsy();
	});
});
