import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [schedRes, configRes, healthRes] = await Promise.all([
		fetch(`${API()}/api/scheduler/status`, { headers }).catch(() => null),
		fetch(`${API()}/api/config`, { headers }).catch(() => null),
		fetch(`${API()}/api/health`, { headers }).catch(() => null)
	]);

	return {
		scheduler: schedRes?.ok ? await schedRes.json() : null,
		config: configRes?.ok ? await configRes.json() : null,
		health: healthRes?.ok ? await healthRes.json() : null
	};
};
