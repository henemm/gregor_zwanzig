// gz-eigenstaendig: Stundenverlauf-Steuerung existiert nur im Ortsvergleich (COMPARE_ONLY_SECTIONS in weatherMetricsTabSections.ts, #2346 S3: beim Trip ist die Mail-Haupttabelle selbst die Stundentabelle); zusaetzlich Anlege-Seite /compare/new des Alt-Editors
// E2E (Staging) — Reihenfolge der Stundenverlauf-Metriken im Ortsvergleich,
// Issue #1361 Befund 4/5 (S1-Rest von Epic #1372).
//
// Spec: Auftrag "S1-Rest #1361 umsetzen" (kein eigenes Spec-Dokument -- direkte
// Team-Lead-Vorgabe, siehe AC-1..AC-5 dort).
//
// Warum Live-Schicht: die Karte „Was steht wo“ und die Anlege-Seite lassen sich nur
// im echten Browser gegen den echten Server nachweisen. Die frühere eigene
// Stundenverlauf-Liste des Vergleichs ist seit #3276 entfernt.
//
// AC-3 → Hub (seit #3154 Karte „Was steht wo“, AC-1/AC-2 gestrichen, s. unten). AC-4 → Anlege-Seite (`/compare/new`), seit #3276 Negativ-Zusicherung. AC-5 (keine
// Regression der An/Aus-Auswahl) ist bereits durch
// hub-wetter-metriken-speichert-selbst.spec.ts MS-2 + compare-stundenverlauf-wertprops.spec.ts
// abgedeckt (Toggle + PUT; vormals compare-layout-tab-dissolution AC-2, #2347 S4) — hier
// nur eine Gegenprobe, dass Ziehen UND Toggle nebeneinander funktionieren.
//
// AC-3 KORRIGIERT (Team-Lead-Gegencheck): KEINE Schnittlinie, da der
// Stundenverlauf laut Backend ausschließlich in der E-Mail erscheint
// (die Stellen-Spalte „Stundenverlauf“ der Tabelle wirkt nur in `render_compare_email`;
// `render_compare_telegram`, :360, hat keinen Stundendaten-Bezug; SMS hat
// `max_table_cols: 0`). Eine Telegram-Kappungslinie wäre eine Falschaussage —
// exakt die mit #1360 AC-4 beseitigte Fehlerklasse. Getestet wird stattdessen:
// Linie fehlt, der wahre Hinweis "nur E-Mail" ist da, keine der in
// compare-layout-tab-dissolution.spec.ts (FORBIDDEN_CLAIMS) verbotenen
// Kappungs-Formulierungen taucht auf.
//
// ── Ausführen (gegen STAGING, aus frontend/, NACH Push + Staging-Deploy) ────
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   npx playwright test --config=playwright.compare-hourly-metric-order.staging.config.ts
//
// Config `frontend/playwright.compare-hourly-metric-order.staging.config.ts`
// liegt daneben (1:1 nach playwright.compare-layout-tab-dissolution.staging.config.ts).
// Anmeldung über gespeicherten Sitzungszustand (storageState), NICHT per
// Test-Login (Token-Bucket 30/h, reference_staging_e2e_storagestate_login_rate_limit).
// #3276: die Vergleichs-Fläche `weather-metrics-stundenverlauf` ist entfernt (AC-4 prüft ihr Fehlen).

import { test, expect, type Page } from '@playwright/test';
import { createTestLocation } from './helpers';
import { oeffneKarte } from './was-steht-wo.helpers';

let createdPresetIds: string[] = [];
let createdLocationIds: string[] = [];

