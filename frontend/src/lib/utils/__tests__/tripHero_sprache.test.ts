// Issue #2652 (i18n F3, Epic #2644) — AC-2: Tagesangaben (`getDaysLabel`) und
// Zeitraum (`formatDateRange`) sprechen die Nutzersprache. Plural ueber trn()
// (`x.one`/`x.other`), Monatsnamen und Zeitraum-Muster aus dem Katalog.
// Deutsch bleibt byte-gleich zu den bisherigen Werten (tripHero.test.ts).
// Jeder en-Fall ruft zuerst unter `de` und schaltet dann OHNE Neuladen auf
// `en`: eine Mutation tr()/trn() -> trFor('de', …) macht ihn rot.
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/lib/utils/__tests__/tripHero_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { getDaysLabel, formatDateRange } from '../tripHero.ts';
import { locale, trFor, trnFor } from '../../i18n/index.ts';
import type { Trip, Stage } from '../../types.ts';

afterEach(() => locale.set('de'));

const stage = (date: string): Stage => ({ id: `s-${date}`, name: 'E', date, waypoints: [] }) as Stage;
const trip = (o: Partial<Trip>): Trip => ({ id: 't1', name: 'T', stages: [], ...o }) as Trip;
const HEUTE = new Date('2026-10-12T12:00:00');

const PAUSIERT_1 = trip({ paused_at: '2026-10-11T08:00:00', stages: [stage('2026-10-20')] });
const PAUSIERT_3 = trip({ paused_at: '2026-10-09T08:00:00', stages: [stage('2026-10-20')] });
const LAUFEND_TAG_2 = trip({ stages: [stage('2026-10-11'), stage('2026-10-12'), stage('2026-10-13')] });
const BEENDET_1 = trip({ stages: [stage('2026-10-10'), stage('2026-10-11')] });
const BEENDET_3 = trip({ stages: [stage('2026-10-08'), stage('2026-10-09')] });
const GEPLANT_1 = trip({ stages: [stage('2026-10-13')] });
const GEPLANT_5 = trip({ stages: [stage('2026-10-17')] });
const OKTOBER = trip({ stages: [stage('2026-10-01'), stage('2026-10-05')] });
const MONATSWECHSEL = trip({ stages: [stage('2026-09-30'), stage('2026-10-03')] });
const JAHRESWECHSEL = trip({ stages: [stage('2025-12-30'), stage('2026-01-03')] });
const EIN_TAG = trip({ stages: [stage('2026-05-11')] });

/** Erst de rendern, dann ohne Neuladen auf en schalten. */
function nachWechsel<T>(f: () => T): T {
	locale.set('de');
	f();
	locale.set('en');
	return f();
}

describe('AC-2: getDaysLabel englisch (Plural ueber trn)', () => {
	test('pausiert: paused for 1 day / paused for 3 days', () => {
		assert.equal(nachWechsel(() => getDaysLabel(PAUSIERT_1, HEUTE)), 'paused for 1 day');
		assert.equal(getDaysLabel(PAUSIERT_3, HEUTE), 'paused for 3 days');
		assert.equal(getDaysLabel(PAUSIERT_3, HEUTE), trnFor('en', 'home.tage.pausiert_seit', 3));
	});
	test('laufend: running since day 2', () => {
		assert.equal(nachWechsel(() => getDaysLabel(LAUFEND_TAG_2, HEUTE)), 'running since day 2');
		assert.equal(getDaysLabel(LAUFEND_TAG_2, HEUTE), trFor('en', 'home.tage.laeuft_seit', { tag: 2 }));
	});
	test('beendet: ended 1 day ago / ended 3 days ago', () => {
		assert.equal(nachWechsel(() => getDaysLabel(BEENDET_1, HEUTE)), 'ended 1 day ago');
		assert.equal(getDaysLabel(BEENDET_3, HEUTE), 'ended 3 days ago');
	});
	test('geplant: tomorrow / in 5 days, ohne Etappen: Katalogtext', () => {
		assert.equal(nachWechsel(() => getDaysLabel(GEPLANT_1, HEUTE)), trFor('en', 'home.tage.morgen'));
		assert.equal(getDaysLabel(GEPLANT_5, HEUTE), trnFor('en', 'home.tage.in_tagen', 5));
		assert.equal(getDaysLabel(trip({}), HEUTE), trFor('en', 'home.tage.nicht_geplant'));
		assert.doesNotMatch(getDaysLabel(GEPLANT_5, HEUTE), /Tagen|morgen|heute/);
	});
});

describe('AC-2: getDaysLabel deutsch byte-gleich (Bestandswerte, auch "1 Tagen")', () => {
	test('pausiert seit 1 Tagen, läuft seit Tag 2, beendet vor 3 Tagen, in 5 Tagen, morgen', () => {
		locale.set('en');
		getDaysLabel(PAUSIERT_1, HEUTE);
		locale.set('de');
		assert.equal(getDaysLabel(PAUSIERT_1, HEUTE), 'pausiert seit 1 Tagen');
		assert.equal(getDaysLabel(LAUFEND_TAG_2, HEUTE), 'läuft seit Tag 2');
		assert.equal(getDaysLabel(BEENDET_3, HEUTE), 'beendet vor 3 Tagen');
		assert.equal(getDaysLabel(BEENDET_1, HEUTE), 'beendet vor 1 Tagen');
		assert.equal(getDaysLabel(GEPLANT_5, HEUTE), 'in 5 Tagen');
		assert.equal(getDaysLabel(GEPLANT_1, HEUTE), 'morgen');
		assert.equal(getDaysLabel(trip({}), HEUTE), 'Trip noch nicht geplant');
	});
});

describe('AC-2: formatDateRange je Sprache', () => {
	test('gleicher Monat: 1–5 October 2026 / 1.–5. Oktober 2026', () => {
		assert.equal(nachWechsel(() => formatDateRange(OKTOBER)), '1–5 October 2026');
		locale.set('de');
		assert.equal(formatDateRange(OKTOBER), '1.–5. Oktober 2026');
	});
	test('Monatswechsel, Jahreswechsel und einzelner Tag englisch', () => {
		assert.equal(nachWechsel(() => formatDateRange(MONATSWECHSEL)), '30 September – 3 October 2026');
		assert.equal(formatDateRange(JAHRESWECHSEL), '30 December 2025 – 3 January 2026');
		assert.equal(formatDateRange(EIN_TAG), '11 May 2026');
	});
	test('deutsch byte-gleich zu tripHero.test.ts', () => {
		locale.set('de');
		assert.equal(formatDateRange(MONATSWECHSEL), '30. September – 3. Oktober 2026');
		assert.equal(formatDateRange(JAHRESWECHSEL), '30. Dezember 2025 – 3. Januar 2026');
		assert.equal(formatDateRange(EIN_TAG), '11. Mai 2026');
	});
});
