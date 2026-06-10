import { fail } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

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
