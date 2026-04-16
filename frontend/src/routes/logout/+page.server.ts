import { redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

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
