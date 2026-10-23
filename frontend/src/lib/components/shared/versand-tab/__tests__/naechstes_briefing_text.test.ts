// TDD RED — Issue #1969 (Nächstes Briefing), AC-21 / AC-19 / AC-16 (Formatierungs-Teil).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md („Anzeige-Wortlaut", AC-21)
//
// Prüfling: shared/versand-tab/nextBriefingText.ts — `formatNextBriefing(nb)`.
// Der Formatierer liefert NUR den Wert („Do 07:00 (CEST)"), nie das Präfix
// „Nächstes Briefing:" — das Etikett setzt der Baustein VTNextBriefing.svelte,
// weil die Konsumenten (Startseite „Nächster · …", Status-Zeile) eigene
// Etiketten tragen.
//
// Browser-Zone ≠ Trip-Zone (AC-16, ADR-0051 Regel 2/3): Die Prozess-Zone wird
// auf America/Los_Angeles gestellt. Würde der Formatierer `at` per `new Date`
// in Browser-Zone umrechnen, käme für 2026-10-22T07:00+02:00 „Mi 22:00" heraus.
// Erwartete Strings sind HART kodiert, nie per Date berechnet.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/versand-tab/__tests__/naechstes_briefing_text.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'America/Los_Angeles';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { formatNextBriefing } = await import(pathToFileURL(path.join(HERE, '..', 'nextBriefingText.ts')).href);

// Donnerstag 22.10.2026, Sommerzeit (Umstellung erst am 25.10.).
const MORGEN_DO = {
	at: '2026-10-22T07:00:00+02:00',
	local_date: '2026-10-22',
	local_time: '07:00',
	tz: 'Europe/Paris',
	tz_abbr: 'CEST',
	slot: 'morning'
};

describe('Positivkontrolle: Prozess-Zone ist wirklich ≠ Trip-Zone', () => {
	test('05:00Z am 22.10. ist in Los Angeles noch der 21.10.', () => {
		assert.equal(new Date('2026-10-22T05:00:00Z').getDate(), 21, 'TZ-Umstellung wirkt nicht — Test wäre vakuum');
	});
});

describe('AC-16/AC-21: Normalfall aus local_date/local_time/tz_abbr, nie Browser-Zone', () => {
	test('Do 07:00 (CEST)', () => {
		assert.equal(formatNextBriefing(MORGEN_DO), 'Do 07:00 (CEST)');
	});

	test('Wochentag stammt aus local_date, nicht aus at (Auckland-Datumsgrenze)', () => {
		// Fr 23.10. 07:00 NZDT = Do 22.10. 18:00 UTC = Do 11:00 in Los Angeles.
		const nb = {
			at: '2026-10-23T07:00:00+13:00',
			local_date: '2026-10-23',
			local_time: '07:00',
			tz: 'Pacific/Auckland',
			tz_abbr: 'NZDT',
			slot: 'morning'
		};
		assert.equal(formatNextBriefing(nb), 'Fr 07:00 (NZDT)');
	});

	test('nach DST-Wechsel trägt die Zeile das Kürzel des Kandidatentags (CET)', () => {
		const nb = {
			at: '2026-10-26T07:00:00+01:00',
			local_date: '2026-10-26',
			local_time: '07:00',
			tz: 'Europe/Paris',
			tz_abbr: 'CET',
			slot: 'morning'
		};
		assert.equal(formatNextBriefing(nb), 'Mo 07:00 (CET)');
	});

	test('UTC-Rückfall wird ehrlich gezeigt (AC-10)', () => {
		const nb = {
			at: '2026-10-22T18:00:00+00:00',
			local_date: '2026-10-22',
			local_time: '18:00',
			tz: 'UTC',
			tz_abbr: 'UTC',
			slot: 'evening'
		};
		assert.equal(formatNextBriefing(nb), 'Do 18:00 (UTC)');
	});
});

describe('AC-21: skip_next', () => {
	test('„Do 18:00 (CEST) — Do 07:00 wird übersprungen"', () => {
		const nb = {
			at: '2026-10-22T18:00:00+02:00',
			local_date: '2026-10-22',
			local_time: '18:00',
			tz: 'Europe/Paris',
			tz_abbr: 'CEST',
			slot: 'evening',
			skipped: { local_date: '2026-10-22', local_time: '07:00', slot: 'morning' }
		};
		assert.equal(formatNextBriefing(nb), 'Do 18:00 (CEST) — Do 07:00 wird übersprungen');
	});
});

describe('AC-21: Gründe bei at == null', () => {
	const ohne = (extra: Record<string, unknown>) => ({ at: null, ...extra });

	test('paused mit Datum → „pausiert bis 28.10."', () => {
		assert.equal(formatNextBriefing(ohne({ reason: 'paused', paused_until: '2026-10-28' })), 'pausiert bis 28.10.');
	});
	test('paused ohne Datum → „pausiert"', () => {
		assert.equal(formatNextBriefing(ohne({ reason: 'paused' })), 'pausiert');
	});
	test('ended → „Trip beendet"', () => {
		assert.equal(formatNextBriefing(ohne({ reason: 'ended' })), 'Trip beendet');
	});
	test('manual → „nur manueller Versand"', () => {
		assert.equal(formatNextBriefing(ohne({ reason: 'manual' })), 'nur manueller Versand');
	});
	test('disabled → „Briefings abgeschaltet"', () => {
		assert.equal(formatNextBriefing(ohne({ reason: 'disabled' })), 'Briefings abgeschaltet');
	});
	test('none → keine erfundene Uhrzeit', () => {
		const out = formatNextBriefing(ohne({ reason: 'none' }));
		assert.equal(typeof out, 'string');
		assert.doesNotMatch(out, /\d{1,2}:\d{2}/);
	});
});

describe('AC-21: overdue', () => {
	test('Hinweis „läuft jetzt / wird nachgeholt"', () => {
		const out = formatNextBriefing({ ...MORGEN_DO, overdue: true });
		assert.ok(out.includes('läuft jetzt / wird nachgeholt'), `overdue-Hinweis fehlt: ${out}`);
	});
	test('ohne overdue kein Nachhol-Hinweis', () => {
		assert.ok(!formatNextBriefing(MORGEN_DO).includes('nachgeholt'));
	});
});

describe('AC-19: nicht geladen / Fehler → „—", nie eine erfundene Zeit', () => {
	test('undefined → „—"', () => {
		assert.equal(formatNextBriefing(undefined), '—');
	});
	test('null → „—"', () => {
		assert.equal(formatNextBriefing(null), '—');
	});
	test('kaputtes Objekt (at == null ohne reason) → „—", kein Absturz', () => {
		assert.equal(formatNextBriefing({ at: null } as never), '—');
	});
});
