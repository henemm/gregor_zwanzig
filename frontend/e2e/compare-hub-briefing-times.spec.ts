// E2E — Issue #1229 (Phase 2 von Epic #1230): Compare-Hub Briefing-Zeiten +
// Neutralisierung.
//
// Spec: docs/specs/modules/issue_1229_monitor_hub.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging/Preview.
// Echter Klick-Pfad (Tab-Klick statt page.goto in den Tab-Zustand), Doppel-
// Mount Desktop+Mobile beachtet (`:visible`-Filter, etabliertes Muster, siehe
// versand-tab-vergleich.spec.ts).
//
// Läuft NUR gegen Staging (via /e2e-verify) — im Slice-1-GREEN-Schritt nur
// Syntax-/Listen-Prüfung (`npx playwright test --list`), KEIN Lauf.
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/compare-hub-briefing-times.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string }> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'CompareHub-Briefing-E2E ' + Date.now(),
			location_ids: ['e2e-loc-innsbruck'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['compare-hub-briefing-e2e@example.com'],
			morning_enabled: true,
			morning_time: '07:00:00',
			evening_enabled: true,
			evening_time: '18:00:00',
			display_config: {},
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id };
}

async function deletePreset(page: Page, id: string): Promise<void> {
	await page.request.delete(`/api/compare/presets/${id}`);
}

