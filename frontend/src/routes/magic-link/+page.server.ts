import { fail } from '@sveltejs/kit';
import type { Actions } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const email = data.get('email')?.toString() ?? '';

		if (!email) {
			return fail(400, { error: 'E-Mail-Adresse erforderlich', email });
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
