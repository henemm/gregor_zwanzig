// Unit-Tests fuer Issue #238 — profileSignature.
//
// Deckt AC-3 (Helper liefert vollstaendige Signatur pro Profil) und AC-4
// (Fallback auf allgemein bei unbekannter Eingabe).
// Spec: docs/specs/modules/issue_238_profile_signatures.md
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/utils/profileSignature.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { profileSignature } from './profileSignature.ts';
import type { ProfileSignature } from './profileSignature.ts';

const HEX_PATTERN = /^#[0-9a-fA-F]{6}$/;

function assertShape(sig: ProfileSignature) {
	assert.equal(typeof sig.accent, 'string');
	assert.equal(typeof sig.accentFallback, 'string');
	assert.equal(typeof sig.icon, 'string');
	assert.equal(typeof sig.eyebrow, 'string');
	assert.notEqual(sig.accent, '');
	assert.notEqual(sig.accentFallback, '');
	assert.notEqual(sig.icon, '');
	assert.notEqual(sig.eyebrow, '');
	assert.match(sig.accentFallback, HEX_PATTERN);
	assert.match(sig.accent, /^var\(--g-profile-[a-z-]+\)$/);
}

// --- AC-3: Pro Profil korrekte Signatur ----------------------------------

test('profileSignature(wintersport) liefert Eis-Blau, Schneeflocke (AC-3)', () => {
	const sig = profileSignature('wintersport');
	assertShape(sig);
	assert.equal(sig.accent, 'var(--g-profile-wintersport)');
	assert.equal(sig.accentFallback, '#4a7fb5');
	assert.equal(sig.icon, '❄');
	assert.equal(sig.eyebrow, 'Wintersport');
});

test('profileSignature(wandern) liefert Waldgruen, Wanderschuh (AC-3)', () => {
	const sig = profileSignature('wandern');
	assertShape(sig);
	assert.equal(sig.accent, 'var(--g-profile-wandern)');
	assert.equal(sig.accentFallback, '#3a7d44');
	assert.equal(sig.icon, '\u{1F97E}');
	assert.equal(sig.eyebrow, 'Wandern');
});

test('profileSignature(summer_trekking) liefert Burnt-Orange, Bergsymbol (AC-3)', () => {
	const sig = profileSignature('summer_trekking');
	assertShape(sig);
	assert.equal(sig.accent, 'var(--g-profile-summer-trekking)');
	assert.equal(sig.accentFallback, '#c45a2a');
	assert.equal(sig.icon, '\u{1F3D4}');
	assert.equal(sig.eyebrow, 'Sommer-Trekking');
});

test('profileSignature(allgemein) liefert Neutral-Grau, Kreis (AC-3)', () => {
	const sig = profileSignature('allgemein');
	assertShape(sig);
	assert.equal(sig.accent, 'var(--g-profile-allgemein)');
	assert.equal(sig.accentFallback, '#6b675c');
	assert.equal(sig.icon, '◯');
	assert.equal(sig.eyebrow, 'Allgemein');
});

// --- AC-4: Fallback bei unbekannter Eingabe -------------------------------

test('profileSignature("") faellt auf allgemein zurueck (AC-4)', () => {
	const sig = profileSignature('');
	assert.equal(sig.eyebrow, 'Allgemein');
	assert.equal(sig.accentFallback, '#6b675c');
});

test('profileSignature("unknown") faellt auf allgemein zurueck (AC-4)', () => {
	const sig = profileSignature('unknown');
	assert.equal(sig.eyebrow, 'Allgemein');
	assert.equal(sig.accentFallback, '#6b675c');
});

test('profileSignature(undefined-cast) faellt auf allgemein zurueck (AC-4)', () => {
	// @ts-expect-error – defensiver Pfad fuer Nicht-TS-Aufrufer
	const sig = profileSignature(undefined);
	assert.equal(sig.eyebrow, 'Allgemein');
});

test('profileSignature(null-cast) faellt auf allgemein zurueck (AC-4)', () => {
	// @ts-expect-error – null darf zur Laufzeit ankommen
	const sig = profileSignature(null);
	assert.equal(sig.eyebrow, 'Allgemein');
});

// --- Konsistenz: Alle 4 Profile haben unique Werte ------------------------

test('Alle 4 Profile haben paarweise unterschiedliche accentFallback-Werte', () => {
	const fallbacks = [
		profileSignature('wintersport').accentFallback,
		profileSignature('wandern').accentFallback,
		profileSignature('summer_trekking').accentFallback,
		profileSignature('allgemein').accentFallback,
	];
	const unique = new Set(fallbacks);
	assert.equal(unique.size, 4, 'jeder accentFallback muss eindeutig sein');
});

test('Alle 4 Profile haben paarweise unterschiedliche Icons', () => {
	const icons = [
		profileSignature('wintersport').icon,
		profileSignature('wandern').icon,
		profileSignature('summer_trekking').icon,
		profileSignature('allgemein').icon,
	];
	const unique = new Set(icons);
	assert.equal(unique.size, 4, 'jeder icon muss eindeutig sein');
});
