// Issue #189 — Pure-Functions für URL-Bau, Default-Report-Type, Char-Count-Status.
// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
// Tests: ./__tests__/previewHelpers.test.ts

export type ReportType = 'morning' | 'evening';
export type CharCountStatus = 'ok' | 'warn' | 'over';

// Baut URL zum Go-Proxy. Session-Cookie geht automatisch mit, user_id wird
// serverseitig injiziert — Frontend hängt keinen user_id-Query an.
// Issue #483: optionales `demo` hängt `demo=1` an die URL (Fixture-Daten).
export function buildPreviewUrl(
	channel: 'email' | 'sms' | 'telegram',
	tripId: string,
	type: ReportType,
	date?: string,
	demo?: boolean
): string {
	const qs = new URLSearchParams({ type });
	if (date) qs.set('date', date);
	if (demo) qs.set('demo', '1');
	return `/api/preview/${encodeURIComponent(tripId)}/${channel}?${qs.toString()}`;
}

// Vor 14 Uhr lokal → Morgen-Briefing, ab 14 Uhr → Abend-Briefing.
export function defaultReportType(now: Date = new Date()): ReportType {
	return now.getHours() < 14 ? 'morning' : 'evening';
}

// n > limit → over · n > limit-16 → warn (letzte ~10 % Puffer) · sonst ok.
export function charCountStatus(n: number, limit = 160): CharCountStatus {
	if (n > limit) return 'over';
	if (n > limit - 16) return 'warn';
	return 'ok';
}

// Issue #421 — Vorschau-Fehler verständlich auf Deutsch.
export const PREVIEW_ERROR_GENERIC =
	'Vorschau konnte nicht geladen werden. Bitte später erneut versuchen.';
export const PREVIEW_ERROR_NO_WAYPOINTS =
	'Diese Etappe hat noch keine Wegpunkte. Bitte im Wegpunkt-Editor ' +
	'mindestens einen Start- und Zielpunkt festlegen.';

// Übersetzt einen HTTP-Fehler der Vorschau-Endpoints in verständliches Deutsch.
// Schlüsselt auf den inhaltlichen Detail-Text (detail enthält "waypoint"),
// nicht auf den numerischen Code — resilient gegen Status-Drift im Backend.
// Parst body defensiv als JSON; wirft niemals.
export function friendlyPreviewError(status: number, body: string): string {
	let detail = '';
	try {
		const parsed = JSON.parse(body);
		if (parsed && typeof parsed.detail === 'string') detail = parsed.detail;
	} catch {
		detail = body ?? '';
	}
	if (/waypoint/i.test(detail)) return PREVIEW_ERROR_NO_WAYPOINTS;
	return PREVIEW_ERROR_GENERIC;
}
