// TDD — Issue #1232 Scheibe 3a: LayoutTab-Primitiva ltChannels.ts
//
// Reine Verhaltenstests (KEIN Mock, KEINE Dateiinhalt-Prüfung) auf
// LT_CHANNELS-Ableitung, ltBadge und ltOverflow.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/layout-tab/ltChannels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { LT_CHANNELS, LT_CH_BY_ID, ltBadge, ltOverflow } from './ltChannels.ts';
import { CHANNEL_COL_BUDGET } from '../../trip-detail/metricsEditor.ts';

describe('LT_CHANNELS — Ableitung aus CHANNEL_COL_BUDGET (einzige Kappungs-Quelle)', () => {
	test('email.max === Infinity (identisch zu CHANNEL_COL_BUDGET.email)', () => {
		assert.equal(LT_CH_BY_ID.email.max, Infinity);
		assert.equal(LT_CH_BY_ID.email.max, CHANNEL_COL_BUDGET.email);
	});

	test('telegram.max === 8 (identisch zu CHANNEL_COL_BUDGET.telegram)', () => {
		assert.equal(LT_CH_BY_ID.telegram.max, 8);
		assert.equal(LT_CH_BY_ID.telegram.max, CHANNEL_COL_BUDGET.telegram);
	});

	test('sms.max === 0 (identisch zu CHANNEL_COL_BUDGET.sms — keine eigene Zahl)', () => {
		assert.equal(LT_CH_BY_ID.sms.max, 0);
		assert.equal(LT_CH_BY_ID.sms.max, CHANNEL_COL_BUDGET.sms);
	});

	test('genau 3 Kanäle in fester Reihenfolge email/telegram/sms', () => {
		assert.deepEqual(
			LT_CHANNELS.map((c) => c.id),
			['email', 'telegram', 'sms']
		);
	});
});

describe('ltBadge — Anzeige-Chip je Kappungswert', () => {
	test('Infinity → "∞"', () => {
		assert.equal(ltBadge(Infinity), '∞');
	});

	test('0 → "—"', () => {
		assert.equal(ltBadge(0), '—');
	});

	test('8 → "8"', () => {
		assert.equal(ltBadge(8), '8');
	});
});

describe('ltOverflow — überschreitende Spaltenzahl je Kanal', () => {
	test('ltOverflow(10) enthält { telegram: 2 } und KEINEN email/sms-Schlüssel', () => {
		const result = ltOverflow(10);
		assert.equal(result.telegram, 2);
		assert.equal('email' in result, false);
		assert.equal('sms' in result, false);
	});

	test('ltOverflow(5) ist leer (unter dem Telegram-Budget von 8)', () => {
		assert.deepEqual(ltOverflow(5), {});
	});

	test('ltOverflow(8) ist leer (exakt am Budget — >, nicht >=)', () => {
		assert.deepEqual(ltOverflow(8), {});
	});
});
