// TDD RED — Issue #2281 (Epic #2345 P4), AC-3 / Test 12.
// Spec: docs/specs/modules/feat_2281_vergleich_versand_historie.md
//
// Zusicherung (Wirkort Hero-Filter `plannedBriefings`): Der Briefing-Log trägt jetzt Trip- UND
// Ortsvergleich-Einträge mit `entity_type`/`entity_id` (Muster Alarm-Log #1467). Ein Compare-Eintrag
// mit derselben Kennung wie der Hero-Trip darf NIE als Trip-Briefing „gesendet" markieren; ein
// Trip-Eintrag im neuen Format (nur `entity_type:"trip"` + `entity_id`, ohne `trip_id`) MUSS zählen.
// Filter-Vorlage: `alertsForTrip` (Typ UND Kennung).
//
// Echte Funktionsaufrufe, kein Mock. `rc = undefined` => beide Slots aktiv (reportSlotAktiv).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/routes/_home/cockpitHelpers.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { plannedBriefings } from './cockpitHelpers.ts';

const HERO = 'gr20-2026';
const jetzt = () => new Date().toISOString();

// Compare-Eintrag mit DERSELBEN Kennung wie der Hero-Trip, Slot morgens, ohne trip_id.
const compareMorgen = { entity_type: 'compare', entity_id: HERO, kind: 'morning', sent_at: jetzt(), channels: ['email'] } as any;
// Trip-Eintrag im NEUEN Format (ohne trip_id), Slot abends.
const tripAbendNeu = { entity_type: 'trip', entity_id: HERO, kind: 'evening', sent_at: jetzt(), channels: ['email'] } as any;

const status = (rows: ReturnType<typeof plannedBriefings>, kind: string) => rows.find((r) => r.kind === kind)?.status;

describe('AC-3: plannedBriefings unterscheidet Trip- und Compare-Einträge', () => {
	test('Compare-Eintrag mit Hero-ID markiert den Morgen-Slot NICHT als gesendet (heute grün: Mutationswache gegen entity_id-Filter ohne Typprüfung)', () => {
		const rows = plannedBriefings(undefined, [compareMorgen, tripAbendNeu], HERO);
		assert.equal(status(rows, 'morgen'), 'planned', 'Compare-Eintrag darf nicht als Trip-Briefing zählen.');
	});

	test('Trip-Eintrag im neuen Format (entity_type="trip", entity_id, ohne trip_id) markiert den Abend-Slot als gesendet', () => {
		const rows = plannedBriefings(undefined, [compareMorgen, tripAbendNeu], HERO);
		assert.equal(status(rows, 'abend'), 'sent', 'Neu-Format-Trip-Eintrag muss zählen (RED: Filter liest nur trip_id).');
	});
});
