import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';

export const load: PageServerLoad = async ({ params }) => {
	throw redirect(301, `/trips/${params.id}?tab=stages`);
};
