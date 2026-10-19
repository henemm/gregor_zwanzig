// TDD RED — Issue #2283 (Epic #2345 P3), Scheibe S2/S3: EIN Lader fuer den
// geteilten Vorschau-Reiter beider Hubs.
// Spec: docs/specs/modules/shared_preview_tab.md — AC-9 (genau ein Abruf, kein
// Laden vor dem Oeffnen, Kanal-/Ansichtswechsel ohne neuen Abruf), AC-10
// (Morgen/Abend + Demo nur im Trip), AC-15 (Vergleich: Frontend-Budget 70 s).
//
// ZIELSCHNITTSTELLE (von diesen Tests festgelegt) — `shared/previewLoader.ts`,
// reines TypeScript ohne Runen, damit es unter node:test laeuft:
//
//   type PreviewKind    = 'route' | 'vergleich'
//   type PreviewChannel = 'email' | 'sms' | 'telegram'
//   type EmailView      = 'desktop' | 'mobile'
//   interface PreviewBundle {            // Antwortform Spec „Bündelaufruf"
//     subject: string; email_html: string;
//     sms: { text: string; char_count: number };
//     telegram: { body: string; bubbles?: string[] };
//   }
//   interface PreviewOptions { type?: 'morning'|'evening'; date?: string; demo?: boolean }
//   interface PreviewState {
//     status: 'idle'|'loading'|'ready'|'error'; data: PreviewBundle|null;
//     error: string|null; channel: PreviewChannel; emailView: EmailView;
//     options: PreviewOptions;
//   }
//   createPreviewLoader({ kind, id, options?, channel?, emailView? }) → {
//     kind, id,
//     getState(): PreviewState,
//     load(): Promise<void>,          // erster Aufruf = genau EIN Abruf; jeder
//                                     // weitere (auch waehrend er laeuft) = keiner
//     setChannel(c), setEmailView(v), // reine Anzeige — NIE ein Abruf
//     setOptions(o): Promise<void>,   // route: geaenderte Option = genau ein neuer
//                                     // Abruf; vergleich: ignoriert, kein Abruf
//     subscribe(fn): () => void,      // meldet jede Zustandsaenderung
//   }
//
// Der Lader holt ueber `briefingVorschau(kind, id, options)` aus `api.ts`
// (GET /api/briefings/{id}/preview?kind=…, Budget vergleich 70 s, route
// `ZEITLIMIT_TRIP_VORSCHAU_MS`). Gezaehlt wird deshalb am ECHTEN Netz-Ausgang
// `globalThis.fetch` hinter dem echten `api.ts` — kein Zaehler-Spiegel einer
// eingeschleusten Funktion. Der fetch-Ersatz ist nur die Netzgrenze und
// antwortet mit einer Buendel-Antwort in Spec-Form.
//
// Grenze dieser Schicht: dass `PreviewTab.svelte` beim Kanalklick wirklich nur
// `setChannel` ruft (und keinen eigenen $effect mit Abruf hat), ist ohne
// Browser nicht belegbar — das bewacht die migrierte Live-Spec
// `frontend/e2e/langlaeufer-zeitbudget-wirkort.spec.ts` (zaehlt Aufrufe an
// /api/briefings/*/preview). Dass PreviewTab den Zustand DIESES Laders
// anzeigt, bewacht `previewTab.test.ts` (Render mit vorgegebenem Lader).
//
// RED HEUTE: `shared/previewLoader.ts` existiert nicht (und `api.ts` kennt
// `briefingVorschau` nicht).
//
// Ausfuehren:
//   cd frontend && npm test -- src/lib/components/shared/__tests__/previewLoader.test.ts

