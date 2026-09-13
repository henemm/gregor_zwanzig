import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { safeRedirectPath } from '$lib/utils/safeRedirect.js';
import { mitAngebotMarker } from '$lib/passkeyAngebot.js';
import { SESSION_MAX_AGE_SECONDS } from '$lib/auth.js';
import type { Actions, PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: PageServerLoad = async () => {
	return {
		googleEnabled: !!env.GZ_GOOGLE_CLIENT_ID,
	};
};

// Issue #2271: `default` und benannte Actions schliessen sich in SvelteKit aus.
// Der bisherige Login-Weg heisst deshalb jetzt `login` — jedes Formular, das
// hierher postet, MUSS `action="?/login"` tragen (auch Browser-`fetch` aus
// Tests: `/login?/login`).
export const actions = {
	login: async ({ request, cookies, url }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';

		if (!username || !password) {
			return fail(400, { error: 'Username and password required', username, resent: false });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		const resp = await fetch(`${API()}/api/auth/login`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ username, password }),
		});

		if (resp.status === 429) {
			return fail(429, { error: 'Rate limit exceeded', username, resent: false });
		}
		// Issue #2271 AC-12: VOR dem pauschalen `!resp.ok`-Zweig. Wessen Passwort
		// stimmt und nur die Adresse noch nicht bestaetigt hat, saehe sonst
		// "Ungueltige Anmeldedaten" — eine Meldung, die ihn in die falsche
		// Richtung schickt (Passwort zuruecksetzen statt Postfach oeffnen).
		if (resp.status === 403) {
			const grund = await resp.json().catch(() => null);
			if (grund?.error === 'email_not_verified') {
				return fail(403, { error: 'email_not_verified', username, resent: false });
			}
		}
		if (!resp.ok) {
			return fail(401, { error: 'Invalid credentials', username, resent: false });
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
					maxAge: SESSION_MAX_AGE_SECONDS,
				});
			}
		}

		// Issue #1006 — nach 401-Redirect zurück zur Ausgangsseite (nur relative Pfade).
		// Issue #2248 — der Anmelde-Marker kommt NACH safeRedirectPath dazu: sonst
		// prüfte die Open-Redirect-Sperre einen Wert, der so nie ausgeliefert wird.
		redirect(302, mitAngebotMarker(safeRedirectPath(url.searchParams.get('redirect'))));
	},

	// Issue #2271 AC-13 — erneuter Versand der Bestätigungsmail. Der Endpunkt
	// antwortet aus Datenschutzgründen IMMER 200 (er verrät nicht, ob es das
	// Konto gibt); die Seite quittiert deshalb ebenfalls immer bestätigend.
	// `error` reist mit zurück, damit der Hinweis aus AC-12 stehen bleibt —
	// SvelteKit ersetzt `form` vollständig durch diesen Rückgabewert, der
	// Erklärungstext verschwände sonst genau dann, wenn er noch gebraucht wird.
	resend: async ({ request }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';

		const clientIP = request.headers.get('x-real-ip') ?? '';
		await fetch(`${API()}/api/auth/verify-email/resend`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ username }),
		}).catch(() => {
			// Auch ein Netzfehler zur Go-API bleibt für den Nutzer eine Bestätigung:
			// eine Fehlermeldung an dieser Stelle böte ihm keine andere Handlung an
			// als dieselbe Schaltfläche noch einmal zu drücken.
		});

		return { error: 'email_not_verified', username, resent: true };
	},
} satisfies Actions;
