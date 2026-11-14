// E2E — Issue #2795 S3b, Teilschritt 1b (Reiter Zustellung): Kopf und Briefing-Zeiten.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — AC-1, AC-2, AC-3, AC-4, AC-8 (Oberflaeche + Server-400)
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   cd frontend && npx playwright test --config playwright.2795-s3b1b.staging.config.ts s3b2795-zustellung-zeiten

import { test, expect, type Request } from '@playwright/test';
import { HUB_KINDS, hubApiPath, tippeUhrzeit } from './helpers';
import {
	DESKTOP,
	ZT,
	angezeigteZeit,
	gespeicherteZeit,
	istZustellungSchreiben,
	oeffneZustellung,
	seedZustellung,
	stand,
	warteAufSpeichern
} from './s3b2795-zustellung.helpers';

const UNTERZEILEN = {
	route: { morgen: 'für die Etappe des Tages', abend: 'für die Etappe von morgen' },
	vergleich: { morgen: 'für heute', abend: 'für morgen' }
} as const;

for (const kind of HUB_KINDS) {
	test(`AC-1/AC-2/AC-3 (${kind}): Kopf, zwei Karten mit Unterzeile, Schalter, Uhrzeitfeld, keine Schnellwahl`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const kopf = reiter.locator('[data-abschnitt="abschnittskopf"]');
			await expect(kopf).toBeVisible();
			await expect(kopf.getByTestId(ZT.titel)).toHaveText('Zustellung');
			await expect(kopf.getByTestId(ZT.erklaer)).toHaveText('Wann die Briefings kommen und auf welchem Weg Briefings und Alarme dich erreichen.');

			for (const slot of ['morgen', 'abend'] as const) {
				const karte = reiter.getByTestId(ZT.karte(slot));
				await expect(karte).toBeVisible();
				await expect(karte).toContainText(slot === 'morgen' ? 'Morgen-Briefing' : 'Abend-Briefing');
				await expect(karte.getByTestId(ZT.unterzeile(slot))).toHaveText(UNTERZEILEN[kind][slot]);
				await expect(karte.getByTestId(ZT.schalter(slot))).toHaveAttribute('role', 'switch');
				expect(await angezeigteZeit(karte.getByTestId(ZT.zeit(slot)))).toBe(slot === 'morgen' ? '07:00' : '18:00');
			}
			await expect(reiter.getByTestId(ZT.schnellwahl), 'V11: keine Schnellwahl-Knoepfe').toHaveCount(0);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-4 (${kind}): 06:45 eintippen, speichern, nach Neuladen steht 06:45`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const feld = reiter.getByTestId(ZT.zeit('morgen'));
			const speichern = warteAufSpeichern(page, kind, hub.id);
			await tippeUhrzeit(page, feld, '06:45');
			await page.keyboard.press('Tab');
			const rumpf = await speichern;
			expect(JSON.stringify(rumpf), 'gesendet wird 06:45, nicht 06:00').toMatch(/06:45/);

			expect(gespeicherteZeit(kind, await stand(page.request, kind, hub.id), 'morgen'), 'gespeichert ohne Kappen').toBe('06:45');
			await page.reload();
			const neu = await oeffneZustellung(page, kind, hub.id);
			expect(await angezeigteZeit(neu.getByTestId(ZT.zeit('morgen')))).toBe('06:45');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-8 (${kind}): 06:50 zeigt die Raster-Meldung und speichert nichts; direkter PUT wird mit 400 abgelehnt`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedZustellung(page.request, kind);
		const puts: Request[] = [];
		page.on('request', (r) => {
			if (istZustellungSchreiben(kind, hub.id)(r)) puts.push(r);
		});
		try {
			const reiter = await oeffneZustellung(page, kind, hub.id);
			const feld = reiter.getByTestId(ZT.zeit('morgen'));
			await tippeUhrzeit(page, feld, '06:50');
			await page.keyboard.press('Tab');
			await expect(reiter.getByTestId(ZT.zeitFehler('morgen'))).toHaveText('Bitte eine Zeit im Viertelstunden-Raster eintragen (00, 15, 30, 45)');

			// Neuladen (loest einen etwa ausstehenden Speichervorgang aus): 06:50 wurde nie gesendet, Feld zeigt 07:00.
			await page.reload();
			const neu = await oeffneZustellung(page, kind, hub.id);
			expect(await angezeigteZeit(neu.getByTestId(ZT.zeit('morgen')))).toBe('07:00');
			for (const r of puts) expect(r.postData() ?? '', 'AC-8: 06:50 darf nie gesendet werden').not.toMatch(/06:50/);
			expect(gespeicherteZeit(kind, await stand(page.request, kind, hub.id), 'morgen')).toBe('07:00');

			const direkt =
				kind === 'route'
					? await page.request.put(hubApiPath(kind, hub.id), { data: { report_config: { morning_time: '06:50:00' } } })
					: await page.request.put(hubApiPath(kind, hub.id), { data: { morning_time: '06:50:00' } });
			expect(direkt.status(), 'Server lehnt 06:50 ab (keine stille Verfaelschung)').toBe(400);
			expect(gespeicherteZeit(kind, await stand(page.request, kind, hub.id), 'morgen')).toBe('07:00');
		} finally {
			await hub.aufraeumen();
		}
	});
}
