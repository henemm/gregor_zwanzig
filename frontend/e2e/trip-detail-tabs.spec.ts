import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-cockpit-test';
// Issue #302 — Labels nach Soll-Mockup. Placeholder-Regex entfernt, weil die
// Inhalte mit Epic #135/137/138/139 längst implementiert sind und die alten
// Skelett-Texte nicht mehr existieren.
const TABS = [
	{ value: 'overview', label: 'Übersicht' },
	{ value: 'stages', label: 'Etappen' },
	{ value: 'weather', label: 'Wetter-Briefing' },
	{ value: 'briefings', label: 'Reports & Kanäle' },
	{ value: 'alerts', label: 'Alarmregeln' },
	{ value: 'preview', label: 'Vorschau' }
];

test.describe('Issue #155 — Trip-Detail Tab-Navigation', () => {
	test('AC-1: 6 Tabs in fester Reihenfolge sichtbar', async ({ page }) => {
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
		const overview = page.getByTestId('trip-detail-tab-overview');
		await expect(overview).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-detail-panel-overview')).toBeVisible();
	});

	test('AC-3: Klick auf "Etappen" wechselt aktiv + URL-Hash + Panel sichtbar', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByTestId('trip-detail-tab-stages').click();
		await expect(page.getByTestId('trip-detail-tab-stages')).toHaveAttribute('data-state', 'active');
		await expect(page).toHaveURL(new RegExp('#stages$'));
		const panel = page.getByTestId('trip-detail-panel-stages');
		await expect(panel).toBeVisible();
	});

	test('AC-4: Aufruf mit ?tab=alerts → Alerts-Tab initial aktiv (Bug #534 — Issue #516)', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}?tab=alerts`);
		await expect(page.getByTestId('trip-detail-tab-alerts')).toHaveAttribute('data-state', 'active');
		await expect(page.getByTestId('trip-detail-panel-alerts')).toBeVisible();
	});

	test('AC-5: Aktiver Tab hat sichtbare Unterstreichung in --g-accent', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}`);
		const overview = page.getByTestId('trip-detail-tab-overview');
		const borderBottomColor = await overview.evaluate(
			(el) => getComputedStyle(el).borderBottomColor
		);
		// accent-Token ist #c45a2a → rgb(196, 90, 42)
		expect(borderBottomColor).toMatch(/rgb\(196,\s*90,\s*42\)|rgba\(196,\s*90,\s*42/);

		const stages = page.getByTestId('trip-detail-tab-stages');
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
			if (tab.value === 'stages' || tab.value === 'alerts') continue;
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
		const overview = page.getByTestId('trip-detail-tab-overview');
		await overview.focus();
		await page.keyboard.press('ArrowRight');
		const focused = await page.evaluate(() =>
			document.activeElement?.getAttribute('data-testid')
		);
		expect(focused).toBe('trip-detail-tab-stages');
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
			path: 'docs/artifacts/epic-135-step1-tab-navigation/screenshot-tabs-overview.png',
			fullPage: false
		});
		await page.goto(`/trips/${TRIP_ID}?tab=alerts`);
		await page.waitForSelector('[data-testid="trip-detail-panel-alerts"]');
		await page.screenshot({
			path: 'docs/artifacts/epic-135-step1-tab-navigation/screenshot-tabs-alerts.png',
			fullPage: false
		});
	});
});
