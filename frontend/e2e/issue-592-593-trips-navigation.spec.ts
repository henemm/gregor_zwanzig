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

const TRIP_ID = 'e2e-cockpit-test';
const TRIPS_PAGE = '/trips';

// ---------------------------------------------------------------------------
// AC-3: Mobile — Kartentipp navigiert direkt
// ---------------------------------------------------------------------------

test.describe('#592 Mobile: Kartentipp navigiert zu Detail', () => {
	test.use({ viewport: { width: 390, height: 844 } });

	// Issue #2278: die Karte ist die geteilte SubscriptionCard; ihr Tipp navigiert direkt.
	// (AC-3b/AC-5 waren Quelltext-Pruefungen des entfallenen trip-card-content-btn — abgeloest.)
	test('AC-3: Tipp auf die Trip-Karte navigiert zu /trips/{id}', async ({ page }) => {
		await page.goto(TRIPS_PAGE);
		const karte = page.locator('[data-testid^="subscription-card-"][data-kind="trip"]').first();
		await expect(karte).toBeVisible();

		await karte.click({ position: { x: 24, y: 24 } });

		// Muss direkt auf Detail-Seite navigieren
		await expect(page).toHaveURL(new RegExp('/trips/[a-z0-9-]+$'));
		// KEIN Expansion-Block sichtbar nach Klick
		await expect(page.locator('[data-testid="trip-card-stack"] .border-t')).not.toBeVisible();
	});
});

// ---------------------------------------------------------------------------
// AC-4: Mobile — Action-Sheet enthält "Briefing senden"
// ---------------------------------------------------------------------------

test.describe('#592 Mobile: Action-Sheet mit Briefing-senden', () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test('AC-4: Action-Sheet enthält "Senden" und es öffnet den Sende-Dialog (nicht nur die Vorschau)', async ({ page }) => {
		await page.goto(TRIPS_PAGE);
		const menuBtn = page.locator('[data-testid^="subscription-card-menu-"]').first();
		await expect(menuBtn).toBeVisible();
		await menuBtn.click();

		const senden = page.getByTestId('subscription-action-send');
		await expect(senden).toHaveText('Senden');
		await senden.click();
		// Issue #2278 (AC-14): "Senden" im Blatt öffnet den Sende-Dialog, statt nur ?tab=vorschau zu öffnen.
		await expect(page.getByTestId('send-confirm-dialog')).toBeVisible();
		await expect(page).not.toHaveURL(/tab=vorschau/);
	});
});

// ---------------------------------------------------------------------------
// Issue #2278 AC-13: Breadcrumb "Trips" im Trip-Hub ist ein Link auf die Liste
// ---------------------------------------------------------------------------

test.describe('#2278 Trip-Hub: Breadcrumb "Trips" fuehrt zur Liste', () => {
	test.use({ viewport: { width: 1280, height: 800 } });

	test('AC-13: Klick auf "Trips" im Breadcrumb navigiert zu /trips', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const bar = page.getByTestId('trip-detail-breadcrumb-bar');
		await expect(bar).toBeVisible();
		await bar.getByRole('link', { name: 'Trips', exact: true }).click();
		await expect(page).toHaveURL(/\/trips\/?$/);
	});
});