import { test, describe, beforeEach, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

// Pfadregel #1409: Pruefling relativ zu DIESER Datei.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const LOADER = pathToFileURL(path.resolve(HERE, '../previewLoader.ts')).href;
const API = pathToFileURL(path.resolve(HERE, '../../../api.ts')).href;
const HELPERS = pathToFileURL(path.resolve(HERE, '../../preview/previewHelpers.ts')).href;

type Kind = 'route' | 'vergleich';
type State = {
	status: string;
	data: unknown;
	error: string | null;
	channel: string;
	emailView: string;
	options: { type?: string; date?: string; demo?: boolean };
};
type Loader = {
	kind: Kind;
	id: string;
	getState(): State;
	load(): Promise<void>;
	setChannel(c: string): void;
	setEmailView(v: string): void;
	setOptions(o: Record<string, unknown>): Promise<void>;
	subscribe(fn: (s: State) => void): () => void;
};
type Modul = { createPreviewLoader: (init: Record<string, unknown>) => Loader };

async function ladeModul(): Promise<Modul> {
	let m: Partial<Modul>;
	try {
		m = (await import(LOADER)) as Partial<Modul>;
	} catch (e) {
		assert.fail(
			`shared/previewLoader.ts fehlt oder laedt nicht (AC-9: EIN Lader fuer beide Hubs): ${(e as Error).message}`
		);
	}
	assert.equal(typeof m.createPreviewLoader, 'function', 'previewLoader.ts muss `createPreviewLoader` exportieren');
	return m as Modul;
}

/** Buendel-Antwort in der Spec-Form (fuer beide kinds gleich). */
const BUENDEL = {
	subject: '[KHW 403] Morgen-Briefing Etappe 3',
	email_html: '<!doctype html><html><body><h1>Etappe 3</h1><table><tr><td>Wind 35</td></tr></table></body></html>',
	sms: { text: 'KHW_03: N3 D11 W35 G52 R2.1 TH:M@14', char_count: 36 },
	telegram: { body: 'Etappe 3 — Wind 35 km/h, Boeen 52 km/h', bubbles: ['Etappe 3 — Wind 35 km/h, Boeen 52 km/h'] }
};

type Aufruf = { url: string; method: string };
let aufrufe: Aufruf[] = [];
let echtesFetch: typeof globalThis.fetch;

/** Netzgrenze: antwortet je nach `modus` mit dem Buendel, 500 oder nie. */
function installiereNetz(modus: 'ok' | 'fehler' | 'nie' = 'ok'): void {
	(globalThis as { fetch: unknown }).fetch = (input: unknown, init?: RequestInit) => {
		aufrufe.push({ url: String(input), method: String(init?.method ?? 'GET') });
		if (modus === 'nie') {
			return new Promise<Response>((_res, rej) => {
				const s = init?.signal;
				const ab = () => rej(new DOMException('The operation was aborted.', 'AbortError'));
				if (s?.aborted) return ab();
				s?.addEventListener('abort', ab, { once: true });
			});
		}
		if (modus === 'fehler') {
			return Promise.resolve(
				new Response(JSON.stringify({ error: 'render_failed', detail: 'boom' }), {
					status: 500,
					headers: { 'Content-Type': 'application/json' }
				})
			);
		}
		return Promise.resolve(
			new Response(JSON.stringify(BUENDEL), { status: 200, headers: { 'Content-Type': 'application/json' } })
		);
	};
}

beforeEach(() => {
	aufrufe = [];
	echtesFetch = globalThis.fetch;
});
afterEach(() => {
	(globalThis as { fetch: unknown }).fetch = echtesFetch;
});

function vorschauAufrufe(): Aufruf[] {
	return aufrufe.filter((a) => /\/api\/briefings\/[^/]+\/preview/.test(a.url));
}

function query(url: string): URLSearchParams {
	return new URL(url, 'http://localhost').searchParams;
}

describe('AC-9: kein Abruf vor dem Oeffnen, genau einer beim Laden', () => {
	for (const kind of ['route', 'vergleich'] as Kind[]) {
		test(`${kind}: Anlegen des Laders ruft nichts ab, Zustand ist idle`, async () => {
			const { createPreviewLoader } = await ladeModul();
			installiereNetz();
			const l = createPreviewLoader({ kind, id: 'e-1' });
			await new Promise((r) => setImmediate(r));
			assert.equal(aufrufe.length, 0, 'der Lader hat schon beim Anlegen abgerufen (kein Laden vor dem Oeffnen, AC-9)');
			assert.equal(l.getState().status, 'idle');
			assert.equal(l.getState().data, null);
		});

		test(`${kind}: load() = genau EIN GET an /api/briefings/{id}/preview?kind=${kind}`, async () => {
			const { createPreviewLoader } = await ladeModul();
			installiereNetz();
			const l = createPreviewLoader({ kind, id: 'e-1' });
			await l.load();
			assert.equal(aufrufe.length, 1, `erwartet genau einen Abruf, bekommen: ${JSON.stringify(aufrufe)}`);
			const [a] = aufrufe;
			assert.equal(a.method, 'GET');
			assert.equal(new URL(a.url, 'http://localhost').pathname, '/api/briefings/e-1/preview');
			assert.equal(query(a.url).get('kind'), kind);
			assert.equal(query(a.url).has('user_id'), false, 'das Frontend haengt nie selbst eine user_id an (ADR-0003)');
			const s = l.getState();
			assert.equal(s.status, 'ready');
			assert.deepEqual(s.data, BUENDEL, 'der Lader muss die Buendel-Antwort unveraendert bereitstellen');
		});

		test(`${kind}: wiederholtes und gleichzeitiges load() ruft nicht erneut ab`, async () => {
			const { createPreviewLoader } = await ladeModul();
			installiereNetz();
			const l = createPreviewLoader({ kind, id: 'e-1' });
			await Promise.all([l.load(), l.load()]);
			await l.load();
			assert.equal(aufrufe.length, 1, 'ein erneutes Oeffnen des Reiters darf die Vorschau nicht nochmal laden');
		});

		test(`${kind}: Kanal- und Ansichtswechsel erzeugen keinen neuen Abruf`, async () => {
			const { createPreviewLoader } = await ladeModul();
			installiereNetz();
			const l = createPreviewLoader({ kind, id: 'e-1' });
			const meldungen: State[] = [];
			const ab = l.subscribe((s) => meldungen.push({ ...s }));
			await l.load();
			const vorher = meldungen.length;
			for (const c of ['sms', 'telegram', 'email', 'sms']) l.setChannel(c);
			l.setChannel('email');
			l.setEmailView('mobile');
			l.setEmailView('desktop');
			l.setEmailView('mobile');
			await new Promise((r) => setImmediate(r));
			assert.equal(aufrufe.length, 1, `Kanal-/Ansichtswechsel hat neu abgerufen: ${JSON.stringify(aufrufe)}`);
			const s = l.getState();
			assert.equal(s.channel, 'email');
			assert.equal(s.emailView, 'mobile');
			assert.ok(meldungen.length > vorher, 'subscribe muss Kanal-/Ansichtswechsel melden (sonst sieht der Reiter sie nicht)');
			assert.equal(meldungen.at(-1)?.emailView, 'mobile');
			ab();
		});
	}

	test('Standard: Kanal E-Mail, Ansicht Desktop', async () => {
		const { createPreviewLoader } = await ladeModul();
		const s = createPreviewLoader({ kind: 'vergleich', id: 'cp-1' }).getState();
		assert.equal(s.channel, 'email');
		assert.equal(s.emailView, 'desktop');
	});

	test('die ID wird im Pfad kodiert', async () => {
		const { createPreviewLoader } = await ladeModul();
		installiereNetz();
		await createPreviewLoader({ kind: 'route', id: 'a b' }).load();
		assert.equal(new URL(aufrufe[0].url, 'http://localhost').pathname, '/api/briefings/a%20b/preview');
	});
});

describe('AC-10: Morgen/Abend und Demo nur im Trip (route)', () => {
	test('route: Standard ist Demo an und der Berichtstyp nach Tageszeit (wie bisher)', async () => {
		const { createPreviewLoader } = await ladeModul();
		const { defaultReportType } = (await import(HELPERS)) as { defaultReportType: () => string };
		installiereNetz();
		const l = createPreviewLoader({ kind: 'route', id: 't-1' });
		assert.equal(l.getState().options.demo, true, 'Trip-Standard demoMode=true muss unveraendert bleiben');
		assert.equal(l.getState().options.type, defaultReportType());
		await l.load();
		const q = query(aufrufe[0].url);
		assert.equal(q.get('demo'), '1');
		assert.equal(q.get('type'), defaultReportType());
	});

	test('route: Optionswechsel (Abend, echte Daten) = genau ein neuer Abruf je Aenderung', async () => {
		const { createPreviewLoader } = await ladeModul();
		installiereNetz();
		const l = createPreviewLoader({ kind: 'route', id: 't-1', options: { type: 'morning', demo: true } });
		await l.load();
		await l.setOptions({ type: 'evening' });
		assert.equal(vorschauAufrufe().length, 2);
		assert.equal(query(aufrufe[1].url).get('type'), 'evening');
		await l.setOptions({ type: 'evening' });
		assert.equal(vorschauAufrufe().length, 2, 'unveraenderte Option darf nicht neu laden');
		await l.setOptions({ demo: false });
		assert.equal(vorschauAufrufe().length, 3);
		const q = query(aufrufe[2].url);
		assert.equal(q.has('demo'), false, 'echte Wetterdaten: kein demo-Parameter');
		assert.equal(q.get('type'), 'evening', 'der gewaehlte Berichtstyp bleibt erhalten');
		assert.equal(l.getState().options.demo, false);
	});

	test('route: Optionswechsel VOR dem ersten load() ruft nicht ab, load() nutzt die neue Option', async () => {
		// Adversary #2283 F004: ein Optionswechsel bei geschlossenem Reiter darf
		// nicht vorab laden (AC-9: kein Laden vor dem Oeffnen).
		const { createPreviewLoader } = await ladeModul();
		installiereNetz();
		const l = createPreviewLoader({ kind: 'route', id: 't-1', options: { type: 'morning', demo: true } });
		await l.setOptions({ type: 'evening' });
		await new Promise((r) => setImmediate(r));
		assert.equal(aufrufe.length, 0, `Optionswechsel vor dem Oeffnen hat abgerufen: ${JSON.stringify(aufrufe)}`);
		assert.equal(l.getState().status, 'idle');
		assert.equal(l.getState().options.type, 'evening');
		await l.load();
		assert.equal(vorschauAufrufe().length, 1);
		assert.equal(query(aufrufe[0].url).get('type'), 'evening');
	});

	test('vergleich: keine Berichtstyp-/Demo-/Datums-Parameter, Optionswechsel ruft nicht ab', async () => {
		const { createPreviewLoader } = await ladeModul();
		installiereNetz();
		const l = createPreviewLoader({
			kind: 'vergleich',
			id: 'cp-1',
			options: { type: 'evening', demo: true, date: '2026-10-20' }
		});
		await l.load();
		const q = query(aufrufe[0].url);
		assert.deepEqual([...q.keys()], ['kind'], `Vergleich darf nur ?kind=vergleich senden, bekam: ${aufrufe[0].url}`);
		await l.setOptions({ type: 'morning', demo: false });
		assert.equal(aufrufe.length, 1, 'im Vergleich gibt es nichts umzuschalten — kein Abruf');
	});
});

describe('Fehlerfall: ehrlicher Fehlerzustand, keine stille Wiederholung', () => {
	test('500 ⇒ status error mit Meldung, Kanal-/Ansichtswechsel bleibt ohne Abruf', async () => {
		const { createPreviewLoader } = await ladeModul();
		installiereNetz('fehler');
		const l = createPreviewLoader({ kind: 'vergleich', id: 'cp-1' });
		await l.load();
		const s = l.getState();
		assert.equal(s.status, 'error');
		assert.equal(s.data, null);
		assert.ok(s.error && s.error.length > 0, 'der Fehlerzustand braucht eine lesbare Meldung');
		l.setChannel('sms');
		l.setEmailView('mobile');
		await new Promise((r) => setImmediate(r));
		assert.equal(aufrufe.length, 1, 'nach einem Fehler darf ein Kanal-/Ansichtswechsel nicht still neu laden');
	});
});

describe('AC-15: Wartezeit — der Lader traegt das Budget der Vorschau (gestellte Uhr)', () => {
	const flush = () => new Promise((r) => setImmediate(r));

	async function budgetGrenze(kind: Kind, budgetMs: number): Promise<void> {
		const { createPreviewLoader } = await ladeModul();
		installiereNetz('nie');
		mock.timers.enable({ apis: ['setTimeout'] });
		try {
			const l = createPreviewLoader({ kind, id: 'e-1' });
			const laeuft = l.load();
			await flush();
			assert.equal(aufrufe.length, 1);
			mock.timers.tick(budgetMs - 1);
			await flush();
			assert.equal(l.getState().status, 'loading', `der ${kind}-Abruf wurde vor seinem Budget von ${budgetMs} ms abgebrochen`);
			mock.timers.tick(1);
			await flush();
			await flush();
			await laeuft;
			assert.equal(l.getState().status, 'error', `nach ${budgetMs} ms muss der ${kind}-Abruf im Zeitlimit enden`);
		} finally {
			mock.timers.reset();
		}
	}

	test('vergleich: 70 s (Go 60 s) — unveraendert gegenueber der alten Compare-Vorschau', async () => {
		await budgetGrenze('vergleich', 70_000);
	});

	test('route: Budget ZEITLIMIT_TRIP_VORSCHAU_MS aus api.ts', async () => {
		const api = (await import(API)) as { ZEITLIMIT_TRIP_VORSCHAU_MS?: number };
		assert.equal(typeof api.ZEITLIMIT_TRIP_VORSCHAU_MS, 'number', 'api.ts muss ZEITLIMIT_TRIP_VORSCHAU_MS exportieren');
		await budgetGrenze('route', api.ZEITLIMIT_TRIP_VORSCHAU_MS!);
	});
});
