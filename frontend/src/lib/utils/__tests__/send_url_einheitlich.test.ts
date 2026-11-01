// Issue #2280 (AC-15, AC-16) — Handversand ueber EINEN Endpunkt.
// Gemessen wird, welche URL der einzige Versand-Ausloeser `sendSubscription`
// tatsaechlich abschickt (aufzeichnender fetch-Ersatz), und was der Nutzer bei
// den drei neuen 422-Antworten bzw. bei Erfolg mit `fehlende_orte` zu sehen bekommt.
// Spec: docs/specs/modules/feat_2280_handversand_endpoint.md
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/utils/__tests__/send_url_einheitlich.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { sendSubscription } from '../../components/shared/subscriptionExec.ts';
import { tr } from '../../i18n/index.ts';

interface Aufruf {
	url: string;
	method: string;
}

/** Ersatz-Server: zeichnet jeden Request auf und antwortet mit der vorgegebenen Antwort. */
function server(status: number, body: unknown): { fn: typeof fetch; aufrufe: Aufruf[] } {
	const aufrufe: Aufruf[] = [];
	const fn = (async (url: any, init?: any) => {
		aufrufe.push({ url: String(url), method: String(init?.method ?? 'GET') });
		return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
	}) as typeof fetch;
	return { fn, aufrufe };
}

function zerlege(url: string): { pfad: string; query: URLSearchParams } {
	const u = new URL(url, 'http://gz.invalid');
	return { pfad: u.pathname, query: u.searchParams };
}

describe('AC-15: Send-URL entsteht einheitlich (/api/briefings/{id}/send?kind=…)', () => {
	test('Trip ohne Berichtsart -> POST /api/briefings/{id}/send?kind=route (report_type fehlt oder morning)', async () => {
		const { fn, aufrufe } = server(200, { status: 'ok', kind: 'route', id: 'trip-ac15a', sent: true });
		const r = await sendSubscription('trip', 'trip-ac15a', {}, fn);
		assert.equal(aufrufe.length, 1);
		assert.equal(aufrufe[0].method, 'POST');
		const { pfad, query } = zerlege(aufrufe[0].url);
		assert.equal(pfad, '/api/briefings/trip-ac15a/send');
		assert.equal(query.get('kind'), 'route', 'Frontend-Wort trip muss auf kind=route abgebildet werden');
		const rt = query.get('report_type');
		assert.ok(rt === null || rt === 'morning', `report_type muss fehlen oder morning sein, war ${rt}`);
		assert.equal(r.kind, 'ok');
	});

	test('Trip mit Berichtsart evening -> kind=route&report_type=evening', async () => {
		const { fn, aufrufe } = server(200, { status: 'ok', kind: 'route', id: 'trip-ac15b', sent: true });
		await sendSubscription('trip', 'trip-ac15b', { reportType: 'evening' }, fn);
		assert.equal(aufrufe.length, 1);
		const { pfad, query } = zerlege(aufrufe[0].url);
		assert.equal(pfad, '/api/briefings/trip-ac15b/send');
		assert.equal(query.get('kind'), 'route');
		assert.equal(query.get('report_type'), 'evening');
	});

	test('Ortsvergleich -> POST /api/briefings/{id}/send?kind=vergleich, ohne report_type', async () => {
		const { fn, aufrufe } = server(200, { status: 'ok', kind: 'vergleich', id: 'cmp-ac15c', sent: true });
		const r = await sendSubscription('vergleich', 'cmp-ac15c', {}, fn);
		assert.equal(aufrufe.length, 1);
		assert.equal(aufrufe[0].method, 'POST');
		const { pfad, query } = zerlege(aufrufe[0].url);
		assert.equal(pfad, '/api/briefings/cmp-ac15c/send');
		assert.equal(query.get('kind'), 'vergleich');
		assert.equal(query.get('report_type'), null, 'report_type gilt nur fuer route');
		assert.equal(r.kind, 'ok');
	});

	test('Ortsvergleich trifft NICHT mehr den Alt-Pfad /api/compare/presets/{id}/send', async () => {
		const { fn, aufrufe } = server(200, { status: 'ok', kind: 'vergleich', id: 'cmp-ac15d', sent: true });
		await sendSubscription('vergleich', 'cmp-ac15d', {}, fn);
		assert.deepEqual(
			aufrufe.filter((a) => a.url.includes('/api/compare/presets/')).map((a) => a.url),
			[]
		);
	});

	test('ID wird URL-kodiert in den Pfad gesetzt', async () => {
		const { fn, aufrufe } = server(200, { status: 'ok', kind: 'vergleich', id: 'a b/c', sent: true });
		await sendSubscription('vergleich', 'a b/c', {}, fn);
		assert.equal(aufrufe.length, 1);
		assert.ok(
			aufrufe[0].url.startsWith(`/api/briefings/${encodeURIComponent('a b/c')}/send?`),
			`unerwartete URL: ${aufrufe[0].url}`
		);
	});
});

describe('AC-16: konkreter Grund statt generischer Fehlermeldung', () => {
	const FAELLE = [
		{ code: 'no_channels', detail: 'Für diesen Ortsvergleich ist kein Kanal eingestellt.' },
		{ code: 'channels_unreachable', detail: 'Keiner der eingestellten Kanäle war erreichbar.' },
		{ code: 'no_weather', detail: 'Für keinen der Orte liegen Wetterdaten vor.' }
	];

	for (const { code, detail } of FAELLE) {
		test(`Ortsvergleich 422 ${code} -> detail-Text unveraendert`, async () => {
			const { fn } = server(422, { detail, code });
			const r = await sendSubscription('vergleich', `cmp-ac16-${code}`, {}, fn);
			assert.equal(r.kind, 'rejected');
			assert.equal(r.message, detail);
			assert.notEqual(r.message, tr('fehler.versand.abgelehnt'));
			assert.equal(r.fehlendeOrte, undefined);
		});
	}

	test('Trip 422 no_channels -> detail-Text unveraendert (gleicher Pfad wie Ortsvergleich)', async () => {
		const detail = 'Für diesen Trip ist kein Kanal eingestellt.';
		const { fn } = server(422, { detail, code: 'no_channels' });
		const r = await sendSubscription('trip', 'trip-ac16', {}, fn);
		assert.equal(r.kind, 'rejected');
		assert.equal(r.message, detail);
	});

	test('Erfolg mit fehlende_orte (neue Erfolgsform) -> fehlendeOrte weitergegeben und in der Meldung genannt', async () => {
		const { fn } = server(200, {
			status: 'ok',
			kind: 'vergleich',
			id: 'cmp-ac16-ok',
			sent: true,
			fehlende_orte: ['alt-ort-1', 'alt-ort-2']
		});
		const r = await sendSubscription('vergleich', 'cmp-ac16-ok', {}, fn);
		assert.equal(r.kind, 'ok');
		assert.deepEqual(r.fehlendeOrte, ['alt-ort-1', 'alt-ort-2']);
		assert.match(r.message, /alt-ort-1/);
		assert.match(r.message, /alt-ort-2/);
	});
});
