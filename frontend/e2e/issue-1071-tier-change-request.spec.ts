// E2E — Issue #1071: Level-Änderungs-Antrag (Tiers-4, Epic #1067)
//
// Spec: docs/specs/modules/issue_1071_tier_change_request.md
//
// AC-7: Nutzer stellt über ein neues Formular in der Account-Karte einen
// Level-Änderungs-Antrag, erhält einen sichtbaren Pending-Hinweis, der auch
// ein Reload übersteht (kein lokaler Client-State, sondern aus
// profile.requested_tier abgeleitet).
//
// TDD RED (Issue #1071): Die data-testids "tier-change-select",
// "tier-change-submit" und "tier-change-pending" existieren im aktuellen
// +page.svelte noch nicht — dieser Test MUSS fehlschlagen, bis das Formular
// in Phase 6 implementiert ist.
//
// Ausführen:
//   cd frontend && GZ_E2E_USER=... GZ_E2E_PASS=... \
//     npx playwright test e2e/issue-1071-tier-change-request.spec.ts \
//     --config playwright.config.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Issue #1071: Level-Änderungs-Antrag', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.goto('/account');
		await page.waitForLoadState('networkidle');
	});

	test('AC-7: Antrag zeigt Pending-Hinweis, uebersteht Reload', async ({ page }) => {
		const select = page.getByTestId('tier-change-select');
		await expect(select).toBeVisible({ timeout: 10_000 });

		await select.selectOption('standard');
		await page.getByTestId('tier-change-submit').click();

		const pending = page.getByTestId('tier-change-pending');
		await expect(pending).toBeVisible({ timeout: 10_000 });
		await expect(pending).toContainText('Standard');

		// Pending-Hinweis muss aus profile.requested_tier abgeleitet sein,
		// nicht aus lokalem Client-State — muss einen Reload ueberstehen.
		await page.reload();
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('tier-change-pending')).toBeVisible({ timeout: 10_000 });
	});
});
