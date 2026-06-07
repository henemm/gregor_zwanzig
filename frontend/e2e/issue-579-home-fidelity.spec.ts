// E2E — #579: Home-Screen Design-Fidelity (Drift-Korrektur, Epic #575)
//
// Spec: docs/specs/modules/issue_579_home_fidelity.md
//
// Verifikation als eingeloggter Nutzer gegen Staging. Das Test-Konto ist im
// COMPARE-Modus (aktiver Vergleich, kein Live-Trip) — also der Apfel-mit-Apfel-
// Modus zu screen-home.jsx mode="compare".
//
// Base-URL: GZ_SVELTE_BASE / playwright.config baseURL (Default Staging).
//
// Ausführen:
//   cd frontend && npx playwright test e2e/issue-579-home-fidelity.spec.ts

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('#579: Home-Fidelity Compare-Modus', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1440, height: 1000 });
		await page.goto('/');
		await page.waitForLoadState('networkidle');
	});

	// ── AC-1: Compare-Modus "Einrichten / Kein Trip geplant"-Empty-State ──────
	test('AC-1: Compare-Modus zeigt "Kein Trip geplant"-Empty-State mit "Neuer Trip"-Button', async ({ page }) => {
		// Eyebrow "Einrichten" (JSX 343) — NICHT "Archiv"
		await expect(page.getByText('Einrichten', { exact: true })).toBeVisible({ timeout: 10_000 });
		// Titel "Kein Trip geplant" (JSX 344)
		await expect(page.getByText('Kein Trip geplant', { exact: true })).toBeVisible();
		// Kicker (JSX 345)
		await expect(
			page.getByText('Sobald ein Mehrtages-Trip ansteht', { exact: false }),
		).toBeVisible();
		// Primary-Button "Neuer Trip" in der Einrichten-Sektion (JSX 346),
		// href -> /trips/new
		const neuerTrip = page.locator('a[href="/trips/new"]', { hasText: 'Neuer Trip' });
		await expect(neuerTrip.first()).toBeVisible();
	});

	// ── AC-1 (negativ): generische "Archiv/Frühere Trips"-Sektion NICHT im Compare-Modus ──
	test('AC-1b: Compare-Modus zeigt NICHT die generische "Frühere Trips"-Sektion', async ({ page }) => {
		await expect(page.getByText('Frühere Trips', { exact: true })).toHaveCount(0);
	});
});
