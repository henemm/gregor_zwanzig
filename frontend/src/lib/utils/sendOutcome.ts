// Issue #2124 — geteiltes Versand-Ergebnis- und Laufzustands-Modul fuer ALLE
// manuellen Versand-Ausloeser (Trip UND Ortsvergleich). Reine Logik, per
// `node --test` pruefbar. Spec: docs/specs/modules/fix_2124_versand_nginx_timeout.md §4.
//
// Kein AbortController / kein Client-Timeout: der Versand darf bis zur
// nginx-Grenze (330 s) laufen.

import { tr } from '../i18n/index.ts';

export type SendOutcomeKind = 'ok' | 'already_running' | 'unclear' | 'rejected' | 'failed';

export type SendResponseInput =
	| { status: number; detail?: string | null }
	| { networkError: true };

// #2660: Meldungen werden bei JEDEM Aufruf in der aktuellen Sprache gebaut (keine
// Modul-Konstanten, die die Sprache beim Import einfroeren).

export function classifySendResponse(input: SendResponseInput): { kind: SendOutcomeKind; message: string } {
	if ('networkError' in input) return { kind: 'unclear', message: tr('fehler.versand.unklar') };
	const { status } = input;
	if (status >= 200 && status < 300) return { kind: 'ok', message: '' };
	if (status === 409) return { kind: 'already_running', message: tr('fehler.versand.laeuft_bereits') };
	if (status === 502 || status === 503 || status === 504) {
		return { kind: 'unclear', message: tr('fehler.versand.unklar') };
	}
	if (status >= 400 && status < 500) {
		const detail =
			typeof input.detail === 'string' && input.detail ? input.detail : tr('fehler.versand.abgelehnt');
		return { kind: 'rejected', message: detail };
	}
	return { kind: 'failed', message: tr('fehler.versand.fehlgeschlagen') };
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

export type SendRunResult = {
	kind: SendOutcomeKind;
	message: string;
	skipped: boolean;
	/** #2216: IDs der Orte, die beim Ortsvergleich-Versand nicht mehr aufloesbar waren. */
	fehlendeOrte?: string[];
};

/**
 * Fuehrt `send` genau einmal je Schluessel gleichzeitig aus. Laeuft schon ein
 * Versand fuer `key`, geht KEIN Request ab (skipped=true, already_running).
 * `endSend` immer in finally; Netzfehler -> unclear.
 */
export async function runSend(key: string, send: () => Promise<Response>): Promise<SendRunResult> {
	if (!beginSend(key)) {
		return { kind: 'already_running', message: tr('fehler.versand.laeuft_bereits'), skipped: true };
	}
	try {
		const res = await send();
		const o = await classifyResponse(res);
		if (o.kind === 'failed' || o.kind === 'rejected') {
			console.error(`Versand ${key} fehlgeschlagen: HTTP ${res.status}`); // i18n-log
		}
		return { ...o, skipped: false };
	} catch (e) {
		console.error(e);
		return { ...classifySendResponse({ networkError: true }), skipped: false };
	} finally {
		endSend(key);
	}
}

/** Art des Briefings im Endpunkt-Vokabular (#2280): Trip = `route`, Ortsvergleich = `vergleich`. */
export type SendBriefingKind = 'route' | 'vergleich';

/** EINZIGE Stelle, die die Send-URL baut (#2280 AC-15). `reportType` gilt nur fuer `route`. */
export function briefingSendUrl(kind: SendBriefingKind, id: string, reportType?: 'morning' | 'evening'): string {
	const rt = kind === 'route' && reportType ? `&report_type=${reportType}` : '';
	return `/api/briefings/${encodeURIComponent(id)}/send?kind=${kind}${rt}`;
}

/**
 * Briefing manuell senden (Trip und Ortsvergleich, #2280). Laufzustand je
 * `trip:<id>` / `compare:<id>`; `fehlende_orte` (#2216) wird bei Erfolg gemeldet.
 */
export async function sendBriefing(
	kind: SendBriefingKind,
	id: string,
	opts: { reportType?: 'morning' | 'evening' } = {},
	fetchFn: typeof fetch = fetch
): Promise<SendRunResult> {
	let fehlende: string[] = [];
	const key = kind === 'route' ? tripSendKey(id) : compareSendKey(id);
	const r = await runSend(key, async () => {
		const res = await fetchFn(briefingSendUrl(kind, id, opts.reportType), { method: 'POST' });
		if (res.ok) {
			try {
				const body = (await res.clone().json()) as { fehlende_orte?: unknown };
				if (Array.isArray(body?.fehlende_orte)) fehlende = body.fehlende_orte.map(String);
			} catch {
				/* kein JSON-Body */
			}
		}
		return res;
	});
	if (r.kind === 'ok' && fehlende.length > 0) {
		return {
			...r,
			fehlendeOrte: fehlende,
			message: tr('fehler.versand.orte_fehlten', { anzahl: fehlende.length, orte: fehlende.join(', ') }),
		};
	}
	return r;
}
