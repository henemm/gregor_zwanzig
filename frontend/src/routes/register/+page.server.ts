import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions, PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: PageServerLoad = async () => {
	return {
		googleEnabled: !!env.GZ_GOOGLE_CLIENT_ID,
	};
};

export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const email = data.get('email')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';
		const confirmPassword = data.get('confirmPassword')?.toString() ?? '';

		if (password !== confirmPassword) {
			return fail(400, { error: 'Passwörter stimmen nicht überein', username, email });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		const resp = await fetch(`${API()}/api/auth/register`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ username, password, email }),
		});

		if (resp.ok) {
			redirect(302, '/login?registered=1');
		}

		if (resp.status === 429) {
			return fail(429, { error: 'Zu viele Versuche — bitte in einigen Minuten erneut versuchen.', username, email });
		}
		if (resp.status === 409) {
			return fail(409, { error: 'Benutzername bereits vergeben', username, email });
		}
		if (resp.status === 400) {
			// Issue #1226: Backend liefert bei ungültiger E-Mail den eigenen
			// Fehlercode "invalid_email" — gezielt auf eine verständliche Meldung
			// mappen, sonst generische Pflichtfeld-Meldung.
			const body = await resp.json().catch(() => ({}) as { error?: string });
			if (body?.error === 'invalid_email') {
				return fail(400, { error: 'Bitte eine gültige E-Mail-Adresse angeben', username, email });
			}
			return fail(400, {
				error: 'Benutzername (3–50 Zeichen), E-Mail und Passwort (mind. 8 Zeichen) erforderlich',
				username,
				email,
			});
		}
		return fail(500, { error: 'Registrierung fehlgeschlagen', username, email });
	},
} satisfies Actions;
