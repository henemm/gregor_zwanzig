// Rework #3020 R1, AC-8 bis AC-10: Nachtblock-Schalter der Karte „Was steht wo“ beim Trip.
// Ersatz fuer den mit #3357 geloeschten trip_night_block_schalter_verdrahtung.test.ts, am heutigen
// Kartenmodell (`wasStehtWoSpeicherung.ts`). AC-11 (Schalter im Anlegen, abgeloest durch #3305) belegt
// organisms/__tests__/was_steht_wo_karte_anlegen_3305.test.ts, die Anzeige im Anlegen
// organisms/__tests__/rework_3020_karte_schalter.test.ts; der Server-Teil von AC-9 in
// internal/store/trip_night_block_altstandard_test.go.
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-8, AC-9, AC-10)
//
//   AC-8:  Alt-Trip ohne `show_night_block` -> Schalter „an“.
//   AC-9:  derselbe Alt-Trip, Speichern ohne Beruehren des Schalters -> Feld wird nicht gesendet.
//   AC-10: geaendert und verworfen -> Sende-Merker zurueck, der naechste Speichervorgang sendet das Feld nicht.
//
// Pruefstand: ECHTES `api` gegen den Go-treuen Ersatz-Server (merge), ECHTE SaveStatus-Instanz.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/rework_3020_nachtblock_schalter.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { SaveStatus } from '../../../../stores/saveStatusStore.svelte.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import { erstelleFelderSpeicherung, felderAusAntwort, felderNutzlast, FELDER_OWNER, type Felder } from '../wasStehtWoSpeicherung.ts';

const TRIP_ID = 'trip-3020-nacht';
const PFAD = `/api/trips/${TRIP_ID}`;

/** `blocks` der Placements-Antwort eines Alt-Trips: kein `show_night_block`. */
const BLOCKS_ALT = { show_stage_stats: true, show_yesterday_comparison: true, show_compact_summary: true, show_stability: true, email_format: 'full', telegram_style: 'rich' };

function altTrip(): Record<string, unknown> {
	return {
		id: TRIP_ID,
		name: 'Alt-Trip',
		stages: [{ id: 'E1', name: 'E1', date: '2026-07-10', waypoints: [] }],
		display_config: { metrics: [{ metric_id: 'wind', enabled: true }] },
		report_config: { enabled: true, show_stability: true }
	};
}

function controller(): SaveStatus {
	const inst = Object.create(SaveStatus.prototype) as SaveStatus;
	const f = inst as unknown as Record<string, unknown>;
	f.state = 'idle';
	f.savedAt = null;
	f.error = null;
	f._timer = null;
	f._pendingFn = null;
	f._inflight = null;
	f._lastFailed = null;
	f._unresolvedError = null;
	f._tripId = TRIP_ID;
	return inst;
}

const puts = (server: FakeTripServer) => server.calls.filter((c) => c.method === 'PUT' && c.path === PFAD);
const dcVon = (server: FakeTripServer) => (server.stand(TRIP_ID).display_config ?? {}) as Record<string, unknown>;

describe('Rework #3020 AC-8: Alt-Trip ohne show_night_block zeigt den Schalter „an“', () => {
	test('fehlendes Feld -> an; gespeichertes false -> aus (Gegenprobe)', () => {
		assert.equal(felderAusAntwort({ blocks: BLOCKS_ALT }).show_night_block, true, 'Alt-Trip ohne Feld muss „an“ zeigen');
		assert.equal(felderAusAntwort({ blocks: { ...BLOCKS_ALT, show_night_block: false } }).show_night_block, false);
	});
});

