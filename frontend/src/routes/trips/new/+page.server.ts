import { env } from '$env/dynamic/private';
import type { PageServerLoad } from './$types.js';

const API = () => env.GZ_API_BASE ?? 'http://localhost:8090';

// Issue #412 — Trip-Wizard Step 4 Kanal-Karte: Profil (mail_to/signal_phone/
// telegram_chat_id) fail-soft laden, damit Step4 die Kontaktdaten je Kanal
// zeigen kann. Bei Fehler bleibt `profile` null (Karte zeigt dann alle Kanaele
// als "in Einstellungen hinterlegen").
export const load: PageServerLoad = async ({ cookies }) => {
	const session = cookies.get('gz_session');
	if (!session) return { profile: null };
	const profile = await fetch(`${API()}/api/auth/profile`, {
		headers: { Cookie: `gz_session=${session}` }
	})
		.then((r) => (r.ok ? r.json() : null))
		.catch(() => null);
	return { profile };
};
