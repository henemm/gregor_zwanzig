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
	renderKomponente,
	renderTrip,
	renderVergleichNeu,
	sichtbarerText,
	tagsMitTestid,
	testids
} from './infoboxSsr.ts';
import { findeKomponenten, type Knoten } from './svelteInstanzPruefstand.ts';
// Issue #2727 (AC-10/AC-22): Daten-Feldsatz statt Instanz der abgeloesten Zustandsklasse; die
// Corridor-Rezepte brauchen keinen Context mehr (der Reiter liest nur corridorPropsAus).
import { neuerFeldsatz } from './compareFeldsatzPruefstand.ts';
import { INFO_TEXTE, PFLICHTREITER, REITER_DES_ABSCHNITTS, REITER_MIT_INFOBOX, type Kontext } from './infoboxTexte.ts';

// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-6): Anlege-Schritte Wetter (Metriken,
// Wertebereiche) und Zustellung (Versand, Alarme); die Infobox-Schluessel selbst bleiben.
const ALLE_FLAGS = { wtVisited: true, zuVisited: true };
const TRIP_BASIS = { name: 'Infobox-Trip', startDate: '2026-07-01', stageNames: ['E1'], ...ALLE_FLAGS };
const VERGLEICH_FLAGS = { metrikenVisited: true, zustellungVisited: true };

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
// #2794 S3a Teil-PR 4a (AC-31): die Wertebereiche-Infobox stand nur im (seit Teil-PR 3 unsichtbar
// gemounteten) Korridor-Editor; mit ihm entfaellt sie in beiden Anlege-Editoren. Den Schluessel
// selbst (info.wertebereiche.*) raeumt Teil-PR 4b auf; der Baustein Infobox kennt ihn noch.
const OHNE_KORRIDOR_EDITOR = (r: string) => r !== 'wertebereiche';
// Issue #3332 (Spec feat_3332_zustellung_anlegen_trip.md, AC-11, Tech-Entscheidung Hub-Parität): im Schritt
// Zustellung des Trip-Anlegens steht der Reiter Zustellung statt des Alt-Panels. Er zeigt keine Infobox — weder
// die Versand-Infobox noch die Wetter-Metriken-Infobox, die bisher im (dort sichtbaren) Alt-Panel stand. Die
// Alarme-Infobox im Trip-Anlegen bleibt. #3333 (D2, AC-12): ebenso im Ortsvergleich-Anlegen — dort entfallen
// Versand- und Wetter-Metriken-Infobox mit dem Alt-Panel; die Alarme-Infobox bleibt (im SSR nicht gemountet,
// der Reiter Alarme wartet auf den Katalog-Abruf in onMount).
const TRIP_OHNE_INFOBOX_SEIT_3332 = ['versand', 'wetter-metriken'];
const MIT_INFOBOX_IM_TRIP_ANLEGEN = (r: string) => !TRIP_OHNE_INFOBOX_SEIT_3332.includes(r);

