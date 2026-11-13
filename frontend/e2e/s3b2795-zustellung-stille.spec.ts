// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): Stille Stunden und Mindestabstand (Cooldown).
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-24, AC-26 (+ AC-32: nur Alarm-Teil gesendet)
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-stille

import { test, expect } from '@playwright/test';
import { HUB_KINDS, tippeUhrzeit } from './helpers';
import { DESKTOP, ZT, angezeigteZeit, oeffneZustellung, schalte, seedZustellung, stand, warteAufSpeichern } from './s3b2795-zustellung.helpers';

for (const kind of HUB_KINDS) {
	test(`AC-24 (${kind}): Stille Stunden von–bis mit Schalter, Aenderung gespeichert und nach Neuladen angezeigt`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const karte = reiter.locator('[data-abschnitt="stille-stunden"]');
			await expect(karte).toContainText('Stille Stunden');
			await expect(karte.getByTestId(ZT.stilleUnterzeile)).toHaveText('keine Alarme, sie kommen mit dem nächsten Morgen-Briefing');
			await expect(karte.getByTestId(ZT.stilleSchalter)).toHaveAttribute('aria-checked', 'true');
			expect(await angezeigteZeit(karte.getByTestId(ZT.stilleVon))).toBe('22:00');
			expect(await angezeigteZeit(karte.getByTestId(ZT.stilleBis))).toBe('06:00');

			const s1 = warteAufSpeichern(page, kind, hub.id);
			await tippeUhrzeit(page, karte.getByTestId(ZT.stilleVon), '23:00');
			await page.keyboard.press('Tab');
			const rumpf = await s1;
			expect(Object.keys(rumpf), 'nur der Alarm-Teil (AC-32)').toEqual(['alert_quiet_from']);
			expect(String((await stand(page.request, kind, hub.id)).alert_quiet_from).slice(0, 5)).toBe('23:00');

			await page.reload();
			const neu = await oeffneZustellung(page, kind, hub.id);
			expect(await angezeigteZeit(neu.getByTestId(ZT.stilleVon))).toBe('23:00');

			const s2 = warteAufSpeichern(page, kind, hub.id);
			await schalte(neu.getByTestId(ZT.stilleSchalter), false);
			await s2;
			const aus = await stand(page.request, kind, hub.id);
			expect(aus.alert_quiet_from ?? null, 'Schalter aus loescht von').toBeNull();
			expect(aus.alert_quiet_to ?? null, 'Schalter aus loescht bis').toBeNull();
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-26 (${kind}): „Anpassen“ zeigt den gespeicherten Mindestabstand; Aenderung wird als alert_cooldown_minutes gespeichert`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const anpassen = reiter.getByTestId(ZT.anpassen);
			await anpassen.locator('summary').click();
			await expect(anpassen).toContainText('Mindestabstand zwischen zwei Alarmen');
			await expect(anpassen).toContainText('derselben Metrik');
			await expect(anpassen).toContainText('Minuten');
			const feld = anpassen.getByTestId(ZT.cooldown);
			await expect(feld, 'zeigt den gespeicherten Wert, nicht das Mockup-Beispiel 10').toHaveValue('45');

			const s = warteAufSpeichern(page, kind, hub.id);
			await feld.fill('90');
			await feld.blur();
			expect(await s).toEqual({ alert_cooldown_minutes: 90 });
			expect((await stand(page.request, kind, hub.id)).alert_cooldown_minutes).toBe(90);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-26 (${kind}): ohne gespeicherten Mindestabstand zeigt das Feld den Standard 120`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind, { alert_cooldown_minutes: null });
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const anpassen = reiter.getByTestId(ZT.anpassen);
			await anpassen.locator('summary').click();
			await expect(anpassen.getByTestId(ZT.cooldown)).toHaveValue('120');
		} finally {
			await hub.aufraeumen();
		}
	});
}
