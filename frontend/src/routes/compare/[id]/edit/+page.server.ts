import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import type { Location, Subscription } from '$lib/types.js';

// Issue #440 — Compare-Wizard Edit-Modus: Subscription + Locations-Library.
// Issue #443 — Profil parallel laden (fail-soft) fuer Step 5 (Kanal-Hints).

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies, params }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [subRes, locsRes, profileRes] = await Promise.all([
		fetch(`${API()}/api/subscriptions/${params.id}`, { headers }).catch(() => null),
		fetch(`${API()}/api/locations`, { headers }).catch(() => null),
		fetch(`${API()}/api/auth/profile`, { headers }).catch(() => null)
	]);

	if (!subRes?.ok) error(404, 'Vergleich nicht gefunden');

	const subscription: Subscription = await subRes.json();
	const locations: Location[] = locsRes?.ok ? await locsRes.json() : [];
	const profile = profileRes?.ok ? await profileRes.json() : null;

	return {
		subscription,
		locations: Array.isArray(locations) ? locations : [],
		profile
	};
};
