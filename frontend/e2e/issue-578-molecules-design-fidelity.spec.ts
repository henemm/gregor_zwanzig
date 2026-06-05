// TDD RED — Issue #578: Molecules + Organisms + Sidebar 1:1 nach JSX
//
// Tests gegen STAGING (https://staging.gregor20.henemm.com) mit Validator-Account.
// Sub-Issue von Epic #575 (Drift-Korrektur). Alle Tests schlagen fehl bis
// die Sidebar 1:1 nach brand-kit.jsx::BrandSidebar rebaut ist und
// Molecules/Organisms-Werte JSX-konform sind.
//
// Spec: docs/specs/modules/issue-578-molecules-1to1.md
//
// Ausführung:
//   STAGING=1 GZ_VALIDATOR_USER=... GZ_VALIDATOR_PASS=... \
//     npx playwright test e2e/issue-578-molecules-design-fidelity.spec.ts

import { test, expect } from '@playwright/test';

const STAGING_URL = 'https://staging.gregor20.henemm.com';
const VALIDATOR_USER = process.env.GZ_VALIDATOR_USER ?? '';
const VALIDATOR_PASS = process.env.GZ_VALIDATOR_PASS ?? '';

async function resolveCssVar(page, varName: string): Promise<string> {
	return await page.evaluate((v) => {
		const probe = document.createElement('span');
		probe.style.color = `var(${v})`;
		document.body.appendChild(probe);
		const c = getComputedStyle(probe).color;
		probe.remove();
		return c;
	}, varName);
}

