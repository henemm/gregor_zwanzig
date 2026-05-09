import { test, expect } from '@playwright/test';

/**
 * TDD RED Tests — Epic #133 Lauf B
 * Issues #143 (Topo-Hintergrundmuster), #144 (Atom-Komponenten), #146 (ElevSparkline)
 *
 * Diese Tests MÜSSEN vor der Implementierung ROT sein:
 * - Showcase-Route /_design existiert noch nicht
 * - Atom-Komponenten (Btn, GCard, Pill, Eyebrow, Dot) existieren noch nicht
 * - TopoBg, ElevSparkline existieren noch nicht
 * - .g-topo-Klasse + [data-slot]-Selektoren in app.css fehlen
 */

test.describe('Epic #133 Lauf B — Showcase-Route /_design', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/_design');
	});

	test('Kriterium 11: /_design lädt nach Login (Title sichtbar)', async ({ page }) => {
		/**
		 * GIVEN: User ist eingeloggt (Storage-State aus global.setup.ts)
		 * WHEN: /_design wird aufgerufen
		 * THEN: Seite antwortet 200, Showcase-Title ist sichtbar
		 */
		await expect(page.getByTestId('design-showcase-title')).toBeVisible();
	});

	test('Kriterium 12: /_design ist nicht in Sidebar verlinkt', async ({ page }) => {
		/**
		 * GIVEN: App ist geladen
		 * WHEN: Sidebar-Nav-Items inspiziert werden
		 * THEN: Kein Link href="/_design"
		 */
		await page.goto('/');
		const designLinks = page.locator('nav a[href="/_design"]');
		await expect(designLinks).toHaveCount(0);
	});
});

test.describe('Issue #143 — Topo-Hintergrundmuster', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/_design');
		await expect(page.getByTestId('design-showcase-title')).toBeVisible();
	});

	test('Kriterium 1: .g-topo-Klasse hat radial-gradient als background-image', async ({ page }) => {
		/**
		 * GIVEN: app.css enthält .g-topo-Klasse mit radial-gradient
		 * WHEN: Element mit Klasse .g-topo wird inspiziert
		 * THEN: computed background-image ist nicht 'none'
		 */
		const topo = page.locator('.g-topo').first();
		await expect(topo).toHaveCount(1);
		const bgImage = await topo.evaluate(el => getComputedStyle(el).backgroundImage);
		expect(bgImage).toContain('radial-gradient');
	});

	test('Kriterium 2: <TopoBg opacity={0.06}> setzt --g-topo-opacity', async ({ page }) => {
		/**
		 * GIVEN: TopoBg-Komponente rendert mit opacity={0.06} auf der Showcase
		 * WHEN: Element mit data-slot="topo-bg" inspiziert wird
		 * THEN: CSS Custom Property --g-topo-opacity ist 0.06
		 */
		const topo = page.locator('[data-slot="topo-bg"]');
		await expect(topo).toBeVisible();
		const opacityVar = await topo.evaluate(el =>
			getComputedStyle(el).getPropertyValue('--g-topo-opacity').trim()
		);
		expect(opacityVar).toBe('0.06');
	});
});

test.describe('Issue #144 — Atom-Komponenten', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/_design');
		await expect(page.getByTestId('design-showcase-title')).toBeVisible();
	});

	test('Kriterium 3: <Btn variant="accent"> rendert mit data-slot/data-variant + Text', async ({ page }) => {
		const btn = page.locator('[data-slot="btn"][data-variant="accent"]').first();
		await expect(btn).toBeVisible();
		await expect(btn).toContainText('Speichern');
	});

	test('Kriterium 3b: <Btn variant="ghost"> und variant="outline" rendern', async ({ page }) => {
		const ghost = page.locator('[data-slot="btn"][data-variant="ghost"]');
		const outline = page.locator('[data-slot="btn"][data-variant="outline"]');
		await expect(ghost).toBeVisible();
		await expect(outline).toBeVisible();
	});

	test('Kriterium 4: <Pill tone="success"> rendert mit data-slot/data-tone', async ({ page }) => {
		const pill = page.locator('[data-slot="pill"][data-tone="success"]');
		await expect(pill).toBeVisible();
		await expect(pill).toContainText('OK');
	});

	test('Kriterium 5: <Eyebrow> rendert mit data-slot und nutzt JetBrains Mono', async ({ page }) => {
		const eyebrow = page.locator('[data-slot="eyebrow"]').first();
		await expect(eyebrow).toBeVisible();
		await expect(eyebrow).toContainText('Wetter');
		const fontFamily = await eyebrow.evaluate(el => getComputedStyle(el).fontFamily);
		expect(fontFamily).toContain('JetBrains Mono');
	});

	test('Kriterium 6: <Dot tone="rain"> rendert mit data-slot/data-tone', async ({ page }) => {
		const dot = page.locator('[data-slot="dot"][data-tone="rain"]');
		await expect(dot).toBeVisible();
	});

	test('Kriterium 7: <GCard> rendert mit data-slot="g-card"', async ({ page }) => {
		const card = page.locator('[data-slot="g-card"]');
		await expect(card).toBeVisible();
	});
});

test.describe('Issue #146 — ElevSparkline', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/_design');
		await expect(page.getByTestId('design-showcase-title')).toBeVisible();
	});

	test('Kriterium 8: ElevSparkline rendert SVG mit Polyline für 5 Datenpunkte', async ({ page }) => {
		const svgs = page.locator('[data-slot="elev-sparkline"]');
		await expect(svgs.first()).toBeVisible();
		const first = svgs.nth(0);
		const polyline = first.locator('polyline');
		await expect(polyline).toBeVisible();
		const points = await polyline.getAttribute('points');
		expect(points).not.toBeNull();
		expect(points!.trim().split(/\s+/).length).toBe(5);
	});

	test('Kriterium 9: ElevSparkline rendert SVG ohne Polyline für leeres Array', async ({ page }) => {
		const svgs = page.locator('[data-slot="elev-sparkline"]');
		const empty = svgs.nth(1);
		await expect(empty).toBeVisible();
		const polyline = empty.locator('polyline');
		await expect(polyline).toHaveCount(0);
	});

	test('Kriterium 10: ElevSparkline rendert SVG für Single-Point ohne NaN', async ({ page }) => {
		const svgs = page.locator('[data-slot="elev-sparkline"]');
		const single = svgs.nth(2);
		await expect(single).toBeVisible();
		const polyline = single.locator('polyline');
		// Single-Point: Polyline existiert mit 1 Koordinaten-Paar, kein NaN im points-Attribut
		if (await polyline.count() > 0) {
			const points = await polyline.getAttribute('points');
			expect(points).not.toContain('NaN');
		}
	});
});
