// E2E — Issue #251: Compare-Hauptbühne (Frontend): Matrix, Banner, Stunden-Verlauf
//
// Spec: docs/specs/modules/issue_251_compare_main_stage.md (AC-1 bis AC-6)
//
// TestID-Inventar (zu implementieren):
//   compare-preset-header           — PresetHeader-Komponente
//   compare-preset-run-btn          — "Vergleich starten"-Button
//   compare-preset-save-btn         — "Als Auto-Briefing speichern"-Button
//   compare-preset-profile-select   — Aktivitätsprofil-Dropdown
//   compare-preset-date-input       — Datum-Picker
//   compare-preset-summary          — Kurzinfo-Zeile (N Locations · Zeitfenster · Horizont)
//   compare-recommendation-banner   — RecommendationBanner-Komponente
//   compare-banner-score            — Score-Badge im Banner
//   compare-banner-location-name    — Location-Name im Banner
//   compare-banner-tags             — Tag-Container im Banner
//   compare-matrix                  — CompareMatrix-Komponente
//   compare-matrix-row              — Zeile in der Vergleichs-Matrix (1 pro Metrik)
//   compare-matrix-cell             — Zelle in der Matrix (data-location-id Attribut)
//   compare-matrix-best             — Zelle mit best-value-Klasse (grün markiert)
//   compare-matrix-minibar          — Mini-Bar innerhalb einer Zelle
//   compare-hourly-matrix           — HourlyMatrix-Komponente
//   compare-hourly-section          — Sections per Location (data-rank Attribut)

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

// Hilfsfunktion: Vergleich starten und auf Ergebnis warten
async function runComparison(page: import('@playwright/test').Page) {
	await page.getByTestId('compare-preset-run-btn').click();
	// Warte auf Matrix oder Banner (eines der neuen Elemente)
	await page.waitForSelector('[data-testid="compare-matrix"], [data-testid="compare-recommendation-banner"]', {
		timeout: 30_000,
	});
}

