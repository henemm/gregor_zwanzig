// TDD RED: Issue #322 — Wetter-Emojis durch WIcon ersetzen
//
// Deckt AC-1, AC-2, AC-3: wmoToWIconKind() gibt korrekte WIconKind-Strings zurück.
// Spec: docs/specs/modules/issue_322_wicon_komponente.md
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/weatherUtils.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { wmoToWIconKind } from './weatherUtils.ts';

// AC-1: Gewitter-WMO → thunder
test('AC-1: WMO 95 (Gewitter) → "thunder"', () => {
	assert.equal(wmoToWIconKind(95), 'thunder');
});

test('AC-1b: WMO 96 (Gewitter mit Hagel) → "thunder"', () => {
	assert.equal(wmoToWIconKind(96), 'thunder');
});

test('AC-1c: WMO 99 (schweres Gewitter) → "thunder"', () => {
	assert.equal(wmoToWIconKind(99), 'thunder');
});

// AC-2: Schnee-WMO → snow
test('AC-2: WMO 71 (leichter Schneefall) → "snow"', () => {
	assert.equal(wmoToWIconKind(71), 'snow');
});

test('AC-2b: WMO 75 (starker Schneefall) → "snow"', () => {
	assert.equal(wmoToWIconKind(75), 'snow');
});

test('AC-2c: WMO 77 (Schneegriesel) → "snow"', () => {
	assert.equal(wmoToWIconKind(77), 'snow');
});

test('AC-2d: WMO 85 (Schneeschauer) → "snow"', () => {
	assert.equal(wmoToWIconKind(85), 'snow');
});

// AC-3: klare Nacht → moon
test('AC-3: isDay=0, cloudPct=20 (klare Nacht) → "moon"', () => {
	assert.equal(wmoToWIconKind(null, 0, null, 20), 'moon');
});

test('AC-3b: isDay=0, cloudPct=0 (wolkenlose Nacht) → "moon"', () => {
	assert.equal(wmoToWIconKind(null, 0, null, 0), 'moon');
});

test('AC-3c: isDay=0, cloudPct=60 (bewölkte Nacht) → "cloud"', () => {
	assert.equal(wmoToWIconKind(null, 0, null, 60), 'cloud');
});

// Regen
test('Regen: WMO 61 → "rain"', () => {
	assert.equal(wmoToWIconKind(61), 'rain');
});

test('Regen: WMO 63 (mäßiger Regen) → "rain"', () => {
	assert.equal(wmoToWIconKind(63), 'rain');
});

test('Regen: WMO 80 (Regenschauer) → "rain"', () => {
	assert.equal(wmoToWIconKind(80), 'rain');
});

// Nebel → cloud
test('Nebel: WMO 45 → "cloud"', () => {
	assert.equal(wmoToWIconKind(45), 'cloud');
});

test('Nebel: WMO 48 (gefrierender Nebel) → "cloud"', () => {
	assert.equal(wmoToWIconKind(48), 'cloud');
});

// Sonniger Tag
test('Sonnig: DNI > 500, isDay=1 → "sun"', () => {
	assert.equal(wmoToWIconKind(null, 1, 600, null), 'sun');
});

// Fallback
test('Fallback: kein WMO, kein isDay, kein dni → "cloud"', () => {
	assert.equal(wmoToWIconKind(null), 'cloud');
});
