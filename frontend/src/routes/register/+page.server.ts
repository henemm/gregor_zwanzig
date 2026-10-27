import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions, PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export type InviteState =
	| { status: 'none' }
	| { status: 'valid'; token: string; tier: string }
	| { status: 'invalid' }
	// Pruefung nicht moeglich (429/5xx/Netz): Token bleibt im Formular, die
	// Einladung wird beim Absenden geprueft (kein stilles Free-Konto).
	| { status: 'unknown'; token: string };

// Issue #2519: Vorab-Check des Einladungslinks (?invite=...) serverseitig per
// POST (Token im Body, nie in der URL/Access-Log). Nur 404 heisst "ungueltig".
async function checkInvite(token: string, clientIP: string): Promise<InviteState> {
	try {
		const resp = await fetch(`${API()}/api/auth/invite/check`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ token }),
		});
		if (resp.ok) {
			const body = await resp.json().catch(() => ({}) as { tier?: string });
			return { status: 'valid', token, tier: String(body?.tier ?? '') };
		}
		if (resp.status === 404) return { status: 'invalid' };
	} catch {
		// Netzfehler: unbekannt, nicht ungueltig.
	}
	return { status: 'unknown', token };
}

export const load: PageServerLoad = async ({ url, request }) => {
	const token = url.searchParams.get('invite');
	const invite: InviteState = token
		? await checkInvite(token, request.headers.get('x-real-ip') ?? '')
		: { status: 'none' };
	return {
		googleEnabled: !!env.GZ_GOOGLE_CLIENT_ID,
		invite,
	};
};

export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const email = data.get('email')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';
		const confirmPassword = data.get('confirmPassword')?.toString() ?? '';
		const invite = data.get('invite')?.toString() ?? '';

		if (password !== confirmPassword) {
			return fail(400, { error: 'Passwörter stimmen nicht überein', username, email });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		const resp = await fetch(`${API()}/api/auth/register`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ username, password, email, ...(invite && { invite }) }),
		});

		if (resp.ok) {
			redirect(302, '/login?registered=1');
		}

		if (resp.status === 429) {
			return fail(429, { error: 'Zu viele Versuche — bitte in einigen Minuten erneut versuchen.', username, email });
		}
		if (resp.status === 409) {
			// Issue #2147 Scheibe B1 (AC-15): "email_taken" ist ein Adress-, kein
			// Kennungskonflikt — eigene, verständliche Meldung statt der
			// sachlich falschen "Benutzername bereits vergeben".
			const body = await resp.json().catch(() => ({}) as { error?: string });
			if (body?.error === 'email_taken') {
				return fail(409, {
					error:
						"Diese E-Mail-Adresse gehört bereits zu einem Konto. Melde dich an – bei Bedarf über 'Passwort vergessen' oder den Anmeldelink per E-Mail.",
					username,
					email,
				});
			}
			return fail(409, { error: 'Benutzername bereits vergeben', username, email });
		}
		if (resp.status === 400) {
			// Issue #1226: Backend liefert bei ungültiger E-Mail den eigenen
			// Fehlercode "invalid_email" — gezielt auf eine verständliche Meldung
			// mappen, sonst generische Pflichtfeld-Meldung.
			const body = await resp.json().catch(() => ({}) as { error?: string });
			if (body?.error === 'invite_invalid') {
				return fail(400, {
					error: 'Die Einladung ist nicht (mehr) gültig. Lade die Seite ohne Einladungslink neu, um dich normal zu registrieren.',
					username,
					email,
				});
			}
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
