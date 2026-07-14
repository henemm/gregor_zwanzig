// TDD — Issue #1256 Scheibe 7 Staging-Fund SF-2 (CRITICAL, AC-37).
//
// Spec: docs/specs/modules/issue_1256_compare_ui_rewire.md § Scheibe 7.
// Root Cause: der Hub-Aktivierungs-Karten-Pfad (CompareTabs.handleToggleActive)
// aktualisiert nur seine eigene `currentPreset`-Baseline, OHNE `invalidateAll()`
// aufzurufen (das wuerde mit der eingefrorenen-Prop-Architektur kollidieren).
// Die Header-Statuspille auf `/compare/[id]` las bislang ausschliesslich
// `data.preset` (nur vom Kebab-Pfad aktualisiert) und blieb nach einem
// Pausieren/Aktivieren aus der Karte auf dem alten Status stehen.
//
// `deriveStatusWithScheduleOverride` (subscriptionHelpers.ts) ist die reine
// Ableitungsfunktion hinter dem Fix — kein DOM/Browser, lauffaehig unter
// node --experimental-strip-types.

import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../types.ts';
import { deriveStatusWithScheduleOverride } from '../subscriptionHelpers.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-1',
		name: 'Skigebiete Tirol',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		weekday: 0,
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

describe('deriveStatusWithScheduleOverride (Staging-Fund SF-2)', () => {
	test('ohne Override: Status kommt unveraendert aus preset.schedule', () => {
		assert.strictEqual(deriveStatusWithScheduleOverride(makePreset({ schedule: 'daily' }), null), 'active');
		assert.strictEqual(deriveStatusWithScheduleOverride(makePreset({ schedule: 'manual' }), null), 'paused');
	});

	test('AC-37: Override aus der Hub-Aktivierungs-Karte (Pausieren) schlaegt preset.schedule, bis ein echter Reload ihn verwirft', () => {
		// preset.schedule ist noch "daily" (kein invalidateAll gelaufen), aber
		// der Hub hat bereits erfolgreich auf "manual" pausiert.
		const stalePreset = makePreset({ schedule: 'daily' });
		assert.strictEqual(
			deriveStatusWithScheduleOverride(stalePreset, 'manual'),
			'paused',
			'Pille muss dem Override folgen, nicht dem veralteten preset.schedule'
		);
	});

	test('AC-37: Override aus der Karte (Aktivieren) schlaegt ein noch veraltetes preset.schedule="manual"', () => {
		const stalePreset = makePreset({ schedule: 'manual' });
		assert.strictEqual(deriveStatusWithScheduleOverride(stalePreset, 'daily'), 'active');
	});

	test('draft bleibt draft, auch mit aktivierendem Override — name/location_ids haben Vorrang (deriveStatusFromPreset)', () => {
		const draftPreset = makePreset({ name: '', schedule: 'daily' });
		assert.strictEqual(deriveStatusWithScheduleOverride(draftPreset, 'daily'), 'draft');
	});

	test('Reset-Fall: Override null nach einem echten Reload liefert wieder den frischen preset.schedule-Stand', () => {
		// Simuliert den $effect in +page.svelte: nach invalidateAll() traegt
		// preset.schedule bereits den korrekten, server-autoritativen Wert,
		// scheduleOverride wurde auf null zurueckgesetzt.
		const freshPreset = makePreset({ schedule: 'manual' });
		assert.strictEqual(deriveStatusWithScheduleOverride(freshPreset, null), 'paused');
	});
});
