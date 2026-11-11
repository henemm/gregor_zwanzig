// TDD RED — Issue #1969 (Nächstes Briefing), AC-21 / AC-19 / AC-16 (Formatierungs-Teil).
// SPEC: docs/specs/modules/feat_1969_naechstes_briefing.md („Anzeige-Wortlaut", AC-21)
//
// Prüfling: shared/versand-tab/nextBriefingText.ts — `formatNextBriefing(nb)`.
// Der Formatierer liefert NUR den Wert („Do 22.10. 07:00 (CEST)"), nie das Präfix
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
	test('Do 22.10. 07:00 (CEST) — #2869: Wochentag + Datum + Uhrzeit + Kürzel', () => {
		assert.equal(formatNextBriefing(MORGEN_DO), 'Do 22.10. 07:00 (CEST)');
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
		assert.equal(formatNextBriefing(nb), 'Fr 23.10. 07:00 (NZDT)');
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
		assert.equal(formatNextBriefing(nb), 'Mo 26.10. 07:00 (CET)');
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
		assert.equal(formatNextBriefing(nb), 'Do 22.10. 18:00 (UTC)');
	});
});

describe('AC-21: skip_next', () => {
	test('„Do 22.10. 18:00 (CEST) — Do 22.10. 07:00 wird übersprungen" (#2869: beide mit Datum)', () => {
		const nb = {
			at: '2026-10-22T18:00:00+02:00',
			local_date: '2026-10-22',
			local_time: '18:00',
			tz: 'Europe/Paris',
			tz_abbr: 'CEST',
			slot: 'evening',
			skipped: { local_date: '2026-10-22', local_time: '07:00', slot: 'morning' }
		};
		assert.equal(formatNextBriefing(nb), 'Do 22.10. 18:00 (CEST) — Do 22.10. 07:00 wird übersprungen');
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

// ---------------------------------------------------------------------------
// Issue #2869 — „Nächster Versand" zeigt immer das Datum.
// Spec: docs/specs/modules/fix_2869_naechster_versand_datum.md (AC-4 bis AC-7)
// Erwartete Strings HART kodiert; Wochentag/Datum nur aus local_date.
// ---------------------------------------------------------------------------

const { locale } = await import(pathToFileURL(path.join(HERE, '..', '..', '..', '..', 'i18n', 'index.ts')).href);
const { execFileSync } = await import('node:child_process');

/** Formatiert in Sprache `lang` und stellt danach wieder Deutsch ein. */
function inSprache(lang: 'de' | 'en', nb: unknown): string {
	locale.set(lang);
	try {
		return formatNextBriefing(nb as never);
	} finally {
		locale.set('de');
	}
}

const termin = (local_date: string, local_time: string, tz_abbr: string, extra: Record<string, unknown> = {}) => ({
	at: `${local_date}T${local_time}:00+01:00`,
	local_date,
	local_time,
	tz: 'Europe/Paris',
	tz_abbr,
	slot: 'morning',
	...extra
});

describe('#2869 AC-4: naher und ferner Termin — gleiches Muster mit Datum', () => {
	test('naher Termin (morgen, 2026-10-29) de → „Do 29.10. 07:00 (CET)"', () => {
		assert.equal(inSprache('de', termin('2026-10-29', '07:00', 'CET')), 'Do 29.10. 07:00 (CET)');
	});
	test('naher Termin en → „Thu 29 Oct 07:00 (CET)"', () => {
		assert.equal(inSprache('en', termin('2026-10-29', '07:00', 'CET')), 'Thu 29 Oct 07:00 (CET)');
	});
	test('ferner Termin (2027-08-01) de → „So 01.08. 06:00 (CEST)"', () => {
		assert.equal(inSprache('de', termin('2027-08-01', '06:00', 'CEST')), 'So 01.08. 06:00 (CEST)');
	});
	test('ferner Termin en → „Sun 1 Aug 06:00 (CEST)" (Wochentag nur einmal)', () => {
		assert.equal(inSprache('en', termin('2027-08-01', '06:00', 'CEST')), 'Sun 1 Aug 06:00 (CEST)');
	});
});

describe('#2869 AC-5: skip_next — beide Termine mit Datum', () => {
	const skip = termin('2026-10-29', '18:00', 'CET', {
		slot: 'evening',
		skipped: { local_date: '2026-10-29', local_time: '07:00', slot: 'morning' }
	});
	test('de → „Do 29.10. 18:00 (CET) — Do 29.10. 07:00 wird übersprungen"', () => {
		assert.equal(inSprache('de', skip), 'Do 29.10. 18:00 (CET) — Do 29.10. 07:00 wird übersprungen');
	});
	test('en → „Thu 29 Oct 18:00 (CET) — Thu 29 Oct 07:00 is skipped"', () => {
		assert.equal(inSprache('en', skip), 'Thu 29 Oct 18:00 (CET) — Thu 29 Oct 07:00 is skipped');
	});
});

describe('#2869 AC-6: Jahreswechsel und DST — Datum aus local_date, Browser-Zone verschiebt nichts', () => {
	const FRONTEND = path.resolve(HERE, '../../../../../..');
	const MODUL = pathToFileURL(path.join(HERE, '..', 'nextBriefingText.ts')).href;
	const I18N = pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href;
	const NB_JAHRESWECHSEL = termin('2027-01-03', '06:00', 'CET');

	/** Formatiert in einem Kindprozess mit Prozess-Zone `tz` (Zonen-Logik startet dort frisch). */
	function inZone(tz: string, lang: 'de' | 'en'): { probe: number; out: string } {
		const skript = [
			`const { formatNextBriefing } = await import(${JSON.stringify(MODUL)});`,
			`const { locale } = await import(${JSON.stringify(I18N)});`,
			`locale.set(${JSON.stringify(lang)});`,
			`const probe = new Date('2027-01-03T05:00:00Z').getDate();`,
			`process.stdout.write(JSON.stringify({ probe, out: formatNextBriefing(${JSON.stringify(NB_JAHRESWECHSEL)}) }));`
		].join('\n');
		const roh = execFileSync(
			process.execPath,
			['--import', './test-lib-loader.mjs', '--experimental-strip-types', '--no-warnings', '--input-type=module', '-e', skript],
			{ cwd: FRONTEND, env: { ...process.env, TZ: tz }, encoding: 'utf-8' }
		);
		return JSON.parse(roh);
	}

	for (const tz of ['Pacific/Auckland', 'America/Los_Angeles']) {
		test(`TZ=${tz}: de „So 03.01. 06:00 (CET)", en „Sun 3 Jan 06:00 (CET)"`, () => {
			const de = inZone(tz, 'de');
			const en = inZone(tz, 'en');
			// Positivkontrolle: 05:00Z am 03.01. ist in Auckland der 03., in Los Angeles der 02.
			assert.equal(de.probe, tz === 'Pacific/Auckland' ? 3 : 2, `TZ=${tz} wirkt im Kindprozess nicht — Test wäre vakuum`);
			assert.equal(de.out, 'So 03.01. 06:00 (CET)');
			assert.equal(en.out, 'Sun 3 Jan 06:00 (CET)');
		});
	}

	test('beide Zonen liefern identischen Text', () => {
		assert.equal(inZone('Pacific/Auckland', 'de').out, inZone('America/Los_Angeles', 'de').out);
		assert.equal(inZone('Pacific/Auckland', 'en').out, inZone('America/Los_Angeles', 'en').out);
	});

	test('DST-Wechsel: Backend liefert CET am 2026-10-26 → „Mo 26.10. 07:00 (CET)"', () => {
		assert.equal(inSprache('de', termin('2026-10-26', '07:00', 'CET')), 'Mo 26.10. 07:00 (CET)');
		assert.equal(inSprache('en', termin('2026-10-26', '07:00', 'CET')), 'Mon 26 Oct 07:00 (CET)');
	});
});

describe('#2869 AC-7: ohne local_date nie ein erfundenes Datum', () => {
	test('at gesetzt, local_date fehlt → „—" (de und en)', () => {
		const nb = { at: '2026-11-08T06:00:00+01:00', local_time: '06:00', tz_abbr: 'CET' };
		assert.equal(inSprache('de', nb), '—');
		assert.equal(inSprache('en', nb), '—');
	});
	test('local_date ungültig → „—"', () => {
		assert.equal(inSprache('de', { at: 'x', local_date: '08.11.2026', local_time: '06:00', tz_abbr: 'CET' }), '—');
	});
	test('Gründe bleiben unverändert und ohne Datum (pausiert bis 28.10. bleibt)', () => {
		assert.equal(inSprache('de', { at: null, reason: 'manual' }), 'nur manueller Versand');
		assert.equal(inSprache('de', { at: null, reason: 'paused', paused_until: '2026-10-28' }), 'pausiert bis 28.10.');
		assert.equal(inSprache('en', { at: null, reason: 'ended' }), 'Trip ended');
	});
});
