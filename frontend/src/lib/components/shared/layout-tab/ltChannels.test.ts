// TDD — Issue #1232 Scheibe 3a: LayoutTab-Primitiva ltChannels.ts
//
// Reine Verhaltenstests (KEIN Mock, KEINE Dateiinhalt-Prüfung) auf
// LT_CHANNELS-Ableitung, ltBadgeForLimit und ltOverflowForLimit.
//
// Issue #1719 Scheibe S3 (GREEN, Bestandstest umgedreht): das Budget-Modell
// wechselt von einer einzigen Spaltenzahl je Kanal (`max: number`) auf eine
// EINHEIT je Kanal (`limit: LtLimit`) — Telegram sinkt von 8 auf 7
// Metrik-Spalten (die 8. Spalte ist die Uhrzeit), SMS trägt eine
// Zeichengrenze statt des Spalten-Sentinels 0. Vier Assertions auf `8` und
// eine auf `ltBadge(0) === '—'` kodierten das ALTE, falsche Modell — hier
// auf das neue umgestellt statt gelöscht (das Verhalten "SMS hat kein
// Spalten-Raster" gilt weiterhin, nur nicht mehr über eine Spaltenzahl).
//
// Spec: docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md (Abschnitt 5, 6)
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/layout-tab/ltChannels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	LT_CHANNELS,
	LT_CH_BY_ID,
	ltBadgeForLimit,
	ltOverflowForLimit,
	ltOverflowAcrossChannels,
	TELEGRAM_METRIC_COLUMNS,
	SMS_TRIP_CHAR_LIMIT
} from './ltChannels.ts';
import { CHANNEL_COL_BUDGET } from '../../trip-detail/metricsEditor.ts';

describe('LT_CHANNELS — Ableitung aus CHANNEL_COL_BUDGET / dem LtLimit-Modell', () => {
	test('email.limit === { kind: "none" } (identisch zu CHANNEL_COL_BUDGET.email === Infinity)', () => {
		assert.deepEqual(LT_CH_BY_ID.email.limit, { kind: 'none' });
		assert.equal(CHANNEL_COL_BUDGET.email, Infinity);
	});

	test('telegram.limit === { kind: "columns", value: 7 } (Issue #1719 S3: von 8 auf 7 korrigiert)', () => {
		assert.deepEqual(LT_CH_BY_ID.telegram.limit, { kind: 'columns', value: 7 });
		assert.equal(
			TELEGRAM_METRIC_COLUMNS,
			CHANNEL_COL_BUDGET.telegram,
			'TELEGRAM_METRIC_COLUMNS muss aus CHANNEL_COL_BUDGET.telegram abgeleitet sein — keine zweite Zahl'
		);
	});

	test('sms.limit === { kind: "chars", value: SMS_TRIP_CHAR_LIMIT } (KEINE Spaltenzahl mehr — SMS hat kein Raster)', () => {
		assert.deepEqual(LT_CH_BY_ID.sms.limit, { kind: 'chars', value: SMS_TRIP_CHAR_LIMIT });
		assert.equal(SMS_TRIP_CHAR_LIMIT, 160);
	});

	test('genau 3 Kanäle in fester Reihenfolge email/telegram/sms', () => {
		assert.deepEqual(
			LT_CHANNELS.map((c) => c.id),
			['email', 'telegram', 'sms']
		);
	});
});

describe('ltBadgeForLimit — Anzeige-Chip je Kappungswert', () => {
	test("{kind:'none'} → '∞'", () => {
		assert.equal(ltBadgeForLimit({ kind: 'none' }), '∞');
	});

	test("{kind:'chars', value:160} → '160' (NICHT '—' — AC-4: SMS zeigt die Zeichenzahl)", () => {
		assert.equal(ltBadgeForLimit({ kind: 'chars', value: 160 }), '160');
	});

	test("{kind:'columns', value:7} → '7'", () => {
		assert.equal(ltBadgeForLimit({ kind: 'columns', value: 7 }), '7');
	});
});

describe('ltOverflowForLimit — überschreitende Spaltenzahl (NUR für kind:columns)', () => {
	test("{kind:'columns', value:7}, 9 → 2 (AC-3: 9 aktive Metriken, Telegram-Budget 7)", () => {
		assert.equal(ltOverflowForLimit({ kind: 'columns', value: 7 }, 9), 2);
	});

	test("{kind:'columns', value:7}, 5 → undefined (unter dem Budget)", () => {
		assert.equal(ltOverflowForLimit({ kind: 'columns', value: 7 }, 5), undefined);
	});

	test("{kind:'columns', value:7}, 7 → undefined (exakt am Budget — >, nicht >=)", () => {
		assert.equal(ltOverflowForLimit({ kind: 'columns', value: 7 }, 7), undefined);
	});

	test("{kind:'chars', value:160}, 999 → undefined (AC-4: für SMS wird kein Überlauf berechnet)", () => {
		assert.equal(ltOverflowForLimit({ kind: 'chars', value: 160 }, 999), undefined);
	});

	test("{kind:'none'}, 999 → undefined (Email ist unbegrenzt)", () => {
		assert.equal(ltOverflowForLimit({ kind: 'none' }, 999), undefined);
	});
});

describe('ltOverflowAcrossChannels — Überlauf-Chip über alle Kanal-Tabs für denselben colCount', () => {
	test('ltOverflowAcrossChannels(9, 160) enthält { telegram: 2 } und KEINEN email/sms-Schlüssel', () => {
		const result = ltOverflowAcrossChannels(9, SMS_TRIP_CHAR_LIMIT);
		assert.equal(result.telegram, 2);
		assert.equal('email' in result, false);
		assert.equal('sms' in result, false, 'SMS (kind:chars) darf keinen Überlauf-Eintrag bekommen');
	});

	test('ltOverflowAcrossChannels(5, 160) ist leer (unter dem Telegram-Budget von 7)', () => {
		assert.deepEqual(ltOverflowAcrossChannels(5, SMS_TRIP_CHAR_LIMIT), {});
	});
});
