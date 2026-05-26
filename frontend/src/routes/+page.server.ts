import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Trip, Subscription, StagesWeatherResponse } from '$lib/types.js';
import { activeOrNextTrip } from '$lib/utils/tripStatus.js';

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

	// Issue #386 — Wetter NUR für die Hero-Tour (aktiv/nächste) holen, fail-soft.
	// Bei Fehler/leer rendert der Hero ohne Wetter (AC-3), trips/subscriptions
	// bleiben unverändert.
	const hero = activeOrNextTrip(trips);
	let heroWeather: StagesWeatherResponse | null = null;
	if (hero?.id) {
		try {
			const wRes = await fetch(`${API()}/api/trips/${hero.id}/stages/weather`, { headers });
			heroWeather = wRes.ok ? await wRes.json() : null;
		} catch {
			heroWeather = null;
		}
	}

	return { trips, subscriptions, heroWeather };
};
