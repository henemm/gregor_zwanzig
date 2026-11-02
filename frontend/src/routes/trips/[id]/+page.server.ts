import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import { loadProfile } from '$lib/server/profileLoader.js';
import { trFor } from '$lib/i18n/index.js';


export const load: PageServerLoad = async ({ params, cookies, locals }) => {
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = {};
	if (session) headers['Cookie'] = `gz_session=${session}`;

	// Feature #1435 Etappe E3a: der Wetter-Metriken-Katalog wird PARALLEL zum
	// Trip geladen, fail-soft (`.catch(() => null)`). Ein Katalog-Ausfall darf
	// die Seite nicht zum Kippen bringen — nur der neue Übersichts-Block
	// verliert seine Datengrundlage und zeigt den Fallback-Hinweis. Beide
	// Fetches werden vor dem `return` awaitet, damit kein Ladefenster
	// entsteht (Fehlerklasse #1320, AC-5).
	const [res, metricsCatalog, profile] = await Promise.all([
		fetch(`${API()}/api/trips/${params.id}`, { headers }),
		fetch(`${API()}/api/metrics`, { headers })
			.then((r) => (r.ok ? r.json() : null))
			.catch(() => null),
		// Issue #2278: Profil fuer den Sende-Dialog (fail-soft, null ohne Session).
		loadProfile(cookies)
	]);
	if (res.status === 404) {
		throw error(404, trFor(locals.lang, 'trip.hub.nicht_gefunden', { id: params.id }));
	}
	if (!res.ok) {
		throw error(res.status, trFor(locals.lang, 'trip.hub.laden_fehler'));
	}

	// Issue #1395 S3: den Stempel der ausgelieferten Fassung mitgeben, damit der
	// erste Schreibvorgang auf dieser Seite ihn als `If-Match` fuehren kann.
	// Fehlt der Header, bleibt `etag` undefined und alles verhaelt sich wie
	// vor dieser Scheibe (S2-Rollout-Politik: fehlender Header = angenommen).
	const etag = res.headers.get('ETag') ?? undefined;
	const trip = await res.json();
	return { trip, etag, metricsCatalog, profile };
};
