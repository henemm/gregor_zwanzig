import type { PageServerLoad } from './$types.js';
import type { Location } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';

// Issue #440 — Compare-Wizard Create-Modus. Locations-Library fuer Step 2.
// Issue #443 — Profil parallel laden (fail-soft) fuer Step 5 (Kanal-Hints).


export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [locsRes, profileRes] = await Promise.all([
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/auth/profile`, { headers }).catch(() => null)
	]);

	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];
	const profile = profileRes?.ok ? await profileRes.json() : null;

	return {
		locations: Array.isArray(locations) ? locations : [],
		profile
	};
};
