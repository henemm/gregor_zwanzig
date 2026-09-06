import { redirect, type Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { verifySession } from '$lib/auth.js';
import { assertSessionSecretConfigured } from '$lib/sessionSecretGate.js';

assertSessionSecretConfigured(env.GZ_SESSION_SECRET, env.GZ_TEST_FIXTURE_DIR);

export const handle: Handle = async ({ event, resolve }) => {
	const publicPaths = ['/login', '/register', '/logout', '/forgot-password', '/reset-password', '/verify-email', '/email-preview-dev', '/magic-link', '/magic-link/verify'];
	if (publicPaths.includes(event.url.pathname)) {
		const response = await resolve(event);
		const ct = response.headers.get('content-type') ?? '';
		if (ct.includes('text/html')) {
			response.headers.set('cache-control', 'no-cache');
		}
		return response;
	}

	// Der Fallback traegt nur noch den Fixture-/E2E-Pfad: dort laeuft auch die
	// Go-API mit ihrem envconfig-Default, beide Seiten muessen dasselbe Secret
	// benutzen. Ausserhalb davon hat der Top-Level-Gate den Prozess schon
	// beendet, bevor handle je aufgerufen wird.
	const secret = env.GZ_SESSION_SECRET ?? 'dev-secret-change-me';
	const session = event.cookies.get('gz_session');
	const result = session ? verifySession(session, secret) : null;

	if (!result) {
		redirect(302, '/login');
	}

	event.locals.userId = result.userId;
	const response = await resolve(event);
	const ct = response.headers.get('content-type') ?? '';
	if (ct.includes('text/html')) {
		response.headers.set('cache-control', 'no-cache');
	}
	return response;
};
