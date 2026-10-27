// TDD RED — Issue #2521 S1 (Spec begriff_erklaerung_infobox.md): die Infobox
// „Kannst du überspringen — Standard: …" steht NUR in den Anlege-Reitern
// (/trips/new, /compare/new), NIE in den Bearbeiten-Hubs; die ⓘ-Erklärungen
// stehen dagegen überall.
//
//   AC-1  Trip, Wetter-Metriken: Infobox mit dem freigegebenen Text
//   AC-2  Ortsvergleich, Wetter-Metriken: Infobox mit dem Vergleichs-Text
//   AC-3  Wertebereiche / Alarme / Versand je Kontext, Versand-Text je Kontext verschieden
//   AC-4  Trip-Wegpunkte
//   AC-5  Pflichtreiter (Trip: Route/Etappen, Vergleich: Vergleich/Orte) OHNE Infobox
//   AC-6  Bearbeiten-Hub: keine Infobox, aber ⓘ
//
// WIE GEMESSEN (Wirkort statt Baustein):
//   * Die Anlege-Editoren werden komplett serverseitig gerendert (Test-Seam
//     `stateOverride`), Desktop UND Mobile. TripNewEditor haelt Desktop- und
//     Mobil-Mount je XOR hinter `isMobileViewport`; fehlt `showInfobox` an EINEM
//     der beiden Mounts, wird der jeweilige Viewport-Fall rot.
//   * 🔴 Im SSR laufen `onMount`/`$effect` nie. Folge fuer den Ortsvergleich:
//     der Alarme-Reiter haengt hinter `alarmeHydrated` und ist im SSR NICHT
//     gemountet. Dort messen: direkter Organismus-Render (mit/ohne Prop) PLUS
//     der strukturelle Waechter am Editor (AST, `// doc-compliance-test`).
//   * Die Organismen rendern im SSR ihren LADEZUSTAND (Katalog nicht geladen).
//     Die Infobox muss deshalb AUSSERHALB der Lade-/Fehler-Verzweigung stehen —
//     sonst ist sie im Browser erst nach dem Laden da und im SSR unsichtbar.
//
// Soll-Texte sind LITERALE (infoboxTexte.ts), nicht aus dem Katalog gelesen.
//
// Erwartete Selektoren (der Implementierer baut genau danach):
//   Infobox:  <aside data-testid="infobox-<reiter>-<route|vergleich>">  (kein <button> darin)
//   Prop an den fuenf Organismen: `showInfobox` (boolean, Default false)
//
// Issue #1743 (feat_1743_reiter_aufraeumen, AC-19/AC-22): „Versand" ist kein Reiter mehr, sondern
// der Abschnitt unten im Reiter Wetter-Metriken (geteilter Baustein WetterMetrikenVersandPanel).
// Die Versand-Infobox steht beim Anlegen im Schritt Wetter-Metriken UEBER dem Versand-Inhalt
// (nach dem Wetter-Metriken-Inhalt), im Bearbeiten-Hub nicht. Kein Versand-Besuchs-Flag mehr.
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/infobox_nur_beim_anlegen.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { parse } from 'svelte/compiler';
import {
	COMPONENTS,
	innen,
	lade,
	neuerWiz,
	renderKomponente,
	renderTrip,
	renderVergleichNeu,
	sichtbarerText,
	tagsMitTestid,
	testids
} from './infoboxSsr.ts';
import { findeKomponenten, type Knoten } from './svelteInstanzPruefstand.ts';
import { INFO_TEXTE, PFLICHTREITER, REITER_DES_ABSCHNITTS, REITER_MIT_INFOBOX, type Kontext } from './infoboxTexte.ts';

const ALLE_FLAGS = { wtVisited: true, wbVisited: true, alVisited: true };
const TRIP_BASIS = { name: 'Infobox-Trip', startDate: '2026-07-01', stageNames: ['E1'], ...ALLE_FLAGS };
const VERGLEICH_FLAGS = { metrikenVisited: true, idealsVisited: true, alarmeVisited: true };

function infoboxIds(html: string): string[] {
	return testids(html, 'infobox-');
}

