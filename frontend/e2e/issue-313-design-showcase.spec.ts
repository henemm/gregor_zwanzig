// TDD RED + GREEN: Issue #313 — `/_design` Showcase vervollstaendigen.
//
// Spec: docs/specs/modules/issue_313_design_showcase.md
//
// Echte E2E gegen die Preview-Build-Showcase-Route `/_design`.
// Deckt AC-1..AC-11 ab (alle 11 Sections, Badge 6 Varianten, WIcon 8 kinds,
// Dot 12 Instanzen, Btn-Loading, Pill-Outlined, Wordmark, Form-Controls,
// Card, Table, Dialog open/close, Accordion A offen / B zu->offen).

import { test, expect } from '@playwright/test';

test.describe('Issue #313 — /_design Showcase', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/_design');
	});

	test('AC-1: alle 11 Sections im DOM mit korrekten data-testid', async ({ page }) => {
		const sections = [
			'atoms-section',
			'wordmark-section',
			'form-controls-section',
			'card-section',
			'table-section',
			'dialog-section',
			'accordion-section',
			'nav-hint-section',
			'topo-section',
			'sparkline-section',
			'profile-signatures-section'
		];
		for (const id of sections) {
			await expect(page.getByTestId(id)).toBeVisible();
		}
	});

	test('AC-2a: Badge in allen 6 Varianten sichtbar', async ({ page }) => {
		const atoms = page.getByTestId('atoms-section');
		const badges = atoms.locator('[data-slot="badge"]');
		await expect(badges).toHaveCount(6);
		for (const label of ['Default', 'Secondary', 'Destructive', 'Outline', 'Ghost', 'Link']) {
			await expect(atoms.locator('[data-slot="badge"]', { hasText: label })).toBeVisible();
		}
	});

	test('AC-2b: WIcon in allen 8 kinds sichtbar', async ({ page }) => {
		const wicons = page.getByTestId('wicon-group').locator('svg');
		await expect(wicons).toHaveCount(8);
	});

	test('AC-3: Btn-Loading-State (disabled + rotierendes Loader2-Icon)', async ({ page }) => {
		const loadingBtn = page.getByTestId('btn-loading');
		await expect(loadingBtn).toBeVisible();
		await expect(loadingBtn).toBeDisabled();
		await expect(loadingBtn.locator('svg.animate-spin')).toBeVisible();
	});

	test('AC-4: mind. 3 Pills mit data-outlined in unterschiedlichen Tones', async ({ page }) => {
		const atoms = page.getByTestId('atoms-section');
		const outlined = atoms.locator('[data-slot="pill"][data-outlined]');
		const count = await outlined.count();
		expect(count).toBeGreaterThanOrEqual(3);
		const tones = new Set<string>();
		for (let i = 0; i < count; i++) {
			const t = await outlined.nth(i).getAttribute('data-tone');
			if (t) tones.add(t);
		}
		expect(tones.size).toBeGreaterThanOrEqual(3);
	});

	test('AC-5: 4 Semantic-Tones x 3 Sizes = 12 Dot-Instanzen', async ({ page }) => {
		const group = page.getByTestId('dot-semantic-group');
		const dots = group.locator('[data-slot="dot"]');
		await expect(dots).toHaveCount(12);
		for (const tone of ['success', 'warning', 'danger', 'info']) {
			for (const size of ['xs', 'sm', 'md']) {
				await expect(
					group.locator(`[data-slot="dot"][data-tone="${tone}"][data-size="${size}"]`)
				).toHaveCount(1);
			}
		}
	});

	test('AC-6: Wordmark in sm/md/lg im selben Container', async ({ page }) => {
		const section = page.getByTestId('wordmark-section');
		await expect(section).toBeVisible();
		// 3 Wordmark-Instanzen — JetBrains-Mono Wortmarke "gregor.zwanzig".
		await expect(section.getByText('gregor', { exact: false })).toHaveCount(3);
	});

	test('AC-7: Form-Controls (Checkbox, Segmented, Label+Input, Select)', async ({ page }) => {
		const section = page.getByTestId('form-controls-section');
		// Checkbox: 3 native checkboxes (checked/unchecked/disabled)
		await expect(section.locator('input[type="checkbox"]')).toHaveCount(3);
		// Segmented: 2 Options
		await expect(section.locator('[data-slot="segmented-item"]')).toHaveCount(2);
		// Label + Input
		await expect(section.locator('label[for="demo-input"]')).toBeVisible();
		await expect(section.locator('#demo-input')).toBeVisible();
		// Select: mind. 2 selects (default + disabled)
		await expect(section.locator('select')).toHaveCount(2);
	});

	test('AC-8: Card mit Header (Title+Description), Content, Footer', async ({ page }) => {
		const section = page.getByTestId('card-section');
		await expect(section.locator('[data-slot="card"]')).toBeVisible();
		await expect(section.locator('[data-slot="card-title"]')).toBeVisible();
		await expect(section.locator('[data-slot="card-description"]')).toBeVisible();
		await expect(section.locator('[data-slot="card-content"]')).toBeVisible();
		await expect(section.locator('[data-slot="card-footer"]')).toBeVisible();
	});

	test('AC-9: Tabelle mit Header-Zeile (3 Spalten) + mind. 2 Daten-Zeilen', async ({ page }) => {
		const section = page.getByTestId('table-section');
		await expect(section.locator('thead th')).toHaveCount(3);
		await expect(section.locator('tbody tr')).toHaveCount(2);
	});

	test('AC-10: Dialog oeffnet via Trigger und schliesst via Schliessen-Btn', async ({ page }) => {
		await page.getByTestId('dialog-open-trigger').click();
		const title = page.locator('[data-slot="dialog-title"]');
		await expect(title).toBeVisible();
		await expect(page.locator('[data-slot="dialog-description"]')).toBeVisible();
		await page.getByTestId('dialog-close-btn').click();
		await expect(title).toBeHidden();
	});

	test('AC-11: Accordion A offen, B geschlossen -> Klick oeffnet B', async ({ page }) => {
		const section = page.getByTestId('accordion-section');
		await expect(section.getByText('Inhalt von Sektion A ist sichtbar.')).toBeVisible();
		await expect(section.getByText('Inhalt von Sektion B ist verborgen.')).toHaveCount(0);
		await page.getByTestId('edit-section-demo-b-header').click();
		await expect(section.getByText('Inhalt von Sektion B ist verborgen.')).toBeVisible();
	});
});
