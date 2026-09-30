import type { PageServerLoad } from './$types.js';
import type { ComparePreset, Location } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';

// Issue #440 — Compare-Wizard Create-Modus. Locations-Library fuer Step 2.
// Issue #443 — Profil parallel laden (fail-soft) fuer Step 5 (Kanal-Hints).


// Issue #2277 S2c — ?from=<id>: eigenen Vergleich als Vorlage laden (Session-Cookie,
// Nutzertrennung ueber die Go-API). Nicht-OK/Fehler/ungueltig => vorlage: null, nie Fehlerseite.
async function ladeVorlage(from: string | null, headers: Record<string, string>) {
	if (!from) return null;
	try {
		const res = await fetch(`${API()}/api/compare/presets/${encodeURIComponent(from)}`, { headers });
		if (!res.ok) return null;
		const preset = (await res.json()) as ComparePreset | null;
		return preset && Array.isArray(preset.location_ids) ? preset : null;
	} catch {
		return null;
	}
}

export const load: PageServerLoad = async ({ cookies, url }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [locsRes, profileRes, vorlage] = await Promise.all([
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/auth/profile`, { headers }).catch(() => null),
		ladeVorlage(url.searchParams.get('from'), headers)
	]);

	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];
	const profile = profileRes?.ok ? await profileRes.json() : null;

	return {
		locations: Array.isArray(locations) ? locations : [],
		profile,
		vorlage
	};
};
