// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): „Alarm ab für alle“ und Zaehler (AC-14).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-14
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
// Alarmfaehigkeit je Metrik kommt aus /api/metrics (`alertable`), nie aus einer Frontend-Kopie.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-alarm-ab

import { test, expect } from '@playwright/test';
import { HUB_KINDS } from './helpers';
import { DESKTOP, WT, abweichungen, aktiveDerVorlage, metriken, oeffneWetter, seedWetter, stand, vorlagen, warteAufSpeichern } from './s3a2794-teil3.helpers';

for (const kind of HUB_KINDS) {
	test(`AC-14 (${kind}): „Alarm ab für alle“ auf Rot wirkt nur auf alarmfaehige Metriken, Zaehler stimmt`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const v = await vorlagen(page.request);
		const auswahl = aktiveDerVorlage(v.wandern);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', auswahl });
		try {
			const kat = await metriken(page.request);
			const faehig = auswahl.filter((id) => kat[id]?.alertable === true);
			const ohne = auswahl.filter((id) => kat[id] && kat[id].alertable !== true);
			expect(faehig, 'Messaufbau: Boeen und Gewitter alarmfaehig').toEqual(expect.arrayContaining(['gust', 'thunder']));
			const geaendert = faehig.filter((id) => v.wandern.ampel.metrics[id].alarm_ab !== 'red').length;

			const reiter = await oeffneWetter(page, kind, hub.id);
			await expect(reiter.getByTestId(WT.alarmAlle)).toContainText('Alarm ab für alle');
			await reiter.getByTestId(WT.alarmAlleStufe('red')).click();

			for (const id of faehig) {
				await expect(reiter.getByTestId(WT.alarmAbStufe(id, 'red')), `${id}: nicht „Alarm ab Rot“`).toHaveAttribute('aria-checked', 'true');
			}
			for (const id of ohne) {
				const zelle = reiter.getByTestId(WT.alarmAb(id));
				await expect(zelle, `${id}: zeigt kein „kein Alarm“`).toHaveText(kat[id].is_precursor ? 'kein Alarm (Vorbote)' : 'kein Alarm');
				await expect(reiter.getByTestId(WT.alarmAbStufe(id, 'red'))).toHaveCount(0);
			}
			await expect(reiter.getByTestId(WT.zaehler)).toHaveText(
				`${faehig.length} von ${faehig.length} Metriken lösen einen Alarm aus. ${ohne.length} können keinen auslösen (Vorboten und reine Anzeige).`
			);
			expect(await abweichungen(reiter), 'AC-14: jede geaenderte Metrik zaehlt als Abweichung').toBe(geaendert);

			await warteAufSpeichern(page, kind, hub.id);
			const s = await stand(page.request, kind, hub.id);
			for (const id of faehig) {
				const soll = v.wandern.ampel.metrics[id].alarm_ab === 'red' ? undefined : 'red';
				expect(s.display_config.ampel.metrics?.[id]?.alarm_ab, `${id}: gespeicherte Alarmstufe`).toBe(soll);
			}
			for (const id of ohne) expect(s.display_config.ampel.metrics?.[id]?.alarm_ab, `${id}: nicht alarmfaehig, trotzdem gesetzt`).toBeUndefined();
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-14 (${kind}): Auswahl nur aus Vorboten -> „Keine der gewählten Metriken kann einen Alarm auslösen …“`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', auswahl: ['humidity', 'rain_probability'] });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			await expect(reiter.getByTestId(WT.zaehler)).toHaveText(
				'Keine der gewählten Metriken kann einen Alarm auslösen. Nimm z.B. Wind, Böen oder Gewitter dazu.'
			);
		} finally {
			await hub.aufraeumen();
		}
	});
}