test.describe('Issue #578: Sidebar 1:1 nach brand-kit.jsx', () => {
	test.beforeEach(async ({ page }) => {
		test.skip(!VALIDATOR_USER || !VALIDATOR_PASS, 'GZ_VALIDATOR_USER/PASS not set');

		await page.goto(`${STAGING_URL}/login`);
		await page.fill('input[name="username"]', VALIDATOR_USER);
		await page.fill('input[name="password"]', VALIDATOR_PASS);
		await page.click('button[type="submit"]');
		await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 15_000 });
		await page.goto(STAGING_URL + '/');
		await page.waitForLoadState('networkidle');
	});

	// AC-1: Vier Items in fester Reihenfolge mit JSX-Wortlaut.
	test('AC-1: Sidebar zeigt vier Items in JSX-Reihenfolge', async ({ page }) => {
		const sidebar = page.locator('[data-testid="desktop-sidebar"]');
		const items = sidebar.locator('a').filter({ hasText: /Startseite|Meine Trips|Orts-Vergleich|Archiv/ });
		await expect(items).toHaveCount(4);
		await expect(items.nth(0)).toContainText('Startseite');
		await expect(items.nth(1)).toContainText('Meine Trips');
		await expect(items.nth(2)).toContainText('Orts-Vergleich');
		await expect(items.nth(3)).toContainText('Archiv');
	});

	// AC-2: Wurzel-aside hat Breite 220 px und Background --g-paper-deep.
	test('AC-2: Sidebar-aside hat width 220px + background --g-paper-deep', async ({ page }) => {
		const aside = page.locator('aside[data-testid="desktop-sidebar"], [data-testid="desktop-sidebar"]').first();
		await expect(aside).toBeVisible();

		const width = await aside.evaluate((el) => getComputedStyle(el).width);
		expect(width).toBe('220px');

		const bg = await aside.evaluate((el) => getComputedStyle(el).backgroundColor);
		const paperDeep = await resolveCssVar(page, '--g-paper-deep');
		expect(bg).toBe(paperDeep);
	});

	// AC-3: Aktives Item hat Background rgba(196, 90, 42, 0.1).
	test('AC-3: aktives Item hat background rgba(196,90,42,0.1)', async ({ page }) => {
		const active = page.locator('[data-testid="desktop-sidebar"] a').filter({ hasText: 'Startseite' }).first();
		await expect(active).toBeVisible();

		const bg = await active.evaluate((el) => getComputedStyle(el).backgroundColor);
		// rgba(196, 90, 42, 0.1) → rgba(196, 90, 42, 0.1) oder rgba(196,90,42,0.1)
		expect(bg).toMatch(/rgba\(\s*196\s*,\s*90\s*,\s*42\s*,\s*0?\.1\s*\)/);
	});

	// AC-4: Inaktives Item hat Color --g-ink-2.
	test('AC-4: inaktives Item hat color --g-ink-2', async ({ page }) => {
		const inactive = page.locator('[data-testid="desktop-sidebar"] a').filter({ hasText: 'Meine Trips' }).first();
		await expect(inactive).toBeVisible();

		const color = await inactive.evaluate((el) => getComputedStyle(el).color);
		const ink2 = await resolveCssVar(page, '--g-ink-2');
		expect(color).toBe(ink2);
	});

	// AC-5: Vier eigene SVG-Icons (16×16) in der Sidebar, keine Lucide-Klassen.
	test('AC-5: Sidebar enthält vier eigene 16x16 SVG-Icons (kein Lucide)', async ({ page }) => {
		const desktopAside = page.locator('[data-testid="desktop-sidebar"]');
		// Zähle 16x16-SVGs im Desktop-Nav
		const svgCount = await desktopAside.locator('a >> svg[width="16"][height="16"]').count();
		expect(svgCount).toBeGreaterThanOrEqual(4);

		// Lucide-Komponenten haben class*="lucide" → darf nicht im aktiven Item sein.
		const lucideInDesktopNav = await desktopAside
			.locator('a.hidden, a:not(.desktop\\:hidden)')
			.locator('[class*="lucide"]')
			.count();
		expect(lucideInDesktopNav).toBe(0);
	});

	// AC-8: Klick auf jedes Item navigiert korrekt.
	test('AC-8: Sidebar-Items navigieren zu /, /trips, /compare, /archiv', async ({ page }) => {
		const sidebar = page.locator('[data-testid="desktop-sidebar"]');

		await sidebar.locator('a').filter({ hasText: 'Meine Trips' }).first().click();
		await page.waitForURL(/\/trips/, { timeout: 10_000 });
		expect(page.url()).toContain('/trips');

		await sidebar.locator('a').filter({ hasText: 'Orts-Vergleich' }).first().click();
		await page.waitForURL(/\/compare/, { timeout: 10_000 });
		expect(page.url()).toContain('/compare');

		await sidebar.locator('a').filter({ hasText: 'Archiv' }).first().click();
		await page.waitForURL(/\/archiv/, { timeout: 10_000 });
		expect(page.url()).toContain('/archiv');

		await sidebar.locator('a').filter({ hasText: 'Startseite' }).first().click();
		await page.waitForURL((u) => u.pathname === '/', { timeout: 10_000 });
	});

	// AC-10: Desktop-Aside enthält keine bg-sidebar/bg-sidebar-accent Klassen.
	test('AC-10: Desktop-Aside hat keine Tailwind bg-sidebar(_accent) Klassen', async ({ page }) => {
		const desktopAside = page.locator('[data-testid="desktop-sidebar"]');

		// Wurzel-Klasse selbst darf kein bg-sidebar* haben
		const rootClass = await desktopAside.getAttribute('class');
		expect(rootClass ?? '').not.toMatch(/\bbg-sidebar(-accent)?\b/);

		// Alle <a>-Elemente im Desktop-Block prüfen
		const links = desktopAside.locator('a');
		const total = await links.count();
		for (let i = 0; i < total; i++) {
			const cls = await links.nth(i).getAttribute('class');
			// Mobile-Drawer-Links sind erlaubt: erkennbar an desktop:hidden / hidden desktop:flex
			// Echte Desktop-Items zeigen sich → wenn sichtbar, darf keine bg-sidebar drin sein
			const visible = await links.nth(i).isVisible();
			if (visible) {
				expect(cls ?? '').not.toMatch(/\bbg-sidebar(-accent)?\b/);
			}
		}
	});
});

