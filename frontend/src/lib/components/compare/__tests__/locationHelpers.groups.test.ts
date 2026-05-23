// TDD RED — Issue #301 Lieferung A: groupLocations (Sidebar-Gruppierung nach group_id).
//
// Bewusst in einer EIGENEN Datei isoliert: der Import von `groupLocations`
// schlägt fehl, solange die Funktion noch nicht exportiert ist (RED-by-import).
// Würde dieser Import in locationHelpers.test.ts stehen, bräche der SyntaxError
// das gesamte Modul ab — dann liefen weder die filterLocations-Assertions noch
// die grünen toKebabCase/isCoordsValid-Tests. Diese Trennung hält den RED-Nachweis
// granular.
//
// Spec: docs/specs/modules/issue_301_sidebar_groups.md (§5 / §8, AC-1/AC-3)
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/locationHelpers.groups.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { toKebabCase, groupLocations } from '../locationHelpers.ts';
import type { Location, ActivityProfile, Group } from '../../../types.ts';

// ─── Fixtures ─────────────────────────────────────────────────────────────────

function loc(name: string, groupId?: string): Location {
	return { id: toKebabCase(name), name, lat: 47, lon: 12, group_id: groupId } as Location;
}

function grp(id: string, name: string, order: number, profile?: ActivityProfile): Group {
	return { id, name, order, default_profile: profile } as Group;
}

const LOCS: Location[] = [
	loc('Penken', 'zillertal'),
	loc('Mayrhofen', 'zillertal'),
	loc('Hochkönig', 'hochkoenig'),
	loc('Dienten', 'hochkoenig'),
	loc('Schladming'),
];

// Bewusst unsortierte Reihenfolge der Gruppen → groupLocations sortiert nach order.
const GROUPS: Group[] = [
	grp('hochkoenig', 'Hochkönig', 2, 'wandern'),
	grp('zillertal', 'Zillertal', 1, 'wintersport'),
	grp('leer', 'Leere Gruppe', 3),
];

// ─── groupLocations (Issue #301 Lieferung A) ──────────────────────────────────
//
// Signatur:
//   groupLocations(locations: Location[], groups: Group[]):
//     { sections: { group: Group; locations: Location[] }[]; ungrouped: Location[] }
//
// Regeln:
// - Orte werden nach group_id ihrer Group-Entity zugeordnet.
// - Sektionen sind nach group.order sortiert.
// - Orte ohne group_id (oder mit unbekannter id) landen in `ungrouped`.
// - Leere Gruppen erscheinen als Sektion mit leerer locations-Liste.

// AC-1: gruppiert Orte nach group_id, Sektionen sortiert nach group.order.
test('groupLocations: gruppiert nach group_id, Sektionen sortiert nach order', () => {
	const { sections } = groupLocations(LOCS, GROUPS);
	// 3 Gruppen → 3 Sektionen, sortiert nach order: zillertal(1), hochkoenig(2), leer(3).
	assert.deepEqual(
		sections.map((s) => s.group.id),
		['zillertal', 'hochkoenig', 'leer']
	);
	// Zillertal hat Penken + Mayrhofen.
	const zillertal = sections.find((s) => s.group.id === 'zillertal');
	assert.ok(zillertal);
	assert.deepEqual(
		zillertal!.locations.map((l) => l.name).sort(),
		['Mayrhofen', 'Penken']
	);
	// Hochkönig hat Hochkönig + Dienten.
	const hochkoenig = sections.find((s) => s.group.id === 'hochkoenig');
	assert.ok(hochkoenig);
	assert.deepEqual(
		hochkoenig!.locations.map((l) => l.name).sort(),
		['Dienten', 'Hochkönig']
	);
});

// AC-3: Orte ohne group_id landen in `ungrouped`.
test('groupLocations: Orte ohne group_id landen in ungrouped', () => {
	const { ungrouped } = groupLocations(LOCS, GROUPS);
	// Schladming hat kein group_id.
	assert.deepEqual(
		ungrouped.map((l) => l.name),
		['Schladming']
	);
});

// AC-3: unbekannte group_id (nicht in groups) → ebenfalls ungrouped.
test('groupLocations: unbekannte group_id landet in ungrouped, nicht in einer Sektion', () => {
	const orphan = loc('Waisenort', 'existiert-nicht');
	const { sections, ungrouped } = groupLocations([...LOCS, orphan], GROUPS);
	assert.ok(ungrouped.some((l) => l.name === 'Waisenort'));
	// Darf in keiner Gruppen-Sektion auftauchen.
	for (const s of sections) {
		assert.ok(!s.locations.some((l) => l.name === 'Waisenort'));
	}
});

// Spec §8: leere Gruppen erscheinen als Sektion mit leerer locations-Liste.
test('groupLocations: leere Gruppe erscheint als Sektion mit leerer Liste', () => {
	const { sections } = groupLocations(LOCS, GROUPS);
	const leer = sections.find((s) => s.group.id === 'leer');
	assert.ok(leer);
	assert.equal(leer!.locations.length, 0);
});
