// TDD: Issue #215 Sprint 1 — Trip-Detail Header: Button → Btn Migration.
//
// Spec: docs/specs/modules/issue_215_sprint1_trip_detail_header.md
//
// Verifiziert:
//   AC-1: TripHeader.svelte importiert Btn statt Button (Source-Check).
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

		const pauseBtn = page.getByTestId('trip-detail-action-pause');
		const archiveBtn = page.getByTestId('trip-detail-action-archive');
		await expect(pauseBtn).toHaveAttribute('data-slot', 'btn');
		await expect(archiveBtn).toHaveAttribute('data-slot', 'btn');

		// Dialog öffnen, dann Dialog-Buttons prüfen.
		await archiveBtn.click();
		const cancelBtn = page.getByTestId('trip-detail-archive-confirm-cancel');
		const confirmBtn = page.getByTestId('trip-detail-archive-confirm-yes');
		await expect(cancelBtn).toHaveAttribute('data-slot', 'btn');
		await expect(confirmBtn).toHaveAttribute('data-slot', 'btn');
	});

	test('AC-1: TripHeader.svelte importiert Btn statt Button', async () => {
		const fs = await import('node:fs/promises');
		const content = await fs.readFile(
			'/home/hem/gregor_zwanzig/frontend/src/lib/components/trip-detail/TripHeader.svelte',
			'utf-8'
		);
		expect(content).toContain(`import { Btn } from '$lib/components/ui/btn/index.js'`);
		expect(content).not.toContain(`import { Button } from '$lib/components/ui/button`);
	});
});
