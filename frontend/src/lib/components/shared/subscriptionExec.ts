// Issue #2278 (Epic #2345 P3) — Ausfuehrungs-Adapter fuer die Aktionen aus
// `subscriptionActions`: je Art der bestehende Endpunkt, KEIN Backend-Eingriff.
// Spec: docs/specs/modules/feat_2278_aktionsmodell.md (Implementation Details 3, AC-7)
//
// Compare-Pausieren: Read-Modify-Write — frischer GET, danach PUT mit NUR
// { schedule, previous_schedule } (#2375, kein Voll-Spread eines veralteten Stands).

import type { ComparePreset } from '../../types.js';
import { statusZielNutzlast } from '../compare/compareHubPersistenz.ts';
import { readErrorDetail, sendBriefing, type SendRunResult } from '../../utils/sendOutcome.ts';
import type { SubscriptionKind } from './subscriptionTabs.ts';

const JSON_HEADER = { 'Content-Type': 'application/json' };
const enc = encodeURIComponent;

const basis = (kind: SubscriptionKind, id: string): string =>
	kind === 'trip' ? `/api/trips/${enc(id)}` : `/api/compare/presets/${enc(id)}`;

/** Fehler eines Schreibwegs mit HTTP-Status und Server-Detail (fuer nutzerverstaendliche Meldungen). */
export class SubscriptionExecError extends Error {
	status: number;
	detail: string | undefined;
	constructor(message: string, status: number, detail?: string) {
		super(message);
		this.status = status;
		this.detail = detail;
	}
}

async function pruefe(res: Response, was: string): Promise<Response> {
	if (!res.ok) {
		const detail = (await readErrorDetail(res)) ?? undefined;
		throw new SubscriptionExecError(`${was} fehlgeschlagen: HTTP ${res.status}`, res.status, detail);
	}
	return res;
}

async function antwort(res: Response): Promise<unknown> {
	try {
		return await res.json();
	} catch {
		return undefined;
	}
}

async function patchState(
	kind: SubscriptionKind,
	id: string,
	body: Record<string, boolean>,
	fetchFn: typeof fetch
): Promise<unknown> {
	const res = await fetchFn(`${basis(kind, id)}/state`, {
		method: 'PATCH',
		headers: JSON_HEADER,
		body: JSON.stringify(body)
	});
	return antwort(await pruefe(res, 'Statuswechsel'));
}

/** Pausieren/Fortsetzen auf den ZIELZUSTAND `paused` (kein Umschalten): Trip nur `{paused}`, Ortsvergleich nur `{schedule, previous_schedule}` aus frischem Stand. Liefert die Serverantwort. */
export async function setPaused(
	kind: SubscriptionKind,
	id: string,
	paused: boolean,
	fetchFn: typeof fetch = fetch
): Promise<unknown> {
	if (kind === 'trip') return patchState(kind, id, { paused }, fetchFn);
	// Zielzustand statt Umschalten (F009): ist der frische Stand schon im Zielzustand, bleibt er es.
	const url = basis(kind, id);
	const frisch = (await (await pruefe(await fetchFn(url), 'Laden')).json()) as ComparePreset;
	const body = statusZielNutzlast(frisch, paused ? 'manual' : 'aktiv', 'daily');
	const res = await fetchFn(url, { method: 'PUT', headers: JSON_HEADER, body: JSON.stringify(body) });
	return antwort(await pruefe(res, 'Pausieren'));
}

export function setArchived(
	kind: SubscriptionKind,
	id: string,
	archived: boolean,
	fetchFn: typeof fetch = fetch
): Promise<unknown> {
	return patchState(kind, id, { archived }, fetchFn);
}

export async function deleteSubscription(
	kind: SubscriptionKind,
	id: string,
	fetchFn: typeof fetch = fetch
): Promise<void> {
	await pruefe(await fetchFn(basis(kind, id), { method: 'DELETE' }), 'Löschen');
}

/** Senden mit In-Flight-Schutz (#2124) ueber POST /api/briefings/{id}/send (#2280); `reportType` gilt nur beim Trip (Default morning). */
export function sendSubscription(
	kind: SubscriptionKind,
	id: string,
	opts: { reportType?: 'morning' | 'evening' } = {},
	fetchFn: typeof fetch = fetch
): Promise<SendRunResult> {
	// #2280: Frontend-Wort `trip` heisst im Endpunkt `route`.
	return kind === 'trip'
		? sendBriefing('route', id, { reportType: opts.reportType ?? 'morning' }, fetchFn)
		: sendBriefing('vergleich', id, {}, fetchFn);
}
