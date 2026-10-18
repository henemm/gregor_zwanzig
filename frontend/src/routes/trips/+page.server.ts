import type { PageServerLoad } from './$types.js';
import type { Trip } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { loadProfile } from '$lib/server/profileLoader.js';


export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	// Issue #2278: Profil fuer den Sende-Dialog (fail-soft, null ohne Session).
	const [res, profile] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers }).catch(() => null),
		loadProfile(cookies)
	]);
	const trips: Trip[] = res?.ok ? await res.json() : [];

	// Issue #2278 AC-11: archivierte Trips erscheinen nicht in der Liste (wie bei Ortsvergleichen).
	return { trips: Array.isArray(trips) ? trips.filter((t) => t.archived_at == null) : [], profile };
};
