// Rework #3020 R1, AC-6: die Speichernutzlast des Trips aus Zustellung-Reiter und Karte „Was steht wo“
// enthaelt `skip_next` nie -- ein von Telegram/SMS gesetztes „naechstes Briefing auslassen“ bleibt
// stehen, auch wenn der Nutzer im offenen Reiter speichert. Ersatz fuer den mit #3357 geloeschten
// trip_python_skip_next_ohne_412.test.ts (Frontend-Teil; Server-Teil: internal/store/trip_skip_next_erhalt_test.go).
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-6)
//
// Pruefstand: ECHTES `api` gegen den Go-treuen Ersatz-Server (`createFakeTripServer({ merge: true })`),
// echte Speicherer (`erstelleZustellungSpeicherung`, `erstelleFelderSpeicherung`), echte Nutzlast-Funktionen.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/rework_3020_trip_nutzlast_ohne_skip_next.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { standAusTrip, type ZustellungStand } from '../zustellung-tab/zustellungModell.ts';
import { erstelleZustellungSpeicherung, zustellungNutzlast } from '../zustellung-tab/zustellungSpeicherung.ts';
import { erstelleFelderSpeicherung, felderNutzlast, type Felder } from '../wetter-tab/wasStehtWoSpeicherung.ts';
import type { Trip } from '../../../types.ts';

const TRIP_ID = 'trip-3020-skip';
const SKIP = { morning: true, set_by: 'telegram', set_at: '2026-11-25T05:12:00Z' };

function trip(): Record<string, unknown> {
	return {
		id: TRIP_ID,
		name: 'GR20',
		stages: [{ id: 'E1', name: 'E1', date: '2026-07-10', waypoints: [] }],
		display_config: { metrics: [{ metric_id: 'wind', enabled: true }] },
		report_config: {
			enabled: true, morning_enabled: true, evening_enabled: true,
			morning_time: '07:00:00', evening_time: '18:00:00',
			send_email: true, send_telegram: false, send_sms: false, send_premium_sms: false,
			show_stage_stats: true, show_yesterday_comparison: true, show_compact_summary: true, show_stability: true,
			email_format: 'full', telegram_style: 'rich',
			skip_next: SKIP
		},
		alert_channels: { email: true, telegram: false, sms: false, premium_sms: false },
		alert_channel_thresholds: { email: 'LOW', telegram: 'LOW', sms: 'LOW', premium_sms: 'LOW' },
		alert_cooldown_minutes: 60
	};
}

/** Jedes Feld, das der Zustellung-Reiter kennt, geaendert. */
function allesGeaendert(s: ZustellungStand): ZustellungStand {
	return {
		...s,
		morgenAn: !s.morgenAn, abendAn: !s.abendAn, morgenZeit: '08:00', abendZeit: '19:00',
		briefing: { email: !s.briefing.email, telegram: !s.briefing.telegram, sms: !s.briefing.sms, premium_sms: !s.briefing.premium_sms },
		alarme: { email: !s.alarme.email, telegram: !s.alarme.telegram, sms: !s.alarme.sms, premium_sms: !s.alarme.premium_sms },
		dringlichkeit: { email: 'HIGH', telegram: 'HIGH', sms: 'HIGH', premium_sms: 'HIGH' },
		stilleAn: !s.stilleAn, cooldown: s.cooldown + 15
	};
}

const FELDER_START: Felder = {
	show_stage_stats: true, show_yesterday_comparison: true, show_night_block: true, show_compact_summary: true,
	show_stability: true, email_format: 'full', telegram_style: 'rich', hourly_enabled: true
};
const FELDER_ALLE_UM: Felder = {
	show_stage_stats: false, show_yesterday_comparison: false, show_night_block: false, show_compact_summary: false,
	show_stability: false, email_format: 'compact', telegram_style: 'kurzform', hourly_enabled: false
};

const putsAnTrip = (server: FakeTripServer) => server.calls.filter((c) => c.method === 'PUT' && c.path === `/api/trips/${TRIP_ID}`);

