import type { ApiError, Stage } from './types.js';
import type { NachladeKennung } from './pwa/geraetespeicher.ts';
import {
	enqueueTripWrite,
	etagVersion,
	extractTripId,
	getKnownEtag,
	istKonflikt,
	markiereKonflikt,
	setKnownEtag,
	setKnownEtagIfUnchanged
} from './etagRegistry.ts';
import { tr } from './i18n/index.ts';

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

/**
 * Issue #2131: meldet den Ausgang eines Abrufs an den Verbindungs-Store.
 *
 * Bewusst ueber ein DOM-Ereignis statt eines Imports: `$lib/api.ts` wird auch
 * von node:test-Nachweisen geladen, die keine Svelte-Runen ausfuehren koennen —
 * ein Import des Runen-Stores wuerde sie beim Laden zerreissen.
 */
function meldeAbrufAusgang(erfolg: boolean): void {
	if (typeof window === 'undefined') return;
	// Ereignisnamen sind Protokoll, kein Nutzertext (Ratsche #2660: Marker i18n-log).
	window.dispatchEvent(new CustomEvent(erfolg ? 'gz-abruf-gelungen' : 'gz-abruf-fehlgeschlagen')); // i18n-log
}

/**
 * Issue #2131 AC-10: ein Schreibversuch ohne Verbindung wird abgewiesen, bevor
 * er losgeht — nicht erst, wenn er scheitert.
 *
 * Die gesperrte Oberflaeche allein genuegt dafuer nicht: ein gesperrtes
 * Bedienelement kann von aussen trotzdem ein `change`-Ereignis erhalten (der
 * Nutzer tippt hartnaeckig, ein Skript setzt einen Wert). Der Schreibweg selbst
 * muss die Sperre kennen, sonst haengt die Zusicherung an der Oberflaeche
 * statt an der Stelle, an der sie wirkt.
 */
const SCHREIBEND = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
let schreibsperre = false;

if (typeof window !== 'undefined') {
	window.addEventListener('gz-schreibsperre', (ereignis) => {
		schreibsperre = (ereignis as CustomEvent<{ gesperrt?: boolean }>).detail?.gesperrt === true;
	});
}

function schreibenVerboten(method: string): boolean {
	if (!SCHREIBEND.has(method)) return false;
	// Geraetemeldung „keine Verbindung" ist als NEGATIVES Signal verlaesslich
	// und gilt auch dann, wenn die Oberflaeche ihren Zustand noch nicht
	// gemeldet hat (erster Frame, Ereignisreihenfolge).
	if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
	return schreibsperre;
}

/**
 * Issue #2361: Zeitlimit je Abruf. Ohne Limit wartet `fetch` bei einer praktisch
 * toten Verbindung (EDGE-Funkloch) minutenlang, ohne dass die App reagiert.
 * 25 s: ein Funkloch wird nach rund einer halben Minute gemeldet. Langlaeufer
 * geben ihr eigenes Budget ueber die Option `zeitlimitMs` mit.
 */
export const STANDARD_ZEITLIMIT_MS = 25_000;
let standardZeitlimitMs = STANDARD_ZEITLIMIT_MS;

/** Nur fuer Tests: senkt das Default-Budget, damit kein Fake-Timer noetig ist. */
export function setzeStandardZeitlimit(ms: number): void {
	standardZeitlimitMs = ms;
}

/** Fetch-Optionen plus eigenes Budget je Aufruf (#2361). */
export type AbrufOptionen = RequestInit & { zeitlimitMs?: number };

function zeitlimitFehler(): Error {
	// Bewusst KEIN `status: 0` — das ist die Schreibsperre aus #2131.
	const fehler = new Error(tr('fehler.verbindung.zeitlimit'));
	fehler.name = 'TimeoutError';
	return fehler;
}

