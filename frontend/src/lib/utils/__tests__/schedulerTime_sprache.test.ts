// Issue #2652 (i18n F3, Epic #2644) — „Nächste Prüfung" (formatNextRun) in der
// Nutzersprache: heute/morgen/Fernzeit. Deutsch bleibt wie bisher (de-AT,
// „heute um …"), Englisch `today at …` / `tomorrow at …` bzw. `Fri 6 Nov, 14:30 CET`
// (en-GB, 24 h). Erst de, dann ohne Neuladen en: eine Mutation tr() -> trFor('de', …)
// oder ein festes 'de-AT' macht den en-Fall rot.
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/lib/utils/__tests__/schedulerTime_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { formatNextRun } from '../schedulerTime.ts';
import { locale, trFor } from '../../i18n/index.ts';
import { fmtDate } from '../../i18n/format.ts';

afterEach(() => locale.set('de'));

const OPT = { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' } as const;
const tagPlus = (n: number, h: number) => {
	const d = new Date();
	d.setDate(d.getDate() + n);
	d.setHours(h, 30, 0, 0);
	return d;
};

describe('formatNextRun je Sprache', () => {
	test('morgen: de „morgen um …", en „tomorrow at …" (en-GB-Uhrzeit)', () => {
		const ziel = tagPlus(1, 14);
		locale.set('de');
		assert.equal(formatNextRun(ziel.toISOString()), `morgen um ${ziel.toLocaleString('de-AT', OPT)}`);
		locale.set('en');
		const en = formatNextRun(ziel.toISOString());
		assert.equal(en, trFor('en', 'home.zeit.morgen_um', { zeit: ziel.toLocaleString('en-GB', OPT) }));
		assert.ok(en.startsWith('tomorrow at '), en);
	});
	test('heute: en „today at …"', () => {
		const ziel = new Date();
		ziel.setHours(23, 59, 0, 0);
		if (ziel.getTime() <= Date.now()) return; // Lauf genau um 23:59 — kein heutiger Termin mehr
		locale.set('de');
		assert.ok(formatNextRun(ziel.toISOString()).startsWith('heute um '));
		locale.set('en');
		assert.ok(formatNextRun(ziel.toISOString()).startsWith('today at '));
	});
	test('Fernzeit: en `Fri 6 Nov, 14:30 CET`-Form, de unveraendert de-AT', () => {
		const ziel = tagPlus(10, 14);
		locale.set('de');
		const de = formatNextRun(ziel.toISOString());
		assert.equal(de, ziel.toLocaleString('de-AT', { day: '2-digit', month: '2-digit', ...OPT }));
		locale.set('en');
		const en = formatNextRun(ziel.toISOString());
		assert.equal(en, `${fmtDate(ziel, 'en', 'kurz')}, ${ziel.toLocaleString('en-GB', OPT)}`);
		assert.notEqual(en, de);
	});
	test('kein Termin bleibt „—" in beiden Sprachen', () => {
		locale.set('en');
		assert.equal(formatNextRun(null), '—');
		assert.equal(formatNextRun('0001-01-01T00:00:00Z'), '—');
	});
});
