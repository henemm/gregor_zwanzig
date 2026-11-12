// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): die Wertebereiche verhalten sich im Browser für
// BEIDE Hubs (Trip und Ortsvergleich) gleich — Schleife über HUB_KINDS, Desktop UND Mobil.
//
// Spec (Ursprung): docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-4 (WW-1..WW-4)
//
// Verlauf: #2792 S1c-3 machte die Korridor-Zeilen (CorridorEditor/CorridorEditorMobile) nur lesbar.
// #2794 Teil 3 (docs/specs/modules/feat_2794_s3a_teil3_wetter.md §4, Known Limitations „Löschung erst
// Teil-PR 4") mountet sie im Reiter Wetter nicht mehr; die Grenzen stehen jetzt in der Ampel-Zeile
// („Grenzen ändern", AC-16). Jeder Fall prüft dieselbe Aussage wie vorher am neuen Träger:
//   - der gespeicherte Wert (Wertprop, hier `display_config.ampel.metrics.<id>`) wird ANGEZEIGT,
//   - eine bestätigte Änderung („Fertig") erzeugt genau EINEN Schreibvorgang und überlebt das Neuladen,
//   - eine nicht bestätigte Eingabe (Verlassen des Feldes, „Fertig" ohne Änderung) sendet NICHTS,
//   - es gibt keinen Sprung in einen Alt-Editor (/edit) und keinen Fehlerbanner.
//
// Stabilitätsfenster per expect.poll statt festem Schlaf. Läuft im isolierten CI-Stack
// (frontend/e2e/ci-stack.sh), Anmeldung über den storageState aus global.setup.ts.
// Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect } from '@playwright/test';
import { HUB_KINDS } from './helpers';
import { DESKTOP, MOBIL, WT, auswahlImStand, oeffneWetter } from './s3a2794-teil3.helpers';
import {
	ALTFELDER,
	anzeige,
	bleibtBei,
	dc,
	fertig,
	grenzenOeffnen,
	seedGrenzen,
	seiteImStand,
	stand,
	zaehleAlleSchreiben,
	zaehleWetterSchreiben
} from './s3a2794-wetter-ci.helpers';

/** Böen (nur oben) mit gespeicherter Abweichung von „wandern" (40/60/75): oben orange 55. */
const ZEILE = 'gust';
const GESPEICHERT = { [ZEILE]: { upper: { yellow: 40, orange: 55, red: 75 } } };