async function send<T>(
	method: string,
	path: string,
	tripId: string | null,
	/** true = dieser Vorgang laeuft durch die Warteschlange (serialisierter PUT). */
	serializedWrite: boolean,
	body?: unknown,
	optionen?: AbrufOptionen,
	/** #2317: nimmt den ETag der Antwort und das Registry-Ergebnis auf. */
	fassung?: AntwortFassung
): Promise<T> {
	// Issue #1395 S3: den Stand ERST HIER nachschlagen — innerhalb der
	// Warteschlange, also zu dem Zeitpunkt, zu dem die Anfrage tatsaechlich
	// losgeht. Vor dem Einreihen gelesen, haetten zwei kurz hintereinander
	// ausgeloeste Schreibvorgaenge derselben Trip beide den alten Wert
	// eingefroren und der zweite scheiterte mit 412, obwohl er gewartet hat.
	// Issue #1433: auch ein keepalive-Request (Unload-Flush) traegt das If-Match,
	// solange die Ressource im Konflikt ist — der Server lehnt mit 412 ab.
	const { zeitlimitMs, ...extra } = optionen ?? {};
	const traegtIfMatch = serializedWrite || (extra?.keepalive === true && tripId !== null && istKonflikt(tripId));
	const ifMatch = traegtIfMatch && tripId ? getKnownEtag(tripId) : undefined;
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
	// Issue #2361: eigenes Abbruch-Signal NACH `...extra` — ein Aufrufer-Signal
	// wird nicht ersetzt, sondern verknuepft (bricht der Aufrufer ab, bricht
	// auch der interne Controller ab). Ohne `AbortSignal.timeout/any`, die
	// Safari < 17.4 nicht kennt. keepalive (Unload-Flush) bleibt ohne Limit:
	// die Seite ist ohnehin im Verlassen, der Browser begrenzt keepalive selbst.
	const aufruferSignal = extra.signal ?? null;
	const mitZeitlimit = extra.keepalive !== true;
	let zeitAbgelaufen = false;
	let timer: ReturnType<typeof setTimeout> | undefined;
	let aufruferAbbruch: (() => void) | undefined;
	if (mitZeitlimit) {
		const steuerung = new AbortController();
		aufruferAbbruch = () => steuerung.abort(aufruferSignal?.reason);
		if (aufruferSignal?.aborted) steuerung.abort(aufruferSignal.reason);
		else aufruferSignal?.addEventListener('abort', aufruferAbbruch, { once: true });
		timer = setTimeout(() => {
			zeitAbgelaufen = true;
			steuerung.abort();
		}, zeitlimitMs ?? standardZeitlimitMs);
		opts.signal = steuerung.signal;
	}
	let res: Response;
	try {
		res = await fetch(path, opts);
	} catch (netzfehler) {
		// Abbruch durch den Aufrufer ist keine Verbindungsstoerung: weiterwerfen
		// (AbortError), nichts melden.
		if (!zeitAbgelaufen && aufruferSignal?.aborted) throw netzfehler;
		// Issue #2131: der einzige belastbare Beweis, dass der Server NICHT
		// erreichbar ist. `navigator.onLine` allein taugt dafuer nicht (es meldet
		// nur eine vorhandene Netzwerkschnittstelle). Ab hier sperrt die
		// Oberflaeche — bis ein Abruf nachweislich wieder gelingt.
		meldeAbrufAusgang(false);
		// #2361: kein automatisches Wiederholen — auch nicht fuer GET.
		if (zeitAbgelaufen) throw zeitlimitFehler();
		throw netzfehler;
	} finally {
		if (timer !== undefined) clearTimeout(timer);
		if (aufruferAbbruch) aufruferSignal?.removeEventListener('abort', aufruferAbbruch);
	}
	// Auch eine 4xx/5xx-Antwort BEWEIST einen erreichbaren Server: es hat
	// jemand geantwortet. Nur der ausbleibende Antwortende sperrt.
	meldeAbrufAusgang(true);
	if (!res.ok) {
		// Issue #1006 — Sitzung abgelaufen (24h-TTL): zentral behandeln statt die
		// rohe {"error":"unauthorized"}-Meldung an Aufrufer durchzureichen.
		if (res.status === 401 && typeof window !== 'undefined') {
			const redirectTarget = window.location.pathname + window.location.search;
			window.location.href = `/login?expired=1&redirect=${encodeURIComponent(redirectTarget)}`;
			// Issue #2128: der Status gehoert an den Fehler. Ein Aufrufer muss
			// unterscheiden koennen, ob er auf der Seite bleibt (dann zeigt er eine
			// Meldung) oder ob die Umleitung auf die Anmeldeseite bereits laeuft.
			const abgelaufen = new Error(tr('fehler.sitzung.abgelaufen')) as Error & {
				status: number;
			};
			abgelaufen.status = 401;
			throw abgelaufen;
		}
		// Issue #1433 (loest #1395 S3 „Discard nach 412" ab): der Stempel bleibt
		// stehen, die Ressource ist im Konflikt. Jeder weitere Schreibvorgang
		// traegt das alte If-Match und wird wieder abgelehnt — ein unbedingtes
		// Schreiben nach 412 wuerde die Fremdaenderung ueberschreiben.
		if (res.status === 412 && tripId) markiereKonflikt(tripId);
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
	// derselben Trip lief neben ihm. Jeder Vorgang AUSSERHALB der Warteschlange
	// (Lesevorgang, Entlade-Flush) traegt dagegen den Stand von SEINEM
	// Anfragezeitpunkt — kommt er verspaetet an, waere sein Stempel ein
	// Rueckschritt und der naechste Schreibvorgang bekaeme 412, obwohl niemand
	// sonst etwas geaendert hat (F001).
	if (tripId) {
		const etag = res.headers.get('ETag');
		if (etag) {
			let inRegistry = true;
			if (serializedWrite) setKnownEtag(tripId, etag);
			else inRegistry = setKnownEtagIfUnchanged(tripId, etag, versionAtStart);
			if (fassung) {
				fassung.etag = etag;
				fassung.inRegistry = inRegistry;
			}
		}
	}
	if (res.status === 204) return undefined as T;
	return res.json();
}

async function request<T>(method: string, path: string, body?: unknown, extra?: AbrufOptionen): Promise<T> {
	if (schreibenVerboten(method)) {
		const gesperrt = new Error(tr('fehler.verbindung.schreiben_offline')) as Error & { status: number };
		gesperrt.status = 0;
		throw gesperrt;
	}
	const tripId = extractTripId(path);
	// `{ keepalive: true }` kommt vom Unload-Flush des Controllers (`flush({
	// keepalive: true })`); ein Reiter setzt es nicht mehr selbst (#1433). Dieser
	// Vorgang hat nur ein sehr kurzes Zeitfenster: er darf weder hinter einem
	// laufenden Schreibvorgang warten (er ginge womoeglich nie los) noch ohne
	// Konflikt an einem unsichtbaren 412 scheitern. Bei offenem Konflikt traegt er
	// das alte If-Match (s. `send`) — dann ist die Ablehnung gewollt.
	const isUnloadFlush = extra?.keepalive === true;
	const serializedWrite = method === 'PUT' && tripId !== null && !isUnloadFlush;
	const run = () => send<T>(method, path, tripId, serializedWrite, body, extra);
	return serializedWrite ? enqueueTripWrite(tripId as string, run) : run();
}

export const api = {
	get: <T>(path: string, extra?: AbrufOptionen) => request<T>('GET', path, undefined, extra),
	post: <T>(path: string, body: unknown, extra?: AbrufOptionen) => request<T>('POST', path, body, extra),
	put: <T>(path: string, body: unknown, extra?: AbrufOptionen) => request<T>('PUT', path, body, extra),
	patch: <T>(path: string, body: unknown, extra?: AbrufOptionen) => request<T>('PATCH', path, body, extra),
	del: (path: string, extra?: AbrufOptionen) => request<void>('DELETE', path, undefined, extra)
};

/**
 * Issue #2361: Budgets der bewusst langen Aktionen — jeweils Server-Limit plus
 * Puffer, damit der Server zuerst antwortet. Aendert sich ein Server-Limit,
 * muss das Budget hier mitwandern.
 */
/** Test-Versand (notify/test): Go-Proxy begrenzt auf 120 s (internal/handler/notify.go). */
export const ZEITLIMIT_TEST_NACHRICHT_MS = 130_000;
/** Alarm-Vorschau: Go-Proxy begrenzt auf ca. 30 s. */
export const ZEITLIMIT_ALARM_VORSCHAU_MS = 40_000;
/**
 * Orts-Aufloesung (locations/resolve): Resolver gesamt bis ca. 30 s. Die beiden
 * Aufrufstellen (Step2Orte, LocationNewModal) rufen `api.post` direkt mit
 * dieser Konstante auf — aeltere Quelltext-Tests verlangen dort die
 * Schreibweise `api.post<ResolveResult>('/api/locations/resolve'`.
 */
export const ZEITLIMIT_ORT_AUFLOESEN_MS = 40_000;

/** #2361: die Langlaeufer-Abrufe — jeder traegt sein eigenes Budget. */
// #1743 F003: `compareVorschau` (POST /api/preview/compare/{id}) entfiel mit der
// Briefing-Vorschau (PO-Entscheid 2026-10-22).
export const langlaeufer = {
	testNachricht: <T>(channel: string) =>
		api.post<T>('/api/notify/test', { channel }, { zeitlimitMs: ZEITLIMIT_TEST_NACHRICHT_MS }),
	alarmVorschau: <T>(tripId: string, payload: unknown) =>
		api.post<T>(`/api/trips/${tripId}/alert-preview`, payload, { zeitlimitMs: ZEITLIMIT_ALARM_VORSCHAU_MS })
};

export type BriefingKind = 'route' | 'vergleich';

/** #2283: kind-neutrale Alarm-Vorschau (POST /api/briefings/{id}/alert-preview?kind=…), 40 s. */
export function alarmVorschau<T>(kind: BriefingKind, id: string, payload: unknown): Promise<T> {
	return api.post<T>(`/api/briefings/${encodeURIComponent(id)}/alert-preview?kind=${kind}`, payload, {
		zeitlimitMs: ZEITLIMIT_ALARM_VORSCHAU_MS
	});
}

/** #2317: ETag einer Antwort und ob die Registry ihn uebernommen hat. */
export interface AntwortFassung {
	etag: string | null;
	inRegistry: boolean;
}

/**
 * Issue #2317 Baustein 3: GET wie `api.get`, liefert zusaetzlich den ETag DIESER
 * Antwort und ob die Registry ihn uebernommen hat. `inRegistry === false` heisst:
 * waehrend der GET unterwegs war, hat ein anderer Vorgang den Eintrag der Trip
 * veraendert (F001-Regel in `send`) — der ETag passt dann nicht zum If-Match
 * der naechsten Speicherung.
 */
export async function getMitFassung<T>(path: string): Promise<{ daten: T } & AntwortFassung> {
	const fassung: AntwortFassung = { etag: null, inRegistry: false };
	const daten = await send<T>('GET', path, extractTripId(path), false, undefined, undefined, fassung);
	return { daten, ...fassung };
}

/**
 * Issue #1395 S4: laedt eine Trip ODER einen Ortsvergleich ausschliesslich, um
 * den bestehenden ETag-Seiteneffekt von `send()` auszuloesen. Der Datensatz wird
 * bewusst NICHT zurueckgegeben — sonst entstuende die Versuchung, ihn dem
 * sichtbaren Seitenzustand zuzuweisen und ungespeicherte Aenderungen anderer
 * Tabs zu ueberschreiben.
 *
 * Issue #2276 S1: die Ressourcenart wird UEBERGEBEN, nie aus der Kennung
 * abgeleitet. Eine Ableitung ueber das Praefix `cp-` waere am Bestand falsch —
 * Alt-Ortsvergleiche tragen Slug-Kennungen ohne Praefix (s. `etagRegistry.ts`).
 */
export async function refreshResourceEtag(id: string, kind: NachladeKennung['typ']): Promise<void> {
	await api.get(kind === 'vergleich' ? `/api/compare/presets/${id}` : `/api/trips/${id}`);
}

/**
 * Fix-Loop 1 (#1433, F001/AC-19): wie `refreshResourceEtag`, liefert aber den geholten
 * Datensatz — ausschliesslich fuer „Nochmal speichern", das ihn zusammen mit dem
 * Stempel (liegt nach dem GET in der Registry) an die Seite gibt, BEVOR die eigenen
 * Aenderungen erneut gesendet werden. `refreshResourceEtag` bleibt bewusst void
 * (#1395 S4 AC-5: andere Aufrufer duerfen den Datensatz nicht zuweisen).
 */
export async function refreshResourceEtagMitTrip(id: string, kind: NachladeKennung['typ']): Promise<unknown> {
	return api.get(kind === 'vergleich' ? `/api/compare/presets/${id}` : `/api/trips/${id}`);
}

/**
 * Issue #2270 — Datenexport nach DSGVO Art. 20.
 *
 * `request<T>` liefert ausschliesslich geparstes JSON und kann eine Archivdatei
 * deshalb nicht transportieren. Der Download nimmt denselben Sonderweg wie
 * `uploadGpx`, nur in der Gegenrichtung: rohes `fetch`, Blob, Objekt-URL und
 * ein programmatischer Anker-Klick.
 */
export async function downloadUserDataExport(): Promise<void> {
	const res = await fetch('/api/auth/export');
	if (!res.ok) {
		const detail = await res.text();
		throw new Error(tr('fehler.download.fehlgeschlagen', { status: res.status, detail }));
	}
	const treffer = /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') ?? '');
	const blob = await res.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = treffer?.[1] ?? 'gregor-zwanzig-export.zip';
	document.body.appendChild(a);
	a.click();
	a.remove();
	// Die Objekt-URL erst verzoegert freigeben: Safari bricht einen noch
	// laufenden Download ab, wenn die Quelle sofort widerrufen wird.
	setTimeout(() => URL.revokeObjectURL(url), 10_000);
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
