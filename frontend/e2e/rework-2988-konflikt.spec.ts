// gz-eigenstaendig: nur der Ortsvergleich lädt nach einem 412 im Reiter Wetter neu (Hub-Schreibschlange mit If-Match); der Trip speichert in zwei PUTs und zeigt den Konflikt ohne Nachladen (Spec AC-12).
//
// E2E — Issue #2988 S3 (AC-12): zwei Sitzungen ändern denselben Ortsvergleich. Nach dem 412 lädt die erste Sitzung
// samt Auflösung neu; scheitert die Auflösung, bleibt ihre Eingabe stehen und nichts wird still überschrieben.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Echte Server (Staging in /e2e-verify).
//
//   cd frontend && npx playwright test e2e/rework-2988-konflikt.spec.ts --workers=1 --trace off

import { test, expect, type BrowserContext, type Locator, type Page, type Request } from '@playwright/test';
import { cleanupTracked, hubApiPath } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter, stand, vorlagen, warteAufSpeichern } from './s3a2794-teil3.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';
const istAufloesung = (url: URL) => url.pathname === AUFLOESUNG;
let weitere: BrowserContext[] = [];

test.afterEach(async ({ page }) => {
	for (const ctx of weitere) await ctx.close().catch(() => undefined);
	weitere = [];
	await cleanupTracked(page.request);
});

const stufe = (reiter: Locator, id: string, s: string) => reiter.getByTestId(WT.zeile(id)).getByTestId(WT.alarmAbStufe(id, s));
const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const status = async (r: Request | undefined) => (r ? (await r.response())?.status() : 0);
const ampelVon = async (page: Page, id: string) => (await stand(page.request, 'vergleich', id)).display_config.ampel;

/** Beide Sitzungen offen, B speichert Wind „Alarm ab Rot“; A hat noch den alten Stand. */
async function zweiSitzungen(page: Page, id: string) {
	const ctx = await page.context().browser()!.newContext({ storageState: await page.context().storageState(), serviceWorkers: 'block', viewport: DESKTOP });
	weitere.push(ctx);
	const b = await ctx.newPage();
	const ra = await oeffneWetter(page, 'vergleich', id);
	const puts: Request[] = [];
	const fragen: string[] = [];
	page.on('request', (r) => {
		const pfad = new URL(r.url()).pathname;
		if (r.method() === 'PUT' && pfad === hubApiPath('vergleich', id)) puts.push(r);
		if (pfad === AUFLOESUNG) fragen.push(r.method());
	});
	const rb = await oeffneWetter(b, 'vergleich', id);
	const gespeichert = warteAufSpeichern(b, 'vergleich', id);
	await stufe(rb, 'wind', 'red').click();
	await gespeichert;
	return { ra, puts, fragen };
}

test('AC-12: nach dem 412 zeigt die Sitzung die fremde Änderung, der Konflikt wird gemeldet', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const hub = await seedWetter(page.request, 'vergleich', { vorlageId: 'wandern' });
	try {
		expect((await vorlagen(page.request)).wandern.ampel.metrics.wind.alarm_ab, 'Messaufbau: Wind steht schon auf Rot').not.toBe('red');
		const { ra, puts, fragen } = await zweiSitzungen(page, hub.id);
		await stufe(ra, 'gust', 'red').click();
		await expect.poll(() => status(puts[0]), { timeout: 20_000 }).toBe(412);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
		await expect(stufe(ra, 'wind', 'red'), 'fremde Änderung nicht sichtbar').toHaveAttribute('aria-checked', 'true', { timeout: 20_000 });
		await expect(stufe(ra, 'gust', 'red'), 'Reiter zeigt nicht den neu geladenen Stand').toHaveAttribute('aria-checked', 'false');
		expect(fragen, 'Nachladen fragt die Auflösung genau einmal').toEqual(['POST']);
		// Länger als die Entprellung: das Neuladen selbst speichert nicht.
		await page.waitForTimeout(1500);
		expect(puts.length).toBe(1);
		expect((await ampelVon(page, hub.id)).metrics, 'fremde Änderung still überschrieben').toEqual({ wind: { alarm_ab: 'red' } });

		await anzeige(page).getByRole('button', { name: 'Nochmal speichern' }).click();
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		expect((await ampelVon(page, hub.id)).metrics.wind, 'fremde Änderung nach „Nochmal speichern“ verloren').toEqual({ alarm_ab: 'red' });
	} finally {
		await hub.aufraeumen();
	}
});

test('AC-12: scheitert die Auflösung nach dem 412, bleibt die Eingabe stehen und nichts wird still überschrieben', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const hub = await seedWetter(page.request, 'vergleich', { vorlageId: 'wandern' });
	try {
		const { ra, puts, fragen } = await zweiSitzungen(page, hub.id);
		await page.route(istAufloesung, (r) => r.abort('connectionfailed'));
		await stufe(ra, 'gust', 'red').click();
		await expect.poll(() => status(puts[0]), { timeout: 20_000 }).toBe(412);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
		await expect.poll(() => fragen.length, { message: 'die Auflösung wird nicht gefragt' }).toBe(1);
		await expect(stufe(ra, 'gust', 'red'), 'eigene Eingabe still verloren').toHaveAttribute('aria-checked', 'true');
		await expect(stufe(ra, 'wind', 'red'), 'Stand halb neu geladen').toHaveAttribute('aria-checked', 'false');
		expect((await ampelVon(page, hub.id)).metrics).toEqual({ wind: { alarm_ab: 'red' } });

		// Weitere Eingabe auf dem alten Stand: wieder 412, die fremde Änderung bleibt stehen.
		await stufe(ra, 'gust', 'never').click();
		await expect.poll(() => status(puts[1]), { timeout: 20_000, message: 'weitere Eingabe überschreibt die fremde Änderung still' }).toBe(412);
		expect((await ampelVon(page, hub.id)).metrics).toEqual({ wind: { alarm_ab: 'red' } });

		await page.unroute(istAufloesung);
		await anzeige(page).getByRole('button', { name: 'Nochmal speichern' }).click();
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		expect((await ampelVon(page, hub.id)).metrics.gust, '„Nochmal speichern“ verliert die eigene Eingabe').toEqual({ alarm_ab: 'never' });
	} finally {
		await page.unroute(istAufloesung).catch(() => {});
		await hub.aufraeumen();
	}
});
