// Issue #2652 (i18n F3, Epic #2644) — AC-2: Zeitraum (`formatDateRange`) sprechen die Nutzersprache. Plural ueber trn()
// (`x.one`/`x.other`), Monatsnamen und Zeitraum-Muster aus dem Katalog.
// Deutsch bleibt byte-gleich zu den bisherigen Werten (tripHero.test.ts).
// Jeder en-Fall ruft zuerst unter `de` und schaltet dann OHNE Neuladen auf
// `en`: eine Mutation tr()/trn() -> trFor('de', …) macht ihn rot.
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/lib/utils/__tests__/tripHero_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { formatDateRange } from '../tripHero.ts';
import { locale } from '../../i18n/index.ts';
import type { Trip, Stage } from '../../types.ts';

afterEach(() => locale.set('de'));

const stage = (date: string): Stage => ({ id: `s-${date}`, name: 'E', date, waypoints: [] }) as Stage;
const trip = (o: Partial<Trip>): Trip => ({ id: 't1', name: 'T', stages: [], ...o }) as Trip;

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

// #2913 c2: die getDaysLabel-Fälle entfallen mit der Funktion (Zusatz „läuft seit Tag N“ laut Mockup weg,
// Spec feat_2913_c2_seitenkopf.md); hier bleibt der Zeitraum.

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
