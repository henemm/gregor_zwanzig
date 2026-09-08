import { createHash } from 'node:crypto';
import { redirect, type Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { verifySession } from '$lib/auth.js';
import { assertSessionSecretConfigured } from '$lib/sessionSecretGate.js';

assertSessionSecretConfigured(env.GZ_SESSION_SECRET, env.GZ_TEST_FIXTURE_DIR);

/**
 * Issue #2131 — Mandantenkennung fuer den Gerätespeicher (ADR-0003).
 *
 * Der Service Worker kennt den angemeldeten Nutzer nicht; `page.data` sieht er
 * nicht, und das Sitzungs-Cookie selbst zu deuten waere eine zweite
 * Wahrheitsquelle. Darum haengt die Kennung an der Antwort, die dieselbe
 * signierte Sitzung ohnehin schon autorisiert hat. Gehasht, weil im
 * Gerätespeicher kein Klarname stehen muss.
 */
const MANDANT_HEADER = 'x-gz-mandant';

function mandantenKennung(userId: string): string {
	return createHash('sha256').update(userId).digest('hex').slice(0, 16);
}

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
	// Issue #2131: an JEDE authentifizierte Nicht-`/api/`-Antwort — also an die
	// Seitenantwort UND an die `__data.json`-Antwort der Client-Navigation
	// (SvelteKit setzt `url.pathname` dabei auf den Seitenpfad). `/api/` bleibt
	// aussen vor: diese Antworten legt der Worker grundsaetzlich nicht ab.
	if (!event.url.pathname.startsWith('/api/')) {
		response.headers.set(MANDANT_HEADER, mandantenKennung(result.userId));
	}
	return response;
};
