// Issue #3020 R1, AC-2 (Ersatz für das mit #3357 gelöschte trip_versand_reiter_ohne_dauer_keepalive, #2317/#1376):
// Der lebende Reiter Zustellung speichert im Betrieb mit If-Match und OHNE keepalive; nur der Flush beim Verlassen
// der Seite geht mit keepalive raus (noch im selben Tick). Die Server-Antwort kommt bei der Seite an.
// Gemessen am ECHTEN Reiter (Instanz-Skript) über das echte `api` gegen den Ersatz-Server, Trip und Orte, beide
// Speicherteile (versand, alarme). Pfadregel #1409: alle Pfade relativ zu DIESER Datei.

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import type { ZustellungStand } from '../../shared/zustellung-tab/zustellungModell.ts';
import * as P from './tripMehrreiterPruefstand.ts';

type Rec = Record<string, unknown>;
let server: FakeTripServer;
beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
});
afterEach(() => server.restore());
const puts = () => server.calls.filter((c) => c.method === 'PUT');

const ORT_ID = 'cp-keepalive';
const ORT = { id: ORT_ID, name: 'Orte', location_ids: ['o1'], morning_time: '07:00:00', alert_quiet_from: '22:00', alert_quiet_to: '07:00' };

interface Mount {
	pfad: string;
	etag: string;
	ctl: ReturnType<typeof P.erstelleController>;
	uebernommen: Rec[];
	aendern(teil: Partial<ZustellungStand>): void;
}
const MOUNT: Record<'route' | 'vergleich', () => Promise<Mount>> = {
	async route() {
		server.seed(P.TRIP_ID, P.vollerTrip());
		await api.get(P.TRIP_PFAD);
		const a = P.neuerAufbau();
		const z = await P.zustellungReiter(a);
		return { pfad: P.TRIP_PFAD, etag: server.etagOf(P.TRIP_ID), ctl: a.ctl, uebernommen: a.updates, aendern: z.aendern };
	},
	async vergleich() {
		const pfad = `/api/compare/presets/${ORT_ID}`;
		await api.get(pfad);
		const ctl = P.erstelleController(ORT_ID, 'vergleich');
		const uebernommen: Rec[] = [];
		const inst = await P.bauen(P.DATEI.zustellung, {
			...P.LAUFZEIT,
			context: 'vergleich',
			panel: { preset: ORT, saveController: ctl, enqueueHubWrite: <T>(fn: () => Promise<T>) => fn(), onCompareUpdate: (p: Rec) => uebernommen.push(p) }
		});
		return { pfad, etag: server.etagOf(ORT_ID), ctl, uebernommen, aendern: (teil) => inst.u.aendern({ ...inst.u.stand, ...teil }) };
	}
};
const GESTEN: [string, Partial<ZustellungStand>][] = [
	['versand (Morgenzeit)', { morgenZeit: '08:00' }],
	['alarme (Stille Stunden aus)', { stilleAn: false }]
];

for (const [name, mount] of Object.entries(MOUNT)) {
	describe(`${name}: Reiter Zustellung speichert ohne Dauer-keepalive`, () => {
		for (const [teil, geste] of GESTEN) {
			test(`${name} ${teil}: regulär mit If-Match und ohne keepalive, die Antwort kommt bei der Seite an`, async () => {
				const m = await mount();
				m.aendern(geste);
				await P.fertig(m.ctl);
				assert.deepEqual(puts().map((p) => [p.path, p.status, p.keepalive, p.ifMatch]), [[m.pfad, 200, false, m.etag]]);
				assert.deepEqual(m.uebernommen, [puts()[0].body]);
				assert.equal(m.ctl.state, 'idle');
			});

			test(`${name} ${teil}: Verlassen der Seite sendet die ausstehende Eingabe im selben Tick mit keepalive`, async () => {
				const m = await mount();
				m.aendern(geste);
				assert.deepEqual(puts(), [], 'Vorbedingung: entprellt, noch nichts gesendet');
				const flush = m.ctl.flush({ keepalive: true });
				assert.deepEqual(puts().map((p) => [p.path, p.keepalive]), [[m.pfad, true]], 'nach dem Entladen ginge nichts mehr raus');
				await flush;
				assert.equal(puts().length, 1);
			});

			test(`${name} ${teil}: nach dem keepalive-Flush speichert der nächste Vorgang wieder ohne keepalive`, async () => {
				const m = await mount();
				m.aendern(geste);
				await m.ctl.flush({ keepalive: true });
				m.aendern({ abendZeit: '20:00' });
				await P.fertig(m.ctl);
				assert.deepEqual(puts().map((p) => p.keepalive), [true, false]);
			});
		}

		test(`${name}: Verlassen ohne Eingabe sendet nichts`, async () => {
			const m = await mount();
			await m.ctl.flush({ keepalive: true });
			assert.deepEqual(puts(), []);
		});
	});
}
