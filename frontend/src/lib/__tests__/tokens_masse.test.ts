// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 1.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-5.
//
// Soll: app.css bekommt reine Maß-Tokens.
//   - --g-tap-min ist 44px (Touch-Ziel).
//   - --g-size-* gibt es NUR für Maße, die nicht schon ein --g-s-1..20-Wert sind (4px-Raster); ein
//     --g-size-* mit einem Rasterwert wäre ein Doppel-Token. Jeder --g-size-*-Wert ist ein fester Wert
//     (px oder em), kein Verweis auf ein anderes Token.
//   - Maß-Tokens sind in Light und Dark identisch: der Dark-Block definiert sie entweder nicht oder mit
//     demselben Wert.
//
// Messweise: Die Token-Definitionen in app.css sind Gegenstand der Regel (wie dark_palette_kontrast):
// doc-compliance-test
//
// RED heute: --g-tap-min fehlt.
//
//   cd frontend && npm test -- src/lib/__tests__/tokens_masse.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const CSS = readFileSync(join(HIER, '..', '..', 'app.css'), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

/** Inhalt des ersten Blocks, dessen Selektor genau `selektor` ist (Klammern gezählt). */
function block(selektor: string): string {
	const re = new RegExp(`(^|[\\s}])${selektor.replace(/[[\]"()=]/g, (c) => `\\${c}`)}\\s*\\{`, 'm');
	const m = re.exec(CSS);
	assert.ok(m, `Block ${selektor} nicht gefunden`);
	let i = m!.index + m![0].length;
	const start = i;
	for (let tiefe = 1; tiefe > 0; i++) {
		if (CSS[i] === '{') tiefe++;
		else if (CSS[i] === '}') tiefe--;
	}
	return CSS.slice(start, i - 1);
}

function tokens(text: string): Map<string, string> {
	const aus = new Map<string, string>();
	for (const m of text.matchAll(/(--g-[\w-]+)\s*:\s*([^;]+);/g)) if (!aus.has(m[1])) aus.set(m[1], m[2].trim());
	return aus;
}

const HELL = tokens(block(':root'));
const DUNKEL = tokens(block(':root[data-theme="dark"]'));
const RASTER = new Set([...HELL].filter(([k]) => /^--g-s-\d+$/.test(k)).map(([, v]) => v));
const SIZE = [...HELL].filter(([k]) => k.startsWith('--g-size-'));

describe('AC-5: Maß-Tokens --g-tap-min und --g-size-*', () => {
	test('--g-tap-min ist im hellen :root als 44px definiert', () => {
		assert.equal(HELL.get('--g-tap-min'), '44px', 'TDD RED: --g-tap-min fehlt oder ist nicht 44px');
	});
	test('das 4px-Raster --g-s-* ist bekannt (Bezugsgröße der Regel)', () => {
		assert.ok(RASTER.has('4px') && RASTER.has('80px'), `Raster: ${[...RASTER].join(', ')}`);
	});
	test('kein --g-size-* doppelt einen Wert des Rasters --g-s-1..20 oder --g-tap-min', () => {
		const doppelt = SIZE.filter(([, v]) => RASTER.has(v) || v === '44px').map(([k, v]) => `${k}: ${v}`);
		assert.deepEqual(doppelt, []);
	});
	test('jedes --g-size-* ist ein fester Maßwert (px oder em), kein Verweis', () => {
		const falsch = SIZE.filter(([, v]) => !/^-?\d*\.?\d+(px|em)$/.test(v)).map(([k, v]) => `${k}: ${v}`);
		assert.deepEqual(falsch, []);
	});
	test('Maß-Tokens sind in Light und Dark identisch', () => {
		const masse = [...HELL].filter(([k]) => k === '--g-tap-min' || k.startsWith('--g-size-'));
		assert.ok(masse.length > 0, 'TDD RED: keine Maß-Tokens im hellen :root');
		const abweichend = masse
			.filter(([k, v]) => DUNKEL.has(k) && DUNKEL.get(k) !== v)
			.map(([k, v]) => `${k}: hell ${v}, dunkel ${DUNKEL.get(k)}`);
		assert.deepEqual(abweichend, []);
		const nurDunkel = [...DUNKEL.keys()].filter(
			(k) => (k === '--g-tap-min' || k.startsWith('--g-size-')) && !HELL.has(k)
		);
		assert.deepEqual(nurDunkel, [], 'Maß-Token nur im Dark-Block definiert');
	});
});
