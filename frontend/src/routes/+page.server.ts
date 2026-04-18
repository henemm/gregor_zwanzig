import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [tripsRes, subsRes] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers }).catch(() => null),
		fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null)
	]);

	const trips = tripsRes?.ok ? await tripsRes.json() : [];
	const subscriptions = subsRes?.ok ? await subsRes.json() : [];

	return {
		trips: Array.isArray(trips) ? trips : [],
		subscriptions: Array.isArray(subscriptions) ? subscriptions : []
	};
};
