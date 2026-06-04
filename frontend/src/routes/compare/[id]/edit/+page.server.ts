import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import type { ComparePreset, Location } from '$lib/types.js';

// Issue #582 — Compare-Edit-Route: auf ComparePreset umgestellt (war: Subscription).
// Fix: /api/compare/presets/{id} statt /api/subscriptions/{id}

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies, params }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [presetRes, locsRes, profileRes] = await Promise.all([
		fetch(`${API()}/api/compare/presets/${params.id}`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/auth/profile`, { headers }).catch(() => null)
	]);

	if (!presetRes?.ok) {
		error(presetRes?.status === 404 ? 404 : 500, 'Orts-Vergleich nicht gefunden');
	}

	const preset: ComparePreset = await presetRes.json();
	const rawLocs = locsRes?.ok ? await locsRes.json() : [];
	const locations: Location[] = Array.isArray(rawLocs) ? rawLocs : [];
	const profile = profileRes?.ok ? await profileRes.json() : null;

	return { preset, locations, profile };
};