/** Text der Infobox + Pruefung, dass sie ein <aside> ohne Bedienelement ist. */
function infoboxText(html: string, reiter: string, kontext: Kontext, nr = 0): string {
	const id = `infobox-${reiter}-${kontext}`;
	const tags = tagsMitTestid(html, id);
	assert.ok(tags.length > nr, `Infobox "${id}" (Nr. ${nr}) fehlt — gefunden: ${JSON.stringify(infoboxIds(html))}`);
	assert.ok(tags[nr].startsWith('<aside'), `Infobox "${id}" ist kein <aside>: ${tags[nr]}`);
	const roh = innen(html, id, nr);
	assert.ok(!/<(button|input|a)\b/.test(roh), `Infobox "${id}" enthält ein Bedienelement (kein Schließen-Knopf erlaubt)`);
	return sichtbarerText(roh);
}

function erwartet(reiter: string, kontext: Kontext): string {
	const text = INFO_TEXTE[`info.${reiter}.${kontext}`];
	assert.ok(text, `Messaufbau: kein freigegebener Text für info.${reiter}.${kontext}`);
	return text;
}

// ─────────────────────────────────────────────────────────────────────────────
// AC-1, AC-3, AC-4: /trips/new — Desktop UND Mobile
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-1/AC-3/AC-4: /trips/new zeigt die Infobox in jedem überspringbaren Reiter', () => {
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		for (const reiter of REITER_MIT_INFOBOX.route) {
			test(`${ansicht}: Reiter ${reiter} trägt genau eine Infobox mit dem freigegebenen Text`, async () => {
				const html = await renderTrip({ ...TRIP_BASIS, activeTab: (REITER_DES_ABSCHNITTS as Record<string, string>)[reiter], isMobileViewport: mobil });
				const id = `infobox-${reiter}-route`;
				if (reiter === 'wegpunkte') {
					// Messaufbau-Beleg: das Wegpunkte-Panel ist in dieser Ansicht wirklich gerendert
					// (Banner-Text je Baum), der Fehlschlag kommt also von der fehlenden Infobox.
					assert.ok(
						html.includes(mobil ? 'Wegpunkte automatisch berechnet' : 'Wegpunkte aus GPX berechnet'),
						'Messaufbau: Wegpunkte-Panel nicht gerendert'
					);
				}
				assert.equal(
					tagsMitTestid(html, id).length,
					1,
					`Erwartet genau eine Infobox "${id}" (${ansicht}) — gefunden: ${JSON.stringify(infoboxIds(html))}. ` +
						'Fehlt sie nur in einer Ansicht, fehlt `showInfobox` am Desktop- bzw. Mobil-Mount.'
				);
				assert.equal(infoboxText(html, reiter, 'route'), erwartet(reiter, 'route'));
			});
		}
		test(`${ansicht}: Versand-Infobox des Trips nennt BEIDE Zeiten (07:00 und 18:00)`, async () => {
			const html = await renderTrip({ ...TRIP_BASIS, activeTab: 'wetter-metriken', isMobileViewport: mobil });
			const text = infoboxText(html, 'versand', 'route');
			assert.match(text, /07:00/);
			assert.match(text, /18:00/);
		});
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-5 (Trip): Pflichtreiter ohne Infobox
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-5: Trip-Pflichtreiter Route und Etappen tragen keine Infobox', () => {
	for (const mobil of [false, true]) {
		for (const reiter of PFLICHTREITER.route) {
			test(`${mobil ? 'Mobil' : 'Desktop'}: Reiter ${reiter} — keine Infobox für diesen Reiter, keine fremde`, async () => {
				const html = await renderTrip({ ...TRIP_BASIS, activeTab: reiter, isMobileViewport: mobil });
				// Messaufbau-Beleg: der Pflichtreiter ist wirklich offen.
				if (reiter === 'route') {
					assert.ok(html.includes('trip-new-name-input-'), 'Route-Reiter ist nicht offen');
				}
				// Positivkontrolle (macht den Fall ohne Implementierung rot): die Infobox-Bausteine
				// sind verdrahtet — der (per display:none gehaltene) Alarme-Reiter traegt seine Infobox.
				assert.equal(
					tagsMitTestid(html, 'infobox-alarme-route').length,
					1,
					'Positivkontrolle: Alarme-Infobox fehlt — ohne Infobox-Verdrahtung beweist „Pflichtreiter ohne“ nichts'
				);
				for (const id of infoboxIds(html)) {
					assert.ok(
						!/^infobox-(route|etappen)-/.test(id),
						`Pflichtreiter trägt eine Infobox: ${id}`
					);
					const reiterId = id.replace(/^infobox-/, '').replace(/-(route|vergleich)$/, '');
					assert.ok(
						REITER_MIT_INFOBOX.route.includes(reiterId),
						`Infobox "${id}" gehört zu keinem überspringbaren Reiter`
					);
				}
				// Jede Infobox im Dokument ist ein <aside> mit erkanntem Testid (kein Stray-Element).
				assert.equal((html.match(/<aside\b/g) ?? []).length, infoboxIds(html).length);
			});
		}
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-2, AC-3 (Ortsvergleich, Anlegen) — Reiter, die im SSR gemountet sind
// ─────────────────────────────────────────────────────────────────────────────
describe('AC-2/AC-3: /compare/new zeigt die Infobox (Wertebereiche, Versand), Desktop UND Mobil', () => {
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		test(`${ansicht}: Wertebereiche — genau eine Infobox mit dem freigegebenen Text`, async () => {
			const html = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'wertebereiche', isMobileViewport: mobil });
			assert.equal(
				tagsMitTestid(html, 'infobox-wertebereiche-vergleich').length,
				1,
				`${ansicht}: fehlt \`showInfobox\` am ${mobil ? 'CorridorEditorMobile' : 'CorridorEditor'}-Mount? ` +
					`gefunden: ${JSON.stringify(infoboxIds(html))}`
			);
			assert.equal(infoboxText(html, 'wertebereiche', 'vergleich'), erwartet('wertebereiche', 'vergleich'));
		});

		test(`${ansicht}: Versand-Abschnitt im Schritt Wetter-Metriken — Infobox je Abschnitt mit Vergleichs-Text (nur 07:00, kein 18:00)`, async () => {
			const html = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'wetter-metriken', isMobileViewport: mobil });
			const anzahl = tagsMitTestid(html, 'infobox-versand-vergleich').length;
			// Je gerendertem Versand-Abschnitt genau eine Infobox.
			assert.equal(anzahl, tagsMitTestid(html, 'versand-abschnitt').length, 'nicht jeder Versand-Abschnitt trägt eine Infobox');
			assert.ok(anzahl >= 1, 'Versand-Abschnitt im Schritt Wetter-Metriken ohne Infobox');
			for (let nr = 0; nr < anzahl; nr++) {
				const text = infoboxText(html, 'versand', 'vergleich', nr);
				assert.equal(text, erwartet('versand', 'vergleich'));
				assert.match(text, /07:00/);
				assert.doesNotMatch(text, /18:00/, 'Vergleichs-Text darf den Abend-Slot nicht nennen (Abend ist aus)');
			}
		});
	}

	test('Wetter-Metriken (Desktop): Infobox mit Vergleichs-Text, nicht dem Trip-Text', async () => {
		const html = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'wetter-metriken', isMobileViewport: false });
		assert.ok(tagsMitTestid(html, 'infobox-wetter-metriken-vergleich').length >= 1, `gefunden: ${JSON.stringify(infoboxIds(html))}`);
		const text = infoboxText(html, 'wetter-metriken', 'vergleich');
		assert.equal(text, erwartet('wetter-metriken', 'vergleich'));
		assert.match(text, /Stundenverlauf/);
		assert.match(text, /3-Tages-Ausblick/);
	});
});

