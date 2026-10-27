// Issue #1433 — Selbsttest des Ersatz-Servers im Merge-Modus.
//
// Der Ersatz-Server ist der GEGENSPIELER aller Mehrreiter-Tests (W1/W2 und die
// Nutzlast-Tests). Bildet er den Go-Merge falsch nach (z. B. tiefer als Go),
// beweist ein gruener Mehrreiter-Test nichts. Diese Datei haelt ihn deshalb an
// den Quellen fest: internal/handler/config_merge.go (mergeConfigMap, :11-22),
// internal/handler/trip.go (UpdateTripHandler), weather_config.go (:99-125).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/fakeTripServerGoMerge.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { createFakeTripServer, type FakeTripServer } from './fakeTripServer.ts';

const ID = 'gr20';
let server: FakeTripServer;

beforeEach(() => {
	server = createFakeTripServer({ merge: true });
	server.install();
});
afterEach(() => server.restore());

const json = { 'Content-Type': 'application/json' };
const put = (body: unknown, ifMatch?: string, pfad = `/api/trips/${ID}`) =>
	fetch(pfad, {
		method: 'PUT',
		headers: { ...json, ...(ifMatch ? { 'If-Match': ifMatch } : {}) },
		body: JSON.stringify(body)
	});

describe('Merge einstufig wie mergeConfigMap (config_merge.go:11-22)', () => {
	test('ein verschachteltes Objekt wird als GANZES ersetzt, nicht tief gemergt', async () => {
		server.seed(ID, {
			name: 'Seed',
			display_config: { channel_layouts: { email: ['a'], telegram: ['b'] }, metrics: ['x'] }
		});
		await put({ display_config: { channel_layouts: { sms: ['c'] } } });
		const dc = server.stand(ID).display_config as Record<string, unknown>;
		assert.deepEqual(dc.channel_layouts, { sms: ['c'] }, 'Go ersetzt den Nested-Wert, es gibt keinen Tiefen-Merge');
		assert.deepEqual(dc.metrics, ['x'], 'ein nicht gesendeter Top-Level-Schluessel bleibt erhalten');
	});

	test('ein fehlender Schluessel bleibt, ein leerer Wert ueberschreibt (Go loescht nie, setzt aber)', async () => {
		server.seed(ID, {
			name: 'Seed',
			report_config: { skip_next: true, morning_time: '07:00:00', show_outlook: true }
		});
		await put({ report_config: { show_outlook: false } });
		const rc = server.stand(ID).report_config as Record<string, unknown>;
		assert.equal(rc.skip_next, true, 'nicht gesendet ⇒ unangetastet');
		assert.equal(rc.show_outlook, false, 'gesendeter Wert ueberschreibt, auch false');
		await put({ display_config: { metrics: [] } });
		assert.deepEqual((server.stand(ID).display_config as Record<string, unknown>).metrics, [], '[] wird geschrieben');
		assert.equal(server.stand(ID).name, 'Seed', 'ein nicht gesendetes Top-Level-Feld bleibt');
	});

	test('Top-Level-null (Zeiger-Feld) und unbekannte Top-Level-Felder aendern nichts', async () => {
		server.seed(ID, { name: 'Seed', alert_cooldown_minutes: 45 });
		await put({ alert_cooldown_minutes: null, skip_next: true, erfunden: 1 });
		const s = server.stand(ID);
		assert.equal(s.alert_cooldown_minutes, 45, 'JSON-null dekodiert Go zu nil = „nicht gesendet"');
		assert.ok(!('skip_next' in s), 'Go kennt kein Top-Level-skip_next und ignoriert es');
		assert.ok(!('erfunden' in s), 'unbekannte Felder werden von Go verworfen');
	});

	test('alert_channels/alert_channel_thresholds mergen je Kanal, official_warnings behaelt sources', async () => {
		server.seed(ID, {
			alert_channels: { email: true, telegram: true, sms: false, premium_sms: false },
			alert_channel_thresholds: { email: 'gering', telegram: 'hoch' },
			official_warnings: { enabled: true, sources: ['meteoalarm'] }
		});
		await put({
			alert_channels: { sms: true },
			alert_channel_thresholds: { telegram: 'mittel' },
			official_warnings: { enabled: false }
		});
		const s = server.stand(ID);
		assert.deepEqual(s.alert_channels, { email: true, telegram: true, sms: true, premium_sms: false });
		assert.deepEqual(s.alert_channel_thresholds, { email: 'gering', telegram: 'mittel' });
		assert.deepEqual(s.official_warnings, { enabled: false, sources: ['meteoalarm'] });
	});

	test('report_config: Slot-Zeiten werden auf die volle Stunde gekappt, ungueltiges Tagesfenster entfernt', async () => {
		server.seed(ID, { report_config: { day_window_start_hour: 4, day_window_end_hour: 19 } });
		await put({ report_config: { morning_time: '07:15:00' } });
		assert.equal((server.stand(ID).report_config as Record<string, unknown>).morning_time, '07:00:00');
		await put({ report_config: { day_window_start_hour: 9, day_window_end_hour: 9 } });
		const rc = server.stand(ID).report_config as Record<string, unknown>;
		assert.ok(!('day_window_start_hour' in rc) && !('day_window_end_hour' in rc), 'start == end ist ungueltig');
	});
});

