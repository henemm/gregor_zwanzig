// Issue #249 — Reine Hilfsfunktionen fuer LocationsRail + NewLocationWizard.
//
// Spec: docs/specs/modules/issue_249_locations_rail.md
//
// Diese Datei enthaelt ausschliesslich pure Funktionen ohne Svelte-Abhaengigkeit —
// damit sind sie via `node --experimental-strip-types --test` unit-testbar.

import type { Location, ActivityProfile, Group } from '../../types.js';

/**
 * Wandelt einen freien Namen in eine URL-/Id-taugliche kebab-case-Form um.
 *
 * Verhalten:
 * - Trimmt fuehrende/nachfolgende Whitespaces
 * - Lowercased
 * - Deutsche Umlaute -> ae/oe/ue, ss -> ss (sz)
 * - Alle uebrigen Nicht-Alphanumerischen Zeichen werden zu '-'
 * - Mehrfach-Bindestriche werden auf einen einzelnen reduziert
 * - Fuehrende/nachfolgende Bindestriche werden entfernt
 *
 * Beispiele:
 *   'Hintertux Gletscher' -> 'hintertux-gletscher'
 *   'Hochkoenig'           -> 'hochkoenig'
 *   '  Zillertal  '       -> 'zillertal'
 *   'Alm & Huette (Tirol)' -> 'alm-huette-tirol'
 */
export function toKebabCase(input: string): string {
	return input
		.trim()
		.toLowerCase()
		.replace(/ä/g, 'ae')
		.replace(/ö/g, 'oe')
		.replace(/ü/g, 'ue')
		.replace(/ß/g, 'ss')
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/-+/g, '-')
		.replace(/^-+|-+$/g, '');
}

/**
 * Filtert eine Location-Liste anhand eines Suchstrings, eines optionalen
 * Gruppen-Chip-Filters (group_id) und eines optionalen Aktivitaetsprofil-Filters.
 *
 * Issue #301 §4: Gruppen werden ueber `group_id` (Group-Entity) statt Legacy-
 * Freitext `loc.group` gefiltert. Die `groupNameMap` (group_id -> group.name)
 * erlaubt die Suche im Gruppennamen (AC-4).
 *
 * Regeln:
 * - `search === ''` UND `activeGroupId === null` UND `activeProfile === null`
 *   -> alle Locations zurueck (kein Filter aktiv)
 * - Suche ist case-insensitiv und vergleicht Ortsname ODER Gruppenname
 *   (aufgeloest via groupNameMap) als Substring-Match
 * - Wenn `activeGroupId !== null` wird zusaetzlich nach exakt dieser group_id
 *   gefiltert (UND-Verknuepfung); Orte ohne group_id matchen dann nie
 * - Wenn `activeProfile !== null` wird zusaetzlich nach exakt diesem Profil
 *   gefiltert; Locations ohne `activity_profile` matchen nicht (Issue #132).
 */
export function filterLocations(
	locations: Location[],
	search: string,
	activeGroupId: string | null,
	activeProfile: ActivityProfile | null = null,
	groupNameMap: Map<string, string> = new Map(),
): Location[] {
	if (search === '' && activeGroupId === null && activeProfile === null) {
		return locations;
	}
	const q = search.toLowerCase();
	return locations.filter((l) => {
		const groupName = groupNameMap.get(l.group_id ?? '') ?? '';
		const matchesSearch =
			search === '' ||
			l.name.toLowerCase().includes(q) ||
			groupName.toLowerCase().includes(q);
		const matchesGroup = activeGroupId === null || l.group_id === activeGroupId;
		const matchesProfile =
			activeProfile === null || l.activity_profile === activeProfile;
		return matchesSearch && matchesGroup && matchesProfile;
	});
}

/**
 * Gruppiert Orte nach `group_id` ihrer Group-Entity fuer die Sidebar (Issue #301 §5/§8).
 *
 * Rueckgabe:
 *   { sections: { group, locations }[]; ungrouped }
 *
 * Regeln:
 * - Sektionen sind nach `group.order` aufsteigend sortiert.
 * - Orte ohne `group_id` ODER mit unbekannter `group_id` (nicht in `groups`)
 *   landen in `ungrouped`.
 * - Leere Gruppen erscheinen als Sektion mit leerer locations-Liste.
 */
export function groupLocations(
	locations: Location[],
	groups: Group[],
): { sections: { group: Group; locations: Location[] }[]; ungrouped: Location[] } {
	const sorted = [...groups].sort((a, b) => a.order - b.order);
	const buckets = new Map<string, Location[]>(sorted.map((g) => [g.id, []]));
	const ungrouped: Location[] = [];
	for (const loc of locations) {
		const bucket = loc.group_id ? buckets.get(loc.group_id) : undefined;
		if (bucket) {
			bucket.push(loc);
		} else {
			ungrouped.push(loc);
		}
	}
	const sections = sorted.map((group) => ({ group, locations: buckets.get(group.id)! }));
	return { sections, ungrouped };
}

/**
 * Prueft ob lat/lon-Werte valide Koordinaten fuer die LocationPreviewMap darstellen.
 * Akzeptiert String- oder Number-Werte (Svelte `bind:value` auf `type="number"`
 * konvertiert mitunter zu Number).
 * Valide = beide nicht leer, beide numerisch UND nicht beide exakt 0.
 * Issue #266, Spec: docs/specs/modules/issue_266_location_preview_map.md
 */
export function isCoordsValid(lat: string | number, lon: string | number): boolean {
	const latStr = String(lat);
	const lonStr = String(lon);
	return (
		latStr.trim() !== '' &&
		lonStr.trim() !== '' &&
		!isNaN(Number(latStr)) &&
		!isNaN(Number(lonStr)) &&
		!(Number(latStr) === 0 && Number(lonStr) === 0)
	);
}
