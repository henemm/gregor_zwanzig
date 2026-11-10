// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): „Grenzen ändern“ (AC-16, AC-17) und Speicher-Einzigkeit (AC-38).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   AC-16 — Boeen (Alarm ab Orange, Vorlage Wandern 40/60/75): oben orange auf 50 -> Erklaersatz „über 50 km/h“,
//           Picker „1 Abweichung“, nur erlaubte Seiten als Felder, Hinweistexte; nach Speichern + Neuladen
//           gespeichert (nur die Abweichung in ampel.metrics.gust), Zeile zeigt „Fertig“ nicht mehr.
//   AC-17 — ungueltige Reihenfolge (oben, unten, unten ueber oben): Fehlertext, nichts gespeichert, alte Grenzen bleiben.
//   AC-38 — mehrere Aenderungen = genau EIN Schreibvorgang des Reiters, ampel als vollstaendige Abweichungsmenge;
//           Vergleich: ETag-Konflikt mit zweiter Sitzung laedt neu und ueberschreibt die fremde Aenderung nicht still.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-grenzen

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, type HubKind } from './helpers';
import {
	DESKTOP, WT, abweichungen, istWetterSchreiben, metriken, oeffneWetter, seedWetter, stand, vorlagen, warteAufSpeichern, type Json
} from './s3a2794-teil3.helpers';

const ohneNull = (s: Json) => Object.fromEntries(Object.entries(s ?? {}).filter(([, v]) => v !== null && v !== undefined));

async function grenzenOeffnen(reiter: Locator, id: string): Promise<Locator> {
	const zeile = reiter.getByTestId(WT.zeile(id));
	await zeile.getByTestId(WT.grenzenAendern(id)).click();
	await expect(zeile.getByTestId(WT.grenzenAendern(id))).toHaveText('Fertig');
	return zeile;
}

function schreibZaehler(page: Page, kind: HubKind, id: string): string[] {
	const liste: string[] = [];
	page.on('request', (r) => istWetterSchreiben(kind, id)(r) && liste.push(`${r.method()} ${r.url()}`));
	return liste;
}

