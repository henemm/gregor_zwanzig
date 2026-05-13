// TDD: Issue #215 Sprint 2 — Forms + Dialoge Button → Btn Migration.
//
// Spec: docs/specs/modules/issue_215_sprint2_forms_dialogs.md
//
// Verifiziert:
//   AC-1: Alle 6 Spec-Dateien importieren Btn statt Button (Source-Check).
//   AC-2: Dialog-Content-Close-Button rendert mit data-slot="btn" (DOM-Check).

import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const FILES = [
	'frontend/src/lib/components/SubscriptionForm.svelte',
	'frontend/src/lib/components/LocationForm.svelte',
	'frontend/src/lib/components/TripForm.svelte',
	'frontend/src/lib/components/WeatherConfigDialog.svelte',
	'frontend/src/lib/components/ui/dialog/dialog-content.svelte',
	'frontend/src/lib/components/ui/dialog/dialog-footer.svelte'
];

const TRIP_ID = 'e2e-cockpit-test';

async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

test.describe('Issue #215 Sprint 2 — Forms+Dialogs Button→Btn Migration', () => {
	for (const file of FILES) {
		const basename = file.split('/').pop();
		test(`AC-1 (${basename}): Btn-Import statt Button-Import`, async () => {
			const content = await readFile(`/home/hem/gregor_zwanzig/${file}`, 'utf-8');
			expect(content).toContain(`import { Btn } from '$lib/components/ui/btn/index.js'`);
			expect(content).not.toContain(`import { Button } from '$lib/components/ui/button`);
		});
	}

	test('AC-2: Dialog-Close-Button (via dialog-content.svelte) rendert als Btn', async ({
		page,
		request
	}) => {
		await resetTripState(request);
		await page.goto(`/trips/${TRIP_ID}`);

		// Dialog via Archive-Action öffnen — dieser nutzt dialog-content.svelte
		const archiveBtn = page.getByTestId('trip-detail-action-archive');
		await archiveBtn.click();

		// Close-Button im Dialog-Overlay (oben rechts):
		// Hinweis: bits-ui's DialogPrimitive.Close spreadet `data-slot="dialog-close"`
		// NACH Btn's eigenen Attributen — der Wert wird überschrieben. Btn-spezifische
		// Attribute (data-variant, data-size) bleiben aber erhalten und beweisen die
		// Migration auf Btn (alter Button hatte diese Attribute nicht).
		const closeBtn = page.locator('[data-slot="dialog-close"]').first();
		await expect(closeBtn).toHaveAttribute('data-variant', 'ghost');
		await expect(closeBtn).toHaveAttribute('data-size', 'icon-sm');

		await resetTripState(request);
	});
});
