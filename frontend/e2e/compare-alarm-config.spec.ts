// E2E — Issue #1170 (Epic #1095 Scheibe 3/3): Compare-Editor Tab „Alarme"
//
// Spec: docs/specs/modules/issue_1170_compare_alert_config.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging. Login-
// Fixture, Preset-Anlage-Helper und Viewport 1:1 aus compare-editor-edit.spec.ts
// uebernommen (Issue #679) — dort NICHTS bewertet, nur wiederverwendet.
//
// Base-URL: GZ_SVELTE_BASE (Default: playwright.config.ts baseURL = Staging)
//
// Ausführen (staging-only, NICHT lokal — kein lokaler Server):
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/compare-alarm-config.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

// ── Hilfsfunktion: legt einen Compare-Preset im aktuellen Nutzer-Kontext an ──
// Identisch zu compare-editor-edit.spec.ts::createPreset (Issue #679), zusätzlich
// mit display_config.active_metrics, damit die Empfindlichkeits-Tabelle
// (AlertMetricLevelTable) im Tab „Alarme" nicht wegen fehlender aktiver
// Metriken leer bleibt (siehe CompareAlarmSection.svelte activeMetrics-Derive).
async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string; empfaenger: string[] }> {
	const empfaenger = ['alarm-rt@example.com'];
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'E2E Alarmkonfig ' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'skitour',
			hour_from: 7,
			hour_to: 16,
			empfaenger,
			display_config: { active_metrics: ['wind_max_kmh'] },
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id, empfaenger: body.empfaenger ?? empfaenger };
}

test.describe('Issue #1170: Compare-Editor Tab „Alarme" (Desktop)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: Tab „Alarme" öffnen → Sektion + Controls sichtbar ─────────────
	test('AC-1: Tab Alarme zeigt Cooldown-, Ruhezeiten- und Empfindlichkeits-Controls', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');

		await page.locator('[data-testid="compare-editor-tab-alarme"]').click();

		await expect(page.locator('[data-testid="compare-alarm-section"]')).toBeVisible({
			timeout: 10_000
		});
		// Empfindlichkeit (aktive Metrik wind_max_kmh → wind_gust ist alarmierbar)
		await expect(page.locator('[data-testid="alert-metric-level-table"]')).toBeVisible();
		// Cooldown
		await expect(page.locator('[data-testid="alert-cooldown-card"]')).toBeVisible();
		await expect(page.locator('[data-testid="alert-cooldown-input"]')).toBeVisible();
		// Ruhezeiten
		await expect(page.locator('[data-testid="alert-quiet-hours-card"]')).toBeVisible();
	});

	// ── AC-2: Wert setzen, speichern, Reload → Wert bleibt gesetzt ──────────
	test('AC-2: gesetzter Cooldown-Wert übersteht Speichern + Reload', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');

		await page.locator('[data-testid="compare-editor-tab-alarme"]').click();
		await expect(page.locator('[data-testid="compare-alarm-section"]')).toBeVisible({
			timeout: 10_000
		});

		await page.locator('[data-testid="alert-cooldown-input"]').fill('90');
		await page.locator('[data-testid="compare-editor-save"]').click();

		// Save navigiert zur Detail-Seite (identisches Muster wie AC-3 #679)
		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });

		// Persistenz via echtem GET prüfen
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.alert_cooldown_minutes).toBe(90);

		// Zusätzlich UI-seitig: erneut öffnen, Tab „Alarme“, Wert weiterhin gesetzt
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-alarme"]').click();
		await expect(page.locator('[data-testid="alert-cooldown-input"]')).toHaveValue('90');

		// page.reload() auf derselben Edit-Seite, Tab erneut öffnen → Wert hält
		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-alarme"]').click();
		await expect(page.locator('[data-testid="alert-cooldown-input"]')).toHaveValue('90');
	});
});
