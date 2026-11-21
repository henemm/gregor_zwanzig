// Issue #3203 (Epic #2913): Sichtbarkeitsregel des Elementlisten-Abgleichs. Spec:
// docs/specs/modules/feat_3203_metrikzeilen_mockup.md (AC-1, AC-2, AC-3; Test Plan Punkte 1-4).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/elementliste_abgleich_logik.test.ts
//
// RED: `sichtbareTextBloecke` ist in frontend/e2e/elementliste_abgleich_logik.ts NEU zu exportieren.
// Festgelegter Vertrag (Developer baut ihn exakt so):
//
//   export type AbgleichKnoten = {
//       nodeType: number;                // 1 = Element, 3 = Text (wie im DOM)
//       nodeValue: string | null;        // Text bei nodeType 3
//       tagName?: string;                // Elemente; HTML in Großbuchstaben, svg-Elemente klein ('svg')
//       childNodes: ArrayLike<AbgleichKnoten>;
//       hasAttribute?(name: string): boolean;
//   };
//   export function sichtbareTextBloecke(
//       wurzel: AbgleichKnoten,
//       stil: (el: AbgleichKnoten) => { display: string; visibility: string }
//   ): string[]
//
//   Regeln:
//   - Ein Element samt Teilbaum zählt NICHT, wenn es `display: none`, `visibility: hidden` oder das
//     Attribut `hidden` trägt oder SCRIPT/STYLE/svg ist (tagName ohne Rücksicht auf Groß-/Kleinschreibung).
//     Damit gilt: kein Vorfahr versteckt -> zählt.
//   - `aria-hidden` wird NICHT ausgewertet (Sichtbarkeit statt Barrierefreiheits-Attribut).
//   - Element mit eigenem (nicht leeren) Textknoten: EIN Block aus seinem gesamten sichtbaren Text in
//     Dokumentreihenfolge (Kind-Elemente wie der Trennpunkt-Span gehören dazu), Leerraum zusammengefasst,
//     getrimmt; seine Kinder liefern dann keinen eigenen Block.
//   - Element ohne eigenen Text: kein Block, seine Kinder werden einzeln betrachtet.
//   - Reihenfolge der Blöcke = Dokumentreihenfolge; leere Blöcke entfallen.
//   - Selbstenthalten (keine Modul-Closures): die Staging-Spec gibt die Funktion per toString() in den
//     Browser und ruft sie in `sichtbareTexte` mit `(el) => getComputedStyle(el)` auf, statt
//     `[aria-hidden="true"]` zu überspringen.
//
// Fixtures bilden die echte Ist-Struktur nach (MetrikZeile.svelte Z. 76-80, AmpelLeiste.svelte Z. 41-52):
// Skala-Marken und Gewitter-Stufen liegen unter `aria-hidden="true"`, der Trennpunkt „·“ ebenso.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';

const HERE = dirname(fileURLToPath(import.meta.url));

type Stil = { display: string; visibility: string };
type Knoten = {
	nodeType: number;
	nodeValue: string | null;
	tagName?: string;
	childNodes: Knoten[];
	hasAttribute?(name: string): boolean;
	getAttribute?(name: string): string | null;
	_stil?: Partial<Stil>;
};
type Bloecke = (wurzel: Knoten, stil: (el: Knoten) => Stil) => string[];

function fn(): Bloecke {
	const f = (L as Record<string, unknown>).sichtbareTextBloecke;
	assert.equal(typeof f, 'function', 'sichtbareTextBloecke fehlt in elementliste_abgleich_logik.ts');
	return f as Bloecke;
}

/** Textknoten. */
const T = (s: string): Knoten => ({ nodeType: 3, nodeValue: s, childNodes: [] });
/** Element: HTML-Tags in Großbuchstaben wie im DOM, svg-Elemente bleiben klein. */
function E(tag: string, attr: Record<string, string> = {}, stil: Partial<Stil> = {}, ...kinder: Array<Knoten | string>): Knoten {
	const svgTag = tag === 'svg' || tag === 'path' || tag === 'text';
	return {
		nodeType: 1,
		nodeValue: null,
		tagName: svgTag ? tag : tag.toUpperCase(),
		childNodes: kinder.map((k) => (typeof k === 'string' ? T(k) : k)),
		hasAttribute: (n) => n in attr,
		getAttribute: (n) => (n in attr ? attr[n] : null),
		_stil: stil
	};
}
/** Berechneter Stil wie getComputedStyle: Standard sichtbar. */
const STIL = (el: Knoten): Stil => ({ display: el._stil?.display ?? 'inline', visibility: el._stil?.visibility ?? 'visible' });
const HIDDEN = { 'aria-hidden': 'true' };

