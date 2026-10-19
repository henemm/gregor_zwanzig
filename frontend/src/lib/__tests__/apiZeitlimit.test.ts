// TDD RED — Issue #2361: Zeitlimit fuer den zentralen Browser-Abruf `send()`.
// Spec: docs/specs/modules/fix_2361_abruf_zeitlimit.md (AC-1 bis AC-7).
//
// Zielschnittstelle in `api.ts` (neu, von diesen Tests festgelegt):
//   * `STANDARD_ZEITLIMIT_MS` — Default-Budget je Abruf (25 000 ms)
//   * `setzeStandardZeitlimit(ms)` — senkt den Default fuer Tests (ca. 20 ms),
//     damit kein Fake-Timer noetig ist; jeder Test setzt ihn danach zurueck
//   * Option `zeitlimitMs` an `api.get/post/put/patch/del` — eigenes Budget je
//     Aufruf; `get/post/patch/del` reichen ihre Optionen dafuer kuenftig durch
//   * Ablauf ⇒ Fehler mit `name === 'TimeoutError'`, deutscher Meldung und OHNE
//     `status: 0` (das ist die Schreibsperre aus #2131)
//
// Der fetch-Ersatz lehnt auf das Abbruch-Signal (`init.signal` 'abort') ab wie
// der Browser — geprueft wird echtes Abbruchverhalten, kein Mock-Theater.
// Jeder Test traegt eine eigene Frist: ohne Zeitlimit kehrt `send()` bei einem
// nie antwortenden Server nie zurueck, der Test scheitert dann an der Frist
// statt den ganzen Lauf aufzuhalten.
//
// Die Langlaeufer-Budgets (Compare-Vorschau 70 s, notify/test 130 s,
// Alarm-Vorschau 40 s) liegen gebuendelt in `langlaeufer` (api.ts),
// locations/resolve 40 s als Konstante `ZEITLIMIT_ORT_AUFLOESEN_MS`; alle sind
// unten mit gestellter Uhr bewacht (Fix-Loop 1, F002). Dass eine
// Svelte-Komponente sie tatsaechlich benutzt, ist in dieser Kern-Schicht nicht
// belegbar (kein Render der Komponenten-Handler); ein Quelltext-Check ist
// verboten.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/apiZeitlimit.test.ts

