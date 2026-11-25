// Rework #3020 R1, AC-17: der Trip speichert seinen eigenen Ausblick-Schalter (Tabelle der Karte,
// `placements.outlook_reports`, ADR-0124 Nr. 6) und seine Warnungswerte (`display_config.metric_alert_levels`)
// mit genau den eingestellten Werten; kein Altfeld (`show_outlook`, `multi_day_trend_reports`) reist mit,
// nicht geaenderte display_config-Felder bleiben aus der Nutzlast und beim Server erhalten.
// Ersatz fuer den mit #3357 geloeschten wetter_metriken_trip_speichert_eigene_ausblick_und_warnungswerte.test.ts.
// Go-Teil (zwei Nutzer, Merge): internal/store/trip_display_config_felderhalt_test.go,
// internal/store/trip_metric_alert_levels_test.go.
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-17)
//
// Pruefstand: ECHTES `api` gegen den Go-treuen Ersatz-Server (merge); echte Speicherwege:
// Karte -> `erstelleTabellenSpeicherung` (PUT /api/briefings/{id}/placements?kind=route), Warnungswerte ->
// `buildAlarmeDeliveryPayload` + `baueTripSpeicherung` (Speicherweg des Reiters Alarme, Trip).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/rework_3020_ausblick_warnungswerte_nutzlast.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import { erstelleTabellenSpeicherung, tabellenPfad } from '../wasStehtWoSpeicherung.ts';
import { mitAusblick, type Placements } from '../wasStehtWoStand.ts';
import { buildAlarmeDeliveryPayload } from '../../alarme-tab/alarmeDeliveryPayload.ts';
import { baueTripSpeicherung } from '../../tripSpeicherung.ts';

const TRIP_ID = 'trip-3020-ausblick';
const ALTFELDER = ['show_outlook', 'multi_day_trend_reports'];
const START: Placements = { version: 1, rows: [{ metric_id: 'wind' }, { metric_id: 'gust' }], outlook_reports: ['evening'] };

function trip(): Record<string, unknown> {
	return {
		id: TRIP_ID,
		name: 'GR20',
		stages: [{ id: 'E1', name: 'E1', date: '2026-07-10', waypoints: [] }],
		display_config: {
			metrics: [{ metric_id: 'wind', enabled: true, morning_enabled: true, evening_enabled: false, format_mode: 'raw' }],
			metric_alert_levels: { wind: 'normal' },
			placements: START,
			ampel: { template: 'wandern' }
		},
		report_config: { enabled: true }
	};
}

const ohneAltfelder = (x: unknown, wo: string) => {
	const s = JSON.stringify(x);
	for (const alt of ALTFELDER) assert.ok(!s.includes(`"${alt}"`), `${wo}: Altfeld ${alt} in ${s}`);
};

describe('Rework #3020 AC-17: Trip speichert Ausblick und Warnungswerte', () => {
	let server: FakeTripServer;
	beforeEach(async () => {
		clearEtagRegistry();
		server = createFakeTripServer({ merge: true });
		server.seed(TRIP_ID, trip());
		server.install();
		await api.get(`/api/trips/${TRIP_ID}`);
	});
	afterEach(() => server.restore());

	for (const [name, berichte, erwartet] of [
		['einschalten (Morgen dazu)', { morning: true, evening: true }, ['morning', 'evening']],
		['ausschalten (alle aus)', { morning: false, evening: false }, []]
	] as const) {
		test(`Ausblick ${name}: Karte sendet placements.outlook_reports = ${JSON.stringify(erwartet)}, kein Altfeld`, async () => {
			let lokal: Placements = START;
			const tabelle = erstelleTabellenSpeicherung({
				client: api, kind: 'route', id: TRIP_ID,
				placements: () => lokal,
				uebernehmen: () => {}
			});
			lokal = mitAusblick(START, berichte);
			tabelle.aenderung();
			await new Promise((r) => setTimeout(r, 10));

			const put = server.calls.find((c) => c.method === 'PUT' && c.path === tabellenPfad('route', TRIP_ID));
			assert.ok(put, 'die Karte hat nicht gespeichert');
			const gesendet = put.anfrage as Placements;
			assert.deepEqual(gesendet.outlook_reports, erwartet, 'Ausblick nicht wie eingestellt gesendet');
			assert.deepEqual(gesendet.rows, START.rows, 'die Zeilen der Tabelle reisen unveraendert mit');
			ohneAltfelder(gesendet, 'Tabellen-PUT');
		});
	}

	test('Warnungsstufe aendern: display_config traegt nur metric_alert_levels mit genau diesen Werten; Rest bleibt beim Server', async () => {
		const stufen = { wind: 'sensibel', wind_gust: 'robust' };
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: true,
			channels: { email: true, telegram: false, sms: false, premium_sms: false },
			metricLevels: stufen
		}) as Record<string, unknown>;
		await baueTripSpeicherung(api, TRIP_ID, payload)();

		const put = server.calls.find((c) => c.method === 'PUT' && c.path === `/api/trips/${TRIP_ID}`)!;
		assert.equal(put.status, 200);
		const anfrage = put.anfrage as Record<string, unknown>;
		assert.deepEqual(anfrage.display_config, { metric_alert_levels: stufen }, 'nur der eigene display_config-Schluessel, mit genau den Werten');
		assert.ok(!('report_config' in anfrage), 'report_config ist nicht geaendert und gehoert nicht in die Nutzlast');
		ohneAltfelder(anfrage, 'Trip-PUT');

		const dc = server.stand(TRIP_ID).display_config as Record<string, unknown>;
		assert.deepEqual(dc.metric_alert_levels, stufen);
		const vorher = trip().display_config as Record<string, unknown>;
		for (const feld of ['metrics', 'placements', 'ampel']) assert.deepEqual(dc[feld], vorher[feld], `display_config.${feld} beim Server veraendert`);
	});
});
