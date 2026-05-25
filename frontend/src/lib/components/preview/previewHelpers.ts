// Issue #189 — Pure-Functions für URL-Bau, Default-Report-Type, Char-Count-Status.
// Spec: docs/specs/modules/issue_189_preview_tab_integration.md
// Tests: ./__tests__/previewHelpers.test.ts

export type ReportType = 'morning' | 'evening';
export type CharCountStatus = 'ok' | 'warn' | 'over';

// Baut URL zum Go-Proxy. Session-Cookie geht automatisch mit, user_id wird
// serverseitig injiziert — Frontend hängt keinen user_id-Query an.
export function buildPreviewUrl(
	channel: 'email' | 'sms' | 'signal' | 'telegram',
	tripId: string,
	type: ReportType,
	date?: string
): string {
	const qs = new URLSearchParams({ type });
	if (date) qs.set('date', date);
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