describe('AC-5: Ortsvergleich-Pflichtreiter Vergleich und Orte tragen keine Infobox', () => {
	for (const mobil of [false, true]) {
		for (const reiter of PFLICHTREITER.vergleich) {
			test(`${mobil ? 'Mobil' : 'Desktop'}: Reiter ${reiter} — gar keine Infobox im Dokument`, async () => {
				const html = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: reiter, isMobileViewport: mobil });
				if (reiter === 'vergleich') {
					assert.ok(html.includes('compare-editor-name'), 'Messaufbau: Vergleich-Reiter ist nicht offen');
				}
				assert.deepEqual(infoboxIds(html), [], 'Pflichtreiter trägt eine Infobox');
				assert.equal((html.match(/<aside\b/g) ?? []).length, 0, 'Pflichtreiter enthält ein <aside>');
				// Positivkontrolle (macht den Fall ohne Implementierung rot): derselbe Editor MIT
				// geoeffnetem Wetter-Metriken-Schritt zeigt die Versand-Infobox — sonst waere „keine“ vakuum.
				const versand = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'wetter-metriken', isMobileViewport: mobil });
				assert.ok(
					tagsMitTestid(versand, 'infobox-versand-vergleich').length >= 1,
					'Positivkontrolle: Wetter-Metriken-Schritt zeigt keine Versand-Infobox — Verdrahtung fehlt'
				);
			});
		}
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// #1743 AC-22: Versand-Infobox beim Anlegen UEBER dem Versand-Inhalt, unter dem
// Wetter-Metriken-Inhalt — beide Anlege-Seiten, Desktop UND Mobil.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1743 AC-22: Anlegen — Versand-Infobox steht im Schritt Wetter-Metriken über dem Versand-Inhalt', () => {
	function reihenfolge(html: string, kontext: Kontext): void {
		const iWm = html.indexOf(`data-testid="infobox-wetter-metriken-${kontext}"`);
		const iVi = html.indexOf(`data-testid="infobox-versand-${kontext}"`);
		const iAb = html.indexOf('data-testid="versand-abschnitt"');
		// Vergleichs-Zweig des VersandTab traegt die Kennung `compare-step5-channel-email`.
		const iKanal = html.search(kontext === 'vergleich' ? /data-testid="compare-step5-channel-email"/ : /data-testid="channel-email"/);
		assert.notEqual(iWm, -1, `Messaufbau: Wetter-Metriken-Infobox fehlt — gefunden: ${JSON.stringify(infoboxIds(html))}`);
		assert.notEqual(iAb, -1, 'Versand-Abschnitt (data-testid="versand-abschnitt") fehlt im Schritt Wetter-Metriken');
		assert.notEqual(iVi, -1, `Versand-Infobox fehlt im Schritt Wetter-Metriken — gefunden: ${JSON.stringify(infoboxIds(html))}`);
		assert.notEqual(iKanal, -1, 'Versand-Kanalschalter (channel-email) fehlen im Schritt Wetter-Metriken');
		assert.ok(iWm < iVi, 'Versand-Infobox steht vor dem Wetter-Metriken-Inhalt');
		assert.ok(iVi < iKanal, 'Versand-Infobox steht nicht über dem Versand-Inhalt');
	}
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		test(`${ansicht}: /trips/new`, async () => {
			reihenfolge(await renderTrip({ ...TRIP_BASIS, activeTab: 'wetter-metriken', isMobileViewport: mobil }), 'route');
		});
		test(`${ansicht}: /compare/new`, async () => {
			reihenfolge(await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'wetter-metriken', isMobileViewport: mobil }), 'vergleich');
		});
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// AC-1/AC-2/AC-3/AC-6 am Organismus: MIT `showInfobox` Infobox, OHNE nicht — ⓘ immer
// ─────────────────────────────────────────────────────────────────────────────
const TRIP = {
	id: 'trip-infobox',
	name: 'Infobox-Trip',
	stages: [],
	alert_rules: [],
	display_config: {},
	report_config: { send_email: true }
};

