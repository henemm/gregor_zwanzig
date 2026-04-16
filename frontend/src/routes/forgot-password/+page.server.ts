import { fail } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

export const actions = {
	default: async ({ request }) => {
		const data = await request.formData();
		const username = data.get('username')?.toString() ?? '';

		if (!username) {
			return fail(400, { error: 'Username required', username });
		}

		await fetch(`${API()}/api/auth/forgot-password`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username }),
		});

		// Always show success (no user enumeration)
		return { success: true, username };
	},
} satisfies Actions;
