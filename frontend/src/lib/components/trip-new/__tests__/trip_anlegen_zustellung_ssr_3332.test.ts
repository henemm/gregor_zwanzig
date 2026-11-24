// TDD RED — Issue #3332 (Teil D1 von #3307, Epic #3122): im Schritt Zustellung des Trip-Anlegens steht der
// Reiter „Zustellung“ wie im Hub; Alt-Panel (Versand-Abschnitt) und Mail-Inhalt-Karte sind dort weg.
// Spec docs/specs/modules/feat_3332_zustellung_anlegen_trip.md, Test Plan Nr. 6 (AC-1, AC-13).
//
// Gemessen am ECHTEN serverseitigen Render der Anlege-Seiten (svelte/server, Test-Seam `stateOverride`),
// Desktop UND Mobil (Editor hält beide Mounts XOR hinter isMobileViewport). Kennungen:
//   Reiter Zustellung  data-testid="zustellung-tab" data-context="route" (+ Kanal-Tabelle, Briefing-Zeiten,
//                      Stille Stunden: zustellung-kanal-tabelle, zustellung-morgen-karte, zustellung-stille-schalter)
//   Alt-Panel          data-testid="versand-abschnitt", Kanal-Schalter channel-email
//   Mail-Inhalt-Karte  data-testid="report-mail-content"
// Ortsvergleich-Anlegen bleibt unverändert (AC-13): dort weiter der Versand-Abschnitt des Alt-Panels.
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_anlegen_zustellung_ssr_3332.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { renderTripNew, assertTabOffen, countTestid, bereichVon } from './tripNewSsr.ts';
import { renderVergleichNeu } from '../../shared/__tests__/infoboxSsr.ts';

const TRIP = { name: 'SSR-3332', startDate: '2026-12-01', stageNames: ['E1'], wtVisited: true, zuVisited: true };

describe('#3332 Test 6 (AC-1): Trip-Anlegen, Schritt Zustellung', () => {
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		test(`${ansicht}: Reiter Zustellung mit Briefing-Zeiten, Kanal-Tabelle, Stille Stunden — genau einmal, im richtigen Baum`, () => {
			const html = renderTripNew({ ...TRIP, activeTab: 'zustellung', isMobileViewport: mobil });
			assertTabOffen(html, 'zustellung');
			assert.equal(countTestid(html, 'zustellung-tab'), 1, 'Reiter Zustellung nicht genau einmal im Schritt Zustellung');
			assert.equal(bereichVon(html, 'zustellung-tab'), mobil ? 'mobil' : 'desktop');
			assert.match(html, /data-testid="zustellung-tab"[^>]*data-context="route"/);
			for (const id of ['zustellung-morgen-karte', 'zustellung-abend-karte', 'zustellung-stille-schalter'])
				assert.equal(countTestid(html, id), 1, `Baustein ${id} fehlt im Reiter`);
			// Die Kanal-Tabelle selbst steht erst nach dem Profil-Abruf (onMount, im SSR nie) — ihr Abschnitt schon.
			for (const abschnitt of ['briefing-zeiten', 'kanaele', 'stille-stunden'])
				assert.equal(html.split(`data-abschnitt="${abschnitt}"`).length - 1, 1, `Abschnitt ${abschnitt} nicht genau einmal`);
		});

		test(`${ansicht}: Alt-Panel (Versand-Abschnitt) und Mail-Inhalt-Karte erscheinen nicht mehr`, () => {
			const html = renderTripNew({ ...TRIP, activeTab: 'zustellung', isMobileViewport: mobil });
			assertTabOffen(html, 'zustellung');
			assert.equal(countTestid(html, 'versand-abschnitt'), 0, 'Alt-Panel noch im Trip-Anlegen (zweiter Schreiber der Versand-Felder)');
			assert.equal(countTestid(html, 'channel-email'), 0, 'Kanal-Schalter des Alt-Panels noch im Trip-Anlegen');
			assert.equal(countTestid(html, 'report-mail-content'), 0, 'Mail-Inhalt-Karte noch im Trip-Anlegen (Hub hat keine)');
		});
	}
});

describe('#3332 Test 6 (AC-13): Ortsvergleich-Anlegen unverändert', () => {
	for (const mobil of [false, true]) {
		test(`${mobil ? 'Mobil' : 'Desktop'}: Schritt Zustellung zeigt weiter das Alt-Panel, keinen Reiter Zustellung`, async () => {
			const html = await renderVergleichNeu({ metrikenVisited: true, zustellungVisited: true, activeTab: 'zustellung', isMobileViewport: mobil });
			assert.ok(countTestid(html, 'versand-abschnitt') >= 1, 'Ortsvergleich-Anlegen ohne Versand-Abschnitt (D1 darf dort nichts ändern)');
			assert.equal(countTestid(html, 'zustellung-tab'), 0, 'Ortsvergleich-Anlegen zeigt bereits den Reiter Zustellung (gehört zu D2, #3333)');
		});
	}
});
