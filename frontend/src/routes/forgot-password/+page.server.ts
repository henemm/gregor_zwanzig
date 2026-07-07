import { fail } from '@sveltejs/kit';
import type { Actions } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';

		if (!username) {
			return fail(400, { error: 'Username required', username });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		await fetch(`${API()}/api/auth/forgot-password`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ username }),
		});

		// Always show success (no user enumeration)
		return { success: true, username };
	},
} satisfies Actions;
