import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Trip, Subscription } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [tripsRes, subsRes] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers }).catch(() => null),
		fetch(`${API()}/api/subscriptions`, { headers }).catch(() => null)
	]);

	const tripsRaw: Trip[] = tripsRes?.ok ? await tripsRes.json() : [];
	const subsRaw: Subscription[] = subsRes?.ok ? await subsRes.json() : [];
	const trips: Trip[] = Array.isArray(tripsRaw) ? tripsRaw : [];
	const subscriptions: Subscription[] = Array.isArray(subsRaw) ? subsRaw : [];

	// Issue #395 — KEIN Live-Wetter-Abruf im Home-Loader. Die Website zeigt kein
	// live geladenes Wetter (Wetter kommt via Briefings); der frühere
	// Wetter-Endpoint-Fetch ließ `/` bis ~57 s hängen (Regression aus #386).
	// Der Hero rendert sofort aus Trip-/Etappen-Daten; Wetter/Risk bleibt dormant.
	return { trips, subscriptions };
};
