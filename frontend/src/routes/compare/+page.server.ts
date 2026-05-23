import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Location, Subscription, Group } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [locsRes, subsRes, groupsRes] = await Promise.all([
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null),
		fetch(`${API()}/api/groups`, { headers }).catch(() => null)
	]);
	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];
	const subscriptions: Subscription[] = subsRes?.ok ? await subsRes.json() : [];
	const groups: Group[] = groupsRes?.ok ? await groupsRes.json() : [];

	return {
		locations: Array.isArray(locations) ? locations : [],
		subscriptions: Array.isArray(subscriptions) ? subscriptions : [],
		groups: Array.isArray(groups) ? groups : []
	};
};
