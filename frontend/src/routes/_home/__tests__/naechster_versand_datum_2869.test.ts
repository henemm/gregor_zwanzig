// TDD RED — Issue #2869 („Nächster Versand" zeigt immer das Datum), AC-8.
// SPEC: docs/specs/modules/fix_2869_naechster_versand_datum.md
//
// Jede Anzeigestelle des EINEN nächsten Termins auf der Startseite zeigt
// denselben Wert mit Wochentag + Datum + Uhrzeit + Kürzel — kein eigener
// Kurzwortlaut ohne Datum:
//   * Startseiten-Kachel Versand (`kachelVersand`, Trip UND Vergleich),
//   * Cockpit-Zeitleiste „Nächster · …" (`homeCompareTimeline`, home.timeline.naechster).
// (Hub-Kennzahl: hub_uebersicht_modell.test.ts; Status-Zeile:
//  compare_status_row_naechstes_briefing_render.test.ts.)
//
// Prozess-Zone ≠ Termin-Zone: TZ=America/Los_Angeles. Erwartete Strings HART kodiert.
//
// Pfadregel #1409: relativ zu DIESER Datei.
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/_home/__tests__/naechster_versand_datum_2869.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'America/Los_Angeles';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { kachelVersand } = await import(pathToFileURL(path.join(HERE, '..', 'kachelVersand.ts')).href);
const { homeCompareTimeline } = await import(pathToFileURL(path.join(HERE, '..', 'cockpitHelpers.ts')).href);

/** Backend-Wert GET /api/next-briefings: So 08.11.2026 06:00 Winterzeit (Innsbruck). */
const NB_08_11 = {
	at: '2026-11-08T06:00:00+01:00',
	local_date: '2026-11-08',
	local_time: '06:00',
	tz: 'Europe/Vienna',
	tz_abbr: 'CET',
	slot: 'morning'
};

const TRIP: any = { id: 'trip-2869', name: 'GR20', stages: [], report_config: { enabled: true } };
const PRESET: any = {
	id: 'cmp-2869',
	name: 'Innsbruck',
	location_ids: ['a', 'b'],
	schedule: 'daily',
	morning_enabled: true,
	morning_time: '06:00:00',
	evening_enabled: false,
	created_at: '2026-01-01T00:00:00Z'
};

describe('#2869 AC-8: Startseiten-Kachel Versand zeigt das Datum', () => {
	test('Trip-Kachel → „So 08.11. 06:00 (CET)"', () => {
		assert.equal(kachelVersand('trip', TRIP, NB_08_11).nextSend, 'So 08.11. 06:00 (CET)');
	});
	test('Vergleichs-Kachel → „So 08.11. 06:00 (CET)" (gleiches Muster wie Trip)', () => {
		assert.equal(kachelVersand('vergleich', PRESET, NB_08_11).nextSend, 'So 08.11. 06:00 (CET)');
	});
});

describe('#2869 AC-8: Cockpit-Zeitleiste „Nächster · …" zeigt das Datum', () => {
	test('daily-Vergleich → „Nächster · So 08.11. 06:00 (CET)"', () => {
		const zeile = homeCompareTimeline(PRESET, NB_08_11).find((r: { when: string }) => r.when.startsWith('Nächster · '));
		assert.ok(zeile, 'Messaufbau: Nächster-Zeile fehlt');
		assert.equal(zeile.when, 'Nächster · So 08.11. 06:00 (CET)');
	});
});
