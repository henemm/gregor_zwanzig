import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [tripsRes, locsRes, healthRes] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/health`).catch(() => null)
	]);

	const trips = tripsRes?.ok ? await tripsRes.json() : [];
	const locations = locsRes?.ok ? await locsRes.json() : [];
	const health = healthRes?.ok
		? await healthRes.json()
		: { status: 'degraded', version: 'unknown', python_core: 'unavailable' };

	return {
		tripCount: Array.isArray(trips) ? trips.length : 0,
		locationCount: Array.isArray(locations) ? locations.length : 0,
		health
	};
};