type Rezept = {
	name: string;
	datei: string;
	kontext: Kontext;
	reiter: string;
	/** erwartete ⓘ-Begriffe im Organismus (leer = der Reiter hat laut Spec kein ⓘ) */
	begriffe: string[];
	props: () => Promise<Record<string, unknown>>;
	context?: () => Map<string, unknown>;
};

const PROFIL = { premium_sms_allowed: false };

async function propsAus(modul: string, fn: string, wiz: unknown): Promise<Record<string, unknown>> {
	const m = await import(new URL(`${modul}.ts`, `file://${COMPONENTS}/`).href);
	return m[fn](wiz);
}

const REZEPTE: Rezept[] = [
	{
		name: 'AlarmeTab (route)',
		datei: 'shared/AlarmeTab.svelte',
		kontext: 'route',
		reiter: 'alarme',
		begriffe: ['kanal_schwelle', 'cooldown'],
		props: async () => ({
			context: 'route',
			trip: TRIP,
			activeMetrics: [],
			metricLevels: {},
			existingChannels: { email: true, telegram: true, sms: false, premium_sms: false },
			profileOverride: PROFIL
		})
	},
	{
		name: 'AlarmeTab (vergleich)',
		datei: 'shared/AlarmeTab.svelte',
		kontext: 'vergleich',
		reiter: 'alarme',
		begriffe: ['kanal_schwelle', 'cooldown'],
		props: async () => ({
			context: 'vergleich',
			...(await propsAus('compare/alarmePropsAus', 'alarmePropsAus', neuerWiz())),
			catalog: [],
			profileOverride: PROFIL
		})
	},
	{
		name: 'CorridorEditor (vergleich)',
		datei: 'shared/corridor-editor/CorridorEditor.svelte',
		kontext: 'vergleich',
		reiter: 'wertebereiche',
		begriffe: ['wertebereiche'],
		props: async () => ({ context: 'vergleich', ...(await propsAus('compare/corridorPropsAus', 'corridorPropsAus', neuerWiz())) }),
		context: () => new Map([['compare-wizard-state', neuerWiz()]])
	},
	{
		name: 'CorridorEditorMobile (vergleich)',
		datei: 'shared/corridor-editor/CorridorEditorMobile.svelte',
		kontext: 'vergleich',
		reiter: 'wertebereiche',
		begriffe: ['wertebereiche'],
		props: async () => ({ context: 'vergleich', ...(await propsAus('compare/corridorPropsAus', 'corridorPropsAus', neuerWiz())) }),
		context: () => new Map([['compare-wizard-state', neuerWiz()]])
	},
	{
		name: 'CorridorEditor (route, Anlegen)',
		datei: 'shared/corridor-editor/CorridorEditor.svelte',
		kontext: 'route',
		reiter: 'wertebereiche',
		begriffe: ['wertebereiche'],
		props: async () => ({ context: 'route', trip: TRIP, createMode: true })
	},
	{
		name: 'WeatherMetricsTab (vergleich)',
		datei: 'shared/WeatherMetricsTab.svelte',
		kontext: 'vergleich',
		reiter: 'wetter-metriken',
		begriffe: [],
		props: async () => ({
			context: 'vergleich',
			...(await propsAus('compare/wetterMetrikenPropsAus', 'wetterMetrikenPropsAus', neuerWiz()))
		})
	},
	{
		name: 'VersandTab (vergleich)',
		datei: 'shared/VersandTab.svelte',
		kontext: 'vergleich',
		reiter: 'versand',
		begriffe: [],
		props: async () => ({
			context: 'vergleich',
			...(await propsAus('compare/versandPropsAus', 'versandPropsAus', neuerWiz()))
		})
	}
];

