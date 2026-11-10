// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Metrik-Zeilen in fuenf Gruppen (AC-15).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-15
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
// Gruppenzugehoerigkeit je Metrik kommt aus /api/metrics (`group`), kein Test gegen eine Frontend-Kopie.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-zeilen

import { test, expect } from '@playwright/test';
import { HUB_KINDS } from './helpers';
import { DESKTOP, WT, aktiveDerVorlage, metriken, oeffneWetter, seedWetter, vorlagen } from './s3a2794-teil3.helpers';

const GRUPPEN = ['temperature', 'wind', 'precip_thunder', 'sky_visibility', 'snow_height'];
const GRUPPEN_TITEL: Record<string, string> = {
	temperature: 'Temperatur',
	wind: 'Wind',
	precip_thunder: 'Niederschlag & Gewitter',
	sky_visibility: 'Himmel & Sicht',
	snow_height: 'Schnee & Höhe'
};

for (const kind of HUB_KINDS) {
	test(`AC-15 (${kind}): Zeilen in fuenf Gruppen (nur belegte), je Zeile Leiste, Erklaersatz, „grün: …“, Alarm ab, Grenzen aendern; kein CAPE/Aggregation/Roh-Einfach`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const v = await vorlagen(page.request);
		const auswahl = [...aktiveDerVorlage(v['alpen-trekking']), 'wind_direction'];
		const hub = await seedWetter(page.request, kind, { vorlageId: 'alpen-trekking', auswahl });
		try {
			const kat = await metriken(page.request);
			const reiter = await oeffneWetter(page, kind, hub.id);

			const belegt = GRUPPEN.filter((g) => auswahl.some((id) => kat[id]?.group === g));
			const gruppenIds = await reiter.locator('[data-testid^="wetter-gruppe-"]').evaluateAll((els) =>
				els.map((e) => (e.getAttribute('data-testid') ?? '').replace('wetter-gruppe-', ''))
			);
			expect(gruppenIds, 'AC-15: Gruppen nicht in der Reihenfolge Temperatur · Wind · Niederschlag & Gewitter · Himmel & Sicht · Schnee & Höhe').toEqual(belegt);
			for (const g of belegt) await expect(reiter.getByTestId(WT.gruppe(g))).toContainText(GRUPPEN_TITEL[g]);

			for (const id of auswahl) {
				const zeile = reiter.getByTestId(WT.gruppe(kat[id].group)).getByTestId(WT.zeile(id));
				await expect(zeile, `${id} steht nicht in Gruppe ${kat[id].group}`).toBeVisible();
				if (kat[id].display_only) {
					await expect(zeile).toContainText('keine Ampel, nur Anzeige');
					await expect(zeile.getByTestId(WT.grenzenAendern(id))).toHaveCount(0);
					continue;
				}
				await expect(zeile.getByTestId(WT.leiste(id))).toBeVisible();
				await expect(zeile.getByTestId(WT.erklaersatz(id))).not.toBeEmpty();
				if (id !== 'thunder') await expect(zeile.getByTestId(WT.gruen(id))).toHaveText(/^(grün: .+|immer grün \(keine Grenze gesetzt\))$/);
				await expect(zeile.getByTestId(WT.grenzenAendern(id))).toHaveText('Grenzen ändern');
				if (kat[id].alertable) await expect(zeile.getByTestId(WT.alarmAbStufe(id, 'never'))).toBeVisible();
				else await expect(zeile.getByTestId(WT.alarmAb(id))).toHaveText(kat[id].is_precursor ? 'kein Alarm (Vorbote)' : 'kein Alarm');
			}

			await expect(reiter.getByTestId(WT.zeile('cape')), 'AC-15: CAPE-Zeile').toHaveCount(0);
			await expect(reiter.locator('[data-testid*="aggregation"]'), 'AC-15: Aggregationswahl').toHaveCount(0);
			await expect(reiter.getByRole('radio', { name: /^(Roh|Einfach)$/ }), 'AC-15: Roh/Einfach in den Zeilen').toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});
}
