// TDD RED: Issue #592 + #593 — Trips-Liste Navigation
//
// Spec: docs/specs/modules/bug_592_593_trips_navigation.md
//
// #592 (critical): Mobile-Kartentipp muss direkt zur Detailseite navigieren
// #593 (high): Desktop-Tabellenzeile muss vollständig klickbar sein
//
// RED-Phase: Diese Tests scheitern, weil:
//   #593: <tr> hat kein onclick → Klick auf Zeile (außerhalb Name-Link) tut nichts
//   #592: trip-card-content-btn expandiert nur, navigiert nicht
//   #592: Action-Sheet fehlt "Briefing senden"

import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';

const TRIP_ID = 'e2e-cockpit-test';
const TRIPS_PAGE = '/trips';

// ---------------------------------------------------------------------------
// AC-1 + AC-2: Desktop — Zeile klickbar, Aktions-Buttons propagieren nicht
// ---------------------------------------------------------------------------

test.describe('#593 Desktop: Trips-Zeile klickbar', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('AC-1: Klick auf Zeile (außerhalb Name) navigiert zu Trip-Detail', async ({ page }) => {
		await page.goto(TRIPS_PAGE);
		// Warte auf erste Tabellenzeile
		const row = page.locator('table tbody tr').first();
		await expect(row).toBeVisible();

		// Klick in die Mitte der Zeile, aber NICHT auf einen Link oder Button
		// (Zeitraum-Zelle hat keinen Link/Button)
		const dateCell = row.locator('td').nth(1);
		await expect(dateCell).toBeVisible();

		const href = await page.locator('table tbody tr a.trip-link').first().getAttribute('href');
		await dateCell.click();

		// Sollte auf Trip-Detail navigieren
		await expect(page).toHaveURL(new RegExp('/trips/[a-z0-9-]+$'));
	});

	test('AC-1b: Desktop-<tr> hat onclick direkt auf dem tr-Element', async () => {
		const content = readFileSync('/home/hem/gregor_zwanzig/frontend/src/routes/trips/+page.svelte', 'utf-8');
		// <tr>-Tag muss onclick direkt enthalten (innerhalb desselben Tags — kein DOTALL über Zeilen)
		expect(content).toMatch(/<tr[^>]*onclick[^>]*cursor-pointer/);
	});

	test('AC-2: Aktions-Cell im Desktop-<tr> hat stopPropagation', async () => {
		const content = readFileSync('/home/hem/gregor_zwanzig/frontend/src/routes/trips/+page.svelte', 'utf-8');
		const desktopBlock = content.slice(content.indexOf('hidden desktop:block'));
		const tbodyBlock = desktopBlock.slice(desktopBlock.indexOf('<tbody'), desktopBlock.indexOf('</tbody>'));
		// Aktions-Cell muss stopPropagation haben (für Buttons/Dropdown)
		expect(tbodyBlock).toContain('stopPropagation');
	});
});

// ---------------------------------------------------------------------------
// AC-3: Mobile — Kartentipp navigiert direkt
// ---------------------------------------------------------------------------

test.describe('#592 Mobile: Kartentipp navigiert zu Detail', () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test('AC-3: Tipp auf trip-card-content-btn navigiert zu /trips/{id}', async ({ page }) => {
		await page.goto(TRIPS_PAGE);
		const contentBtn = page.getByTestId('trip-card-content-btn').first();
		await expect(contentBtn).toBeVisible();

		await contentBtn.click();

		// Muss direkt auf Detail-Seite navigieren
		await expect(page).toHaveURL(new RegExp('/trips/[a-z0-9-]+$'));
		// KEIN Expansion-Block sichtbar nach Klick
		await expect(page.locator('[data-testid="trip-card-stack"] .border-t')).not.toBeVisible();
	});

	test('AC-3b: trip-card-content-btn hat goto-Navigation, kein expandedCardId-Toggle', async () => {
		const content = readFileSync('/home/hem/gregor_zwanzig/frontend/src/routes/trips/+page.svelte', 'utf-8');
		// content-btn darf expandedCardId NICHT mehr setzen
		const contentBtnBlock = content.match(/data-testid="trip-card-content-btn"[\s\S]*?(?=data-testid="trip-card-menu-btn")/)?.[0] ?? '';
		expect(contentBtnBlock).not.toContain('expandedCardId');
		// content-btn muss goto haben
		expect(contentBtnBlock).toContain('goto');
	});

	test('AC-5: expandedCardId-Toggle komplett aus trip-card-content-btn entfernt', async () => {
		const content = readFileSync('/home/hem/gregor_zwanzig/frontend/src/routes/trips/+page.svelte', 'utf-8');
		// expandedCardId darf nicht mehr im content-btn verwendet werden
		const contentBtnBlock = content.match(/data-testid="trip-card-content-btn"[\s\S]*?<\/button>/)?.[0] ?? '';
		expect(contentBtnBlock).not.toContain('expandedCardId');
	});
});

// ---------------------------------------------------------------------------
// AC-4: Mobile — Action-Sheet enthält "Briefing senden"
// ---------------------------------------------------------------------------

test.describe('#592 Mobile: Action-Sheet mit Briefing-senden', () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test('AC-4: Action-Sheet enthält "Briefing senden" nach EllipsisVertical-Tipp', async ({ page }) => {
		await page.goto(TRIPS_PAGE);
		const menuBtn = page.getByTestId('trip-card-menu-btn').first();
		await expect(menuBtn).toBeVisible();
		await menuBtn.click();

		const sheet = page.getByTestId('trip-action-sheet');
		await expect(sheet).toBeVisible();
		await expect(sheet).toContainText('Briefing senden');
	});

	test('AC-4b: Action-Sheet-Briefing navigiert zu ?tab=preview', async () => {
		const content = readFileSync('/home/hem/gregor_zwanzig/frontend/src/routes/trips/+page.svelte', 'utf-8');
		// Im Action-Sheet (sheetTrip) muss "Briefing senden" mit tab=preview-Route vorhanden sein
		const sheetBlock = content.match(/data-testid="trip-action-sheet"[\s\S]*/)?.[0] ?? '';
		expect(sheetBlock).toContain('Briefing senden');
		expect(sheetBlock).toContain('tab=preview');
	});
});
