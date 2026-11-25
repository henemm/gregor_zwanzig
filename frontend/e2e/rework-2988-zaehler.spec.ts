// E2E — Issue #2988 (AC-1, S1, wiederholt in S3): der Zaehler „von der Vorlage abweichend“ reagiert im
// Reiter Wetter sofort, und bei keiner Eingabe geht ein Aufruf an die Auflösung.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Echte Server (Staging in /e2e-verify).
//
//   cd frontend && npx playwright test e2e/rework-2988-zaehler.spec.ts --workers=1 --trace off

import { test, expect } from '@playwright/test';
import { cleanupTracked } from './helpers';
import { DESKTOP, OHNE_KINDER, WT, abweichungen, aktiveDerVorlage, metriken, oeffneWetter, seedWetter, vorlageImReiterWaehlen, vorlagen } from './s3a2794-teil3.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

for (const kind of ['route', 'vergleich'] as const) {
	test(`AC-1 (${kind}): Zähler sofort nach jeder Eingabe, kein Aufruf der Auflösung`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const vorlage = (await vorlagen(page.request)).wandern;
		const aktive = aktiveDerVorlage(vorlage);
		const kat = await metriken(page.request);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern' });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');

			// Erst ab hier zaehlen: das Laden selbst darf die Auflösung (ab S3) einmal fragen.
			const aufrufe: string[] = [];
			page.on('request', (r) => {
				if (new URL(r.url()).pathname === AUFLOESUNG) aufrufe.push(r.method());
			});

			// Reihenfolge und Zahlen wie im Kern-Test zaehler_ohne_netz_2988.test.ts (Zahl sofort, ohne auf das Speichern zu warten).
			const zahl = (n: number, was: string) =>
				expect.poll(() => abweichungen(reiter), { message: was, timeout: 2000 }).toBe(n);

			// 1) Grenze ändern: während des Tippens (Entwurf offen) und nach „Fertig“.
			const gust = reiter.getByTestId(WT.zeile('gust'));
			await gust.getByTestId(WT.grenzenAendern('gust')).click();
			await gust.getByTestId(WT.grenze('gust', 'upper', 'yellow')).fill('41');
			await zahl(1, 'Grenze während des Tippens');
			await gust.getByTestId(WT.grenzenAendern('gust')).click();
			await expect(gust.getByTestId(WT.grenzenAendern('gust'))).toHaveText('Grenzen ändern');
			await zahl(1, 'Grenze nach Fertig');

			// 2) „Alarm ab“ umstellen (Wind: auf Rot, stand es schon auf Rot, auf „kein Alarm“).
			const stufe = vorlage.ampel.metrics.wind.alarm_ab === 'red' ? 'never' : 'red';
			await reiter.getByTestId(WT.zeile('wind')).getByTestId(WT.alarmAbStufe('wind', stufe)).click();
			await zahl(2, 'Alarm ab');

			// 3) Metrik entfernen.
			const weg = aktive.includes('precipitation') ? 'precipitation' : aktive.find((id) => !['gust', 'wind', 'thunder'].includes(id))!;
			await reiter.getByTestId(WT.entfernen(weg)).click();
			await zahl(3, `Metrik entfernt (${weg})`);

			// 4) Metrik hinzufügen: eine, die die Vorlage nicht enthält (ohne abgeleitete Kinder, genau eine neue Zeile).
			const kandidaten = Object.keys(kat).filter((id) => !aktive.includes(id) && OHNE_KINDER(id) && id !== weg);
			let neu = '';
			for (const id of ['dewpoint', ...kandidaten]) {
				if ((await reiter.getByTestId(WT.plus(id)).count()) > 0) { neu = id; break; }
			}
			expect(neu, 'Messaufbau: eine Metrik unter „Nicht im Briefing“ mit „+“').not.toBe('');
			await reiter.getByTestId(WT.plus(neu)).click();
			await zahl(4, `Metrik hinzugefügt (${neu})`);

			// 5) Gewitterfarbe ändern (Stufe „mittel“: Rot, steht sie schon auf Rot, Orange).
			const gewitter = reiter.getByTestId(WT.zeile('thunder'));
			await gewitter.getByTestId(WT.grenzenAendern('thunder')).click();
			const istRot = (await gewitter.getByTestId(WT.gewitterFarbe('mittel', 'red')).getAttribute('aria-checked')) === 'true';
			await gewitter.getByTestId(WT.gewitterFarbe('mittel', istRot ? 'orange' : 'red')).click();
			await zahl(5, 'Gewitterfarbe');
			await gewitter.getByTestId(WT.grenzenAendern('thunder')).click();
			await zahl(5, 'Gewitterfarbe nach Fertig');

			// 6) Zurücksetzen auf die Vorlage.
			await reiter.getByTestId(WT.zuruecksetzen).click();
			await zahl(0, 'Zurücksetzen');
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');

			// 7) Andere Vorlage übernehmen.
			await vorlageImReiterWaehlen(page, 'skitouren');
			await expect(reiter.getByTestId(WT.pickerStatus), 'Vorlage übernommen').toHaveText('unverändert');

			// Laenger als die Speicher-Entprellung (700 ms): auch das Speichern fragt die Auflösung nicht.
			await page.waitForTimeout(1500);
			expect(aufrufe).toEqual([]);
		} finally {
			await hub.aufraeumen();
		}
	});
}
