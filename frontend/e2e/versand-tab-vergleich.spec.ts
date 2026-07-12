// E2E — Issue #1232 Scheibe 2b: VersandTab context="vergleich" im Compare-Editor
//
// Spec: docs/specs/modules/versand_tab_vergleich.md
//
// Verhaltensnachweis der ACs als eingeloggter Nutzer gegen Staging/Preview.
// Echter Klick-Pfad (Tab-Klick, kein page.goto direkt in den Tab-Zustand),
// Doppel-Mount Desktop+Mobile beachtet (`:visible`-Filter, etabliertes Muster).
//
// Hinweis (RED-Probe #1232 Scheibe 2b): `alert-metric-level-table` rendert nur,
// wenn das Preset aktive Metriken (display_config.active_metrics) hat — sonst
// zeigt CompareAlarmSection den Hinweis `compare-alarm-no-metrics`. Presets in
// diesem Spec setzen deshalb bewusst `active_metrics: ['wind_max_kmh']`.
//
// Ausführen:
//   cd frontend && E2E_USER=admin E2E_PASS=test1234 \
//     npx playwright test e2e/versand-tab-vergleich.spec.ts --config playwright.config.ts

import { test, expect, type Page, type Locator } from '@playwright/test';
import { login } from './helpers.js';

async function createPreset(
	page: Page,
	overrides: Record<string, unknown> = {}
): Promise<{ id: string }> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: 'VersandTab-Vergleich-E2E ' + Date.now(),
			location_ids: [],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['versand-vergleich-e2e@example.com'],
			display_config: { active_metrics: ['wind_max_kmh'] },
			...overrides
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	return { id: body.id };
}