for (const kind of HUB_KINDS) {
	test.describe(`Hub · Wertebereiche (Reiter Wetter, Grenzen) auf Wertprops (${kind})`, () => {
		// WW-1 — fängt: der gespeicherte Wert erreicht das Feld nicht (Anzeige falsch) bzw. die
		// bestätigte Änderung wird nicht oder doppelt geschrieben.
		test(`WW-1 (${kind}): Feld zeigt den gespeicherten Wert, Ändern + „Fertig" → genau EIN Schreibvorgang, überlebt Neuladen`, async ({
			page
		}) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedGrenzen(page.request, kind, GESPEICHERT);
			try {
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);
				await expect(reiter.getByTestId(WT.erklaersatz(ZEILE)), 'der gespeicherte Wert steht im Erklärsatz').toContainText('55');
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				const feld = zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'orange'));
				await expect(feld, 'der gespeicherte Wert wird angezeigt').toHaveValue('55');

				await feld.fill('62');
				await fertig(zeile, ZEILE);
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await bleibtBei(() => puts.length, 1, 1_200, 'WW-1: genau EIN Schreibvorgang');
				expect(seiteImStand(await stand(page, kind, hub.id), ZEILE, 'upper')).toEqual({ yellow: 40, orange: 62, red: 75 });

				const r2 = await oeffneWetter(page, kind, hub.id);
				const z2 = await grenzenOeffnen(r2, ZEILE);
				await expect(z2.getByTestId(WT.grenze(ZEILE, 'upper', 'orange'))).toHaveValue('62');
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-2 — derselbe Weg am Handy (390 × 844): Anzeige, Ändern, Speichern, Neuladen.
		test(`WW-2 (${kind}): Mobil — Feld zeigt den gespeicherten Wert, Ändern + „Fertig" → gespeichert, überlebt Neuladen`, async ({ page }) => {
			await page.setViewportSize(MOBIL);
			const hub = await seedGrenzen(page.request, kind, GESPEICHERT);
			try {
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				const feld = zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'red'));
				await expect(feld, 'der gespeicherte Wert wird angezeigt').toHaveValue('75');
				await feld.fill('80');
				await fertig(zeile, ZEILE);
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await bleibtBei(() => puts.length, 1, 1_200, 'WW-2: genau EIN Schreibvorgang');
				expect(seiteImStand(await stand(page, kind, hub.id), ZEILE, 'upper')).toEqual({ yellow: 40, orange: 55, red: 80 });

				const r2 = await oeffneWetter(page, kind, hub.id);
				const z2 = await grenzenOeffnen(r2, ZEILE);
				await expect(z2.getByTestId(WT.grenze(ZEILE, 'upper', 'red'))).toHaveValue('80');
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3a (Alt compare-hub-inline-edit AC-33) — Zahlenfeld tippen und verlassen ohne „Fertig":
		// kein Schreibvorgang, kein Redirect in einen Alt-Editor, Serverstand unverändert.
		test(`WW-3a (${kind}): Feld tippen und verlassen ohne „Fertig" → KEIN Schreibvorgang, kein Redirect, Serverstand unverändert`, async ({
			page
		}) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedGrenzen(page.request, kind, GESPEICHERT);
			try {
				const alle = zaehleAlleSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				const feld = zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'yellow'));
				await feld.fill('45');
				await feld.blur();

				await bleibtBei(() => alle.length, 0, 1_200, 'WW-3a: Verlassen des Feldes ohne „Fertig" darf nichts senden');
				expect(seiteImStand(await stand(page, kind, hub.id), ZEILE, 'upper')).toEqual(GESPEICHERT[ZEILE].upper);
				await expect(page).not.toHaveURL(/\/edit/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3b (Alt compare-hub-inline-edit AC-34) — „Metrik hinzufügen" heißt jetzt „+" unter
		// „Nicht im Briefing" (AC-19): neue Zeile, genau EIN Schreibvorgang, bestehende Grenzen und
		// Altfelder bleiben, kein Redirect.
		test(`WW-3b (${kind}): „+ Metrik" unter „Nicht im Briefing" → neue Zeile, genau EIN Schreibvorgang, Grenzen und Altfelder unverändert`, async ({
			page
		}) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedGrenzen(page.request, kind, GESPEICHERT);
			try {
				const vorher = ALTFELDER[kind](await stand(page, kind, hub.id));
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const plus = reiter.getByTestId(WT.nichtImBriefing).locator('[data-testid^="wetter-nicht-im-briefing-plus-"]').first();
				const neu = (await plus.getAttribute('data-testid'))!.replace('wetter-nicht-im-briefing-plus-', '');
				const zeilenVorher = await reiter.locator('[data-testid^="wetter-zeile-"]:not([data-testid^="wetter-zeile-entfernen-"])').count();
				await plus.click();
				await expect(reiter.getByTestId(WT.zeile(neu)), 'die neue Zeile steht im Briefing').toBeVisible();
				await expect(reiter.locator('[data-testid^="wetter-zeile-"]:not([data-testid^="wetter-zeile-entfernen-"])')).toHaveCount(zeilenVorher + 1);

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await bleibtBei(() => puts.length, 1, 1_200, 'WW-3b: genau EIN Schreibvorgang');
				const s = await stand(page, kind, hub.id);
				expect(auswahlImStand(kind, s)).toContain(neu);
				expect(seiteImStand(s, ZEILE, 'upper'), 'bestehende Grenzen unverändert').toEqual(GESPEICHERT[ZEILE].upper);
				expect(ALTFELDER[kind](s), 'AC-30: Altfelder (Korridore usw.) unverändert').toEqual(vorher);
				await expect(page).not.toHaveURL(/\/edit/);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-3c (Alt compare-hub-inline-edit F002) — „Grenzen ändern" öffnen und ohne Änderung mit
		// „Fertig" schließen: nichts geschrieben, Wert bleibt, überlebt Neuladen.
		test(`WW-3c (${kind}): „Grenzen ändern" öffnen, ohne Änderung „Fertig" → KEIN Schreibvorgang, Wert bleibt, überlebt Neuladen`, async ({
			page
		}) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedGrenzen(page.request, kind, GESPEICHERT);
			try {
				const alle = zaehleAlleSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				await expect(zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'orange'))).toHaveValue('55');
				await fertig(zeile, ZEILE);

				await bleibtBei(() => alle.length, 0, 1_200, 'WW-3c: „Fertig" ohne Änderung darf nichts senden');
				await expect(reiter.getByTestId(WT.pickerStatus), 'Abweichungszahl unverändert').toHaveText('1 Abweichung');
				expect(seiteImStand(await stand(page, kind, hub.id), ZEILE, 'upper')).toEqual(GESPEICHERT[ZEILE].upper);

				const r2 = await oeffneWetter(page, kind, hub.id);
				const z2 = await grenzenOeffnen(r2, ZEILE);
				await expect(z2.getByTestId(WT.grenze(ZEILE, 'upper', 'orange'))).toHaveValue('55');
			} finally {
				await hub.aufraeumen();
			}
		});

		// WW-4 — beidseitig offene Grenze (früher „×" auf der letzten Grenze): AC-16 „Ein leeres Feld
		// heißt: auf dieser Seite keine Grenze." Temperatur (beidseitig) ganz leeren → „immer grün",
		// kein Fehlertext, kein Fehlerbanner, gespeichert, Anzeige „Gespeichert".
		test(`WW-4 (${kind}): beidseitig offene Grenze herstellen (alle Felder leer) → „immer grün", kein Fehler, genau EIN Schreibvorgang, Serverstand folgt`, async ({
			page
		}) => {
			await page.setViewportSize(DESKTOP);
			const hub = await seedGrenzen(page.request, kind);
			try {
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const id = 'temperature';
				const zeile = await grenzenOeffnen(reiter, id);
				for (const seite of ['lower', 'upper'] as const)
					for (const f of ['yellow', 'orange', 'red'] as const) await zeile.getByTestId(WT.grenze(id, seite, f)).fill('');
				await fertig(zeile, id);

				await expect(zeile.getByTestId(WT.grenzenFehler(id)), 'WW-4: kein Fehlertext').toHaveCount(0);
				await expect(zeile.getByTestId(WT.gruen(id))).toHaveText('· immer grün (keine Grenze gesetzt)');
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await bleibtBei(() => puts.length, 1, 2_500, 'WW-4: genau EIN Schreibvorgang');
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle');
				const s = await stand(page, kind, hub.id);
				expect(seiteImStand(s, id, 'lower'), 'unten ohne Grenze gespeichert').toEqual({});
				expect(seiteImStand(s, id, 'upper'), 'oben ohne Grenze gespeichert').toEqual({});
				expect(dc(s).ampel.template).toBe('wandern');
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
