// TDD RED — Issue #2346 S4 (AC-1 vollstaendig, AC-15).
// SPEC: docs/specs/modules/feat_2346_cockpit_paritaet.md
//
// `kachelVersand` (routes/_home/kachelVersand.ts) liest den letzten Versand fuer BEIDE kinds
// aus `NextBriefing.last_briefing` der Sammelantwort GET /api/next-briefings (relativeLastSent);
// `ComparePreset.letzter_versand` ist keine Parallelquelle mehr. Fehlt/ist null/ist kaputt => null
// (die Kachel zeigt "—"), nie ein erfundener Zeitpunkt.
//
// Pfadregel #1409: relativ zu DIESER Datei.
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/_home/__tests__/letzter_versand_aus_backend.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { kachelVersand, kachelNextBriefing } = await import(pathToFileURL(path.join(HERE, '..', 'kachelVersand.ts')).href);

const TAG = 24 * 60 * 60 * 1000;
const vor = (ms: number) => new Date(Date.now() - ms).toISOString();

const TRIP: any = { id: 'trip-1', name: 'GR20', stages: [], report_config: { enabled: true } };
const PRESET: any = { id: 'cmp-1', name: 'Nord', location_ids: ['a', 'b'], schedule: 'daily' };
const NB = { at: '2026-10-22T07:00:00+02:00', local_date: '2026-10-22', local_time: '07:00', tz: 'Europe/Paris', tz_abbr: 'CEST', slot: 'morning' };

describe('AC-15: Trip-Kachel zeigt den letzten Versand aus last_briefing', () => {
	test('Trip mit gestern versendetem Briefing: lastSent "gestern" (nicht null), nextSend aus next', () => {
		const v = kachelVersand('trip', TRIP, { ...NB, last_briefing: vor(TAG) });
		assert.equal(v.lastSent, 'gestern');
		assert.equal(v.nextSend, 'Do 07:00 (CEST)');
	});

	test('Trip mit heute versendetem Briefing: "heute"', () => {
		assert.equal(kachelVersand('trip', TRIP, { ...NB, last_briefing: vor(60 * 1000) }).lastSent, 'heute');
	});

	test('last_briefing null / fehlt / kaputt: null (Kachel zeigt "—"), nie ein erfundener Zeitpunkt', () => {
		assert.equal(kachelVersand('trip', TRIP, { ...NB, last_briefing: null }).lastSent, null);
		assert.equal(kachelVersand('trip', TRIP, NB).lastSent, null);
		assert.equal(kachelVersand('trip', TRIP, { ...NB, last_briefing: 'kein-datum' }).lastSent, null);
		assert.equal(kachelVersand('trip', TRIP, null).lastSent, null);
	});

	test('at === null bei vorhandenem last_briefing: Grund als nextSend UND letzter Versand bleibt sichtbar', () => {
		const v = kachelVersand('trip', TRIP, { at: null, reason: 'paused', last_briefing: vor(TAG) });
		assert.equal(v.nextSend, 'pausiert');
		assert.equal(v.lastSent, 'gestern');
	});
});

describe('AC-1: beide kinds beziehen den letzten Versand aus derselben Quelle', () => {
	test('Vergleich und Trip mit gleichem last_briefing liefern dasselbe lastSent', () => {
		const lb = vor(TAG);
		assert.equal(kachelVersand('vergleich', PRESET, { ...NB, last_briefing: lb }).lastSent,
			kachelVersand('trip', TRIP, { ...NB, last_briefing: lb }).lastSent);
	});

	test('Vergleich: letzter_versand am Preset wird ignoriert, wenn last_briefing fehlt (keine Parallelquelle)', () => {
		const v = kachelVersand('vergleich', { ...PRESET, letzter_versand: vor(60 * 1000) }, NB);
		assert.equal(v.lastSent, null);
	});

	test('kachelNextBriefing reicht last_briefing aus der kind-eigenen Map unveraendert durch', () => {
		const lbT = vor(TAG);
		const lbC = vor(3 * TAG);
		const nbs = {
			trips: { x: { ...NB, last_briefing: lbT } },
			compare: { x: { ...NB, last_briefing: lbC } }
		};
		assert.equal(kachelNextBriefing('trip', 'x', nbs).last_briefing, lbT);
		assert.equal(kachelNextBriefing('vergleich', 'x', nbs).last_briefing, lbC);
	});
});
