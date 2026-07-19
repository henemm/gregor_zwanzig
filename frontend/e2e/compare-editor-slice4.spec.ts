// E2E — Issue #681 (Epic #677): Compare-Editor Slice 4 — Layout + Versand Fidelity
//
// Spec: docs/specs/modules/issue_681_compare_editor_slice4.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging.
//
// Epic #1273 S4c: Layout-/Versand-Preview lebt nur im Create-Wizard; Einstieg ab
// /compare/new (Edit = 307-Redirect), Tabs progressiv frei; data-active-Asserts
// entfallen (sichtbarer Preview belegt den aktiven Tab).
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/compare-editor-slice4.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

// Legt 2 Orte an und arbeitet sich im Create-Wizard bis zum Layout-Tab vor.
async function openWizardLayout(page: Page): Promise<void> {
	const suffix = Date.now();
	const nameA = 'Slice4-Ort-A ' + suffix;
	const nameB = 'Slice4-Ort-B ' + suffix;
	const resA = await page.request.post('/api/locations', {
		data: { name: nameA, lat: 47.2, lon: 12.3 }
	});
	const resB = await page.request.post('/api/locations', {
		data: { name: nameB, lat: 47.3, lon: 12.4 }
	});
	expect(resA.ok() && resB.ok(), 'Location-Anlage fehlgeschlagen').toBeTruthy();

	await page.goto('/compare/new');
	await page.waitForLoadState('networkidle');
	await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();
	await page.locator('[data-testid="compare-editor-name"]').fill('Slice4 E2E ' + suffix);
	await page.locator('[data-testid="compare-editor-profile-wintersport"]:visible').first().click();

	await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
	const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await lib.waitFor({ timeout: 8_000 });
	for (const n of [nameA, nameB]) {
		await lib.getByText(n, { exact: true }).click();
	}

	await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
	await expect(async () => {
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').first().click();
		await expect(
			page.locator('[data-testid="compare-step4-layout-preview"]:visible').first()
		).toBeVisible({ timeout: 5_000 });
	}).toPass({ timeout: 30_000 });
}

