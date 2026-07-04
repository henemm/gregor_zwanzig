import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { safeRedirectPath } from '$lib/utils/safeRedirect.js';
import type { Actions, PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async () => {
	return {
		googleEnabled: !!env.GZ_GOOGLE_CLIENT_ID,
	};
};

export const actions = {
	default: async ({ request, cookies, url }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';

		if (!username || !password) {
			return fail(400, { error: 'Username and password required', username });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		const resp = await fetch(`${API()}/api/auth/login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ username, password }),
		});

		if (resp.status === 429) {
			return fail(429, { error: 'Rate limit exceeded', username });
		}
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

		// Issue #1006 — nach 401-Redirect zurück zur Ausgangsseite (nur relative Pfade).
		redirect(302, safeRedirectPath(url.searchParams.get('redirect')));
	},
} satisfies Actions;
