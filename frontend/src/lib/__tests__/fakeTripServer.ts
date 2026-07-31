// Issue #1395 S3 — Ersatz-Server fuer `globalThis.fetch`.
//
// KEIN Mock im verbotenen Sinn ("spiegelt die eigene Annahme zurueck"): bildet
// den S2-Server-Vertrag nach (docs/specs/modules/issue_1395_s2_etag_ifmatch.md)
// und ist der GEGENSPIELER der Tests. Fuehrt einen echten Fingerabdruck je Tour
// (aendert sich bei JEDEM erfolgreichen Schreibvorgang, S1/ADR-0036), prueft
// `If-Match` mit derselben Parser-Logik wie `internal/handler/etag.go` und
// antwortet mit echten `Response`/`Headers`/Statuscodes/JSON-Ruempfen. Ein Test
// kann hier real scheitern — genau das ist der Zweck.

export interface RequestRecord {
	method: string;
	path: string;
	ifMatch: string | null;
	contentType: string | null;
	keepalive: boolean;
	/** monotone Zeitmarke (performance.now) VOR der simulierten Server-Laufzeit */
	startedAt: number;
	/** monotone Zeitmarke NACH der simulierten Server-Laufzeit */
	finishedAt: number;
	status: number;
	body: unknown;
}

export interface FakeTripServer {
	/** Ersatz fuer `globalThis.fetch` */
	handler: (input: unknown, init?: RequestInit) => Promise<Response>;
	calls: RequestRecord[];
	/** aktueller ETag-Wert (inkl. Anfuehrungszeichen) einer Tour */
	etagOf(tripId: string): string;
	/** zuletzt erfolgreich geschriebener Rumpf einer Tour */
	storedBody(tripId: string): unknown;
	install(): void;
	restore(): void;
}

