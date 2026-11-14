// E2E — Issue #2999: Datumsfeld — getippter Tag 29–31 bleibt unverändert, ein Datum, das es nicht
// gibt, wird gemeldet und nicht gespeichert.
// Spec: docs/specs/modules/fix_2999_datumfeld_tag_31.md (AC-1 bis AC-12)
//
// Die Browser-Uhr wird per page.clock.setFixedTime eingefroren, damit der Nachweis nicht vom
// heutigen Monat abhängt: 14.11.2026 (Bezugsmonat mit 30 Tagen) und 10.02.2027 (28 Tage, der
// härteste Fall: dort rutscht ohne Fix die „1" von „31" ins Monatssegment).
// Wirkstellen: Laufzeit-Datum im Reiter Zustellung (Orts-Briefing, leeres Feld, speichert end_date),
// Startdatum beim Trip-Anlegen (leerMelden), Etappen-Datum (gefülltes Feld, Autosave).
//
//   cd frontend && npx playwright test --config playwright.2999-datumfeld.staging.config.ts

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { ANLEGE_SEL, feldEingabe, hubApiPath, openHub, seedHub, tippeDatum, tippeUhrzeit } from './helpers';
import { DESKTOP, ZT, gespeicherteZeit, oeffneZustellung, seedZustellung, stand } from './s3b2795-zustellung.helpers';

const UHREN = [
	{ name: 'November (30 Tage)', zeit: '2026-11-14T10:00:00' },
	{ name: 'Februar (28 Tage)', zeit: '2027-02-10T10:00:00' }
] as const;

const MELDUNG_DE = 'Dieses Datum gibt es nicht.';
const MELDUNG_EN = 'This date does not exist.';

const anzeige = (iso: string): string => iso.split('-').reverse().join('.');

/** Sammelt alle PUTs auf einen Hub (Trip oder Orts-Briefing) — Beweis „nichts/genau einmal gespeichert". */
function sammlePuts(page: Page, pfad: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) puts.push(r);
	});
	return puts;
}

/** Feld verlassen (Tab bliebe im nächsten Segment desselben Felds). */
const verlasseFeld = (page: Page) => page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

/** Meldung „Datum gibt es nicht" (role=alert) — gefiltert, weil der Reiter eigene Warnboxen hat. */
const datumMeldung = (page: Page, text = MELDUNG_DE): Locator => page.getByRole('alert').filter({ hasText: text });

/** Öffnet das Laufzeit-Datumsfeld (Orts-Briefing, „Bis Datum") und liefert Feld + PUT-Sammler. */
async function laufzeitFeld(page: Page, hubId: string): Promise<{ feld: Locator; puts: Request[] }> {
	const reiter = await oeffneZustellung(page, 'vergleich', hubId);
	const karte = reiter.locator('[data-abschnitt="laufzeit"]');
	const puts = sammlePuts(page, hubApiPath('vergleich', hubId));
	await karte.getByTestId(ZT.laufzeitBisDatum).click();
	const feld = karte.getByTestId(ZT.laufzeitDatum);
	await expect(feld).toBeVisible();
	// Gezählt werden nur PUTs mit gesetztem end_date (siehe enddaten).
	return { feld, puts };
}

/** end_date-Werte aller bisher gesendeten PUTs, die ein Enddatum tragen. */
const enddaten = (puts: Request[]): string[] =>
	puts.map((r) => (r.postDataJSON() ?? {}).end_date).filter((d): d is string => typeof d === 'string' && d !== '');

/** Alle drei Segmente stehen auf Platzhalter (Feld leer). */
async function erwarteLeer(feld: Locator): Promise<void> {
	for (const s of ['day', 'month', 'year']) {
		// bits-ui markiert ein leeres Segment mit aria-valuetext="Empty" (fester Wert, nicht übersetzt).
		await expect(feld.locator(`[data-segment="${s}"]`), `Segment ${s} leer`).toHaveAttribute('aria-valuetext', 'Empty');
	}
}