test.afterEach(async ({ page }) => {
	for (const id of createdPresetIds) {
		try {
			await page.request.delete(`/api/compare/presets/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdPresetIds = [];
	for (const id of createdLocationIds) {
		try {
			await page.request.delete(`/api/locations/${id}`);
		} catch {
			/* Staging-Hygiene: Cleanup-Fehler ist nicht test-kritisch */
		}
	}
	createdLocationIds = [];
});

// #3359: die frühere Saat einer eigenen Stundenverlauf-Reihenfolge ist entfallen (Altfeld ohne Wirkung
// seit #3277); die Stellen-Spalte „Stundenverlauf“ kommt aus der Tabelle der Grundauswahl.

async function createLocation(page: Page, name: string, lat: number, lon: number): Promise<string> {
	const loc = await createTestLocation(page.request, { name, lat, lon });
	createdLocationIds.push(loc.id);
	return loc.id;
}

async function createPreset(page: Page, name: string, locationIds: string[]): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name,
			location_ids: locationIds,
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			display_config: { active_metrics: ['temp_max_c', 'wind_max_kmh', 'sunny_hours_h'] }
		}
	});
	expect(res.ok(), 'Preset-Anlage fehlgeschlagen: ' + res.status()).toBeTruthy();
	const body = await res.json();
	createdPresetIds.push(body.id);
	return body.id as string;
}

test.describe('Issue #1361 Befund 4/5: Reihenfolge des Stundenverlaufs im Ortsvergleich', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): im Hub gibt es keine eigene
	// Stundenverlauf-Liste mehr. AC-1/AC-2 (Ziehen im Hub speichert die Stundenverlauf-Reihenfolge) sind
	// gestrichen — es gibt EINE Reihenfolge fuer alle Stellen der Karte „Was steht wo“, Ersatz:
	// was-steht-wo-karte.spec.ts WS-2 (Tastatur und Maus, drei Faelle inkl. Orte, Neuladen). AC-3 laeuft an der
	// Karte: die Spalte und der Schalter „Stundenverlauf“ behaupten keine Kanal-Kappung, nur „nur in der E-Mail“.
	const FORBIDDEN_CHANNEL_CLAIMS: RegExp[] = [
		/Telegram\s*·\s*max\s*\d+/i,
		/kappt\s+je\s+Kanal/i,
		/Spalten\s+pro\s+Kanal/i,
		/Übersicht\s+pro\s+Kanal/i,
		/max\.?\s*\d+\s*(Orte|Spalten)/i
	];

	test('AC-3: der Stundenverlauf (Karte im Reiter Wetter) behauptet KEINE Kappung, sondern „nur in der E-Mail“', async ({
		page
	}) => {
		const suffix = Date.now();
		const locA = await createLocation(page, `E2E 1361 CutLine A ${suffix}`, 47.3, 11.3);
		const locB = await createLocation(page, `E2E 1361 CutLine B ${suffix}`, 47.4, 11.4);
		const id = await createPreset(page, `E2E 1361 CutLine ${suffix}`, [locA, locB]);

		const karte = await oeffneKarte(page, 'vergleich', id);
		await expect(karte.locator('[data-slot="et-kopf-stelle"][data-stelle="hourly"]'), 'Spalte Stundenverlauf fehlt').toHaveCount(1);
		await expect(karte, 'AC-3: sichtbarer, wahrer Hinweis, dass der Block nur die E-Mail betrifft').toContainText(/Stunden-Tabelle je Ort unter der Übersicht, nur in der E-Mail/);
		await expect(karte.locator('[data-testid="wm2-cut-line"]'), 'AC-3: keine Schnittlinie').toHaveCount(0);
		const text = await karte.innerText();
		for (const claim of FORBIDDEN_CHANNEL_CLAIMS) {
			expect(text, `AC-3: die Karte darf keine Kanal-Kappungs-Aussage behaupten (${claim})`).not.toMatch(claim);
		}
	});

	// ── AC-4: Anlege-Seite ────────────────────────────────────────────────────
	// #3276 (Spec feat_3276_vergleich_altfelder_entfernen.md AC-3/AC-6): die eigene Stundenverlauf-Liste
	// der Anlege-Seite ist entfernt; Reihenfolge und Stellen stehen nur noch in der Karte „Was steht wo“
	// (Ersatz: was-steht-wo-karte.spec.ts WS-2). Die frühere Ziehgesten-Zusicherung wird zur Negativ-Zusicherung.
	test('AC-4 (#3276): auf /compare/new gibt es keine eigene Stundenverlauf-Liste mehr', async ({ page }) => {
		const suffix = Date.now();
		const locA = await createTestLocation(page.request, { name: `E2E 1361 New A ${suffix}`, lat: 47.5, lon: 11.5 });
		createdLocationIds.push(locA.id);
		const locB = await createTestLocation(page.request, { name: `E2E 1361 New B ${suffix}`, lat: 47.6, lon: 11.6 });
		createdLocationIds.push(locB.id);

		await page.goto('/compare/new');
		await page.waitForLoadState('networkidle');
		await expect(page.locator('[data-testid="compare-editor"]:visible').first()).toBeVisible({ timeout: 15_000 });
		await page.locator('[data-testid="compare-editor-name"]:visible').first().fill(`E2E 1361 New ${suffix}`);
		await page.locator('[data-testid="compare-editor-tab-orte"]:visible').first().click();
		const lib = page.locator('[data-testid="compare-step2-library"]:visible').first();
		await lib.waitFor({ timeout: 10_000 });
		for (const n of [locA.name, locB.name]) {
			await lib.getByText(n, { exact: true }).click();
		}
		await page.locator('[data-testid="compare-editor-tab-wetter"]:visible').first().click();
		const zustellung = page.locator('[data-testid="compare-editor-tab-zustellung"]:visible').first();
		await zustellung.click();
		await expect(zustellung).toHaveAttribute('data-active', 'true', { timeout: 10_000 });
		await expect(page.locator('[data-testid="weather-metrics-stundenverlauf"]'), 'AC-4: alte Stundenverlauf-Liste im Vergleich').toHaveCount(0);
		await expect(page.locator('[data-testid="compare-layout-hourly-metrics"]'), 'AC-4: alte Stundenverlauf-Auswahl im Vergleich').toHaveCount(0);
	});
});
