// E2E-Tests fuer Epic #136 Sub-Spec #162 (Step 2: GPX-Multi-Upload + Drag-Sort + Pause).
//
// Spec-Referenz: docs/specs/modules/epic_136_step2_stages.md
//
// TestID-Inventar (Sub-Spec §10):
//   trip-wizard-step2-stages (Container, aus #160 vorhanden)
//   trip-wizard-step2-dropzone
//   trip-wizard-step2-pending
//   trip-wizard-step2-pending-count
//   trip-wizard-step2-bulk-startdate
//   trip-wizard-step2-bulk-commit
//   trip-wizard-step2-bulk-cancel
//   trip-wizard-step2-stage-list
//   trip-wizard-step2-stage-row-{i}
//   trip-wizard-step2-stage-pill-{i}
//   trip-wizard-step2-stage-date-{i}
//   trip-wizard-step2-stage-delete-{i}
//   trip-wizard-step2-drag-handle-{i}
//   trip-wizard-step2-pause-marker-{i}
//   trip-wizard-step2-pause-after-{i}

import { test, expect } from '@playwright/test';
import { login, fillStep1, fillStep2, type Step1Input } from './helpers.js';
import * as path from 'node:path';

const DEFAULT_STEP1: Step1Input = {
	activity: 'trekking',
	name: 'Step2-Test',
	startDate: '2026-06-01'
};

const FIXTURE_DIR = path.resolve('./e2e/fixtures');
const TEST_GPX = path.resolve(FIXTURE_DIR, 'test-trip.gpx');
const KHW_00A = path.resolve(FIXTURE_DIR, 'KHW_00a.gpx');
const KHW_10 = path.resolve(FIXTURE_DIR, 'KHW_10.gpx');
const KHW_11 = path.resolve(FIXTURE_DIR, 'KHW_11.gpx');

async function gotoStep2(page: import('@playwright/test').Page) {
	await page.goto('/trips/new');
	await fillStep1(page, DEFAULT_STEP1);
	await page.getByTestId('trip-wizard-next').click();
	await expect(page.getByTestId('trip-wizard-step2-stages')).toBeVisible();
}

