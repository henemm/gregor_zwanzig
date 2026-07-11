import { fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types.js';
// Dynamischer statt statischer Import: der `node --test`-Loader
// (test-lib-hooks.mjs) mappt `$lib/server/*.js`-Spezifizierer aktuell nicht
// auf die tatsächliche `.ts`-Datei zurück (pre-existing gap, reproduzierbar
// auch mit dem unveränderten reset-password/+page.server.ts). Ein statischer
// Top-Level-Import würde daher JEDEN Test crashen, der nur `load` importiert.
// Laufzeitverhalten in SvelteKit/Vite ist mit dynamischem Import identisch.

export const load: PageServerLoad = async ({ url }) => {
	return {
		user: url.searchParams.get('user') ?? '',
		token: url.searchParams.get('token') ?? '',
	};
};

export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const user = data.get('user')?.toString() ?? '';
		const token = data.get('token')?.toString() ?? '';

		if (!user || !token) {
			return fail(400, { error: 'Ungültiger Bestätigungslink.', user, token });
		}

		const { apiBase: API } = await import('$lib/server/apiBase.js');
		const clientIP = request.headers.get('x-real-ip') ?? '';
		const resp = await fetch(`${API()}/api/auth/verify-email`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ user, token }),
		});

		if (!resp.ok) {
			const body = await resp.json().catch(() => ({}));
			const msg =
				body.error === 'token expired'
					? 'Der Bestätigungslink ist abgelaufen. Bitte ändere deine Adresse erneut, um einen neuen Link zu erhalten.'
					: 'Der Bestätigungslink ist ungültig oder wurde bereits verwendet.';
			return fail(400, { error: msg, user, token });
		}

		return { success: true };
	},
} satisfies Actions;
