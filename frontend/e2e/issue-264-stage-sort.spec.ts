// E2E-Tests für Issue #264 — GPX-Etappenreihenfolge: Sort nach Stage-Name statt Dateiname.
//
// Spec: docs/specs/modules/issue_264_stage_order.md
//
// Kernproblem: `naturalSort(pendingFiles, (f) => f.name)` sortiert nach Dateinamen.
// Komoot-Exporte haben Datum-Präfixe (z.B. `2026-03-22_..._KHW_03_.gpx`).
// Dadurch sortiert das Frontend nach Aufnahmedatum, nicht nach KHW-Etappennummer.
//
// Fixture-Dateien (e2e/fixtures/):
//   2026-03-22_2842051671_KHW_03_.gpx  → stage.name: "KHW_03: von Porzehütte..."
//   2026-03-24_2841451574_KHW_01_.gpx  → stage.name: "KHW_01: Sillianer Hütte..."
//   2026-03-24_2844573181_KHW_00a_.gpx → stage.name: "KHW_00a: Von Troblach Bhf..."
//
// Dateiname-Sort-Reihenfolge (FALSCH): KHW_03, KHW_01, KHW_00a
//   (weil 2026-03-22 < 2026-03-24, innerhalb Datum nach Activity-ID)
//
// Stage-Name-Sort-Reihenfolge (RICHTIG): KHW_00a, KHW_01, KHW_03
//
// TDD RED: Tests schlagen fehl weil Step2Stages.svelte noch nach Dateiname sortiert.
// Nach Fix (sort nach stage.name): Tests werden grün.

import { test, expect } from '@playwright/test';
import { login, fillStep1 } from './helpers.js';
import * as path from 'node:path';

const FIXTURE_DIR = path.resolve('./e2e/fixtures');

// Komoot-Export-Fixtures: Dateiname enthält Datum-Präfix + Activity-ID
const KHW_03 = path.resolve(FIXTURE_DIR, '2026-03-22_2842051671_KHW_03_.gpx');
const KHW_01 = path.resolve(FIXTURE_DIR, '2026-03-24_2841451574_KHW_01_.gpx');
const KHW_00A_DATED = path.resolve(FIXTURE_DIR, '2026-03-24_2844573181_KHW_00a_.gpx');

const STEP1: Parameters<typeof fillStep1>[1] = {
	activity: 'trekking',
	name: 'KHW-Sort-Test',
	startDate: '2026-08-01'
};

test.describe('Issue #264 — GPX Stage-Sort: Komoot Datum-Präfix in Dateiname (#264)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	// AC-1: Wizard-Flow — Komoot-Dateien mit Datum-Präfix ergeben korrekte Stage-Reihenfolge
	test('AC-1: Stage-Row-0 zeigt KHW_00a (niedrigste Etappe), nicht KHW_03 (ältestes Datum)', async ({
		page
	}) => {
		// Step 1 ausfüllen
		await page.goto('/trips/new');
		await fillStep1(page, STEP1);
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();

		// 3 GPX-Dateien mit Komoot-Datum-Präfix hochladen
		// Dateiname-Sort würde ergeben: [KHW_03, KHW_01, KHW_00a] (nach Datum 22 < 24)
		// Stage-Name-Sort muss ergeben: [KHW_00a, KHW_01, KHW_03] (nach KHW-Nummer)
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_03, KHW_01, KHW_00A_DATED]);

		// Startdatum setzen und commiten
		await page.getByTestId('trip-wizard-step2-bulk-startdate').fill('2026-08-01');
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();

		// Alle 3 Rows müssen erscheinen
		await page.getByTestId('trip-wizard-step2-stage-row-2').waitFor({ state: 'visible' });

		// AC-1: Row 0 muss KHW_00a enthalten (korrekte Etappenreihenfolge nach stage.name)
		// SCHLÄGT FEHL bis Fix: aktuell enthält Row 0 "KHW_03" (falsche Dateiname-Sortierung)
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toContainText('KHW_00a');
	});

	// AC-1 ergänzend: vollständige Reihenfolge prüfen
	test('AC-1: Vollständige Reihenfolge ist KHW_00a → KHW_01 → KHW_03', async ({ page }) => {
		await page.goto('/trips/new');
		await fillStep1(page, STEP1);
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();

		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_03, KHW_01, KHW_00A_DATED]);
		await page.getByTestId('trip-wizard-step2-bulk-startdate').fill('2026-08-01');
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await page.getByTestId('trip-wizard-step2-stage-row-2').waitFor({ state: 'visible' });

		// Korrekte Reihenfolge nach Stage-Name
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toContainText('KHW_00a');
		await expect(page.getByTestId('trip-wizard-step2-stage-row-1')).toContainText('KHW_01');
		await expect(page.getByTestId('trip-wizard-step2-stage-row-2')).toContainText('KHW_03');
	});

	// AC-4: Regression — Dateien OHNE Datum-Präfix bleiben korrekt sortiert
	test('AC-4: Dateien ohne Datum-Präfix sortieren korrekt (kein Regression)', async ({
		page
	}) => {
		// KHW_00a.gpx, KHW_10.gpx, KHW_11.gpx — kurze Namen, kein Datum-Präfix
		const KHW_00A = path.resolve(FIXTURE_DIR, 'KHW_00a.gpx');
		const KHW_10 = path.resolve(FIXTURE_DIR, 'KHW_10.gpx');
		const KHW_11 = path.resolve(FIXTURE_DIR, 'KHW_11.gpx');

		await page.goto('/trips/new');
		await fillStep1(page, { ...STEP1, name: 'KHW-Regression-Test' });
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();

		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		// Dateien in umgekehrter Reihenfolge hochladen — sort by stage name muss korrigieren
		await fileInput.setInputFiles([KHW_11, KHW_10, KHW_00A]);
		await page.getByTestId('trip-wizard-step2-bulk-startdate').fill('2026-08-01');
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await page.getByTestId('trip-wizard-step2-stage-row-2').waitFor({ state: 'visible' });

		// KHW_00a < KHW_10 < KHW_11 nach stage.name
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toContainText('KHW_00a');
		await expect(page.getByTestId('trip-wizard-step2-stage-row-1')).toContainText('KHW_10');
		await expect(page.getByTestId('trip-wizard-step2-stage-row-2')).toContainText('KHW_11');
	});
});
