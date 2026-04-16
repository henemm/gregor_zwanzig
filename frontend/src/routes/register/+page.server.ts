import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';
		const confirmPassword = data.get('confirmPassword')?.toString() ?? '';

		if (password !== confirmPassword) {
			return fail(400, { error: 'Passwörter stimmen nicht überein', username });
		}

		const resp = await fetch(`${API()}/api/auth/register`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, password }),
		});

		if (resp.ok) {
			redirect(302, '/login?registered=1');
		}

		if (resp.status === 409) {
			return fail(409, { error: 'Benutzername bereits vergeben', username });
		}
		if (resp.status === 400) {
			return fail(400, {
				error: 'Benutzername (3–50 Zeichen) und Passwort (mind. 8 Zeichen) erforderlich',
				username,
			});
		}
		return fail(500, { error: 'Registrierung fehlgeschlagen', username });
	},
} satisfies Actions;
