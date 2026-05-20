// Issue #249 — Reine Hilfsfunktionen fuer LocationsRail + NewLocationWizard.
//
// Spec: docs/specs/modules/issue_249_locations_rail.md
//
// Diese Datei enthaelt ausschliesslich pure Funktionen ohne Svelte-Abhaengigkeit —
// damit sind sie via `node --experimental-strip-types --test` unit-testbar.

import type { Location, ActivityProfile } from '../../types.js';

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
 * Gruppen-Chip-Filters und eines optionalen Aktivitaetsprofil-Filters.
 *
 * Regeln:
 * - `search === ''` UND `activeGroup === null` UND `activeProfile === null`
 *   -> alle Locations zurueck (kein Filter aktiv)
 * - Suche ist case-insensitiv und vergleicht Name ODER Gruppe (Substring-Match)
 * - Wenn `activeGroup !== null` wird zusaetzlich nach exakt diesem Gruppennamen
 *   gefiltert (UND-Verknuepfung)
 * - Wenn `activeProfile !== null` wird zusaetzlich nach exakt diesem Profil
 *   gefiltert; Locations ohne `activity_profile` matchen nicht (Issue #132).
 */
export function filterLocations(
	locations: Location[],
	search: string,
	activeGroup: string | null,
	activeProfile: ActivityProfile | null = null,
): Location[] {
	if (search === '' && activeGroup === null && activeProfile === null) {
		return locations;
	}
	const q = search.toLowerCase();
	return locations.filter((l) => {
		const matchesSearch =
			search === '' ||
			l.name.toLowerCase().includes(q) ||
			(l.group ?? '').toLowerCase().includes(q);
		const matchesGroup = activeGroup === null || l.group === activeGroup;
		const matchesProfile =
			activeProfile === null || l.activity_profile === activeProfile;
		return matchesSearch && matchesGroup && matchesProfile;
	});
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
