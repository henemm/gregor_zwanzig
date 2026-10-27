import type { PageServerLoad } from './$types.js';
import type { Trip, ComparePreset, CockpitStatus } from '$lib/types.js';
import { apiBase as API } from '$lib/server/apiBase.js';
import type { NextBriefing } from '$lib/components/shared/versand-tab/nextBriefingText';

type NextBriefings = { trips: Record<string, NextBriefing>; compare: Record<string, NextBriefing> };


export const load: PageServerLoad = async ({ cookies, locals }) => {
	// Issue #2520 — Ausgeloggte sehen die oeffentliche Startseite: keine
	// Go-API-Aufrufe, keine Nutzerdaten.
	if (!locals.userId) {
		return {
			oeffentlich: true,
			trips: [] as Trip[],
			presets: [] as ComparePreset[],
			cockpitStatus: null as CockpitStatus | null
		};
	}
	const session = cookies.get('gz_session');
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	if (session) headers['Cookie'] = `gz_session=${session}`;

	const [tripsRes, presetsRes, cockpitRes, nextRes] = await Promise.all([
		fetch(`${API()}/api/trips`, { headers, signal: AbortSignal.timeout(5000) }).catch(() => null),
		// Issue #492 — Home-Sektion zeigt aktive Orts-Vergleiche aus dem
		// ComparePreset-Endpoint (#458). Ersetzt den vorherigen Subscription-Fetch.
		fetch(`${API()}/api/compare/presets`, { headers, signal: AbortSignal.timeout(5000) }).catch(() => null),
		// Issue #393 — Cockpit-Status (Versandstatus + Alarm-Historie) aus Log-Files.
		// Read-only, kein Wetter-Endpoint; fail-soft mit 3000ms-Timeout.
		fetch(`${API()}/api/cockpit/status`, { headers, signal: AbortSignal.timeout(3000) }).catch(() => null),
		// Issue #1969 (AC-23): nächster Versand je Trip/Vergleich aus EINER
		// Backend-Ableitung — fail-soft (Anzeige „—"), nie eine eigene Rechnung.
		fetch(`${API()}/api/next-briefings`, { headers, signal: AbortSignal.timeout(3000) }).catch(() => null)
	]);

	const tripsRaw: Trip[] = tripsRes?.ok ? await tripsRes.json() : [];
	const presetsRaw: ComparePreset[] = presetsRes?.ok ? await presetsRes.json() : [];
	const trips: Trip[] = Array.isArray(tripsRaw) ? tripsRaw : [];
	const presets: ComparePreset[] = Array.isArray(presetsRaw) ? presetsRaw : [];

	const cockpitStatus: CockpitStatus | null = cockpitRes?.ok
		? await cockpitRes.json().catch(() => null)
		: null;

	// Issue #395 — KEIN Live-Wetter-Abruf im Home-Loader. Die Website zeigt kein
	// live geladenes Wetter (Wetter kommt via Briefings); der frühere
	// Wetter-Endpoint-Fetch ließ `/` bis ~57 s hängen (Regression aus #386).
	// Der Hero rendert sofort aus Trip-/Etappen-Daten; Wetter/Risk bleibt dormant.
	// trips/presets behalten defensive AbortSignal.timeout(5000) (fail-soft).
	const nextRaw: unknown = nextRes?.ok ? await nextRes.json().catch(() => null) : null;
	const nextBriefings: NextBriefings | null =
		nextRaw && typeof nextRaw === 'object' && !Array.isArray(nextRaw)
			? {
					trips: ((nextRaw as Partial<NextBriefings>).trips ?? {}) as NextBriefings['trips'],
					compare: ((nextRaw as Partial<NextBriefings>).compare ?? {}) as NextBriefings['compare']
				}
			: null;

	return { oeffentlich: false, trips, presets, cockpitStatus, nextBriefings };
};
