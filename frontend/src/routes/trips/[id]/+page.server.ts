import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: PageServerLoad = async ({ params, cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = {};
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const res = await fetch(`${API()}/api/trips/${params.id}`, { headers });
	if (res.status === 404) {
		throw error(404, `Trip '${params.id}' nicht gefunden`);
	}
	if (!res.ok) {
		throw error(res.status, 'Fehler beim Laden des Trips');
	}

	const trip = await res.json();
	return { trip };
};