describe('Rework #3020 AC-9/AC-10: Nachtblock wird nur gesendet, wenn der Nutzer ihn wirklich aendert', () => {
	let server: FakeTripServer;
	let start: Felder;
	beforeEach(async () => {
		clearEtagRegistry();
		server = createFakeTripServer({ merge: true });
		server.seed(TRIP_ID, altTrip());
		server.install();
		await api.get(PFAD);
		start = felderAusAntwort({ blocks: BLOCKS_ALT });
	});
	afterEach(() => server.restore());

	test('AC-9: Speichern eines anderen Schalters sendet show_night_block nicht, der Alt-Trip bleibt ohne Feld', async () => {
		assert.deepEqual(felderNutzlast('route', start, start), {}, 'unveraendert = leere Nutzlast');
		const ctl = controller();
		const sp = erstelleFelderSpeicherung({ client: api, kind: 'route', id: TRIP_ID, saveController: ctl, start });

		sp.melden({ ...start, show_stability: false });
		await ctl.flush();

		const [put] = puts(server);
		assert.equal(put?.status, 200, 'Vorbedingung: der Schalter wurde gespeichert');
		assert.deepEqual(put.anfrage, { report_config: { show_stability: false } }, 'nur der geaenderte Schalter geht hinaus');
		assert.ok(!('show_night_block' in dcVon(server)), `Alt-Trip traegt nach dem Speichern show_night_block: ${JSON.stringify(dcVon(server))}`);
	});

	test('AC-10a: geaendert und vor dem Speichern zurueckgenommen -> kein Feld; der naechste Vorgang sendet es nicht', async () => {
		const ctl = controller();
		const sp = erstelleFelderSpeicherung({ client: api, kind: 'route', id: TRIP_ID, saveController: ctl, start });

		sp.melden({ ...start, show_night_block: false });
		sp.melden({ ...start });
		await ctl.flush();
		assert.equal(puts(server).length, 0, 'verworfene Aenderung darf nichts schreiben');

		sp.melden({ ...start, show_stability: false });
		await ctl.flush();
		const [put] = puts(server);
		assert.ok(put, 'Vorbedingung: der zweite Vorgang wurde gesendet');
		assert.ok(!JSON.stringify(put.anfrage).includes('show_night_block'), `verworfener Nachtblock reist mit: ${JSON.stringify(put.anfrage)}`);
		assert.ok(!('show_night_block' in dcVon(server)));
	});

	test('AC-10b: gescheitertes Speichern verwirft die Aenderung -> Sende-Merker zurueck, naechster Vorgang ohne Feld', async () => {
		server.foreignWrite(TRIP_ID, { name: 'fremd' }); // anderes Geraet: der bekannte Stempel ist veraltet
		const ctl = controller();
		let angezeigt: Felder = { ...start };
		const sp = erstelleFelderSpeicherung({
			client: api, kind: 'route', id: TRIP_ID, saveController: ctl, start,
			// wie WasStehtWoKarte.svelte: Anzeige zurueck auf den gespeicherten Stand
			onFehler: (_e, stand) => (angezeigt = stand)
		});

		angezeigt = { ...start, show_night_block: false };
		sp.melden(angezeigt);
		await ctl.flush().catch(() => {});
		assert.equal(puts(server)[0]?.status, 412, 'Vorbedingung: der Server lehnt den veralteten Stand ab');
		assert.equal(angezeigt.show_night_block, true, 'nach dem Verwerfen zeigt der Schalter wieder den gespeicherten Stand');

		await api.get(PFAD); // neu laden (Konflikt aufgeloest)
		sp.melden({ ...angezeigt, show_stability: false });
		await ctl.flush().catch(() => {});
		assert.equal(puts(server).length, 2, 'Vorbedingung: der naechste Vorgang wurde gesendet');
		const letzter = puts(server).at(-1)!;
		assert.equal(letzter.status, 200, 'Vorbedingung: der naechste Vorgang ist gespeichert');
		assert.ok(!JSON.stringify(letzter.anfrage).includes('show_night_block'), `verworfener Nachtblock reist mit: ${JSON.stringify(letzter.anfrage)}`);
		assert.equal(FELDER_OWNER, 'was-steht-wo-schalter');
	});
});
