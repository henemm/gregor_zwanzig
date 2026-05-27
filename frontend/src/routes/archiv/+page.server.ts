import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Trip } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [tripsRes, statsRes] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers, signal: AbortSignal.timeout(5000) }).catch(
			() => null
		),
		fetch(`${API()}/api/archive/stats`, { headers, signal: AbortSignal.timeout(5000) }).catch(
			() => null
		)
	]);

	const all: Trip[] = tripsRes?.ok ? await tripsRes.json() : [];
	const trips = (Array.isArray(all) ? all : []).filter((t) => t.archived_at != null);

	const statsJson = statsRes?.ok ? await statsRes.json() : null;
	const archiveStats: { briefings: Record<string, number>; alerts: Record<string, number> } = {
		briefings: statsJson?.briefings ?? {},
		alerts: statsJson?.alerts ?? {}
	};

	return { trips, archiveStats };
};
