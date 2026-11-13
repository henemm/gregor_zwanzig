import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ params, url }) => {
	const tab = url.searchParams.get('tab');
	// #2961: Kennung und Reiter kodiert in die Zieladresse uebernehmen.
	const pfad = `/trips/${encodeURIComponent(params.id)}`;
	const target = tab ? `${pfad}?tab=${encodeURIComponent(tab)}` : pfad;
	throw redirect(307, target);
};
