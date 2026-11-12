// TDD: Issue #215 Sprint 1 — Trip-Detail Header: Button → Btn Migration.
//
// Spec: docs/specs/modules/issue_215_sprint1_trip_detail_header.md
//
// Verifiziert:
//   AC-1 (Quelltext-Check über Hauptrepo-Pfad) entfiel mit #2243.
//   AC-2: alle Header-Action-Buttons rendern mit data-slot="btn" (DOM-Check).
//
// Voraussetzung: Test-Trip `e2e-cockpit-test` aus global.setup.ts existiert.

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

test.describe('Issue #215 Sprint 1 — TripHeader Button→Btn Migration', () => {
	test.beforeEach(async ({ request }) => {
		await resetTripState(request);
	});

	test.afterAll(async ({ request }) => {
		await resetTripState(request);
	});

	test('AC-2: alle Header-Action-Buttons haben data-slot="btn"', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);

		// #2278: Header-Aktionen = Primaerknopf "Senden" (Btn) + Lebenszyklus-Menue (Archivieren steht darin).
		const sendBtn = page.getByTestId('subscription-hub-send');
		await expect(sendBtn).toHaveAttribute('data-slot', 'btn');

		// Dialog öffnen, dann Dialog-Buttons prüfen.
		await page.getByTestId('subscription-kebab').click();
		await page.getByTestId('subscription-action-archive').click();
		const cancelBtn = page.getByTestId('trip-detail-archive-confirm-cancel');
		const confirmBtn = page.getByTestId('trip-detail-archive-confirm-yes');
		await expect(cancelBtn).toHaveAttribute('data-slot', 'btn');
		await expect(confirmBtn).toHaveAttribute('data-slot', 'btn');
	});
});
