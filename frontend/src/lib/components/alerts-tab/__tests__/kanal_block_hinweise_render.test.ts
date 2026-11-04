// TDD RED — #1895 S3b2: Hinweise „Kanal ohne Empfänger" und „Kanal-Schwelle über Metrik-Stufe"
// im `AlertMetricChannelsBlock.svelte` (neue Props `profil`, `schwellen`). SSR-Muster wie
// kanal_block_zeilen_und_hinweise_render.test.ts. Spec alert_metric_channels.md AC-63..AC-73, AC-75.
// Testids: kanal-hinweis-kein-empfaenger-<k>, kanal-hinweis-schwelle-<k>.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { derivePremiumSmsAlarmGate } from '../../shared/alarme-tab/premiumSmsAlarmGate.ts';
import { locale, trFor } from '../../../i18n/index.ts';
import { umgebungFuer } from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const Block = (await import(pathToFileURL(path.join(HERE, '..', 'AlertMetricChannelsBlock.svelte')).href)).default;

const ANTWORT = { keys: { thunder_level: ['thunder'] }, accepted: ['thunder'] };
const NUR_MAIL = { email: true, telegram: false, sms: false, premium_sms: false };
const TG = { email: false, telegram: true, sms: false, premium_sms: false };
const PSMS = { email: false, telegram: false, sms: false, premium_sms: true };
const ALLE = { email: true, telegram: true, sms: true, premium_sms: true };
const VOLL = { mail_to: 'a@x.de', telegram_chat_id: '42', sms_to: '+491', sms_allowed: true, sms_verified: true, premium_sms_reply_state: 'fresh' };
const LOW = { email: 'LOW', telegram: 'LOW', sms: 'LOW', premium_sms: 'LOW' };
const KANAELE = ['email', 'telegram', 'sms', 'premium_sms'];

const props = (over: Record<string, unknown> = {}) => ({
	aktiveMetriken: ['thunder_level'], eintraege: { thunder: TG }, aboKanaele: NUR_MAIL,
	premiumSmsGate: derivePremiumSmsAlarmGate({ premium_sms_allowed: true }), schluesselOverride: ANTWORT,
	profil: VOLL, schwellen: LOW, onChange: () => {}, ...over
});
const html = (over: Record<string, unknown> = {}): string => render(Block, { props: props(over) }).body;
const hat = (h: string, id: string) => h.includes(`data-testid="${id}"`);
const OHNE_CHAT = { ...VOLL, telegram_chat_id: '' };

test('AC-63: Telegram ohne Chat ⇒ Hinweis kein Empfänger; mit Chat nicht', () => {
	assert.ok(hat(html({ profil: OHNE_CHAT }), 'kanal-hinweis-kein-empfaenger-telegram'));
	assert.ok(!hat(html(), 'kanal-hinweis-kein-empfaenger-telegram'));
});

test('AC-63: Hinweistext nennt den Kanalnamen', () => {
	const h = html({ profil: OHNE_CHAT });
	const i = h.indexOf('data-testid="kanal-hinweis-kein-empfaenger-telegram"');
	assert.notEqual(i, -1, 'Hinweis fehlt');
	assert.ok(h.slice(i, h.indexOf('</p>', i)).includes('Telegram'));
});

test('AC-65: Premium-SMS none/stale ⇒ Hinweis, fresh nicht', () => {
	for (const s of ['none', 'stale']) {
		assert.ok(hat(html({ eintraege: { thunder: PSMS }, profil: { ...VOLL, premium_sms_reply_state: s } }), 'kanal-hinweis-kein-empfaenger-premium_sms'), s);
	}
	assert.ok(!hat(html({ eintraege: { thunder: PSMS } }), 'kanal-hinweis-kein-empfaenger-premium_sms'));
});

test('AC-66: E-Mail gewählt, leeres Profil ⇒ kein Empfänger-Hinweis', () => {
	const h = html({ eintraege: { thunder: NUR_MAIL }, profil: {} });
	assert.ok(!h.includes('kanal-hinweis-kein-empfaenger-email'));
});

test('AC-67: Profil null ⇒ kein Empfänger-Hinweis; Schwellen-Hinweis bleibt', () => {
	const h = html({ eintraege: { thunder: ALLE }, profil: null, schwellen: { ...LOW, telegram: 'HIGH' } });
	for (const k of ['telegram', 'sms', 'premium_sms']) assert.ok(!hat(h, `kanal-hinweis-kein-empfaenger-${k}`), k);
	assert.ok(hat(h, 'kanal-hinweis-schwelle-telegram'));
});

