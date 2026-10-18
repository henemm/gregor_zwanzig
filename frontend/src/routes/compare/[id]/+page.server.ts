// Issue #491 — Compare-Preset Detail-Seite: SSR-Loader.
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import type { ComparePreset, Location } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { loadProfile } from '$lib/server/profileLoader.js';


export const load: PageServerLoad = async ({ cookies, params }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [presetRes, locsRes, profile] = await Promise.all([
		fetch(`${API()}/api/compare/presets/${params.id}`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		// Issue #2278: Profil fuer den Sende-Dialog (fail-soft, null ohne Session).
		loadProfile(cookies)
	]);

	if (!presetRes?.ok) {
		error(presetRes?.status === 404 ? 404 : 500, 'Orts-Vergleich nicht gefunden');
	}

	const preset: ComparePreset = await presetRes.json();
	const rawLocs = locsRes?.ok ? await locsRes.json() : [];
	const allLocations: Location[] = Array.isArray(rawLocs) ? rawLocs : [];
	const location_ids: string[] = preset.location_ids ?? [];
	const locations = allLocations.filter((l) => location_ids.includes(l.id));

	return { preset, locations, profile, etag: presetRes.headers.get('ETag') ?? undefined };
};
