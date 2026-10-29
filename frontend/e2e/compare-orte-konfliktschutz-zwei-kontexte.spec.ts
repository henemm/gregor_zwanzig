// gz-eigenstaendig: Orte-Tab ist eine der drei erlaubten Compare-Eigenheiten; sein Trip-Gegenstück „Etappen" hat andere Gesten und Felder, kein `location_ids`-Teilfeld (#2347 S3c, Spec Entscheidung 1).
//
// E2E — Issue #2347 S3c (aus #2375, Epic #2345): Konfliktschutz im Reiter Orte des
// Ortsvergleich-Hubs mit ZWEI Browser-Kontexten desselben Nutzers.
//
// Spec: docs/specs/modules/feat_2347_s3c_paritaets_e2e.md (KO-1 / AC-5)
//   A ändert den Namen, B entfernt einen Ort: der erste PUT von B trägt If-Match aus
//   dem Seitenaufbau, 412; die Ortsliste von B bleibt stehen (kein Rollback);
//   „Nochmal speichern" sendet erneut nur { location_ids }; Name von A UND verkürzte
//   Ortsliste stehen auf dem Server. Seit #1433 bleibt nach einem 412 das alte
//   If-Match stehen, bis „Nochmal speichern" läuft (Konflikt-Sperre).
//
// Zweiter Kontext = weiterer Browser-Kontext mit DEMSELBEN storageState (kein
// zweiter Login). Läuft im isolierten CI-Stack; Wegwerf-Objekt E2E-GZ-, Aufräumen im
// finally. Gewartet wird nur über expect.poll/toHaveAttribute/toHaveCount.

import { test, expect, type BrowserContext, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX, HUB_SEL, hubApiPath, openHub, seedHub } from './helpers';

let weitereKontexte: BrowserContext[] = [];

test.afterEach(async () => {
	for (const ctx of weitereKontexte) await ctx.close().catch(() => undefined);
	weitereKontexte = [];
});

const status = async (r: Request | undefined) => (r ? (await r.response())?.status() : 0);

test('KO-1 (vergleich): A ändert den Namen, B entfernt einen Ort → 412 mit If-Match → „Nochmal speichern" → Name von A UND Ortsliste von B', async ({
	page,
	browser,
	baseURL,
	storageState
}) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	const hub = await seedHub(page.request, 'vergleich');
	try {
		const pfad = hubApiPath('vergleich', hub.id);
		const ctx = await browser.newContext({
			baseURL,
			storageState: storageState as string,
			serviceWorkers: 'block',
			viewport: { width: 1280, height: 900 }
		});
		weitereKontexte.push(ctx);
		const b = await ctx.newPage();
		const putsB: Request[] = [];
		b.on('request', (r) => {
			if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) putsB.push(r);
		});
		await openHub(b, 'vergleich', hub.id, { tab: 'orte' });
		const zeilen = b.locator('[data-testid="hub-orte-row"]');
		await expect(zeilen).toHaveCount(2, { timeout: 10_000 });

		// A benennt um
		await openHub(page, 'vergleich', hub.id);
		const kopf = HUB_SEL.vergleich.kopf;
		const putsA: Request[] = [];
		page.on('request', (r) => {
			if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) putsA.push(r);
		});
		const nameA = `${E2E_TEST_PREFIX}Name von A ${Date.now()}`;
		await page.locator(`[data-testid="${kopf}-name-edit-toggle"]:visible`).click();
		await page.locator(`[data-testid="${kopf}-name-edit"]:visible`).fill(nameA);
		await page.locator(`[data-testid="${kopf}-name-save"]:visible`).click();
		await expect.poll(() => status(putsA[0]), { timeout: 10_000 }).toBe(200);

		// B entfernt einen Ort
		await b.locator('[data-testid="hub-orte-row"][data-loc-id="e2e-loc-stubai"] [data-testid="hub-orte-remove"]').click();
		await expect.poll(() => status(putsB[0]), { timeout: 10_000 }).toBe(412);
		expect(await putsB[0].headerValue('if-match'), 'AC-5: If-Match aus dem Seitenaufbau').toBeTruthy();
		const anzeige = b.locator('[data-testid="save-indicator"]');
		await expect(anzeige).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
		await expect(zeilen, 'nach dem 412 bleibt die Ortsliste von B stehen (kein Rollback)').toHaveCount(1, { timeout: 5_000 });

		// „Nochmal speichern"
		await anzeige.getByRole('button', { name: 'Nochmal speichern' }).click();
		await expect(anzeige).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await expect.poll(() => putsB.length, { timeout: 10_000, message: 'der Wiederholungs-PUT wurde gesendet' }).toBe(2);
		expect(await status(putsB[1])).toBe(200);
		expect(putsB[1].postDataJSON(), 'der Orte-PUT trägt nur { location_ids }').toEqual({ location_ids: ['e2e-loc-innsbruck'] });

		const res = await page.request.get(pfad);
		expect(res.ok()).toBeTruthy();
		const stand = (await res.json()) as Record<string, unknown>;
		expect(stand.name, 'der Name von A ging beim Orte-Speichern von B verloren').toBe(nameA);
		expect(stand.location_ids).toEqual(['e2e-loc-innsbruck']);
	} finally {
		await hub.aufraeumen();
	}
});
