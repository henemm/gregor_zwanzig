import { fail } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions, PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const load: PageServerLoad = async ({ url }) => {
	return {
		user: url.searchParams.get('user') ?? '',
		token: url.searchParams.get('token') ?? '',
	};
};

export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const token = data.get('token')?.toString() ?? '';
		const newPassword = data.get('new_password')?.toString() ?? '';

		if (!username || !token || !newPassword) {
			return fail(400, { error: 'Alle Felder sind erforderlich', username, token });
		}

		if (newPassword.length < 8) {
			return fail(400, { error: 'Passwort muss mindestens 8 Zeichen haben', username, token });
		}

		const resp = await fetch(`${API()}/api/auth/reset-password`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, token, new_password: newPassword }),
		});

		if (!resp.ok) {
			const body = await resp.json().catch(() => ({}));
			const msg = body.error === 'token expired' ? 'Token abgelaufen' : 'Ungültiger Token';
			return fail(400, { error: msg, username, token });
		}

		return { success: true };
	},
} satisfies Actions;
