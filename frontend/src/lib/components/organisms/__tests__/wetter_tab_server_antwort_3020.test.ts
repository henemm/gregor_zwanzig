// Issue #3020 R1 (E005; Spec docs/specs/modules/rework_3020_altbausteine_entfernen.md, AC-6): nach dem Speichern reicht
// der Reiter Wetter genau die Server-Antwort an die Seite (#850: Alarmregeln und alles andere danach frisch), beim Trip an
// `onTripUpdate`, bei Orten an `onCompareUpdate`.
//
// Messweise: das ECHTE Instanz-Skript von WetterTabInhalt.svelte (tripMehrreiterPruefstand), echter Speicherer, echtes
// `api` gegen den Ersatz-Server. Der Server-Stand trägt Felder, die kein Rumpf des Reiters sendet; nur die Antwort kennt
// sie. Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_server_antwort_3020.test.ts

import { test, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { live, liveVergleichsKatalog } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
type Kontext = 'route' | 'vergleich';
const kopie = (x: J): J => JSON.parse(JSON.stringify(x));

const PRESET_ID = 'cp-3020-antwort';
const ABO: Record<Kontext, { id: string; pfad: string; doc: () => J }> = {
	route: { id: P.TRIP_ID, pfad: P.TRIP_PFAD, doc: () => ({ ...P.vollerTrip(), alert_rules: [{ id: 'r-server', metric: 'wind' }] }) },
	vergleich: {
		id: PRESET_ID,
		pfad: `/api/compare/presets/${PRESET_ID}`,
		doc: () => ({
			id: PRESET_ID,
			name: 'Orte 3020',
			alert_rules: [{ id: 'r-server', metric: 'wind' }],
			location_ids: ['o1', 'o2'],
			display_config: {
				active_metrics: ['temperature', 'wind'].map((metric_id) => ({ metric_id, aggregation: 'max' })),
				ampel: { template: 'allgemein' },
				metric_alert_levels: { wind: 'HIGH' }
			}
		})
	}
};

let server: FakeTripServer;
beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	// Der Ersatz-Server mischt Orts-Abos nicht; die Antwort des echten Servers trägt immer das ganze Abo.
	const basis = globalThis.fetch;
	antworten = [];
	(globalThis as J).fetch = async (input: unknown, init?: RequestInit) => {
		const r = await basis(input as never, init);
		if (init?.method !== 'PUT' || r.status !== 200) return r;
		let koerper: J = await r.json();
		if (String(input) === ABO.vergleich.pfad) {
			const doc = ABO.vergleich.doc();
			koerper = { ...doc, ...koerper, display_config: { ...doc.display_config, ...koerper.display_config } };
		}
		antworten.push(koerper);
		return new Response(JSON.stringify(koerper), { status: 200, headers: r.headers });
	};
});
afterEach(() => server.restore());
const puts = () => server.calls.filter((c) => c.method === 'PUT');
/** Server-Antworten auf PUTs, in Reihenfolge. */
let antworten: J[] = [];

/** Reiter Wetter des Abos, geladen; beide Rückkanäle der Seite werden mitgeschnitten. */
async function reiter(context: Kontext) {
	const { id, pfad, doc } = ABO[context];
	server.seed(id, doc());
	const abo = doc();
	await api.get(pfad);
	const ctl = P.erstelleController(id, context === 'route' ? 'trip' : 'vergleich');
	const gemeldet: { onTripUpdate: J[]; onCompareUpdate: J[] } = { onTripUpdate: [], onCompareUpdate: [] };
	const inst = await P.bauen(P.DATEI.wetter, {
		...P.LAUFZEIT,
		context,
		[context === 'route' ? 'trip' : 'preset']: abo,
		createMode: false,
		saveController: ctl,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(),
		onTripUpdate: (t: J) => gemeldet.onTripUpdate.push(kopie(t)),
		onCompareUpdate: (p: J) => gemeldet.onCompareUpdate.push(kopie(p))
	});
	const daten = { '/api/metrics': live().metrics, '/api/templates': live().templates, '/api/metric-presets': [], '/api/compare/metrics': liveVergleichsKatalog() };
	await P.mitAntworten(daten, () => inst.u.laden());
	assert.equal(inst.u.phase, 'bereit', `Messaufbau: Reiter Wetter (${context}) nicht geladen`);
	return { inst, gemeldet, fertig: () => P.fertig(ctl) };
}

test('Reiter Wetter (Trip) reicht genau die Server-Antwort an onTripUpdate, Orte an onCompareUpdate', async () => {
	for (const [context, ziel, anderes] of [['route', 'onTripUpdate', 'onCompareUpdate'], ['vergleich', 'onCompareUpdate', 'onTripUpdate']] as const) {
		const m = await reiter(context);
		m.inst.u.hinzufuegen('gust');
		await m.fertig();
		const letzter = puts().at(-1)!;
		assert.deepEqual([letzter.path, letzter.status], [ABO[context].pfad, 200], `${context}: letzter PUT`);
		assert.deepEqual(m.gemeldet[ziel], [antworten.at(-1)], `${context}: die Seite bekommt nicht genau die Server-Antwort`);
		assert.deepEqual(m.gemeldet[anderes], [], `${context}: falscher Rückkanal`);
		// Aus der Antwort, nicht aus dem Rumpf: diese Felder sendet der Reiter nie.
		const a = m.gemeldet[ziel][0];
		assert.equal('name' in (letzter.anfrage as object), false, 'Messaufbau: der Rumpf trägt den Namen');
		assert.equal(a.name, ABO[context].doc().name);
		assert.deepEqual(a.alert_rules, [{ id: 'r-server', metric: 'wind' }], `${context}: Alarmregeln fehlen in der Meldung`);
		assert.deepEqual(a.display_config.metric_alert_levels, ABO[context].doc().display_config.metric_alert_levels);
		server.calls.length = 0;
	}
});

test('Gegenprobe E005: Öffnen ohne Änderung meldet der Seite nichts', async () => {
	for (const context of ['route', 'vergleich'] as const) {
		const m = await reiter(context);
		await m.fertig();
		assert.deepEqual(m.gemeldet, { onTripUpdate: [], onCompareUpdate: [] });
		assert.deepEqual(puts(), []);
	}
});
