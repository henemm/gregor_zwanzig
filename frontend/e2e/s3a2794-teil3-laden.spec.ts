// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Kopf, Ladezustand und Ladefehler (AC-9).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-9
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
// Katalog-Abruf = GET /api/metrics. Der Ladezustand wird mit einem Tor im Browser-Netz gehalten,
// der Abbruch per page.route(...).abort() erzeugt (keine Mock-Logik im Produktivcode).
// Die gespeicherten Einstellungen bleiben per API vorher/nachher gleich.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-laden

import { test, expect, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, openHub } from './helpers';
import { DESKTOP, WT, seedWetter, stand } from './s3a2794-teil3.helpers';

const istKatalog = (url: URL) => url.pathname === '/api/metrics';

const reiterIm = (page: Page, kind: (typeof HUB_KINDS)[number]) =>
	page.locator(`[data-testid="${HUB_SEL[kind].panel}-wetter"]:visible`).first().getByTestId(WT.tab);

for (const kind of HUB_KINDS) {
	test(`AC-9 (${kind}): Kopf „Wetter“ mit Erklaersatz, „Lade Metriken …“ waehrend des Katalog-Abrufs`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind);
		let freigeben: () => void = () => {};
		const tor = new Promise<void>((r) => (freigeben = r));
		await page.route(istKatalog, async (route) => {
			await tor;
			await route.continue();
		});
		try {
			await openHub(page, kind, hub.id, { tab: 'wetter' });
			const reiter = reiterIm(page, kind);
			await expect(reiter).toBeVisible({ timeout: 15_000 });
			await expect(reiter.getByTestId(WT.titel)).toHaveText('Wetter');
			await expect(reiter.getByTestId(WT.erklaer)).toHaveText(
				'Was im Briefing steht, was für dich zu viel oder zu wenig ist und ab wann du einen Alarm bekommst.'
			);
			await expect(reiter.getByTestId(WT.laden)).toBeVisible();
			await expect(reiter.getByTestId(WT.laden)).toContainText('Lade Metriken …');
			freigeben();
			await expect(reiter.getByTestId(WT.laden)).toHaveCount(0, { timeout: 15_000 });
			await expect(reiter.locator('[data-testid^="wetter-zeile-"]').first()).toBeVisible();
		} finally {
			freigeben();
			await page.unroute(istKatalog);
			await hub.aufraeumen();
		}
	});

	test(`AC-9 (${kind}): Katalog-Abbruch zeigt Fehlermeldung + „Erneut laden“, Abo unveraendert, Klick laedt neu`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { ampel: { metrics: { gust: { alarm_ab: 'red' } } } });
		try {
			const vorher = await stand(page.request, kind, hub.id);
			await page.route(istKatalog, (route) => route.abort('connectionfailed'));
			await openHub(page, kind, hub.id, { tab: 'wetter' });
			const reiter = reiterIm(page, kind);
			await expect(reiter.getByTestId(WT.fehler)).toHaveText(
				/Die Metriken konnten nicht geladen werden\. Die Verbindung zum Server ist abgebrochen\. Deine Einstellungen sind gespeichert und gehen nicht verloren\./,
				{ timeout: 15_000 }
			);
			const knopf = reiter.getByTestId(WT.erneutLaden);
			await expect(knopf).toHaveText('Erneut laden');
			await expect(reiter.locator('[data-testid^="wetter-zeile-"]')).toHaveCount(0);

			const nachFehler = await stand(page.request, kind, hub.id);
			expect(nachFehler.display_config, 'AC-9: Ladefehler hat die gespeicherten Einstellungen veraendert').toEqual(vorher.display_config);

			await page.unroute(istKatalog);
			const neu = page.waitForRequest((r) => istKatalog(new URL(r.url())));
			await knopf.click();
			await neu;
			await expect(reiter.getByTestId(WT.fehler)).toHaveCount(0, { timeout: 15_000 });
			await expect(reiter.locator('[data-testid^="wetter-zeile-"]').first()).toBeVisible();
			await expect(reiter.getByTestId(WT.zeile('gust')).getByTestId(WT.alarmAbStufe('gust', 'red'))).toHaveAttribute('aria-checked', 'true');

			const nachher = await stand(page.request, kind, hub.id);
			expect(nachher.display_config).toEqual(vorher.display_config);
		} finally {
			await page.unroute(istKatalog).catch(() => {});
			await hub.aufraeumen();
		}
	});
}
