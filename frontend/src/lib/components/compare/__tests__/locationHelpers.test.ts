// TDD RED — Issue #249: LocationsRail + NewLocationWizard Hilfs-Logik.
// TDD RED — Issue #266: isCoordsValid — Validierungslogik für LocationPreviewMap.
// TDD RED — Issue #301 Lieferung A: filterLocations auf group_id + groupNameMap.
//           (groupLocations-Tests liegen isoliert in locationHelpers.groups.test.ts,
//            damit der dortige fehlende Export dieses Modul nicht mit-abbricht und
//            die filterLocations-Assertions als sichtbares RED laufen.)
//
// Specs:
//   docs/specs/modules/issue_249_locations_rail.md
//   docs/specs/modules/issue_266_location_preview_map.md
//   docs/specs/modules/issue_301_sidebar_groups.md
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/locationHelpers.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { toKebabCase, filterLocations, isCoordsValid } from '../locationHelpers.ts';
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

// ─── filterLocations (Issue #301: group_id + groupNameMap) ────────────────────
//
// Spec §4: filterLocations(locations, search, activeGroupId, activeProfile, groupNameMap).
// Gruppen werden über group_id (Group-Entity) statt Legacy-Freitext loc.group gefiltert.
// Die groupNameMap (group_id → group.name) ermöglicht die Suche im Gruppennamen (AC-4).

// group_id-Werte sind kebab-case IDs der Group-Entity (analog Backend).
function loc(name: string, groupId?: string): Location {
	return { id: toKebabCase(name), name, lat: 47, lon: 12, group_id: groupId } as Location;
}

const LOCS: Location[] = [
	loc('Penken', 'zillertal'),
	loc('Mayrhofen', 'zillertal'),
	loc('Hochkönig', 'hochkoenig'),
	loc('Dienten', 'hochkoenig'),
	loc('Schladming'),
];

// group_id → Gruppenname (für die Suche im Gruppennamen, AC-4).
const GROUP_NAME_MAP = new Map<string, string>([
	['zillertal', 'Zillertal'],
	['hochkoenig', 'Hochkönig'],
]);

// AC-2: Suche filtert nach Name — Groß-/Kleinschreibung irrelevant.
test('filterLocations: Suche nach Name, case-insensitiv', () => {
	const result = filterLocations(LOCS, 'pENKeN', null, null, GROUP_NAME_MAP);
	assert.equal(result.length, 1);
	assert.equal(result[0].name, 'Penken');
});

// AC-4: Suche trifft den Gruppennamen über groupNameMap → alle Orte dieser Gruppe.
test('filterLocations: Suche nach Gruppenname (via groupNameMap) liefert alle Locations dieser Gruppe', () => {
	const result = filterLocations(LOCS, 'zillertal', null, null, GROUP_NAME_MAP);
	assert.equal(result.length, 2);
	assert.deepEqual(
		result.map((l) => l.name).sort(),
		['Mayrhofen', 'Penken']
	);
});

// AC-1/Spec §4: Chip-Filter nach group_id — nur diese Gruppe sichtbar.
test('filterLocations: Gruppen-Filter nach activeGroupId zeigt nur diese Gruppe', () => {
	const result = filterLocations(LOCS, '', 'hochkoenig', null, GROUP_NAME_MAP);
	assert.equal(result.length, 2);
	assert.ok(result.every((l) => l.group_id === 'hochkoenig'));
});

// Spec §4: activeGroupId null → alle sichtbar (auch Orte ohne group_id).
test('filterLocations: activeGroupId null zeigt alle Locations inkl. ohne group_id', () => {
	const result = filterLocations(LOCS, '', null, null, GROUP_NAME_MAP);
	assert.equal(result.length, 5);
	// Schladming hat kein group_id und muss bei activeGroupId=null enthalten sein.
	assert.ok(result.some((l) => l.name === 'Schladming'));
});

// Kombiniert: Suche + Gruppen-Filter (UND-Verknüpfung).
test('filterLocations: Suche + activeGroupId kombiniert', () => {
	const result = filterLocations(LOCS, 'dienten', 'hochkoenig', null, GROUP_NAME_MAP);
	assert.equal(result.length, 1);
	assert.equal(result[0].name, 'Dienten');
});

// Keine Treffer.
test('filterLocations: kein Treffer liefert leeres Array', () => {
	const result = filterLocations(LOCS, 'xyz', null, null, GROUP_NAME_MAP);
	assert.equal(result.length, 0);
});

// ─── filterLocations: activeProfile (Issue #132, Issue #301 Signatur) ─────────
//
// Tests für den activeProfile-Parameter (Issue #132); seit Issue #301 mit
// groupNameMap als 5. Argument und group_id statt Legacy-group in den Fixtures.
// Spec: docs/specs/modules/issue_132_compare_activity_profiles.md
//       docs/specs/modules/issue_301_sidebar_groups.md §4

