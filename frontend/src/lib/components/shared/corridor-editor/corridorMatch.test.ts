// TDD — Issue #1231, Slice 1: corridorInside() Paritäts-Test.
//
// AC-2 (docs/specs/modules/issue_1231_korridor_editor.md): dieselbe
// Fixture-Tabelle wie tests/tdd/test_corridor_match.py (Python-Port) und die
// JSX-Referenz (claude-code-handoff/current/jsx/corridor-editor.jsx) —
// Backend/Frontend müssen identisch matchen (C5).
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/corridor-editor/corridorMatch.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { corridorInside } from './corridorMatch.ts';

// Identisch zu CORRIDOR_INSIDE_FIXTURES in tests/tdd/test_corridor_match.py.
const CORRIDOR_INSIDE_FIXTURES: [number | null, number | null, number | null, boolean | null][] = [
	// value=null -> neutral (null), unabhaengig von min/max
	[null, 0.0, 10.0, null],
	[null, null, null, null],
	[null, null, 10.0, null],
	[null, 0.0, null, null],

	// Grenzwert exakt auf min bzw. max -> true (< / > sind exklusiv geprueft)
	[0.0, 0.0, 10.0, true],
	[10.0, 0.0, 10.0, true],

	// innerhalb des Korridors
	[5.0, 0.0, 10.0, true],

	// ausserhalb: unter min bzw. ueber max
	[-0.1, 0.0, 10.0, false],
	[10.1, 0.0, 10.0, false],

	// offene Untergrenze (min=null) -> nur Obergrenze zaehlt
	[-1000.0, null, 10.0, true],
	[10.0, null, 10.0, true],
	[10.1, null, 10.0, false],

	// offene Obergrenze (max=null) -> nur Untergrenze zaehlt
	[1000.0, 0.0, null, true],
	[0.0, 0.0, null, true],
	[-0.1, 0.0, null, false],

	// beide Seiten offen -> immer true (ausser value=null)
	[0.0, null, null, true],
	[-99999.0, null, null, true],
	[99999.0, null, null, true],
];

describe('corridorInside — Paritaet zu Python-Port + JSX-Referenz (AC-2)', () => {
	for (const [value, min, max, expected] of CORRIDOR_INSIDE_FIXTURES) {
		test(`v=${value} min=${min} max=${max} -> ${expected}`, () => {
			assert.equal(corridorInside(value, min, max), expected);
		});
	}
});

describe('corridorInside — Neutralitaet (C1)', () => {
	test('value=null liefert null, nicht false', () => {
		const result = corridorInside(null, 0, 10);
		assert.equal(result, null);
		assert.notEqual(result, false);
	});
});

describe('corridorInside — beidseitig offen (C2)', () => {
	test('akzeptiert jeden numerischen Wert als innerhalb', () => {
		assert.equal(corridorInside(0, null, null), true);
		assert.equal(corridorInside(-1_000_000, null, null), true);
		assert.equal(corridorInside(1_000_000, null, null), true);
	});
});
