// Soll/Ist-Bilder #2794 S3a Teil-PR 4b — nur Screenshots, Staging, Wegwerfdaten (E2E-GZ-).
import { test, expect, type Page } from '@playwright/test';
import { cleanupTracked, createTestTrip, seedHub } from './helpers';

const OUT = '/tmp/claude-1000/-home-hem-gregor-zwanzig--claude-worktrees-hashed-plotting-corbato/8723626f-fa9b-43ed-badd-c356c0d53832/scratchpad/bilder/roh';
const MOCKUP = 'file:///home/hem/gregor_zwanzig/.claude/worktrees/hashed-plotting-corbato/docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html';
const GERAETE = { desktop: { width: 1280, height: 900 }, handy: { width: 390, height: 844 } } as const;

test.setTimeout(400_000);

/** Ganze Seite inkl. inneren Scroll-Container: Viewport auf die volle Inhaltshöhe ziehen. */
async function vollbild(page: Page, pfad: string, geraet: 'desktop' | 'handy') {
	const h = await page.evaluate(() => {
		let m = document.documentElement.scrollHeight;
		for (const el of Array.from(document.querySelectorAll('*'))) {
			const e = el as HTMLElement;
			if (e.scrollHeight > e.clientHeight + 20 && getComputedStyle(e).overflowY.match(/auto|scroll/)) {
				m = Math.max(m, e.scrollHeight + e.getBoundingClientRect().top);
			}
		}
		return Math.ceil(m);
	});
	await page.setViewportSize({ width: GERAETE[geraet].width, height: Math.min(Math.max(h, GERAETE[geraet].height), 6000) });
	await page.waitForTimeout(800);
	await page.screenshot({ path: pfad, fullPage: true });
	await page.setViewportSize(GERAETE[geraet]);
}

async function mockup(page: Page, ctx: 'trip' | 'orte', geraet: 'desktop' | 'handy') {
	await page.setViewportSize(GERAETE[geraet]);
	await page.goto(MOCKUP);
	await page.locator(`[data-ctx="${ctx}"]`).click();
	await page.locator('#tabs [data-tab="uebersicht"]').click();
	await page.addStyleTag({ content: '.frame,.fb{display:none!important}' });
	await page.waitForTimeout(400);
	await page.screenshot({ path: `${OUT}/soll-${ctx}-${geraet}.png`, fullPage: true });
}

test('Bilder', async ({ page }) => {
	// Soll
	for (const ctx of ['trip', 'orte'] as const) for (const g of ['desktop', 'handy'] as const) await mockup(page, ctx, g);

	// Ist
	const heute = new Date();
	const tag = (n: number) => new Date(heute.getTime() + n * 86400000).toISOString().slice(0, 10);
	const tripId = `e2e-gz-trip-${Date.now()}`;
	const stages = [0, 1, 2].map((i) => ({
		id: `${tripId}-s${i + 1}`,
		name: `Etappe ${i + 1}`,
		date: tag(i),
		waypoints: [
			{ id: `${tripId}-w${i}a`, name: `Start ${i + 1}`, lat: 42.1 + i * 0.05, lon: 9.0, elevation_m: 500 + i * 200 },
			{ id: `${tripId}-w${i}b`, name: `Ziel ${i + 1}`, lat: 42.13 + i * 0.05, lon: 9.03, elevation_m: 900 + i * 200 }
		]
	}));
	const { id } = await createTestTrip(page.request, { id: tripId, stages });
	const hub = await seedHub(page.request, 'vergleich');
	try {
		for (const g of ['desktop', 'handy'] as const) {
			await page.setViewportSize(GERAETE[g]);
			// (1) Trip-Hub Übersicht
			await page.goto(`/trips/${id}?tab=uebersicht`);
			await expect(page.locator('[data-testid="hub-overview"]:visible').first()).toBeVisible({ timeout: 20_000 });
			await page.waitForTimeout(2500);
			await expect(page.getByText('Übersicht', { exact: true }).locator('visible=true').first()).toBeVisible();
			await vollbild(page, `${OUT}/ist-trip-uebersicht-${g}.png`, g);
			// (2) Orts-Briefing-Hub Übersicht
			await page.goto(`/compare/${hub.id}?tab=uebersicht`);
			await expect(page.locator('[data-testid="compare-detail-panel-uebersicht"]:visible').first()).toBeVisible({ timeout: 20_000 });
			await page.waitForTimeout(2500);
			await expect(page.getByText('Übersicht', { exact: true }).locator('visible=true').first()).toBeVisible();
			await vollbild(page, `${OUT}/ist-orte-uebersicht-${g}.png`, g);
			// (3) Trip-Liste mit Menü
			await page.goto('/trips');
			if (g === 'handy') {
				await page.getByTestId(`subscription-card-menu-${id}`).click();
				await expect(page.getByTestId('subscription-action-weather').locator('visible=true').first()).toBeVisible();
			} else {
				const zeile = page.getByTestId(`trip-row-${id}`).locator('visible=true').first();
				await zeile.scrollIntoViewIfNeeded();
				await zeile.getByTestId('trip-row-menu-btn').click();
				await expect(page.getByRole('menu')).toBeVisible();
			}
			await page.waitForTimeout(600);
			await page.screenshot({ path: `${OUT}/ist-trip-liste-menue-${g}.png` });
			await page.keyboard.press('Escape');
			// (4) Orts-Liste mit Menü
			await page.goto('/compare');
			if (g === 'handy') {
				await page.getByTestId(`subscription-card-menu-${hub.id}`).click();
				await expect(page.getByTestId('subscription-action-weather').locator('visible=true').first()).toBeVisible();
			} else {
				const zeile = page.getByTestId(`compare-tile-${hub.id}`).locator('visible=true').first();
				await zeile.scrollIntoViewIfNeeded();
				await zeile.getByTestId('compare-row-kebab').click();
				await expect(page.getByRole('menu')).toBeVisible();
			}
			await page.waitForTimeout(600);
			await page.screenshot({ path: `${OUT}/ist-orte-liste-menue-${g}.png` });
			await page.keyboard.press('Escape');
		}
	} finally {
		await hub.aufraeumen().catch(() => {});
		await cleanupTracked(page.request).catch(() => {});
		await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
	}
});

test('Aufräumcheck', async ({ page }) => {
	const p = await (await page.request.get('/api/compare/presets')).json();
	const t = await (await page.request.get('/api/trips')).json();
	const liste = (x: unknown) => (Array.isArray(x) ? x : ((x as Record<string, unknown>).presets ?? (x as Record<string, unknown>).trips ?? [])) as { id: string; name: string }[];
	console.log('PRESETS', JSON.stringify(liste(p).filter((x) => /E2E-GZ-/.test(x.name)).map((x) => [x.id, x.name])));
	console.log('TRIPS', JSON.stringify(liste(t).filter((x) => /E2E-GZ-/.test(x.name)).map((x) => [x.id, x.name])));
	const prof = await (await page.request.get('/api/auth/profile')).json();
	console.log('SPRACHE', prof.language);
});
