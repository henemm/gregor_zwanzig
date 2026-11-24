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
// Ortsvergleich-Anlegen: AC-13 (unverändert) ist seit D2 (#3333) abgelöst — dort ebenfalls der Reiter Zustellung.
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

// Fix-Loop 1 (Adversary F001, Mutation M11): der Reiter baut seinen Startstand aus `zustellungStart`, wenn der
// Editor ihn mitgibt (Neuaufbau beim Wechsel Desktop/Mobil oder nach Schrittwechsel) — nicht aus dem Trip.
// Gemessen am echten Server-Render des Reiters: die SICHTBARE Morgenzeit, der Stille-Schalter und die
// Stille-Zeiten folgen dem mitgegebenen Stand, obwohl der Trip etwas anderes trägt (07:00, keine Stille).
describe('#3332 Test 7 (AC-6, F001): Reiter zeigt den Startstand des Editors', () => {
	const EINTRITT = { id: '__new__', name: 'SSR-3332', stages: [], report_config: undefined };
	const text = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
	async function zeige(zustellungStart?: Record<string, unknown>): Promise<string> {
		const { render } = await import('svelte/server');
		const { pathToFileURL } = await import('node:url');
		const { FRONTEND } = await import('./tripNewSsr.ts');
		const pfad = `${FRONTEND}/src/lib/components/shared/zustellung-tab/ZustellungTab.svelte`;
		const ZustellungTab = (await import(pathToFileURL(pfad).href)).default;
		return render(ZustellungTab, { props: { context: 'route', trip: EINTRITT, createMode: true, zustellungStart, onAnlegeStand: () => {} } }).body;
	}
	function karte(h: string, id: string): string {
		const i = h.indexOf(`data-testid="${id}"`);
		assert.ok(i >= 0, `${id} fehlt im Render`);
		return h.slice(i, i + 4000);
	}
	const segmente = (h: string, id: string) => text(karte(h, id).split(`data-testid="${id}-schalter"`)[0]).replace(/\s/g, '');

	test('ohne zustellungStart: Startstand aus dem Trip (Messaufbau-Gegenprobe)', async () => {
		const h = await zeige();
		assert.match(segmente(h, 'zustellung-morgen-karte'), /07:?00/, 'Messaufbau: Trip-Startzeit 07:00 nicht sichtbar');
	});

	test('mit zustellungStart (Morgen 06:45, Stille an 22:30–06:15): genau dieser Stand ist sichtbar', async () => {
		const { standAusTrip } = await import('../../shared/zustellung-tab/zustellungModell.ts');
		const start = { ...standAusTrip(EINTRITT as never), morgenZeit: '06:45', stilleAn: true, stilleVon: '22:30', stilleBis: '06:15' };
		const h = await zeige(start);
		const ohne = await zeige();
		const morgen = segmente(h, 'zustellung-morgen-karte');
		assert.match(morgen, /06:?45/, `Reiter ignoriert zustellungStart: Morgenzeit ${morgen}`);
		assert.doesNotMatch(morgen, /07:?00/);
		const stille = karte(h, 'zustellung-stille-schalter').slice(0, 600);
		const stilleOhne = karte(ohne, 'zustellung-stille-schalter').slice(0, 600);
		assert.notEqual(stille, stilleOhne, 'Stille-Schalter folgt nicht dem zustellungStart');
		assert.match(text(karte(h, 'zustellung-stille-von')).replace(/\s/g, ''), /22:?30/, 'Stille-von folgt nicht dem zustellungStart');
	});
});

// #3333 (D2, AC-1) löst AC-13 von D1 ab: das Ortsvergleich-Anlegen zeigt jetzt ebenfalls den Reiter Zustellung
// (context="vergleich") statt des Alt-Panels. Ausführlich: compare-new/__tests__/vergleich_anlegen_zustellung_ssr_3333.test.ts.
describe('#3332 Test 6 (AC-13, abgelöst durch #3333): Ortsvergleich-Anlegen folgt seit D2', () => {
	for (const mobil of [false, true]) {
		test(`${mobil ? 'Mobil' : 'Desktop'}: Schritt Zustellung zeigt den Reiter Zustellung (vergleich), kein Alt-Panel`, async () => {
			const html = await renderVergleichNeu({ metrikenVisited: true, zustellungVisited: true, activeTab: 'zustellung', isMobileViewport: mobil });
			assert.equal(countTestid(html, 'versand-abschnitt'), 0, 'Ortsvergleich-Anlegen zeigt noch den Versand-Abschnitt des Alt-Panels');
			assert.equal(countTestid(html, 'zustellung-tab'), 1, 'Ortsvergleich-Anlegen ohne Reiter Zustellung');
			assert.match(html, /data-testid="zustellung-tab"[^>]*data-context="vergleich"/);
		});
	}
});
