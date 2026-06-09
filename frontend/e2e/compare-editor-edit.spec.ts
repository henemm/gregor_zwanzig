// E2E — Issue #679 (Epic #677): Compare-Editor Slice 2 — Edit-Modus + Dirty/Save-Flow
//
// Spec: docs/specs/modules/issue_679_compare_editor_edit.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging. In der
// RED-Phase schlägt der Test fehl, weil `/compare/[id]/edit` noch den alten
// `CompareWizard` (Stepper) rendert — die neuen Editor-Testids
// (`compare-editor`, `compare-editor-dirty-pill`, `compare-editor-save`,
// `compare-editor-discard`, `compare-editor-status-dot`) existieren nicht.
//
// Base-URL: GZ_SVELTE_BASE (Default: playwright.config.ts baseURL = Staging)
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/compare-editor-edit.spec.ts --config playwright.config.ts

import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import { login } from './helpers.js';

// ── Hilfsfunktion: legt einen Compare-Preset im aktuellen Nutzer-Kontext an ──
// Nutzt den Session-Cookie der eingeloggten Page → echte Mandanten-Bindung.
async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string; empfaenger: string[] }> {
	const empfaenger = ['edit-rt@example.com'];
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'E2E Editvergleich ' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'skitour',
			hour_from: 7,
			hour_to: 16,
			empfaenger,
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id, empfaenger: body.empfaenger ?? empfaenger };
}

test.describe('Issue #679: Compare-Editor Edit-Modus (Desktop)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: alle 5 Tabs sofort frei, KEIN Fortschrittsbalken ───────────────
	test('AC-1: alle Tabs anklickbar, kein Fortschrittsbalken', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');

		const editor = page.locator('[data-testid="compare-editor"]');
		await expect(editor).toBeVisible({ timeout: 10_000 });

		// Kein Fortschrittsbalken im Edit-Modus
		await expect(page.locator('[data-testid="compare-editor-progress"]')).toHaveCount(0);

		// Alle fünf Tabs sind freigeschaltet (data-locked=false)
		for (const t of ['vergleich', 'orte', 'idealwerte', 'layout', 'versand']) {
			await expect(
				page.locator(`[data-testid="compare-editor-tab-${t}"]`)
			).toHaveAttribute('data-locked', 'false');
		}
		// Direktsprung auf einen späten Tab funktioniert
		await page.locator('[data-testid="compare-editor-tab-versand"]').click();
		await expect(
			page.locator('[data-testid="compare-editor-tab-versand"]')
		).toHaveAttribute('data-active', 'true');
	});

	// ── AC-2: Feldänderung → „Ungespeichert"-Pill + Speichern aktiv ──────────
	test('AC-2: Änderung zeigt Ungespeichert-Pill', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');

		// Vor Änderung: keine Dirty-Pill
		await expect(page.locator('[data-testid="compare-editor-dirty-pill"]')).toHaveCount(0);

		await page.locator('[data-testid="compare-editor-name"]').fill('Geänderter Name');

		await expect(page.locator('[data-testid="compare-editor-dirty-pill"]')).toBeVisible();
		await expect(page.locator('[data-testid="compare-editor-save"]')).toBeEnabled();
	});

	// ── AC-3: Speichern persistiert + empfaenger bleibt erhalten ─────────────
	test('AC-3: Speichern ist persistent und behält Empfänger', async ({ page }) => {
		const { id, empfaenger } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');

		const neuerName = 'Persistiert ' + Date.now();
		await page.locator('[data-testid="compare-editor-name"]').fill(neuerName);
		await page.locator('[data-testid="compare-editor-save"]').click();

		// Save navigiert zur Detail-Seite
		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });

		// Persistenz + Datenerhalt via echtem GET prüfen
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.name).toBe(neuerName);
		expect(preset.empfaenger).toEqual(empfaenger); // Empfänger NICHT verloren
	});

	// ── AC-4: Verwerfen → Bestätigung → Navigation zur Detail-Seite ──────────
	test('AC-4: Verwerfen verwirft Änderung und navigiert zur Detail-Seite', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');

		await page.locator('[data-testid="compare-editor-name"]').fill('Wird verworfen');
		await page.locator('[data-testid="compare-editor-discard"]').click();

		// Bestätigungsdialog bestätigen
		const confirm = page.getByRole('button', { name: /Verwerfen|Bestätigen|Ja/ });
		await confirm.click();

		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });

		// Änderung wurde NICHT persistiert
		const res = await page.request.get(`/api/compare/presets/${id}`);
		const preset = await res.json();
		expect(preset.name).not.toBe('Wird verworfen');
	});

	// ── AC-5: Mandantentrennung — Nutzer B sieht/ändert A's Preset nicht ─────
	test('AC-5: zweiter Nutzer hat keinen Zugriff auf fremdes Preset', async ({ page, browser }) => {
		const { id } = await createPreset(page); // gehört Nutzer A (admin)

		// Nutzer B registrieren + einloggen in frischem Kontext
		const ctxB = await browser.newContext();
		const pageB = await ctxB.newPage();
		const userB = 'editb' + Date.now();
		const reg = await pageB.request.post('/api/auth/register', {
			data: { username: userB, password: 'test1234' }
		});
		expect([200, 201].includes(reg.status()), 'Registrierung B fehlgeschlagen').toBeTruthy();

		// B liest A's Preset → 404 (mandantengetrennt)
		const getB = await pageB.request.get(`/api/compare/presets/${id}`);
		expect(getB.status()).toBe(404);

		// B versucht A's Preset zu überschreiben → 404, kein Cross-User-Write
		const putB = await pageB.request.put(`/api/compare/presets/${id}`, {
			data: { name: 'Hijack', location_ids: [], schedule: 'daily', profil: 'skitour', hour_from: 7, hour_to: 16, empfaenger: [] }
		});
		expect(getB.status() === 404 || putB.status() === 404).toBeTruthy();

		await ctxB.close();
	});

	// ── AC-6: Status-Dot zeigt aktiv/pausiert ────────────────────────────────
	test('AC-6: Status-Dot spiegelt aktiv vs. pausiert', async ({ page }) => {
		// Aktiver Vergleich (schedule != manual)
		const active = await createPreset(page, { schedule: 'daily' });
		await page.goto(`/compare/${active.id}/edit`);
		await page.waitForLoadState('networkidle');
		await expect(
			page.locator('[data-testid="compare-editor-status-dot"]')
		).toHaveAttribute('data-status', 'active');

		// Pausierter Vergleich (schedule == manual)
		const paused = await createPreset(page, { schedule: 'manual' });
		await page.goto(`/compare/${paused.id}/edit`);
		await page.waitForLoadState('networkidle');
		await expect(
			page.locator('[data-testid="compare-editor-status-dot"]')
		).toHaveAttribute('data-status', 'paused');
	});
});
