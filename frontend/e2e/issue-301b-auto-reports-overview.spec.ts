// TDD RED Issue #301 Lieferung B — post-push gegen Staging.
//
// E2E — AutoReportsOverview: Default-Content im Compare-Bereich als
// Eyebrow + H1 + responsives Kachelraster (AutoReportCard + AddReportCard)
// statt der bisherigen Karten-Liste (CompareSubscriptionsPanel).
// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (AC-1, AC-2, AC-6, AC-7)
//
// RED-by-construction: die referenzierten data-testids (auto-reports-overview,
// reports-grid, auto-report-card-*, add-report-card, empty-hint) existieren im
// Frontend noch nicht. Wird NICHT lokal ausgeführt, sondern post-push gegen
// https://staging.gregor20.henemm.com.
//
// TestID-Inventar (laut Spec):
//   auto-reports-overview        — Wrapper-<section> des Default-Contents
//   reports-grid                 — CSS-Grid-Container (display: grid)
//   auto-report-card-{sub.id}    — Anzeige-Kachel pro Subscription
//   add-report-card              — gestrichelte "+"-Kachel (immer letzte Position)
//   empty-hint                   — dezenter Hinweistext bei 0 Subscriptions

import { test, expect } from '@playwright/test';
import { login } from './helpers.js';

test.describe('Issue #301 Lieferung B: AutoReportsOverview Default-Content', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/compare');
	});

	// AC-1: Default-Content (keine Selektion/kein Ergebnis) zeigt Eyebrow + H1.
	test('AC-1: Eyebrow "Orts-Vergleich · Auto-Reports" + H1 "Deine Auto-Reports"', async ({
		page
	}) => {
		const overview = page.getByTestId('auto-reports-overview');
		await expect(overview).toBeVisible();

		// Eyebrow-Beschriftung über der H1.
		await expect(overview).toContainText('Orts-Vergleich · Auto-Reports');

		// H1 mit exaktem Titel.
		const heading = overview.getByRole('heading', { level: 1, name: 'Deine Auto-Reports' });
		await expect(heading).toBeVisible();
	});

	// AC-2 / AC-6: reports-grid ist display:grid; bei vorhandenen Subs ≥1 Kachel.
	test('AC-2: reports-grid nutzt display:grid; Subscriptions erscheinen als Kacheln', async ({
		page
	}) => {
		const grid = page.getByTestId('reports-grid');
		await expect(grid).toBeVisible();

		// Container ist ein CSS-Grid (keine vertikale <ul>/<li>-Liste).
		const display = await grid.evaluate((el) => getComputedStyle(el).display);
		expect(display).toBe('grid');

		// add-report-card ist immer Teil des Grids.
		await expect(grid.getByTestId('add-report-card')).toBeVisible();

		// Wenn Subscriptions existieren, erscheinen sie als auto-report-card-*-Kacheln.
		const cards = grid.locator('[data-testid^="auto-report-card-"]');
		const cardCount = await cards.count();
		if (cardCount > 0) {
			await expect(cards.first()).toBeVisible();
		} else {
			// 0 Subscriptions → der Empty-Pfad wird in AC-6 separat geprüft.
			expect(cardCount).toBe(0);
		}
	});

	// AC-6: Bei 0 Subscriptions nur add-report-card + empty-hint, keine Kachel.
	test('AC-6: leeres Array → nur AddReportCard + empty-hint, keine auto-report-card', async ({
		page
	}) => {
		const grid = page.getByTestId('reports-grid');
		const cards = grid.locator('[data-testid^="auto-report-card-"]');
		const cardCount = await cards.count();

		if (cardCount > 0) {
			// Staging hat Subscriptions → der Empty-Pfad ist nicht erreichbar.
			// Dann darf der empty-hint NICHT sichtbar sein (Negativ-Assertion).
			await expect(page.getByTestId('empty-hint')).toHaveCount(0);
			return;
		}

		// 0 Subscriptions → AddReportCard + empty-hint sichtbar, keine Kachel im DOM.
		await expect(page.getByTestId('add-report-card')).toBeVisible();
		await expect(page.getByTestId('empty-hint')).toBeVisible();
		expect(cardCount).toBe(0);
	});

	// AC-7: Klick auf AddReportCard öffnet den Speichern-Dialog (SubscriptionForm),
	//        URL bleibt /compare (keine Navigation).
	test('AC-7: Klick auf AddReportCard öffnet SubscriptionForm-Dialog, URL bleibt /compare', async ({
		page
	}) => {
		const urlBefore = new URL(page.url()).pathname;
		expect(urlBefore).toBe('/compare');

		await page.getByTestId('add-report-card').click();

		// SubscriptionForm-Dialog öffnet sich (Speichern-Dialog "Als Auto-Report speichern").
		const dialog = page.locator('[role="dialog"]');
		await expect(dialog).toBeVisible();
		await expect(dialog).toContainText('Als Auto-Report speichern');

		// Keine Navigation — URL bleibt /compare.
		expect(new URL(page.url()).pathname).toBe('/compare');
	});
});
