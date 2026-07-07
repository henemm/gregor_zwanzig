import type { PageServerLoad } from './$types.js';
import type { Trip } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';


// Issue #412 — Trip-Wizard Step 4 Kanal-Karte: Profil (mail_to/signal_phone/
// telegram_chat_id) fail-soft laden, damit Step4 die Kontaktdaten je Kanal
// zeigen kann. Bei Fehler bleibt `profile` null (Karte zeigt dann alle Kanaele
// als "in Einstellungen hinterlegen").
// Issue #559 — `?from=`-Parameter: archivierten Trip als Vorlage laden.
export const load: PageServerLoad = async ({ url, cookies }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const profileRes = await fetch(`${API()}/api/auth/profile`, {
		headers,
		signal: AbortSignal.timeout(5000)
	}).catch(() => null);
	const profile = profileRes?.ok ? await profileRes.json() : null;

	const fromId = url.searchParams.get('from');
	let templateTrip: Trip | null = null;
	if (fromId) {
		const tripRes = await fetch(`${API()}/api/trips/${fromId}`, {
			headers,
			signal: AbortSignal.timeout(5000)
		}).catch(() => null);
		templateTrip = tripRes?.ok ? await tripRes.json() : null;
	}

	return { profile, templateTrip };
};
