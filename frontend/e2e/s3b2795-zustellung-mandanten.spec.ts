// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): Mandantentrennung, Oberflaechen-Seite von AC-34.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-34 (Server-Seite: Go-Test aus Teilschritt 1a)
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   Nutzer B (eigenes, bestaetigtes Konto, eigener Browser-Kontext) setzt in SEINEM Reiter Zustellung 06:45,
//   Cooldown und Stille Stunden. Danach ist A's gespeicherter Zustand unveraendert, B kann A's Objekt weder lesen
//   noch schreiben (PUT auf A's Objekt abgelehnt).
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-mandanten

import { test, expect } from '@playwright/test';
import { HUB_KINDS, hubApiPath, registriereBestaetigtenZweitnutzer, tippeUhrzeit } from './helpers';
import { wegwerfPasswort } from './stagingZugang';
import { DESKTOP, ZT, gespeicherteZeit, oeffneZustellung, seedZustellung, stand, warteAufSpeichern, type Json } from './s3b2795-zustellung.helpers';

for (const kind of HUB_KINDS) {
	test(`AC-34 (${kind}): B aendert Zustellung im eigenen Reiter — A unveraendert, B kommt nicht an A's Objekt`, async ({ page, browser }) => {
		const hubA = await seedZustellung(page.request, kind);
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: undefined,
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		let hubB: Awaited<ReturnType<typeof seedZustellung>> | undefined;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2e2795mandant${kind}${Date.now()}`, kennwort);
			hubB = await seedZustellung(gast.request, kind);
			const vorherA: Json = await stand(page.request, kind, hubA.id);

			const seiteB = await gast.newPage();
			await seiteB.setViewportSize(DESKTOP);
			const reiter = await oeffneZustellung(seiteB, kind, hubB.id);
			const s1 = warteAufSpeichern(seiteB, kind, hubB.id);
			await tippeUhrzeit(seiteB, reiter.getByTestId(ZT.zeit('morgen')), '06:45');
			await seiteB.keyboard.press('Tab');
			await s1;
			const anpassen = reiter.getByTestId(ZT.anpassen);
			await anpassen.locator('summary').click();
			const s2 = warteAufSpeichern(seiteB, kind, hubB.id);
			await anpassen.getByTestId(ZT.cooldown).fill('30');
			await anpassen.getByTestId(ZT.cooldown).blur();
			await s2;

			const standB: Json = await stand(gast.request, kind, hubB.id);
			expect(gespeicherteZeit(kind, standB, 'morgen'), 'B: eigene Aenderung gespeichert').toBe('06:45');
			expect(standB.alert_cooldown_minutes).toBe(30);

			const nachherA: Json = await stand(page.request, kind, hubA.id);
			expect(nachherA, 'AC-34: Daten von A veraendert').toEqual(vorherA);

			const lesen = await gast.request.get(hubApiPath(kind, hubA.id));
			expect([403, 404], `B liest A's Objekt: HTTP ${lesen.status()}`).toContain(lesen.status());
			const schreiben = await gast.request.put(hubApiPath(kind, hubA.id), { data: { alert_cooldown_minutes: 5 } });
			expect([403, 404], `B schreibt A's Objekt: HTTP ${schreiben.status()}`).toContain(schreiben.status());
			expect(await stand(page.request, kind, hubA.id)).toEqual(vorherA);
		} finally {
			await hubB?.aufraeumen().catch(() => {});
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
			await hubA.aufraeumen();
		}
	});
}
