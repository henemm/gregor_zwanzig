// E2E — Epic #1301 Scheibe F2a: /compare/new Aktivieren-Gate + Create-POST.
//
// Spec: docs/specs/modules/feat_1301_f2a_compare_new_trip_pattern.md § AC-8/AC-9/AC-11
//
// Vormals Issue #681 „Slice 4 Layout + Versand Fidelity" — die Layout-Fidelity-
// Tests (channel-tab-*/compare-step4-layout-preview/SMS-Budget/Detail-Pill/
// channel_layouts-POST) prüften die channel_layouts-ATTRAPPE, die vom
// Compare-Renderpfad NIE gelesen wurde (#1301-Grundbefund) und in F2a ersatzlos
// entfällt. Diese Blöcke sind gelöscht. Erhalten bleibt, was echte Funktion prüft:
// das „Briefing aktivieren"-Gate (disabled bis Versand besucht) und der echte
// Create-POST auf /api/compare/presets.
//
// Ausführen:
//   cd frontend && npx playwright test e2e/compare-editor-slice4.spec.ts --config playwright.config.ts

import { test, expect, type Page } from '@playwright/test';
import { login, createTestLocation } from './helpers.js';

// #1329 Maßnahme B: zentralisiert über den geteilten Helfer (helpers.ts) —
// diese Datei hatte zuvor GAR kein Cleanup (garantierter Leak, Kontext-Dok.).
async function makeTwoLocations(page: Page): Promise<[string, string]> {
	const locA = await createTestLocation(page.request, { lat: 47.2, lon: 12.3 });
	const locB = await createTestLocation(page.request, { lat: 47.3, lon: 12.4 });
	return [locA.name, locB.name];
}

