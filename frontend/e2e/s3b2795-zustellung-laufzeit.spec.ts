// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): Laufzeit.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-9 (Trip), AC-10 (Orte, end_date)
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-laufzeit

import { test, expect } from '@playwright/test';
import { tippeDatum } from './helpers';
import { DESKTOP, ZT, oeffneZustellung, seedZustellung, stand, warteAufSpeichern } from './s3b2795-zustellung.helpers';

test('AC-9 (route): Laufzeit-Satz aus den Etappen und „Etappen öffnen →“ springt in den Reiter Etappen', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const hub = await seedZustellung(page.request, 'route');
	try {
		const reiter = await oeffneZustellung(page, 'route', hub.id);
		const karte = reiter.locator('[data-abschnitt="laufzeit"]');
		await expect(karte).toContainText('Laufzeit');
		const satz = (await karte.getByTestId(ZT.laufzeitSatz).innerText()).trim();
		expect(satz).toMatch(/\. Die Briefings enden nach der letzten Etappe\. Die Daten pflegst du in den Etappen\.$/);
		expect(satz, 'Daten der Etappen (1.–4. August 2027)').toMatch(/2027/);
		await expect(karte.getByTestId(ZT.laufzeitOffen), 'Trip hat kein Laufzeit-Segment').toHaveCount(0);
		await karte.getByTestId(ZT.etappenOeffnen).click();
		await expect.poll(() => new URL(page.url()).searchParams.get('tab')).toBe('etappen');
	} finally {
		await hub.aufraeumen();
	}
});

test('AC-10 (vergleich): „Bis auf Weiteres“ ohne Enddatum, „Bis Datum“ mit Datumsfeld speichert end_date', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	const hub = await seedZustellung(page.request, 'vergleich');
	try {
		const reiter = await oeffneZustellung(page, 'vergleich', hub.id);
		const karte = reiter.locator('[data-abschnitt="laufzeit"]');
		await expect(karte.getByTestId(ZT.laufzeitOffen)).toHaveAttribute('aria-pressed', 'true');
		await expect(karte.getByTestId(ZT.laufzeitSatz)).toHaveText('Das Briefing läuft, bis du es pausierst.');
		await expect(karte.getByTestId(ZT.laufzeitDatum)).toHaveCount(0);

		await karte.getByTestId(ZT.laufzeitBisDatum).click();
		await expect(karte.getByTestId(ZT.laufzeitSatz)).toHaveText(/^Danach pausiert das Briefing von selbst\. Im Kopf steht dann [„‚]Laufzeit überschritten[“‘]\.$/);
		const datum = karte.getByTestId(ZT.laufzeitDatum);
		await expect(datum).toBeVisible();
		const speichern = warteAufSpeichern(page, 'vergleich', hub.id);
		await tippeDatum(page, datum, '2027-03-31');
		await page.keyboard.press('Tab');
		await speichern;
		expect((await stand(page.request, 'vergleich', hub.id)).end_date).toBe('2027-03-31');

		await page.reload();
		const neu = await oeffneZustellung(page, 'vergleich', hub.id);
		await expect(neu.getByTestId(ZT.laufzeitBisDatum)).toHaveAttribute('aria-pressed', 'true');
	} finally {
		await hub.aufraeumen();
	}
});
