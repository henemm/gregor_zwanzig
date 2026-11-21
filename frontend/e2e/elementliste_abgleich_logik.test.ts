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

describe('#3203 AC-2/AC-3 (F004): verbundener Block ohne Doppelzählung und ohne versteckten Text', () => {
	test('aria-hidden-Kind MIT Buchstaben neben Eigentext zählt nur im verbundenen Block, nicht zusätzlich einzeln', () => {
		const w = E('span', {}, {}, 'Dauer ', E('span', HIDDEN, {}, 'Std'), ' gesamt');
		assert.deepEqual(fn()(w, STIL), ['Dauer Std gesamt']);
	});
	test('visibility:hidden unter einem verbundenen aria-hidden-Kind gelangt nicht in den Block', () => {
		const w = E('span', {}, {}, 'Wert ',
			E('span', HIDDEN, {}, 'sichtbar', E('span', {}, { visibility: 'hidden' }, 'WEG1')),
			E('span', HIDDEN, { visibility: 'hidden' }, 'WEG2'));
		assert.deepEqual(fn()(w, STIL), ['Wert sichtbar']);
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

// Fix-Loop 1 (Adversary F001/F003): keine neuen Abweichungen in anderen Reitern. Bisheriges Verhalten je Element
// bleibt; verbunden wird nur ein aria-hidden-Kind mit dem eigenen Text seines Elements. Die vorher ungetestete
// Browser-Schleife (Eingaben, aria-label, svg-Ausschluss, Doppelzählung) ist jetzt Teil von sichtbareTextBloecke.
describe('#3203 Fix-Loop 1: bisheriges Verhalten je Element, Sammel-Schleife testbar', () => {
	type Ein = (e: { tag: string; ariaLabel: string | null; placeholder: string | null; value: string }) => string;
	type Sammler = (wurzel: Knoten, stil: (el: Knoten) => Stil, eingabe?: Ein) => string[];
	const sammle = () => fn() as unknown as Sammler;
	const EIN: Ein = (e) => ((e.tag === 'INPUT' || e.tag === 'TEXTAREA') ? e.ariaLabel || e.placeholder || e.value : '');
	const INPUT = (attr: Record<string, string>, value: string): Knoten => ({ ...E('input', attr), value } as Knoten);

	test('Zähler/Badge (ohne aria-hidden) bleibt eigener Text, wird nicht an den Reiternamen geklebt', () => {
		const reiter = E('a', {}, { display: 'flex' }, 'Etappen', E('span', {}, {}, '4'));
		assert.deepEqual(sammle()(reiter, STIL), ['Etappen', '4']);
	});
	test('Hervorhebung im Satz bleibt getrennt wie bisher („Amtliche Warnungen“ + Hinweis)', () => {
		const zeile = E('div', {}, { display: 'block' }, E('b', {}, {}, 'Amtliche Warnungen'), ' immer dabei');
		assert.deepEqual(sammle()(zeile, STIL), ['immer dabei', 'Amtliche Warnungen']);
	});
	test('verbundenes aria-hidden-Kind wird nicht doppelt gezählt', () => {
		const gruen = E('span', {}, {}, E('span', HIDDEN, {}, '·'), ' grün: ab 3 h');
		const b = sammle()(gruen, STIL);
		assert.deepEqual(b, ['· grün: ab 3 h']);
		assert.ok(!b.includes('·'));
	});
	test('reine Zeichen unter aria-hidden („–“, „－“, „:“, „✓“) sind Dekoration; Zahlen und Wörter zählen', () => {
		const w = E('div', {}, { display: 'block' },
			E('span', HIDDEN, {}, '–'), E('span', HIDDEN, {}, '－'), E('span', HIDDEN, {}, ':'), E('span', HIDDEN, {}, '✓'),
			E('span', HIDDEN, {}, '-15'), E('span', HIDDEN, {}, 'mittel'));
		assert.deepEqual(sammle()(w, STIL), ['-15', 'mittel']);
	});
	test('dasselbe Zeichen ohne aria-hidden zählt wie bisher', () => {
		assert.deepEqual(sammle()(E('div', {}, { display: 'block' }, E('span', {}, {}, '–')), STIL), ['–']);
	});
	test('mit eingabe: Eingabefeld-Text und aria-label von Knopf/switch in Dokumentreihenfolge', () => {
		const w = E('div', {}, { display: 'block' },
			E('label', {}, {}, 'Name'),
			INPUT({ 'aria-label': 'Trip-Name' }, 'GR221'),
			E('button', { 'aria-label': 'Entfernen' }, {}, E('svg', HIDDEN, {}, E('text', {}, {}, 'x'))),
			E('div', { role: 'switch', 'aria-label': 'Alarm an' }, {}),
			E('span', { 'aria-label': 'kein Knopf' }, {}, 'Text'));
		assert.deepEqual(sammle()(w, STIL, EIN), ['Name', 'Trip-Name', 'Entfernen', 'Alarm an', 'Text']);
	});
	test('ohne eingabe: keine aria-label und keine Eingaben (nur Textblöcke)', () => {
		const w = E('div', {}, { display: 'block' }, INPUT({ placeholder: 'Ort' }, ''), E('button', { 'aria-label': 'Entfernen' }, {}));
		assert.deepEqual(sammle()(w, STIL), []);
	});
	test('svg wird auch mit eingabe ausgeschlossen (kein Text, keine Beschriftung darin)', () => {
		const w = E('div', {}, { display: 'block' }, E('svg', {}, {}, E('text', {}, {}, 'Legende'), E('g', { role: 'group', 'aria-label': 'Achse' }, {})), E('span', {}, {}, 'da'));
		assert.deepEqual(sammle()(w, STIL, EIN), ['da']);
	});
	test('unter aria-hidden keine aria-label und keine Eingaben (wie bisher)', () => {
		const w = E('div', HIDDEN, { display: 'block' }, E('button', { 'aria-label': 'Schließen' }, {}), INPUT({ placeholder: 'x' }, ''));
		assert.deepEqual(sammle()(w, STIL, EIN), []);
	});
	test('display:none am Vorfahr schließt auch Eingaben und aria-label aus', () => {
		const w = E('div', {}, { display: 'none' }, E('button', { 'aria-label': 'Weg' }, {}), INPUT({}, 'weg'));
		assert.deepEqual(sammle()(w, STIL, EIN), []);
	});
	test('Staging-Spec gibt eingabeText an sichtbareTextBloecke und hat keine eigene Element-Schleife (doc-compliance-test)', () => {
		// doc-compliance-test: Verdrahtung im Browser (kein DOM-Parser im Projekt), Wirkung belegt der Staging-Lauf.
		const spec = readFileSync(join(HERE, 'elementliste-abgleich.staging.spec.ts'), 'utf8');
		const rumpf = spec.match(/function sichtbareTexte\([\s\S]*?\n\}\n/)?.[0] ?? '';
		assert.match(rumpf, /sammle\(wurzel, stil, eingabe\)/, 'sichtbareTexte ruft die Logik nicht mit eingabe auf');
		assert.ok(!/querySelectorAll\('\*'\)/.test(rumpf), 'sichtbareTexte hat wieder eine eigene Element-Schleife');
		assert.ok(!/childNodes/.test(rumpf), 'sichtbareTexte liest Textknoten selbst statt über die Logik');
	});
});
