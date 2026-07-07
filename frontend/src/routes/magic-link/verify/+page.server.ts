import { fail, redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import type { Actions, PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


export const load: PageServerLoad = async ({ url }) => {
	return { email: url.searchParams.get('email') ?? '' };
};

export const actions = {
	default: async ({ request, cookies }) => {
		const data = await request.formData();
		const email = data.get('email')?.toString() ?? '';
		const code = data.get('code')?.toString() ?? '';

		if (!email || !code) {
			return fail(400, { error: 'E-Mail und Code erforderlich', email });
		}

		const clientIP = request.headers.get('x-real-ip') ?? '';
		const resp = await fetch(`${API()}/api/auth/magic-link/verify`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', ...(clientIP && { 'X-Real-IP': clientIP }) },
			body: JSON.stringify({ email, code })
		});

		if (!resp.ok) {
			const body = await resp.json().catch(() => ({}));
			const msg =
				body.error === 'max_attempts_exceeded'
					? 'Zu viele Fehlversuche. Bitte fordere einen neuen Code an.'
					: 'Ungültiger oder abgelaufener Code.';
			return fail(400, { error: msg, email });
		}

		// Cookie aus dem Backend-Response extrahieren (analog zu /login).
		const setCookie = resp.headers.get('set-cookie');
		if (setCookie) {
			const match = setCookie.match(/gz_session=([^;]+)/);
			if (match) {
				cookies.set('gz_session', match[1], {
					path: '/',
					httpOnly: true,
					sameSite: 'lax',
					secure: env.NODE_ENV === 'production',
					maxAge: 86400
				});
			}
		}

		redirect(302, '/');
	}
} satisfies Actions;
