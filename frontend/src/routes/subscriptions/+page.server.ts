import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Subscription, Location } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [subsRes, locsRes] = await Promise.all([
		fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null)
	]);

	const subscriptions: Subscription[] = subsRes?.ok ? await subsRes.json() : [];
	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];

	return {
		subscriptions: Array.isArray(subscriptions) ? subscriptions : [],
		locations: Array.isArray(locations) ? locations : []
	};
};
