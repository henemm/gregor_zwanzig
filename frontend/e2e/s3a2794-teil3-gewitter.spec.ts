// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Gewitter- und Windrichtungs-Zeile (AC-18).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-18
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich); zwei Vorlagen (Allgemein, Wassersport).
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-gewitter

import { test, expect } from '@playwright/test';
import { HUB_KINDS } from './helpers';
import { DESKTOP, WT, aktiveDerVorlage, oeffneWetter, seedWetter, vorlagen } from './s3a2794-teil3.helpers';

for (const kind of HUB_KINDS) {
	test(`AC-18 (${kind}): Gewitter mittel gelb·orange·rot, hoch orange·rot, „keins“-Hinweis, kein „Alarm ab Gelb“; Windrichtung nur Anzeige`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const v = await vorlagen(page.request);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'allgemein', auswahl: [...aktiveDerVorlage(v.allgemein), 'wind_direction'] });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			const gewitter = reiter.getByTestId(WT.zeile('thunder'));
			await gewitter.getByTestId(WT.grenzenAendern('thunder')).click();
			const mittel = gewitter.getByTestId(WT.gewitterStufe('mittel'));
			const hoch = gewitter.getByTestId(WT.gewitterStufe('hoch'));
			await expect(mittel).toContainText('mittel');
			await expect(hoch).toContainText('hoch');
			for (const f of ['yellow', 'orange', 'red']) await expect(gewitter.getByTestId(WT.gewitterFarbe('mittel', f))).toHaveCount(1);
			for (const f of ['orange', 'red']) await expect(gewitter.getByTestId(WT.gewitterFarbe('hoch', f))).toHaveCount(1);
			await expect(gewitter.getByTestId(WT.gewitterFarbe('hoch', 'yellow')), 'AC-18: hoch bietet Gelb an').toHaveCount(0);
			await expect(gewitter.getByTestId(WT.gewitterKeins)).toHaveText('‚keins‘ ist immer grün.');
			await expect(gewitter.getByTestId(WT.alarmAbStufe('thunder', 'yellow')), 'AC-18: „Alarm ab Gelb“ beim Gewitter').toHaveCount(0);
			for (const s of ['never', 'orange', 'red']) await expect(gewitter.getByTestId(WT.alarmAbStufe('thunder', s))).toHaveCount(1);

			const richtung = reiter.getByTestId(WT.zeile('wind_direction'));
			await expect(richtung).toContainText('keine Ampel, nur Anzeige');
			await expect(richtung.getByTestId(WT.grenzenAendern('wind_direction'))).toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-18 (${kind}): Wassersport, Gewitter Alarm ab Rot -> „Alarm, wenn die Gewitter-Stufe … auf mittel steigt (rot) …“`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wassersport' });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			const gewitter = reiter.getByTestId(WT.zeile('thunder'));
			await gewitter.getByTestId(WT.alarmAbStufe('thunder', 'red')).click();
			await expect(gewitter.getByTestId(WT.erklaersatz('thunder'))).toHaveText(
				/^Alarm, wenn die Gewitter-Stufe seit dem letzten Briefing auf mittel steigt \(rot\)\. Entwarnung, wenn sie wieder fällt\.$/i
			);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-18 (${kind}): Farben erreichen die Stufe nie -> „Mit diesen Farben erreicht Gewitter nie …, daher kein Alarm.“`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, {
			vorlageId: 'allgemein',
			ampel: { metrics: { thunder: { alarm_ab: 'red' } }, thunder: { mittel: 'yellow', hoch: 'orange' } }
		});
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			await expect(reiter.getByTestId(WT.erklaersatz('thunder'))).toHaveText(/^Mit diesen Farben erreicht Gewitter nie rot, daher kein Alarm\.$/i);
		} finally {
			await hub.aufraeumen();
		}
	});
}
