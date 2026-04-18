import { env } from '$env/dynamic/private';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ params, cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = {};
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const res = await fetch(`${API()}/api/trips/${params.id}`, { headers });
	if (!res.ok) throw error(404, 'Trip nicht gefunden');

	const trip = await res.json();
	return { trip };
};
