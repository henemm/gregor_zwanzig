// E2E — Issue #774 / Fix #971: „Metriken-Überblick"-Checkbox aus der Mail-Inhalt-Karte entfernt.
//
// Spec: docs/specs/modules/fix_970_971_1011_e2e_ui_drift.md (Bündel I, AC-4)
//
// Reale Ziel-Oberfläche der Checkbox: Neuanlegen-Formular /trips/new, Tab
// „Briefing-Zeitplan" (TripNewEditor → MailInhaltCard, showMailContent
// default true). Auf der Trip-Detail-Seite ist der Mail-Inhalt-Block via
// showMailContent={false} ohnehin ausgeblendet.
//
// Die frühere Persistenz-Prüfung (AC-1) entfällt ersatzlos: seit #790 rendert der
// Mail-Renderer den Metriken-Überblick-Block unconditional — die Checkbox war eine
// wirkungslose Karteileiche und wurde entfernt.
//
// DEPLOY-GATED: greift erst NACH dem Deploy der Checkbox-Entfernung. Der harte
// Surface-Check (report-mail-content sichtbar) stellt sicher, dass der Zeitplan-Tab
// tatsächlich geprüft wird (kein bedeutungsloses count()==0 auf leerem DOM).

import { test, expect } from '@playwright/test';
import { tippeDatum } from './helpers';
import type { Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

async function openNewTripZeitplan(page: Page) {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('Fix #971 E2E 774');
	await tippeDatum(page, page.getByTestId('trip-new-date-input'), new Date().toISOString().slice(0, 10));

	const tabbar = page.getByTestId('tn-mobile-tabbar');
	await tabbar.getByRole('tab', { name: /Etappen/ }).click({ force: true });

	const gpx = path.resolve('./e2e/fixtures/test-trip.gpx');
	// GPX in jede Etappe laden. WICHTIG: TripNewEditor.svelte:644 (`{#if s.gpx}`)
	// entfernt den Datei-Input einer Etappe komplett aus dem DOM, sobald deren GPX
	// gesetzt ist — der nächste offene Input rutscht danach auf Index 0. Ein vorab
	// fixierter `.nth(i)`-Zähler zeigt also ab der zweiten Iteration ins Leere.
	// Daher IMMER den ERSTEN verbleibenden offenen Input frisch auflösen (kein
	// Index-Zähler); `stageCount` dient nur als Obergrenze für die Loop-Länge.
	const stageCount = await page.locator('.tn-mobile input[type="file"][accept=".gpx"]').count();
	for (let i = 0; i < stageCount; i++) {
		const input = page.locator('.tn-mobile input[type="file"][accept=".gpx"]').first();
		await Promise.all([
			page.waitForResponse((r) => r.url().includes('/api/gpx/parse'), { timeout: 30_000 }).catch(() => null),
			input.setInputFiles(gpx),
		]);
		await page.waitForTimeout(600);
	}

	await tabbar.getByRole('tab', { name: /Wetter/ }).click({ force: true });
	// #3332 (AC-10): die Mail-Inhalt-Karte entfällt im Trip-Anlegen (Hub-Parität); die verbleibenden
	// Inhalts-Bausteine bedient die Karte „Was steht wo“ im Schritt Wetter. Harter Surface-Check auf sie.
	await expect(
		page.locator('.tn-mobile [data-testid="was-steht-wo"] [data-testid="was-steht-wo-show_stage_stats"]'),
	).toBeVisible({ timeout: 20_000 });
}

test.describe('Issue #774 / Fix #971: Metriken-Überblick-Checkbox entfernt', () => {
	test('AC-4: keine Metriken-Überblick-Checkbox, verbleibende Inhalts-Bausteine sichtbar', async ({ page }) => {
		await openNewTripZeitplan(page);

		// Die entfernte Checkbox darf NICHT mehr existieren — auch nicht im Schritt Zustellung.
		await expect(page.getByTestId('report-show-metrics-summary')).toHaveCount(0);
		await page.getByTestId('tn-mobile-tabbar').getByRole('tab', { name: /Zustellung/ }).click({ force: true });
		await expect(page.locator('.tn-mobile [data-testid="zustellung-tab"]')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('report-show-metrics-summary')).toHaveCount(0);
		await expect(page.getByTestId('report-mail-content'), '#3332 AC-10: Mail-Inhalt-Karte noch im Trip-Anlegen').toHaveCount(0);

		// Die verbleibenden Inhalts-Bausteine sind weiterhin bedienbar — in der Karte „Was steht wo“.
		await page.getByTestId('tn-mobile-tabbar').getByRole('tab', { name: /Wetter/ }).click({ force: true });
		const karte = page.locator('.tn-mobile [data-testid="was-steht-wo"]');
		await expect(karte.getByTestId('was-steht-wo-ausblick-morning')).toBeVisible({ timeout: 15_000 });
		await expect(karte.getByTestId('was-steht-wo-show_stage_stats')).toBeVisible();
		await expect(karte.getByTestId('was-steht-wo-show_yesterday_comparison')).toBeVisible();
	});
});
