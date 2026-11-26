// Issue #3020 R1 (Spec docs/specs/modules/rework_3020_altbausteine_entfernen.md, AC-2, AC-6): die Karte „Was steht wo“
// beim Laden, am lebenden Code. E040: vor der Antwort schreibt keine Bedienung (sonst ginge ein Stand aus Vorgaben
// über den gespeicherten). E043: gespeicherte Werte der Schalter werden so geladen, wie sie gespeichert sind (aus
// bleibt aus). E047/E054/E056: im Hub holt das Öffnen die Tabelle samt Legende genau einmal, mit der Art des Kontexts.
//
// Messweise: das ECHTE Instanz-Skript der Karte (tripMehrreiterPruefstand.bauen) mit der ECHTEN Speicherung
// (wasStehtWoSpeicherung, `api`, SaveStatus) gegen den Ersatz-Server; nur das GET der Tabelle beantwortet der Test.
// `$derived` wertet der Prüfstand einmal beim Aufbau aus: vor jeder Geste wird `aktFelder` wie im Baustein bestimmt.
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/was_steht_wo_karte_laden_3020.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { felderAusAntwort, type Felder } from '../../shared/wetter-tab/wasStehtWoSpeicherung.ts';
import { ohneTypen, werte } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Kontext = 'route' | 'vergleich';
const ID = 'abo-3020';
const PFAD: Record<Kontext, string> = { route: `/api/trips/${ID}`, vergleich: `/api/compare/presets/${ID}` };
const TABELLE = (context: Kontext) => `/api/briefings/${ID}/placements?kind=${context}`;
const ruhe = () => new Promise((r) => setTimeout(r, 20));

let server: FakeTripServer;
let gelesen: string[];
beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(ID, { id: ID, name: 'Abo 3020', display_config: { telegram_style: 'kurzform' }, report_config: { telegram_style: 'kurzform', show_stability: false }, hourly_enabled: false });
	// Das Profil (Telegram verbunden) führt der Ersatz-Server nicht; alles andere geht an ihn.
	const basis = globalThis.fetch;
	(globalThis as J).fetch = async (input: unknown, init?: RequestInit) =>
		String(input) === '/api/auth/profile' ? new Response('{"telegram_chat_id":"1"}', { status: 200 }) : basis(input as never, init);
	gelesen = [];
});
afterEach(() => server.restore());
const puts = () => server.calls.filter((c) => c.method !== 'GET');

const antwortFuer = (context: Kontext): J => ({
	...P.tabellenAntwort(context, { placements: { version: 1, rows: [{ metric_id: 'wind' }], outlook_reports: ['evening'] } }, ['wind'], { telegram_style: 'kurzform', show_stability: false, hourly: false }),
	legend: { metrics: [{ metric_id: 'wind', kuerzel: 'W-X', meaning: 'Bedeutung-X' }], fixed: [{ token: 'FEST-X', key: 'k', meaning: 'Fest-Bedeutung-X' }] }
});

/** Die Karte im Hub, geöffnet: ihre onMount-Aufrufe laufen wie beim Öffnen. */
async function oeffnen(context: Kontext, lesen: (pfad: string) => Promise<J>) {
	await api.get(PFAD[context]);
	server.calls.length = 0;
	const mounts: Array<() => unknown> = [];
	const ctl = P.erstelleController(ID, context === 'route' ? 'trip' : 'vergleich');
	const staende: J[] = [];
	const k = await P.bauen(P.DATEI.karte, {
		...P.LAUFZEIT,
		onMount: (fn: () => unknown) => void mounts.push(fn),
		api: {
			...api,
			get: (pfad: string) => {
				gelesen.push(pfad);
				return lesen(pfad);
			}
		},
		context,
		id: ID,
		saveController: ctl,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
		onAnlegeStand: (s: J) => staende.push(s)
	});
	// Der Prüfstand wertet nur Deklarationen aus: die onMount-Anweisungen des Skripts hier ausführen.
	for (const stmt of k.ast.instance.content.body as J[])
		if (stmt.type === 'ExpressionStatement' && stmt.expression?.callee?.name === 'onMount') werte(ohneTypen(k.quelle, stmt.expression), k.u);
	assert.equal(mounts.length, 1, 'Messaufbau: onMount der Karte nicht erfasst');
	for (const m of mounts) m();
	await ruhe();
	const u = k.u;
	const geste = (fn: () => void) => {
		u.aktFelder = u.felder ?? (u.antwort ? u.felderAusAntwort(u.antwort) : null);
		fn();
	};
	return {
		u,
		staende,
		schalten: (feld: string, wert: unknown) => geste(() => u.feld(feld, wert)),
		fertig: async () => {
			await P.fertig(ctl);
			await ruhe();
		}
	};
}

const SCHALTER: Record<Kontext, [string, unknown][]> = {
	route: [['telegram_style', 'rich'], ['telegram_style', 'kurzform'], ['show_stability', true], ['show_stability', false], ['show_night_block', false], ['email_format', 'compact']],
	vergleich: [['telegram_style', 'rich'], ['telegram_style', 'kurzform'], ['hourly_enabled', true], ['hourly_enabled', false], ['email_format', 'compact']]
};
const NIE = (): Promise<J> => new Promise<J>(() => {});
const KAPUTT = async (): Promise<J> => {
	throw Object.assign(new Error('kein Netz'), { status: 503 });
};