describe('Rework #3020 AC-6: Trip-Speichernutzlast ohne skip_next', () => {
	let server: FakeTripServer;
	beforeEach(() => {
		clearEtagRegistry();
		server = createFakeTripServer({ merge: true });
		server.seed(TRIP_ID, trip());
		server.install();
	});
	afterEach(() => server.restore());

	test('Zustellung-Reiter: Nutzlast aus geladenem Trip mit skip_next traegt skip_next nie, Server behaelt es', async () => {
		const geladen = (await api.get<Trip>(`/api/trips/${TRIP_ID}`)) as Trip;
		const basis = standAusTrip(geladen);
		const jetzt = allesGeaendert(basis);

		const n = zustellungNutzlast('route', basis, jetzt);
		assert.ok(n.versand && n.alarme, 'Vorbedingung: beide Teile haben Aenderungen');
		assert.ok(!JSON.stringify(n).includes('skip_next'), `skip_next in der Nutzlast: ${JSON.stringify(n)}`);

		const sp = erstelleZustellungSpeicherung({ context: 'route', id: TRIP_ID, client: api, saveController: sofort(), basis });
		sp.aenderungMelden(jetzt);
		await warteAufPuts(server, 2);

		const puts = putsAnTrip(server);
		assert.equal(puts.length, 2, 'Vorbedingung: Versand- und Alarm-Teil gesendet');
		for (const p of puts) {
			assert.equal(p.status, 200);
			assert.ok(!JSON.stringify(p.anfrage).includes('skip_next'), `skip_next im PUT: ${JSON.stringify(p.anfrage)}`);
		}
		const rc = server.stand(TRIP_ID).report_config as Record<string, unknown>;
		assert.equal(rc.morning_time, '08:00:00', 'Vorbedingung: die Aenderung ist angekommen');
		assert.deepEqual(rc.skip_next, SKIP, 'skip_next muss nach dem Speichern unveraendert stehen');
	});

	test('Karte „Was steht wo“: Schalter-Nutzlast traegt skip_next nie, Server behaelt es', async () => {
		const rumpf = felderNutzlast('route', FELDER_ALLE_UM, FELDER_START);
		assert.ok(!JSON.stringify(rumpf).includes('skip_next'), `skip_next in der Nutzlast: ${JSON.stringify(rumpf)}`);

		await api.get(`/api/trips/${TRIP_ID}`);
		const sp = erstelleFelderSpeicherung({ client: api, kind: 'route', id: TRIP_ID, start: FELDER_START });
		sp.melden(FELDER_ALLE_UM);
		await warteAufPuts(server, 1);

		const [put] = putsAnTrip(server);
		assert.equal(put.status, 200);
		assert.ok(!JSON.stringify(put.anfrage).includes('skip_next'), `skip_next im PUT: ${JSON.stringify(put.anfrage)}`);
		const rc = server.stand(TRIP_ID).report_config as Record<string, unknown>;
		assert.equal(rc.show_stability, false, 'Vorbedingung: die Aenderung ist angekommen');
		assert.deepEqual(rc.skip_next, SKIP, 'skip_next muss nach dem Speichern unveraendert stehen');
	});
});

/** Planer, der jeden Vorgang sofort ausfuehrt (kein Entprellen) -- echter Aufruf der Speicherfunktion. */
function sofort() {
	return {
		schedule(fn: (init?: RequestInit) => Promise<void>) {
			void fn().catch(() => {});
		},
		cancel() {}
	} as unknown as Parameters<typeof erstelleZustellungSpeicherung>[0]['saveController'];
}

async function warteAufPuts(server: FakeTripServer, anzahl: number): Promise<void> {
	for (let i = 0; i < 50; i++) {
		const fertig = putsAnTrip(server).filter((c) => c.status !== 0);
		if (fertig.length >= anzahl) return;
		await new Promise((r) => setTimeout(r, 5));
	}
}