// Dieselbe Pfad-Definition wie der echte Server: Tour-Ressource, ihre
// Wetter-Konfiguration und (Issue #1395 S6) der Ortsvergleich-Preset tragen
// einen ETag. `id` liefert match[1] (Trip) oder match[2] (Compare-Preset).
const TRIP_PATH_RE =
	/^\/api\/(?:trips\/([^/?#]+)(?:\/weather-config)?|compare\/presets\/([^/?#]+))(?:[?#]|$)/;

/** Spiegelbild von `ifMatchAllows` in `internal/handler/etag.go` (S2). */
function ifMatchAllows(header: string, current: string): boolean {
	const h = header.trim();
	if (h === '' || h === '*') return true;
	const cur = current.replace(/^"/, '').replace(/"$/, '');
	return h.split(',').some((part) => part.trim().replace(/^"/, '').replace(/"$/, '') === cur);
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/**
 * Wortlaut der 412-Antwort — WOERTLICH aus `internal/handler/etag.go:26-28`
 * (`preconditionFailedDetail`), inklusive der dortigen ASCII-Umschreibung
 * ("geaendert"/"Aenderung"). Ein Pruefstand, der hier vom echten Server
 * abweicht, taeuscht genau die Uebereinstimmung vor, die er belegen soll.
 */
export const PRECONDITION_FAILED_DETAIL =
	'Der Stand wurde zwischenzeitlich an anderer Stelle geaendert. ' +
	'Bitte neu laden und die Aenderung erneut vornehmen.';

/** Laufzeit je Anfrage — fest oder abhaengig von Methode/Pfad. */
type Latency = number | ((method: string, path: string) => number);

export function createFakeTripServer(options: { latencyMs?: Latency } = {}): FakeTripServer {
	const latencyOf = (method: string, path: string): number => {
		const l = options.latencyMs ?? 0;
		return typeof l === 'function' ? l(method, path) : l;
	};
	const fingerprints = new Map<string, string>();
	const stored = new Map<string, unknown>();
	const calls: RequestRecord[] = [];
	let seq = 0;
	let originalFetch: typeof globalThis.fetch | undefined;

	function etagOf(tripId: string): string {
		let fp = fingerprints.get(tripId);
		if (fp === undefined) {
			seq += 1;
			fp = `fp-${seq}`;
			fingerprints.set(tripId, fp);
		}
		return `"${fp}"`;
	}

	function bump(tripId: string): string {
		seq += 1;
		const fp = `fp-${seq}`;
		fingerprints.set(tripId, fp);
		return `"${fp}"`;
	}

	const handler = async (input: unknown, init?: RequestInit): Promise<Response> => {
		const path = String(input);
		const method = (init?.method ?? 'GET').toUpperCase();
		const reqHeaders = new Headers((init?.headers ?? {}) as HeadersInit);
		const ifMatch = reqHeaders.get('If-Match');
		const match = TRIP_PATH_RE.exec(path);
		const tripId = match ? decodeURIComponent(match[1] ?? match[2]) : null;

		// Der Eintrag entsteht bei ANKUNFT, nicht beim Abschluss — wie ein echtes
		// Zugriffsprotokoll. Nur so kann ein Test feststellen, dass eine Anfrage
		// bereits unterwegs ist, waehrend eine zweite losgeschickt wird.
		const record: RequestRecord = {
			method,
			path,
			ifMatch,
			contentType: reqHeaders.get('Content-Type'),
			keepalive: init?.keepalive === true,
			startedAt: performance.now(),
			finishedAt: Number.NaN,
			status: 0,
			body: undefined
		};
		calls.push(record);

		// Die Anfrage wird BEI ANKUNFT behandelt (Fingerabdruck lesen, If-Match
		// pruefen, ggf. schreiben) — wie der echte Handler, der das alles unter
		// `LockBriefing` erledigt. Die Laufzeit liegt danach: sie bildet die
		// Uebertragung der Antwort ab, nicht die Bearbeitung. Nur so laesst sich
		// ein langsam zurueckkommender Lesevorgang nachstellen, dessen Stempel
		// beim Eintreffen bereits veraltet ist.
		const respHeaders = new Headers({ 'Content-Type': 'application/json' });
		let status = 200;
		let body: unknown;

		if (tripId === null) {
			// Nicht-Trip-/Nicht-Compare-Preset-Pfad (z. B. /api/locations/...,
			// /api/trips/{id}/state): kein ETag, keine Vorbedingung.
			body = { ok: true, path };
		} else if (method === 'GET') {
			respHeaders.set('ETag', etagOf(tripId));
			body = { id: tripId, ...(stored.get(tripId) as object | undefined) };
		} else if (method === 'PUT') {
			const current = etagOf(tripId);
			if (ifMatch !== null && !ifMatchAllows(ifMatch, current)) {
				status = 412;
				body = { error: 'precondition_failed', detail: PRECONDITION_FAILED_DETAIL };
				// KEIN ETag-Header — S2 AC-13.
			} else {
				let payload: unknown = undefined;
				if (typeof init?.body === 'string') {
					try {
						payload = JSON.parse(init.body);
					} catch {
						/* Rumpf war kein JSON */
					}
				}
				stored.set(tripId, payload);
				respHeaders.set('ETag', bump(tripId));
				body = { id: tripId, ...(payload as object | undefined) };
			}
		} else {
			// PATCH/DELETE auf die Tour-Ressource: veraendert die Datei (neuer
			// Fingerabdruck), liefert aber KEINEN ETag zurueck.
			bump(tripId);
			body = { id: tripId };
		}

		const latencyMs = latencyOf(method, path);
		if (latencyMs > 0) await sleep(latencyMs);

		record.finishedAt = performance.now();
		record.status = status;
		record.body = body;
		return new Response(JSON.stringify(body), { status, headers: respHeaders });
	};

	return {
		handler,
		calls,
		etagOf,
		storedBody: (tripId: string) => stored.get(tripId),
		install() {
			originalFetch = globalThis.fetch;
			(globalThis as { fetch: unknown }).fetch = handler;
		},
		restore() {
			if (originalFetch) (globalThis as { fetch: unknown }).fetch = originalFetch;
		}
	};
}
