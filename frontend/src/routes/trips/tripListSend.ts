// Issue #2155 S1 — „Briefing senden" der Trip-Liste sendet genau den gewählten
// Trip über POST /api/trips/<id>/send (statt des Sammel-Triggers
// /api/scheduler/trip-reports, der jetzt nur Admins offensteht).
// Fehlertext-Behandlung wie trips/[id]/+page.svelte (handleTestBriefing).

export type ReportType = 'morning' | 'evening';

const ALLGEMEIN = 'Versand fehlgeschlagen — bitte später erneut versuchen.';
const SERVERFEHLER = 'Versand fehlgeschlagen — Serverfehler, bitte später erneut versuchen.';

export function reportTypeForHour(hour: 7 | 18): ReportType {
	return hour === 7 ? 'morning' : 'evening';
}

async function fehlertext(res: Response): Promise<string> {
	let body: { detail?: unknown; error?: unknown } | undefined;
	try {
		body = await res.json();
	} catch {
		/* kein JSON-Body */
	}
	if (res.status >= 500) {
		// Serverfehler: handlungsleitende Meldung, Rohtext nur ins Log.
		console.error(`Test-Report fehlgeschlagen: HTTP ${res.status}`, body?.detail);
		return SERVERFEHLER;
	}
	if (typeof body?.detail === 'string' && body.detail) return body.detail;
	if (typeof body?.error === 'string' && body.error) return body.error;
	return ALLGEMEIN;
}

export async function sendTripTestReport(
	tripId: string,
	hour: 7 | 18,
	fetchFn: typeof fetch = fetch
): Promise<{ result: string | null; error: string | null }> {
	const reportType = reportTypeForHour(hour);
	try {
		const res = await fetchFn(`/api/trips/${encodeURIComponent(tripId)}/send?report_type=${reportType}`, {
			method: 'POST'
		});
		if (!res.ok) return { result: null, error: await fehlertext(res) };
		const label = reportType === 'morning' ? 'Morning' : 'Evening';
		return { result: `Test-Report (${label}) für diesen Trip wurde ausgelöst.`, error: null };
	} catch (e) {
		console.error(e);
		return { result: null, error: ALLGEMEIN };
	}
}
