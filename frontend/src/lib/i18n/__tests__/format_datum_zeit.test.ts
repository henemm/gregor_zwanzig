// Issue #2647 (i18n S2) — AC-7: Datums- und Zeitformate in beiden Sprachen
// ohne Intl-Abkuerzungen. Lokale Date-Objekte (Konstruktor mit Jahr/Monat/Tag
// in Ortszeit) — damit ist der Test zeitzonenunabhaengig.
// Spec: docs/specs/modules/i18n_s2_frontend_sprachkern_2647.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/format_datum_zeit.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fmtDate, fmtDateNumeric, fmtTime, fmtWeekday, fmtRelativeMinutes } from '../format.ts';

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

// Issue #2651 (i18n F2) AC-5: numerisches Datum der Testmail-Zeile.
// Feste UTC-Zeitpunkte; die Zone Europe/Berlin gilt unabhaengig von der
// Zeitzone der Laufzeit (vorher: toLocaleDateString('de-DE', Europe/Berlin)).
describe('AC-5 (#2651): fmtDateNumeric', () => {
	const TESTMAIL = new Date('2026-10-30T10:00:00Z');
	test('de 30.10.2026, en 30 Oct 2026', () => {
		assert.equal(fmtDateNumeric(TESTMAIL, 'de'), '30.10.2026');
		assert.equal(fmtDateNumeric(TESTMAIL, 'en'), '30 Oct 2026');
	});
	test('de zweistellig, en ohne fuehrende Null', () => {
		const d = new Date('2026-01-05T12:00:00Z');
		assert.equal(fmtDateNumeric(d, 'de'), '05.01.2026');
		assert.equal(fmtDateNumeric(d, 'en'), '5 Jan 2026');
	});
	test('Zone Europe/Berlin: 23:30 UTC ist in Berlin schon der naechste Tag', () => {
		const d = new Date('2026-10-29T23:30:00Z'); // Berlin (MEZ) 30.10. 00:30
		assert.equal(fmtDateNumeric(d, 'de'), '30.10.2026');
		assert.equal(fmtDateNumeric(d, 'en'), '30 Oct 2026');
		const sommer = new Date('2026-06-30T22:30:00Z'); // Berlin (MESZ) 01.07. 00:30
		assert.equal(fmtDateNumeric(sommer, 'de'), '01.07.2026');
		assert.equal(fmtDateNumeric(sommer, 'en'), '1 Jul 2026');
	});
	test('de byte-gleich zur bisherigen Ausgabe (toLocaleDateString de-DE, Europe/Berlin)', () => {
		const alt = (d: Date) =>
			d.toLocaleDateString('de-DE', { timeZone: 'Europe/Berlin', day: '2-digit', month: '2-digit', year: 'numeric' });
		for (let i = 0; i < 400; i += 7) {
			const d = new Date(Date.UTC(2026, 0, 1, 23, 15) + i * 86_400_000);
			assert.equal(fmtDateNumeric(d, 'de'), alt(d), d.toISOString());
		}
	});
	test('jeder englische Monat hat sein Kuerzel', () => {
		const soll = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
		for (let m = 0; m < 12; m++) {
			assert.equal(fmtDateNumeric(new Date(Date.UTC(2026, m, 15, 12)), 'en'), `15 ${soll[m]} 2026`);
		}
	});
});
