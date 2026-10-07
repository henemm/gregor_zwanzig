// Issue #2155 S1 — „Briefing senden" der Trip-Liste sendet genau den gewählten
// Trip über POST /api/trips/<id>/send (statt des Sammel-Triggers
// /api/scheduler/trip-reports, der jetzt nur Admins offensteht).
// Issue #2124: Laufzustand + Fehlerklassifikation kommen aus dem geteilten
// Modul `$lib/utils/sendOutcome` (Schlüssel trip:<id>, gleich wie Trip-Detail).

import { sendTripBriefing } from '$lib/utils/sendOutcome';

export type ReportType = 'morning' | 'evening';

export function reportTypeForHour(hour: 7 | 18): ReportType {
	return hour === 7 ? 'morning' : 'evening';
}

export async function sendTripTestReport(
	tripId: string,
	hour: 7 | 18,
	fetchFn: typeof fetch = fetch
): Promise<{ result: string | null; error: string | null }> {
	const reportType = reportTypeForHour(hour);
	const o = await sendTripBriefing(tripId, reportType, fetchFn);
	if (o.kind !== 'ok') return { result: null, error: o.message };
	const label = reportType === 'morning' ? 'Morning' : 'Evening';
	return { result: `Test-Report (${label}) für diesen Trip wurde ausgelöst.`, error: null };
}