test('AC-68: Zeile „wie Abo-Kanäle" ⇒ weder Empfänger- noch Schwellen-Hinweis', () => {
	const hoch = { email: 'HIGH', telegram: 'HIGH', sms: 'HIGH', premium_sms: 'HIGH' };
	const h = html({ eintraege: { thunder: null }, profil: {}, schwellen: hoch });
	assert.ok(!h.includes('kanal-hinweis-kein-empfaenger-'));
	assert.ok(!h.includes('kanal-hinweis-schwelle-'));
});

test('AC-69/AC-70: LOW ⇒ kein Hinweis; MODERATE/HIGH ⇒ Hinweis nur am betroffenen Kanal', () => {
	assert.ok(!html({ eintraege: { thunder: ALLE } }).includes('kanal-hinweis-schwelle-'));
	for (const k of KANAELE) {
		for (const s of ['MODERATE', 'HIGH']) {
			const h = html({ eintraege: { thunder: ALLE }, schwellen: { ...LOW, [k]: s } });
			assert.ok(hat(h, `kanal-hinweis-schwelle-${k}`), `${k} ${s}`);
			for (const a of KANAELE.filter((x) => x !== k)) assert.ok(!hat(h, `kanal-hinweis-schwelle-${a}`), `${a} still bei ${k}`);
		}
	}
});

test('AC-70: Schwellen-Hinweis nennt Kanalnamen', () => {
	const h = html({ schwellen: { ...LOW, telegram: 'HIGH' } });
	const i = h.indexOf('data-testid="kanal-hinweis-schwelle-telegram"');
	assert.notEqual(i, -1, 'Hinweis fehlt');
	assert.ok(h.slice(i, h.indexOf('</p>', i)).includes('Telegram'));
});

test('AC-71: beide Hinweise gleichzeitig, jeder mit eigener Testid', () => {
	const h = html({ profil: OHNE_CHAT, schwellen: { ...LOW, telegram: 'HIGH' } });
	assert.ok(hat(h, 'kanal-hinweis-kein-empfaenger-telegram'));
	assert.ok(hat(h, 'kanal-hinweis-schwelle-telegram'));
});

test('AC-72: Hinweis sperrt nichts — Schalter bedienbar, Eintrag unverändert', async () => {
	const over = { profil: OHNE_CHAT, schwellen: { ...LOW, telegram: 'HIGH' } };
	const h = html(over);
	assert.ok(hat(h, 'kanal-hinweis-kein-empfaenger-telegram'), 'Hinweis muss da sein, sonst beweist der Test nichts');
	const i = h.indexOf('data-testid="kanal-schalter-thunder-telegram"');
	assert.notEqual(i, -1);
	assert.doesNotMatch(h.slice(i, h.indexOf('</div>', i)), /\sdisabled/);
	const rufe: unknown[][] = [];
	const { u } = await umgebungFuer(path.join(HERE, '..', 'AlertMetricChannelsBlock.svelte'), props({
		...over, onChange: (...a: unknown[]) => rufe.push(a)
	}));
	u.kanalSetzen('thunder', 'email', true);
	assert.deepStrictEqual(rufe, [['thunder', { ...TG, email: true }]]);
});

test('AC-73: zwei Nutzer — A (Chat) ohne, B (kein Chat) mit Hinweis', () => {
	assert.ok(!hat(html({ profil: { ...VOLL, telegram_chat_id: '42' } }), 'kanal-hinweis-kein-empfaenger-telegram'));
	assert.ok(hat(html({ profil: OHNE_CHAT }), 'kanal-hinweis-kein-empfaenger-telegram'));
});

test('AC-75: Hinweise erscheinen in DE und EN (Kanalname bleibt Protokoll-Token)', () => {
	try {
		for (const lang of ['de', 'en'] as const) {
			locale.set(lang);
			const h = html({ profil: OHNE_CHAT, schwellen: { ...LOW, telegram: 'HIGH' } });
			const i = h.indexOf('data-testid="kanal-hinweis-kein-empfaenger-telegram"');
			assert.notEqual(i, -1, `${lang}: Hinweis fehlt`);
			const erwartet = trFor(lang, 'alarme.kanaele.kein_empfaenger' as never, { kanal: 'Telegram' } as never);
			assert.ok(!String(erwartet).startsWith('alarme.kanaele'), `${lang}: Katalogschlüssel fehlt`);
			assert.ok(h.slice(i, h.indexOf('</p>', i)).includes('Telegram'));
		}
	} finally {
		locale.set('de');
	}
});
