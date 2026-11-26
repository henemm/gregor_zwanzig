// TDD RED — Issue #1721 (Epic #2259): Schalter "Nacht-Stundentabelle in der Mail zeigen".
//
// Spec: docs/specs/modules/fix_1721_nachtausgabe.md — AC-2, AC-3, AC-6 (Nutzlast-Teil).
//
// Gemessen werden der ANFRAGE-Rumpf der ECHTEN Karte „Was steht wo“ bzw. der ECHTEN Reiter am
// Ersatz-Server und der Server-Stand danach (gleicher Pruefstand wie trip_reiter_nutzlast_nur_eigene_felder).
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

const serverNachtBlock = () => (server.stand(P.TRIP_ID).display_config as Record<string, unknown>).show_night_block;

// #3020 R1: den Schalter schaltet seit #3122 die Karte „Was steht wo“ (wasStehtWoSpeicherung), gespeichert als
// Teilfeld-PUT `{ display_config: { show_night_block } }`. Die Faelle messen die ECHTE Karte bzw. die ECHTEN Reiter.

describe('AC-3: Schalter aus -> false geht als bewusster Wert durch', () => {
	for (const vorher of [true, undefined]) {
		test(`Geste an der Karte (gespeichert: ${vorher ?? 'kein Feld'}): genau { display_config: { show_night_block: false } }`, async () => {
			await start(tripMitNachtBlock(vorher));
			const a = P.neuerAufbau(tripMitNachtBlock(vorher));
			(await P.karteWasStehtWo(a)).schalten('show_night_block', false);
			await P.fertig(a.ctl);
			assert.deepEqual(puts().map((c) => [c.path, c.anfrage]), [[P.TRIP_PFAD, { display_config: { show_night_block: false } }]]);
			assert.equal(serverNachtBlock(), false);
		});
	}

	test('Gespeichertes aus wieder an: true geht als bewusster Wert durch', async () => {
		await start(tripMitNachtBlock(false));
		const a = P.neuerAufbau(tripMitNachtBlock(false));
		(await P.karteWasStehtWo(a)).schalten('show_night_block', true);
		await P.fertig(a.ctl);
		assert.equal(serverNachtBlock(), true);
	});
});

describe('AC-2: gespeicherter Wert wird gezeigt und bleibt bei jedem anderen Speichern stehen', () => {
	/** Anzeige-Stand der Karte (`aktFelder`), wie der Baustein ihn aus der Antwort bildet. */
	const anzeige = (k: { inst: P.Instanz }) => k.inst.u.felderAusAntwort(k.inst.u.antwort).show_night_block;

	test('Alt-Trip: Schalter steht auf an (Standard true)', async () => {
		await start(tripMitNachtBlock(undefined));
		const k = await P.karteWasStehtWo(P.neuerAufbau(tripMitNachtBlock(undefined)));
		assert.equal(anzeige(k), true, 'ohne gespeichertes Feld gilt "an" (wie loader.py)');
	});

	/** Ein Vorgang je lebendem Schreiber, der den Nacht-Block NICHT betrifft. */
	const anderesSpeichern: Array<[string, (a: P.Aufbau) => Promise<void>]> = [
		['Reiter Wetter', async (a) => (await P.wetterReiter(a)).abwaehlen('wind')],
		['anderer Schalter der Karte', async (a) => (await P.karteWasStehtWo(a)).schalten('show_stage_stats', false)]
	];

	test('Alt-Trip: andere Metrik speichern sendet show_night_block NICHT', async () => {
		for (const [wer, lauf] of anderesSpeichern) {
			await start(tripMitNachtBlock(undefined));
			const a = P.neuerAufbau(tripMitNachtBlock(undefined));
			await lauf(a);
			await P.fertig(a.ctl);
			assert.ok(puts().length > 0, `Messaufbau: ${wer} hat nicht gespeichert`);
			assert.equal(serverNachtBlock(), undefined, `${wer}: ohne gespeicherten Wert und ohne Nutzergeste entsteht kein Feld`);
			server.restore();
		}
	});

	test('Trip mit gespeichertem aus: Schalter zeigt aus, anderes Speichern laesst den Wert stehen', async () => {
		for (const [wer, lauf] of anderesSpeichern) {
			await start(tripMitNachtBlock(false));
			const a = P.neuerAufbau(tripMitNachtBlock(false));
			assert.equal(anzeige(await P.karteWasStehtWo(a)), false, 'gespeichertes aus wird als aus gezeigt');
			await lauf(a);
			await P.fertig(a.ctl);
			assert.ok(puts().length > 0, `Messaufbau: ${wer} hat nicht gespeichert`);
			assert.equal(serverNachtBlock(), false, `${wer}: aus bleibt aus`);
			for (const p of puts()) assert.ok(!JSON.stringify(p.anfrage).includes('show_night_block'), `${wer} sendet fremdes show_night_block`);
			server.restore();
		}
	});

	test('Trip mit gespeichertem an: Reiter Wetter sendet den Wert nicht mit, der Server behaelt ihn', async () => {
		await start(tripMitNachtBlock(true));
		const a = P.neuerAufbau(tripMitNachtBlock(true));
		(await P.wetterReiter(a)).abwaehlen('wind');
		await P.fertig(a.ctl);
		assert.ok(!('show_night_block' in weatherConfigBody()));
		assert.equal(serverNachtBlock(), true);
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

	test('Reiter Zustellung sendet show_night_block nie', async () => {
		await start(tripMitNachtBlock(false));
		const a = P.neuerAufbau(tripMitNachtBlock(false));
		(await P.zustellungReiter(a)).aendern({ morgenZeit: '06:30', stilleAn: false });
		await P.fertig(a.ctl);
		assert.ok(puts().length > 0, 'Messaufbau: es gab einen PUT');
		for (const p of puts()) assert.ok(!('display_config' in (p.anfrage as object)), 'Zustellung schreibt nie display_config');
		assert.equal(serverNachtBlock(), false);
	});
});
