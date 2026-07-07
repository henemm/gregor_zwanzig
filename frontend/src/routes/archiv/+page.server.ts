import type { PageServerLoad } from './$types.js';
import type { Trip, ComparePreset } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


// Issue #611 — vereinheitlichter Archiv-Eintrag für Trips UND Orts-Vergleiche.
export type ArchiveEntry = {
	id: string;
	type: 'trip' | 'compare';
	name: string;
	detail: string; // "13 Etappen" | "6 Orte"
	archived: string; // YYYY-MM-DD
};

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [tripsRes, presetsRes] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers, signal: AbortSignal.timeout(5000) }).catch(() => null),
		fetch(`${API()}/api/compare/presets`, { headers, signal: AbortSignal.timeout(5000) }).catch(
			() => null
		)
	]);

	const allTrips: Trip[] = tripsRes?.ok ? await tripsRes.json() : [];
	const tripEntries: ArchiveEntry[] = (Array.isArray(allTrips) ? allTrips : [])
		.filter((t) => t.archived_at != null)
		.map((t) => {
			const n = t.stages?.length ?? 0;
			return {
				id: t.id,
				type: 'trip' as const,
				name: t.name,
				detail: `${n} ${n === 1 ? 'Etappe' : 'Etappen'}`,
				archived: (t.archived_at ?? '').slice(0, 10)
			};
		});

	const rawPresets = presetsRes?.ok ? await presetsRes.json() : [];
	const allPresets: ComparePreset[] = Array.isArray(rawPresets)
		? rawPresets
		: (rawPresets?.presets ?? []);
	const compareEntries: ArchiveEntry[] = allPresets
		.filter((p) => p.archived_at != null)
		.map((p) => {
			const n = p.location_ids?.length ?? 0;
			return {
				id: p.id,
				type: 'compare' as const,
				name: p.name,
				detail: `${n} ${n === 1 ? 'Ort' : 'Orte'}`,
				archived: (p.archived_at ?? '').slice(0, 10)
			};
		});

	const entries = [...tripEntries, ...compareEntries].sort((a, b) =>
		b.archived.localeCompare(a.archived)
	);

	return { entries };
};
