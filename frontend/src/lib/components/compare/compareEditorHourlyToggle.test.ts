// TDD — Issue #1107: Ortsvergleich D — Stundenverlauf-Sektion abschaltbar (AC-6)
//
// Spec: docs/specs/modules/issue_1107_compare_hourly_toggle.md § AC-6
//
// Reine Verhaltenstests auf der Pure-Function `buildComparePresetSavePayload`
// (KEIN Mock, KEINE Dateiinhalt-Prüfung). Muster: compareEditorForecastHours.test.ts.
//
//   1. Toggle „Stundenverlauf" aus → `edits.hourlyEnabled=false` muss als
//      `hourly_enabled: false` im PUT-Payload landen, alle anderen
//      unveränderten Original-Felder (Empfänger, Zeitfenster, display_config)
//      bleiben byte-identisch (Round-Trip-Beweis auf Client-Ebene).
//   2. `edits.hourlyEnabled` `undefined` (keine Änderung im Editor) →
//      `body.hourly_enabled` bleibt aus dem `original`-Spread erhalten (kein
//      versehentliches Überschreiben).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorHourlyToggle.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import type { ComparePreset } from '../../types.ts';

// ─── Fixture: echtes ComparePreset mit mehreren befuellten Feldern ───────────
function makePresetWithHourlySection(): ComparePreset {
	return {
		id: 'preset-1107-xyz',
		name: 'Vergleich Zillertal/Stubai/Innsbruck',
		location_ids: ['loc-1', 'loc-2', 'loc-3'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 4,
		profil: 'summer_trekking',
		hour_from: 9,
		hour_to: 16,
		empfaenger: ['a@example.com', 'b@example.com'],
		forecast_hours: 48,
		created_at: '2026-06-01T08:00:00Z',
		display_config: { region: 'Zillertal', hourly_metrics: ['temp_c', 'wind_kmh'] },
		hourly_enabled: true
	} as ComparePreset;
}

function baseEdits() {
	return {
		name: 'Vergleich Zillertal/Stubai/Innsbruck',
		activityProfile: 'summer_trekking' as const,
		pickedIds: ['loc-1', 'loc-2', 'loc-3'],
		region: 'Zillertal',
		idealRanges: {},
		channelLayouts: null
	};
}

describe('buildComparePresetSavePayload — hourly_enabled (AC-6)', () => {
	test('Toggle „Stundenverlauf" aus (false) landet als hourly_enabled im Body', () => {
		const original = makePresetWithHourlySection(); // hourly_enabled: true
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			hourlyEnabled: false
		});

		assert.equal(
			(body as ComparePreset).hourly_enabled,
			false,
			'hourly_enabled muss aus dem Edit-Wert (false) gesetzt werden, nicht aus dem Spread (true)'
		);
		// Andere, nicht angefasste Felder bleiben byte-identisch (Round-Trip-Beweis).
		assert.deepEqual(body.empfaenger, ['a@example.com', 'b@example.com']);
		assert.equal(body.hour_from, 9);
		assert.equal(body.hour_to, 16);
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).hourly_metrics,
			['temp_c', 'wind_kmh']
		);
	});

	test('Toggle „Stundenverlauf" an (true) landet als hourly_enabled im Body', () => {
		const original = { ...makePresetWithHourlySection(), hourly_enabled: false };
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			hourlyEnabled: true
		});
		assert.equal((body as ComparePreset).hourly_enabled, true);
	});
});

describe('buildComparePresetSavePayload — hourly_enabled Round-Trip (kein Überschreiben)', () => {
	test('edits.hourlyEnabled undefined -> gespeicherter Wert (true) bleibt unveraendert', () => {
		const original = makePresetWithHourlySection(); // hourly_enabled: true
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits()
			// hourlyEnabled bewusst NICHT gesetzt (Editor-Tab hat den Toggle nicht angefasst)
		});

		assert.equal(
			(body as ComparePreset).hourly_enabled,
			true,
			'Round-Trip: hourly_enabled darf ohne Editor-Aenderung nicht verloren gehen'
		);
	});

	test('edits.hourlyEnabled undefined -> gespeicherter Wert (false) bleibt unveraendert', () => {
		const original = { ...makePresetWithHourlySection(), hourly_enabled: false };
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits()
		});

		assert.equal(
			(body as ComparePreset).hourly_enabled,
			false,
			'Round-Trip: hourly_enabled=false darf ohne Editor-Aenderung nicht auf true zurueckfallen'
		);
	});
});
