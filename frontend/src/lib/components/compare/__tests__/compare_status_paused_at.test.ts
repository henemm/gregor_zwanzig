// TDD — Issue #1250 Scheibe 2 "Pause-Konvergenz" (AC-8/AC-9).
//
// Spec: docs/specs/modules/issue_1250_briefing_subscription.md, AC-7–AC-9.
//
// deriveStatusFromPreset bevorzugt seit dieser Scheibe `paused_at` vor der
// Alt-Semantik `schedule === 'manual'` (Trip-Zielsemantik). Draft-Vorrang
// bleibt oberste Regel. deriveStatusWithScheduleOverride darf bei einem
// gesetzten Override nicht an einem stalen `paused_at` einfrieren.
//
// KEIN DOM/Browser — reine Ableitungsfunktionen, lauffaehig unter
// node --experimental-strip-types.

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import { deriveStatusFromPreset, deriveStatusWithScheduleOverride } from '../subscriptionHelpers.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		profil: 'wintersport',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		forecast_hours: 48,
		created_at: '2026-01-01T00:00:00Z',
		display_config: {},
		...overrides
	};
}

describe('deriveStatusFromPreset — AC-8: Fallback ohne paused_at (Alt-Presets)', () => {
	test('schedule="manual" ohne paused_at -> paused', () => {
		assert.strictEqual(deriveStatusFromPreset(makePreset({ schedule: 'manual' })), 'paused');
	});

	test('schedule="daily" ohne paused_at -> active', () => {
		assert.strictEqual(deriveStatusFromPreset(makePreset({ schedule: 'daily' })), 'active');
	});
});

describe('deriveStatusFromPreset — AC-9: paused_at hat Vorrang vor schedule', () => {
	test('paused_at gesetzt + schedule="daily" (inkonsistent) -> paused', () => {
		const preset = makePreset({ schedule: 'daily', paused_at: '2026-07-15T10:00:00Z' });
		assert.strictEqual(deriveStatusFromPreset(preset), 'paused');
	});
});

describe('deriveStatusFromPreset — Draft-Vorrang bleibt oberste Regel', () => {
	test('kein Name + paused_at gesetzt -> draft (nicht paused)', () => {
		const preset = makePreset({ name: '', paused_at: '2026-07-15T10:00:00Z' });
		assert.strictEqual(deriveStatusFromPreset(preset), 'draft');
	});

	test('keine Orte + paused_at gesetzt -> draft (nicht paused)', () => {
		const preset = makePreset({ location_ids: [], paused_at: '2026-07-15T10:00:00Z' });
		assert.strictEqual(deriveStatusFromPreset(preset), 'draft');
	});
});

describe('deriveStatusWithScheduleOverride — Anti-Freeze bei stalem paused_at', () => {
	test('Reaktivieren-Override auf ein Preset mit stalem paused_at -> active (nicht paused)', () => {
		// preset traegt noch den alten Pausenzeitstempel (kein Reload gelaufen),
		// aber der Hub hat bereits erfolgreich auf "daily" reaktiviert.
		const stalePreset = makePreset({ schedule: 'manual', paused_at: '2026-07-01T08:00:00Z' });
		assert.strictEqual(
			deriveStatusWithScheduleOverride(stalePreset, 'daily'),
			'active',
			'Pille muss dem Reaktivieren-Override folgen, nicht dem stalen paused_at'
		);
	});

	test('Pausieren-Override -> paused, auch ohne vorhandenes paused_at', () => {
		const preset = makePreset({ schedule: 'daily' });
		assert.strictEqual(deriveStatusWithScheduleOverride(preset, 'manual'), 'paused');
	});

	test('kein Override (null) -> paused_at bleibt unveraendert massgeblich', () => {
		const preset = makePreset({ schedule: 'daily', paused_at: '2026-07-01T08:00:00Z' });
		assert.strictEqual(deriveStatusWithScheduleOverride(preset, null), 'paused');
	});
});
