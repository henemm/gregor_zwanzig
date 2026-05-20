// TDD RED — Issue #249: LocationsRail + NewLocationWizard Hilfs-Logik.
//
// Spec: docs/specs/modules/issue_249_locations_rail.md
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/locationHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { toKebabCase, filterLocations } from '../locationHelpers.ts';
import type { Location, ActivityProfile } from '../../../types.ts';

// ─── toKebabCase ────────────────────────────────────────────────────────────

// AC-6: id-Generierung aus Name muss deterministisch und URL-safe sein.
test('toKebabCase: Leerzeichen → Bindestrich', () => {
	assert.equal(toKebabCase('Hintertux Gletscher'), 'hintertux-gletscher');
});

test('toKebabCase: Großbuchstaben → Kleinbuchstaben', () => {
	assert.equal(toKebabCase('Hochkönig'), 'hochkoenig');
});

test('toKebabCase: führende/nachfolgende Leerzeichen werden entfernt', () => {
	assert.equal(toKebabCase('  Zillertal  '), 'zillertal');
});

test('toKebabCase: mehrere Sonderzeichen → Bindestrich, kein doppelter Bindestrich', () => {
	assert.equal(toKebabCase('Alm & Hütte (Tirol)'), 'alm-huette-tirol');
});

test('toKebabCase: bereits kebab-case bleibt unverändert', () => {
	assert.equal(toKebabCase('schladming'), 'schladming');
});

// ─── filterLocations ─────────────────────────────────────────────────────────

function loc(name: string, group?: string): Location {
	return { id: toKebabCase(name), name, lat: 47, lon: 12, group } as Location;
}

const LOCS: Location[] = [
	loc('Penken', 'Zillertal'),
	loc('Mayrhofen', 'Zillertal'),
	loc('Hochkönig', 'Hochkönig'),
	loc('Dienten', 'Hochkönig'),
	loc('Schladming'),
];

// AC-2: Suche filtert nach Name — Groß-/Kleinschreibung irrelevant.
test('filterLocations: Suche nach Name, case-insensitiv', () => {
	const result = filterLocations(LOCS, 'pENKeN', null);
	assert.equal(result.length, 1);
	assert.equal(result[0].name, 'Penken');
});

// AC-2: Suche filtert auch nach Gruppe.
test('filterLocations: Suche nach Gruppenname liefert alle Locations dieser Gruppe', () => {
	const result = filterLocations(LOCS, 'zillertal', null);
	assert.equal(result.length, 2);
	assert.deepEqual(
		result.map((l) => l.name).sort(),
		['Mayrhofen', 'Penken']
	);
});

// AC-3: Chip-Filter nach Gruppe — nur diese Gruppe sichtbar.
test('filterLocations: Gruppen-Chip-Filter zeigt nur gewählte Gruppe', () => {
	const result = filterLocations(LOCS, '', 'Hochkönig');
	assert.equal(result.length, 2);
	assert.ok(result.every((l) => l.group === 'Hochkönig'));
});

// AC-3: Chip-Filter null → alle sichtbar.
test('filterLocations: Chip-Filter null zeigt alle Locations', () => {
	const result = filterLocations(LOCS, '', null);
	assert.equal(result.length, 5);
});

// Kombiniert: Suche + Chip-Filter.
test('filterLocations: Suche + Chip-Filter kombiniert', () => {
	const result = filterLocations(LOCS, 'dienten', 'Hochkönig');
	assert.equal(result.length, 1);
	assert.equal(result[0].name, 'Dienten');
});

// Keine Treffer.
test('filterLocations: kein Treffer liefert leeres Array', () => {
	const result = filterLocations(LOCS, 'xyz', null);
	assert.equal(result.length, 0);
});

// ─── filterLocations: activeProfile (Issue #132) ─────────────────────────────
//
// Tests for activeProfile parameter (Issue #132 — will FAIL until filterLocations is extended)
// Spec: docs/specs/modules/issue_132_compare_activity_profiles.md
//
// Erweitert filterLocations() um den 4. Parameter
// `activeProfile: ActivityProfile | null = null`. Default `null` erhaelt
// Backward-Compat zu allen bestehenden 3-arg-Aufrufen.

function locWithProfile(name: string, profile?: ActivityProfile, group?: string): Location {
	return { id: toKebabCase(name), name, lat: 47, lon: 12, group, activity_profile: profile } as Location;
}

const LOCS_WITH_PROFILES: Location[] = [
	locWithProfile('Penken', 'wintersport', 'Zillertal'),
	locWithProfile('Mayrhofen', 'wintersport', 'Zillertal'),
	locWithProfile('Hochkönig', 'wandern', 'Hochkönig'),
	locWithProfile('Dienten', 'allgemein', 'Hochkönig'),
	locWithProfile('Schladming', undefined),
];

// AC-4 / AC-5 (Spec §1): activeProfile=null darf nicht filtern.
test('filterLocations: activeProfile null returns all locations', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, null);
	assert.equal(result.length, LOCS_WITH_PROFILES.length);
});

// AC-4: Chip-Filter auf "wintersport" zeigt nur Locations mit diesem Profil.
test('filterLocations: activeProfile filters to matching locations only', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, 'wintersport');
	assert.equal(result.length, 2);
	assert.ok(result.every((l) => l.activity_profile === 'wintersport'));
	assert.deepEqual(
		result.map((l) => l.name).sort(),
		['Mayrhofen', 'Penken']
	);
});

// AC-4 Randfall: Filter auf Profil ohne Treffer -> leeres Array.
test('filterLocations: activeProfile with no matching locations returns empty array', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, 'summer_trekking');
	assert.equal(result.length, 0);
});

// AC-4 (Spec §1): UND-Verknuepfung — search + activeProfile.
test('filterLocations: combines search and activeProfile filter', () => {
	// Suche "may" matched "Mayrhofen" (wintersport) und sonst nichts.
	const result = filterLocations(LOCS_WITH_PROFILES, 'may', null, 'wintersport');
	assert.equal(result.length, 1);
	assert.equal(result[0].name, 'Mayrhofen');

	// Suche "hoch" matched "Hochkönig" (wandern); mit Profil-Filter "wintersport" -> 0.
	const result2 = filterLocations(LOCS_WITH_PROFILES, 'hoch', null, 'wintersport');
	assert.equal(result2.length, 0);
});

// AC-2: Locations ohne activity_profile dürfen niemals einen aktiven Profil-Filter matchen.
test('filterLocations: location without profile does not match activeProfile filter', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, 'wintersport');
	// Schladming hat kein Profil -> darf nicht auftauchen.
	assert.ok(!result.some((l) => l.name === 'Schladming'));
	// Dienten hat 'allgemein' -> darf bei Filter 'wintersport' ebenfalls nicht auftauchen.
	assert.ok(!result.some((l) => l.name === 'Dienten'));
});
