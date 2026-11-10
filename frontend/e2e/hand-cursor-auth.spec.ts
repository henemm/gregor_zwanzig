import { test, expect, type Page } from '@playwright/test';

/**
 * Issue #2621 — Hand-Cursor auf klickbaren Knoepfen.
 *
 * Tailwind v4 setzt im Preflight fuer <button> `cursor: default`. Rohe Knoepfe ohne eigene
 * Cursor-Regel (alle Auth-Seiten, viele Stellen in der App) zeigen dadurch keine Hand.
 * Gemessen wird der BERECHNETE Cursor im echten Browser (getComputedStyle), nicht der Dateiinhalt.
 *
 *   cd frontend && npx playwright test e2e/hand-cursor-auth.spec.ts
 */

const cursorVon = (page: Page, selektor: string) =>
	page.locator(selektor).first().evaluate((el) => getComputedStyle(el).cursor);

/** Cursor aller sichtbaren, aktiven Knoepfe der Seite: [Beschriftung, Cursor][] */
async function cursorAktiverKnoepfe(page: Page): Promise<Array<[string, string]>> {
	return page.$$eval('button, [role="button"]', (els) =>
		els
			.filter((el) => {
				const r = el.getBoundingClientRect();
				const sichtbar = r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
				const gesperrt =
					(el as HTMLButtonElement).disabled === true || el.getAttribute('aria-disabled') === 'true';
				return sichtbar && !gesperrt;
			})
			.map((el) => [(el.textContent ?? '').trim().slice(0, 40) || el.outerHTML.slice(0, 60), getComputedStyle(el).cursor]),
	);
}

test.describe('#2621 Auth-Seiten ohne Login', () => {
	test.use({ storageState: { cookies: [], origins: [] } });

	test('AC-1: /verify-email — Bestaetigen-Knopf zeigt die Hand', async ({ page }) => {
		await page.goto('/verify-email?user=e2e-hand-cursor&token=e2e-hand-cursor-token');
		const knopf = page.locator('form button[type="submit"]');
		await expect(knopf).toBeVisible();
		expect(await knopf.evaluate((el) => getComputedStyle(el).cursor)).toBe('pointer');
	});

	const SEITEN = ['/login', '/register', '/forgot-password', '/reset-password?token=e2e-hand-cursor', '/magic-link'];
	for (const pfad of SEITEN) {
		test(`AC-2: ${pfad} — jeder aktive Knopf zeigt die Hand`, async ({ page }) => {
			await page.goto(pfad);
			await expect(page.locator('form button[type="submit"]').first()).toBeVisible();
			const knoepfe = await cursorAktiverKnoepfe(page);
			expect(knoepfe.length, `keine aktiven Knoepfe auf ${pfad}`).toBeGreaterThan(0);
			const ohneHand = knoepfe.filter(([, c]) => c !== 'pointer');
			expect(ohneHand, `Knoepfe ohne Hand auf ${pfad}`).toEqual([]);
		});
	}
});

test.describe('#2621 eingeloggte App', () => {
	// Die Boden-Regel ist global; gemessen wird an Elementen, die in eine echte App-Seite
	// eingesetzt werden — so ist der Nachweis unabhaengig davon, welche Seite gerade welchen
	// rohen Knopf traegt, und laeuft trotzdem gegen das ausgelieferte CSS der App.
	test.beforeEach(async ({ page }) => {
		await page.goto('/');
		await page.evaluate(() => {
			const box = document.createElement('div');
			box.id = 'e2e-hand-cursor';
			box.innerHTML = `
				<button id="hc-roh" type="button">roh</button>
				<div id="hc-rolle" role="button" tabindex="0">rolle</div>
				<input id="hc-feld" type="checkbox" /><label id="hc-label" for="hc-feld">label</label>
				<details><summary id="hc-summary">summary</summary><p>x</p></details>
				<button id="hc-disabled" type="button" disabled>gesperrt</button>
				<button id="hc-aria" type="button" aria-disabled="true">aria-gesperrt</button>
				<div id="hc-rolle-aria" role="button" aria-disabled="true">rolle-gesperrt</div>
				<button id="hc-btn-gesperrt" type="button" data-slot="btn" disabled>atom</button>
				<button id="hc-default" type="button" class="cursor-default">ausnahme</button>
			`;
			document.body.appendChild(box);
		});
	});

	test('AC-3: roher <button> ohne Cursor-Klasse zeigt die Hand', async ({ page }) => {
		expect(await cursorVon(page, '#hc-roh')).toBe('pointer');
	});

	test('AC-3: role="button", label[for] und summary zeigen die Hand', async ({ page }) => {
		expect(await cursorVon(page, '#hc-rolle')).toBe('pointer');
		expect(await cursorVon(page, '#hc-label')).toBe('pointer');
		expect(await cursorVon(page, '#hc-summary')).toBe('pointer');
	});

	test('AC-4: gesperrte Knoepfe (disabled / aria-disabled="true") zeigen keine Hand', async ({ page }) => {
		expect(await cursorVon(page, '#hc-disabled')).not.toBe('pointer');
		expect(await cursorVon(page, '#hc-aria')).not.toBe('pointer');
		expect(await cursorVon(page, '#hc-rolle-aria')).not.toBe('pointer');
	});

	test('AC-5: gesperrtes Btn-Atom behaelt not-allowed', async ({ page }) => {
		expect(await cursorVon(page, '#hc-btn-gesperrt')).toBe('not-allowed');
	});

	test('AC-6: Utility cursor-default gewinnt gegen die Boden-Regel', async ({ page }) => {
		expect(await cursorVon(page, '#hc-default')).toBe('default');
	});
});
