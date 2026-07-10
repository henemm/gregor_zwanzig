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
// Aktuell (RED): der Toggle `compare-alarm-radar-toggle` existiert NICHT im
// DOM von `CompareAlarmSection.svelte` — das Backend-Feld
// `radar_alert_enabled` (Slice 1b) ist bereits live, aber im Frontend noch
// nicht verdrahtet. AC-1/AC-2/AC-3 muessen daher fehlschlagen.
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
	await page.goto(`/compare/${id}/edit`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-editor-tab-alarme"]').click();
	// CompareEditor.svelte rendert CompareAlarmSection zweimal (Desktop- und
	// Mobile-Markup, `.cm-mobile` per CSS-Breakpoint ausgeblendet, DOM bleibt
	// aber bestehen) — `.first()` greift bei 1280x900 immer den Desktop-Block.
	await expect(page.locator('[data-testid="compare-alarm-section"]').first()).toBeVisible({
		timeout: 10_000
	});
}

// `.first()` s.o. — RADAR_TOGGLE existiert (sobald implementiert) ebenfalls
// zweifach im DOM (Desktop/Mobile-Duplikat von CompareAlarmSection).
function radarToggle(page: Page) {
	return page.locator('[data-testid="compare-alarm-radar-toggle"] input[type="checkbox"]').first();
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

		await page.locator('[data-testid="compare-editor-save"]').click();
		// Issue #758: handleSave() speichert direkt via api.put OHNE Redirect
		// (CompareEditor.svelte:164 „Save direkt via api.put, kein Redirect") —
		// kein toHaveURL-Wait mehr. Stattdessen: SaveIndicator wechselt nach
		// erfolgreichem PUT auf data-state="idle" (compareSaveCtl.setSaved()).
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
		await page.locator('[data-testid="compare-editor-tab-alarme"]').click();
		await expect(radarToggle(page)).toBeChecked();
	});

	// ── AC-3: Radar an, nur Name aendern + speichern → Radar bleibt erhalten ──
	test('test_radar_toggle_preserved_on_unrelated_save', async ({ page }) => {
		const { id } = await createPreset(page);
		await openAlarmeTab(page, id);

		const toggle = radarToggle(page);
		await toggle.click();
		await expect(toggle).toBeChecked();
		await page.locator('[data-testid="compare-editor-save"]').click();
		// Issue #758: kein Redirect nach dem Speichern (s. AC-2-Kommentar oben) —
		// auf den SaveIndicator-Abschluss warten statt auf eine URL-Änderung.
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute(
			'data-state',
			'idle',
			{ timeout: 10_000 }
		);

		// Nur der Name wird geaendert — Radar-Alarm-Feld nicht angefasst.
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-name"]').fill('Nur Name geändert ' + Date.now());
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute(
			'data-state',
			'idle',
			{ timeout: 10_000 }
		);

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.radar_alert_enabled).toBe(true);

		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-alarme"]').click();
		await expect(radarToggle(page)).toBeChecked();
	});
});
