import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const actions = {
	default: async ({ request, cookies }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';

		if (!username || !password) {
			return fail(400, { error: 'Username and password required', username });
		}

		const resp = await fetch(`${API()}/api/auth/login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, password }),
		});

		if (!resp.ok) {
			return fail(401, { error: 'Invalid credentials', username });
		}

		// Extract session cookie from Go response and set it for the browser
		const setCookie = resp.headers.get('set-cookie');
		if (setCookie) {
			const match = setCookie.match(/gz_session=([^;]+)/);
			if (match) {
				cookies.set('gz_session', match[1], {
					path: '/',
					httpOnly: true,
					sameSite: 'lax',
					secure: env.NODE_ENV === 'production',
					maxAge: 86400,
				});
			}
		}

		redirect(302, '/');
	},
} satisfies Actions;
