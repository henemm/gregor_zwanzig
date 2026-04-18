import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [schedRes, healthRes, profileRes, tripsRes, subsRes, locsRes] = await Promise.all([
		fetch(`${API()}/api/scheduler/status`, { headers }).catch(() => null),
		fetch(`${API()}/api/health`, { headers }).catch(() => null),
		fetch(`${API()}/api/auth/profile`, { headers }).catch(() => null),
		fetch(`${API()}/api/trips`, { headers }).catch(() => null),
		fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
	]);

	const trips = tripsRes?.ok ? await tripsRes.json() : [];
	const subscriptions = subsRes?.ok ? await subsRes.json() : [];
	const locations = locsRes?.ok ? await locsRes.json() : [];

	return {
		scheduler: schedRes?.ok ? await schedRes.json() : null,
		health: healthRes?.ok ? await healthRes.json() : null,
		profile: profileRes?.ok ? await profileRes.json() : null,
		trips: Array.isArray(trips) ? trips : [],
		subscriptions: Array.isArray(subscriptions) ? subscriptions : [],
		locations: Array.isArray(locations) ? locations : [],
	};
};
