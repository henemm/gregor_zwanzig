import { redirect, type Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { verifySession } from '$lib/auth.js';

export const handle: Handle = async ({ event, resolve }) => {
	if (event.url.pathname === '/login') {
		return resolve(event);
	}

	const secret = env.GZ_SESSION_SECRET ?? 'dev-secret-change-me';
	const session = event.cookies.get('gz_session');
	const result = session ? verifySession(session, secret) : null;

	if (!result) {
		redirect(302, '/login');
	}

	event.locals.userId = result.userId;
	return resolve(event);
};
