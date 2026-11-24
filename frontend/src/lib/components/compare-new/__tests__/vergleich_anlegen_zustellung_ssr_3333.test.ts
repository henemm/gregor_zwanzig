// TDD RED — Issue #3333 (Teil D2 von #3307, Epic #3122): im Schritt Zustellung des Ortsvergleich-Anlegens
// steht der Reiter „Zustellung“ wie im Hub; das Alt-Panel (Versand-Abschnitt, Karte „Layout je Kanal“,
// Infobox) ist dort weg, der Aktivierungs-Banner bleibt und kommt aus dem Reiter.
// Spec docs/specs/modules/feat_3333_zustellung_anlegen_orte.md, Test Plan Nr. 6 und 8 (AC-1, AC-11, AC-12).
// Pendant zu trip-new/__tests__/trip_anlegen_zustellung_ssr_3332.test.ts.
//
// Gemessen am ECHTEN serverseitigen Render der Anlege-Seite (svelte/server, Test-Seam `stateOverride`),
// Desktop UND Mobil (der Editor hält beide Mounts XOR hinter isMobileViewport). Kennungen:
//   Reiter Zustellung  data-testid="zustellung-tab" data-context="vergleich" (+ zustellung-morgen-karte,
//                      zustellung-abend-karte, zustellung-stille-schalter; Abschnitte data-abschnitt=…)
//   Alt-Panel          data-testid="versand-abschnitt", Kanal-Schalter compare-step5-channel-email,
//                      Karte „Layout je Kanal“ weather-metrics-vergleich-reihenfolge, Infoboxen infobox-versand-vergleich /
//                      infobox-wetter-metriken-vergleich
//   Banner             data-testid="compare-step5-activation-banner" data-ready="true|false"
//
//   cd frontend && npm test -- src/lib/components/compare-new/__tests__/vergleich_anlegen_zustellung_ssr_3333.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { renderVergleichNeu, innen, testids, tagsMitTestid, attribut } from '../../shared/__tests__/infoboxSsr.ts';

const BESUCHT = { metrikenVisited: true, zustellungVisited: true, activeTab: 'zustellung' };

function countTestid(html: string, testid: string): number {
	return html.split(`data-testid="${testid}"`).length - 1;
}
/** Desktop- oder Mobil-Baum? Der Mobil-Baum ist der letzte `.cm-mobile`-Block des Dokuments. */
function bereichVon(html: string, testid: string): 'desktop' | 'mobil' {
	const mi = html.indexOf(`data-testid="${testid}"`);
	assert.notEqual(mi, -1, `Testid "${testid}" fehlt im gerenderten Dokument.`);
	const mobil = html.lastIndexOf('class="cm-mobile');
	assert.notEqual(mobil, -1, 'Mobil-Inhaltsbaum (.cm-mobile) nicht gefunden.');
	return mi < mobil ? 'desktop' : 'mobil';
}

describe('#3333 Test 6 (AC-1): Orte-Anlegen, Schritt Zustellung', () => {
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		test(`${ansicht}: Reiter Zustellung mit Briefing-Zeiten, Kanal-Tabelle, Stille Stunden — genau einmal, im richtigen Baum`, async () => {
			const html = await renderVergleichNeu({ ...BESUCHT, isMobileViewport: mobil });
			assert.equal(countTestid(html, 'zustellung-tab'), 1, 'Reiter Zustellung nicht genau einmal im Schritt Zustellung');
			assert.equal(bereichVon(html, 'zustellung-tab'), mobil ? 'mobil' : 'desktop');
			assert.match(html, /data-testid="zustellung-tab"[^>]*data-context="vergleich"/);
			for (const id of ['zustellung-morgen-karte', 'zustellung-abend-karte', 'zustellung-stille-schalter'])
				assert.equal(countTestid(html, id), 1, `Baustein ${id} fehlt im Reiter`);
			// Die Kanal-Tabelle selbst steht erst nach dem Profil-Abruf (onMount, im SSR nie) — ihr Abschnitt schon.
			for (const abschnitt of ['briefing-zeiten', 'laufzeit', 'kanaele', 'stille-stunden'])
				assert.equal(html.split(`data-abschnitt="${abschnitt}"`).length - 1, 1, `Abschnitt ${abschnitt} nicht genau einmal`);
		});

		test(`${ansicht}: Alt-Panel (Versand-Abschnitt, Kanal-Schalter, Karte „Layout je Kanal“) erscheint nicht mehr`, async () => {
			const html = await renderVergleichNeu({ ...BESUCHT, isMobileViewport: mobil });
			assert.ok(countTestid(html, 'zustellung-tab') >= 1, 'Messaufbau: Schritt Zustellung ohne Reiter gerendert');
			assert.equal(countTestid(html, 'versand-abschnitt'), 0, 'Alt-Panel noch im Orte-Anlegen (zweiter Schreiber der Versand-Felder)');
			assert.equal(countTestid(html, 'compare-step5-channel-email'), 0, 'Kanal-Schalter des Alt-Panels noch im Orte-Anlegen');
			assert.equal(countTestid(html, 'versand-tab'), 0, 'VersandTab noch im Orte-Anlegen');
			assert.equal(countTestid(html, 'weather-metrics-vergleich-reihenfolge'), 0, 'Karte „Layout je Kanal“ (#3301) noch im Orte-Anlegen');
		});

		test(`${ansicht}: Aktivierungs-Banner steht im Reiter Zustellung, genau einmal, mit data-ready (AC-11)`, async () => {
			const html = await renderVergleichNeu({ ...BESUCHT, isMobileViewport: mobil });
			assert.equal(countTestid(html, 'compare-step5-activation-banner'), 1, 'Banner nicht genau einmal');
			const reiter = innen(html, 'zustellung-tab');
			const banner = tagsMitTestid(reiter, 'compare-step5-activation-banner');
			assert.equal(banner.length, 1, 'Banner nicht im Reiter Zustellung (stammt aus dem Alt-Panel?)');
			assert.equal(attribut(banner[0], 'data-ready'), 'true', 'Name, zwei Orte, alle Schritte besucht: Banner meldet „bereit“');
		});

		test(`${ansicht}: Banner „nicht bereit“, solange der Schritt Zustellung nicht freigeschaltet ist (data-ready false)`, async () => {
			const html = await renderVergleichNeu({ ...BESUCHT, isMobileViewport: mobil, pickedIds: ['loc-a'] });
			const reiter = innen(html, 'zustellung-tab');
			const banner = tagsMitTestid(reiter, 'compare-step5-activation-banner');
			assert.equal(banner.length, 1, 'Banner nicht im Reiter Zustellung');
			assert.equal(attribut(banner[0], 'data-ready'), 'false');
		});
	}
});

