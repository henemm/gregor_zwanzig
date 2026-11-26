// Issue #3020 R1 (E101 bis E105; Spec docs/specs/modules/rework_3020_altbausteine_entfernen.md, AC-6) — Vorlage im
// Reiter Wetter und Fortbewegung des Trips (#3196 AC-7).
//   E102 (gilt heute, muss halten): Bearbeiten eines Trips mit Fortbewegung Rad lässt Vorlage und Metrikwahl stehen,
//        das Öffnen schreibt nichts.
//   E101, E103 bis E105 (ausstehend, `todo`): beim Anlegen folgt die Vorlage der Fortbewegung — gilt am lebenden
//        Reiter nicht (#3358), hier nicht behoben.
//
// Messweise: das ECHTE Instanz-Skript von WetterTabInhalt.svelte (tripMehrreiterPruefstand) mit den echten Antworten
// von /api/metrics und /api/templates; im Bearbeiten samt echter Karte, echtem Speicherer und Ersatz-Server.
// Den Trip mit `tempo` reicht der Anlege-Editor dem Reiter als `trip` (`wetterAnlegeTrip`).
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/vorlage_folgt_fortbewegung_3358.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { effekteVon } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';
import * as P from '../../trip-detail/__tests__/tripMehrreiterPruefstand.ts';

type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any

const daten = (): Record<string, unknown> => ({ '/api/metrics': live().metrics, '/api/templates': live().templates, '/api/metric-presets': [] });
/** Ohne abgeleitete Kinder (Temperatur), damit genau die gespeicherte Wahl in der Auswahl steht. */
const WAHL = ['gust', 'visibility', 'uv_index'];

let server: FakeTripServer;
beforeEach(() => {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
});
afterEach(() => server.restore());
const schreibend = () => server.calls.filter((c) => c.method !== 'GET');

function tripMitRad(): J {
	const doc: J = P.vollerTrip();
	doc.tempo = { fortbewegung: 'rad', grundtempo_kmh: 15 };
	doc.display_config = {
		...doc.display_config,
		ampel: { template: 'alpen-trekking' },
		metrics: [
			...WAHL.map((metric_id) => ({ metric_id, enabled: true, aggregations: ['max'] })),
			{ metric_id: 'wind', enabled: false, aggregations: ['max'] }
		]
	};
	return doc;
}
const gewaehlt = (metrics: J[]): string[] => metrics.filter((m) => m.enabled).map((m) => m.metric_id);

describe('E102: Bearbeiten, die Fortbewegung fasst die gespeicherte Wahl nicht an', () => {
	async function offen() {
		const doc = tripMitRad();
		server.seed(P.TRIP_ID, doc);
		await api.get(P.TRIP_PFAD);
		const ctl = P.erstelleController();
		const inst = await P.bauen(P.DATEI.wetter, { ...P.LAUFZEIT, context: 'route', trip: doc, createMode: false, saveController: ctl });
		await P.mitAntworten(daten(), () => inst.u.laden());
		assert.equal(inst.u.phase, 'bereit', 'Messaufbau: Reiter Wetter nicht geladen');
		for (const e of effekteVon(inst.ast, inst.quelle, inst.u)) e();
		await P.karteImReiter(inst, () => P.tabellenAntwort('route', doc.display_config, WAHL));
		await P.fertig(ctl);
		return { inst, ctl };
	}

	test('Bearbeiten, Trip mit tempo Rad: Metrikwahl bleibt, Öffnen löst keinen PUT aus', async () => {
		const vorher = tripMitRad();
		const { inst } = await offen();
		assert.deepEqual([...inst.u.stand.auswahl], WAHL);
		assert.equal(inst.u.stand.vorlageId, 'alpen-trekking');
		assert.deepEqual(schreibend().map((c) => [c.method, c.path]), [], 'Öffnen schreibt');
		assert.deepEqual(server.stand(P.TRIP_ID), vorher, 'gespeicherter Trip verändert');
	});

	test('Gegenprobe E102: eine andere Änderung danach speichert Vorlage und Metrikwahl unverändert mit', async () => {
		const { inst, ctl } = await offen();
		inst.u.aendern({ ...inst.u.stand, tagesfenster: { start: 6, end: 20 } });
		await P.fertig(ctl);
		assert.deepEqual(schreibend().map((c) => [c.path, c.status]), [[`${P.TRIP_PFAD}/weather-config`, 200], [P.TRIP_PFAD, 200]]);
		const dc = server.stand(P.TRIP_ID).display_config as J;
		assert.deepEqual(gewaehlt(dc.metrics), WAHL);
		assert.equal(dc.ampel.template, 'alpen-trekking');
	});
});

describe('E101, E103 bis E105: Anlegen, die Vorlage folgt der Fortbewegung', () => {
	const FAELLE = [['fuss', 'alpen-trekking', 'ski', 4], ['rad', 'radtour', 'fuss', 15], ['mtb', 'radtour', 'ski', 10], ['ski', 'skitouren', 'rad', 3]] as const;
	for (const [f, vorlage, danach, kmh] of FAELLE) {
		test(`Anlegen: Fortbewegung ${f} ⇒ Vorlage ${vorlage}; ungesicherte Wahl bleibt`, { todo: 'Fehler #3358: der Reiter Wetter liest die Fortbewegung nicht' }, async () => {
			const staende: J[] = [];
			const trip: J = { id: '__new__', name: 'Neu', stages: [], tempo: { fortbewegung: f, grundtempo_kmh: kmh }, display_config: { channels: { email: true } } };
			const inst = await P.bauen(P.DATEI.wetter, { ...P.LAUFZEIT, context: 'route', trip, createMode: true, onAnlegeStand: (s: J) => staende.push(s) });
			const effekte = () => {
				for (const e of effekteVon(inst.ast, inst.quelle, inst.u)) e();
			};
			await P.mitAntworten(daten(), () => inst.u.laden());
			assert.equal(inst.u.phase, 'bereit', 'Messaufbau: Reiter Wetter nicht geladen');
			effekte();
			const soll = live().templates.find((t) => t.id === vorlage)!.ampel.metrics as Record<string, { enabled?: boolean }>;
			assert.equal(inst.u.stand.vorlageId, vorlage);
			assert.equal(staende.at(-1)?.weatherConfig.ampel.template, vorlage, 'der Anlege-POST trägt die Vorlage');
			for (const [id, m] of Object.entries(soll)) if (m.enabled) assert.ok(inst.u.stand.auswahl.includes(id), `${id} der Vorlage fehlt in der Auswahl`);
			// Ungesicherte Wahl des Nutzers: ein späterer Wechsel der Fortbewegung wirft sie nicht weg.
			inst.u.entfernen('wind');
			const wahl = [...inst.u.stand.auswahl];
			inst.u.trip = { ...trip, tempo: { fortbewegung: danach, grundtempo_kmh: 4 } };
			effekte();
			assert.deepEqual([...inst.u.stand.auswahl], wahl);
			assert.equal(inst.u.stand.vorlageId, vorlage);
			assert.deepEqual(schreibend(), []);
		});
	}
});
