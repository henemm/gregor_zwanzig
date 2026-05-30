import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Location, Subscription, Group, ComparePreset } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [locsRes, subsRes, groupsRes, presetsRes] = await Promise.all([
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null),
		fetch(`${API()}/api/groups`, { headers }).catch(() => null),
		fetch(`${API()}/api/compare/presets`, { headers }).catch(() => null)
	]);
	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];
	const subscriptions: Subscription[] = subsRes?.ok ? await subsRes.json() : [];
	const groups: Group[] = groupsRes?.ok ? await groupsRes.json() : [];
	const rawPresets = presetsRes?.ok ? await presetsRes.json() : [];
	const presets: ComparePreset[] = Array.isArray(rawPresets)
		? rawPresets
		: (rawPresets?.presets ?? []);

	return {
		locations: Array.isArray(locations) ? locations : [],
		subscriptions: Array.isArray(subscriptions) ? subscriptions : [],
		groups: Array.isArray(groups) ? groups : [],
		presets
	};
};
