// Issue #491 — Compare-Preset Detail-Seite: SSR-Loader.
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import type { ComparePreset, Location } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { loadProfile } from '$lib/server/profileLoader.js';
import { kennungImPfad } from '$lib/server/apiPfad.js';
// Issue #2659 (i18n F10): Fehlermeldung in der Sprache des angemeldeten Nutzers (locals.lang).
import { trFor } from '$lib/i18n/index.js';


export const load: PageServerLoad = async ({ cookies, params, locals }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	// #2961: Kennung geprueft und kodiert in den Pfad zur Go-API; ungueltig => 404.
	const kennung = kennungImPfad(params.id);
	if (kennung === null) error(404, trFor(locals.lang, 'vergleich.hub.nicht_gefunden'));

	const [presetRes, locsRes, profile] = await Promise.all([
		fetch(`${API()}/api/compare/presets/${kennung}`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		// Issue #2278: Profil fuer den Sende-Dialog (fail-soft, null ohne Session).
		loadProfile(cookies)
	]);

	if (!presetRes?.ok) {
		error(presetRes?.status === 404 ? 404 : 500, trFor(locals.lang, 'vergleich.hub.nicht_gefunden'));
	}

	const preset: ComparePreset = await presetRes.json();
	const rawLocs = locsRes?.ok ? await locsRes.json() : [];
	const allLocations: Location[] = Array.isArray(rawLocs) ? rawLocs : [];
	const location_ids: string[] = preset.location_ids ?? [];
	const locations = allLocations.filter((l) => location_ids.includes(l.id));

	return { preset, locations, profile, etag: presetRes.headers.get('ETag') ?? undefined };
};
