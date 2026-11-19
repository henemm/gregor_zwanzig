// Staging-Klickpfad — #1720 Scheibe 1/2: 3-Tages-Ausblick des Trips (AC-6, AC-10, AC-13).
//
// Spec: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md
// Kontext: docs/context/feat-1720-vorschau-metriken.md
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): der Abschnitt „3-Tages-Vorschau“ und die
// Mail-Inhalt-Karte sind aus dem Reiter Zustellung entfernt. Den Ausblick bedient im Hub allein die Karte
// „Was steht wo“ im Reiter Wetter: Spalte „3-Tages-Ausblick“ (Haken je Metrik, gespeichert als Stelle `outlook`
// in `display_config.placements`) und unter „Ganze Blöcke ein- und ausschalten“ genau ein Schalter-Paar
// Morgen/Abend (`outlook_reports`). Die Zusicherungen laufen dort.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/trip-outlook-metric-selection.staging.spec.ts
//   npx playwright test --config=playwright.trip-outlook.staging.config.ts

import { test, expect } from '@playwright/test';
import { ersteAngehakte, gespeichertAn, haken, oeffneKarte, seedAbo, tabelle, tabelleGespeichert, type Abo } from './was-steht-wo.helpers';

type CatalogEntry = { key: string; label: string; metric_id: string; aggregation: string };

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.describe('Trip-Ausblick in der Karte „Was steht wo“ (#1720, #3154)', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
	});

	test('AC-6 (#1720 S1): eine abgewaehlte Groesse bleibt nach dem Neuladen abgewaehlt, ohne Konsolenfehler', async ({ page }) => {
		const fehler: string[] = [];
		page.on('console', (m) => {
			if (m.type() === 'error') fehler.push(m.text());
		});
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		let karte = await oeffneKarte(page, 'route', abo.id);
		const m = await ersteAngehakte(karte, 'outlook');
		const gespeichert = tabelleGespeichert(page, abo.id);
		await haken(karte, m, 'outlook').click();
		await gespeichert;
		expect(gespeichertAn((await tabelle(page.request, 'route', abo.id)).placements, m, 'outlook')).toBe(false);
		await page.reload();
		karte = await oeffneKarte(page, 'route', abo.id);
		await expect(haken(karte, m, 'outlook')).not.toBeChecked();
		expect(fehler, 'keine Konsolenfehler').toEqual([]);
		await page.screenshot({ path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-6-abwahl-ueberlebt-reload.png' });
	});

	test('AC-6 (#1720 S2): der Trip-Ausblick traegt KEINEN Hinweis "Erscheint nur in der E-Mail"', async ({ page }) => {
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		const karte = await oeffneKarte(page, 'route', abo.id);
		const kopf = karte.locator('[data-slot="et-kopf-stelle"][data-stelle="outlook"]');
		await expect(kopf, 'Vorbedingung: Spalte Ausblick').toHaveCount(1);
		await expect(kopf, 'die Auswahl wirkt in E-Mail und Telegram').toContainText('E-Mail und Telegram');
		await expect(karte.getByText('Erscheint nur in der E-Mail', { exact: false })).toHaveCount(0);
		await page.screenshot({ path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-7-kein-email-hinweis.png' });
	});

	test('AC-13 (#1720 S1): genau ein Ausblick-Schalter (je Briefing), keiner sonst im Hub', async ({ page }) => {
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		await oeffneKarte(page, 'route', abo.id);
		for (const b of ['morning', 'evening']) await expect(page.locator(`[data-testid="was-steht-wo-ausblick-${b}"]`)).toHaveCount(1);
		await expect(page.getByTestId('report-show-outlook'), 'kein alter Ausblick-Schalter').toHaveCount(0);
		await page.getByTestId('trip-detail-tab-zustellung').first().click();
		await expect(page.getByTestId('zustellung-uebergang').first()).toBeVisible({ timeout: 15_000 });
		await expect(page.locator('[data-testid="report-show-outlook"], [data-testid^="was-steht-wo-ausblick-"]'), 'Reiter Zustellung ohne Ausblick-Schalter').toHaveCount(0);
		await page.screenshot({ path: '../docs/artifacts/feat-1720-vorschau-metriken/ac-13-kein-zweiter-schalter.png', fullPage: true });
	});

	test('AC-10 (#710): der Ausblick-Katalog bietet "Vorhersage-Genauigkeit" nicht an', async ({ page }) => {
		const katalogRes = await page.request.get('/api/compare/metrics');
		expect(katalogRes.ok(), `GET /api/compare/metrics HTTP ${katalogRes.status()}`).toBeTruthy();
		const katalog = (await katalogRes.json()) as { metrics: CatalogEntry[] };
		expect(katalog.metrics.some((m) => m.metric_id === 'confidence'), 'AC-10: der Katalog darf "confidence" nicht anbieten (PO-Entscheid #710)').toBe(false);
		expect(katalog.metrics.length, 'Vakuum-Schutz').toBeGreaterThan(20);
		const abo = await seedAbo(page.request, 'route');
		abos.push(abo);
		const karte = await oeffneKarte(page, 'route', abo.id);
		await expect(karte.locator('[data-slot="et-zeile"][data-metrik="confidence"]'), 'AC-10: keine Zeile Vorhersage-Genauigkeit').toHaveCount(0);
		expect(((await tabelle(page.request, 'route', abo.id)).rows as Array<{ metric_id: string }>).some((r) => r.metric_id === 'confidence')).toBe(false);
	});
});
