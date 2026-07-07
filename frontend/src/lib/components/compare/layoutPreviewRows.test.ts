// TDD — Issue #1093: LayoutPreview crasht bei echten pickedIds (rows[0] undefined)
//
// Reine Verhaltenstests auf der Pure-Function `selectPreviewRows` (KEIN Mock,
// KEINE Dateiinhalt-Prüfung). Vor dem Fix filterte der `rows`-$derived nach
// pickedIds gegen die Dummy-IDs — echte Location-UUIDs matchen diese nie,
// wodurch rows=[] entstand und `rows[0].feels` etc. mit
// "Cannot read properties of undefined" crashten. Der Fix deckelt stattdessen
// nur die Anzahl der Beispielzeilen auf pickedIds.length, ohne nach ID zu
// filtern — das Ergebnis ist bei pickedIds.length > 0 nie leer.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/layoutPreviewRows.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { selectPreviewRows } from './layoutPreviewRows.ts';

const DUMMIES = [{ id: 'loc-01' }, { id: 'loc-07' }, { id: 'loc-08' }];

describe('selectPreviewRows — Bug-Reproduktion #1093', () => {
	test('echte UUID-artige pickedIds (matchen keine Dummy-ID) ergeben trotzdem gefüllte rows', () => {
		const pickedIds = ['loc-abc-uuid-1', 'loc-xyz-uuid-2'];
		const result = selectPreviewRows(pickedIds, DUMMIES);

		assert.equal(
			result.length,
			2,
			'vor dem Fix hätte ein ID-Filter hier [] ergeben (keine Dummy-ID matcht eine echte UUID)'
		);
		assert.notEqual(
			result[0],
			undefined,
			'result[0] muss definiert sein — sonst crasht rows[0].feels wie in #1093'
		);
	});
});

describe('selectPreviewRows — Längen-Deckelung', () => {
	for (const count of [1, 2, 3, 100]) {
		test(`pickedIds.length=${count} → Ergebnislänge = min(${count}, 3), nie leer`, () => {
			const pickedIds = Array.from({ length: count }, (_, i) => `loc-real-${i}`);
			const result = selectPreviewRows(pickedIds, DUMMIES);

			assert.equal(result.length, Math.min(count, DUMMIES.length));
			assert.notEqual(result[0], undefined, 'result[0] muss immer definiert sein');
		});
	}
});

describe('selectPreviewRows — leere Auswahl', () => {
	test('pickedIds = [] gibt alle Dummys zurück', () => {
		const result = selectPreviewRows([], DUMMIES);

		assert.equal(result.length, DUMMIES.length);
		assert.deepEqual(result, DUMMIES);
	});
});