for (const kind of HUB_KINDS) {
	test(`AC-16 (${kind}): Boeen oben orange 50 — Erklaersatz, 1 Abweichung, erlaubte Seiten, gespeichert nach Neuladen`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern' });
		try {
			const v = await vorlagen(page.request);
			const kat = await metriken(page.request);
			expect(kat.gust.allowed_sides, 'Messaufbau: Boeen nur oben').toBe('upper');
			const reiter = await oeffneWetter(page, kind, hub.id);
			const zeile = await grenzenOeffnen(reiter, 'gust');

			for (const f of ['yellow', 'orange', 'red'] as const) await expect(zeile.getByTestId(WT.grenze('gust', 'upper', f))).toBeVisible();
			for (const f of ['yellow', 'orange', 'red'] as const) await expect(zeile.getByTestId(WT.grenze('gust', 'lower', f)), 'AC-16: untere Seite bei „nur oben“').toHaveCount(0);
			await expect(zeile.getByTestId(WT.grenzenHinweis('gust'))).toContainText(
				'Grün ist alles zwischen ‚gelb unten‘ und ‚gelb oben‘. Ein leeres Feld heißt: auf dieser Seite keine Grenze.'
			);
			await expect(zeile.getByTestId(WT.grenzenAbweichend('gust')), 'Abweichungs-Satz ohne Abweichung').toHaveCount(0);

			await zeile.getByTestId(WT.grenze('gust', 'upper', 'orange')).fill('50');
			await expect(zeile.getByTestId(WT.erklaersatz('gust'))).toContainText('über 50 km/h');
			await expect(reiter.getByTestId(WT.pickerStatus)).toHaveText('1 Abweichung');
			await expect(zeile.getByTestId(WT.grenzenAbweichend('gust'))).toHaveText(`Abweichend von der Vorlage ‚${v.wandern.label}‘.`);

			const speichern = warteAufSpeichern(page, kind, hub.id);
			await zeile.getByTestId(WT.grenzenAendern('gust')).click();
			await speichern;

			await page.reload();
			const r2 = await oeffneWetter(page, kind, hub.id);
			await expect(r2.getByTestId(WT.grenzenAendern('gust'))).toHaveText('Grenzen ändern');
			await expect(r2.getByTestId(WT.erklaersatz('gust'))).toContainText('über 50 km/h');
			const s = await stand(page.request, kind, hub.id);
			const gust = s.display_config.ampel.metrics.gust;
			expect(Object.keys(gust), 'AC-16: mehr als die Abweichung gespeichert').toEqual(['upper']);
			expect(ohneNull(gust.upper)).toEqual({ yellow: 40, orange: 50, red: 75 });
			expect(Object.keys(s.display_config.ampel.metrics), 'nur gust weicht ab').toEqual(['gust']);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-16 (${kind}): erlaubte Seiten — beidseitig (Temperatur) und nur unten (Sonnenschein)`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern' });
		try {
			const kat = await metriken(page.request);
			const reiter = await oeffneWetter(page, kind, hub.id);
			for (const [id, oben, unten] of [['temperature', true, true], ['sunshine', false, true]] as const) {
				expect(kat[id].allowed_sides).toBe(oben && unten ? 'both' : 'lower');
				const zeile = await grenzenOeffnen(reiter, id);
				await expect(zeile.getByTestId(WT.grenze(id, 'upper', 'yellow'))).toHaveCount(oben ? 1 : 0);
				await expect(zeile.getByTestId(WT.grenze(id, 'lower', 'yellow'))).toHaveCount(unten ? 1 : 0);
			}
		} finally {
			await hub.aufraeumen();
		}
	});

	const UNGUELTIG: Array<[string, string, Array<[('lower' | 'upper'), ('yellow' | 'orange' | 'red'), string]>]> = [
		['oben gelb 50 / orange 40', 'gust', [['upper', 'yellow', '50'], ['upper', 'orange', '40']]],
		['unten gelb 0 / orange 5', 'temperature', [['lower', 'yellow', '0'], ['lower', 'orange', '5']]],
		['unten ueber oben', 'temperature', [['lower', 'yellow', '30'], ['upper', 'yellow', '26']]]
	];
	for (const [name, id, eingaben] of UNGUELTIG) {
		test(`AC-17 (${kind}): ${name} -> Fehlertext, nichts gespeichert, alte Grenzen bleiben`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', ampel: { metrics: { [id]: { upper: id === 'gust' ? { yellow: 41, orange: 61, red: 76 } : { yellow: 26, orange: 30, red: 33 } } } } });
			try {
				const vorher = await stand(page.request, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const schreib = schreibZaehler(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, id);
				for (const [seite, farbe, wert] of eingaben) await zeile.getByTestId(WT.grenze(id, seite, farbe)).fill(wert);
				await zeile.getByTestId(WT.grenzenAendern(id)).click();
				await expect(zeile.getByTestId(WT.grenzenFehler(id))).toBeVisible();
				await expect(zeile.getByTestId(WT.grenzenFehler(id))).not.toBeEmpty();
				await expect(zeile.getByTestId(WT.grenzenAendern(id)), 'Editor schliesst trotz Fehler').toHaveText('Fertig');
				await page.reload();
				await oeffneWetter(page, kind, hub.id);
				expect(schreib, 'AC-17: ungueltige Grenzen wurden gesendet').toEqual([]);
				expect((await stand(page.request, kind, hub.id)).display_config).toEqual(vorher.display_config);
			} finally {
				await hub.aufraeumen();
			}
		});
	}

	test(`AC-38 (${kind}): mehrere Aenderungen -> genau EIN Schreibvorgang, ampel vollstaendig`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern', ampel: { metrics: { wind: { alarm_ab: 'red' } } } });
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			const schreib = schreibZaehler(page, kind, hub.id);
			const zeile = await grenzenOeffnen(reiter, 'gust');
			await zeile.getByTestId(WT.grenze('gust', 'upper', 'orange')).fill('50');
			await zeile.getByTestId(WT.grenze('gust', 'upper', 'red')).fill('70');
			const speichern = warteAufSpeichern(page, kind, hub.id);
			await zeile.getByTestId(WT.grenzenAendern('gust')).click();
			await speichern;
			await page.reload();
			const r2 = await oeffneWetter(page, kind, hub.id);
			expect(schreib.length, `AC-38: ${schreib.length} Schreibvorgaenge: ${schreib.join(' | ')}`).toBe(1);
			const s = await stand(page.request, kind, hub.id);
			expect(s.display_config.ampel.metrics.wind, 'AC-38: bestehende Abweichung ging verloren (Teilmenge gesendet)').toEqual({ alarm_ab: 'red' });
			expect(ohneNull(s.display_config.ampel.metrics.gust.upper)).toEqual({ yellow: 40, orange: 50, red: 70 });
			expect(await abweichungen(r2)).toBe(2);
		} finally {
			await hub.aufraeumen();
		}
	});
}

test('AC-38 (vergleich): ETag-Konflikt mit zweiter Sitzung laedt neu, fremde Aenderung bleibt', async ({ browser, page }) => {
	await page.setViewportSize(DESKTOP);
	const kind: HubKind = 'vergleich';
	const hub = await seedWetter(page.request, kind, { vorlageId: 'wandern' });
	const zweit = await browser.newContext({ storageState: await page.context().storageState(), viewport: DESKTOP });
	const b = await zweit.newPage();
	try {
		const ra = await oeffneWetter(page, kind, hub.id);
		const rb = await oeffneWetter(b, kind, hub.id);
		// B aendert zuerst und speichert
		const sb = warteAufSpeichern(b, kind, hub.id);
		await rb.getByTestId(WT.zeile('wind')).getByTestId(WT.alarmAbStufe('wind', 'red')).click();
		await sb;
		// A (veralteter Stand) aendert etwas anderes
		await ra.getByTestId(WT.zeile('gust')).getByTestId(WT.alarmAbStufe('gust', 'red')).click();
		await expect
			.poll(async () => (await stand(page.request, kind, hub.id)).display_config.ampel.metrics?.wind?.alarm_ab, { timeout: 20_000 })
			.toBe('red');
		await expect(ra.getByTestId(WT.zeile('wind')).getByTestId(WT.alarmAbStufe('wind', 'red')), 'A hat nach dem Konflikt nicht neu geladen').toHaveAttribute('aria-checked', 'true', { timeout: 20_000 });
		const s = await stand(page.request, kind, hub.id);
		expect(s.display_config.ampel.metrics.wind, 'AC-38: fremde Aenderung still ueberschrieben').toEqual({ alarm_ab: 'red' });
	} finally {
		await zweit.close();
		await hub.aufraeumen();
	}
});