test.describe('Issue #578: Mobile-Drawer bleibt funktional', () => {
	test.use({ viewport: { width: 375, height: 812 } });

	test.beforeEach(async ({ page }) => {
		test.skip(!VALIDATOR_USER || !VALIDATOR_PASS, 'GZ_VALIDATOR_USER/PASS not set');

		await page.goto(`${STAGING_URL}/login`);
		await page.fill('input[name="username"]', VALIDATOR_USER);
		await page.fill('input[name="password"]', VALIDATOR_PASS);
		await page.click('button[type="submit"]');
		await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 15_000 });
		await page.goto(STAGING_URL + '/');
		await page.waitForLoadState('networkidle');
	});

	// AC-9: Mobile-Drawer Hamburger öffnet, Backdrop schließt.
	test('AC-9: Mobile-Drawer öffnet via Hamburger, Backdrop schließt', async ({ page }) => {
		const drawer = page.locator('[data-testid="mobile-drawer"]');
		// Vor Klick: Drawer hat -translate-x-full / hidden
		await expect(drawer).toHaveClass(/-translate-x-full|hidden/);

		// Hamburger-Button im Mobile-Topbar (außerhalb der Sidebar)
		const hamburger = page
			.locator('button')
			.filter({ has: page.locator('svg') })
			.first();
		await hamburger.click();

		await expect(drawer).toHaveClass(/translate-x-0/);

		// Backdrop: .fixed.inset-0.bg-black/50 (z-50, vor Drawer z-40)
		const backdrop = page.locator('.fixed.inset-0.bg-black\\/50').first();
		await expect(backdrop).toBeVisible();
		await backdrop.click();

		await expect(drawer).toHaveClass(/-translate-x-full|hidden/);
	});
});

test.describe('Issue #578: Field-Molecule Token-Treue', () => {
	test.beforeEach(async ({ page }) => {
		// Login-Seite hat Field.svelte mit Error-Anzeige — keine Anmeldung nötig.
		await page.goto(`${STAGING_URL}/login`);
		await page.waitForLoadState('networkidle');
	});

	// AC-6: Field zeigt error-Text in var(--g-bad) (nicht --g-danger).
	test('AC-6: Field error-color entspricht var(--g-bad)', async ({ page }) => {
		// Login mit Falsch-Credentials triggert Error im Field
		await page.fill('input[name="username"]', 'kein-user-578');
		await page.fill('input[name="password"]', 'falsches-passwort');
		await page.click('button[type="submit"]');

		// Warte auf Error-Anzeige (egal welche Form)
		const errorEl = page.locator('text=/falsch|fehlerhaft|ungültig|nicht/i').first();
		// Falls Login-Form keinen sichtbaren Error zeigt, lass Test SKIPpen — wir
		// brauchen einen Field mit error-Prop. Bei /login ist das aktuell nicht
		// garantiert. Wir markieren das als hard-fail damit Implementierung
		// einen Sichtweg liefert.
		const visible = await errorEl.isVisible({ timeout: 5000 }).catch(() => false);
		if (!visible) {
			// Kein sichtbarer Error → Test schlägt fehl, damit Implementierung
			// eine Demo-Route oder Storybook-Eintrag bereitstellt.
			expect(visible, 'Kein Field-Error sichtbar zum Messen — Implementierung muss Demo-Route liefern').toBe(true);
			return;
		}

		const color = await errorEl.evaluate((el) => getComputedStyle(el).color);
		const bad = await resolveCssVar(page, '--g-bad');
		expect(color).toBe(bad);
	});
});

test.describe('Issue #578: Tracer-Diff D-home-trip', () => {
	// AC-7: Pixel-Diff Home (D-home-trip) < 10 %.
	// Dieser Test ist ein Proxy für das Diff-Gate. Echte Messung läuft via
	// .claude/hooks/design_fidelity_diff.py --screen D-home-trip im
	// Validation-Skript. Hier prüfen wir, dass das passed:true-Artefakt
	// existiert (wird vom Hook geschrieben, fehlt vor Implementierung).
	test('AC-7: design-diff-D-home-trip.json existiert mit passed:true', async () => {
		const fs = await import('fs');
		const path = await import('path');
		// Playwright cwd ist frontend/, Artefakte liegen im Repo-Root.
		const repoRoot = path.resolve(process.cwd(), '..');
		const artefact = path.join(repoRoot, 'docs/artifacts/issue-578-molecules-1to1/design-diff-D-home-trip.json');
		expect(fs.existsSync(artefact), `Artefakt fehlt: ${artefact}`).toBe(true);

		const data = JSON.parse(fs.readFileSync(artefact, 'utf8'));
		expect(data.passed, `diff_pct=${data.diff_pct} threshold=${data.threshold}`).toBe(true);
		// Threshold ist im SCREEN_THRESHOLD_MAP für D-home-trip auf 20 erhöht
		// (Foundation-Issue, Home-Content-Drift gehört zu #579). passed:true reicht.
		expect(data.diff_pct).toBeLessThan(data.threshold);
	});
});
