// Issue #3020 R1 (G16, G51): scheitert das Laden des Reiters Wetter im Trip, zeigt er die Fehlerphase und speichert
// nichts (Hub und Anlegen); „Erneut laden“ heilt. Orte: fixloop4_vergleich_katalog_ladefehler.test.ts.
//
// Gemessen im ECHTEN Instanz-Skript von WetterTabInhalt.svelte; Katalog und Vorlagen live aus dem Python-Core.
// Zwei Nutzer mit verschiedenen Trips (Hub: A, Anlegen: B).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/trip_ladefehler_schreibt_nicht_3020.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { umgebungFuer, type Knoten } from '../../__tests__/svelteInstanzPruefstand.ts';
import { aufloesungPost, live } from './wetterTabDaten.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const WETTER_TAB = join(HIER, '..', '..', '..', 'organisms', 'wetter-tab', 'WetterTabInhalt.svelte');

const trip = (id: string, metriken: string[]) => ({
	id,
	name: id,
	stages: [],
	display_config: { metrics: metriken.map((metric_id, order) => ({ metric_id, enabled: true, bucket: 'primary', order })) },
	report_config: {}
});

async function reiter(createMode: boolean, t: Knoten) {
	const mit = { katalogOk: false, geplant: [] as unknown[], gemeldet: [] as unknown[], geschrieben: [] as string[] };
	const schreibend = (art: string) => async (pfad: string) => {
		mit.geschrieben.push(`${art} ${pfad}`);
		return {};
	};
	const api = {
		get: async (pfad: string) => {
			if (pfad === '/api/metrics') {
				if (!mit.katalogOk) throw Object.assign(new Error('kaputt'), { status: 503 });
				return live().metrics;
			}
			if (pfad === '/api/templates') return live().templates;
			if (pfad === '/api/metric-presets') return [];
			throw new Error(`unerwartet: ${pfad}`);
		},
		put: schreibend('PUT'),
		// #2988: der POST der Ampel-Auflösung liest nur; jeder andere POST zählt als Schreibvorgang.
		post: (pfad: string, rumpf?: unknown) => (pfad === '/api/ampel/aufloesung' ? aufloesungPost()(pfad, rumpf) : schreibend('POST')(pfad))
	};
	const { u } = await umgebungFuer(WETTER_TAB, {
		context: 'route',
		trip: structuredClone(t),
		preset: undefined,
		createMode,
		saveController: { schedule: (...a: unknown[]) => void mit.geplant.push(a), cancel: () => {} },
		enqueueHubWrite: undefined,
		onTripUpdate: (x: unknown) => mit.gemeldet.push(x),
		onCompareUpdate: undefined,
		onAnlegeStand: (x: unknown) => mit.gemeldet.push(x),
		api
	});
	return { u, mit };
}

describe('#3020 G16/G51: Ladefehler im Reiter Wetter (Trip)', () => {
	test('Trip: Laden scheitert — Fehlerphase, kein Stand, kein Speichervorgang; „Erneut laden“ heilt', async () => {
		const A = trip('trip-a-3020', ['wind', 'thunder', 'gust']);
		const B = trip('trip-b-3020', ['thunder', 'precipitation']);
		for (const [wo, createMode, abo] of [['Hub', false, A], ['Anlegen', true, B]] as const) {
			const { u, mit } = await reiter(createMode, abo);
			await u.laden();
			assert.equal(u.phase, 'fehler', `${wo}: Ladefehler wird verschluckt`);
			assert.deepEqual([u.stand, u.daten], [null, null], `${wo}: der Reiter hydriert trotz Ladefehler`);
			assert.deepEqual([mit.geplant, mit.gemeldet, mit.geschrieben], [[], [], []], `${wo}: Speichervorgang trotz Ladefehler`);

			mit.katalogOk = true; // „Erneut laden"
			await u.laden();
			assert.equal(u.phase, 'bereit', `${wo}: „Erneut laden“ heilt nicht`);
			const soll = abo.display_config.metrics.map((m) => m.metric_id);
			assert.deepEqual(u.stand.auswahl, soll, `${wo}: gespeicherte Auswahl des Trips`);
			// Anlegen meldet genau den Anfangsstand, der Hub nichts; geschrieben wird in keinem der beiden.
			assert.equal(mit.gemeldet.length, createMode ? 1 : 0, wo);
			assert.deepEqual([mit.geplant, mit.geschrieben], [[], []], wo);

			// Die Gewitterzeile ist bedienbar: „Alarm ab“ geht genau einmal an den Speicherer.
			assert.equal(u.daten.eig.thunder.allowed_sides, 'level', 'Messaufbau: Gewitter ist die Stufen-Zeile');
			u.grenzenUmschalten('thunder');
			assert.equal(u.offen, 'thunder');
			u.gewitterWahl('mittel', u.stand.ampel.thunder?.mittel === 'orange' ? 'yellow' : 'orange');
			assert.equal(u.fertig(), true);
			assert.equal(createMode ? mit.gemeldet.length : mit.geplant.length, createMode ? 2 : 1, `${wo}: Bedienung der Gewitterzeile kommt nicht an`);
		}
	});
});
