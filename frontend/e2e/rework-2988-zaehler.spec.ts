// E2E — Issue #2988 (AC-1, S1, wiederholt in S3): der Zaehler „von der Vorlage abweichend“ reagiert im
// Reiter Wetter sofort, und bei keiner Eingabe geht ein Aufruf an die Auflösung.
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md. Echte Server (Staging in /e2e-verify).
//
//   cd frontend && npx playwright test e2e/rework-2988-zaehler.spec.ts --workers=1 --trace off

import { test, expect } from '@playwright/test';
import { cleanupTracked } from './helpers';
import { DESKTOP, WT, abweichungen, oeffneWetter, seedWetter, vorlageImReiterWaehlen } from './s3a2794-teil3.helpers';

const AUFLOESUNG = '/api/ampel/aufloesung';

test.afterEach(async ({ page }) => {
	await cleanupTracked(page.request);
});

for (const kind of ['route', 'vergleich'] as const) {
	test(`AC-1 (${kind}): Zähler sofort nach jeder Eingabe, kein Aufruf der Auflösung`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern' });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('unverändert');

			// Erst ab hier zaehlen: das Laden selbst darf die Auflösung (ab S3) einmal fragen.
			const aufrufe: string[] = [];
			page.on('request', (r) => {
				if (new URL(r.url()).pathname === AUFLOESUNG) aufrufe.push(r.method());
			});

			await reiter.getByTestId(WT.entfernen('gust')).click();
			expect(await abweichungen(reiter), 'Metrik entfernt').toBe(1);
			await reiter.getByTestId(WT.entfernen('wind')).click();
			expect(await abweichungen(reiter), 'zweite Metrik entfernt').toBe(2);
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
