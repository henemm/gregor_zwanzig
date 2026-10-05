import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
// Issue #302 — Labels nach Soll-Mockup. Placeholder-Regex entfernt, weil die
// Inhalte mit Epic #135/137/138/139 längst implementiert sind und die alten
// Skelett-Texte nicht mehr existieren.
// Issue #2287: Reihenfolge und Beschriftungen = shared/subscriptionTabs.ts ('trip').
const TABS = [
	{ value: 'uebersicht', label: 'Übersicht' },
	{ value: 'etappen', label: 'Etappen & Wegpunkte' },
	{ value: 'wetter-metriken', label: 'Wetter-Metriken' },
	{ value: 'wertebereiche', label: 'Wertebereiche' },
	{ value: 'alarme', label: 'Alarme' },
	{ value: 'versand', label: 'Versand' },
	{ value: 'vorschau', label: 'Vorschau' }
];

test.describe('Issue #155 — Trip-Detail Tab-Navigation', () => {
	test('AC-1: 7 Tabs in fester Reihenfolge sichtbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const list = page.getByTestId('trip-detail-tab-list');
		await expect(list).toBeVisible();
		for (const tab of TABS) {
			const trigger = page.getByTestId(`trip-detail-tab-${tab.value}`);
			await expect(trigger).toBeVisible();
			await expect(trigger).toContainText(tab.label);
		}
	});

	test('AC-2: ohne URL-Hash → Übersicht ist aktiv', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const overview = page.getByTestId('trip-detail-tab-uebersicht');
		await expect(overview).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-detail-panel-uebersicht')).toBeVisible();
	});

	test('AC-3: Klick auf "Etappen" wechselt aktiv + URL ?tab=etappen + Panel sichtbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-etappen').click();
		await expect(page.getByTestId('trip-detail-tab-etappen')).toHaveAttribute('data-state', 'active');
		await expect(page).toHaveURL(/[?&]tab=etappen$/);
		const panel = page.getByTestId('trip-detail-panel-etappen');
		await expect(panel).toBeVisible();
	});

	test('AC-4: Aufruf mit ?tab=wertebereiche → Alerts-Tab initial aktiv (Bug #534 — Issue #516)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}?tab=wertebereiche`);
		await expect(page.getByTestId('trip-detail-tab-wertebereiche')).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-detail-panel-wertebereiche')).toBeVisible();
	});

	test('AC-5: Aktiver Tab hat sichtbare Unterstreichung in --g-accent', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const overview = page.getByTestId('trip-detail-tab-uebersicht');
		const borderBottomColor = await overview.evaluate(
			(el) => getComputedStyle(el).borderBottomColor
		);
		// accent-Token ist #c45a2a → rgb(196, 90, 42)
		expect(borderBottomColor).toMatch(/rgb\(196,\s*90,\s*42\)|rgba\(196,\s*90,\s*42/);

		const stages = page.getByTestId('trip-detail-tab-etappen');
		const inactiveBorder = await stages.evaluate((el) => getComputedStyle(el).borderBottomColor);
		expect(inactiveBorder).not.toMatch(/rgb\(196,\s*90,\s*42\)/);
	});

	test('AC-6/AC-7: Badge-Slot — Tabs ohne Inhalt rendern KEIN Badge', async ({
		page
	}) => {
		// Issue #302: stages + alerts haben jetzt Auto-Badges (Etappenanzahl +
		// enabled Alert-Rules). Die anderen Tabs dürfen weiterhin kein Badge zeigen.
		await page.goto(`/trips/${TRIP_ID}`);
		for (const tab of TABS) {
			if (tab.value === 'etappen' || tab.value === 'wertebereiche') continue;
			const badge = page.getByTestId(`trip-detail-tab-badge-${tab.value}`);
			await expect(badge).toHaveCount(0);
		}
	});

	test('AC-8: Unbekannte Trip-ID → 404', async ({ page }) => {
		const response = await page.goto('/trips/unknown-id-does-not-exist');
		expect(response?.status()).toBe(404);
	});

	test('AC-9: Tastatur-Navigation mit ArrowRight wechselt Fokus', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const overview = page.getByTestId('trip-detail-tab-uebersicht');
		await overview.focus();
		await page.keyboard.press('ArrowRight');
		const focused = await page.evaluate(() =>
			document.activeElement?.getAttribute('data-testid')
		);
		expect(focused).toBe('trip-detail-tab-etappen');
	});

	test('Badge-Guard: badges={alerts: 0} rendert KEINE Badge (>= 1 Regel, Spec §2)', async () => {
		// Source-Scan-Assertion: garantiert, dass das Template den Wert 0 ausschließt.
		// Component-Mounting-Test wäre Overhead, da +page.svelte heute badges={} hart übergibt.
		const fs = await import('fs');
		const source = fs.readFileSync(
			new URL('../src/lib/components/trip-detail/TripTabs.svelte', import.meta.url),
			'utf-8'
		);
		// Anti-Pattern (zu schwach): badges[X] !== undefined
		expect(source).not.toMatch(/badges\[[^\]]+\]\s*!==\s*undefined/);
		// Erforderlich: >= 1-Bedingung (mit oder ohne ?? 0 Default)
		expect(source).toMatch(
			/badges\[[^\]]+\]\s*\?\?\s*0\)\s*>=\s*1|badges\[[^\]]+\]\s*>=?\s*1/
		);
	});

	test('Screenshot der Tab-Navigation für visuelle Verifikation', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.waitForSelector('[data-testid="trip-detail-tab-list"]');
		await page.screenshot({
			path: '../docs/artifacts/epic-135-step1-tab-navigation/screenshot-tabs-overview.png',
			fullPage: false
		});
		await page.goto(`/trips/${TRIP_ID}?tab=wertebereiche`);
		await page.waitForSelector('[data-testid="trip-detail-panel-wertebereiche"]');
		await page.screenshot({
			path: '../docs/artifacts/epic-135-step1-tab-navigation/screenshot-tabs-alerts.png',
			fullPage: false
		});
	});
});
