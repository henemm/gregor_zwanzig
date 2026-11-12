// TDD: Issue #215 Sprint 2 — Forms + Dialoge Button → Btn Migration.
//
// Spec: docs/specs/modules/issue_215_sprint2_forms_dialogs.md
//
// Verifiziert:
//   AC-1 (Quelltext-Check über Hauptrepo-Pfad) entfiel mit #2243.
//   AC-2: Dialog-Content-Close-Button rendert mit data-slot="btn" (DOM-Check).

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';

async function resetTripState(request: import('@playwright/test').APIRequestContext) {
	await request.patch(`/api/trips/${TRIP_ID}/state`, {
		data: { paused: false, archived: false }
	});
}

test.describe('Issue #215 Sprint 2 — Forms+Dialogs Button→Btn Migration', () => {
	test('AC-2: Dialog-Close-Button (via dialog-content.svelte) rendert als Btn', async ({
		page,
		request
	}) => {
		await resetTripState(request);
		await page.goto(`/trips/${TRIP_ID}`);

		// Dialog via Archive-Action öffnen — dieser nutzt dialog-content.svelte
		await page.getByTestId('subscription-kebab').click();
		await page.getByTestId('subscription-action-archive').click();

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