describe('AC-1/AC-2/AC-3: Organismus MIT showInfobox rendert die Infobox (auch im Lade-Zustand)', () => {
	for (const r of REZEPTE) {
		test(`${r.name}: genau eine Infobox "${r.reiter}" mit dem freigegebenen Text`, async () => {
			const Komp = await lade(r.datei);
			const html = renderKomponente(Komp, { ...(await r.props()), showInfobox: true }, r.context?.());
			assert.equal(
				tagsMitTestid(html, `infobox-${r.reiter}-${r.kontext}`).length,
				1,
				`gefunden: ${JSON.stringify(infoboxIds(html))}`
			);
			assert.equal(infoboxText(html, r.reiter, r.kontext), erwartet(r.reiter, r.kontext));
		});
	}
});

describe('AC-6: Organismus OHNE showInfobox (Bearbeiten-Hub): keine Infobox, aber die ⓘ-Erklärungen', () => {
	for (const r of REZEPTE) {
		test(`${r.name}: kein Infobox-Element${r.begriffe.length ? ', ⓘ ' + r.begriffe.join(' + ') + ' vorhanden' : ''}`, async () => {
			const Komp = await lade(r.datei);
			const html = renderKomponente(Komp, await r.props(), r.context?.());
			assert.deepEqual(infoboxIds(html), [], 'Infobox ohne `showInfobox` gerendert (Default muss false sein)');
			assert.equal((html.match(/<aside\b/g) ?? []).length, 0);
			for (const b of r.begriffe) {
				assert.ok(
					tagsMitTestid(html, `begriff-erklaerung-${b}`).length >= 1,
					`ⓘ "${b}" fehlt im Organismus ${r.name} (Bearbeiten-Hub zeigt die Erklärung überall)`
				);
			}
			if (r.begriffe.length === 0) {
				// Organismus ohne ⓘ: Positivkontrolle statt Leerlauf — mit Prop MUSS die Infobox kommen.
				const mit = renderKomponente(Komp, { ...(await r.props()), showInfobox: true }, r.context?.());
				assert.equal(
					tagsMitTestid(mit, `infobox-${r.reiter}-${r.kontext}`).length,
					1,
					'Positivkontrolle: mit showInfobox fehlt die Infobox'
				);
			}
		});
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Verdrahtung — Anlege-Editoren setzen `showInfobox` an JEDEM Organismus-Mount,
// die Hubs und die Wertprop-Bündel setzen es NIE.
// ─────────────────────────────────────────────────────────────────────────────
// #1743: der geteilte Panel-Baustein (Wetter-Metriken + Versand) zaehlt als Organismus-Mount.
const ORGANISMEN = ['WeatherMetricsTab', 'CorridorEditor', 'CorridorEditorMobile', 'AlarmeTab', 'VersandTab', 'WetterMetrikenVersandPanel'];

function mounts(datei: string): Record<string, Knoten[]> {
	const quelle = readFileSync(datei, 'utf-8');
	const ast = parse(quelle, { modern: true }) as Knoten;
	const aus: Record<string, Knoten[]> = {};
	for (const n of ORGANISMEN) aus[n] = findeKomponenten(ast, n);
	return aus;
}

function attributNamen(einbettung: Knoten): string[] {
	return ((einbettung.attributes ?? []) as Knoten[]).filter((a) => a.type === 'Attribute').map((a) => String(a.name));
}

/** Wert des Attributs im Quelltext: `true` fuer Kurzform `showInfobox`, sonst der Ausdruck. */
function showInfoboxWert(einbettung: Knoten, quelle: string): string | null {
	for (const a of (einbettung.attributes ?? []) as Knoten[]) {
		if (a.type !== 'Attribute' || a.name !== 'showInfobox') continue;
		if (a.value === true) return 'true';
		const v = a.value?.type === 'ExpressionTag' ? a.value : null;
		return v ? quelle.slice(v.expression.start, v.expression.end) : '?';
	}
	return null;
}

// doc-compliance-test
describe('Verdrahtung: jeder Anlege-Mount setzt showInfobox explizit auf true', () => {
	const EDITOREN: [string, string, Record<string, number>][] = [
		[
			'TripNewEditor',
			join(COMPONENTS, 'trip-new/TripNewEditor.svelte'),
			// #1743: Wetter-Metriken und Versand nur noch ueber den geteilten Panel-Baustein (Desktop + Mobil).
			{ WeatherMetricsTab: 0, CorridorEditor: 2, CorridorEditorMobile: 0, AlarmeTab: 2, VersandTab: 0, WetterMetrikenVersandPanel: 2 }
		],
		[
			'CompareNewEditor',
			join(COMPONENTS, 'compare-new/CompareNewEditor.svelte'),
			{ WeatherMetricsTab: 0, CorridorEditor: 1, CorridorEditorMobile: 1, AlarmeTab: 2, VersandTab: 0, WetterMetrikenVersandPanel: 2 }
		]
	];
	for (const [name, datei, erwartetAnzahl] of EDITOREN) {
		test(`${name}: Mount-Anzahl stimmt (sonst beweist „alle" nichts) und jeder trägt showInfobox`, () => {
			const quelle = readFileSync(datei, 'utf-8');
			const m = mounts(datei);
			for (const org of ORGANISMEN) {
				assert.equal(m[org].length, erwartetAnzahl[org], `${name}: ${org} hat ${m[org].length} statt ${erwartetAnzahl[org]} Mounts`);
				for (const [i, einbettung] of m[org].entries()) {
					const wert = showInfoboxWert(einbettung, quelle);
					assert.ok(
						wert === 'true',
						`${name}: ${org}-Mount Nr. ${i + 1} setzt \`showInfobox\` nicht (explizit true). Wert: ${wert}`
					);
				}
			}
		});
	}

	test('TripNewEditor: das Wegpunkte-Panel trägt eine Infobox (Desktop- und Mobil-Baum)', () => {
		const quelle = readFileSync(join(COMPONENTS, 'trip-new/TripNewEditor.svelte'), 'utf-8');
		const ast = parse(quelle, { modern: true }) as Knoten;
		const infoboxen = findeKomponenten(ast, 'Infobox');
		assert.equal(infoboxen.length, 2, 'Erwartet je eine <Infobox> im Wegpunkte-Panel (Desktop + Mobil)');
	});
});

// doc-compliance-test
describe('AC-6 Verdrahtung: die Bearbeiten-Hubs und die Wertprop-Bündel setzen showInfobox NIE', () => {
	// Der Trip-Hub mountet Alarme und Versand nicht in TripTabs selbst, sondern in
	// zwei Reiter-Huellen — alle drei Dateien gehoeren zur Bearbeiten-Flaeche.
	for (const [name, dateien] of [
		[
			'Trip-Hub (TripTabs + AlarmeScheduleTab + BriefingScheduleTab)',
			[
				join(COMPONENTS, 'trip-detail/TripTabs.svelte'),
				join(COMPONENTS, 'trip-detail/AlarmeScheduleTab.svelte'),
				join(COMPONENTS, 'trip-detail/BriefingScheduleTab.svelte')
			]
		],
		['CompareTabs', [join(COMPONENTS, 'compare/CompareTabs.svelte')]]
	] as const) {
		test(`${name}: mountet die Organismen (nicht vakuum) ohne showInfobox`, () => {
			const alle: Record<string, Knoten[]> = Object.fromEntries(ORGANISMEN.map((o) => [o, []]));
			for (const datei of dateien) {
				const m = mounts(datei);
				for (const o of ORGANISMEN) alle[o].push(...m[o]);
			}
			const gesamt = ORGANISMEN.reduce((s, o) => s + alle[o].length, 0);
			assert.ok(gesamt >= 4, `${name}: nur ${gesamt} Organismus-Mounts gefunden — Messaufbau kaputt`);
			assert.ok(alle.AlarmeTab.length >= 1, `${name}: kein AlarmeTab-Mount gefunden`);
			// #1743: Wetter-Metriken/Versand duerfen auch ueber den geteilten Panel-Baustein kommen.
			for (const org of ['WeatherMetricsTab', 'VersandTab']) {
				assert.ok(
					alle[org].length + alle.WetterMetrikenVersandPanel.length >= 1,
					`${name}: kein ${org}- bzw. WetterMetrikenVersandPanel-Mount gefunden`
				);
			}
			assert.ok(
				alle.CorridorEditor.length + alle.CorridorEditorMobile.length >= 1,
				`${name}: kein Corridor-Mount`
			);
			for (const org of ORGANISMEN) {
				for (const einbettung of alle[org]) {
					assert.ok(
						!attributNamen(einbettung).includes('showInfobox'),
						`${name}: ${org} setzt showInfobox — im Bearbeiten-Hub darf die Infobox nicht stehen`
					);
				}
			}
			// Gegenstueck (macht den Fall ohne Implementierung rot): der zugehoerige ANLEGE-Editor
			// setzt das Prop — „Hub ohne“ ist nur dann eine Aussage, wenn das Prop existiert.
			const editor = name.startsWith('Trip')
				? join(COMPONENTS, 'trip-new/TripNewEditor.svelte')
				: join(COMPONENTS, 'compare-new/CompareNewEditor.svelte');
			const quelleEditor = readFileSync(editor, 'utf-8');
			const ersterMount = mounts(editor).AlarmeTab[0];
			assert.equal(showInfoboxWert(ersterMount, quelleEditor), 'true', 'Anlege-Editor setzt showInfobox nicht');
		});
	}

	test('wetterMetriken-/corridor-/alarme-/versandPropsAus liefern kein showInfobox-Feld', async () => {
		const wiz = neuerWiz();
		for (const [modul, fn] of [
			['compare/wetterMetrikenPropsAus', 'wetterMetrikenPropsAus'],
			['compare/corridorPropsAus', 'corridorPropsAus'],
			['compare/alarmePropsAus', 'alarmePropsAus'],
			['compare/versandPropsAus', 'versandPropsAus']
		] as const) {
			const props = await propsAus(modul, fn, wiz);
			assert.ok(Object.keys(props).length > 3, `${fn}: leeres Bündel — Messaufbau kaputt`);
			assert.ok(
				!('showInfobox' in props),
				`${fn} enthält showInfobox — das Bündel speist auch den Bearbeiten-Hub`
			);
		}
		// Gegenstueck (rot ohne Implementierung): der Anlege-Editor setzt das Prop AUSSERHALB der Bündel.
		const editor = join(COMPONENTS, 'compare-new/CompareNewEditor.svelte');
		const quelle = readFileSync(editor, 'utf-8');
		const panel = mounts(editor).WetterMetrikenVersandPanel[0];
		assert.ok(panel, '#1743: CompareNewEditor mountet den geteilten WetterMetrikenVersandPanel nicht');
		assert.equal(showInfoboxWert(panel, quelle), 'true', 'Anlege-Editor setzt showInfobox nicht');
	});
});
