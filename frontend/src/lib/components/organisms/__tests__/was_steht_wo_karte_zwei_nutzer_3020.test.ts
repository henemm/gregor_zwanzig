// Issue #3020 R1, G40 und Katalog E-R8-T1-SMS-LADEN-A/-B (Ersatz für das mit #3357 gelöschte
// lade_kanal_layouts_aus_trip, #3047 R8 T1): die Karte „Was steht wo“ zeigt beim Laden die GESPEICHERTE SMS-Auswahl,
// Folge und Roh/Einfach-Form des eigenen Abos — zwei Nutzer mit verschiedenen Abos, keine Werte des anderen.
// Messweise: ECHTES Instanz-Skript der Karte, ECHTER Ladeweg (`tabelle.laden` über das echte `api`), gezeigt wird mit
// der ECHTEN Ansicht (metrikenAus). Der Ersatz-Server antwortet nur auf den Pfad des jeweiligen Abos.
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { tr } from '../../../i18n/index.ts';
import { metrikenAus } from '../../shared/wetter-tab/wasStehtWoAnsicht.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Zeile = { id: string; sms: boolean; format: 'raw' | 'simplified' };

/** Gespeicherte Tabelle je Nutzer: eigene Folge, eigene SMS-Haken, eigene Form in der E-Mail. */
const ABO: Record<'trip-anna' | 'trip-bruno', Zeile[]> = {
	'trip-anna': [
		{ id: 'precipitation', sms: true, format: 'simplified' },
		{ id: 'wind', sms: true, format: 'raw' },
		{ id: 'cloud_total', sms: true, format: 'simplified' },
		{ id: 'gust', sms: false, format: 'simplified' }
	],
	'trip-bruno': [
		{ id: 'cloud_total', sms: true, format: 'raw' },
		{ id: 'gust', sms: true, format: 'raw' },
		{ id: 'wind', sms: false, format: 'simplified' }
	]
};
const tabelle = (zeilen: Zeile[]) => ({
	version: 1,
	rows: zeilen.map((z) => ({ metric_id: z.id, ...(z.sms ? {} : { places: { sms: false } }), formats: { email: z.format } })),
	outlook_reports: []
});
const antwort = (zeilen: Zeile[], stored = true) => ({
	kind: 'route',
	stored,
	placements: tabelle(zeilen),
	columns: [{ stelle: 'email' }, { stelle: 'sms' }],
	rows: zeilen.map((z) => ({ metric_id: z.id, name: z.id, cells: { email: { state: 'on', format: z.format }, sms: { state: z.sms ? 'on' : 'off' } } })),
	outlook_reports: [],
	fixed_rows: [],
	blocks: {}
});

const basisFetch = globalThis.fetch;
let antworten: Record<string, J> = {};
/** Verzögerung der nächsten Antworten je Pfad (ms). */
let verzoegert: number[] = [];
beforeEach(() => {
	clearEtagRegistry();
	verzoegert = [];
	antworten = Object.fromEntries(Object.entries(ABO).map(([id, z]) => [`/api/briefings/${id}/placements?kind=route`, antwort(z)]));
	(globalThis as { fetch: unknown }).fetch = async (input: unknown) => {
		const a = antworten[String(input)];
		const ms = verzoegert.shift() ?? 0;
		if (ms) await new Promise((r) => setTimeout(r, ms));
		return a ? new Response(JSON.stringify(a), { status: 200, headers: { 'Content-Type': 'application/json' } }) : new Response('{}', { status: 404 });
	};
});
afterEach(() => {
	(globalThis as { fetch: unknown }).fetch = basisFetch;
});

const karte = (id: string) => P.bauen(P.DATEI.karte, { ...P.LAUFZEIT, context: 'route', id, saveController: P.erstelleController(id) });
async function geladen(id: string): Promise<P.Instanz> {
	const k = await karte(id);
	await k.u.laden();
	assert.equal(k.u.phase, 'bereit', `Messaufbau: Karte ${id} hat nicht geladen`);
	return k;
}
/** Was die Karte zeigt: Zeilenfolge, SMS-Haken, Form der E-Mail-Zelle. */
const gezeigt = (k: P.Instanz): Zeile[] =>
	metrikenAus(k.u.antwort, tr as never).map((m) => ({ id: m.id, sms: m.zellen.sms.zustand === 'on', format: m.zellen.email.format as Zeile['format'] }));

describe('G40: die Karte lädt die gespeicherte SMS-Auswahl des eigenen Abos', () => {
	test('Nutzer A: SMS-Spalte zeigt gespeicherte Auswahl, Folge und Roh/Einfach', async () => {
		const a = await geladen('trip-anna');
		assert.deepEqual(gezeigt(a), ABO['trip-anna']);
		assert.deepEqual(JSON.parse(JSON.stringify(a.u.placementsZumMitspeichern())), tabelle(ABO['trip-anna']));
		assert.equal(metrikenAus(a.u.antwort, tr as never)[0].zellen.sms.format, null, 'in der SMS gibt es kein Roh/Einfach');
	});

	test('Nutzer B: eigene SMS-Spalte, keine Werte von Nutzer A', async () => {
		const a = await geladen('trip-anna');
		const b = await geladen('trip-bruno');
		assert.deepEqual(gezeigt(b), ABO['trip-bruno']);
		assert.deepEqual(JSON.parse(JSON.stringify(b.u.placementsZumMitspeichern())), tabelle(ABO['trip-bruno']));
		assert.ok(!JSON.stringify([b.u.antwort, b.u.lokal]).includes('precipitation'), 'eine Zeile von Nutzer A steht in der Karte von Nutzer B');
		assert.deepEqual(gezeigt(a), ABO['trip-anna'], 'das Laden von Nutzer B ändert die Karte von Nutzer A nicht');
	});

	test('eine ältere, verspätete Antwort ersetzt die neuere nicht', async () => {
		const k = await karte('trip-anna');
		const pfad = '/api/briefings/trip-anna/placements?kind=route';
		antworten[pfad] = antwort([...ABO['trip-anna']].reverse());
		verzoegert = [40];
		const alt = k.u.laden();
		await new Promise((r) => setTimeout(r, 5));
		antworten[pfad] = antwort(ABO['trip-anna']);
		await k.u.laden();
		await alt;
		assert.deepEqual(gezeigt(k), ABO['trip-anna']);
	});

	test('ohne gespeicherte Tabelle: Haken aus der Antwort, nichts zum Mitspeichern', async () => {
		antworten['/api/briefings/trip-anna/placements?kind=route'] = antwort(ABO['trip-anna'], false);
		const a = await geladen('trip-anna');
		assert.deepEqual(gezeigt(a), ABO['trip-anna']);
		assert.equal(a.u.placementsZumMitspeichern(), undefined);
	});
});
