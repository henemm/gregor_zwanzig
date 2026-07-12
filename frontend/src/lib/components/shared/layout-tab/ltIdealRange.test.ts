// TDD — Issue #1232 Scheibe 3a Fix-Runde (Adversary F003): ltIdealRange.ts
//
// Reine Verhaltenstests (KEIN Mock). Range gesetzt → Grün-Entscheidung folgt
// dem Range; kein Range (oder nicht-numerisch, z. B. Enum) → Fallback.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/layout-tab/ltIdealRange.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { isIdealGood } from './ltIdealRange.ts';

const fallbackAlwaysTrue = () => true;
const fallbackAlwaysFalse = () => false;
const fallbackSnowThreshold = (v: number) => v >= 80;

describe('isIdealGood — Range konfiguriert (min+max)', () => {
	test('Wert innerhalb [min,max] → true (Fallback wird ignoriert)', () => {
		assert.equal(isIdealGood(100, { min: 30, max: 200 }, fallbackAlwaysFalse), true);
	});

	test('Wert unterhalb min → false', () => {
		assert.equal(isIdealGood(10, { min: 30, max: 200 }, fallbackAlwaysTrue), false);
	});

	test('Wert oberhalb max → false', () => {
		assert.equal(isIdealGood(250, { min: 30, max: 200 }, fallbackAlwaysTrue), false);
	});
});

describe('isIdealGood — Range nur min ODER nur max', () => {
	test('nur min gesetzt, Wert darüber → true', () => {
		assert.equal(isIdealGood(50, { min: 30 }, fallbackAlwaysFalse), true);
	});

	test('nur max gesetzt, Wert darunter → true', () => {
		assert.equal(isIdealGood(20, { max: 40 }, fallbackAlwaysFalse), true);
	});

	test('nur max gesetzt, Wert darüber → false', () => {
		assert.equal(isIdealGood(50, { max: 40 }, fallbackAlwaysTrue), false);
	});
});

describe('isIdealGood — Grenzen inklusive (Adversary F005)', () => {
	test('Wert exakt auf min → true (min inklusiv)', () => {
		assert.equal(isIdealGood(30, { min: 30 }, fallbackAlwaysFalse), true);
	});

	test('Wert exakt auf max → true (max inklusiv)', () => {
		assert.equal(isIdealGood(40, { max: 40 }, fallbackAlwaysFalse), true);
	});
});

describe('isIdealGood — kein Range konfiguriert → Fallback', () => {
	test('range undefined → Fallback-Funktion entscheidet', () => {
		assert.equal(isIdealGood(90, undefined, fallbackSnowThreshold), true);
		assert.equal(isIdealGood(10, undefined, fallbackSnowThreshold), false);
	});

	test('range vorhanden, aber weder min noch max numerisch (Enum, z. B. thunder_level_max: "NONE") → Fallback', () => {
		assert.equal(isIdealGood(90, { max: 'NONE' }, fallbackSnowThreshold), true);
	});

	test('leeres Range-Objekt {} → Fallback', () => {
		assert.equal(isIdealGood(10, {}, fallbackSnowThreshold), false);
	});
});