test.describe('Trip-Wizard Step 2 — GPX-Upload + Drag-Sort + Pause (#162)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('AC: Drop-Zone ist sichtbar', async ({ page }) => {
		await gotoStep2(page);
		await expect(page.getByTestId('trip-wizard-step2-dropzone')).toBeVisible();
	});

	test('AC: Drop-Zone ist tastatur-erreichbar (Enter triggert File-Picker)', async ({ page }) => {
		await gotoStep2(page);
		const dropzone = page.getByTestId('trip-wizard-step2-dropzone');
		await expect(dropzone).toHaveAttribute('role', 'button');
		await expect(dropzone).toHaveAttribute('tabindex', '0');
	});

	test('AC: Multi-File-Upload zeigt Pending-Region mit Count-Badge', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A, KHW_10, KHW_11]);
		await expect(page.getByTestId('trip-wizard-step2-pending-count')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-pending-count')).toContainText('3');
	});

	test('AC: Single-File-Upload zeigt "1 Etappe anlegen"-Button', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([TEST_GPX]);
		const commit = page.getByTestId('trip-wizard-step2-bulk-commit');
		await expect(commit).toHaveText(/1 Etappe anlegen/);
	});

	test('AC: Multi-File-Upload zeigt "X Etappen anlegen"-Button', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A, KHW_10, KHW_11]);
		const commit = page.getByTestId('trip-wizard-step2-bulk-commit');
		await expect(commit).toHaveText(/3 Etappen anlegen/);
	});

	test('AC: Bulk-Datumspicker ist sichtbar bei Pending-Files', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([TEST_GPX]);
		await expect(page.getByTestId('trip-wizard-step2-bulk-startdate')).toBeVisible();
	});

	test('AC: Bulk-Cancel verwirft Pending-Files', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([TEST_GPX]);
		await expect(page.getByTestId('trip-wizard-step2-pending-count')).toBeVisible();
		await page.getByTestId('trip-wizard-step2-bulk-cancel').click();
		await expect(page.getByTestId('trip-wizard-step2-pending-count')).not.toBeVisible();
	});

	test('AC: Commit erzeugt Stage-Row mit T01-Pill', async ({ page }) => {
		await gotoStep2(page);
		await fillStep2(page);
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-pill-0')).toContainText('T01');
	});

	test('AC: Stage-Row hat Drag-Handle, Date-Input, Delete-Btn', async ({ page }) => {
		await gotoStep2(page);
		await fillStep2(page);
		await expect(page.getByTestId('trip-wizard-step2-drag-handle-0')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-date-0')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-delete-0')).toBeVisible();
	});

	test('AC: Auto-Datierung — erste Stage erbt startDate aus Step 1', async ({ page }) => {
		await gotoStep2(page);
		await fillStep2(page);
		await expect(page.getByTestId('trip-wizard-step2-stage-date-0')).toHaveValue('2026-06-01');
	});

	test('AC: Multi-Upload Auto-Datierung lueckenlos', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A, KHW_10, KHW_11]);
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-2')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-date-0')).toHaveValue('2026-06-01');
		await expect(page.getByTestId('trip-wizard-step2-stage-date-1')).toHaveValue('2026-06-02');
		await expect(page.getByTestId('trip-wizard-step2-stage-date-2')).toHaveValue('2026-06-03');
	});

	test('AC: Manuelles Datum-Override schuetzt Stage vor Auto-Re-Date', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A, KHW_10]);
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-1')).toBeVisible();

		// Stage 0 manuell auf 2026-08-01 setzen
		await page.getByTestId('trip-wizard-step2-stage-date-0').fill('2026-08-01');
		await expect(page.getByTestId('trip-wizard-step2-stage-date-0')).toHaveValue('2026-08-01');

		// Pause einfuegen ruft recomputeStageDates — Override muss bleiben
		await page.getByTestId('trip-wizard-step2-pause-after-1').click({ force: true });
		await expect(page.getByTestId('trip-wizard-step2-stage-date-0')).toHaveValue('2026-08-01');
	});

	test('AC: Pause-Inserter fuegt Pausentag zwischen Stages ein', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A, KHW_10]);
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-1')).toBeVisible();

		// Pause nach Stage 0 einfuegen
		await page.getByTestId('trip-wizard-step2-pause-after-0').click({ force: true });
		await expect(page.getByTestId('trip-wizard-step2-stage-row-2')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-pause-marker-1')).toBeVisible();
	});

	test('AC: Pausentag bekommt KEINE T-Pill', async ({ page }) => {
		await gotoStep2(page);
		await fillStep2(page);
		await page.getByTestId('trip-wizard-step2-pause-after-0').click({ force: true });
		await expect(page.getByTestId('trip-wizard-step2-pause-marker-1')).toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-pill-1')).toHaveCount(0);
	});

	test('AC: T-Nummerierung ueberspringt Pausen', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A, KHW_10]);
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-1')).toBeVisible();

		// Pause nach Stage 0 einfuegen — Reihenfolge: T01, Pause, T02
		await page.getByTestId('trip-wizard-step2-pause-after-0').click({ force: true });
		await expect(page.getByTestId('trip-wizard-step2-stage-pill-0')).toContainText('T01');
		await expect(page.getByTestId('trip-wizard-step2-stage-pill-2')).toContainText('T02');
	});

	test('AC: Stage-Delete entfernt Row', async ({ page }) => {
		await gotoStep2(page);
		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A, KHW_10]);
		await page.getByTestId('trip-wizard-step2-bulk-commit').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-1')).toBeVisible();

		await page.getByTestId('trip-wizard-step2-stage-delete-0').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-1')).not.toBeVisible();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
	});

	test('AC: Weiter-Button initial in Step 2 disabled, nach Upload enabled', async ({ page }) => {
		await gotoStep2(page);
		await expect(page.getByTestId('trip-wizard-next')).toBeDisabled();
		await fillStep2(page);
		await expect(page.getByTestId('trip-wizard-next')).toBeEnabled();
	});

	test('AC: Zurueck-Button in Step 2 sichtbar', async ({ page }) => {
		await gotoStep2(page);
		await expect(page.getByTestId('trip-wizard-back')).toBeVisible();
	});

	test('AC: Zurueck-Klick fuehrt nach Step 1, Step-2-Zustand bleibt erhalten', async ({ page }) => {
		await gotoStep2(page);
		await fillStep2(page);
		await page.getByTestId('trip-wizard-back').click();
		await expect(page.getByTestId('trip-wizard-step1-profile')).toBeVisible();
		await page.getByTestId('trip-wizard-next').click();
		await expect(page.getByTestId('trip-wizard-step2-stage-row-0')).toBeVisible();
	});
});
