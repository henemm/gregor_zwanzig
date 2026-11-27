// TDD RED — Issue #3440 (S5a): Versandweg mit Kanalwahl `channel` und Auswertung `sent_channels`.
// Spec: docs/specs/modules/feat_3440_test_schicken_menue.md — AC-6, AC-10, AC-12 (Kern-Schicht).
//
// VERTRAG für den Developer:
//   sendOutcome.briefingSendUrl(kind, id, reportType?, channel?: KanalId): string
//       hängt `&channel=<kanal>` an; ohne channel KEIN channel-Parameter („Alle eingerichteten Kanäle“).
//   sendOutcome.sendBriefing(kind, id, { reportType?, channel? }, fetchFn)
//   subscriptionExec.sendSubscription(kind, id, { reportType?, channel? }, fetchFn)
//       reichen `channel` durch (Trip: zusätzlich report_type, Vergleich: ohne report_type).
//   SendRunResult.sentChannels?: KanalId[]   — bei Erfolg aus `sent_channels` der Antwort.
// Fehlerklassifikation bleibt unverändert (fehler.versand.*, Server-`detail`).
//
// Gemessen wird die tatsächlich abgeschickte URL und das Ergebnis am einzigen Versand-Auslöser
// `sendSubscription`; der fetch-Ersatz ist die Transportgrenze (zeichnet auf, antwortet wie der Server).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/utils/__tests__/send_channel_3440.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { sendSubscription } from '../../components/shared/subscriptionExec.ts';
import { briefingSendUrl } from '../sendOutcome.ts';
import { tr } from '../../i18n/index.ts';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

function server(status: number, body: unknown): { fn: typeof fetch; urls: string[] } {
	const urls: string[] = [];
	const fn = (async (url: Json, init?: Json) => {
		assert.equal(String(init?.method ?? 'GET'), 'POST');
		urls.push(String(url));
		return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
	}) as typeof fetch;
	return { fn, urls };
}

const query = (url: string) => new URL(url, 'http://gz.invalid').searchParams;

describe('#3440 AC-6 — briefingSendUrl mit channel', () => {
	for (const kanal of ['email', 'telegram', 'sms', 'premium_sms'] as const) {
		test(`route + ${kanal}: kind, report_type und channel in der URL`, () => {
			const q = query((briefingSendUrl as Json)('route', 't-3440', 'evening', kanal));
			assert.equal(q.get('kind'), 'route');
			assert.equal(q.get('report_type'), 'evening');
			assert.equal(q.get('channel'), kanal);
		});
	}
	test('vergleich + telegram: channel, kein report_type', () => {
		const q = query((briefingSendUrl as Json)('vergleich', 'v-3440', undefined, 'telegram'));
		assert.equal(q.get('kind'), 'vergleich');
		assert.equal(q.get('channel'), 'telegram');
		assert.equal(q.get('report_type'), null);
	});
});

describe('#3440 AC-6 — sendSubscription reicht channel durch und liefert sentChannels', () => {
	test('Trip, Abend, Telegram ⇒ genau ein POST mit channel=telegram; Ergebnis ok mit sentChannels', async () => {
		const { fn, urls } = server(200, { status: 'ok', kind: 'route', id: 't1', sent: true, report_type: 'evening', sent_channels: ['telegram'] });
		const r: Json = await (sendSubscription as Json)('trip', 't1', { reportType: 'evening', channel: 'telegram' }, fn);
		assert.equal(urls.length, 1);
		const q = query(urls[0]);
		assert.equal(new URL(urls[0], 'http://gz.invalid').pathname, '/api/briefings/t1/send');
		assert.equal(q.get('kind'), 'route');
		assert.equal(q.get('report_type'), 'evening');
		assert.equal(q.get('channel'), 'telegram');
		assert.equal(r.kind, 'ok');
		assert.deepEqual(r.sentChannels, ['telegram']);
	});

	test('Vergleich, E-Mail ⇒ channel=email, ohne report_type', async () => {
		const { fn, urls } = server(200, { status: 'ok', kind: 'vergleich', id: 'v1', sent: true, sent_channels: ['email'] });
		const r: Json = await (sendSubscription as Json)('vergleich', 'v1', { channel: 'email' }, fn);
		const q = query(urls[0]);
		assert.equal(q.get('kind'), 'vergleich');
		assert.equal(q.get('channel'), 'email');
		assert.equal(q.get('report_type'), null);
		assert.deepEqual(r.sentChannels, ['email']);
	});
});

describe('#3440 AC-10 — „Alle eingerichteten Kanäle“: ohne channel, sentChannels aus der Antwort', () => {
	for (const kind of ['trip', 'vergleich'] as const) {
		test(`${kind}: kein channel-Parameter, sentChannels = sent_channels`, async () => {
			const { fn, urls } = server(200, { status: 'ok', kind: kind === 'trip' ? 'route' : 'vergleich', id: 'x', sent: true, sent_channels: ['email', 'telegram'] });
			const r: Json = await sendSubscription(kind, 'x', {}, fn);
			assert.equal(query(urls[0]).has('channel'), false, 'Alle-Versand darf keinen channel schicken');
			assert.equal(r.kind, 'ok');
			assert.deepEqual(r.sentChannels, ['email', 'telegram']);
		});
	}
});

describe('#3440 AC-12 — Fehlerfälle beim Einzelkanal: bestehende Texte, Request trägt channel', () => {
	const faelle: { name: string; status: number; body: Json; kind: string; message: () => string }[] = [
		{ name: 'Kanal nicht erreichbar (422)', status: 422, body: { code: 'channels_unreachable', detail: 'Kein Kanal erreichbar.' }, kind: 'rejected', message: () => 'Kein Kanal erreichbar.' },
		{ name: 'Kontingent erschöpft (429)', status: 429, body: { code: 'kontingent_erschoepft', detail: 'Tageskontingent erschöpft.' }, kind: 'rejected', message: () => 'Tageskontingent erschöpft.' },
		{ name: 'E-Mail unbestätigt (422)', status: 422, body: { code: 'email_unverified', detail: 'Adresse noch nicht bestätigt.' }, kind: 'rejected', message: () => 'Adresse noch nicht bestätigt.' },
		{ name: 'läuft bereits (409)', status: 409, body: { code: 'already_in_progress', detail: 'x' }, kind: 'already_running', message: () => tr('fehler.versand.laeuft_bereits') },
		{ name: 'Serverfehler (500)', status: 500, body: { code: 'send_failed', detail: 'x' }, kind: 'failed', message: () => tr('fehler.versand.fehlgeschlagen') }
	];
	for (const f of faelle) {
		test(f.name, async () => {
			const { fn, urls } = server(f.status, f.body);
			const r: Json = await (sendSubscription as Json)('trip', `t-${f.status}`, { reportType: 'morning', channel: 'sms' }, fn);
			assert.equal(query(urls[0]).get('channel'), 'sms', 'Einzelkanal-Request ohne channel');
			assert.equal(r.kind, f.kind);
			assert.equal(r.message, f.message());
			assert.ok(!r.sentChannels || r.sentChannels.length === 0, 'Fehlschlag darf keine gesendeten Kanäle melden');
		});
	}
});