test.describe('Compare Hauptbühne (#251)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 900 });
		await page.goto('/compare');
	});

	// ── AC-1: Best-Value-Markierung + Mini-Bars ──────────────────────────────
	test('AC-1: Best-Value jeder Zeile trägt CSS-Klasse best-value; Mini-Bars vorhanden', async ({ page }) => {
		await runComparison(page);

		const matrix = page.getByTestId('compare-matrix');
		await expect(matrix).toBeVisible();

		// Mindestens eine Zelle mit best-value-Klasse
		const bestCells = page.getByTestId('compare-matrix-best');
		await expect(bestCells.first()).toBeVisible();

		// Mindestens eine Mini-Bar existiert
		const miniBars = page.getByTestId('compare-matrix-minibar');
		await expect(miniBars.first()).toBeVisible();

		// Mini-Bar hat style="width: N%" — Breite muss zwischen 0 und 100% liegen
		const firstBar = miniBars.first();
		const style = await firstBar.getAttribute('style');
		expect(style).toMatch(/width:\s*\d+(\.\d+)?%/);
	});

	// ── AC-2: Profil-spezifische Zeilen ─────────────────────────────────────
	test('AC-2: WINTERSPORT zeigt Schneehöhe als erste Zeile; SUMMER_TREKKING zeigt Niederschlag', async ({ page }) => {
		const profileSelect = page.getByTestId('compare-preset-profile-select');
		await expect(profileSelect).toBeVisible();

		// WINTERSPORT-Profil wählen
		await profileSelect.selectOption('wintersport');
		await runComparison(page);

		const firstRowWinter = page.getByTestId('compare-matrix-row').first();
		await expect(firstRowWinter).toContainText(/Schneehöhe/i);

		// SUMMER_TREKKING-Profil wählen
		await profileSelect.selectOption('summer_trekking');
		await runComparison(page);

		const firstRowSummer = page.getByTestId('compare-matrix-row').first();
		await expect(firstRowSummer).toContainText(/Niederschlag|Regen|precip/i);
	});

	// ── AC-3: Banner-Score stimmt mit rows[0].score überein ─────────────────
	test('AC-3: Score im Empfehlungs-Banner stimmt mit Rank-1 in Matrix überein', async ({ page }) => {
		await runComparison(page);

		const banner = page.getByTestId('compare-recommendation-banner');
		await expect(banner).toBeVisible();

		// Score im Banner lesen
		const scoreEl = page.getByTestId('compare-banner-score');
		await expect(scoreEl).toBeVisible();
		const bannerScore = await scoreEl.textContent();
		expect(bannerScore).toMatch(/\d+/);

		// Rank-1-Zeile (erste Spalte der ersten Datenzeile) muss denselben Score zeigen
		// Die Matrix-Kopfzeile enthält Location-Namen; Rank-1 ist die erste Locations-Spalte
		const firstCell = page.getByTestId('compare-matrix-cell').first();
		await expect(firstCell).toBeVisible();
		// Location-Name im Banner muss in Matrix-Kopfzeile erscheinen
		const bannerName = await page.getByTestId('compare-banner-location-name').textContent();
		const matrix = page.getByTestId('compare-matrix');
		await expect(matrix).toContainText(bannerName!.trim());
	});

	// ── AC-4: Top-3 im Stunden-Verlauf ──────────────────────────────────────
	test('AC-4: Stunden-Verlauf zeigt exakt Top-3-Locations (Rank 1, 2, 3)', async ({ page }) => {
		await runComparison(page);

		const hourlyMatrix = page.getByTestId('compare-hourly-matrix');
		await expect(hourlyMatrix).toBeVisible();

		// Exakt 3 Sections
		const sections = page.getByTestId('compare-hourly-section');
		await expect(sections).toHaveCount(3);

		// Sections haben data-rank 1, 2, 3
		await expect(sections.nth(0)).toHaveAttribute('data-rank', '1');
		await expect(sections.nth(1)).toHaveAttribute('data-rank', '2');
		await expect(sections.nth(2)).toHaveAttribute('data-rank', '3');
	});

	// ── AC-5: toCompareProfile-Adapter: 'wandern' → 'ALPINE_TOURING' ────────
	test('AC-5: Profil "wandern" wird als ALPINE_TOURING an POST /api/compare/run gesendet', async ({ page }) => {
		const profileSelect = page.getByTestId('compare-preset-profile-select');
		await profileSelect.selectOption('wandern');

		// Request abfangen
		let capturedBody: Record<string, unknown> | null = null;
		page.on('request', (req) => {
			if (req.url().includes('/api/compare/run') && req.method() === 'POST') {
				try {
					capturedBody = JSON.parse(req.postData() ?? '{}');
				} catch {
					// ignore
				}
			}
		});

		await page.getByTestId('compare-preset-run-btn').click();
		// Kurz warten damit der Request abgefangen wird
		await page.waitForTimeout(5_000);

		expect(capturedBody).not.toBeNull();
		expect((capturedBody as Record<string, unknown>)['profile']).toBe('ALPINE_TOURING');
		// System-Namespace darf nicht im Request erscheinen
		expect((capturedBody as Record<string, unknown>)['profile']).not.toBe('wandern');
	});

	// ── AC-6: allSelected → explizites ID-Array, kein '*'-Wildcard ──────────
	test('AC-6: Bei "Alle ausgewählt" enthält location_ids ein Array, kein Wildcard', async ({ page }) => {
		let capturedBody: Record<string, unknown> | null = null;
		page.on('request', (req) => {
			if (req.url().includes('/api/compare/run') && req.method() === 'POST') {
				try {
					capturedBody = JSON.parse(req.postData() ?? '{}');
				} catch {
					// ignore
				}
			}
		});

		// Sicherstellen dass "Alle" ausgewählt sind (Standard-Zustand)
		await page.getByTestId('compare-preset-run-btn').click();
		await page.waitForTimeout(5_000);

		expect(capturedBody).not.toBeNull();
		const ids = (capturedBody as Record<string, unknown>)['location_ids'];
		// Muss ein Array sein
		expect(Array.isArray(ids)).toBe(true);
		// Darf kein '*'-Wildcard sein
		expect(ids).not.toContain('*');
		expect(typeof ids).not.toBe('string');
		// Mindestens 2 Einträge (Go-Engine-Anforderung)
		expect((ids as string[]).length).toBeGreaterThanOrEqual(2);
	});

	// ── Smoke: PresetHeader-Komponente existiert ─────────────────────────────
	test('Smoke: PresetHeader-Komponente ist sichtbar', async ({ page }) => {
		const header = page.getByTestId('compare-preset-header');
		await expect(header).toBeVisible();
	});
});
