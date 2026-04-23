import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

/** Fallback templates when /api/templates is not available (yet). */
const FALLBACK_TEMPLATES = [
	{ id: 'alpen-trekking', label: 'Alpen-Trekking', metrics: ['temperature','wind_chill','wind','gust','precipitation','thunder','cape','rain_probability','snowfall_limit','freezing_level','cloud_total','cloud_low','visibility','uv_index'] },
	{ id: 'wandern', label: 'Wandern', metrics: ['temperature','humidity','wind','gust','precipitation','rain_probability','cloud_total','sunshine','uv_index'] },
	{ id: 'skitouren', label: 'Skitouren', metrics: ['temperature','wind_chill','wind','gust','precipitation','fresh_snow','snow_depth','snowfall_limit','freezing_level','cloud_total','cloud_low','visibility'] },
	{ id: 'wintersport', label: 'Wintersport', metrics: ['temperature','wind_chill','wind','gust','precipitation','fresh_snow','snow_depth','cloud_total','sunshine','visibility'] },
	{ id: 'radtour', label: 'Radtour', metrics: ['temperature','wind','wind_direction','gust','precipitation','rain_probability','thunder','cape','cloud_total','sunshine','uv_index'] },
	{ id: 'wassersport', label: 'Wassersport', metrics: ['temperature','wind','gust','wind_direction','precipitation','rain_probability','thunder','cape','cloud_total','visibility'] },
	{ id: 'allgemein', label: 'Allgemein', metrics: ['temperature','wind','gust','precipitation','rain_probability','cloud_total','sunshine'] },
];

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const h = { headers: { Cookie: `gz_session=${session}` } };

	const [profile, scheduler, health, apiTemplates, trips, subscriptions, locations] =
		await Promise.all([
			fetch(`${API()}/api/auth/profile`, h).then(r => r.ok ? r.json() : null).catch(() => null),
			fetch(`${API()}/api/scheduler/status`, h).then(r => r.ok ? r.json() : null).catch(() => null),
			fetch(`${API()}/api/health`, h).then(r => r.ok ? r.json() : null).catch(() => null),
			fetch(`${API()}/api/templates`, h).then(r => r.ok ? r.json() : null).catch(() => null),
			fetch(`${API()}/api/trips`, h).then(r => r.ok ? r.json() : []).catch(() => []),
			fetch(`${API()}/api/subscriptions`, h).then(r => r.ok ? r.json() : []).catch(() => []),
			fetch(`${API()}/api/locations`, h).then(r => r.ok ? r.json() : []).catch(() => []),
		]);

	const templates = Array.isArray(apiTemplates) ? apiTemplates : FALLBACK_TEMPLATES;

	return { profile, scheduler, health, templates, trips, subscriptions, locations };
};
