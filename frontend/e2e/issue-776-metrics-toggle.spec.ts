// E2E — Issue #776 / Fix #971: Metriken-Überblick ist fester Mail-Bestandteil (kein Opt-out).
//
// Spec: docs/specs/modules/fix_970_971_1011_e2e_ui_drift.md (Bündel I, AC-4)
//
// Der frühere Toggle-Test klickte den seit dem v2-Redesign entfernten
// `report-content-modules-toggle` und die „Metriken-Überblick"-Checkbox. Seit #790
// rendert der Mail-Renderer den Metriken-Überblick-Block unconditional
// (build_metrics_summary_pills, src/output/renderers/email/html.py:1292/1500) —
// die Opt-out-Checkbox war eine wirkungslose Karteileiche und wurde entfernt.
//
// Reale Ziel-Oberfläche der Checkbox: das Neuanlegen-Formular /trips/new,
// Tab „Briefing-Zeitplan" (TripNewEditor → EditReportConfigSection, showMailContent
// default true). Auf der Trip-Detail-Seite ist der Mail-Inhalt-Block via
// showMailContent={false} ohnehin ausgeblendet (BriefingScheduleTab).
//
// DEPLOY-GATED: greift erst NACH dem Deploy der Checkbox-Entfernung — vorher zeigt
// Staging die Checkbox noch (Prod-Code-Änderung). Der harte Surface-Check
// (report-mail-content sichtbar) stellt sicher, dass wirklich der Zeitplan-Tab
// geprüft wird und nicht still ein leerer DOM.

import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import * as path from 'node:path';

const MOBILE = { width: 390, height: 844 };

// /trips/new bis zum Zeitplan-Tab durchklicken (mobiler, verlässlicher Pfad):
// Name+Datum → Etappen → je Etappe GPX laden (schaltet den Zeitplan frei) →
// Wetter-Metriken besuchen → Briefing-Zeitplan öffnen. Kein Mock.
async function openNewTripZeitplan(page: Page) {
	await page.setViewportSize(MOBILE);
	await page.goto('/trips/new');
	await page.getByTestId('trip-new-name-input-mobile').fill('Fix #971 E2E');
	await page.getByTestId('trip-new-date-input').fill(new Date().toISOString().slice(0, 10));

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
	await tabbar.getByRole('tab', { name: /Zeitplan/ }).click({ force: true });

	// Harter Surface-Check: die Mail-Inhalt-Karte MUSS sichtbar sein — sonst prüfen
	// wir versehentlich einen leeren DOM und count()==0 wäre bedeutungslos.
	// EditReportConfigSection wird sowohl im .tn-desktop- als auch im .tn-mobile-Baum
	// gemountet (CSS-Media-Query-Toggle statt {#if}) — beide Instanzen stehen
	// gleichzeitig im DOM, daher hier wie bei den GPX-Inputs auf .tn-mobile scopen.
	await expect(page.locator('.tn-mobile').getByTestId('report-mail-content')).toBeVisible({ timeout: 15_000 });
}

test.describe('Issue #776 / Fix #971: Metriken-Überblick fest in der Mail, kein Opt-out', () => {
	test('kein Metriken-Überblick-Opt-out; Kompakt-Hinweis bestätigt festen Block', async ({ page }) => {
		await openNewTripZeitplan(page);

		// (a) Kein Opt-out-Schalter mehr für den Metriken-Überblick.
		await expect(page.getByTestId('report-show-metrics-summary')).toHaveCount(0);
		await expect(page.locator('[data-testid="report-content-modules-toggle"]')).toHaveCount(0);

		// (b) Kompakt-Modus wählen → der Hinweis bestätigt, dass der Metriken-Überblick
		//     FIX (immer) gezeigt wird — der Block ist kein optionaler Baustein.
		// (auf .tn-mobile scopen — .tn-desktop-Baum enthält dieselben Testids doppelt)
		await page.locator('.tn-mobile [data-testid="report-email-format-compact"]').check();
		const hint = page.locator('.tn-mobile').getByTestId('report-compact-hint');
		await expect(hint).toBeVisible();
		await expect(hint).toContainText('Metriken-Überblick');
	});
});
