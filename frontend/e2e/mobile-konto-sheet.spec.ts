// E2E — Mobile-Shell S2: Konto-Kreis neben der Tabbar oeffnet das Konto-Sheet.
//
// Konzept: docs/design-requests/mobile_shell_ohne_topbar.md (§2 Zielbild,
// §3 Ersatz-Tabelle, §8 PO-Entscheidungen 2026-09-19). Soll: Design-Canvas
// „Gregor Mobile Shell", Artboards „TabBar" und „Konto-Sheet".
//
// Ersetzt den Hamburger-Drawer (mobile-bottom-nav AC-4, issue-725 AC-3):
// kein fixer Balken oben, Konto/Abmelden nur ueber den Konto-Kreis.
//
// Ausführen: cd frontend && npx playwright test e2e/mobile-konto-sheet.spec.ts

import { test, expect } from '@playwright/test';

const MOBILE = { width: 375, height: 667 };
const DESKTOP = { width: 1440, height: 900 };
const NAV_HEIGHT_PX = 64; // --g-nav-h
const SIDE_INSET_PX = 16; // --g-nav-inset

test.describe('Mobile-Shell S2: Konto-Kreis → Konto-Sheet', () => {
	test.beforeEach(async ({ page }) => {
		await page.setViewportSize(MOBILE);
		await page.goto('/');
		await expect(page.getByTestId('bottom-nav')).toBeVisible();
	});

	test('AC-1: Konto-Kreis steht rechts neben der Tabbar, gleiche Hoehe, Initialen sichtbar', async ({ page }) => {
		const kreis = page.getByTestId('konto-kreis');
		await expect(kreis).toBeVisible();
		await expect(kreis).toHaveAttribute('aria-haspopup', 'dialog');
		await expect(kreis).toHaveAttribute('aria-expanded', 'false');
		// Initialen: mindestens ein Zeichen, Grossbuchstaben (kein leerer Kreis)
		await expect(kreis).toHaveText(/^[A-ZÄÖÜ?]{1,2}$/);

		const nav = await page.getByTestId('bottom-nav').boundingBox();
		const box = await kreis.boundingBox();
		expect(nav).not.toBeNull();
		expect(box).not.toBeNull();
		// Rechts neben der Leiste, buendig mit deren Ober-/Unterkante
		expect(box!.x).toBeGreaterThan(nav!.x + nav!.width);
		expect(Math.round(box!.x + box!.width)).toBe(MOBILE.width - SIDE_INSET_PX);
		expect(Math.round(box!.height)).toBe(NAV_HEIGHT_PX);
		expect(Math.round(box!.width)).toBe(NAV_HEIGHT_PX);
		expect(Math.round(box!.y)).toBe(Math.round(nav!.y));

		// Glas wie die Leiste: kein Akzent-Fill auf dem Kreis selbst (AP-012)
		const glas = await kreis.evaluate((el) => {
			const cs = getComputedStyle(el);
			return { background: cs.backgroundColor, radius: parseFloat(cs.borderRadius) };
		});
		expect(glas.background).not.toMatch(/rgb\(196, 90, 42\)/);
		expect(glas.radius).toBeGreaterThanOrEqual(NAV_HEIGHT_PX / 2);
		// Die vier Nav-Ziele bleiben genau vier (Charter §2)
		await expect(page.getByTestId('bottom-nav').locator('a')).toHaveCount(4);
	});

	test('AC-2: Tippen oeffnet das Konto-Sheet mit den sechs Zeilen, ohne Benachrichtigungen', async ({ page }) => {
		await page.getByTestId('konto-kreis').click();
		const sheet = page.getByTestId('konto-sheet');
		await expect(sheet).toBeVisible();
		await expect(page.getByTestId('konto-kreis')).toHaveAttribute('aria-expanded', 'true');

		await expect(sheet.getByTestId('konto-sheet-name')).not.toBeEmpty();
		await expect(sheet.getByTestId('konto-sheet-kanaele')).toHaveAttribute('href', '/account#kanaele');
		await expect(sheet.getByTestId('konto-sheet-einstellungen')).toHaveAttribute('href', '/account');
		await expect(sheet.getByTestId('konto-sheet-status')).toHaveAttribute('href', '/account#system-status');
		await expect(sheet.getByTestId('konto-sheet-dark').getByRole('switch')).toBeVisible();
		await expect(sheet.getByTestId('konto-sheet-export')).toHaveAttribute('href', '/account#datenexport');
		await expect(sheet.getByTestId('konto-sheet-logout')).toHaveText(/Abmelden/);
		// PO 2026-09-19: keine Benachrichtigungen-Zeile, kein roter Punkt
		await expect(sheet).not.toContainText(/Benachrichtigung/);
		await expect(page.getByTestId('top-app-bar')).toHaveCount(0);
		await expect(page.getByTestId('mobile-drawer')).toHaveCount(0);

		// Jede Zeile ist ein echtes Touch-Ziel (>= 44px)
		for (const id of ['konto-sheet-kanaele', 'konto-sheet-einstellungen', 'konto-sheet-status', 'konto-sheet-export']) {
			const b = await sheet.getByTestId(id).boundingBox();
			expect(b, `${id}: keine boundingBox`).not.toBeNull();
			expect(b!.height, `${id}: Zeile unter 44px`).toBeGreaterThanOrEqual(44);
		}
	});

	test('AC-3: Dunkles Design schaltet im Sheet um und bleibt gemerkt', async ({ page }) => {
		await page.getByTestId('konto-kreis').click();
		const schalter = page.getByTestId('konto-sheet-dark').getByRole('switch');
		const vorher = await page.evaluate(() => localStorage.getItem('gz-dark') === '1');
		await schalter.click();
		await expect
			.poll(() => page.evaluate(() => localStorage.getItem('gz-dark') === '1'))
			.toBe(!vorher);
		const dunkel = await page.evaluate(() => document.documentElement.style.getPropertyValue('--color-background') !== '');
		expect(dunkel).toBe(!vorher);
		// Zuruecksetzen, damit Folge-Tests nicht im Dunkelmodus starten
		await schalter.click();
		await expect
			.poll(() => page.evaluate(() => localStorage.getItem('gz-dark') === '1'))
			.toBe(vorher);
	});

	test('AC-4: Backdrop und Schliessen-Knopf schliessen das Sheet; Navigation aus dem Sheet schliesst es ebenfalls', async ({ page }) => {
		await page.getByTestId('konto-kreis').click();
		const sheet = page.getByTestId('konto-sheet');
		await expect(sheet).toBeVisible();
		await sheet.getByRole('button', { name: 'Schließen' }).click();
		await expect(sheet).toHaveCount(0);

		await page.getByTestId('konto-kreis').click();
		await expect(sheet).toBeVisible();
		// Backdrop: Tipp oben links, weit weg vom Sheet
		await page.mouse.click(10, 10);
		await expect(sheet).toHaveCount(0);

		await page.getByTestId('konto-kreis').click();
		await sheet.getByTestId('konto-sheet-einstellungen').click();
		await page.waitForURL('**/account');
		await expect(page.getByTestId('konto-sheet')).toHaveCount(0);
	});

	test('AC-5: Desktop (>= 900px) zeigt weder Konto-Kreis noch Sheet — Konto bleibt am User-Badge der Sidebar', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		await page.goto('/');
		await expect(page.getByTestId('konto-kreis')).toBeHidden();
		await expect(page.getByTestId('konto-sheet')).toHaveCount(0);
		await expect(page.getByTestId('desktop-sidebar')).toBeVisible();
	});

	test('AC-6: Inhalt beginnt oben ohne Balken — main hat nur den Raster-Schritt als oberes Padding', async ({ page }) => {
		const paddingTop = await page
			.locator('main.mobile-scroll-pad')
			.evaluate((el) => parseFloat(getComputedStyle(el).paddingTop));
		// env(safe-area-inset-top) ist im Test-Viewport 0 → nur --g-s-3 (12px)
		expect(paddingTop).toBe(12);
		await expect(page.getByTestId('home-wordmark-row')).toBeVisible();
	});
});
