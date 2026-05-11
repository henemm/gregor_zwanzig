// E2E-Tests fuer Issue #183 — Email-Preview Header (AC-5 + AC-6).
//
// Spec-Referenz: docs/specs/modules/issue_183_email_preview_header.md
//   - AC-5: Header zeigt Trip-Name + Eyebrow ("Morgen-Briefing" / "Abend-Briefing")
//   - AC-6: Stats-Grid mit 5 Labels (Distanz, Aufstieg, Abstieg, Max-Hoehe, Segmente)
//
// Test-Strategie: Dev-Route /email-preview-dev rendert die Komponente
// isoliert mit Mock-Daten. Die Route wird in Issue #189 (Vorschau-Integration)
// durch die echte Einbindung ersetzt.

import { test, expect } from '@playwright/test';

test.describe('Issue #183 — Email-Preview Header (Dev-Route)', () => {
	test('AC-5: Header zeigt Trip-Name "Zillertal" und Eyebrow "Morgen-Briefing"', async ({
		page
	}) => {
		await page.goto('/email-preview-dev');
		await expect(page.getByTestId('email-preview-header').first()).toBeVisible();
		await expect(
			page.getByTestId('email-preview-header-eyebrow').first()
		).toHaveText(/Morgen-Briefing/);
		await expect(
			page.getByTestId('email-preview-header-title').first()
		).toContainText('Zillertal');
	});

	test('AC-6: Stats-Grid enthaelt 5 Labels', async ({ page }) => {
		await page.goto('/email-preview-dev');
		const firstHeader = page.getByTestId('email-preview-header').first();
		await expect(firstHeader).toBeVisible();
		for (const key of ['distanz', 'aufstieg', 'abstieg', 'max-hoehe', 'segmente']) {
			await expect(
				firstHeader.getByTestId(`email-preview-header-stats-label-${key}`)
			).toHaveCount(1);
		}
		// Zusaetzlich: Text-Inhalt pruefen, damit AC-6 (Beschriftung lt. Spec) erhalten bleibt
		const labels = firstHeader.locator('[data-testid^="email-preview-header-stats-label-"]');
		const texts = (await labels.allTextContents()).map((t) => t.trim());
		expect(texts).toEqual(['Distanz', 'Aufstieg', 'Abstieg', 'Max-Höhe', 'Segmente']);
	});

	test('Screenshot-Snapshot fuer visuelle Verifikation', async ({ page }) => {
		await page.goto('/email-preview-dev');
		await page.waitForSelector('[data-testid="email-preview-header"]');
		await page.screenshot({
			path: '../docs/artifacts/issue-183-email-preview-header/screenshot-header.png',
			fullPage: false
		});
	});
});
