import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { trFor } from '$lib/i18n/index.js';


export const load: PageServerLoad = async ({ url }) => {
	return {
		user: url.searchParams.get('user') ?? '',
		token: url.searchParams.get('token') ?? '',
	};
};

export const actions = {
	default: async ({ request, locals }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';
		const token = data.get('token')?.toString() ?? '';
		const newPassword = data.get('new_password')?.toString() ?? '';

		if (!username || !token || !newPassword) {
			return fail(400, { error: trFor(locals.lang, 'auth.reset.fehler_pflichtfelder'), username, token });
		}

		if (newPassword.length < 8) {
			return fail(400, { error: trFor(locals.lang, 'auth.reset.fehler_passwort_kurz'), username, token });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		const resp = await fetch(`${API()}/api/auth/reset-password`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ username, token, new_password: newPassword }),
		});

		if (!resp.ok) {
			const body = await resp.json().catch(() => ({}));
			const msg =
				body.code === 'token_expired'
					? trFor(locals.lang, 'auth.reset.fehler_token_abgelaufen')
					: trFor(locals.lang, 'auth.reset.fehler_token_ungueltig');
			return fail(400, { error: msg, username, token });
		}

		return { success: true };
	},
} satisfies Actions;
