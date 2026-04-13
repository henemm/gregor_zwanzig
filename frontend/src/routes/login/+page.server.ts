import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { signSession } from '$lib/auth.js';
import type { Actions } from './$types.js';

export const actions = {
	default: async ({ request, cookies }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';

		const expectedUser = env.GZ_AUTH_USER ?? 'admin';
		const expectedPass = env.GZ_AUTH_PASS ?? '';

		if (!expectedPass) {
			return fail(500, { error: 'GZ_AUTH_PASS not configured on server' });
		}

		if (username !== expectedUser || password !== expectedPass) {
			return fail(401, { error: 'Invalid credentials', username });
		}

		const secret = env.GZ_SESSION_SECRET ?? 'dev-secret-change-me';
		const userId = 'default';
		const sessionValue = signSession(userId, secret);

		cookies.set('gz_session', sessionValue, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			secure: env.NODE_ENV === 'production',
			maxAge: 86400
		});

		redirect(302, '/');
	}
} satisfies Actions;