function locWithProfile(name: string, profile?: ActivityProfile, groupId?: string): Location {
	return {
		id: toKebabCase(name),
		name,
		lat: 47,
		lon: 12,
		group_id: groupId,
		activity_profile: profile,
	} as Location;
}

const LOCS_WITH_PROFILES: Location[] = [
	locWithProfile('Penken', 'wintersport', 'zillertal'),
	locWithProfile('Mayrhofen', 'wintersport', 'zillertal'),
	locWithProfile('Hochkönig', 'wandern', 'hochkoenig'),
	locWithProfile('Dienten', 'allgemein', 'hochkoenig'),
	locWithProfile('Schladming', undefined),
];

// AC-4 / AC-5 (Spec §1): activeProfile=null darf nicht filtern.
test('filterLocations: activeProfile null returns all locations', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, null, GROUP_NAME_MAP);
	assert.equal(result.length, LOCS_WITH_PROFILES.length);
});

// AC-4: Chip-Filter auf "wintersport" zeigt nur Locations mit diesem Profil.
test('filterLocations: activeProfile filters to matching locations only', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, 'wintersport', GROUP_NAME_MAP);
	assert.equal(result.length, 2);
	assert.ok(result.every((l) => l.activity_profile === 'wintersport'));
	assert.deepEqual(
		result.map((l) => l.name).sort(),
		['Mayrhofen', 'Penken']
	);
});

// AC-4 Randfall: Filter auf Profil ohne Treffer -> leeres Array.
test('filterLocations: activeProfile with no matching locations returns empty array', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, 'summer_trekking', GROUP_NAME_MAP);
	assert.equal(result.length, 0);
});

// AC-4 (Spec §1): UND-Verknuepfung — search + activeProfile.
test('filterLocations: combines search and activeProfile filter', () => {
	// Suche "may" matched "Mayrhofen" (wintersport) und sonst nichts.
	const result = filterLocations(LOCS_WITH_PROFILES, 'may', null, 'wintersport', GROUP_NAME_MAP);
	assert.equal(result.length, 1);
	assert.equal(result[0].name, 'Mayrhofen');

	// Suche "hoch" matched "Hochkönig" (wandern); mit Profil-Filter "wintersport" -> 0.
	const result2 = filterLocations(LOCS_WITH_PROFILES, 'hoch', null, 'wintersport', GROUP_NAME_MAP);
	assert.equal(result2.length, 0);
});

// AC-2: Locations ohne activity_profile dürfen niemals einen aktiven Profil-Filter matchen.
test('filterLocations: location without profile does not match activeProfile filter', () => {
	const result = filterLocations(LOCS_WITH_PROFILES, '', null, 'wintersport', GROUP_NAME_MAP);
	// Schladming hat kein Profil -> darf nicht auftauchen.
	assert.ok(!result.some((l) => l.name === 'Schladming'));
	// Dienten hat 'allgemein' -> darf bei Filter 'wintersport' ebenfalls nicht auftauchen.
	assert.ok(!result.some((l) => l.name === 'Dienten'));
});

// ─── isCoordsValid (Issue #266) ───────────────────────────────────────────────
//
// Prueft die Koordinaten-Validierungslogik fuer LocationPreviewMap.
// Spec: docs/specs/modules/issue_266_location_preview_map.md (coordsValid-Logik)
//
// Regel: valide wenn lat und lon numerisch und NOT beide 0.

// AC-2: Default-Koordinaten (47.0 / 11.0) sind valide.
test('isCoordsValid: 47.0 / 11.0 ist valide (Default-Werte)', () => {
	assert.equal(isCoordsValid('47.0', '11.0'), true);
});

// AC-3: 0 / 0 ist nicht valide.
test('isCoordsValid: 0 / 0 ist nicht valide', () => {
	assert.equal(isCoordsValid('0', '0'), false);
});

// Randfall: 0 / 11.0 ist valide (nur beide 0 sind verboten).
test('isCoordsValid: 0 lat mit gültigem lon ist valide', () => {
	assert.equal(isCoordsValid('0', '11.0'), true);
});

// Randfall: 47.0 / 0 ist valide.
test('isCoordsValid: gültiger lat mit 0 lon ist valide', () => {
	assert.equal(isCoordsValid('47.0', '0'), true);
});

// Randfall: NaN-String ist nicht valide.
test('isCoordsValid: NaN-String ist nicht valide', () => {
	assert.equal(isCoordsValid('abc', '11.0'), false);
});

// Randfall: Leerer String ist nicht valide.
test('isCoordsValid: leerer String ist nicht valide', () => {
	assert.equal(isCoordsValid('', '11.0'), false);
});

// AC-4: Negative Koordinaten (z.B. Südhalbkugel) sind valide.
test('isCoordsValid: negative Koordinaten sind valide', () => {
	assert.equal(isCoordsValid('-33.8688', '151.2093'), true);
});

// Randfall: Sehr kleine Nicht-Null-Werte sind valide.
test('isCoordsValid: kleiner positiver Wert (0.0001) ist valide', () => {
	assert.equal(isCoordsValid('0.0001', '0.0001'), true);
});
