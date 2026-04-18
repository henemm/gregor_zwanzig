import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Location, Subscription } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [locsRes, subsRes] = await Promise.all([
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null)
	]);
	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];
	const subscriptions: Subscription[] = subsRes?.ok ? await subsRes.json() : [];

	return {
		locations: Array.isArray(locations) ? locations : [],
		subscriptions: Array.isArray(subscriptions) ? subscriptions : []
	};
};
