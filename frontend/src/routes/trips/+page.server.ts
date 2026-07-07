import type { PageServerLoad } from './$types.js';
import type { Trip } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const res = await fetch(`${API()}/api/trips`, { headers }).catch(() => null);
	const trips: Trip[] = res?.ok ? await res.json() : [];

	return { trips: Array.isArray(trips) ? trips : [] };
};
