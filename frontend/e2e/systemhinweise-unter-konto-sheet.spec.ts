// E2E — Issue #2370 (Mobile-Audit 2026-09-19, P1-1): die Systemhinweise am
// unteren Rand (iOS-Install, Update, Passkey-Angebot) duerfen nie ueber dem
// offenen Konto-Sheet liegen und dessen Zeilen verdecken.
//
// Spec: docs/specs/modules/systemhinweise_unter_konto_sheet.md, AC-1..AC-5.
//
// Laeuft im Playwright-Projekt `tests` (Dateiname passt nicht auf
// /pwa-.*\.spec\.ts/, Service Worker daher geblockt) — der iOS-Hinweis
// braucht keinen aktiven Worker, nur UA + `display-mode`.
//
// Ausfuehren: cd frontend && npx playwright test e2e/systemhinweise-unter-konto-sheet.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';

// Vorlage: e2e/pwa-update-und-abmelden.spec.ts:802 (iosKontext/IOS_SAFARI_UA).
const IOS_SAFARI_UA =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 ' +
	'(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

const VIEWPORT_A = { width: 390, height: 844 };
const VIEWPORT_B = { width: 375, height: 667 };

// Vorlage: e2e/mobile-konto-sheet.spec.ts:56ff.
const SHEET_ZEILEN = [
	'konto-sheet-kanaele',
	'konto-sheet-einstellungen',
	'konto-sheet-status',
	'konto-sheet-dark',
	'konto-sheet-export',
	'konto-sheet-logout'
];

test.beforeEach(({ baseURL }) => {
	assertNotProdBaseURL(baseURL ?? '');
});

/** Oeffnet '/' unter iOS-Safari-Bedingungen und wartet auf den faelligen Hinweis. */
async function gotoMitFaelligemHinweis(page: Page) {
	await page.goto('/');
	const hinweis = page.getByTestId('ios-install-hint');
	await expect(hinweis).toBeVisible({ timeout: 15_000 });
	return hinweis;
}

/**
 * Prueft je Testid, ob `document.elementFromPoint` an der Mitte der
 * `getBoundingClientRect()` innerhalb der Zeile selbst landet (also nicht auf
 * einem darueberliegenden Hinweis/Backdrop).
 */
async function erwarteZeileKlickbar(page: Page, testid: string) {
	const treffer = await page.evaluate((id: string) => {
		const zeile = document.querySelector(`[data-testid="${id}"]`);
		if (!zeile) return { ok: false, hitTestid: null, hitTag: 'ZEILE FEHLT IM DOM' };
		const rect = zeile.getBoundingClientRect();
		const cx = rect.left + rect.width / 2;
		const cy = rect.top + rect.height / 2;
		const hit = document.elementFromPoint(cx, cy);
		return {
			ok: hit !== null && hit.closest(`[data-testid="${id}"]`) !== null,
			hitTestid: hit?.getAttribute('data-testid') ?? null,
			hitTag: hit?.tagName ?? 'KEIN TREFFER'
		};
	}, testid);
	expect(
		treffer.ok,
		`${testid}: am Mittelpunkt getroffen wurde stattdessen ` +
			`testid="${treffer.hitTestid}" (${treffer.hitTag})`
	).toBe(true);
}

test.describe('Issue #2370: Rand-Hinweise unter dem Konto-Sheet', () => {
	test.use({ userAgent: IOS_SAFARI_UA, viewport: VIEWPORT_A });

	test('AC-1: bei offenem Konto-Sheet ist der iOS-Install-Hinweis nicht mehr im DOM', async ({
		page
	}) => {
		const hinweis = await gotoMitFaelligemHinweis(page);

		await page.getByTestId('konto-kreis').click();
		const sheet = page.getByTestId('konto-sheet');
		await expect(sheet).toBeVisible();

		await expect(hinweis).toHaveCount(0);
	});

	test('AC-3: unveraendert weggelassener Hinweis kehrt nach dem Schliessen des Sheets zurueck', async ({
		page
	}) => {
		const hinweis = await gotoMitFaelligemHinweis(page);

		await page.getByTestId('konto-kreis').click();
		const sheet = page.getByTestId('konto-sheet');
		await expect(sheet).toBeVisible();
		await expect(hinweis).toHaveCount(0);

		await sheet.getByRole('button', { name: 'Schließen' }).click();
		await expect(sheet).toHaveCount(0);

		await expect(page.getByTestId('ios-install-hint')).toBeVisible();
		expect(
			await page.evaluate(() => localStorage.getItem('gz-ios-install-hint')),
			'der Merker wurde durch das blosse Ausblenden gesetzt'
		).toBeNull();
	});

	test('AC-4: der Rand-Hinweis liegt unter der Sheet-Ebene (z-Index < 60)', async ({ page }) => {
		const hinweis = await gotoMitFaelligemHinweis(page);

		const zIndex = await hinweis.evaluate((el) => parseInt(getComputedStyle(el).zIndex, 10));
		expect(zIndex).toBeLessThan(60);
	});

	test('AC-5: ueber "Schliessen" abgewiesener Hinweis bleibt auch nach einem Sheet-Zyklus weg', async ({
		page
	}) => {
		const hinweis = await gotoMitFaelligemHinweis(page);

		await hinweis.getByRole('button', { name: 'Schließen' }).click();
		await expect(hinweis).toHaveCount(0);

		await page.getByTestId('konto-kreis').click();
		const sheet = page.getByTestId('konto-sheet');
		await expect(sheet).toBeVisible();
		await sheet.getByRole('button', { name: 'Schließen' }).click();
		await expect(sheet).toHaveCount(0);

		await expect(page.getByTestId('ios-install-hint')).toHaveCount(0);
	});
});

for (const viewport of [VIEWPORT_A, VIEWPORT_B]) {
	test.describe(`AC-2 @ ${viewport.width}x${viewport.height}`, () => {
		test.use({ userAgent: IOS_SAFARI_UA, viewport });

		test(`AC-2: alle sechs Sheet-Zeilen bleiben bei ${viewport.width}x${viewport.height} klickbar, kein Hinweis dazwischen`, async ({
			page
		}) => {
			await gotoMitFaelligemHinweis(page);

			await page.getByTestId('konto-kreis').click();
			const sheet = page.getByTestId('konto-sheet');
			await expect(sheet).toBeVisible();

			for (const testid of SHEET_ZEILEN) {
				await erwarteZeileKlickbar(page, testid);
			}
		});
	});
}
