// Issue #2647 (i18n S2) — AC-7: Datums- und Zeitformate in beiden Sprachen
// ohne Intl-Abkuerzungen. Lokale Date-Objekte (Konstruktor mit Jahr/Monat/Tag
// in Ortszeit) — damit ist der Test zeitzonenunabhaengig.
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/format_datum_zeit.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fmtDate, fmtTime, fmtWeekday, fmtRelativeMinutes } from '../format.ts';

// 30.10.2026 14:30 Ortszeit — ein Freitag.
const FR = new Date(2026, 9, 30, 14, 30);
// 5.1.2026 08:05 Ortszeit — ein Montag (einstellige Tage/Monate, fuehrende Nullen).
const MO = new Date(2026, 0, 5, 8, 5);

describe('AC-7: fmtDate', () => {
	test('kurz', () => {
		assert.equal(fmtDate(FR, 'de', 'kurz'), 'Fr 30.10.');
		assert.equal(fmtDate(FR, 'en', 'kurz'), 'Fri 30 Oct');
		assert.equal(fmtDate(MO, 'de', 'kurz'), 'Mo 05.01.');
		assert.equal(fmtDate(MO, 'en', 'kurz'), 'Mon 5 Jan');
	});
	test('lang', () => {
		assert.equal(fmtDate(FR, 'de', 'lang'), 'Freitag, 30. Oktober 2026');
		assert.equal(fmtDate(FR, 'en', 'lang'), 'Friday, 30 October 2026');
		assert.equal(fmtDate(MO, 'de', 'lang'), 'Montag, 5. Januar 2026');
		assert.equal(fmtDate(MO, 'en', 'lang'), 'Monday, 5 January 2026');
	});
	test('jeder Wochentag einer Woche hat das richtige Kuerzel (berechnet, nicht geraten)', () => {
		const de = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
		const en = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
		for (let i = 0; i < 7; i++) {
			const d = new Date(2026, 0, 5 + i, 12, 0); // 5.1.2026 ist ein Montag
			assert.equal(fmtWeekday(d, 'de'), de[i]);
			assert.equal(fmtWeekday(d, 'en'), en[i]);
		}
	});
});

describe('AC-7: fmtWeekday', () => {
	test('kurz (Standard) und ausgeschrieben', () => {
		assert.equal(fmtWeekday(FR, 'de'), 'Fr');
		assert.equal(fmtWeekday(FR, 'en'), 'Fri');
		assert.equal(fmtWeekday(FR, 'de', false), 'Freitag');
		assert.equal(fmtWeekday(FR, 'en', false), 'Friday');
	});
});

describe('AC-7: fmtTime', () => {
	test('24 h, beide Sprachen gleich, fuehrende Nullen', () => {
		assert.equal(fmtTime(FR), '14:30');
		assert.equal(fmtTime(MO), '08:05');
	});
});

describe('AC-7: fmtRelativeMinutes', () => {
	test('Plural ueber den Katalog', () => {
		assert.equal(fmtRelativeMinutes(3, 'de'), 'vor 3 Min');
		assert.equal(fmtRelativeMinutes(3, 'en'), '3 min ago');
		assert.equal(fmtRelativeMinutes(1, 'de'), 'vor 1 Min');
		assert.equal(fmtRelativeMinutes(1, 'en'), '1 min ago');
	});
	test('unter einer Minute: gerade eben / just now', () => {
		assert.equal(fmtRelativeMinutes(0, 'de'), 'gerade eben');
		assert.equal(fmtRelativeMinutes(0.4, 'en'), 'just now');
	});
});
