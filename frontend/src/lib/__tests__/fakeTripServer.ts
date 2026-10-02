// Issue #1395 S3 — Ersatz-Server fuer `globalThis.fetch`.
//
// KEIN Mock im verbotenen Sinn ("spiegelt die eigene Annahme zurueck"): bildet
// den S2-Server-Vertrag nach (docs/specs/modules/issue_1395_s2_etag_ifmatch.md)
// und ist der GEGENSPIELER der Tests. Fuehrt einen echten Fingerabdruck je Trip
// (aendert sich bei JEDEM erfolgreichen Schreibvorgang, S1/ADR-0036), prueft
// `If-Match` mit derselben Parser-Logik wie `internal/handler/etag.go` und
// antwortet mit echten `Response`/`Headers`/Statuscodes/JSON-Ruempfen. Ein Test
// kann hier real scheitern — genau das ist der Zweck.
//
// Issue #1433: optional `merge: true` — dann mergt ein Trip-PUT wie der echte
// Go-Handler (einstufig, s. `mergeTrip` unten) und `foreignWrite` simuliert den
// Python-Fremdschreiber. Ohne die Option bleibt alles wie vor #1433 (PUT
// ersetzt den Rumpf), weil rund 35 bestehende Tests darauf bauen.

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
	/** geparster ANFRAGE-Rumpf (PUT/PATCH), auch bei 412-abgelehnten Anfragen
	 *  (#1433: dort entscheidet der Inhalt, ob ein Reiter Fremdfelder mitsendet). */
	anfrage?: unknown;
}

export interface FakeTripServer {
	/** Ersatz fuer `globalThis.fetch` */
	handler: (input: unknown, init?: RequestInit) => Promise<Response>;
	calls: RequestRecord[];
	/** aktueller ETag-Wert (inkl. Anfuehrungszeichen) einer Trip */
	etagOf(tripId: string): string;
	/** zuletzt erfolgreich geschriebener Rumpf einer Trip */
	storedBody(tripId: string): unknown;
	install(): void;
	restore(): void;
	/** Nur mit `merge: true` (Issue #1433): Ausgangsstand einer Trip anlegen. */
	seed(tripId: string, doc: Record<string, unknown>): void;
	/** Nur mit `merge: true`: der gemergte Gesamtstand einer Trip (tiefe Kopie). */
	stand(tripId: string): Record<string, unknown>;
	/**
	 * Nur mit `merge: true`: Fremdschreiber (Python-Core: Telegram-/SMS-Befehl,
	 * Scheduler, `save_trip`) — schreibt OHNE If-Match, nicht ueber `api.ts`,
	 * der ETag aendert sich. Merge wie Go (einstufig), aber ohne die Go-
	 * Allowlist der Top-Level-Felder: Python schreibt die Datei direkt.
	 * Taucht NICHT in `calls` auf (kein Client-Zugriff).
	 */
	foreignWrite(tripId: string, teil: Record<string, unknown>): void;
}

