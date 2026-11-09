// TDD RED — Issue #2837 Scheibe S2b (Epic #2345, ADR-0110): beide Anlege-Editoren zeichnen den
// Fortschritt mit DEMSELBEN Baustein `AnlegeFortschritt` — Computer im Rahmen, Handy an der
// Handy-Stelle des Editors. Gerendert werden die echten Editoren (SSR, Startwerte über
// `stateOverride`), gelesen der Element-Baum des Outputs — kein Mock, kein Quelltext-Grep.
// Spec: docs/specs/modules/rework_2837_s2b_anlege_fortschritt.md — AC-2 (Testids), AC-3 (keine
//   Tönung im Handy-Balken des Vergleichs), AC-4 (Parität data-done/Farbe Trip = Vergleich),
//   AC-8 (compare-editor-progress-segment genau 5×, neue Testid tn-mobile-progress).
//   Mutationen: „Trip-Handy ohne tn-mobile-progress" ⇒ rot; „Handy-Segment heißt wieder
//   compare-editor-progress-segment" ⇒ rot (10 statt 5); „Tönung aktiv wieder eingebaut" ⇒ rot.
//
// Testid-Schema (Vertrag aus anlege_fortschritt.test.ts): Container = testidPrefix, Segmente
// `${testidPrefix}-segment` mit data-done; Desktop `trip-new-progress` / `compare-editor-progress`,
// Handy `tn-mobile-progress` / `cm-mobile-progress`.
//
// RED HEUTE: Trip-Handy-Balken hat keine Testid; Handy-Segmente beider Editoren ohne Testid und
// ohne data-done; Vergleich tönt das aktive Handy-Segment mit var(--g-accent-soft,#bcd).
//
// Pfadregel #1409: Prüflinge relativ zu src/lib/components/ über infoboxSsr.ts (relativ zu dessen Datei).
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/anlege-rahmen/__tests__/fortschritt_in_beiden_editoren_gleich.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { renderTrip, renderVergleichNeu, FRONTEND } from '../../__tests__/infoboxSsr.ts';
import { baum, alle, einzig, liegtIn, mitTestid, text, klassen, type Knoten } from '../../hub-kopf/__tests__/htmlBaum.ts';

const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
afterEach(() => locale.set('de'));

type Art = 'route' | 'vergleich';
type Geraet = 'desktop' | 'mobil';
const TESTID: Record<Art, Record<Geraet, string>> = {
	route: { desktop: 'trip-new-progress', mobil: 'tn-mobile-progress' },
	vergleich: { desktop: 'compare-editor-progress', mobil: 'cm-mobile-progress' }
};

function hintergrund(k: Knoten): string {
	const m = /(?:^|;)\s*background\s*:\s*([^;]+)/.exec(k.attrs.style ?? '');
	return m ? m[1].trim() : '';
}

/** Zustände, in denen Trip und Vergleich dieselbe Zahl erledigter Schritte und denselben aktiven Schritt (Segment 0) haben. */
const ZUSTAND: Record<'leer' | 'eins', Record<Art, () => Promise<string>>> = {
	leer: {
		route: () => renderTrip({ activeTab: 'route', isMobileViewport: false }),
		vergleich: () => renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false, name: '', pickedIds: [] })
	},
	eins: {
		route: () => renderTrip({ activeTab: 'route', isMobileViewport: false, name: 'Paritaet', startDate: '2026-12-01' }),
		vergleich: () => renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false, name: 'Paritaet', pickedIds: ['loc-a'] })
	}
};

function balken(html: string, art: Art, geraet: Geraet) {
	const w = baum(html);
	const id = TESTID[art][geraet];
	const container = einzig(w, id);
	const segmente = mitTestid(w, `${id}-segment`);
	return { w, container, segmente };
}

describe('#2837 S2b AC-2/AC-8 — Testids des Fortschritts in beiden Editoren', () => {
	for (const art of ['route', 'vergleich'] as const) {
		for (const geraet of ['desktop', 'mobil'] as const) {
			const id = TESTID[art][geraet];
			test(`${art}/${geraet}: ${id} genau einmal, darin 5× ${id}-segment mit data-done`, async () => {
				const { container, segmente } = balken(await ZUSTAND.leer[art](), art, geraet);
				assert.equal(segmente.length, 5, `${id}-segment steht ${segmente.length}× im Editor (erwartet 5)`);
				for (const s of segmente) {
					assert.ok(liegtIn(s, container), `${id}-segment liegt nicht in ${id}`);
					assert.ok(['true', 'false'].includes(s.attrs['data-done'] ?? ''), `${id}-segment ohne data-done`);
				}
			});
		}
	}

	test('AC-8: compare-editor-progress-segment genau 5× im Vergleich (Handy-Segmente heißen cm-mobile-progress-segment)', async () => {
		const html = await ZUSTAND.eins.vergleich();
		assert.equal(mitTestid(baum(html), 'compare-editor-progress-segment').length, 5);
		assert.equal(mitTestid(baum(html), 'cm-mobile-progress-segment').length, 5);
	});

	test('AC-8: trip-new-progress-segment genau 5× im Trip (Handy-Segmente heißen tn-mobile-progress-segment)', async () => {
		const html = await ZUSTAND.eins.route();
		assert.equal(mitTestid(baum(html), 'trip-new-progress-segment').length, 5);
		assert.equal(mitTestid(baum(html), 'tn-mobile-progress-segment').length, 5);
	});
});

