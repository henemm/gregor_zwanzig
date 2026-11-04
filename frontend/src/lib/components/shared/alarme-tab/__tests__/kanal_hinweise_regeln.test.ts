// TDD RED — #1895 S3b2: reine Hinweis-Regeln `kanaeleOhneEmpfaenger` und `kanaeleMitSchwelle`
// in `../alertMetricChannels.ts` (fehlen noch ⇒ Aufruf rot). Spec alert_metric_channels.md
// AC-63..AC-70, AC-73. Namespace-Import, damit fehlende Exporte je Test rot werden.

import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as helfer from '../alertMetricChannels.ts';
import { channelConnectionStatus, type ConnectionProfile } from '../../versand-tab/channelConnectionStatus.ts';

type Fn = (...a: unknown[]) => unknown;
const ohneEmpf = (e: unknown, p: unknown) => (helfer as unknown as Record<string, Fn>).kanaeleOhneEmpfaenger(e, p) as string[];
const mitSchw = (e: unknown, s: unknown) => (helfer as unknown as Record<string, Fn>).kanaeleMitSchwelle(e, s) as Array<{ kanal: string; schwelle: string }>;

const alle = { email: true, telegram: true, sms: true, premium_sms: true };
const nur = (k: string) => ({ email: false, telegram: false, sms: false, premium_sms: false, [k]: true });
const VOLL: ConnectionProfile = {
	mail_to: 'a@x.de', telegram_chat_id: '42', sms_to: '+491', sms_allowed: true, sms_verified: true, premium_sms_reply_state: 'fresh'
};
const SCHW = (over: Record<string, string> = {}) => ({ email: 'LOW', telegram: 'LOW', sms: 'LOW', premium_sms: 'LOW', ...over });

test('AC-63: Telegram ohne Chat ⇒ kein Empfänger; mit Chat nicht', () => {
	assert.deepStrictEqual(ohneEmpf(nur('telegram'), { ...VOLL, telegram_chat_id: '' }), ['telegram']);
	assert.deepStrictEqual(ohneEmpf(nur('telegram'), { ...VOLL, telegram_chat_id: undefined }), ['telegram']);
	assert.deepStrictEqual(ohneEmpf(nur('telegram'), VOLL), []);
});

test('AC-64: SMS ohne Nummer, ohne Freigabe oder unbestätigt ⇒ kein Empfänger', () => {
	for (const p of [{ ...VOLL, sms_to: '' }, { ...VOLL, sms_allowed: false }, { ...VOLL, sms_verified: false }, { ...VOLL, sms_verified: undefined }]) {
		assert.deepStrictEqual(ohneEmpf(nur('sms'), p), ['sms'], JSON.stringify(p));
	}
	assert.deepStrictEqual(ohneEmpf(nur('sms'), VOLL), []);
});

test('AC-64: Gleichlauf mit channelConnectionStatus — „sendebereit" (good) ⇔ kein Hinweis', () => {
	const profile: ConnectionProfile[] = [
		VOLL, { ...VOLL, sms_to: '' }, { ...VOLL, sms_allowed: false }, { ...VOLL, sms_verified: false },
		{ ...VOLL, telegram_chat_id: '' }, {}
	];
	for (const p of profile) {
		const st = channelConnectionStatus(p);
		assert.strictEqual(ohneEmpf(nur('sms'), p).includes('sms'), st.sms.tone !== 'good', `sms ${JSON.stringify(p)}`);
		assert.strictEqual(ohneEmpf(nur('telegram'), p).includes('telegram'), st.telegram.tone !== 'good', `telegram ${JSON.stringify(p)}`);
	}
});

test('AC-65: Premium-SMS none/stale ⇒ kein Empfänger, fresh nicht', () => {
	assert.deepStrictEqual(ohneEmpf(nur('premium_sms'), { ...VOLL, premium_sms_reply_state: 'none' }), ['premium_sms']);
	assert.deepStrictEqual(ohneEmpf(nur('premium_sms'), { ...VOLL, premium_sms_reply_state: 'stale' }), ['premium_sms']);
	assert.deepStrictEqual(ohneEmpf(nur('premium_sms'), { ...VOLL, premium_sms_reply_state: 'fresh' }), []);
});

test('AC-66: E-Mail nie ohne Empfänger — auch bei leerem Profil', () => {
	assert.deepStrictEqual(ohneEmpf(nur('email'), {}), []);
	assert.deepStrictEqual(ohneEmpf(nur('email'), VOLL), []);
});

test('AC-63..66: nur gewählte Kanäle zählen, Reihenfolge wie KANAELE', () => {
	assert.deepStrictEqual(ohneEmpf(alle, {}), ['telegram', 'sms', 'premium_sms']);
	assert.deepStrictEqual(ohneEmpf(nur('email'), {}), []);
});

test('AC-67: Profil null/undefined ⇒ nie „kein Empfänger" raten', () => {
	assert.deepStrictEqual(ohneEmpf(alle, null), []);
	assert.deepStrictEqual(ohneEmpf(alle, undefined), []);
});

test('AC-68: keine eigene Wahl (null/undefined) ⇒ keine Hinweise', () => {
	assert.deepStrictEqual(ohneEmpf(null, {}), []);
	assert.deepStrictEqual(ohneEmpf(undefined, {}), []);
	assert.deepStrictEqual(mitSchw(null, SCHW({ telegram: 'HIGH' })), []);
	assert.deepStrictEqual(mitSchw(undefined, SCHW({ telegram: 'HIGH' })), []);
});

test('AC-69: Schwelle LOW ⇒ kein Schwellen-Hinweis, für alle vier Kanäle', () => {
	assert.deepStrictEqual(mitSchw(alle, SCHW()), []);
});

test('AC-70: MODERATE und HIGH ⇒ Hinweis je Kanal samt Schwelle', () => {
	for (const k of ['email', 'telegram', 'sms', 'premium_sms']) {
		for (const s of ['MODERATE', 'HIGH']) {
			assert.deepStrictEqual(mitSchw(nur(k), SCHW({ [k]: s })), [{ kanal: k, schwelle: s }], `${k} ${s}`);
		}
	}
});

test('AC-70: nur gewählte Kanäle; ungewählter Kanal mit hoher Schwelle bleibt still', () => {
	assert.deepStrictEqual(mitSchw(nur('email'), SCHW({ telegram: 'HIGH', email: 'MODERATE' })), [{ kanal: 'email', schwelle: 'MODERATE' }]);
	assert.deepStrictEqual(mitSchw(nur('email'), SCHW({ telegram: 'HIGH' })), []);
});

test('AC-73: zwei Nutzer — Stand von A beeinflusst B nicht (reine Funktion, kein Zustand)', () => {
	const A = { ...VOLL, telegram_chat_id: '42' };
	const B = { ...VOLL, telegram_chat_id: '' };
	assert.deepStrictEqual(ohneEmpf(nur('telegram'), A), []);
	assert.deepStrictEqual(ohneEmpf(nur('telegram'), B), ['telegram']);
	assert.deepStrictEqual(ohneEmpf(nur('telegram'), A), [], 'A nach B unverändert');
});
