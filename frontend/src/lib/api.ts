import type { ApiError, Stage } from './types.js';
import {
	discardEtag,
	enqueueTripWrite,
	etagVersion,
	extractTripId,
	getKnownEtag,
	setKnownEtag,
	setKnownEtagIfUnchanged
} from './etagRegistry.ts';

/**
 * Issue #1395 S3: Header feldweise zusammenfuehren. `extra` wurde bisher per
 * Spread NACH `headers` gemergt — wer `If-Match` ueber `extra.headers`
 * ergaenzte, loeschte damit den `Content-Type` und der Server verschluckte sich
 * am Rumpf.
 */
function headerFields(init?: HeadersInit): Record<string, string> {
	if (!init) return {};
	if (Array.isArray(init)) return Object.fromEntries(init);
	if (typeof (init as Headers).forEach === 'function') {
		const out: Record<string, string> = {};
		(init as Headers).forEach((value, key) => {
			out[key] = value;
		});
		return out;
	}
	return { ...(init as Record<string, string>) };
}

async function send<T>(
	method: string,
	path: string,
	tripId: string | null,
	/** true = dieser Vorgang laeuft durch die Warteschlange (serialisierter PUT). */
	serializedWrite: boolean,
	body?: unknown,
	extra?: RequestInit
): Promise<T> {
	// Issue #1395 S3: den Stand ERST HIER nachschlagen — innerhalb der
	// Warteschlange, also zu dem Zeitpunkt, zu dem die Anfrage tatsaechlich
	// losgeht. Vor dem Einreihen gelesen, haetten zwei kurz hintereinander
	// ausgeloeste Schreibvorgaenge derselben Tour beide den alten Wert
	// eingefroren und der zweite scheiterte mit 412, obwohl er gewartet hat.
	const ifMatch = serializedWrite && tripId ? getKnownEtag(tripId) : undefined;
	// Stand der Registry beim Losschicken — Grundlage dafuer, einen verspaetet
	// eintreffenden Stempel als Rueckschritt zu erkennen (F001).
	const versionAtStart = tripId ? etagVersion(tripId) : 0;
	const opts: RequestInit = {
		method,
		...extra,
		headers: {
			'Content-Type': 'application/json',
			...headerFields(extra?.headers),
			...(ifMatch ? { 'If-Match': ifMatch } : {})
		}
	};
	if (body !== undefined) {
		opts.body = JSON.stringify(body);
	}
	const res = await fetch(path, opts);
	if (!res.ok) {
		// Issue #1006 — Sitzung abgelaufen (24h-TTL): zentral behandeln statt die
		// rohe {"error":"unauthorized"}-Meldung an Aufrufer durchzureichen.
		if (res.status === 401 && typeof window !== 'undefined') {
			const redirectTarget = window.location.pathname + window.location.search;
			window.location.href = `/login?expired=1&redirect=${encodeURIComponent(redirectTarget)}`;
			throw new Error('Sitzung abgelaufen — bitte neu anmelden.');
		}
		// Issue #1395 S3: der gemerkte Stand ist nachweislich veraltet und die
		// 412-Antwort traegt keinen neuen. Einmal melden, dann nicht mehr im Weg
		// stehen — der naechste Versuch laeuft ohne Vorbedingung durch.
		if (res.status === 412 && tripId) discardEtag(tripId);
		const err: ApiError = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
		// `status` kommt ZUSAETZLICH dazu; `error`/`detail` bleiben unveraendert,
		// damit extractMessage() weiterhin die deutsche Servermeldung findet.
		const enriched: ApiError = { ...err, status: res.status };
		throw enriched;
	}
	// Issue #1395 S3: neuen Stempel uebernehmen — bei GET wie bei PUT, und noch
	// INNERHALB der Warteschlange, damit der naechste Wartende ihn vorfindet.
	//
	// Bedingungslos darf das nur ein serialisierter Schreibvorgang: er ist der
	// letzte, der die Datei angefasst hat, und kein anderer Schreibvorgang
	// derselben Tour lief neben ihm. Jeder Vorgang AUSSERHALB der Warteschlange
	// (Lesevorgang, Entlade-Flush) traegt dagegen den Stand von SEINEM
	// Anfragezeitpunkt — kommt er verspaetet an, waere sein Stempel ein
	// Rueckschritt und der naechste Schreibvorgang bekaeme 412, obwohl niemand
	// sonst etwas geaendert hat (F001).
	if (tripId) {
		const etag = res.headers.get('ETag');
		if (etag) {
			if (serializedWrite) setKnownEtag(tripId, etag);
			else setKnownEtagIfUnchanged(tripId, etag, versionAtStart);
		}
	}
	if (res.status === 204) return undefined as T;
	return res.json();
}

async function request<T>(method: string, path: string, body?: unknown, extra?: RequestInit): Promise<T> {
	const tripId = extractTripId(path);
	// `{ keepalive: true }` setzt im gesamten Repo ausschliesslich der
	// willUnload-Zweig beim Verlassen der Seite. Dieser Vorgang hat nur ein sehr
	// kurzes Zeitfenster: er darf weder hinter einem laufenden Schreibvorgang
	// warten (er ginge womoeglich nie los) noch an einem unsichtbaren 412
	// scheitern (der Nutzer sieht die Ablehnung nie, die Seite ist schon weg).
	const isUnloadFlush = extra?.keepalive === true;
	const serializedWrite = method === 'PUT' && tripId !== null && !isUnloadFlush;
	const run = () => send<T>(method, path, tripId, serializedWrite, body, extra);
	return serializedWrite ? enqueueTripWrite(tripId as string, run) : run();
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
	put: <T>(path: string, body: unknown, extra?: RequestInit) => request<T>('PUT', path, body, extra),
	patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
	del: (path: string) => request<void>('DELETE', path)
};

/**
 * Issue #1395 S4: laedt eine Tour ausschliesslich, um den bestehenden
 * ETag-Seiteneffekt von `send()` auszuloesen. Der Trip-Datensatz wird bewusst
 * NICHT zurueckgegeben — sonst entstuende die Versuchung, ihn dem sichtbaren
 * Seitenzustand zuzuweisen und ungespeicherte Aenderungen anderer Tabs zu
 * ueberschreiben.
 */
export async function refreshTripEtag(tripId: string): Promise<void> {
	await api.get(`/api/trips/${tripId}`);
}

export async function uploadGpx(
	file: File,
	stageDate: string,
	startHour: number
): Promise<Stage> {
	// Python FastAPI endpoint reads stage_date / start_hour from query params
	// (see api/routers/gpx.py); the file goes via multipart body.
	const form = new FormData();
	form.append('file', file);

	const params = new URLSearchParams();
	if (stageDate) params.set('stage_date', stageDate);
	params.set('start_hour', String(startHour));

	const res = await fetch(`/api/gpx/parse?${params.toString()}`, {
		method: 'POST',
		body: form
	});
	if (!res.ok) {
		const detail = await res.text();
		throw new Error(`GPX parse failed: ${detail}`);
	}
	return res.json() as Promise<Stage>;
}
