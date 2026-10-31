// Issue #2648 (i18n S3) — Besucher-Umschalter (Konventionen Abschnitt 1):
// Formfeld `lang` (de/en) -> Cookie `gz_lang`, danach 303 zurueck auf den
// Referer (nur gleicher Ursprung, sonst `/`). Schreibt keine Nutzerdaten.
import { redirect } from '@sveltejs/kit';
import { safeRedirectPath } from '$lib/utils/safeRedirect.js';
import type { RequestHandler } from './$types';

const EIN_JAHR = 31536000;

function rueckweg(referer: string | null, origin: string): string {
	try {
		const r = new URL(referer ?? '');
		if (r.origin === origin) return safeRedirectPath(r.pathname + r.search);
	} catch {
		// kein oder unlesbarer Referer
	}
	return '/';
}

export const POST: RequestHandler = async ({ request, cookies, url }) => {
	const lang = (await request.formData()).get('lang')?.toString();
	if (lang === 'de' || lang === 'en') {
		cookies.set('gz_lang', lang, {
			path: '/',
			maxAge: EIN_JAHR,
			sameSite: 'lax',
			secure: url.protocol === 'https:',
			httpOnly: false
		});
	}
	redirect(303, rueckweg(request.headers.get('referer'), url.origin));
};