describe('#3333 Test 8 (AC-12): keine Infobox des Alt-Panels im Reiter Zustellung', () => {
	for (const mobil of [false, true]) {
		test(`${mobil ? 'Mobil' : 'Desktop'}: Reiter Zustellung ohne Infobox; keine Versand-/Wetter-Metriken-Infobox im Schritt`, async () => {
			const html = await renderVergleichNeu({ ...BESUCHT, isMobileViewport: mobil });
			assert.deepEqual(testids(innen(html, 'zustellung-tab'), 'infobox-'), [], 'Reiter Zustellung trägt eine Infobox');
			for (const id of ['infobox-versand-vergleich', 'infobox-wetter-metriken-vergleich'])
				assert.equal(tagsMitTestid(html, id).length, 0, `Infobox "${id}" des Alt-Panels noch im Orte-Anlegen`);
		});
	}
});

// AC-7 am Wirkort Render: der Reiter zeigt den Startstand, den der Editor mitgibt (Neuaufbau), nicht die
// Abo-Sicht. Der Stub-Abo (id '') trägt Morgen 07:00 ohne Stille; der mitgegebene Stand 06:45 mit Stille.
describe('#3333 Test 7 (AC-7): Reiter context="vergleich" createMode zeigt zustellungStart, Stub-Abo wirft nicht', () => {
	const STUB = { id: '', name: 'SSR-3333', location_ids: ['loc-a', 'loc-b'], alert_channels: { email: true, telegram: true, sms: false, premium_sms: false } };
	const text = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
	async function zeige(zustellungStart?: Record<string, unknown>): Promise<string> {
		const { render } = await import('svelte/server');
		const { pathToFileURL, fileURLToPath } = await import('node:url');
		const path = await import('node:path');
		const pfad = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../shared/zustellung-tab/ZustellungTab.svelte');
		const ZustellungTab = (await import(pathToFileURL(pfad).href)).default;
		return render(ZustellungTab, { props: { context: 'vergleich', preset: STUB, createMode: true, zustellungStart, onAnlegeStand: () => {} } }).body;
	}
	const morgen = (h: string) => {
		const i = h.indexOf('data-testid="zustellung-morgen-karte"');
		assert.ok(i >= 0, 'Morgen-Karte fehlt');
		return text(h.slice(i, i + 4000).split('data-testid="zustellung-morgen-karte-schalter"')[0]).replace(/\s/g, '');
	};

	test('ohne zustellungStart: Startstand aus dem Stub-Abo (07:00), kein Wurf', async () => {
		assert.match(morgen(await zeige()), /07:?00/);
	});

	test('mit zustellungStart 06:45: genau dieser Stand ist sichtbar', async () => {
		const { standAusPreset } = await import('../../shared/zustellung-tab/zustellungModell.ts');
		const start = { ...standAusPreset(STUB as never), morgenZeit: '06:45', stilleAn: true, stilleVon: '22:30', stilleBis: '06:15' };
		const h = await zeige(start);
		assert.match(morgen(h), /06:?45/);
		assert.doesNotMatch(morgen(h), /07:?00/);
	});
});