describe('#2837 S2b AC-3 — Handy-Balken des Vergleichs tönt den aktiven Schritt nicht', () => {
	// Aktiver, noch nicht erledigter Schritt: „orte" mit nur einem Ort (vergleich erledigt, orte offen).
	test('Vergleich mobil, aktiv = orte (offen): kein --g-accent-soft, kein #bcd, aktives Segment = transparent (offen, #2881)', async () => {
		const html = await renderVergleichNeu({ activeTab: 'orte', isMobileViewport: true, pickedIds: ['loc-a'] });
		const { container, segmente } = balken(html, 'vergleich', 'mobil');
		const roh = alle(container, () => true).map((n) => n.attrs.style ?? '').join(' ');
		assert.ok(!roh.includes('--g-accent-soft'), `--g-accent-soft im Handy-Balken: ${roh}`);
		assert.ok(!/#bcd\b/i.test(roh), `Rückfallwert #bcd im Handy-Balken: ${roh}`);
		assert.equal(segmente.length, 5);
		assert.equal(segmente[1].attrs['data-done'], 'false', 'Vorbedingung: Schritt „orte" ist offen');
		assert.equal(hintergrund(segmente[1]), 'transparent', `aktives offenes Segment: „${hintergrund(segmente[1])}"`);
		assert.equal(hintergrund(segmente[0]), 'var(--g-accent)', 'erledigter Schritt „vergleich" nicht in Akzentfarbe');
	});
});

describe('#2837 S2b AC-4 — Parität: gleicher Zustand ⇒ gleiche data-done-Folge und Farben', () => {
	for (const zustand of ['leer', 'eins'] as const) {
		for (const geraet of ['desktop', 'mobil'] as const) {
			test(`${zustand}, ${geraet}: Trip und Vergleich zeigen dieselbe Folge (data-done, background)`, async () => {
				const folge = async (art: Art) =>
					balken(await ZUSTAND[zustand][art](), art, geraet).segmente.map((s) => `${s.attrs['data-done']}|${hintergrund(s)}`);
				const trip = await folge('route');
				const vergleich = await folge('vergleich');
				assert.equal(trip.length, 5, `Trip ${geraet}: ${trip.length} Segmente`);
				assert.deepEqual(vergleich, trip);
				const n = zustand === 'leer' ? 0 : 1;
				assert.deepEqual(
					trip.map((f) => f.split('|')[0]),
					[0, 1, 2, 3, 4].map((i) => String(i < n)),
					`Vorbedingung: ${n} erledigte Schritte`
				);
			});
		}
	}
});

// Fix-Loop 2 (Adversary F001/F004): die Variante und der aktive Schritt werden an der Wirkstelle
// geprüft — im gerenderten Editor, nicht nur am Baustein. Mutationen: „Trip-Handy variante=desktop"
// ⇒ Zählertext wird Katalog-Langtext statt „n/5" ⇒ rot; „aktiv am Trip-Handy weggelassen" ⇒ kein
// aria-current ⇒ rot.

/** Zähler = letztes Kind des Testid-Containers, ein <span class="mono">. */
function zaehlerText(container: Knoten): string {
	const letztes = container.kinder[container.kinder.length - 1];
	assert.ok(letztes, 'Container hat keine Kinder');
	assert.equal(letztes.tag, 'span', `letztes Kind ist <${letztes.tag}>, erwartet <span class="mono">`);
	assert.deepEqual(klassen(letztes), ['mono'], `Zähler hat class="${letztes.attrs.class}"`);
	return text(letztes);
}

describe('#2837 S2b AC-6/AC-7 — Zählertext je Gerät in beiden Editoren (de/en)', () => {
	for (const lang of ['de', 'en'] as const) {
		for (const zustand of ['leer', 'eins'] as const) {
			const n = zustand === 'leer' ? 0 : 1;
			for (const geraet of ['desktop', 'mobil'] as const) {
				const soll = () =>
					geraet === 'mobil'
						? `${n}/5`
						: n === 0
							? trFor(lang, 'trip.anlegen.nichts_eingerichtet')
							: trFor(lang, 'trip.anlegen.abschnitte', { n, gesamt: 5 });
				test(`${lang}, ${zustand}, ${geraet}: Trip und Vergleich zeigen denselben Zählertext`, async () => {
					locale.set(lang);
					const texte: Record<Art, string> = { route: '', vergleich: '' };
					for (const art of ['route', 'vergleich'] as const) {
						texte[art] = zaehlerText(balken(await ZUSTAND[zustand][art](), art, geraet).container);
					}
					if (geraet === 'mobil') assert.equal(texte.route, `${n}/5`, `Trip-Handy zeigt „${texte.route}" (erwartet exakt „${n}/5")`);
					assert.equal(texte.route, soll(), `Trip ${geraet}: „${texte.route}"`);
					assert.equal(texte.vergleich, soll(), `Vergleich ${geraet}: „${texte.vergleich}"`);
					assert.equal(texte.vergleich, texte.route, `${geraet}: Trip und Vergleich unterscheiden sich`);
				});
			}
		}
	}
});

describe('#2837 S2b AC-2/AC-4 — Handy: genau das Segment des aktiven Reiters trägt aria-current="step"', () => {
	for (const zustand of ['leer', 'eins'] as const) {
		test(`${zustand}: Trip-Handy und Vergleichs-Handy markieren gleich (aktiver Reiter = Segment 0)`, async () => {
			const markierung = async (art: Art) =>
				balken(await ZUSTAND[zustand][art](), art, 'mobil').segmente.map((s) => s.attrs['aria-current'] ?? '');
			const trip = await markierung('route');
			const vergleich = await markierung('vergleich');
			assert.deepEqual(trip, ['step', '', '', '', ''], `Trip-Handy aria-current: ${JSON.stringify(trip)}`);
			assert.deepEqual(vergleich, trip, `Vergleichs-Handy aria-current: ${JSON.stringify(vergleich)}`);
		});
	}
});

// Fix-Loop 1 (Adversary F003): der Balken färbt je Schritt (erledigt.has(step)), nicht nach
// Position — so zeichneten die Bestandsbalken (done.has(step)). Zustände, in denen ein späterer
// Schritt erledigt ist, ein früherer aber nicht. Mutationen: „Rahmen ohne erledigt-Prop" ⇒
// Desktop färbt Segment 0 ⇒ rot; „Handy ohne erledigt-Prop" ⇒ Handy färbt Segment 0 ⇒ rot.

const LUECKE: { name: string; art: Art; render: () => Promise<string>; soll: boolean[] }[] = [
	{
		name: 'Trip mit Startdatum ohne Namen, Metriken besucht (nur wetter-metriken erledigt)',
		art: 'route',
		render: () => renderTrip({ activeTab: 'route', isMobileViewport: false, name: '', startDate: '2026-12-01', wtVisited: true }),
		soll: [false, false, true, false, false]
	},
	{
		name: 'Vergleich ohne Namen, Metriken besucht (nur metriken erledigt)',
		art: 'vergleich',
		render: () => renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false, name: '', pickedIds: [], metrikenVisited: true }),
		soll: [false, false, true, false, false]
	},
	{
		name: 'Vergleich ohne Namen, zwei Orte (nur orte erledigt)',
		art: 'vergleich',
		render: () => renderVergleichNeu({ activeTab: 'vergleich', isMobileViewport: false, name: '', pickedIds: ['loc-a', 'loc-b'] }),
		soll: [false, true, false, false, false]
	}
];

describe('#2837 S2b F003 — Segment erledigt je Schritt, nicht nach Position (beide Geräte)', () => {
	for (const fall of LUECKE) {
		for (const geraet of ['desktop', 'mobil'] as const) {
			test(`${fall.name}, ${geraet}`, async () => {
				const { container, segmente } = balken(await fall.render(), fall.art, geraet);
				assert.equal(segmente.length, 5);
				const ist = segmente.map((s) => `${s.attrs['data-done']}|${hintergrund(s)}`);
				const soll = fall.soll.map((d) => `${d}|${d ? 'var(--g-accent)' : 'transparent'}`);
				assert.deepEqual(ist, soll, `${geraet}: Segmentfolge ${JSON.stringify(ist)}`);
				// Der Zähler bleibt die Anzahl erledigter Schritte.
				if (geraet === 'mobil') assert.equal(zaehlerText(container), '1/5');
			});
		}
	}
});
