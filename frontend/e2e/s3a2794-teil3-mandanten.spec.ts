// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Mandantentrennung (AC-30), zwei Konten.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-30
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   Nutzer A hat Grenzen und Alarm-ab gesetzt. Nutzer B (eigenes, bestaetigtes Konto, eigener Browser-Kontext)
//   aendert in SEINEM Reiter Wetter Grenzen und speichert. Danach:
//     - A's gespeicherter Zustand (per API des Kontos A) ist unveraendert,
//     - B sieht keine Werte von A (eigener Zustand ohne A's Grenzen/Alarm-ab, A's Objekt per API nicht lesbar,
//       nicht in B's Liste).
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-mandanten

import { test, expect } from '@playwright/test';
import { HUB_KINDS, registriereBestaetigtenZweitnutzer } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter, stand, warteAufSpeichern, type Json } from './s3a2794-teil3.helpers';
import { wegwerfPasswort } from './stagingZugang';

const LISTE = { route: '/api/trips', vergleich: '/api/compare/presets' } as const;

for (const kind of HUB_KINDS) {
	test(`AC-30 (${kind}): Nutzer B aendert Grenzen — Daten von A unveraendert, B sieht nichts von A`, async ({ page, browser }) => {
		await page.setViewportSize(DESKTOP);
		const hubA = await seedWetter(page.request, kind, {
			vorlageId: 'wandern',
			ampel: { metrics: { gust: { upper: { yellow: 31, orange: 41, red: 71 }, alarm_ab: 'red' } } }
		});
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: undefined,
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		let hubB: Awaited<ReturnType<typeof seedWetter>> | undefined;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2eteil3mandant${kind}${Date.now()}`, kennwort);
			hubB = await seedWetter(gast.request, kind, { vorlageId: 'wandern' });

			const vorherA: Json = await stand(page.request, kind, hubA.id);
			expect(vorherA.display_config.ampel.metrics.gust.alarm_ab, 'Messaufbau: A hat Alarm-ab gesetzt').toBe('red');

			// B aendert Grenzen im Reiter Wetter und speichert
			const seiteB = await gast.newPage();
			await seiteB.setViewportSize(DESKTOP);
			const reiter = await oeffneWetter(seiteB, kind, hubB.id);
			const zeile = reiter.getByTestId(WT.zeile('gust'));
			await zeile.getByTestId(WT.grenzenAendern('gust')).click();
			await expect(zeile.getByTestId(WT.grenzenAendern('gust'))).toHaveText('Fertig');
			await zeile.getByTestId(WT.grenze('gust', 'upper', 'orange')).fill('52');
			const speichern = warteAufSpeichern(seiteB, kind, hubB.id);
			await zeile.getByTestId(WT.grenzenAendern('gust')).click();
			await speichern;

			// B: eigener Wert gespeichert, keine Werte von A
			const standB: Json = await stand(gast.request, kind, hubB.id);
			const gustB = standB.display_config.ampel.metrics.gust;
			expect(gustB.upper.orange, 'B: eigene Aenderung gespeichert').toBe(52);
			expect(gustB.upper.yellow, 'Mandantentrennung: Wert von A bei B').not.toBe(31);
			expect(gustB.upper.red, 'Mandantentrennung: Wert von A bei B').not.toBe(71);
			expect(gustB.alarm_ab ?? null, 'Mandantentrennung: Alarm-ab von A bei B').not.toBe('red');

			// A unveraendert (Antwort des Kontos A)
			const nachherA: Json = await stand(page.request, kind, hubA.id);
			expect(nachherA, 'AC-30: Daten von A veraendert').toEqual(vorherA);

			// B kann A's Objekt nicht lesen, und es steht nicht in B's Liste
			const lesen = await gast.request.get(`${LISTE[kind]}/${hubA.id}`);
			expect([403, 404], `B liest A's Objekt: HTTP ${lesen.status()}`).toContain(lesen.status());
			const liste = await gast.request.get(LISTE[kind]);
			expect(liste.ok()).toBeTruthy();
			expect(JSON.stringify(await liste.json()), 'Mandantentrennung: A in B-Liste').not.toContain(hubA.id);
		} finally {
			await hubB?.aufraeumen().catch(() => {});
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
			await hubA.aufraeumen();
		}
	});
}