test.describe('F2a: /compare/new Aktivieren-Gate + Create-POST', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// ── AC-8: „Briefing aktivieren" disabled bis Versand-Tab besucht ───────────
	test('AC-8: "Briefing aktivieren" ist disabled bis Versand-Tab besucht', async ({ page }) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');

		const activateBtn = page.locator('[data-testid="compare-editor-activate"]');
		await expect(activateBtn).toBeVisible({ timeout: 8_000 });

		const isDisabled =
			(await activateBtn.getAttribute('disabled')) !== null ||
			(await activateBtn.getAttribute('aria-disabled')) === 'true';
		expect(isDisabled, 'Button muss initial disabled sein').toBeTruthy();

		const hint = page
			.locator('[data-testid="compare-editor"]')
			.getByText('Versand einrichten zum Aktivieren');
		await expect(hint).toBeVisible();
	});

	// ── AC-8: Aktivieren-Button existiert im Create-Modus ──────────────────────
	test('AC-8: "Briefing aktivieren" ist im Create-Wizard vorhanden', async ({ page }) => {
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-name"]').fill('Slice4-Aktivierung ' + Date.now());
		await expect(page.locator('[data-testid="compare-editor-activate"]')).toBeVisible({ timeout: 8_000 });
	});

	// ── AC-9: Vollständiger Anlege-Flow mit echter Auswahl → EIN POST + Roundtrip ──
	// F001-Härtung (Adversary): der Test trifft im Flow echte Auswahlen (Wetter-
	// Metrik umschalten, Wertebereiche via Profil-Prefill, Stundenverlauf-Metrik
	// setzen) und weist danach nach, dass der POST-Body vollständig ist
	// (display_config.active_metrics + corridors + display_config.hourly_metrics)
	// UND dass die Werte nach dem Redirect im gespeicherten Preset stehen
	// (GET-Roundtrip = Hub-Wahrheit, kein Wert geht auf dem Weg verloren).
	test('AC-9: Aktivieren sendet die vollständige Auswahl und persistiert sie (Roundtrip)', async ({
		page
	}) => {
		const [nameA, nameB] = await makeTwoLocations(page);
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();

		const vergleichName = 'Slice4-Flow ' + Date.now();
		await page.locator('[data-testid="compare-editor-name"]').fill(vergleichName);
		await page.locator('[data-testid="compare-editor-profile-wintersport"]:visible').first().click();

		// Orte
		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 8_000 });
		for (const n of [nameA, nameB]) {
			await lib.getByText(n, { exact: true }).click();
		}

		// Wetter-Metriken: eine Metrik aktiv umschalten (verändert active_metrics).
		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').first().click();
		const metricRow = page
			.locator('.cm-desktop [data-testid^="weather-metrics-vergleich-row-"] input')
			.first();
		await expect(metricRow).toBeVisible({ timeout: 10_000 });
		await metricRow.click();

		// Wertebereiche: Profil-Prefill (isFreshCompareCreate) befüllt corridors +
		// activeMetricKeys beim Öffnen (Besuch genügt, echter Klickpfad).
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
		await expect(
			page.locator('[data-testid="corridor-editor-vergleich"]:visible').first()
		).toBeVisible({ timeout: 8_000 });

		// Layout: eine Stundenverlauf-Metrik umschalten (setzt hourly_metrics).
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').first().click();
		const hourlyToggle = page
			.locator('.cm-desktop [data-testid="compare-layout-hourly-metric-temp_c"] input')
			.first();
		await expect(hourlyToggle).toBeVisible({ timeout: 8_000 });
		await hourlyToggle.click();

		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();

		// Genau EIN POST; Response liefert die neue Preset-ID für den Roundtrip.
		const [response] = await Promise.all([
			page.waitForResponse(
				(res) =>
					res.url().includes('/api/compare/presets') && res.request().method() === 'POST'
			),
			page.locator('[data-testid="compare-editor-activate"]:visible').first().click()
		]);
		const body = response.request().postDataJSON() as Record<string, any>;
		expect(body.name, 'POST-Body trägt den Vergleichsnamen').toBe(vergleichName);
		expect(
			Array.isArray(body.location_ids) && body.location_ids.length === 2,
			'POST-Body trägt genau die 2 gewählten Orte'
		).toBeTruthy();
		const dc = (body.display_config ?? {}) as Record<string, any>;
		expect(
			Array.isArray(dc.active_metrics) && dc.active_metrics.length >= 1,
			`display_config.active_metrics fehlt/leer im POST: ${JSON.stringify(dc.active_metrics)}`
		).toBeTruthy();
		expect(
			Array.isArray(dc.hourly_metrics) && dc.hourly_metrics.length >= 1,
			`display_config.hourly_metrics fehlt/leer im POST: ${JSON.stringify(dc.hourly_metrics)}`
		).toBeTruthy();
		expect(
			Array.isArray(body.corridors) && body.corridors.length >= 1,
			`corridors fehlt/leer im POST: ${JSON.stringify(body.corridors)}`
		).toBeTruthy();

		// Roundtrip: der neu erzeugte Vergleich trägt die gesetzten Werte (Hub-Wahrheit).
		const created = (await response.json()) as { id: string };
		const getRes = await page.request.get(`/api/compare/presets/${created.id}`);
		expect(getRes.ok(), 'GET des neuen Presets fehlgeschlagen').toBeTruthy();
		const preset = (await getRes.json()) as Record<string, any>;
		const pdc = (preset.display_config ?? {}) as Record<string, any>;
		expect(pdc.active_metrics, 'active_metrics persistiert (Roundtrip)').toEqual(dc.active_metrics);
		expect(pdc.hourly_metrics, 'hourly_metrics persistiert (Roundtrip)').toEqual(dc.hourly_metrics);
		expect(
			Array.isArray(preset.corridors) && preset.corridors.length >= 1,
			'corridors persistiert (Roundtrip)'
		).toBeTruthy();

		// Staging-Hygiene: das im Test angelegte Preset wieder abräumen.
		await page.request.delete(`/api/compare/presets/${created.id}`).catch(() => {});
	});

	// ── AC-9b (Staging-Fund #1301 F2a): Doppelklick → genau EIN Create-POST ─────
	// Re-Entrancy-Guard: ein schneller Doppelklick auf „Briefing aktivieren" darf
	// NUR ein Preset anlegen (vorher: 2× POST = Duplikat-Karteileiche, 3/3 repro).
	test('AC-9b: Doppelklick auf „Briefing aktivieren" löst genau EINEN POST aus', async ({ page }) => {
		const [nameA, nameB] = await makeTwoLocations(page);
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible();
		await page.locator('[data-testid="compare-editor-name"]').fill('Slice4-Dbl ' + Date.now());
		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 8_000 });
		for (const n of [nameA, nameB]) {
			await lib.getByText(n, { exact: true }).click();
		}
		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-alarme"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-versand"]:visible').first().click();

		// Alle Create-POSTs mitzählen (nicht nur den ersten abwarten).
		let postCount = 0;
		page.on('request', (req) => {
			if (req.url().includes('/api/compare/presets') && req.method() === 'POST') postCount++;
		});
		const respPromise = page.waitForResponse(
			(res) => res.url().includes('/api/compare/presets') && res.request().method() === 'POST'
		);

		// Schneller Doppelklick — der Guard muss den zweiten POST verhindern.
		await page.locator('[data-testid="compare-editor-activate"]:visible').first().dblclick();
		const resp = await respPromise;
		const created = (await resp.json()) as { id: string };

		// Zeitfenster für einen etwaigen (unerwünschten) zweiten POST offen lassen.
		await page.waitForTimeout(2_000);
		expect(postCount, `Doppelklick löste ${postCount} POST(s) aus, erwartet genau 1`).toBe(1);

		await page.request.delete(`/api/compare/presets/${created.id}`).catch(() => {});
	});

	// ── AC-11: keine Layout-Attrappe (channel-tab/preview) auf dem Layout-Tab ───
	test('AC-11: Layout-Tab zeigt keine channel_layouts-Attrappe mehr', async ({ page }) => {
		const [nameA, nameB] = await makeTwoLocations(page);
		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await page.locator('[data-testid="compare-editor-name"]').fill('Slice4-NoAttrappe ' + Date.now());
		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 8_000 });
		for (const n of [nameA, nameB]) {
			await lib.getByText(n, { exact: true }).click();
		}
		await page.locator('[data-testid="compare-editor-tab-metriken"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-idealwerte"]:visible').first().click();
		await page.locator('[data-testid="compare-editor-tab-layout"]:visible').first().click();

		await expect(
			page.locator('[data-testid="compare-layout-hourly-enabled-toggle"]:visible').first()
		).toBeVisible({ timeout: 8_000 });
		await expect(page.locator('[data-testid="channel-tab-email"]')).toHaveCount(0);
		await expect(page.locator('[data-testid="compare-step4-layout-preview"]')).toHaveCount(0);
	});
});
