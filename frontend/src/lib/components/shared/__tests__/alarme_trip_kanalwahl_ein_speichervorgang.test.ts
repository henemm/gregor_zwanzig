// TDD RED — #1895 S3b1, Speicherweg Trip (AC-42, 47, 54, 59). Angenommene Signaturen:
// `AlarmeDeliveryState.metricChannelsDiff` (Top-Level `alert_metric_channels` nur bei nicht-leerem
// Diff), `CreateTripAlarmState.metricChannels`, AlarmeTab route: `routeAlertMetricChannels` +
// Prop `existingAlertMetricChannels`, `<AlertMetricChannelsBlock onChange={Funktionsname|typfreier Ausdruck}>`.
// AC-54 ohne DOM über svelteInstanzPruefstand: echter onChange-Ausdruck + echte $effect-Rümpfe;
// ein zweiter schedule() (Handler oder zweiter $effect) ⇒ Zähler ≠ 1.
// AC-59: fakeTripServer kennt nur Ressourcen-IDs, keine Nutzer — bewiesen ist die Trennung A/B
// auf dem Speicherweg; user_id aus dem Auth-Kontext sichert der Go-Handler (nicht hier).

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildAlarmeDeliveryPayload } from '../alarme-tab/alarmeDeliveryPayload.ts';
import { buildCreateTripPayload, initialCreateTripAlarmState } from '../../trip-new/tripNewLogic.ts';
import { createFakeTripServer } from '../../../__tests__/fakeTripServer.ts';
import { umgebungFuer, effekteVon, findeKomponenten, attributAusdruck, werte } from './svelteInstanzPruefstand.ts';

const TAB = join(dirname(fileURLToPath(import.meta.url)), '..', 'AlarmeTab.svelte');
const TG = { email: false, telegram: true, sms: false, premium_sms: false };
const MAIL = { email: true, telegram: false, sms: false, premium_sms: false };
const basis = (diff?: Record<string, unknown>) =>
	buildAlarmeDeliveryPayload({ officialWarningsEnabled: false, channels: MAIL, metricLevels: { wind_gust: 'hoch' },
		...(diff !== undefined ? { metricChannelsDiff: diff } : {}) } as never) as Record<string, unknown>;

test('AC-47: Trip-PUT trägt alert_metric_channels Top-Level (nicht in display_config), ohne Änderung fehlt es', () => {
	const mit = basis({ thunder: TG });
	assert.deepStrictEqual(mit.alert_metric_channels, { thunder: TG });
	assert.ok(!('alert_metric_channels' in (mit.display_config as object)), 'nie unter display_config');
	assert.ok(!('alert_metric_channels' in basis({})), 'leerer Diff ⇒ Feld fehlt');
	assert.ok(!('alert_metric_channels' in basis()), 'kein Diff ⇒ Feld fehlt');
});

test('AC-54 (Anlegen): der Anlege-Payload /trips/new trägt die Kanalwahl', () => {
	const trip = buildCreateTripPayload({
		name: 'T', startDate: '2026-11-03', stages: [{ id: 1, name: 'E1' }],
		channels: { email: true, telegram: false, sms: false },
		alarm: { ...initialCreateTripAlarmState(), metricChannels: { thunder: TG } } as never
	}) as unknown as Record<string, unknown>;
	assert.deepStrictEqual(trip.alert_metric_channels, { thunder: TG });
	assert.ok(!('alert_metric_channels' in (trip.display_config as object)));
});

test('AC-54: eine Kanalwahl im Trip-Hub plant über den bestehenden Dirty-$effect genau EINEN Speichervorgang', async () => {
	const gebaut: unknown[][] = [];
	const geplant: unknown[] = [];
	const bestand = { gust: MAIL, snowfall_limit: MAIL };
	const { ast, quelle, u } = await umgebungFuer(TAB, {
		context: 'route', trip: { id: 't-1', display_config: {}, alert_metric_channels: bestand },
		existingAlertMetricChannels: bestand, untrack: (fn: () => unknown) => fn(),
		profileOverride: { premium_sms_allowed: false }, activeMetrics: ['wind_gust', 'thunder_level'],
		metricLevels: {}, existingChannels: null, existingChannelThresholds: null,
		baueTripSpeicherung: (...a: unknown[]) => (gebaut.push(a), async () => {}),
		saveController: { schedule: (fn: unknown) => geplant.push(fn) },
		createMode: undefined
	});
	const block = findeKomponenten(ast, 'AlertMetricChannelsBlock');
	assert.strictEqual(block.length, 1, `AlarmeTab bettet AlertMetricChannelsBlock ${block.length}× ein (erwartet 1)`);
	const ausdruck = attributAusdruck(block[0], quelle, 'onChange');
	assert.ok(ausdruck, 'Einbettung ohne onChange-Rückruf');
	const onChange = werte(ausdruck!, u) as (k: string, e: unknown) => void;

	onChange('thunder', TG);
	assert.strictEqual(geplant.length, 0, 'der Rückruf selbst darf nicht schedule() rufen (zweiter Schreiber)');
	const effekte = effekteVon(ast, quelle, u, 'routeAlertMetricChannels');
	assert.ok(effekte.length >= 1, 'kein $effect liest routeAlertMetricChannels — die Wahl wird nie gespeichert');
	for (const e of effekte) e();
	assert.strictEqual(geplant.length, 1, `schedule()-Aufrufe: ${geplant.length} (erwartet genau 1)`);
	const payload = gebaut.at(-1)?.[2] as Record<string, unknown>;
	assert.deepStrictEqual(payload.alert_metric_channels, { thunder: TG }, 'nur der Diff, kein gust/snowfall_limit');
	assert.ok(!('alert_metric_channels' in ((payload.display_config as object) ?? {})));
});

test('AC-59/AC-42: B ändert, speichert und rollt zurück — A bleibt unverändert, B behält snowfall_limit', async () => {
	const server = createFakeTripServer({ merge: true });
	server.seed('trip-a', { name: 'A', alert_metric_channels: { gust: TG } });
	server.seed('trip-b', { name: 'B', alert_metric_channels: { gust: MAIL, snowfall_limit: MAIL } });
	server.install();
	try {
		const put = (id: string, body: unknown) =>
			fetch(`/api/trips/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
		await put('trip-b', basis({ thunder: TG }));
		assert.deepStrictEqual(server.stand('trip-b').alert_metric_channels, { gust: MAIL, snowfall_limit: MAIL, thunder: TG });
		await put('trip-b', basis({ thunder: null }));
		assert.deepStrictEqual(server.stand('trip-b').alert_metric_channels, { gust: MAIL, snowfall_limit: MAIL, thunder: null });
		assert.deepStrictEqual(server.stand('trip-a').alert_metric_channels, { gust: TG }, 'A darf sich nie ändern');
	} finally {
		server.restore();
	}
});
