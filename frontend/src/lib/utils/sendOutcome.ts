// Issue #2124 — geteiltes Versand-Ergebnis- und Laufzustands-Modul fuer ALLE
// manuellen Versand-Ausloeser (Trip UND Ortsvergleich). Reine Logik, per
// `node --test` pruefbar. Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md §4.
//
// Kein AbortController / kein Client-Timeout: der Versand darf bis zur
// nginx-Grenze (330 s) laufen.

export type SendOutcomeKind = 'ok' | 'already_running' | 'unclear' | 'rejected' | 'failed';

export type SendResponseInput =
	| { status: number; detail?: string | null }
	| { networkError: true };

export const SEND_UNCLEAR_MESSAGE = 'Ergebnis unklar — Versand kann noch laufen, nicht erneut senden';
export const SEND_ALREADY_RUNNING_MESSAGE = 'Versand läuft bereits';
export const SEND_FAILED_MESSAGE = 'Versand fehlgeschlagen — Serverfehler, bitte später erneut versuchen.';
export const SEND_REJECTED_FALLBACK = 'Versand fehlgeschlagen — bitte später erneut versuchen.';

export function classifySendResponse(input: SendResponseInput): { kind: SendOutcomeKind; message: string } {
	if ('networkError' in input) return { kind: 'unclear', message: SEND_UNCLEAR_MESSAGE };
	const { status } = input;
	if (status >= 200 && status < 300) return { kind: 'ok', message: '' };
	if (status === 409) return { kind: 'already_running', message: SEND_ALREADY_RUNNING_MESSAGE };
	if (status === 502 || status === 503 || status === 504) {
		return { kind: 'unclear', message: SEND_UNCLEAR_MESSAGE };
	}
	if (status >= 400 && status < 500) {
		const detail = typeof input.detail === 'string' && input.detail ? input.detail : SEND_REJECTED_FALLBACK;
		return { kind: 'rejected', message: detail };
	}
	return { kind: 'failed', message: SEND_FAILED_MESSAGE };
}

/** Liest `detail` bzw. `error` aus einem JSON-Fehlerkoerper (best effort). */
export async function readErrorDetail(res: Response): Promise<string | null> {
	try {
		const body = (await res.json()) as { detail?: unknown; error?: unknown };
		if (typeof body?.detail === 'string' && body.detail) return body.detail;
		if (typeof body?.error === 'string' && body.error) return body.error;
	} catch {
		/* kein JSON-Body */
	}
	return null;
}

/** Klassifiziert eine fetch-Antwort (liest bei Nicht-2xx den Fehlertext). */
export async function classifyResponse(res: Response): Promise<{ kind: SendOutcomeKind; message: string }> {
	if (res.ok) return classifySendResponse({ status: res.status });
	return classifySendResponse({ status: res.status, detail: await readErrorDetail(res) });
}

// ---------------------------------------------------------------------------
// Laufzustand je Schluessel (`trip:<id>` / `compare:<id>`), modulweit.
// ---------------------------------------------------------------------------

const running = new Set<string>();

/** false, wenn fuer `key` schon ein Versand laeuft; sonst true und Lauf markiert. */
export function beginSend(key: string): boolean {
	if (running.has(key)) return false;
	running.add(key);
	return true;
}

export function endSend(key: string): void {
	running.delete(key);
}

export function isSending(key: string): boolean {
	return running.has(key);
}

// ---------------------------------------------------------------------------
// Gemeinsamer Ablauf fuer ALLE Ausloeser: Laufzustand + fetch + Klassifikation.
// ---------------------------------------------------------------------------

export const tripSendKey = (tripId: string): string => `trip:${tripId}`;
export const compareSendKey = (presetId: string): string => `compare:${presetId}`;

export type SendRunResult = { kind: SendOutcomeKind; message: string; skipped: boolean };

/**
 * Fuehrt `send` genau einmal je Schluessel gleichzeitig aus. Laeuft schon ein
 * Versand fuer `key`, geht KEIN Request ab (skipped=true, already_running).
 * `endSend` immer in finally; Netzfehler -> unclear.
 */
export async function runSend(key: string, send: () => Promise<Response>): Promise<SendRunResult> {
	if (!beginSend(key)) {
		return { kind: 'already_running', message: SEND_ALREADY_RUNNING_MESSAGE, skipped: true };
	}
	try {
		const res = await send();
		const o = await classifyResponse(res);
		if (o.kind === 'failed' || o.kind === 'rejected') {
			console.error(`Versand ${key} fehlgeschlagen: HTTP ${res.status}`);
		}
		return { ...o, skipped: false };
	} catch (e) {
		console.error(e);
		return { ...classifySendResponse({ networkError: true }), skipped: false };
	} finally {
		endSend(key);
	}
}

/** Trip-Briefing manuell senden (Trip-Detail, Trip-Liste). */
export function sendTripBriefing(
	tripId: string,
	reportType: 'morning' | 'evening',
	fetchFn: typeof fetch = fetch
): Promise<SendRunResult> {
	return runSend(tripSendKey(tripId), () =>
		fetchFn(`/api/trips/${encodeURIComponent(tripId)}/send?report_type=${reportType}`, { method: 'POST' })
	);
}

/** Ortsvergleich-Briefing manuell senden (Hub, Liste, Tabs). */
export function sendComparePreset(presetId: string, fetchFn: typeof fetch = fetch): Promise<SendRunResult> {
	return runSend(compareSendKey(presetId), () =>
		fetchFn(`/api/compare/presets/${encodeURIComponent(presetId)}/send`, { method: 'POST' })
	);
}
