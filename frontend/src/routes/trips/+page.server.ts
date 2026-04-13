import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Trip } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const res = await fetch(`${API()}/api/trips`, { headers }).catch(() => null);
	const trips: Trip[] = res?.ok ? await res.json() : [];

	return { trips: Array.isArray(trips) ? trips : [] };
};
