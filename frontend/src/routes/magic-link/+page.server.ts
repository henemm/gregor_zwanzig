import { fail } from '@sveltejs/kit';
import type { Actions } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { trFor } from '$lib/i18n/index.js';


export const actions = {
	default: async ({ request, locals }) => {
		const data = await request.formData();
		const email = data.get('email')?.toString() ?? '';

		if (!email) {
			return fail(400, { error: trFor(locals.lang, 'auth.magic.fehler_email_pflicht'), email });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		// Backend liefert immer 200 — Fehler still absorbieren, kein User-Enum.
		await fetch(`${API()}/api/auth/magic-link`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ email })
		}).catch(() => {});

		return { sent: true, email };
	}
} satisfies Actions;
