import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ params, url }) => {
	const tab = url.searchParams.get('tab');
	const target = tab ? `/trips/${params.id}?tab=${tab}` : `/trips/${params.id}`;
	throw redirect(307, target);
};
