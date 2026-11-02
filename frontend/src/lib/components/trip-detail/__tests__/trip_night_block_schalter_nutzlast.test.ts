// TDD RED — Issue #1721 (Epic #2259): Schalter "Nacht-Stundentabelle in der Mail zeigen".
//
// Spec: docs/specs/modules/fix_1721_nachtausgabe.md — AC-2, AC-3, AC-6 (Nutzlast-Teil).
//
// Gemessen wird der ANFRAGE-Rumpf, den der ECHTE Wetter-Metriken-Reiter an den
// Ersatz-Server schickt (gleicher Pruefstand wie trip_reiter_nutzlast_nur_eigene_felder).
// Zielschnittstelle (existiert noch NICHT -> RED): Instanz-Variable `showNightBlock`
// im Reiter `WeatherMetricsTab.svelte`; Schluessel `show_night_block` in
// `WETTER_DISPLAY_KEYS`.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/trip-detail/__tests__/trip_night_block_schalter_nutzlast.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import * as P from './tripMehrreiterPruefstand.ts';

let server: FakeTripServer;

afterEach(() => server.restore());

async function start(trip: Record<string, unknown>): Promise<void> {
	clearEtagRegistry();
	server = createFakeTripServer({ merge: true });
	server.install();
	server.seed(P.TRIP_ID, trip);
	await api.get(P.TRIP_PFAD);
}

const puts = () => server.calls.filter((c) => c.method === 'PUT');
const weatherConfigBody = (): Record<string, unknown> => {
	const p = puts().find((c) => /\/weather-config$/.test(c.path));
	assert.ok(p, `Messaufbau: kein PUT /weather-config (gesehen: ${puts().map((c) => c.path).join(', ')})`);
	return p.anfrage as Record<string, unknown>;
};

function tripMitNachtBlock(wert: boolean | undefined): Record<string, unknown> {
	const t = P.vollerTrip();
	const dc = { ...(t.display_config as Record<string, unknown>) };
	if (wert === undefined) delete dc.show_night_block;
	else dc.show_night_block = wert;
	return { ...t, display_config: dc };
}

describe('AC-3: Schalter aus -> false geht als bewusster Wert durch', () => {
	test('Nutzer legt den Schalter auf aus: /weather-config traegt show_night_block=false', async () => {
		await start(tripMitNachtBlock(true));
		const a = P.neuerAufbau(tripMitNachtBlock(true));
		const wm = await P.wetterMetrikenReiter(a);
		wm.inst.u.showNightBlock = false;
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		assert.equal(weatherConfigBody().show_night_block, false, '/weather-config muss show_night_block=false senden');
	});
});

describe('AC-2: Alt-Trip ohne Feld bekommt beim Speichern keinen neuen Wert', () => {
	test('Alt-Trip: Schalter steht auf an (Standard true)', async () => {
		await start(tripMitNachtBlock(undefined));
		const a = P.neuerAufbau(tripMitNachtBlock(undefined));
		const wm = await P.wetterMetrikenReiter(a);
		assert.equal(wm.inst.u.showNightBlock, true, 'ohne gespeichertes Feld gilt "an" (wie loader.py)');
	});

	test('Alt-Trip: andere Metrik speichern sendet show_night_block NICHT', async () => {
		await start(tripMitNachtBlock(undefined));
		const a = P.neuerAufbau(tripMitNachtBlock(undefined));
		const wm = await P.wetterMetrikenReiter(a);
		assert.equal(wm.inst.u.showNightBlock, true, 'Vorbedingung: Schalter-Variable existiert (Standard an)');
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		assert.ok(
			!('show_night_block' in weatherConfigBody()),
			'ohne gespeicherten Wert und ohne Nutzergeste darf der Schluessel nicht gesendet werden'
		);
	});

	test('Trip mit gespeichertem Wert: der Wert wird beim Speichern mitgegeben', async () => {
		await start(tripMitNachtBlock(true));
		const a = P.neuerAufbau(tripMitNachtBlock(true));
		const wm = await P.wetterMetrikenReiter(a);
		wm.metrikenSpeichern();
		await P.fertig(a.ctl);

		assert.equal(weatherConfigBody().show_night_block, true);
	});
});

describe('AC-6: nur der Wetter-Metriken-Reiter ist Eigentuemer des Feldes', () => {
	test('Alarme-Reiter sendet show_night_block nie', async () => {
		await start(tripMitNachtBlock(false));
		const a = P.neuerAufbau(tripMitNachtBlock(false));
		const alarme = await P.alarmeReiter(a);
		alarme.empfindlichkeitAendern('wind', 'sensibel');
		await P.fertig(a.ctl);

		assert.ok(puts().length > 0, 'Messaufbau: es gab einen PUT');
		for (const p of puts()) {
			const dc = ((p.anfrage as Record<string, unknown>).display_config ?? {}) as Record<string, unknown>;
			assert.ok(!('show_night_block' in dc), 'Alarme darf show_night_block nie senden');
		}
	});

	test('Versand-Reiter sendet show_night_block nie', async () => {
		await start(tripMitNachtBlock(false));
		const a = P.neuerAufbau(tripMitNachtBlock(false));
		const v = await P.versandReiter(a);
		v.aendern({ morning_time: '06:30' });
		await P.fertig(a.ctl);

		for (const p of puts()) {
			const dc = ((p.anfrage as Record<string, unknown>).display_config ?? {}) as Record<string, unknown>;
			assert.ok(!('show_night_block' in dc), 'Versand darf show_night_block nie senden');
		}
	});
});
