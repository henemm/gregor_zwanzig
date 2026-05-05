import { test, expect } from '@playwright/test';
import { login } from './helpers.js';
import * as path from 'node:path';
import * as fs from 'node:fs';
import * as os from 'node:os';
import { fileURLToPath } from 'node:url';

/**
 * Issue #127: Multi-GPX-Upload mit Natural-Sort und Startdatum-Abfrage.
 *
 * Spec: docs/specs/modules/gpx_multi_import.md (v1.1, SvelteKit-Schicht)
 *
 * Validiert: Buffer-Pattern statt sofortigem Upload, Natural-Sort vor
 * Stage-Erstellung, expliziter Datums-Picker mit Default = today() oder
 * lastStage+1, lückenlose Datums-Propagation auch bei skipped corrupt files.
 */

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.resolve(__dirname, 'fixtures');
const KHW_00A = path.join(FIXTURES_DIR, 'KHW_00a.gpx');
const KHW_10 = path.join(FIXTURES_DIR, 'KHW_10.gpx');
const KHW_11 = path.join(FIXTURES_DIR, 'KHW_11.gpx');

test.describe('Trip Wizard Multi-GPX Upload (Issue #127)', () => {
	test.beforeEach(async ({ page }) => {
		await login(page);
	});

	test('shows bulk-stage date picker and commit button after multi-upload', async ({ page }) => {
		await page.goto('/trips/new');
		await page.locator('[data-testid="trip-name-input"]').fill('Multi-GPX Test');

		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_11, KHW_00A, KHW_10]);

		// Buffered files indicator (count of pending files)
		await expect(page.locator('[data-testid="bulk-stage-pending-count"]')).toBeVisible();

		// Date picker for the start date is present
		const datePicker = page.locator('[data-testid="bulk-stage-start-date"]');
		await expect(datePicker).toBeVisible();

		// Commit button shows count
		const commit = page.locator('[data-testid="bulk-stage-commit"]');
		await expect(commit).toBeVisible();
		await expect(commit).toHaveText(/3 Etappen anlegen/);
	});

	test('single-file upload still shows date picker with "1 Etappe anlegen"', async ({ page }) => {
		await page.goto('/trips/new');
		await page.locator('[data-testid="trip-name-input"]').fill('Single GPX');

		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_00A]);

		await expect(page.locator('[data-testid="bulk-stage-start-date"]')).toBeVisible();
		const commit = page.locator('[data-testid="bulk-stage-commit"]');
		await expect(commit).toHaveText(/1 Etappe anlegen/);
	});

	test('commit applies natural-sort: KHW_11, KHW_00a, KHW_10 -> KHW_00a, KHW_10, KHW_11', async ({ page }) => {
		await page.goto('/trips/new');
		await page.locator('[data-testid="trip-name-input"]').fill('Natural Sort');

		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_11, KHW_00A, KHW_10]);

		// Set start date and commit
		const datePicker = page.locator('[data-testid="bulk-stage-start-date"]');
		await datePicker.fill('2026-05-01');
		await page.locator('[data-testid="bulk-stage-commit"]').click();

		// Wait for stages to be loaded
		await expect(page.locator('text=/3 Etappe\\(n\\) geladen/')).toBeVisible({ timeout: 10_000 });

		// Navigate to step 2 to inspect stages in order
		await page.locator('[data-testid="wizard-next"]').click();

		const stageCards = page.locator('[data-testid^="stage-card-"]');
		await expect(stageCards).toHaveCount(3);

		// Stage names should reflect natural-sorted file names
		const name0 = await stageCards.nth(0).locator('input[placeholder="Etappenname"]').inputValue();
		const name1 = await stageCards.nth(1).locator('input[placeholder="Etappenname"]').inputValue();
		const name2 = await stageCards.nth(2).locator('input[placeholder="Etappenname"]').inputValue();

		// natural sort order: KHW_00a < KHW_10 < KHW_11
		expect(name0).toMatch(/KHW_00a/i);
		expect(name1).toMatch(/KHW_10/i);
		expect(name2).toMatch(/KHW_11/i);
	});

	test('date propagates from start date: 2026-05-01, 2026-05-02, 2026-05-03', async ({ page }) => {
		await page.goto('/trips/new');
		await page.locator('[data-testid="trip-name-input"]').fill('Date Prop');

		const fileInput = page.locator('input[type="file"][accept=".gpx"]');
		await fileInput.setInputFiles([KHW_11, KHW_00A, KHW_10]);

		await page.locator('[data-testid="bulk-stage-start-date"]').fill('2026-05-01');
		await page.locator('[data-testid="bulk-stage-commit"]').click();

		await expect(page.locator('text=/3 Etappe\\(n\\) geladen/')).toBeVisible({ timeout: 10_000 });
		await page.locator('[data-testid="wizard-next"]').click();

		const stageCards = page.locator('[data-testid^="stage-card-"]');
		await expect(stageCards).toHaveCount(3);

		const date0 = await stageCards.nth(0).locator('input[type="date"]').inputValue();
		const date1 = await stageCards.nth(1).locator('input[type="date"]').inputValue();
		const date2 = await stageCards.nth(2).locator('input[type="date"]').inputValue();

		expect(date0).toBe('2026-05-01');
		expect(date1).toBe('2026-05-02');
		expect(date2).toBe('2026-05-03');
	});

	test('corrupt file is skipped and remaining stages get gapless dates', async ({ page }) => {
		// Create a corrupt GPX in tmp dir (named to sort between the valid files)
		const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'gpx-corrupt-'));
		const corruptFile = path.join(tmpDir, 'KHW_05_corrupt.gpx');
		fs.writeFileSync(corruptFile, 'NOT A VALID GPX FILE');

		try {
			await page.goto('/trips/new');
			await page.locator('[data-testid="trip-name-input"]').fill('Corrupt Skip');

			const fileInput = page.locator('input[type="file"][accept=".gpx"]');
			// Order with corrupt in the middle (natural-sort: 00a < 05 < 10)
			await fileInput.setInputFiles([KHW_00A, corruptFile, KHW_10]);

			await page.locator('[data-testid="bulk-stage-start-date"]').fill('2026-05-01');
			await page.locator('[data-testid="bulk-stage-commit"]').click();

			// Wait until upload finished — exactly 2 valid stages loaded
			await expect(page.locator('text=/2 Etappe\\(n\\) geladen/')).toBeVisible({ timeout: 10_000 });

			// Inline error must be visible for the corrupt file
			await expect(page.locator('text=/KHW_05_corrupt/')).toBeVisible();

			// Navigate to step 2 and verify dates are gapless 2026-05-01, 2026-05-02
			await page.locator('[data-testid="wizard-next"]').click();
			const stageCards = page.locator('[data-testid^="stage-card-"]');
			await expect(stageCards).toHaveCount(2);

			const date0 = await stageCards.nth(0).locator('input[type="date"]').inputValue();
			const date1 = await stageCards.nth(1).locator('input[type="date"]').inputValue();
			expect(date0).toBe('2026-05-01');
			expect(date1).toBe('2026-05-02');
		} finally {
			fs.rmSync(tmpDir, { recursive: true, force: true });
		}
	});
});