/** Ist-Struktur einer Metrik-Zeile (Temperatur) mit Skala, Erklärsatz und grün-Span. */
const zeileTemperatur = (): Knoten =>
	E('div', { class: 'wt-zeile' }, { display: 'grid' },
		E('div', { class: 'wt-name' }, { display: 'block' }, E('b', {}, {}, 'Temperatur')),
		E('div', { class: 'wt-mitte' }, { display: 'block' },
			E('div', { class: 'wt-leiste' }, { display: 'block' },
				E('div', { class: 'wt-marken', ...HIDDEN }, { display: 'block' },
					E('i', {}, {}, '-15'), E('i', {}, {}, '-10'), E('i', {}, {}, '-3'), E('i', {}, {}, '2'), E('i', {}, {}, '27')),
				E('div', { class: 'wt-band' }, { display: 'flex' }, E('span', { role: 'img', 'aria-label': 'rot' }), E('span', { role: 'img', 'aria-label': 'grün' }))),
			E('p', { class: 'wt-why' }, { display: 'block' },
				'\n\t\t\t',
				E('span', {}, {}, 'Alarm, wenn es unter -3 °C fällt.'),
				'\n\t\t\t',
				E('span', { class: 'wt-gruen' }, {}, E('span', HIDDEN, {}, '·'), ' grün: 2 bis 27 °C'),
				'\n\t\t')));

/** Ist-Struktur der Gewitter-Leiste (Stufenwörter unter aria-hidden). */
const leisteGewitter = (): Knoten =>
	E('div', { class: 'wt-leiste' }, { display: 'block' },
		E('div', { class: 'wt-marken wt-marken--stufen', ...HIDDEN }, { display: 'flex' },
			E('span', {}, {}, 'keins'), E('span', {}, {}, 'mittel'), E('span', {}, {}, 'hoch')),
		E('div', { class: 'wt-band' }, { display: 'flex' }, E('span', { role: 'img', 'aria-label': 'grün' })));

describe('#3203 AC-1: sichtbarer Text unter aria-hidden zählt', () => {
	test('Skala-Zahlen der Temperatur-Leiste (-15, -10, …) sind einzelne Texte', () => {
		const bloecke = fn()(zeileTemperatur(), STIL);
		for (const z of ['-15', '-10', '-3', '2', '27']) assert.ok(bloecke.includes(z), `Skala-Zahl ${z} fehlt: ${JSON.stringify(bloecke)}`);
	});
	test('Gewitter-Stufenwörter keins/mittel/hoch in Reihenfolge', () => {
		assert.deepEqual(fn()(leisteGewitter(), STIL), ['keins', 'mittel', 'hoch']);
	});
	test('Skala-Zahlen stehen vor dem Alarm-Satz (Dokumentreihenfolge, Reihenfolge-Prüfung AC-1/AC-2)', () => {
		const bloecke = fn()(zeileTemperatur(), STIL);
		assert.deepEqual(bloecke, ['Temperatur', '-15', '-10', '-3', '2', '27', 'Alarm, wenn es unter -3 °C fällt.', '· grün: 2 bis 27 °C']);
	});
	test('aria-hidden="false" und fehlendes aria-hidden ändern nichts', () => {
		const w = E('div', {}, { display: 'block' }, E('span', { 'aria-hidden': 'false' }, {}, 'eins'), E('span', {}, {}, 'zwei'), E('span', HIDDEN, {}, 'drei'));
		assert.deepEqual(fn()(w, STIL), ['eins', 'zwei', 'drei']);
	});
});

describe('#3203 AC-2: Trennpunkt und grün-Text sind EIN Text', () => {
	test('„·“ (aria-hidden) neben „grün: 2 bis 27 °C“ ergibt „· grün: 2 bis 27 °C“', () => {
		const gruen = E('span', { class: 'wt-gruen' }, {}, E('span', HIDDEN, {}, '·'), ' grün: 2 bis 27 °C');
		assert.deepEqual(fn()(gruen, STIL), ['· grün: 2 bis 27 °C']);
	});
	test('Ergebnis passt auf das Elementlisten-Muster „· grün: {von} bis {bis} {einheit}“', () => {
		const bloecke = fn()(zeileTemperatur(), STIL);
		const re = L.musterAlsRegExp('· grün: {von} bis {bis} {einheit}');
		assert.ok(bloecke.map(L.normalisiere).some((t) => re.test(t)), `kein Block passt: ${JSON.stringify(bloecke)}`);
		assert.ok(!bloecke.includes('grün: 2 bis 27 °C'), 'grün-Text ohne Trennpunkt darf nicht als eigener Block stehen');
	});
	test('Element ohne eigenen Text (p.wt-why) verschmilzt seine Kinder nicht', () => {
		const bloecke = fn()(zeileTemperatur(), STIL);
		assert.ok(bloecke.includes('Alarm, wenn es unter -3 °C fällt.'), JSON.stringify(bloecke));
		assert.ok(!bloecke.some((b) => b.includes('fällt.') && b.includes('grün')), `Erklärsatz und grün verschmolzen: ${JSON.stringify(bloecke)}`);
	});
});

