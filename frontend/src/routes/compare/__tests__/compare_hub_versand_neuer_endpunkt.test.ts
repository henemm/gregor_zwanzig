// Issue #2280 (AC-15, AC-16) — der Senden-Klick im Ortsvergleich-Hub laeuft ueber den
// einheitlichen Ausloeser und trifft den neuen Endpunkt /api/briefings/{id}/send?kind=vergleich.
// Gemessen am ECHTEN Instanz-Code von routes/compare/[id]/+page.svelte (Pruefstand
// `umgebungFuer`, echte Importe) gegen einen aufzeichnenden Ersatz-Server — nicht am Quelltext.
// Spec: docs/specs/modules/feat_2280_handversand_endpoint.md
//
// Pfadregel #1409: relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/compare/__tests__/compare_hub_versand_neuer_endpunkt.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { umgebungFuer } from '../../../lib/components/shared/__tests__/svelteInstanzPruefstand.ts';
import { clearEtagRegistry } from '../../../lib/etagRegistry.ts';
import { tr } from '../../../lib/i18n/index.ts';

const SEITE = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', '[id]', '+page.svelte');

interface Aufruf {
	method: string;
	url: string;
}
let aufrufe: Aufruf[] = [];
let antwort: { status: number; body: unknown } = { status: 200, body: {} };
let originalFetch: typeof fetch;
let originalWindow: unknown;

const PRESET = { id: 'c2280', name: 'Vergleich', location_ids: ['a', 'b'], schedule: 'daily', previous_schedule: 'daily' };

beforeEach(() => {
	clearEtagRegistry();
	aufrufe = [];
	antwort = { status: 200, body: { status: 'ok', kind: 'vergleich', id: PRESET.id, sent: true } };
	originalFetch = globalThis.fetch;
	originalWindow = (globalThis as any).window;
	(globalThis as any).window = { location: { href: '', reload() {} } };
	globalThis.fetch = (async (url: any, init?: any) => {
		aufrufe.push({ method: String(init?.method ?? 'GET'), url: String(url) });
		return new Response(JSON.stringify(antwort.body), {
			status: antwort.status,
			headers: { 'Content-Type': 'application/json' }
		});
	}) as typeof fetch;
});
afterEach(() => {
	globalThis.fetch = originalFetch;
	(globalThis as any).window = originalWindow;
});

async function hub() {
	const { u } = await umgebungFuer(
		SEITE,
		{ data: { preset: { ...PRESET }, locations: [], profile: { mail_to: 'a@example.org' } } },
		{ jsAlsTs: true }
	);
	return u;
}

const posts = () => aufrufe.filter((a) => a.method === 'POST');

describe('AC-15: Hub-Klick trifft den neuen Endpunkt', () => {
	test('handleTestSend -> genau ein POST /api/briefings/c2280/send?kind=vergleich', async () => {
		const u = await hub();
		await u.handleTestSend();
		assert.equal(posts().length, 1, `erwartet genau einen POST, war: ${JSON.stringify(posts())}`);
		const url = new URL(posts()[0].url, 'http://gz.invalid');
		assert.equal(url.pathname, '/api/briefings/c2280/send');
		assert.equal(url.searchParams.get('kind'), 'vergleich');
		assert.equal(u.isSending, false);
	});

	test('handleTestSend trifft NICHT den Alt-Pfad /api/compare/presets/{id}/send', async () => {
		const u = await hub();
		await u.handleTestSend();
		assert.deepEqual(
			posts().filter((a) => a.url.includes('/api/compare/presets/')).map((a) => a.url),
			[]
		);
	});
});

describe('AC-16: Hub zeigt den konkreten Grund', () => {
	for (const [code, detail] of [
		['no_channels', 'Für diesen Ortsvergleich ist kein Kanal eingestellt.'],
		['channels_unreachable', 'Keiner der eingestellten Kanäle war erreichbar.'],
		['no_weather', 'Für keinen der Orte liegen Wetterdaten vor.']
	] as const) {
		test(`422 ${code} am neuen Endpunkt -> sendMsg ist der detail-Text`, async () => {
			antwort = { status: 422, body: { detail, code } };
			const u = await hub();
			await u.handleTestSend();
			assert.ok(
				posts().some((a) => a.url.startsWith('/api/briefings/c2280/send')),
				`Versand ging nicht an den neuen Endpunkt: ${JSON.stringify(posts())}`
			);
			assert.equal(u.sendMsg, detail);
			assert.notEqual(u.sendMsg, tr('fehler.versand.abgelehnt'));
		});
	}

	test('Erfolg mit fehlende_orte am neuen Endpunkt -> Meldung nennt die fehlenden Orte', async () => {
		antwort = {
			status: 200,
			body: { status: 'ok', kind: 'vergleich', id: PRESET.id, sent: true, fehlende_orte: ['alt-ort-9'] }
		};
		const u = await hub();
		await u.handleTestSend();
		assert.ok(posts().some((a) => a.url.startsWith('/api/briefings/c2280/send')));
		assert.match(String(u.sendMsg), /alt-ort-9/);
	});
});