// Dieselbe Pfad-Definition wie der echte Server: Trip-Ressource, ihre
// Wetter-Konfiguration und (Issue #1395 S6) der Ortsvergleich-Preset tragen
// einen ETag. `id` liefert match[1] (Trip) oder match[2] (Compare-Preset).
const TRIP_PATH_RE =
	/^\/api\/(?:trips\/([^/?#]+)(?:\/weather-config)?|compare\/presets\/([^/?#]+))(?:[?#]|$)/;
const STATE_PATH_RE = /^\/api\/trips\/([^/?#]+)\/state(?:[?#]|$)/;
const WEATHER_CONFIG_RE = /^\/api\/trips\/[^/?#]+\/weather-config(?:[?#]|$)/;

/** Spiegelbild von `ifMatchAllows` in `internal/handler/etag.go` (S2). */
function ifMatchAllows(header: string, current: string): boolean {
	const h = header.trim();
	if (h === '' || h === '*') return true;
	const cur = current.replace(/^"/, '').replace(/"$/, '');
	return h.split(',').some((part) => part.trim().replace(/^"/, '').replace(/"$/, '') === cur);
}

// ─── Issue #1433: Go-treuer Merge (nur mit `merge: true`) ────────────────────
// Quellen: internal/handler/config_merge.go (mergeConfigMap :11-22),
// internal/handler/trip.go (UpdateTripHandler :268ff, tripUpdateRequest :225ff,
// tripStateRequest-Handler :495ff), internal/handler/weather_config.go :99-125,
// internal/store/slot_hour_normalization.go.
// Der Merge ist EINSTUFIG: Top-Level-Schluessel der Config-Objekte
// ueberschreiben, verschachtelte Werte werden als Ganzes ersetzt, geloescht
// wird nie. Ein nicht gesendeter Schluessel (oder JSON-`null` auf einem
// Zeiger-Feld) laesst den Bestand unberuehrt.

type Dok = Record<string, unknown>;

function istObjekt(v: unknown): v is Dok {
	return v !== null && typeof v === 'object' && !Array.isArray(v);
}

const kopie = <T>(v: T): T => (v === undefined ? v : (JSON.parse(JSON.stringify(v)) as T));

/** Spiegelbild `mergeConfigMap`: Schluessel aus `src` ueberschreiben, Rest bleibt. */
function mergeConfigMap(dst: unknown, src: Dok): Dok {
	const out: Dok = istObjekt(dst) ? dst : {};
	for (const [k, v] of Object.entries(src)) out[k] = kopie(v);
	return out;
}

/** `tripUpdateRequest` (trip.go:225-262): nur diese Top-Level-Felder kennt Go. */
const GO_TRIP_FELDER = new Set([
	'name',
	'stages',
	'avalanche_regions',
	'aggregation',
	'weather_config',
	'display_config',
	'report_config',
	'alert_rules',
	'corridors',
	'alert_cooldown_minutes',
	'alert_quiet_from',
	'alert_quiet_to',
	'region',
	'activity',
	'official_alerts_enabled',
	'official_alert_triggers_enabled',
	'official_warnings',
	'alert_channels',
	'alert_channel_thresholds',
	'alert_metric_channels'
]);
/** Felder mit `mergeConfigMap` (trip.go:300-336). */
const GO_MAP_MERGE = new Set([
	'aggregation',
	'weather_config',
	'display_config',
	'report_config',
	'alert_metric_channels'
]);
/** Unterobjekte mit Feld-Merge je Kanal (trip.go:376-448). */
const GO_KANAL_MERGE = new Set(['alert_channels', 'alert_channel_thresholds']);

/** `TruncateTimeStringToHour` (slot_hour_normalization.go:36-49). */
function aufStundeKappen(wert: string): string {
	const v = wert.length === 5 ? `${wert}:00` : wert;
	const m = /^(\d{2}):(\d{2}):(\d{2})$/.exec(v);
	if (!m) return wert;
	if (m[2] === '00' && m[3] === '00') return wert;
	return `${m[1]}:00:00`;
}

function reportConfigNormalisieren(rc: Dok): void {
	for (const k of ['morning_time', 'evening_time']) {
		if (typeof rc[k] === 'string' && rc[k] !== '') rc[k] = aufStundeKappen(rc[k] as string);
	}
	// ClampReportConfigDayWindow: ungueltiges Paar ⇒ beide Schluessel entfernt.
	const s = rc.day_window_start_hour;
	const e = rc.day_window_end_hour;
	const sOk = typeof s === 'number';
	const eOk = typeof e === 'number';
	if (!sOk && !eOk) return;
	const gueltig = sOk && eOk && s >= 0 && s <= 23 && e >= 0 && e <= 23 && s !== e;
	if (!gueltig) {
		delete rc.day_window_start_hour;
		delete rc.day_window_end_hour;
	}
}

/** `PUT /api/trips/{id}` — Go-Semantik; `alsPython` laesst jedes Top-Level-Feld zu. */
function mergeTrip(dok: Dok, teil: Dok, alsPython = false): void {
	for (const [k, v] of Object.entries(teil)) {
		if (v === null || v === undefined) continue; // JSON-null auf Zeiger-Feld = „nicht gesendet"
		if (!alsPython && !GO_TRIP_FELDER.has(k)) continue; // unbekanntes Feld: Go ignoriert es
		if (GO_MAP_MERGE.has(k) && istObjekt(v)) {
			dok[k] = mergeConfigMap(dok[k], v);
		} else if (GO_KANAL_MERGE.has(k) && istObjekt(v)) {
			dok[k] = { ...(istObjekt(dok[k]) ? dok[k] : {}), ...kopie(v) };
		} else if (k === 'official_warnings' && istObjekt(v)) {
			const alt = istObjekt(dok[k]) ? dok[k] : {};
			const neu: Dok = kopie(v);
			if (!('sources' in neu) && 'sources' in alt) neu.sources = alt.sources;
			dok[k] = neu;
		} else {
			dok[k] = kopie(v);
		}
	}
	if (!alsPython && istObjekt(teil.report_config) && istObjekt(dok.report_config)) {
		reportConfigNormalisieren(dok.report_config);
	}
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

export function createFakeTripServer(
	options: {
		latencyMs?: Latency;
		/**
		 * Issue #1433: Go-treuer Merge statt „PUT ersetzt den Rumpf". Ohne diese
		 * Option bleibt das Verhalten fuer alle bestehenden Tests unveraendert
		 * (`storedBody` = zuletzt geschriebener Rumpf, GET liefert ihn zurueck).
		 */
		merge?: boolean;
	} = {}
): FakeTripServer {
	const latencyOf = (method: string, path: string): number => {
		const l = options.latencyMs ?? 0;
		return typeof l === 'function' ? l(method, path) : l;
	};
	const merge = options.merge === true;
	const fingerprints = new Map<string, string>();
	const stored = new Map<string, unknown>();
	const docs = new Map<string, Dok>();
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

	const dokOf = (tripId: string): Dok => {
		let d = docs.get(tripId);
		if (!d) {
			d = {};
			docs.set(tripId, d);
		}
		return d;
	};

	const handler = async (input: unknown, init?: RequestInit): Promise<Response> => {
		const path = String(input);
		const method = (init?.method ?? 'GET').toUpperCase();
		const reqHeaders = new Headers((init?.headers ?? {}) as HeadersInit);
		const ifMatch = reqHeaders.get('If-Match');
		const match = TRIP_PATH_RE.exec(path);
		const tripId = match ? decodeURIComponent(match[1] ?? match[2]) : null;
		// Nur im Merge-Modus: `PATCH /api/trips/{id}/state` veraendert die Datei
		// (neuer Fingerabdruck), liefert aber keinen ETag (S2 AC-15).
		const stateMatch = merge ? STATE_PATH_RE.exec(path) : null;
		let anfrage: unknown = undefined;
		if (typeof init?.body === 'string') {
			try {
				anfrage = JSON.parse(init.body);
			} catch {
				/* Rumpf war kein JSON */
			}
		}

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
			body: undefined,
			anfrage
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

		if (stateMatch) {
			const id = decodeURIComponent(stateMatch[1]);
			const dok = dokOf(id);
			const req = (istObjekt(anfrage) ? anfrage : {}) as Dok;
			const jetzt = new Date().toISOString();
			if (typeof req.paused === 'boolean') dok.paused_at = req.paused ? jetzt : null;
			if (typeof req.archived === 'boolean') dok.archived_at = req.archived ? jetzt : null;
			bump(id); // KEIN ETag-Header in der Antwort (S2 AC-15)
			body = { id, ...kopie(dok) };
		} else if (tripId === null) {
			// Nicht-Trip-/Nicht-Compare-Preset-Pfad (z. B. /api/locations/...,
			// /api/trips/{id}/state): kein ETag, keine Vorbedingung.
			body = { ok: true, path };
		} else if (method === 'GET') {
			respHeaders.set('ETag', etagOf(tripId));
			body = merge
				? { id: tripId, ...kopie(dokOf(tripId)) }
				: { id: tripId, ...(stored.get(tripId) as object | undefined) };
		} else if (method === 'PUT') {
			const current = etagOf(tripId);
			if (ifMatch !== null && !ifMatchAllows(ifMatch, current)) {
				status = 412;
				body = { error: 'precondition_failed', detail: PRECONDITION_FAILED_DETAIL };
				// KEIN ETag-Header — S2 AC-13.
			} else {
				const payload = anfrage;
				stored.set(tripId, payload);
				if (merge && istObjekt(payload) && match?.[1] !== undefined) {
					const dok = dokOf(tripId);
					if (WEATHER_CONFIG_RE.test(path)) {
						// weather_config.go:114-125 — der Rumpf IST die display_config.
						dok.display_config = mergeConfigMap(dok.display_config, payload);
						respHeaders.set('ETag', bump(tripId));
						body = kopie(dok.display_config);
					} else {
						mergeTrip(dok, payload);
						respHeaders.set('ETag', bump(tripId));
						body = { id: tripId, ...kopie(dok) };
					}
				} else {
					respHeaders.set('ETag', bump(tripId));
					body = { id: tripId, ...(payload as object | undefined) };
				}
			}
		} else {
			// PATCH/DELETE auf die Trip-Ressource: veraendert die Datei (neuer
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
		seed(tripId, doc) {
			docs.set(tripId, kopie(doc));
			bump(tripId);
		},
		stand: (tripId) => kopie(dokOf(tripId)),
		foreignWrite(tripId, teil) {
			mergeTrip(dokOf(tripId), teil, true);
			bump(tripId);
		},
		install() {
			originalFetch = globalThis.fetch;
			(globalThis as { fetch: unknown }).fetch = handler;
		},
		restore() {
			if (originalFetch) (globalThis as { fetch: unknown }).fetch = originalFetch;
		}
	};
}
