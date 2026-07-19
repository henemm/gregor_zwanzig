// E2E — Issue #1041 Slice 2/3 (Frontend): Radar-Alarm-Schalter im
// Compare-Editor-Tab „Alarme".
//
// Spec: docs/specs/modules/issue_1041c_radar_toggle_frontend.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging. Login-
// Fixture, Preset-Anlage-Helper und Viewport 1:1 aus
// compare-alarm-config.spec.ts (Issue #1170) uebernommen — dort NICHTS
// bewertet, nur wiederverwendet.
//
// Issue #1258 Scheibe S4: CompareAlarmSection wurde durch den geteilten
// AlarmeTab (context="vergleich") abgeloest und geloescht — Testids
// migriert: `compare-alarm-section` → `alarme-tab`,
// `compare-alarm-radar-toggle` → `alarme-radar-toggle`.
//
// Base-URL: GZ_SVELTE_BASE (Default: playwright.config.ts baseURL = Staging)
//
// Ausführen (staging-only, NICHT lokal — kein lokaler Server):
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/compare-radar-toggle.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

// ── Hilfsfunktion: legt einen Compare-Preset im aktuellen Nutzer-Kontext an ──
// Identisch zu compare-alarm-config.spec.ts::createPreset (Issue #1170).
async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string; empfaenger: string[] }> {
	const empfaenger = ['radar-toggle-rt@example.com'];
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'E2E Radar-Toggle ' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
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

async function openAlarmeTab(page: Page, id: string): Promise<void> {
	await page.goto(`/compare/${id}`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
	// Hub rendert AlarmeTab doppelt (Desktop/Mobile im DOM) — `.first()` greift
	// bei 1280x900 den Desktop-Block.
	await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({
		timeout: 10_000
	});
}

// `.first()` s.o. — RADAR_TOGGLE existiert ebenfalls zweifach im DOM
// (Desktop/Mobile-Duplikat des AlarmeTab-Organism).
function radarToggle(page: Page) {
	return page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first();
}

test.describe('Issue #1041 Slice 2: Radar-Alarm-Schalter im Compare-Editor (Desktop)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: neues/Altpreset ohne radar_alert_enabled → Schalter sichtbar, AUS ──
	test('test_radar_toggle_default_off_on_new_preset', async ({ page }) => {
		const { id } = await createPreset(page);
		await openAlarmeTab(page, id);

		const toggle = radarToggle(page);
		await expect(toggle).toBeVisible();
		await expect(toggle).not.toBeChecked();
	});

	// ── AC-2: Schalter einschalten, speichern, Reload → Schalter AN + Backend ──
	test('test_radar_toggle_enable_persists_roundtrip', async ({ page }) => {
		const { id } = await createPreset(page);
		await openAlarmeTab(page, id);

		const toggle = radarToggle(page);
		await expect(toggle).not.toBeChecked();
		await toggle.click();
		await expect(toggle).toBeChecked();

		// Hub-Autosave (Epic #1273 S4c): kein Speichern-Button (SaveIndicator → idle).
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute(
			'data-state',
			'idle',
			{ timeout: 10_000 }
		);

		// Persistenz via echtem GET pruefen.
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.radar_alert_enabled).toBe(true);

		// Zusaetzlich UI-seitig: Seite neu laden, Tab „Alarme“, Schalter AN.
		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
		await expect(radarToggle(page)).toBeChecked();
	});

	// ── AC-3: Radar an, nur Name aendern + speichern → Radar bleibt erhalten ──
	test('test_radar_toggle_preserved_on_unrelated_save', async ({ page }) => {
		const { id } = await createPreset(page);
		await openAlarmeTab(page, id);

		const toggle = radarToggle(page);
		await toggle.click();
		await expect(toggle).toBeChecked();
		// Hub-Autosave (s. AC-2): kein manueller Speichern-Button — auf den
		// SaveIndicator-Abschluss (idle) warten.
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute(
			'data-state',
			'idle',
			{ timeout: 10_000 }
		);

		// Nur der Name wird geaendert (Radar-Feld unberührt) — im Hub via
		// Inline-Edit-Sequenz (Stift → Feld → OK).
		const neuerName = 'Nur Name geändert ' + Date.now();
		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-hub-name-edit-toggle"]:visible').first().click();
		await page.locator('[data-testid="compare-hub-name-edit"]:visible').first().fill(neuerName);
		await page.locator('[data-testid="compare-hub-name-save"]:visible').first().click();
		// Umbenennung persistiert, sobald der Kopf den neuen Namen zeigt.
		await expect(page.getByRole('heading', { level: 1 })).toContainText(neuerName, {
			timeout: 10_000
		});

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.radar_alert_enabled).toBe(true);

		await page.goto(`/compare/${id}`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-detail-tab-alarme"]').click();
		await expect(radarToggle(page)).toBeChecked();
	});
});