async function openVersandTab(page: Page, id: string): Promise<void> {
	await page.goto(`/compare/${id}/edit`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();
}

test.describe('Issue #1232 Scheibe 2b: VersandTab (vergleich) im Compare-Editor', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-1: 4 Versand-Sektionen in Design-Reihenfolge ──────────────────────
	test('AC-1: Versand-Tab zeigt Kanäle → Zeitplan → Laufzeit → Alert-Zustellung', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		await openVersandTab(page, id);

		await expect(page.locator('[data-testid="compare-step5-channel-email"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
		await expect(page.locator('[data-testid="morning-master-switch"]:visible').first()).toBeVisible();
		await expect(page.locator('[data-testid="briefings-laufzeit-vergleich"]:visible').first()).toBeVisible();
		await expect(page.locator('[data-testid="alert-cooldown-card"]:visible').first()).toBeVisible();
	});

	// ── AC-3: Laufzeit — "Bis auf Weiteres" löscht ein gesetztes end_date ────
	test('AC-3: "Bis auf Weiteres" löscht ein gesetztes Enddatum nach Speichern + Reload', async ({
		page
	}) => {
		const { id } = await createPreset(page, { end_date: '2026-09-01' });
		await openVersandTab(page, id);

		await page.locator('[data-testid="compare-versand-enddate-open"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.end_date, 'end_date muss nach dem Sentinel gelöscht sein').toBeFalsy();
	});

	// ── AC-3b: Laufzeit — "Bis Datum" + Datum setzt end_date reload-fest ─────
	test('AC-3b: "Bis Datum" + Datumsauswahl persistiert das Enddatum', async ({ page }) => {
		const { id } = await createPreset(page);
		await openVersandTab(page, id);

		await page.locator('[data-testid="compare-versand-enddate-date"]:visible').first().click();
		await page
			.locator('[data-testid="compare-versand-enddate-input"]:visible')
			.first()
			.fill('2026-10-15');
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.end_date).toBe('2026-10-15');
	});

	// ── AC-4: Alarme-Tab verliert Cooldown/Quiet, behält Level-Tabelle ───────
	test('AC-4: Alarme-Tab enthält keine Cooldown-Karte mehr, Level-Tabelle bleibt', async ({
		page
	}) => {
		const { id } = await createPreset(page);
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();

		await expect(page.locator('[data-testid="compare-alarm-section"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
		// Level-Tabelle sichtbar (Preset hat aktive Metrik wind_max_kmh → wind_gust)
		await expect(page.locator('[data-testid="alert-metric-level-table"]:visible').first()).toBeVisible();
		// Cooldown-Karte NICHT mehr im Alarme-Tab (zog in den Versand-Tab um)
		await expect(page.locator('[data-testid="alert-cooldown-card"]:visible')).toHaveCount(0);
	});

	// ── AC-7: Kein Kanal aktiv → Warnbox statt Zeitplan-Karten ───────────────
	test('AC-7: alle Kanäle aus zeigt "Kein Kanal aktiv" statt Zeitplan-Karten', async ({ page }) => {
		const { id } = await createPreset(page);
		await openVersandTab(page, id);

		const email: Locator = page
			.locator('[data-testid="compare-step5-channel-email"]:visible')
			.first()
			.locator('input[type="checkbox"]');
		if (await email.isChecked()) await email.uncheck();

		await expect(page.locator('[data-testid="briefings-channel-empty"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
	});

	// ── AC-9/AC-10: Doppel-Mount Desktop+Mobile, kein horizontales Scrollen ──
	test('AC-10: mobiler Viewport — Versand-Tab ohne horizontales Scrollen', async ({ page }) => {
		const { id } = await createPreset(page);
		await page.setViewportSize({ width: 390, height: 844 });
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="cm-mobile-tab-versand"]').click();

		await expect(page.locator('[data-testid="compare-step5-channel-email"]:visible').first()).toBeVisible({
			timeout: 10_000
		});
		const noHorizontalScroll = await page.evaluate(
			() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
		);
		expect(noHorizontalScroll, 'horizontales Scrollen auf Mobile darf nicht auftreten').toBeTruthy();
	});

	// ── AC-2: Morgen-Uhrzeit ändern → Speichern → Reload → Wert bleibt ───────
	test('AC-2: geänderte Morgen-Uhrzeit übersteht Speichern + Reload', async ({ page }) => {
		const { id } = await createPreset(page); // Default: morning_enabled=true, morning_time=07:00:00
		await openVersandTab(page, id);

		const morningTime = () => page.locator('[data-testid="report-morning-time"]:visible').first();
		await expect(morningTime()).toHaveValue('07:00', { timeout: 10_000 });

		await morningTime().fill('08:30');
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		await page.reload();
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();
		await expect(morningTime()).toHaveValue('08:30', { timeout: 10_000 });

		// Testdaten sauber: Ausgangswert wiederherstellen und speichern.
		await morningTime().fill('07:00');
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});
	});

	// ── AC-6: Create-Flow — POST-Body enthält die 5 Slot-Felder ──────────────
	test('AC-6: Create-Flow sendet die 5 Slot-Felder im POST-Body an /api/compare/presets', async ({
		page
	}) => {
		const suffix = Date.now();
		const nameA = 'VersandVergleich-Ort-A-' + suffix;
		const nameB = 'VersandVergleich-Ort-B-' + suffix;
		const [rA, rB] = await Promise.all([
			page.request.post('/api/locations', {
				data: { name: nameA, lat: 47.0, lon: 13.0, region: 'VersandVergleich-Region' }
			}),
			page.request.post('/api/locations', {
				data: { name: nameB, lat: 47.1, lon: 13.1, region: 'VersandVergleich-Region' }
			})
		]);
		expect(rA.ok() && rB.ok(), 'Location-Anlage fehlgeschlagen').toBeTruthy();

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		const d = page.locator('.cm-desktop');

		await d.locator('[data-testid="compare-editor-name"]').fill('AC-6 Create-Flow ' + suffix);
		await d.locator('[data-testid="compare-editor-tab-orte"]').click();
		await d.locator('[data-testid="compare-step2-library"]').waitFor({ timeout: 8_000 });
		await d.locator('[data-testid="compare-step2-library"]').getByText(nameA, { exact: true }).click();
		await d.locator('[data-testid="compare-step2-library"]').getByText(nameB, { exact: true }).click();
		await d.locator('[data-testid="compare-editor-tab-idealwerte"]').click();
		await d.locator('[data-testid="compare-editor-tab-layout"]').click();
		await d.locator('[data-testid="compare-editor-tab-versand"]').click();

		const [request] = await Promise.all([
			page.waitForRequest(
				(req) => req.url().includes('/api/compare/presets') && req.method() === 'POST'
			),
			d.locator('[data-testid="compare-editor-activate"]').click()
		]);
		const body = request.postDataJSON() as Record<string, unknown>;

		expect(body.morning_enabled).toBe(true);
		expect(body.morning_time).toBe('07:00:00');
		expect(body.evening_enabled).toBe(false);
		expect(body.evening_time).toBe('18:00:00');
		expect(body.end_date == null, 'end_date darf beim Create ohne Laufzeit-Auswahl fehlen/null sein').toBeTruthy();
	});

	// ── AC-8: Verwerfen setzt Slot-/Laufzeit-Änderungen zurück ───────────────
	test('AC-8: Verwerfen verwirft geänderte Slot-Felder und Laufzeit', async ({ page }) => {
		const { id } = await createPreset(page); // Default: morning 07:00 an, kein end_date
		await openVersandTab(page, id);

		await page.locator('[data-testid="report-morning-time"]:visible').first().fill('11:15');
		await page.locator('[data-testid="compare-versand-enddate-date"]:visible').first().click();
		await page
			.locator('[data-testid="compare-versand-enddate-input"]:visible')
			.first()
			.fill('2026-12-01');

		await page.locator('[data-testid="compare-editor-discard"]').click();
		const confirmBtn = page.getByRole('button', { name: /Verwerfen|Bestätigen|Ja/ });
		await confirmBtn.click();

		await expect(page).toHaveURL(new RegExp(`/compare/${id}$`), { timeout: 10_000 });

		// Persistenz unangetastet (API).
		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.morning_time).toBe('07:00:00');
		expect(preset.end_date == null).toBeTruthy();

		// UI-seitig: frisches Öffnen des Edit-Pfads zeigt den zuletzt gespeicherten Stand.
		await openVersandTab(page, id);
		await expect(page.locator('[data-testid="report-morning-time"]:visible').first()).toHaveValue('07:00');
		await expect(page.locator('[data-testid="compare-versand-enddate-open"]:visible').first()).toHaveAttribute(
			'aria-selected',
			'true'
		);
	});

	// ── Staging-F001 (AC-5): Horizont/Top-N/Stundenverlauf persistieren ──────
	// Bug: CompareEditor.svelte trackte forecastHours/topN/hourlyEnabled weder
	// im Dirty-Snapshot noch im handleSave()-Aufruf — UI änderte sich, der
	// PUT-Body enthielt aber weiterhin die alten Werte (Round-Trip-Spread aus
	// original statt aus wiz.*). Layout-Tab (CompareInhaltSection) ist analog
	// zu CompareInhaltSection ebenfalls Doppel-Mount (Desktop+Mobile) — `:visible`.
	test('Staging-F001: Horizont/Top-N/Stundenverlauf-Toggle persistieren über den zentralen Speichern-Button', async ({
		page
	}) => {
		const { id } = await createPreset(page); // Default: forecast_hours=48 (Go-Fallback), topN=3, hourly_enabled=true
		await page.goto(`/compare/${id}/edit`);
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').first().click();

		const horizon = page.locator('[data-testid="compare-step5-forecast-hours"]:visible').first();
		const topN = page.locator('[data-testid="compare-step5-topn"]:visible').first();
		const hourlyToggle = page
			.locator('[data-testid="compare-step5-hourly-enabled-toggle"]:visible')
			.first()
			.locator('input[type="checkbox"]');

		await expect(horizon).toBeVisible({ timeout: 10_000 });
		await expect(hourlyToggle).toBeChecked();

		await horizon.selectOption('24');
		await topN.fill('7');
		await hourlyToggle.uncheck();

		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});

		const res = await page.request.get(`/api/compare/presets/${id}`);
		expect(res.ok()).toBeTruthy();
		const preset = await res.json();
		expect(preset.forecast_hours, 'Horizont muss auf 24 persistieren').toBe(24);
		expect(
			(preset.display_config ?? {}).top_n,
			'Top-N muss auf 7 persistieren'
		).toBe(7);
		expect(preset.hourly_enabled, 'Stundenverlauf-Toggle muss auf false persistieren').toBe(false);

		// Testdaten sauber: Ausgangswerte wiederherstellen und speichern.
		await horizon.selectOption('48');
		await topN.fill('3');
		await hourlyToggle.check();
		await page.locator('[data-testid="compare-editor-save"]').click();
		await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
			timeout: 10_000
		});
	});
});
