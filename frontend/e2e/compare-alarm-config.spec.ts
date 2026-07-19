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
			profil: 'wintersport',
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

// Epic #1273 S4c BEFUND: activeMetricKeys hydratisiert nur lazy beim Besuch des
// Wetter-Metriken-/Idealwerte-Tabs (CompareTabs.svelte:647/347), NICHT beim
// Alarme-Mount (:569) → zuerst Wetter-Metriken-Tab besuchen.
async function openAlarmeTab(page: Page, id: string): Promise<void> {
	await page.goto(`/compare/${id}`);
	await page.waitForLoadState('networkidle');
	// Wetter-Metriken-Tab besuchen → hydratisiert wiz.activeMetricKeys.
	await page.locator('[data-testid="compare-detail-tab-wetter-metriken"]').click();
	await page.waitForTimeout(300);
	await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
	await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
}

test.describe('Issue #1170: Compare-Editor Tab „Alarme" (Desktop)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: Tab „Alarme" → Empfindlichkeits-Tabelle + Cooldown/Quiet ──────
	// Issue #1258 Scheibe S4 (E5, AC-18): der geteilte AlarmeTab (context=
	// "vergleich") ersetzt CompareAlarmSection — Cooldown/Ruhezeiten ziehen
	// vom Versand-Tab zurueck in den Alarme-Tab (umgekehrt zu #1232 Scheibe
	// 2b). Testid `compare-alarm-section` → `alarme-tab`.
	test('AC-1: Alarme zeigt Empfindlichkeits-Tabelle + Cooldown/Ruhezeiten; Versand nicht mehr', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		await openAlarmeTab(page, id);
		// Empfindlichkeit (aktive Metrik wind_max_kmh → wind_gust ist alarmierbar)
		await expect(page.locator('[data-testid="alert-metric-level-table"]').first()).toBeVisible();
		await expect(page.locator('[data-testid="alert-cooldown-card"]').first()).toBeVisible();
		await expect(page.locator('[data-testid="alert-cooldown-input"]').first()).toBeVisible();
		await expect(page.locator('[data-testid="alert-quiet-hours-card"]').first()).toBeVisible();

		// Versand-Tab enthaelt die Alert-Zustellung nicht mehr (AC-18).
		await page.locator('[data-testid="compare-detail-tab-versand"]').click();
		await expect(page.locator('[data-testid="alert-cooldown-card"]')).toHaveCount(0);
	});

	// ── AC-2: Wert setzen, speichern, Reload → Wert bleibt gesetzt ──────────
	test('AC-2: gesetzter Cooldown-Wert übersteht Speichern + Reload', async ({ page }) => {
		const { id } = await createPreset(page);
		await openAlarmeTab(page, id);
		await expect(page.locator('[data-testid="alert-cooldown-input"]').first()).toBeVisible({
			timeout: 10_000
		});

		await page.locator('[data-testid="alert-cooldown-input"]').first().fill('90');
		await page.locator('[data-testid="alert-cooldown-input"]').first().blur();

		// Hub-Autosave (Epic #1273 S4c): kein manueller Speichern-Button — die
		// Eingabe wird automatisch persistiert (SaveIndicator → idle).
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute(
			'data-state',
			'idle',
			{ timeout: 10_000 }
		);

		// Persistenz via echtem GET prüfen
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.alert_cooldown_minutes).toBe(90);

		// Zusätzlich UI-seitig: erneut öffnen, Alarme-Tab, Wert weiterhin gesetzt
		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
		await expect(page.locator('[data-testid="alert-cooldown-input"]').first()).toHaveValue('90');

		// page.reload() auf derselben Edit-Seite, Tab erneut öffnen → Wert hält
		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
		await expect(page.locator('[data-testid="alert-cooldown-input"]').first()).toHaveValue('90');
	});
});
