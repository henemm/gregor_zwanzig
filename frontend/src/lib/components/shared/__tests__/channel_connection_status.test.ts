// TDD RED — Issue #1258 Scheibe S6 (R5): Kanal-Verbindungsstatus.
// AC-21 + Spec-Abschnitt 12 (S6-Detail-Festlegungen): channelConnectionStatus(profile)
// liefert je Kanal {tone, label} nach der dort festgelegten Zustands-Matrix.
//
// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (Abschnitt 12, AC-20/21/22)
// Context: docs/context/feat-1258-s6-r5-status-dot.md (R1-R4)
//
// `channelConnectionStatus.ts` existiert noch NICHT — Import schlägt heute fehl
// (RED), bis Phase B das Modul unter
// frontend/src/lib/components/shared/versand-tab/channelConnectionStatus.ts anlegt.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/__tests__/channel_connection_status.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';

import { channelConnectionStatus } from '../versand-tab/channelConnectionStatus.ts';

test('#1258 AC-21: E-Mail bestätigt (mail_to + email_verified) -> good/"bestätigt"', () => {
	const status = channelConnectionStatus({ mail_to: 'a@b.de', email_verified: true });
	assert.deepEqual(status.email, { tone: 'good', label: 'bestätigt' });
});

test('#1258 AC-21/Abschnitt-12-Kante: E-Mail konfiguriert aber unbestätigt -> neutral/"nicht bestätigt"', () => {
	const status = channelConnectionStatus({ mail_to: 'a@b.de', email_verified: false });
	assert.deepEqual(status.email, { tone: 'neutral', label: 'nicht bestätigt' });
});

test('#1258 AC-21: E-Mail fehlt -> neutral/"nicht verbunden"', () => {
	const status = channelConnectionStatus({ email_verified: true });
	assert.deepEqual(status.email, { tone: 'neutral', label: 'nicht verbunden' });
});

test('#1258 AC-21: Telegram mit chat_id -> good/"verbunden"', () => {
	const status = channelConnectionStatus({ telegram_chat_id: '999' });
	assert.deepEqual(status.telegram, { tone: 'good', label: 'verbunden' });
});

test('#1258 AC-21: Telegram ohne chat_id -> neutral/"nicht verbunden"', () => {
	const status = channelConnectionStatus({});
	assert.deepEqual(status.telegram, { tone: 'neutral', label: 'nicht verbunden' });
});

test('#1258 AC-21: SMS hinterlegt und Tier erlaubt -> good/"hinterlegt"', () => {
	const status = channelConnectionStatus({ sms_to: '+491511234567', sms_allowed: true });
	assert.deepEqual(status.sms, { tone: 'good', label: 'hinterlegt' });
});

test('#1258 Abschnitt-12-Kante: SMS hinterlegt aber Tier-gesperrt (sms_allowed:false) -> neutral/"nicht verbunden"', () => {
	const status = channelConnectionStatus({ sms_to: '+491511234567', sms_allowed: false });
	assert.deepEqual(status.sms, { tone: 'neutral', label: 'nicht verbunden' });
});

test('#1258 AC-21: SMS ohne Nummer -> neutral/"nicht verbunden"', () => {
	const status = channelConnectionStatus({ sms_allowed: true });
	assert.deepEqual(status.sms, { tone: 'neutral', label: 'nicht verbunden' });
});

test('#1258 AC-21: leeres Profil -> alle drei Kanäle neutral/"nicht verbunden"', () => {
	const status = channelConnectionStatus({});
	assert.deepEqual(status, {
		email: { tone: 'neutral', label: 'nicht verbunden' },
		telegram: { tone: 'neutral', label: 'nicht verbunden' },
		sms: { tone: 'neutral', label: 'nicht verbunden' }
	});
});

test('#1258 AC-21: null-Profil -> alle drei Kanäle neutral/"nicht verbunden"', () => {
	const status = channelConnectionStatus(null);
	assert.deepEqual(status, {
		email: { tone: 'neutral', label: 'nicht verbunden' },
		telegram: { tone: 'neutral', label: 'nicht verbunden' },
		sms: { tone: 'neutral', label: 'nicht verbunden' }
	});
});
