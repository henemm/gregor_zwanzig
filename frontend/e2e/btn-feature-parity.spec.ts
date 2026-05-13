// TDD RED + GREEN: Issue #214 — Btn Feature-Paritaet (Phase A).
//
// Spec: docs/specs/modules/issue_214_btn_feature_parity.md
//
// Diese Tests laufen gegen die `/_design`-Showcase-Route und decken AC-1..AC-19
// auf E2E-Ebene ab (Sichtbarkeit, Render-Modi, Computed-Styles, Disabled-State).

import { test, expect } from '@playwright/test';

test.describe('Issue #214 — Btn Feature-Paritaet', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/_design');
	});

	test('AC-1: 7 Variants in der Showcase sichtbar (primary, accent, outline, ghost, secondary, destructive, link)', async ({
		page
	}) => {
		const ids = [
			'btn-showcase-variant-primary',
			'btn-showcase-variant-accent',
			'btn-showcase-variant-outline',
			'btn-showcase-variant-ghost',
			'btn-showcase-variant-secondary',
			'btn-showcase-variant-destructive',
			'btn-showcase-variant-link'
		];
		for (const id of ids) {
			await expect(page.getByTestId(id)).toBeVisible();
		}
	});

	test('AC-2: 8 Sizes in der Showcase sichtbar und data-size korrekt', async ({ page }) => {
		const sizes: Array<{ id: string; expected: string }> = [
			{ id: 'btn-showcase-size-xs', expected: 'xs' },
			{ id: 'btn-showcase-size-sm', expected: 'sm' },
			{ id: 'btn-showcase-size-md', expected: 'md' },
			{ id: 'btn-showcase-size-lg', expected: 'lg' },
			{ id: 'btn-showcase-size-icon-xs', expected: 'icon-xs' },
			{ id: 'btn-showcase-size-icon-sm', expected: 'icon-sm' },
			{ id: 'btn-showcase-size-icon', expected: 'icon' },
			{ id: 'btn-showcase-size-icon-lg', expected: 'icon-lg' }
		];
		for (const { id, expected } of sizes) {
			const el = page.getByTestId(id);
			await expect(el).toBeVisible();
			await expect(el).toHaveAttribute('data-size', expected);
		}
	});

	test('AC-5 + AC-6: href-Switch + WAI-ARIA disabled-Link Pattern', async ({ page }) => {
		// Default = primary = <button>
		const variant = page.getByTestId('btn-showcase-variant-primary');
		await expect(variant).toHaveJSProperty('tagName', 'BUTTON');

		// href-Btn rendert als <a>
		const link = page.getByTestId('btn-showcase-state-link');
		await expect(link).toHaveJSProperty('tagName', 'A');

		// href + disabled: kein href im DOM, WAI-ARIA-Pattern
		const disabledLink = page.getByTestId('btn-showcase-state-link-disabled');
		await expect(disabledLink).toHaveJSProperty('tagName', 'A');
		const hrefAttr = await disabledLink.getAttribute('href');
		expect(hrefAttr).toBeNull();
		await expect(disabledLink).toHaveAttribute('aria-disabled', 'true');
		await expect(disabledLink).toHaveAttribute('tabindex', '-1');
		await expect(disabledLink).toHaveAttribute('role', 'link');
	});

	test('AC-7 + AC-8: <button> + disabled hat natives disabled-Attribut und sichtbar reduzierte Opacity', async ({
		page
	}) => {
		const disabled = page.getByTestId('btn-showcase-state-disabled');
		await expect(disabled).toBeDisabled();
		const opacity = await disabled.evaluate((el) => parseFloat(getComputedStyle(el).opacity));
		expect(opacity).toBeLessThan(1);
	});

	test('AC-9 + AC-10: SVG-Icon-Sizing pro Size (md=16px, lg=18px)', async ({ page }) => {
		const md = page.getByTestId('btn-showcase-size-md').locator('svg').first();
		const mdBox = await md.boundingBox();
		expect(mdBox).not.toBeNull();
		expect(Math.round(mdBox!.width)).toBe(16);
		expect(Math.round(mdBox!.height)).toBe(16);

		const lg = page.getByTestId('btn-showcase-size-lg').locator('svg').first();
		const lgBox = await lg.boundingBox();
		expect(lgBox).not.toBeNull();
		expect(Math.round(lgBox!.width)).toBe(18);
		expect(Math.round(lgBox!.height)).toBe(18);
	});

	test('AC-11: icon-sm ist quadratisch 28x28', async ({ page }) => {
		const el = page.getByTestId('btn-showcase-size-icon-sm');
		const box = await el.boundingBox();
		expect(box).not.toBeNull();
		expect(Math.round(box!.width)).toBe(28);
		expect(Math.round(box!.height)).toBe(28);
	});

	test('AC-14 + AC-15 + AC-16: Variant-Tokens (primary=ink+paper, destructive=danger+danger, accent=accent)', async ({
		page
	}) => {
		// Erwartete Token-Werte aus app.css (Light-Mode-Default, gelesen am 2026-05-13):
		// --g-ink: #1a1a18, --g-paper: #f6f4ee, --g-accent: #c45a2a, --g-danger: #b33a2a
		// Browser rendert als rgb(...). Die Werte sind realer als die in der Spec
		// genannten Beispiel-Tokens (Spec war veraltet, app.css ist Quelle der Wahrheit).
		const inkRgb = 'rgb(26, 26, 24)';
		const paperRgb = 'rgb(246, 244, 238)';
		const accentRgb = 'rgb(196, 90, 42)';
		const dangerRgb = 'rgb(179, 58, 42)';

		const primary = page.getByTestId('btn-showcase-variant-primary');
		const pBg = await primary.evaluate((el) => getComputedStyle(el).backgroundColor);
		const pColor = await primary.evaluate((el) => getComputedStyle(el).color);
		expect(pBg).toBe(inkRgb);
		expect(pColor).toBe(paperRgb);

		const accent = page.getByTestId('btn-showcase-variant-accent');
		const aBg = await accent.evaluate((el) => getComputedStyle(el).backgroundColor);
		expect(aBg).toBe(accentRgb);

		const destructive = page.getByTestId('btn-showcase-variant-destructive');
		const dColor = await destructive.evaluate((el) => getComputedStyle(el).color);
		const dBorderColor = await destructive.evaluate((el) => getComputedStyle(el).borderTopColor);
		expect(dColor).toBe(dangerRgb);
		expect(dBorderColor).toBe(dangerRgb);
	});

	test('AC-19: Tab-Fokus springt nicht auf disabled-Button und nicht auf disabled-Link', async ({
		page
	}) => {
		// Tab durch die Showcase. Der disabled <button> hat HTML-natives disabled
		// (nicht fokussierbar). Der disabled <a> hat tabindex="-1" (nicht via Tab erreichbar).
		// Wir setzen Focus zuerst auf das nicht-disabled Link, dann Tab.
		const linkBtn = page.getByTestId('btn-showcase-state-link');
		await linkBtn.focus();
		// Tabbing weiter: das naechste Element MUSS nicht "btn-showcase-state-link-disabled" sein
		await page.keyboard.press('Tab');
		const focusedId = await page.evaluate(
			() => (document.activeElement as HTMLElement | null)?.getAttribute('data-testid') ?? null
		);
		expect(focusedId).not.toBe('btn-showcase-state-link-disabled');
		expect(focusedId).not.toBe('btn-showcase-state-disabled');
	});
});