describe('#3203 AC-3: Verstecktes und reine Icons erzeugen kein Rauschen', () => {
	test('display:none (am Element und am Vorfahr) zählt nicht', () => {
		const w = E('div', {}, { display: 'block' },
			E('span', {}, { display: 'none' }, 'weg-1'),
			E('div', {}, { display: 'none' }, E('span', HIDDEN, {}, 'weg-2')),
			E('span', {}, {}, 'da'));
		assert.deepEqual(fn()(w, STIL), ['da']);
	});
	test('visibility:hidden (am Element und am Vorfahr) zählt nicht', () => {
		const w = E('div', {}, { display: 'block' },
			E('span', {}, { visibility: 'hidden' }, 'weg-1'),
			E('div', {}, { visibility: 'hidden' }, E('span', {}, {}, 'weg-2')),
			E('span', {}, {}, 'da'));
		assert.deepEqual(fn()(w, STIL), ['da']);
	});
	test('Attribut hidden zählt nicht', () => {
		const w = E('div', {}, { display: 'block' }, E('p', { hidden: '' }, {}, 'weg'), E('p', {}, {}, 'da'));
		assert.deepEqual(fn()(w, STIL), ['da']);
	});
	test('reines SVG/Icon unter aria-hidden liefert keinen Text', () => {
		const icon = E('svg', HIDDEN, {}, E('path', { d: 'M0 0' }), E('text', {}, {}, 'x'));
		const w = E('div', {}, { display: 'block' },
			E('button', { 'aria-label': 'Entfernen' }, {}, icon),
			E('span', HIDDEN, {}, E('svg', {}, {}, E('text', {}, {}, '★'))));
		assert.deepEqual(fn()(w, STIL), []);
	});
	test('Icon neben Text: nur der Text zählt', () => {
		const w = E('button', {}, {}, E('svg', HIDDEN, {}, E('text', {}, {}, '+')), ' Metrik hinzufügen');
		assert.deepEqual(fn()(w, STIL), ['Metrik hinzufügen']);
	});
	test('script und style liefern keinen Text', () => {
		const w = E('div', {}, { display: 'block' }, E('script', {}, {}, 'var a = 1;'), E('style', {}, {}, '.x{}'), E('span', {}, {}, 'da'));
		assert.deepEqual(fn()(w, STIL), ['da']);
	});
	test('nur Leerraum ergibt keinen Block', () => {
		assert.deepEqual(fn()(E('div', {}, { display: 'block' }, '  \n\t ', E('span', {}, {}, ' ')), STIL), []);
	});
});

describe('#3203: Browser-Regel = getestete Regel', () => {
	test('new Function(toString) liefert dieselben Ergebnisse (selbstenthalten serialisierbar)', () => {
		const original = fn();
		const kopie = new Function(`return ${original.toString()}`)() as Bloecke;
		assert.equal(typeof kopie, 'function');
		for (const w of [zeileTemperatur(), leisteGewitter()]) assert.deepEqual(kopie(w, STIL), original(w, STIL));
	});

	test('Staging-Spec überspringt aria-hidden nicht mehr und nutzt sichtbareTextBloecke (doc-compliance-test)', () => {
		// doc-compliance-test: im Projekt gibt es keinen DOM-Parser (kein jsdom/linkedom/happy-dom); sichtbareTexte
		// läuft nur per page.evaluate im Browser. Geprüft wird die Verdrahtung: die getestete Regel wird in den
		// Browser gegeben und dort benutzt, der alte aria-hidden-Filter ist weg. Die Wirkung belegt der Staging-Lauf.
		const spec = readFileSync(join(HERE, 'elementliste-abgleich.staging.spec.ts'), 'utf8');
		const rumpf = spec.match(/function sichtbareTexte\([\s\S]*?\n\}\n/)?.[0];
		assert.ok(rumpf, 'sichtbareTexte nicht gefunden');
		assert.ok(!/aria-hidden/.test(rumpf!), 'sichtbareTexte wertet weiterhin aria-hidden aus');
		assert.match(spec, /^\s*sichtbareTextBloecke,$/m, 'Spec importiert sichtbareTextBloecke aus der Logik');
		assert.match(spec, /sichtbareTextBloecke\.toString\(\)/, 'sichtbareTextBloecke wird nicht per toString() in den Browser gegeben');
		assert.ok(!/function sichtbareTextBloecke\b/.test(spec), 'Spec darf keine eigene Kopie der Regel haben');
	});
});