test.describe('Issue #1229: Compare-Hub Briefing-Zeiten + Neutralisierung', () => {
	// login() ist mit vorhandenem storageState (Staging-Setup-Projekt,
	// playwright.1229-hub.staging.config.ts) ein No-Op: goto('/') landet nicht
	// auf /login, der Form-Login-Zweig (POST /api/auth/login) wird also NICHT
	// pro Test erneut ausgefuehrt — genau das vermeidet das Staging-Rate-Limit.
	// Ohne Setup-Projekt (z.B. lokaler Lauf gegen playwright.config.ts) bleibt
	// login() weiterhin funktionsfaehig als echter Fallback-Login.
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// ── AC-1: Stat "Briefings" Desktop ───────────────────────────────────────
	test('AC-1: Übersicht (Desktop) zeigt Stat "Briefings" mit "Morgen 07:00 · Abend 18:00"', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');

			await expect(page.locator('[data-testid="compare-detail-stat-briefings"]:visible').first()).toHaveText(
				'Morgen 07:00 · Abend 18:00',
				{ timeout: 10_000 }
			);
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── AC-2: Stat "Briefings" Mobile, dieselbe Angabe wie Desktop ───────────
	test('AC-2: Übersicht (Mobile) zeigt dieselbe Briefings-Angabe wie Desktop', async ({ page }) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 390, height: 844 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');

			await expect(page.locator('[data-testid="compare-detail-stat-briefings"]:visible').first()).toHaveText(
				'Morgen 07:00 · Abend 18:00',
				{ timeout: 10_000 }
			);
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── AC-4: Versand-Tab zeigt "Briefing-Zeiten", nicht mehr Rhythmus-Sprache ─
	test('AC-4: Versand-Tab zeigt "Briefing-Zeiten", nicht mehr "Rhythmus & Vorausschau"/"Zeitplan"/"Zeitfenster"', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');
			await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();

			const panel = page.locator('[data-testid="compare-detail-panel-versand"]:visible').first();
			await expect(panel).toBeVisible({ timeout: 10_000 });
			await expect(panel).toContainText('Briefing-Zeiten');
			await expect(panel).not.toContainText('Rhythmus & Vorausschau');
			await expect(panel).not.toContainText('Zeitplan');
			await expect(panel).not.toContainText('Zeitfenster');
			await expect(panel).not.toContainText(`${7}–${16} Uhr`);
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── Fix-Loop 1 (F001/F002): Übersicht-Panel zeigt denselben rohen
	// Stunden-Bereich nirgends mehr — weder im Monitoring-Streifen ("Nächster
	// Versand"-Stat) noch in der Zusammenfassungs-Card "Versand".
	test('Fix-Loop 1: Übersicht-Panel zeigt keinen rohen Stunden-Bereich und keine Rhythmus-Sprache', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');

			const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible').first();
			await expect(panel).toBeVisible({ timeout: 10_000 });
			await expect(panel).not.toContainText(`${7}–${16} Uhr`);
			await expect(panel).not.toContainText('Rhythmus');
			await expect(panel).not.toContainText('Zeitplan');
			await expect(panel).not.toContainText('Zeitfenster');
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── AC-5: Edit-Stift → /edit?tab=versand, Versand-Tab dort direkt aktiv ──
	test('AC-5: Edit-Stift bei "Briefings" navigiert zu /edit?tab=versand mit aktivem Versand-Tab', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');
			await page.locator('[data-testid="compare-detail-tab-versand"]:visible').first().click();

			await page.locator('[data-testid="compare-versand-edit-briefings"]:visible').first().click();
			await page.waitForLoadState('networkidle');

			await expect(page).toHaveURL(new RegExp(`/compare/${id}/edit\\?tab=versand$`));
			await expect(
				page.locator('[data-testid="compare-editor-tab-versand"]:visible').first()
			).toHaveAttribute('data-active', 'true', { timeout: 10_000 });
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── AC-6: unbekannter/fehlender ?tab=-Wert → Default-Tab ─────────────────
	test('AC-6: unbekannter ?tab=-Wert im Editor → Default-Tab "vergleich" aktiv, kein Crash', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		try {
			await page.goto(`/compare/${id}/edit?tab=doesnotexist`);
			await page.waitForLoadState('networkidle');

			await expect(
				page.locator('[data-testid="compare-editor-tab-vergleich"]:visible').first()
			).toHaveAttribute('data-active', 'true', { timeout: 10_000 });

			await page.goto(`/compare/${id}/edit`);
			await page.waitForLoadState('networkidle');
			await expect(
				page.locator('[data-testid="compare-editor-tab-vergleich"]:visible').first()
			).toHaveAttribute('data-active', 'true', { timeout: 10_000 });
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── AC-7: Idealwerte-SummaryCard neue Copy, keine Ranking-Formulierung ───
	test('AC-7: Idealwerte-SummaryCard zeigt "Kein Score, kein Ranking", nicht mehr "bestimmen das Ranking"', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');

			const panel = page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible').first();
			await expect(panel).toContainText('Kein Score, kein Ranking', { timeout: 10_000 });
			await expect(panel).not.toContainText('bestimmen das Ranking');
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── AC-8: Vorschau-Tab Kanal SMS/Telegram → Missing-Hinweis, kein Rang/Score ─
	test('AC-8: Vorschau-Tab Kanal SMS/Telegram zeigt Missing-Hinweis, kein Rang/Score-Markup', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');
			await page.locator('[data-testid="compare-detail-tab-vorschau"]:visible').first().click();

			const panel = page.locator('[data-testid="compare-detail-panel-vorschau"]:visible').first();
			await expect(panel).toBeVisible({ timeout: 10_000 });

			for (const label of ['SMS', 'Telegram']) {
				await panel.getByRole('button', { name: label, exact: true }).first().click();
				await expect(panel).toContainText('Vorschau-Daten nicht verfügbar.', { timeout: 10_000 });
				// Kein Rang/Score-Markup der V1-Molecules (CompareChatBubble/CompareSmsPreview):
				// deren Bubble-Header trägt den Marker-Text "Gregor Zwanzig".
				await expect(panel).not.toContainText('Gregor Zwanzig');
			}
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── AC-10: alle 6 Tabs klickbar, Panel je sichtbar ───────────────────────
	test('AC-10: alle sechs compare-detail-tab-* Testids klickbar, Panel sichtbar', async ({ page }) => {
		const { id } = await createPreset(page);
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');

			const tabs = ['uebersicht', 'orte', 'idealwerte', 'layout', 'versand', 'vorschau'];
			for (const tab of tabs) {
				await page.locator(`[data-testid="compare-detail-tab-${tab}"]:visible`).first().click();
				await expect(
					page.locator(`[data-testid="compare-detail-panel-${tab}"]:visible`).first()
				).toBeVisible({ timeout: 10_000 });
			}
		} finally {
			await deletePreset(page, id);
		}
	});

	// ── Edge Case: Draft ohne aktive Slots → "—" ─────────────────────────────
	test('Draft ohne aktive Briefing-Slots zeigt "—" statt leerem/verwaistem Text', async ({ page }) => {
		const { id } = await createPreset(page, {
			morning_enabled: false,
			evening_enabled: false
		});
		try {
			await page.setViewportSize({ width: 1280, height: 900 });
			await page.goto(`/compare/${id}`);
			await page.waitForLoadState('networkidle');

			await expect(page.locator('[data-testid="compare-detail-stat-briefings"]:visible').first()).toHaveText(
				'—',
				{ timeout: 10_000 }
			);
		} finally {
			await deletePreset(page, id);
		}
	});
});
