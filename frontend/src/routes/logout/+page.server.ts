import { redirect } from '@sveltejs/kit';
import type { Actions } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const actions = {
	default: async ({ cookies }) => {
		const session = cookies.get('gz_session');
		if (session) {
			await fetch(`${API()}/api/auth/logout`, {
				method: 'POST',
				headers: { Cookie: `gz_session=${session}` },
			});
		}
		cookies.delete('gz_session', { path: '/' });
		redirect(302, '/login');
	},
} satisfies Actions;