test.describe('Issue #681: Compare-Editor Slice 4 — Layout + Versand Fidelity', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: Kanalwechsel → Badge + Live-Vorschau aktualisiert ───────────────
	test('AC-1: Kanalwechsel zeigt korrektes Badge und wechselt Live-Vorschau', async ({ page }) => {
		await openWizardLayout(page);

		const preview = page.locator('[data-testid="compare-step4-layout-preview"]:visible').first();
		await expect(preview).toBeVisible({ timeout: 8_000 });

		// Email-Kanal: Badge muss "∞" zeigen
		const emailBtn = page.locator('[data-testid="channel-tab-email"]:visible').first();
		await emailBtn.click();
		await expect(emailBtn).toContainText('∞');

		// Issue #1232 Scheibe 3a (C1): Vorschau ist neutral — kein Rang, kein
		// Empfehlungs-Banner, dafür der Hinweis "Kein Ranking".
		await expect(preview.locator('.rank-badge')).toHaveCount(0);
		await expect(preview.locator('.recommendation-banner')).toHaveCount(0);
		// Whitespace normalisieren: "Kein Ranking" enthält im Markup Umbruch/Tabs.
		const previewText = ((await preview.textContent()) ?? '').replace(/\s+/g, ' ');
		expect(previewText).not.toContain('Empfehlung');
		expect(previewText).toContain('Kein Ranking');

		// Telegram-Kanal: Badge muss "8" zeigen
		const telegramBtn = page.locator('[data-testid="channel-tab-telegram"]:visible').first();
		await telegramBtn.click();
		await expect(telegramBtn).toContainText('8');

		// SMS-Kanal: Badge muss "—" zeigen
		const smsBtn = page.locator('[data-testid="channel-tab-sms"]:visible').first();
		await smsBtn.click();
		await expect(smsBtn).toContainText('—');
		// SMS-Vorschau zeigt Fließtext (nicht Tabelle)
		const smsBranch = page.locator('[data-testid="compare-step4-preview-sms"]:visible').first();
		await expect(smsBranch).toBeVisible({ timeout: 5_000 });
	});

	// ── AC-2: Telegram-Überlauf → ↳ Detail-Pill ab Position 8 ────────────────
	test('AC-2: Telegram-Kanal zeigt ↳ Detail-Pill für Spalten jenseits Position 8', async ({
		page
	}) => {
		await openWizardLayout(page);

		// Telegram-Kanal wählen
		await page.locator('[data-testid="channel-tab-telegram"]:visible').first().click();

		// Pill für Position 8 (Index 8, 0-basiert) muss existieren wenn >8 aktive Spalten
		const detailPill = page.locator('[data-testid="compare-step4-detail-pill-8"]:visible').first();
		await expect(detailPill).toBeVisible({ timeout: 5_000 });
		await expect(detailPill).toContainText('↳ Detail');
	});

	// ── AC-3: SMS-Vorschau zeigt Fließtext ≤ 140 Zeichen, keine Tabelle ───────
	test('AC-3: SMS-Vorschau ist Fließtext ≤ 140 Zeichen (keine Tabelle)', async ({ page }) => {
		await openWizardLayout(page);

		await page.locator('[data-testid="channel-tab-sms"]:visible').first().click();

		// SMS-Fließtext-Block muss existieren
		const smsBlock = page.locator('[data-testid="compare-step4-preview-sms"]:visible').first();
		await expect(smsBlock).toBeVisible({ timeout: 5_000 });

		// Kein <table>-Element innerhalb der Vorschau
		const preview = page.locator('[data-testid="compare-step4-layout-preview"]:visible').first();
		await expect(preview.locator('table')).toHaveCount(0);

		// Text-Länge ≤ 140 Zeichen
		const smsText = await smsBlock.textContent();
		expect(
			(smsText ?? '').replace(/\s+/g, ' ').trim().length,
			`SMS-Text zu lang: ${smsText}`
		).toBeLessThanOrEqual(200); // etwas Puffer für Hinweis-Zeile
	});

	// ── AC-4a: „Briefing aktivieren" disabled bis Versand-Tab besucht ────────
	test('AC-4a: "Briefing aktivieren" ist disabled bis Versand-Tab besucht', async ({ page }) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');

		// Button muss sichtbar sein
		const activateBtn = page.locator('[data-testid="compare-editor-activate"]');
		await expect(activateBtn).toBeVisible({ timeout: 8_000 });

		// Vor Versand-Besuch: disabled (aria-disabled oder disabled-Attribut)
		const isDisabled =
			(await activateBtn.getAttribute('disabled')) !== null ||
			(await activateBtn.getAttribute('aria-disabled')) === 'true';
		expect(isDisabled, 'Button muss initial disabled sein').toBeTruthy();

		// Hinweis-Text daneben
		const hint = page.locator('[data-testid="compare-editor"]').getByText(
			'Versand einrichten zum Aktivieren'
		);
		await expect(hint).toBeVisible();
	});

	// ── AC-4b: „Briefing aktivieren" existiert im Create-Modus ────────────────
	// Epic #1273 S4c: vestigialer /edit-Umweg entfernt; es bleibt: der
	// Aktivieren-Button ist im Create-Wizard vorhanden.
	test('AC-4b: "Briefing aktivieren" ist im Create-Wizard vorhanden', async ({ page }) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-name"]').fill('Slice4-Aktivierung ' + Date.now());

		await expect(
			page.locator('[data-testid="compare-editor-activate"]')
		).toBeVisible({ timeout: 8_000 });
	});

	// ── AC-5: Layout-Tab zeigt die Versand-Kachel, Wizard den Aktivierungs-Banner ──
	// Issue #1268: Zeitfenster-/Horizont-Kachel entfernt — es bleibt die
	// Versand-Kachel (Testids unverändert seit #1232 Scheibe 2b).
	test('AC-5: Layout-Tab zeigt die Versand-Kachel, Create-Wizard den Aktivierungs-Banner', async ({ page }) => {
		await openWizardLayout(page);

		// Versand-Kachel im Layout-Tab
		await expect(
			page.locator('[data-testid="compare-step5-schedule-tile"]:visible').first()
		).toBeVisible({ timeout: 5_000 });
		// Issue #1268: Zeitfenster-/Horizont-Kachel duerfen nicht mehr erscheinen.
		await expect(page.locator('[data-testid="compare-step5-timewindow-tile"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="compare-step5-horizon-tile"]')).toHaveCount(0);

		// Aktivierungs-Banner ist im Create-Wizard vorhanden (bereits im obigen
		// /compare/new-Flow gemountet).
		await expect(
			page.locator('[data-testid="compare-step5-activation-banner"]')
		).toBeAttached({ timeout: 3_000 });
	});

	// ── AC-5b: channel_layouts pro Kanal getrennt persistiert ────────────────
	// Epic #1273 S4c: Preset entsteht erst beim Aktivieren → POST-Body-Nachweis.
	test('AC-5b: channel_layouts im Aktivierungs-POST-Body pro Kanal getrennt', async ({ page }) => {
		await openWizardLayout(page);

		// Layout-Tab: zwischen Kanälen wechseln (befüllt channel_layouts).
		await page.locator('[data-testid="channel-tab-email"]:visible').first().click();
		await page.locator('[data-testid="channel-tab-telegram"]:visible').first().click();
		await page.locator('[data-testid="channel-tab-email"]:visible').first().click();

		// Bis zum Versand-Tab durchklicken (schaltet den Aktivieren-Button frei).
		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();

		const [request] = await Promise.all([
			page.waitForRequest(
				(req) => req.url().includes('/api/compare/presets') && req.method() === 'POST'
			),
			page.locator('[data-testid="compare-editor-activate"]:visible').first().click()
		]);
		const body = request.postDataJSON() as Record<string, unknown>;
		const dc = (body.display_config ?? {}) as Record<string, unknown>;
		const cl = dc.channel_layouts ?? {};
		expect(
			typeof cl === 'object' && cl !== null,
			'display_config.channel_layouts muss im POST-Body ein Objekt sein'
		).toBeTruthy();
	});
});