describe('E040: vor der Antwort der Tabelle schreibt die Karte nichts', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`vor der Antwort (laedt, fehler) schreibt ein Schalter nichts (${context})`, async () => {
			for (const [phase, lesen] of [['laedt', NIE], ['fehler', KAPUTT]] as const) {
				const k = await oeffnen(context, lesen);
				assert.equal(k.u.phase, phase, 'Messaufbau: Phase der Karte');
				const vorher = server.stand(ID);
				for (const [feld, wert] of SCHALTER[context]) {
					k.schalten(feld, wert);
					assert.equal(k.u.felder, null, `${phase}/${feld}: Schalterstand aus Vorgaben gebildet`);
					await k.fertig();
				}
				k.u.haken({ metrik: 'wind', stelle: 'telegram', an: false });
				k.u.format({ metrik: 'wind', stelle: 'telegram', format: 'raw' });
				k.u.reihenfolge(['wind']);
				k.u.ausblick('morning', true);
				await k.fertig();
				assert.deepEqual(puts().map((c) => [c.method, c.path]), [], `${phase}: Schreiben vor der Antwort`);
				assert.deepEqual(server.stand(ID), vorher, `${phase}: gespeicherter Stand verändert`);
				assert.deepEqual(k.staende, []);
			}
		});

		test(`Gegenprobe E040: nach der Antwort schreibt derselbe Schalter genau seinen Wert (${context})`, async () => {
			const k = await oeffnen(context, async () => antwortFuer(context));
			assert.equal(k.u.phase, 'bereit');
			k.schalten('telegram_style', 'rich');
			await k.fertig();
			assert.deepEqual(puts().map((c) => [c.method, c.path, c.status]), [['PUT', PFAD[context], 200]]);
			assert.deepEqual(puts()[0].anfrage, { [context === 'route' ? 'report_config' : 'display_config']: { telegram_style: 'rich' } });
		});
	}
});

// ── E043 ──────────────────────────────────────────────────────────────────────

/** Vorgaben des Python-Kerns (fehlender Wert). */
const VORGABE: Felder = {
	show_stage_stats: true,
	show_yesterday_comparison: true,
	show_night_block: true,
	show_compact_summary: true,
	show_stability: true,
	email_format: 'full',
	telegram_style: 'rich',
	hourly_enabled: true
};
/** Feld der Karte, Schlüssel in `blocks` der Antwort, speicherbare Werte. */
const LESEN: [keyof Felder, string, unknown[]][] = [
	['show_stage_stats', 'show_stage_stats', [true, false]],
	['show_yesterday_comparison', 'show_yesterday_comparison', [true, false]],
	['show_night_block', 'show_night_block', [true, false]],
	['show_compact_summary', 'show_compact_summary', [true, false]],
	['show_stability', 'show_stability', [true, false]],
	['email_format', 'email_format', ['full', 'compact']],
	['telegram_style', 'telegram_style', ['rich', 'kurzform']],
	['hourly_enabled', 'hourly', [true, false]]
];

describe('E043: gespeicherte Schalterwerte werden geladen, wie sie gespeichert sind (aus bleibt aus)', () => {
	test('messaufbau_jedes_feld_der_karte_ist_dabei', () => {
		assert.deepEqual(LESEN.map(([f]) => f).sort(), Object.keys(felderAusAntwort({ blocks: {} })).sort());
	});
	for (const [feld, schluessel, werte] of LESEN) {
		for (const wert of werte) {
			test(`felderAusAntwort: ${feld} gespeichert ${wert} bleibt ${wert}, fehlend gilt die Vorgabe`, () => {
				// Nur dieses Feld gespeichert: genau sein Wert, alle übrigen auf ihrer Vorgabe.
				assert.deepEqual(felderAusAntwort({ blocks: { [schluessel]: wert } }), { ...VORGABE, [feld]: wert });
				// Alle anderen gegen ihre Vorgabe gespeichert: dieses Feld fehlt und bleibt auf der Vorgabe.
				const gegen = Object.fromEntries(LESEN.filter(([f]) => f !== feld).map(([f, s, w]) => [s, w.find((x) => x !== VORGABE[f])]));
				assert.equal(felderAusAntwort({ blocks: gegen })[feld], VORGABE[feld]);
				assert.equal(felderAusAntwort({ blocks: { ...gegen, [schluessel]: wert } })[feld], wert);
			});
		}
	}
});

// ── E047, E054, E056 ──────────────────────────────────────────────────────────

describe('E047/E054/E056: Tabelle und Legende kommen im Hub mit einem Abruf', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`Hub: Öffnen holt die Tabelle genau einmal mit kind des Kontexts (${context})`, async () => {
			const k = await oeffnen(context, async () => antwortFuer(context));
			assert.deepEqual(gelesen, [TABELLE(context)]);
			assert.equal(k.u.phase, 'bereit');
			assert.deepEqual(k.u.lokal.rows.map((r: J) => r.metric_id), ['wind']);
			const legende = k.u.legendeAus(k.u.antwort, k.u.$t) as unknown;
			assert.ok(JSON.stringify(legende).includes('FEST-X'), `Legende ohne Eintrag der Antwort: ${JSON.stringify(legende)}`);
			assert.deepEqual(puts().map((c) => [c.method, c.path]), [], 'Öffnen schreibt nichts');
		});
	}
});