describe('weather-config, state, ETag, Fremdschreiber', () => {
	test('PUT /weather-config: der Rumpf IST die display_config (weather_config.go:114-125)', async () => {
		server.seed(ID, { name: 'Seed', display_config: { metric_alert_levels: { wind: 'hoch' }, metrics: ['x'] }, report_config: { a: 1 } });
		const res = await put({ metrics: ['y'] }, undefined, `/api/trips/${ID}/weather-config`);
		assert.equal(res.status, 200);
		const s = server.stand(ID);
		assert.deepEqual(s.display_config, { metric_alert_levels: { wind: 'hoch' }, metrics: ['y'] });
		assert.deepEqual(s.report_config, { a: 1 }, 'report_config bleibt unberuehrt');
		assert.ok(!('metrics' in s), 'metrics gehoert in display_config, nicht auf die oberste Ebene');
		assert.ok(res.headers.get('ETag'), 'die Antwort traegt den neuen ETag');
	});

	test('foreignWrite: ETag aendert sich, kein Eintrag in calls, If-Match des Klienten wird veraltet', async () => {
		server.seed(ID, { name: 'Seed', display_config: { metrics: ['x'] } });
		const gelesen = await fetch(`/api/trips/${ID}`);
		const alt = gelesen.headers.get('ETag')!;
		const vorher = server.calls.length;
		server.foreignWrite(ID, { display_config: { metrics: ['y'] }, report_config: { skip_next: true } });
		assert.equal(server.calls.length, vorher, 'der Fremdschreiber laeuft nicht ueber den Klienten');
		assert.notEqual(server.etagOf(ID), alt, 'der Fremdschreiber veraendert den Fingerabdruck');
		const res = await put({ name: 'spaet' }, alt);
		assert.equal(res.status, 412, 'ein If-Match auf den alten Stand wird abgelehnt');
		assert.equal(server.stand(ID).name, 'Seed', 'ein abgelehnter PUT schreibt nichts');
		assert.equal((server.stand(ID).report_config as Record<string, unknown>).skip_next, true);
		assert.deepEqual(server.calls.at(-1)?.anfrage, { name: 'spaet' }, 'der abgelehnte Rumpf wird mitgeschnitten');
	});

	test('PATCH /state: setzt paused_at/archived_at, veraendert den ETag, liefert keinen ETag-Header', async () => {
		server.seed(ID, { name: 'Seed' });
		const vorher = server.etagOf(ID);
		const res = await fetch(`/api/trips/${ID}/state`, {
			method: 'PATCH',
			headers: json,
			body: JSON.stringify({ paused: true })
		});
		assert.equal(res.status, 200);
		assert.equal(res.headers.get('ETag'), null, 'S2 AC-15: /state liefert keinen Stempel');
		assert.notEqual(server.etagOf(ID), vorher, 'die Datei hat sich geaendert');
		assert.ok(server.stand(ID).paused_at, 'paused wird als paused_at festgehalten');
	});

	test('ohne merge: PUT ersetzt den Rumpf wie vor #1433 (Bestandsvertrag der 35 Altdateien)', async () => {
		server.restore();
		const alt = createFakeTripServer();
		alt.install();
		try {
			await put({ a: 1 });
			await put({ b: 2 });
			assert.deepEqual(alt.storedBody(ID), { b: 2 });
			const res = await fetch(`/api/trips/${ID}`);
			assert.deepEqual(await res.json(), { id: ID, b: 2 });
		} finally {
			alt.restore();
		}
	});
});
