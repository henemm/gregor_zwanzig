// TDD RED — Issue #631: Wochen-Rhythmus beim Pausieren/Reaktivieren erhalten.
//
// Spec: docs/specs/modules/issue_627_631_compare_send_rhythm.md (AC-6/AC-7)
//
// SOLL: NEUE pure Funktion computePauseToggle(preset) in subscriptionHelpers.ts,
//   die den nächsten { schedule, previous_schedule }-Zustand liefert:
//     - Pausieren  (schedule != 'manual'): merkt das aktuelle schedule in
//       previous_schedule und setzt schedule='manual'.
//     - Reaktivieren (schedule == 'manual'): stellt previous_schedule wieder her
//       (Fallback 'daily', wenn kein previous_schedule vorhanden ist).
//
// RED-Erwartung (vor Fix): computePauseToggle existiert noch nicht → ImportError
//   beim dynamischen Import / undefined-Aufruf → Test schlägt fehl.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_631_pause_rhythm.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

const helpers = (await import('../subscriptionHelpers.ts')) as {
	computePauseToggle?: (preset: {
		schedule: string;
		previous_schedule?: string;
	}) => { schedule: string; previous_schedule?: string };
};

describe('Issue #631 AC-6: Pausieren merkt sich den Wochen-Rhythmus', () => {
	test('computePauseToggle existiert (pure Helper)', () => {
		assert.equal(
			typeof helpers.computePauseToggle,
			'function',
			'computePauseToggle muss in subscriptionHelpers.ts exportiert sein (#631)'
		);
	});

	test('weekly pausieren → { schedule: "manual", previous_schedule: "weekly" }', () => {
		const fn = helpers.computePauseToggle!;
		const next = fn({ schedule: 'weekly' });
		assert.equal(next.schedule, 'manual', 'Pausieren setzt schedule=manual');
		assert.equal(
			next.previous_schedule,
			'weekly',
			'Pausieren merkt das vorige schedule (weekly) in previous_schedule'
		);
	});

	test('daily pausieren → { schedule: "manual", previous_schedule: "daily" }', () => {
		const fn = helpers.computePauseToggle!;
		const next = fn({ schedule: 'daily' });
		assert.equal(next.schedule, 'manual');
		assert.equal(next.previous_schedule, 'daily');
	});
});

describe('Issue #631 AC-7: Reaktivieren stellt den Rhythmus wieder her', () => {
	test('manual + previous_schedule=weekly → reaktivieren liefert schedule=weekly', () => {
		const fn = helpers.computePauseToggle!;
		const next = fn({ schedule: 'manual', previous_schedule: 'weekly' });
		assert.equal(
			next.schedule,
			'weekly',
			'Reaktivieren stellt den gespeicherten Wochen-Rhythmus wieder her (nicht daily)'
		);
	});

	test('manual ohne previous_schedule → reaktivieren-Fallback schedule=daily', () => {
		const fn = helpers.computePauseToggle!;
		const next = fn({ schedule: 'manual' });
		assert.equal(
			next.schedule,
			'daily',
			'Ohne previous_schedule fällt Reaktivieren auf daily zurück'
		);
	});
});
