import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';
import type { Trip, Stage, SchedulerStatus } from '$lib/types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [tripsRes, schedulerRes] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers }).catch(() => null),
		fetch(`${API()}/api/scheduler/status`, { headers }).catch(() => null)
	]);

	const trips: Trip[] = tripsRes?.ok ? await tripsRes.json() : [];
	const schedulerStatus: SchedulerStatus | null = schedulerRes?.ok
		? await schedulerRes.json()
		: null;

	// Aktiver Trip: Etappe mit heutigem Datum
	const today = new Date().toISOString().slice(0, 10);
	const tripsArr = Array.isArray(trips) ? trips : [];
	const activeTrip = tripsArr.find((t: Trip) =>
		t.stages?.some((s: Stage) => s.date === today)
	);
	const todayStage = activeTrip?.stages?.find((s: Stage) => s.date === today);
	const firstWaypoint = todayStage?.waypoints?.[0];
	const forecastCoords = firstWaypoint
		? { lat: firstWaypoint.lat, lon: firstWaypoint.lon }
		: null;

	return {
		trips: tripsArr,
		schedulerStatus,
		forecastCoords
	};
};
