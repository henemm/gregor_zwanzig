// TDD RED: Bug #283 — Trip-Editor Wegpunkte als Tabelle mit Mono-Koordinaten
//
// Spec: docs/specs/modules/bug_283_editor_waypoint_table.md
// Phase 5 (TDD RED) — Tests MÜSSEN FEHLSCHLAGEN bis Phase 6.
//
// AC-1: Desktop-Kopfzeile (Name/Lat/Lon/Höhe) in Uppercase-Mono
// AC-2: Lat/Lon-Inputs mit JetBrains Mono + tabular-nums + rechts ausgerichtet
// AC-3: Höhen-Input mit faint "m"-Suffix
// AC-4: Datum-Input mit g-num-input-Klasse
// AC-5: AccordionSection mit --g-surface-2 + ChevronDown-Icon
// AC-6: Regression — alle bestehenden Testids bleiben gültig

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
const EDIT_URL = `/trips/${TRIP_ID}/edit`;

async function ensureEtappenOpen(page: import('@playwright/test').Page) {
	// Etappen ist Default-offen; nur klicken wenn geschlossen
	const section = page.getByTestId('edit-section-etappen');
	const header = page.getByTestId('edit-section-etappen-header');
	await expect(header).toBeVisible();
	const cls = await section.getAttribute('class') ?? '';
	if (!cls.includes('shadow-sm') && !cls.includes('border-primary')) {
		await header.click();
		await page.waitForTimeout(200);
	}
}

// =============================================================================
// AC-1: Kopfzeile mit Spaltenbezeichnungen (Desktop)
// =============================================================================

test('AC-1: Wegpunkt-Tabelle hat Kopfzeile mit Name/Lat/Lon/Höhe', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	// Kopfzeile muss Spaltenbezeichnungen enthalten — scheitert weil .g-th noch nicht existiert
	const header = page.locator('.g-th').first();
	await expect(header).toBeVisible();

	// Konkrete Spaltentitel prüfen
	const allHeaders = page.locator('.g-th');
	const texts = await allHeaders.allTextContents();
	const normalized = texts.map(t => t.toUpperCase().trim());
	expect(normalized).toContain('NAME');
	expect(normalized).toContain('LAT');
	expect(normalized).toContain('LON');
});

// =============================================================================
// AC-2: Lat/Lon-Inputs in JetBrains Mono mit tabular-nums
// =============================================================================

test('AC-2: Lat/Lon-Inputs haben Klasse g-num-input und sind rechtsbündig', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	const latInput = page.getByTestId('wp-lat').first();
	await expect(latInput).toBeVisible();

	// Klasse g-num-input muss vorhanden sein — scheitert weil noch nicht implementiert
	await expect(latInput).toHaveClass(/g-num-input/);

	const lonInput = page.getByTestId('wp-lon').first();
	await expect(lonInput).toHaveClass(/g-num-input/);

	// Rechtsbündig prüfen
	await expect(latInput).toHaveClass(/text-right/);
	await expect(lonInput).toHaveClass(/text-right/);
});

// =============================================================================
// AC-3: Höhen-Input mit "m"-Suffix
// =============================================================================

test('AC-3: Höhen-Eingabefeld zeigt "m"-Einheitssuffix', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	const eleInput = page.getByTestId('wp-ele').first();
	await expect(eleInput).toBeVisible();

	// "m"-Suffix als Geschwister-Element neben dem Input — scheitert weil noch nicht implementiert
	const unitSuffix = eleInput.locator('..').locator('span').filter({ hasText: 'm' });
	await expect(unitSuffix).toBeVisible();
});

// =============================================================================
// AC-4: Datum-Input mit g-num-input-Klasse
// =============================================================================

test('AC-4: Stage-Datum-Input hat Klasse g-num-input', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	// Datum-Input einer Stage — scheitert weil g-num-input noch nicht ergänzt
	const dateInput = page.locator('input[type="date"]').first();
	await expect(dateInput).toBeVisible();
	await expect(dateInput).toHaveClass(/g-num-input/);
});

// =============================================================================
// AC-5: AccordionSection nutzt Design-Token + ChevronDown-Icon
// =============================================================================

test('AC-5: Accordion-Header zeigt ChevronDown-SVG statt ASCII +/-', async ({ page }) => {
	await page.goto(EDIT_URL);

	const routeHeader = page.getByTestId('edit-section-route-header');
	await expect(routeHeader).toBeVisible();

	// ASCII +/- darf NICHT mehr vorhanden sein — scheitert weil noch nicht implementiert
	const headerText = await routeHeader.textContent();
	expect(headerText).not.toContain('+');
	expect(headerText).not.toContain('−');

	// SVG-Icon (ChevronDown) muss vorhanden sein
	const chevron = routeHeader.locator('svg');
	await expect(chevron).toBeVisible();
});

test('AC-5b: Accordion-Header nutzt var(--g-surface-2) als Hintergrund', async ({ page }) => {
	await page.goto(EDIT_URL);

	const routeHeader = page.getByTestId('edit-section-route-header');
	await expect(routeHeader).toBeVisible();

	// bg-primary/10 und text-primary dürfen nicht mehr für offene Sektionen gelten
	// Etappen ist standardmäßig offen → prüfen ob primary-Klassen weg sind
	const etappenHeader = page.getByTestId('edit-section-etappen-header');
	await expect(etappenHeader).not.toHaveClass(/text-primary/);
	await expect(etappenHeader).not.toHaveClass(/bg-primary/);
});

// =============================================================================
// AC-6: Regression — bestehende Testids unverändert
// =============================================================================

test('AC-6: Alle bestehenden Wegpunkt-Testids funktionieren weiterhin', async ({ page }) => {
	await page.goto(EDIT_URL);
	await ensureEtappenOpen(page);

	// Diese Testids MÜSSEN weiterhin vorhanden sein
	await expect(page.getByTestId('stage-card-0')).toBeVisible();
	await expect(page.getByTestId('waypoint-0').first()).toBeVisible();
	await expect(page.getByTestId('wp-name').first()).toBeVisible();
	await expect(page.getByTestId('wp-lat').first()).toBeVisible();
	await expect(page.getByTestId('wp-lon').first()).toBeVisible();
	await expect(page.getByTestId('wp-ele').first()).toBeVisible();
});