describe('AC-1/AC-3/AC-4: /trips/new zeigt die Infobox in jedem überspringbaren Reiter', () => {
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		for (const reiter of REITER_MIT_INFOBOX.route.filter(OHNE_KORRIDOR_EDITOR).filter(MIT_INFOBOX_IM_TRIP_ANLEGEN)) {
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
		// #3332 AC-11: ersetzt „Versand-Infobox des Trips nennt BEIDE Zeiten“ — der Reiter Zustellung hat keine Infobox.
		test(`${ansicht}: #3332 AC-11 — Schritt Zustellung des Trips: Reiter Zustellung ohne Infobox, Alarme-Infobox bleibt`, async () => {
			const html = await renderTrip({ ...TRIP_BASIS, activeTab: 'zustellung', isMobileViewport: mobil });
			assert.equal(tagsMitTestid(html, 'zustellung-tab').length, 1, 'Messaufbau: Reiter Zustellung nicht im Schritt Zustellung');
			assert.deepEqual(testids(innen(html, 'zustellung-tab'), 'infobox-'), [], 'Reiter Zustellung trägt eine Infobox');
			for (const reiter of TRIP_OHNE_INFOBOX_SEIT_3332)
				assert.equal(tagsMitTestid(html, `infobox-${reiter}-route`).length, 0, `Infobox "${reiter}" noch im Trip-Anlegen`);
			assert.equal(tagsMitTestid(html, 'infobox-alarme-route').length, 1, 'Alarme-Infobox im Trip-Anlegen verloren');
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
describe('AC-2/AC-3: /compare/new zeigt die Infobox (Versand), Desktop UND Mobil', () => {
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		// #2794 S3a Teil-PR 4a (AC-31): kein versteckter Korridor-Editor mehr — damit auch keine
		// (unsichtbare) Wertebereiche-Infobox im Schritt Wetter, in keinem der beiden Anlege-Editoren.
		test(`${ansicht}: Schritt Wetter — keine Wertebereiche-Infobox mehr (Korridor-Editor entfernt)`, async () => {
			const vergleich = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'wetter', isMobileViewport: mobil });
			const trip = await renderTrip({ ...TRIP_BASIS, activeTab: 'wetter', isMobileViewport: mobil });
			assert.ok(vergleich.includes('data-testid="wetter-tab'), 'Messaufbau: Schritt Wetter (Vergleich) nicht gerendert');
			assert.deepEqual(tagsMitTestid(vergleich, 'infobox-wertebereiche-vergleich'), [], `gefunden: ${JSON.stringify(infoboxIds(vergleich))}`);
			assert.deepEqual(tagsMitTestid(trip, 'infobox-wertebereiche-route'), [], `gefunden: ${JSON.stringify(infoboxIds(trip))}`);
			assert.ok(!/data-testid="corridor-editor/.test(vergleich + trip), 'Korridor-Editor noch im Anlege-Markup');
		});

		// #3333 AC-12: ersetzt „Versand-Abschnitt mit Vergleichs-Text“ — der Reiter Zustellung hat keine Infobox,
		// die Infoboxen des Alt-Panels (Versand, Wetter-Metriken) sind aus dem Orte-Anlegen verschwunden.
		test(`${ansicht}: #3333 AC-12 — Schritt Zustellung des Ortsvergleichs: Reiter Zustellung ohne Infobox, keine Alt-Panel-Infobox`, async () => {
			const html = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'zustellung', isMobileViewport: mobil });
			assert.equal(tagsMitTestid(html, 'zustellung-tab').length, 1, 'Messaufbau: Reiter Zustellung nicht im Schritt Zustellung');
			assert.deepEqual(testids(innen(html, 'zustellung-tab'), 'infobox-'), [], 'Reiter Zustellung trägt eine Infobox');
			for (const reiter of ['versand', 'wetter-metriken'])
				assert.equal(tagsMitTestid(html, `infobox-${reiter}-vergleich`).length, 0, `Infobox "${reiter}" noch im Ortsvergleich-Anlegen`);
		});
	}
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
				// Positivkontrolle (sonst waere „keine“ vakuum): seit #3333 (AC-12) zeigt das Orte-Anlegen im SSR gar
				// keine Infobox mehr (Alt-Panel weg, Alarme-Reiter erst nach onMount) — die Messung selbst wird deshalb
				// am Trip-Anlegen gegengeprueft, dessen Schritt Zustellung die Alarme-Infobox im SSR traegt.
				const trip = await renderTrip({ ...TRIP_BASIS, activeTab: 'zustellung', isMobileViewport: mobil });
				assert.ok(
					tagsMitTestid(trip, 'infobox-alarme-route').length >= 1,
					'Positivkontrolle: die Infobox-Messung findet die Alarme-Infobox des Trip-Anlegens nicht — Messaufbau kaputt'
				);
			});
		}
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// #1743 AC-22: Versand-Infobox beim Anlegen UEBER dem Versand-Inhalt, unter dem
// Wetter-Metriken-Inhalt — beide Anlege-Seiten, Desktop UND Mobil.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1743 AC-22 (abgelöst durch #3332/#3333): Anlegen — keine Versand-Infobox und kein Versand-Abschnitt mehr', () => {
	// #3332 AC-11 / #3333 AC-12: beide Anlegeseiten zeigen im Schritt Zustellung den Reiter Zustellung (ohne Infobox)
	// statt des Alt-Panels — die frühere Reihenfolge-Zusicherung (Versand-Infobox über dem Versand-Inhalt) hat
	// kein Objekt mehr. Geprüft wird, dass weder Abschnitt noch Infobox zurückkehren.
	for (const mobil of [false, true]) {
		const ansicht = mobil ? 'Mobil' : 'Desktop';
		test(`${ansicht}: /trips/new und /compare/new`, async () => {
			const trip = await renderTrip({ ...TRIP_BASIS, activeTab: 'zustellung', isMobileViewport: mobil });
			const vergleich = await renderVergleichNeu({ ...VERGLEICH_FLAGS, activeTab: 'zustellung', isMobileViewport: mobil });
			for (const [html, kontext] of [[trip, 'route'], [vergleich, 'vergleich']] as const) {
				assert.equal(tagsMitTestid(html, 'zustellung-tab').length, 1, `Messaufbau (${kontext}): Reiter Zustellung fehlt`);
				assert.equal(tagsMitTestid(html, 'versand-abschnitt').length, 0, `${kontext}: Versand-Abschnitt des Alt-Panels noch im Anlegen`);
				assert.equal(tagsMitTestid(html, `infobox-versand-${kontext}`).length, 0, `${kontext}: Versand-Infobox noch im Anlegen`);
			}
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
			...(await propsAus('compare/alarmePropsAus', 'alarmePropsAus', neuerFeldsatz())),
			catalog: [],
			profileOverride: PROFIL
		})
	},
	// #2794 S3a Teil-PR 4a: die drei CorridorEditor-Rezepte entfallen mit dem Korridor-Editor.
	// #3297/#3020: die Rezepte WeatherMetricsTab und VersandTab entfallen — beide Dateien geloescht.
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
// #2794 S3a Teil-PR 4a: CorridorEditor/CorridorEditorMobile entfernt — ein Wiederauftauchen
// faellt im Mount-Zaehler (Soll 0) auf, solange die Namen gezaehlt werden.
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
			// #2794 S3a Teil-PR 4a: die zwei versteckten CorridorEditor-Mounts sind entfernt (Soll 0).
			// #3332 (AC-1/AC-11): der Reiter Zustellung ersetzt das Panel (Soll 0); er trägt keine Infobox (Block unten).
			{ WeatherMetricsTab: 0, CorridorEditor: 0, CorridorEditorMobile: 0, AlarmeTab: 2, VersandTab: 0, WetterMetrikenVersandPanel: 0 }
		],
		[
			'CompareNewEditor',
			join(COMPONENTS, 'compare-new/CompareNewEditor.svelte'),
			// #2794 S3a Teil-PR 3 (AC-38): der Schritt Wetter ist der WetterTab; das Panel stand je Gerät
			// nur noch im Schritt Zustellung. Teil-PR 4a: die unsichtbaren Wertebereiche-Mounts sind entfernt
			// (Soll 0). #3333 (AC-1/AC-12): der Reiter Zustellung ersetzt das Panel (Soll 0); ohne Infobox (Block unten).
			{ WeatherMetricsTab: 0, CorridorEditor: 0, CorridorEditorMobile: 0, AlarmeTab: 2, VersandTab: 0, WetterMetrikenVersandPanel: 0 }
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

	for (const [name, datei] of [['#3332 AC-11: TripNewEditor', 'trip-new/TripNewEditor.svelte'], ['#3333 AC-12: CompareNewEditor', 'compare-new/CompareNewEditor.svelte']] as const) {
		test(`${name} mountet den Reiter Zustellung zweimal (Desktop + Mobil), nie mit showInfobox`, () => {
			const ast = parse(readFileSync(join(COMPONENTS, datei), 'utf-8'), { modern: true }) as Knoten;
			const zt = findeKomponenten(ast, 'ZustellungTab');
			assert.equal(zt.length, 2, `${name}: ZustellungTab hat ${zt.length} statt 2 Mounts`);
			for (const e of zt) assert.ok(!attributNamen(e).includes('showInfobox'), 'Reiter Zustellung im Anlegen mit showInfobox (Hub-Parität verletzt)');
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
	// #2794 S3a Teil-PR 3: die Metrik-Oberflaeche steht in beiden Hubs im Reiter Zustellung
	// (Huelle ZustellungTab), die Grenzen traegt der WetterTab — beide gehoeren zur Flaeche.
	// #2795 S3b Teilschritt 1b: der Reiter Zustellung ist neu gebaut — Alarm- und Versand-Bausteine
	// (AlarmeTab/VersandTab und ihre Trip-Huellen) sind aus den Hubs entfernt; das Panel steht im
	// Uebergangsblock. Gemessen wird die tatsaechlich gemountete Kette Hub -> ZustellungTab ->
	// UebergangBlock (die nicht mehr gemounteten Huellen AlarmeScheduleTab/BriefingScheduleTab
	// gehoeren nicht mehr zur Bearbeiten-Flaeche; Abbau in Teilschritt 1c).
	const ZUSTELLUNG_HUELLE = join(COMPONENTS, 'shared/zustellung-tab/ZustellungTab.svelte');
	// #3036: der Uebergangsblock ist aufgeloest. #3458: der Beispiel-Alarm (BeispielAlarm) ist entfernt —
	// die Kette endet an der Huelle ZustellungTab.
	const HUB_ORGANISMEN = [...ORGANISMEN, 'WetterTab'];
	for (const [name, dateien] of [
		['Trip-Hub (TripTabs + Reiter Zustellung)', [join(COMPONENTS, 'trip-detail/TripTabs.svelte'), ZUSTELLUNG_HUELLE]],
		['CompareTabs', [join(COMPONENTS, 'compare/CompareTabs.svelte'), ZUSTELLUNG_HUELLE]]
	] as const) {
		test(`${name}: mountet die Organismen (nicht vakuum) ohne showInfobox`, () => {
			const alle: Record<string, Knoten[]> = Object.fromEntries(HUB_ORGANISMEN.map((o) => [o, []]));
			for (const datei of dateien) {
				const quelle = readFileSync(datei, 'utf-8');
				const ast = parse(quelle, { modern: true }) as Knoten;
				for (const o of HUB_ORGANISMEN) alle[o].push(...findeKomponenten(ast, o));
			}
			const gesamt = HUB_ORGANISMEN.reduce((s, o) => s + alle[o].length, 0);
			// #2794 S3a Teil-PR 3: im Vergleichs-Hub ersetzt EIN WetterTab Desktop- und Mobil-Wertebereiche.
			// Fix-Loop 2 (F-A5): exakte Zahl statt Untergrenze (vorher `>= 4`) — je Hub gezaehlt,
			// jeder Traeger unten zusaetzlich einzeln zugesichert. Trip-Hub 4 (AlarmeTab, Panel in der
			// Zustellungs-Huelle, VersandTab in BriefingScheduleTab, WetterTab); CompareTabs 3 (AlarmeTab, Panel
			// in der Zustellungs-Huelle, WetterTab — EIN WetterTab ersetzt die zwei Wertebereiche-Mounts).
			// #2795 S3b 1b: je Hub 2 (Panel im Uebergangsblock, WetterTab); kein AlarmeTab/VersandTab mehr.
			// #3154 (#3122 B3b): je Hub 1 (WetterTab) — der Uebergangsblock traegt kein Panel mehr.
			const ERWARTET_GESAMT: Record<string, number> = {
				'Trip-Hub (TripTabs + Reiter Zustellung)': 1,
				CompareTabs: 1
			};
			const soll = ERWARTET_GESAMT[name] ?? -1;
			assert.equal(gesamt, soll, `${name}: ${gesamt} Organismus-Mounts gefunden (erwartet ${soll}) — Messaufbau kaputt`);
			assert.equal(alle.AlarmeTab.length + alle.VersandTab.length, 0, `${name}: alter AlarmeTab/VersandTab noch im Hub gemountet`);
			assert.equal(alle.WetterMetrikenVersandPanel.length, 0, `${name}: WetterMetrikenVersandPanel noch im Hub gemountet (#3154)`);
			// #2794 S3a Teil-PR 3: Traeger der Grenzen im Hub ist der WetterTab (statt CorridorEditor).
			assert.ok(alle.WetterTab.length >= 1, `${name}: kein WetterTab-Mount (Grenzen-Traeger)`);
			for (const org of HUB_ORGANISMEN) {
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

	// #2794 S3a Teil-PR 4a: corridorPropsAus ist mit seinem einzigen Verwender (Korridor-Editor) entfallen.
	// #3384 S4: wetterMetrikenPropsAus und versandPropsAus sind als Waisen gelöscht; es bleibt alarmePropsAus.
	test('alarmePropsAus liefert kein showInfobox-Feld', async () => {
		const wiz = neuerFeldsatz();
		for (const [modul, fn] of [['compare/alarmePropsAus', 'alarmePropsAus']] as const) {
			const props = await propsAus(modul, fn, wiz);
			assert.ok(Object.keys(props).length > 3, `${fn}: leeres Bündel — Messaufbau kaputt`);
			assert.ok(
				!('showInfobox' in props),
				`${fn} enthält showInfobox — das Bündel speist auch den Bearbeiten-Hub`
			);
		}
		// Gegenstueck (rot ohne Implementierung): der Anlege-Editor setzt das Prop AUSSERHALB der Bündel —
		// seit #3333 am Reiter Alarme (das Panel mit dem Versand-Bündel ist im Anlegen nicht mehr gemountet).
		const editor = join(COMPONENTS, 'compare-new/CompareNewEditor.svelte');
		const quelle = readFileSync(editor, 'utf-8');
		const alarme = mounts(editor).AlarmeTab[0];
		assert.ok(alarme, 'CompareNewEditor mountet den Reiter Alarme nicht');
		assert.equal(showInfoboxWert(alarme, quelle), 'true', 'Anlege-Editor setzt showInfobox nicht');
	});
});