import { test, describe, before, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';

import { clearEtagRegistry, getKnownEtag, istKonflikt } from '../etagRegistry.ts';
import { createFakeTripServer } from './fakeTripServer.ts';

// `window` existiert unter node:test nicht. `api.ts` meldet den Abrufausgang
// ueber `window.dispatchEvent` — ein EventTarget genuegt. Deshalb wird `api.ts`
// erst NACH diesem Setup dynamisch geladen (s. apiSchreibsperre.test.ts).
const windowStandIn = new EventTarget();
(globalThis as { window?: unknown }).window = windowStandIn;

type Optionen = RequestInit & { zeitlimitMs?: number };
type ZeitlimitApi = {
	get: <T>(path: string, extra?: Optionen) => Promise<T>;
	post: <T>(path: string, body: unknown, extra?: Optionen) => Promise<T>;
	put: <T>(path: string, body: unknown, extra?: Optionen) => Promise<T>;
	patch: <T>(path: string, body: unknown, extra?: Optionen) => Promise<T>;
	del: (path: string, extra?: Optionen) => Promise<void>;
};
type Modul = {
	api: ZeitlimitApi;
	STANDARD_ZEITLIMIT_MS?: number;
	setzeStandardZeitlimit?: (ms: number) => void;
};

let modul: Modul;
const LIMIT = 20;
const FRIST = { timeout: 1500 };

before(async () => {
	modul = (await import('../api.ts')) as unknown as Modul;
});

function api(): ZeitlimitApi {
	return modul.api;
}

function setzeDefault(ms: number): void {
	assert.equal(
		typeof modul.setzeStandardZeitlimit,
		'function',
		'api.ts muss `setzeStandardZeitlimit(ms)` exportieren (Test-Setter fuer das Default-Budget)'
	);
	modul.setzeStandardZeitlimit!(ms);
}

const warte = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Zaehlt die Ausgangsmeldungen an den Verbindungs-Store. */
function lausche(): { fehlgeschlagen: number; gelungen: number; stop: () => void } {
	const z = { fehlgeschlagen: 0, gelungen: 0 };
	const f = () => (z.fehlgeschlagen += 1);
	const g = () => (z.gelungen += 1);
	windowStandIn.addEventListener('gz-abruf-fehlgeschlagen', f);
	windowStandIn.addEventListener('gz-abruf-gelungen', g);
	return {
		get fehlgeschlagen() {
			return z.fehlgeschlagen;
		},
		get gelungen() {
			return z.gelungen;
		},
		stop: () => {
			windowStandIn.removeEventListener('gz-abruf-fehlgeschlagen', f);
			windowStandIn.removeEventListener('gz-abruf-gelungen', g);
		}
	};
}

type Aufruf = { path: string; init?: RequestInit };

/**
 * fetch-Ersatz: antwortet nach `nachMs` (null = nie) mit 200/JSON — oder lehnt
 * mit `AbortError` ab, sobald das uebergebene Signal abbricht.
 */
function installiereFetch(nachMs: number | null, status = 200): { aufrufe: Aufruf[]; restore: () => void } {
	const echtesFetch = globalThis.fetch;
	const aufrufe: Aufruf[] = [];
	(globalThis as { fetch: unknown }).fetch = (input: unknown, init?: RequestInit) => {
		aufrufe.push({ path: String(input), init });
		return new Promise<Response>((resolve, reject) => {
			const signal = init?.signal;
			const abbrechen = () => reject(new DOMException('The operation was aborted.', 'AbortError'));
			if (signal?.aborted) return abbrechen();
			signal?.addEventListener('abort', abbrechen, { once: true });
			if (nachMs !== null) {
				setTimeout(() => {
					resolve(
						status === 204
							? new Response(null, { status })
							: new Response(JSON.stringify({ ok: true }), {
									status,
									headers: { 'Content-Type': 'application/json' }
								})
					);
				}, nachMs);
			}
		});
	};
	return {
		aufrufe,
		restore: () => {
			(globalThis as { fetch: unknown }).fetch = echtesFetch;
		}
	};
}

function istZeitlimitFehler(e: unknown): boolean {
	const err = e as { name?: string; message?: string; status?: number };
	assert.equal(err.name, 'TimeoutError', `erwartet TimeoutError, bekommen: ${err.name} — ${err.message}`);
	assert.notEqual(err.status, 0, 'ein Zeitlimit-Fehler darf NICHT `status: 0` tragen (das ist die Schreibsperre)');
	assert.match(String(err.message), /Verbindung|Antwort/, 'der Fehler braucht eine deutsche Meldung');
	return true;
}

let ohr: ReturnType<typeof lausche>;
let netz: ReturnType<typeof installiereFetch> | null = null;

beforeEach(() => {
	ohr = lausche();
});
afterEach(() => {
	ohr.stop();
	netz?.restore();
	netz = null;
	if (typeof modul.setzeStandardZeitlimit === 'function' && typeof modul.STANDARD_ZEITLIMIT_MS === 'number') {
		modul.setzeStandardZeitlimit(modul.STANDARD_ZEITLIMIT_MS);
	}
});

describe('#2361 Default-Budget', () => {
	test('das Default-Budget betraegt 25 Sekunden (EDGE-tauglich)', () => {
		assert.equal(modul.STANDARD_ZEITLIMIT_MS, 25_000, 'api.ts muss `STANDARD_ZEITLIMIT_MS = 25_000` exportieren');
	});
});

describe('AC-1: tote Verbindung ⇒ TimeoutError und Meldung „offline"', () => {
	test('send() wirft nach Ablauf TimeoutError, meldet genau einmal Fehlschlag, nie Erfolg', FRIST, async () => {
		setzeDefault(LIMIT);
		netz = installiereFetch(null);
		await assert.rejects(api().get('/api/trips'), istZeitlimitFehler);
		assert.equal(ohr.fehlgeschlagen, 1, '`gz-abruf-fehlgeschlagen` muss genau einmal feuern');
		assert.equal(ohr.gelungen, 0);
	});

	test('auch ein schreibender Abruf (POST) laeuft ins Zeitlimit', FRIST, async () => {
		setzeDefault(LIMIT);
		netz = installiereFetch(null);
		await assert.rejects(api().post('/api/locations', { name: 'X' }), istZeitlimitFehler);
		assert.equal(ohr.fehlgeschlagen, 1);
	});
});

describe('AC-2: langsame Antwort innerhalb des Budgets', () => {
	test('Antwort nach der Haelfte des Limits kommt an und meldet Erfolg', FRIST, async () => {
		setzeDefault(LIMIT * 3);
		netz = installiereFetch(LIMIT);
		assert.deepEqual(await api().get('/api/trips'), { ok: true });
		assert.equal(ohr.gelungen, 1);
		assert.equal(ohr.fehlgeschlagen, 0);
	});

	test('nach erfolgreicher Antwort bleibt kein Zeitlimit-Timer zurueck (Signal bleibt unberuehrt)', FRIST, async () => {
		setzeDefault(LIMIT);
		netz = installiereFetch(0);
		await api().get('/api/trips');
		const signal = netz.aufrufe[0]?.init?.signal;
		assert.ok(signal, '`send()` muss fetch ein Abbruch-Signal mitgeben');
		await warte(LIMIT * 4);
		assert.equal(signal!.aborted, false, 'der Zeitlimit-Timer wurde nach der Antwort nicht aufgeraeumt');
	});
});

describe('AC-3: eigenes Budget je Aufruf (`zeitlimitMs`)', () => {
	const faelle: Array<[string, (a: ZeitlimitApi, o: Optionen) => Promise<unknown>]> = [
		['get', (a, o) => a.get('/api/compare/presets', o)],
		['post', (a, o) => a.post('/api/preview/compare/cp-1', {}, o)],
		['put', (a, o) => a.put('/api/locations/l-1', { name: 'X' }, o)],
		['patch', (a, o) => a.patch('/api/locations/l-1', { name: 'X' }, o)],
		['del', (a, o) => a.del('/api/locations/l-1', o)]
	];

	for (const [methode, aufruf] of faelle) {
		test(`api.${methode}: laenger als der Default, kuerzer als das eigene Budget ⇒ gelingt`, FRIST, async () => {
			setzeDefault(LIMIT);
			netz = installiereFetch(LIMIT * 3, methode === 'del' ? 204 : 200);
			await aufruf(api(), { zeitlimitMs: LIMIT * 20 });
			assert.equal(ohr.fehlgeschlagen, 0, `api.${methode} wurde trotz eigenem Budget nach dem Default abgebrochen`);
			assert.equal(ohr.gelungen, 1);
		});
	}

	test('das eigene Budget ist wirklich ein Limit, nicht nur „kein Limit"', FRIST, async () => {
		setzeDefault(LIMIT);
		netz = installiereFetch(LIMIT * 30);
		await assert.rejects(api().post('/api/notify/test', {}, { zeitlimitMs: LIMIT * 3 }), istZeitlimitFehler);
	});
});

describe('AC-4: keepalive (Unload-Flush) bekommt kein Zeitlimit', () => {
	test('ein keepalive-PUT wird vom Zeitlimit nicht abgebrochen', FRIST, async () => {
		setzeDefault(LIMIT);
		netz = installiereFetch(LIMIT * 4);
		const ergebnis = await api().put('/api/trips/t-keep', { name: 'X' }, { keepalive: true });
		assert.deepEqual(ergebnis, { ok: true });
		const signal = netz.aufrufe[0]?.init?.signal;
		assert.equal(signal?.aborted ?? false, false, 'das an fetch uebergebene Signal darf nicht ausgeloest sein');
		assert.equal(ohr.fehlgeschlagen, 0);
	});
});

describe('AC-5: Abbruch durch den Aufrufer', () => {
	test('Aufrufer bricht vor dem Limit ab ⇒ AbortError, keine Verbindungsstoerung', FRIST, async () => {
		setzeDefault(LIMIT * 20);
		netz = installiereFetch(null);
		const ctrl = new AbortController();
		const laeuft = api().get('/api/trips', { signal: ctrl.signal });
		setTimeout(() => ctrl.abort(), LIMIT / 2);
		await assert.rejects(laeuft, (e: { name?: string }) => {
			assert.equal(e.name, 'AbortError', `erwartet AbortError, bekommen: ${e.name}`);
			return true;
		});
		assert.equal(ohr.fehlgeschlagen, 0, 'ein Aufrufer-Abbruch ist keine Verbindungsstoerung');
	});

	test('ein mitgegebenes Aufrufer-Signal verdraengt das Zeitlimit nicht', FRIST, async () => {
		setzeDefault(LIMIT);
		netz = installiereFetch(null);
		const ctrl = new AbortController(); // wird nie abgebrochen
		await assert.rejects(api().get('/api/trips', { signal: ctrl.signal }), istZeitlimitFehler);
		assert.equal(ohr.fehlgeschlagen, 1);
	});
});

describe('AC-6: keine automatische Wiederholung nach Zeitlimit', () => {
	test('GET: genau ein fetch-Aufruf, auch nach mehreren Limits', FRIST, async () => {
		setzeDefault(LIMIT);
		netz = installiereFetch(null);
		await assert.rejects(api().get('/api/trips'), istZeitlimitFehler);
		await warte(LIMIT * 5);
		assert.equal(netz.aufrufe.length, 1, 'ein Lesezugriff wurde nach dem Zeitlimit wiederholt');
	});

	test('PUT: genau ein fetch-Aufruf, auch nach mehreren Limits', FRIST, async () => {
		clearEtagRegistry();
		setzeDefault(LIMIT);
		netz = installiereFetch(null);
		await assert.rejects(api().put('/api/trips/t-2361-retry', { name: 'X' }), istZeitlimitFehler);
		await warte(LIMIT * 5);
		assert.equal(netz.aufrufe.length, 1, 'ein Schreibvorgang wurde nach dem Zeitlimit wiederholt');
	});
});

describe('AC-7: PUT im Zeitlimit, Server hat ihn trotzdem angenommen', () => {
	const TRIP = 't-2361';
	const PFAD = `/api/trips/${TRIP}`;

	test('Folge-PUT startet, traegt das alte If-Match und endet im 412-Konfliktpfad', FRIST, async () => {
		clearEtagRegistry();
		setzeDefault(LIMIT);
		const server = createFakeTripServer({ merge: true });
		server.install();
		server.seed(TRIP, { id: TRIP, name: 'Ausgang', stages: [] });
		// Erster PUT: der Server verarbeitet ihn, die Antwort erreicht den Client
		// aber nie (Funkloch auf dem Rueckweg) — bis das Zeitlimit abbricht.
		let erster = true;
		const serverFetch = globalThis.fetch;
		(globalThis as { fetch: unknown }).fetch = async (input: unknown, init?: RequestInit) => {
			if (erster && init?.method === 'PUT') {
				erster = false;
				await serverFetch(input as string, { ...init, signal: undefined });
				return new Promise<Response>((_resolve, reject) => {
					const abbrechen = () => reject(new DOMException('The operation was aborted.', 'AbortError'));
					if (init.signal?.aborted) return abbrechen();
					init.signal?.addEventListener('abort', abbrechen, { once: true });
				});
			}
			return serverFetch(input as string, init);
		};
		try {
			await api().get(PFAD);
			const alterEtag = getKnownEtag(TRIP);
			assert.ok(alterEtag, 'Messaufbau: die Registry kennt den Stand');

			await assert.rejects(api().put(PFAD, { name: 'Erster' }), istZeitlimitFehler);
			assert.equal(server.stand(TRIP).name, 'Erster', 'Messaufbau: der Server hat den ersten PUT angenommen');

			await assert.rejects(api().put(PFAD, { name: 'Zweiter' }), (e: { status?: number }) => {
				assert.equal(e.status, 412, 'der Folge-PUT muss im Konfliktpfad (412) enden');
				return true;
			});
			const puts = server.calls.filter((c) => c.method === 'PUT');
			assert.equal(puts.at(-1)?.ifMatch, alterEtag, 'der Folge-PUT muss das alte If-Match tragen');
			assert.equal(istKonflikt(TRIP), true, '`markiereKonflikt` muss gegriffen haben');
			assert.equal(server.stand(TRIP).name, 'Erster', 'der Server-Stand darf nicht still ueberschrieben werden');
		} finally {
			server.restore();
		}
	});
});

// Fix-Loop 1 (F002): die Budgets der Langlaeufer sind auf den Millisekunden-
// Punkt bewacht. Echtes Warten auf 40–130 s ist ausgeschlossen; die Uhr wird
// deshalb mit `mock.timers` gestellt — sie treibt den ECHTEN `send()`, kein
// Argument-Spiegel. Ein Budget eine Millisekunde vor Ablauf: Abruf laeuft noch;
// bei Ablauf: TimeoutError. Fehlt das Budget, greift der (gesenkte) Default und
// der Abruf scheitert schon beim ersten Vorruecken.
type Langlaeufer = {
	compareVorschau: (presetId: string) => Promise<unknown>;
	testNachricht: (channel: string) => Promise<unknown>;
	alarmVorschau: (tripId: string, payload: unknown) => Promise<unknown>;
};

const flush = () => new Promise((r) => setImmediate(r));

/** Prueft die Budget-Grenze eines Abrufs mit gestellter Uhr. */
async function pruefeBudgetGrenze(
	starte: () => Promise<unknown>,
	budgetMs: number
): Promise<Aufruf[]> {
	setzeDefault(LIMIT);
	netz = installiereFetch(null);
	mock.timers.enable({ apis: ['setTimeout'] });
	try {
		type Ausgang = { ok: boolean; fehler?: unknown };
		const stand: { ausgang: Ausgang | null } = { ausgang: null };
		starte().then(
			() => (stand.ausgang = { ok: true }),
			(fehler) => (stand.ausgang = { ok: false, fehler })
		);
		await flush();
		mock.timers.tick(budgetMs - 1);
		await flush();
		assert.equal(stand.ausgang, null, `der Abruf wurde vor seinem Budget von ${budgetMs} ms abgebrochen`);
		mock.timers.tick(1);
		await flush();
		await flush();
		const ausgang = stand.ausgang as Ausgang | null;
		assert.ok(ausgang, `nach ${budgetMs} ms muss der Abruf ins Zeitlimit laufen`);
		assert.equal(ausgang.ok, false);
		istZeitlimitFehler(ausgang.fehler);
		assert.equal(ohr.fehlgeschlagen, 1);
		return netz.aufrufe;
	} finally {
		mock.timers.reset();
	}
}

describe('F002: Langlaeufer tragen ihr eigenes Budget (gestellte Uhr)', () => {
	function langlaeufer(): Langlaeufer {
		const l = (modul as unknown as { langlaeufer?: Langlaeufer }).langlaeufer;
		assert.ok(l, 'api.ts muss `langlaeufer` exportieren');
		return l!;
	}

	test('Compare-Vorschau: 70 s (Go-Proxy 60 s), POST /api/preview/compare/{id}', FRIST, async () => {
		const aufrufe = await pruefeBudgetGrenze(() => langlaeufer().compareVorschau('cp-1'), 70_000);
		assert.equal(aufrufe.length, 1);
		assert.equal(aufrufe[0].path, '/api/preview/compare/cp-1');
		assert.equal(aufrufe[0].init?.method, 'POST');
	});

	test('Test-Versand: 130 s (Go-Proxy 120 s), POST /api/notify/test {channel}', FRIST, async () => {
		const aufrufe = await pruefeBudgetGrenze(() => langlaeufer().testNachricht('telegram'), 130_000);
		assert.equal(aufrufe[0].path, '/api/notify/test');
		assert.equal(aufrufe[0].init?.method, 'POST');
		assert.deepEqual(JSON.parse(String(aufrufe[0].init?.body)), { channel: 'telegram' });
	});

	test('Alarm-Vorschau: 40 s (Go-Proxy ca. 30 s), POST /api/trips/{id}/alert-preview', FRIST, async () => {
		const aufrufe = await pruefeBudgetGrenze(
			() => langlaeufer().alarmVorschau('t-1', { rules: [] }),
			40_000
		);
		assert.equal(aufrufe[0].path, '/api/trips/t-1/alert-preview');
		assert.deepEqual(JSON.parse(String(aufrufe[0].init?.body)), { rules: [] });
	});

	test('Orts-Aufloesung (Step2Orte/LocationNewModal): `api.post` mit ZEITLIMIT_ORT_AUFLOESEN_MS laeuft 40 s', FRIST, async () => {
		const m = modul as unknown as { ZEITLIMIT_ORT_AUFLOESEN_MS?: number };
		assert.equal(m.ZEITLIMIT_ORT_AUFLOESEN_MS, 40_000);
		await pruefeBudgetGrenze(
			() => api().post('/api/locations/resolve', { input: 'x' }, { zeitlimitMs: m.ZEITLIMIT_ORT_AUFLOESEN_MS }),
			40_000
		);
	});
});

// ── Issue #2283 (AC-15, AC-21): kind-neutrale Vorschau-Abrufe ──────────────
// Spec: docs/specs/modules/shared_preview_tab.md. Zielschnittstelle (neu, von
// diesen Tests festgelegt) — BENANNTE Exporte von `api.ts` (nicht in
// `langlaeufer`: dort heisst `alarmVorschau(tripId, payload)` schon anders und
// bleibt fuer den Alt-Weg unveraendert, s. F002 oben):
//   * `briefingVorschau(kind, id, options?)` → GET
//     /api/briefings/{id}/preview?kind=route|vergleich[&type&date&demo=1]
//     (type/date/demo NUR bei kind=route); Budget vergleich 70 s
//     (= ZEITLIMIT_COMPARE_VORSCHAU_MS, Go 60 s), route
//     `ZEITLIMIT_TRIP_VORSCHAU_MS` (Go 30 s ⇒ ueber 30 s, unter 70 s)
//   * `alarmVorschau(kind, id, payload)` → POST
//     /api/briefings/{id}/alert-preview?kind=route|vergleich, JSON-Koerper =
//     payload, Budget 40 s (= ZEITLIMIT_ALARM_VORSCHAU_MS, unveraendert)
// RED HEUTE: keiner der Exporte existiert.
type KindAbrufe = {
	briefingVorschau?: (kind: string, id: string, options?: Record<string, unknown>) => Promise<unknown>;
	alarmVorschau?: (kind: string, id: string, payload: unknown) => Promise<unknown>;
	ZEITLIMIT_TRIP_VORSCHAU_MS?: number;
};

describe('#2283: briefingVorschau / alarmVorschau (kind-neutral, gestellte Uhr)', () => {
	function abrufe(): Required<Pick<KindAbrufe, 'briefingVorschau' | 'alarmVorschau'>> {
		const m = modul as unknown as KindAbrufe;
		assert.equal(typeof m.briefingVorschau, 'function', 'api.ts muss `briefingVorschau(kind, id, options?)` exportieren');
		assert.equal(typeof m.alarmVorschau, 'function', 'api.ts muss `alarmVorschau(kind, id, payload)` exportieren');
		return m as Required<Pick<KindAbrufe, 'briefingVorschau' | 'alarmVorschau'>>;
	}
	const q = (url: string) => new URL(url, 'http://localhost');

	test('Vergleichs-Vorschau: 70 s, GET /api/briefings/{id}/preview?kind=vergleich ohne Trip-Optionen', FRIST, async () => {
		const aufrufe = await pruefeBudgetGrenze(
			() => abrufe().briefingVorschau('vergleich', 'cp-1', { type: 'evening', demo: true, date: '2026-10-20' }),
			70_000
		);
		assert.equal(aufrufe.length, 1);
		const u = q(aufrufe[0].path);
		assert.equal(u.pathname, '/api/briefings/cp-1/preview');
		assert.deepEqual([...u.searchParams.entries()], [['kind', 'vergleich']]);
		assert.equal(String(aufrufe[0].init?.method ?? 'GET').toUpperCase(), 'GET');
	});

	test('Trip-Vorschau: kuerzeres eigenes Budget ZEITLIMIT_TRIP_VORSCHAU_MS, Optionen als Query', FRIST, async () => {
		const budget = (modul as unknown as KindAbrufe).ZEITLIMIT_TRIP_VORSCHAU_MS;
		assert.equal(typeof budget, 'number', 'api.ts muss `ZEITLIMIT_TRIP_VORSCHAU_MS` exportieren');
		assert.ok(
			budget! > 30_000 && budget! < 70_000,
			`Trip-Budget ${budget} muss ueber dem Go-Limit (30 s) und unter dem Vergleich (70 s) liegen`
		);
		const aufrufe = await pruefeBudgetGrenze(
			() => abrufe().briefingVorschau('route', 't-1', { type: 'morning', demo: true, date: '2026-10-20' }),
			budget!
		);
		const u = q(aufrufe[0].path);
		assert.equal(u.pathname, '/api/briefings/t-1/preview');
		assert.equal(u.searchParams.get('kind'), 'route');
		assert.equal(u.searchParams.get('type'), 'morning');
		assert.equal(u.searchParams.get('demo'), '1');
		assert.equal(u.searchParams.get('date'), '2026-10-20');
		assert.equal(u.searchParams.has('user_id'), false, 'das Frontend haengt nie selbst eine user_id an (ADR-0003)');
	});

	for (const kind of ['vergleich', 'route']) {
		test(`Alarm-Vorschau ${kind}: 40 s, POST /api/briefings/{id}/alert-preview?kind=${kind}`, FRIST, async () => {
			const koerper =
				kind === 'vergleich'
					? { changes: [{ location_id: 'l-1', metric: 'gust_max_kmh', old_value: 25, new_value: 72, delta: 47, threshold: 60, severity: 'major', direction: 'increase' }] }
					: { changes: [], segment_times: [] };
			const aufrufe = await pruefeBudgetGrenze(() => abrufe().alarmVorschau(kind, 'e-1', koerper), 40_000);
			const u = q(aufrufe[0].path);
			assert.equal(u.pathname, '/api/briefings/e-1/alert-preview');
			assert.deepEqual([...u.searchParams.entries()], [['kind', kind]]);
			assert.equal(aufrufe[0].init?.method, 'POST');
			assert.deepEqual(JSON.parse(String(aufrufe[0].init?.body)), koerper);
		});
	}
});