// ─── AC-1 / AC-2 / AC-3 / AC-11: gültige Daten kommen unverändert an ────────────────────

for (const uhr of UHREN) {
	for (const iso of ['2027-03-31', '2028-02-29']) {
		test(`AC-1/2/3/11 (${uhr.name}): leeres Feld, ${anzeige(iso)} getippt → steht unverändert im Feld und wird so gespeichert`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await page.clock.setFixedTime(new Date(uhr.zeit));
			const hub = await seedZustellung(page.request, 'vergleich');
			try {
				const { feld, puts } = await laufzeitFeld(page, hub.id);
				await tippeDatum(page, feld, iso);
				// Noch im Feld: kein Segment verrutscht, die Anzeige ist genau das Getippte.
				await expect(feldEingabe(feld), 'Anzeige nach dem Tippen').toHaveText(anzeige(iso));
				await expect(feld.locator('[data-segment="day"]')).toHaveText(iso.slice(8, 10));
				await expect(feld.locator('[data-segment="month"]')).toHaveText(iso.slice(5, 7));
				await expect(feld.locator('[data-segment="year"]')).toHaveText(iso.slice(0, 4));
				await page.keyboard.press('Tab');
				await expect.poll(async () => (await stand(page.request, 'vergleich', hub.id)).end_date, { message: 'gespeichertes end_date', timeout: 15_000 }).toBe(iso);
				expect(enddaten(puts), 'genau ein Speichervorgang mit dem getippten Datum, kein Zwischenstand').toEqual([iso]);
				await expect(feldEingabe(feld), 'Anzeige nach dem Verlassen').toHaveText(anzeige(iso));
				await expect(datumMeldung(page)).toHaveCount(0);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

// ─── AC-4 / AC-5 / AC-8: ungültige Daten werden gemeldet, nichts gespeichert ───────────

for (const uhr of UHREN) {
	for (const [ungueltig, gueltig] of [
		['2027-04-31', '2027-04-30'],
		['2027-02-29', '2027-03-01']
	] as const) {
		test(`AC-4/5/8 (${uhr.name}): ${anzeige(ungueltig)} → Meldung, nichts gespeichert, Feld leer; danach ${anzeige(gueltig)} → Meldung weg, gespeichert`, async ({ page }) => {
			await page.setViewportSize(DESKTOP);
			await page.clock.setFixedTime(new Date(uhr.zeit));
			const hub = await seedZustellung(page.request, 'vergleich');
			try {
				const { feld, puts } = await laufzeitFeld(page, hub.id);
				// Ziffern einzeln: `tippeDatum` erwartet ein ISO-Datum, das es geben kann.
				const [j, m, t] = ungueltig.split('-');
				await feld.locator('[data-segment="day"]').click();
				await page.keyboard.type(`${t}${m}${j}`);

				const meldung = datumMeldung(page);
				await expect(meldung, `Meldung „${MELDUNG_DE}"`).toBeVisible();
				await expect(meldung).toHaveText(MELDUNG_DE);
				// Direkt unter dem Feld.
				const fb = (await feld.boundingBox())!;
				const mb = (await meldung.boundingBox())!;
				expect(mb.y, 'Meldung steht unter dem Feld').toBeGreaterThanOrEqual(fb.y + fb.height - 1);
				expect(mb.y - (fb.y + fb.height), 'Meldung direkt unter dem Feld').toBeLessThan(40);
				await erwarteLeer(feld);

				await verlasseFeld(page);
				await erwarteLeer(feld);
				expect((await stand(page.request, 'vergleich', hub.id)).end_date ?? null, 'nichts gespeichert').toBeNull();

				// AC-8: danach ein gültiges Datum — Meldung verschwindet, Wert wird übernommen.
				await tippeDatum(page, feld, gueltig);
				await expect(meldung, 'Meldung verschwindet nach gültigem Datum').toHaveCount(0);
				await page.keyboard.press('Tab');
				await expect.poll(async () => (await stand(page.request, 'vergleich', hub.id)).end_date, { message: 'gültiges Datum gespeichert', timeout: 15_000 }).toBe(gueltig);
				expect(enddaten(puts), 'das ungültige Datum hat nie einen (geklemmten) Speichervorgang ausgelöst').toEqual([gueltig]);
			} finally {
				await hub.aufraeumen();
			}
		});
	}
}

// ─── AC-6: Trip anlegen (leerMelden) — keine Doppelmeldung mit „Startdatum fehlt" ───────

test('AC-6: Trip anlegen, ungültiges Startdatum → nur „Dieses Datum gibt es nicht.", nicht zusätzlich „Startdatum fehlt"', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.clock.setFixedTime(new Date(UHREN[0].zeit));
	await page.goto(ANLEGE_SEL.route.url);
	const feld = page.getByTestId('trip-new-date-input-desktop');
	await expect(feld).toBeVisible({ timeout: 15_000 });
	await ANLEGE_SEL.route.name(page).fill(`E2E-GZ-2999-${Date.now()}`);
	const fehlt = page.getByText('Startdatum fehlt', { exact: true });
	await expect(fehlt, 'Vorbedingung: Pflichthinweis bei leerem Datum').toBeVisible();

	await feld.locator('[data-segment="day"]').click();
	await page.keyboard.type('31042027');
	await expect(datumMeldung(page)).toBeVisible();
	await expect(fehlt, 'keine Doppelmeldung, solange die Datumsmeldung steht').toBeHidden();
	await verlasseFeld(page);
	await expect(datumMeldung(page)).toBeVisible();
	await expect(fehlt, 'keine Doppelmeldung nach dem Verlassen').toBeHidden();
	await expect(page.getByTestId('trip-new-continue-etappen'), 'ohne gültiges Datum kein Weiter').toBeDisabled();
});

// ─── AC-7: gefülltes Etappenfeld — kein geklemmter Zwischen-PUT ─────────────────────────

test('AC-7: Etappe 15.04.2027, 31052027 darübergetippt → genau ein Speichervorgang mit 31.05.2027', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.clock.setFixedTime(new Date(UHREN[0].zeit));
	const hub = await seedHub(page.request, 'route', {
		extra: {
			stages: [{ id: 's1', name: 'Tag 1', date: '2027-04-15', waypoints: [{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 }, { id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 1200 }] }]
		}
	});
	try {
		await openHub(page, 'route', hub.id, { tab: 'etappen' });
		const feld = page.locator('[data-testid="stage-date-field"]:visible').first();
		await expect(feldEingabe(feld)).toHaveText('15.04.2027', { timeout: 15_000 });
		const puts = sammlePuts(page, hubApiPath('route', hub.id));
		await tippeDatum(page, feld, '2027-05-31');
		await expect(feldEingabe(feld), 'Anzeige nach dem Tippen').toHaveText('31.05.2027');
		await verlasseFeld(page);
		await expect
			.poll(async () => ((await stand(page.request, 'route', hub.id)).stages as { date: string }[])[0]?.date, { message: 'gespeichertes Etappen-Datum', timeout: 15_000 })
			.toBe('2027-05-31');
		const daten = puts.map((r) => ((r.postDataJSON() ?? {}).stages as { date?: string }[] | undefined)?.[0]?.date ?? null);
		expect(daten, 'kein Zwischenstand (30.04./01.05.) gespeichert, genau ein PUT mit 31.05.2027').toEqual(['2027-05-31']);
		await expect(feldEingabe(feld)).toHaveText('31.05.2027');
	} finally {
		await hub.aufraeumen();
	}
});

// ─── AC-9: Englisch — Meldung aus dem Katalog, Screenreader-Verknüpfung ─────────────────

test('AC-9: Sprache EN, 31042027 → „This date does not exist.", role=alert, per aria-describedby am Feld', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.clock.setFixedTime(new Date(UHREN[0].zeit));
	const hub = await seedZustellung(page.request, 'vergleich');
	try {
		const res = await page.request.put('/api/auth/profile', { data: { language: 'en' } });
		expect(res.ok(), `Sprache en setzen: HTTP ${res.status()}`).toBeTruthy();
		const { feld } = await laufzeitFeld(page, hub.id);
		await feld.locator('[data-segment="day"]').click();
		await page.keyboard.type('31042027');
		const meldung = datumMeldung(page, MELDUNG_EN);
		await expect(meldung).toBeVisible();
		await expect(meldung).toHaveText(MELDUNG_EN);
		await expect(page.getByText(MELDUNG_DE)).toHaveCount(0);
		const id = await meldung.getAttribute('id');
		expect(id, 'Meldung braucht eine id für aria-describedby').toBeTruthy();
		await expect(feld.locator(`[aria-describedby~="${id}"]`).first(), 'Feld ist per aria-describedby mit der Meldung verknüpft').toBeAttached();
	} finally {
		await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
		await hub.aufraeumen();
	}
});

// ─── AC-10: Regression Kalenderklick und Backspace ─────────────────────────────────────

test('AC-10: Kalenderklick übernimmt den Tag; Backspace leert das Segment ohne Speichern bis das Datum vollständig ist', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.clock.setFixedTime(new Date(UHREN[0].zeit));
	const hub = await seedZustellung(page.request, 'vergleich');
	try {
		const { feld, puts } = await laufzeitFeld(page, hub.id);
		await feld.locator('[data-slot="datum-feld-kalender-knopf"]').click();
		const kalender = page.locator('[data-slot="datum-feld-kalender"]:visible');
		await expect(kalender).toBeVisible();
		await kalender.locator('[data-value="2026-11-20"]:not([data-outside-month])').getByRole('button').click();
		await expect(feldEingabe(feld)).toHaveText('20.11.2026');
		await expect.poll(async () => (await stand(page.request, 'vergleich', hub.id)).end_date, { message: 'Kalenderklick gespeichert', timeout: 15_000 }).toBe('2026-11-20');

		await feld.locator('[data-segment="day"]').click();
		await page.keyboard.press('Backspace');
		await page.keyboard.press('Backspace');
		await expect(feld.locator('[data-segment="day"]'), 'Backspace leert das Tag-Segment').toHaveAttribute('aria-valuetext', 'Empty');
		await expect(datumMeldung(page)).toHaveCount(0);
		expect(enddaten(puts), 'Backspace speichert nichts Neues').toEqual(['2026-11-20']);
		await page.keyboard.type('25');
		await verlasseFeld(page);
		await expect.poll(async () => (await stand(page.request, 'vergleich', hub.id)).end_date, { message: 'vervollständigtes Datum gespeichert', timeout: 15_000 }).toBe('2026-11-25');
		expect(enddaten(puts)).toEqual(['2026-11-20', '2026-11-25']);
	} finally {
		await hub.aufraeumen();
	}
});

// ─── AC-12: Uhrzeitfeld unverändert, keine Datumsmeldung ───────────────────────────────

test('AC-12: Uhrzeit 08:15 im Morgen-Briefing tippen → gespeichert, keine Datumsmeldung', async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await page.clock.setFixedTime(new Date(UHREN[1].zeit));
	const hub = await seedZustellung(page.request, 'vergleich');
	try {
		const reiter = await oeffneZustellung(page, 'vergleich', hub.id);
		await tippeUhrzeit(page, reiter.getByTestId(ZT.zeit('morgen')), '08:15');
		await verlasseFeld(page);
		await expect.poll(async () => gespeicherteZeit('vergleich', await stand(page.request, 'vergleich', hub.id), 'morgen'), { timeout: 15_000 }).toBe('08:15');
		await expect(datumMeldung(page)).toHaveCount(0);
	} finally {
		await hub.aufraeumen();
	}
});
