// Issue #2647 (i18n S2) — AC-4: Platzhalter, Plural und Fallback des reinen
// Uebersetzungskerns `translate.ts`. Gemessen wird die ECHTE Funktion mit einem
// kleinen, echten Katalog als Argument; `console.warn` wird nur mitgezaehlt
// (die Originalfunktion bleibt wirksam, kein Mock eines Prueflings).
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/platzhalter_plural_fallback.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { translate, translatePlural } from '../translate.ts';

const KATALOGE = {
	de: {
		'probe.gruss': 'Hallo {name}',
		'probe.zwei': '{a} und {b}',
		'probe.etappen.one': '{count} Etappe für {name}',
		'probe.etappen.other': '{count} Etappen für {name}',
		'probe.nur_de': 'Nur deutsch',
		'probe.nur_de_zwei': 'Auch nur deutsch'
	},
	en: {
		'probe.gruss': 'Hello {name}',
		'probe.zwei': '{a} and {b}',
		'probe.etappen.one': '{count} stage for {name}',
		'probe.etappen.other': '{count} stages for {name}'
	}
};

let warnungen: string[] = [];
const originalWarn = console.warn;
beforeEach(() => {
	warnungen = [];
	console.warn = (...args: unknown[]) => {
		warnungen.push(args.map(String).join(' '));
	};
});
afterEach(() => {
	console.warn = originalWarn;
});

describe('AC-4: Platzhalter', () => {
	test('{name} wird in beiden Sprachen ersetzt', () => {
		assert.equal(translate(KATALOGE, 'de', 'probe.gruss', { name: 'Anna' }), 'Hallo Anna');
		assert.equal(translate(KATALOGE, 'en', 'probe.gruss', { name: 'Anna' }), 'Hello Anna');
	});
	test('mehrere Platzhalter, Zahlen als Werte', () => {
		assert.equal(translate(KATALOGE, 'en', 'probe.zwei', { a: 1, b: 'zwei' }), '1 and zwei');
	});
	test('fehlender Parameter bleibt sichtbar stehen (kein Absturz)', () => {
		assert.equal(translate(KATALOGE, 'de', 'probe.gruss'), 'Hallo {name}');
		assert.equal(translate(KATALOGE, 'de', 'probe.zwei', { a: 'x' }), 'x und {b}');
	});
	test('ohne Platzhalter: Text unveraendert, keine Warnung', () => {
		assert.equal(translate(KATALOGE, 'de', 'probe.nur_de'), 'Nur deutsch');
		assert.deepEqual(warnungen, []);
	});
});

describe('AC-4: Plural', () => {
	test('.one bei 1, .other bei 0 und 2; {count} implizit verfuegbar', () => {
		assert.equal(translatePlural(KATALOGE, 'de', 'probe.etappen', 1, { name: 'GR20' }), '1 Etappe für GR20');
		assert.equal(translatePlural(KATALOGE, 'de', 'probe.etappen', 0, { name: 'GR20' }), '0 Etappen für GR20');
		assert.equal(translatePlural(KATALOGE, 'de', 'probe.etappen', 2, { name: 'GR20' }), '2 Etappen für GR20');
		assert.equal(translatePlural(KATALOGE, 'en', 'probe.etappen', 1, { name: 'GR20' }), '1 stage for GR20');
		assert.equal(translatePlural(KATALOGE, 'en', 'probe.etappen', 0, { name: 'GR20' }), '0 stages for GR20');
		assert.equal(translatePlural(KATALOGE, 'en', 'probe.etappen', 2, { name: 'GR20' }), '2 stages for GR20');
	});
});

describe('AC-4: Fallback auf Deutsch', () => {
	test('fehlt en, kommt der deutsche Text; je Schluessel genau EINE Warnung', () => {
		assert.equal(translate(KATALOGE, 'en', 'probe.nur_de'), 'Nur deutsch');
		assert.equal(translate(KATALOGE, 'en', 'probe.nur_de'), 'Nur deutsch');
		assert.equal(translate(KATALOGE, 'en', 'probe.nur_de'), 'Nur deutsch');
		assert.deepEqual(warnungen, ['i18n fallback: probe.nur_de']);
	});
	test('ein zweiter fehlender Schluessel warnt seinerseits genau einmal', () => {
		translate(KATALOGE, 'en', 'probe.nur_de_zwei');
		translate(KATALOGE, 'en', 'probe.nur_de_zwei');
		assert.deepEqual(warnungen, ['i18n fallback: probe.nur_de_zwei']);
	});
	test('Deutsch selbst loest nie eine Fallback-Warnung aus', () => {
		translate(KATALOGE, 'de', 'probe.gruss', { name: 'x' });
		translate(KATALOGE, 'en', 'probe.gruss', { name: 'x' });
		assert.deepEqual(warnungen, []);
	});
});
