// TDD RED — Issue #1232 Scheibe 2b: VersandTab (vergleich) — Zwei-Slot-Zeitplan
// + editierbare Laufzeit im Compare-Editor Save-Payload.
//
// Spec: docs/specs/modules/versand_tab_vergleich.md § Acceptance Criteria (AC-2, AC-3)
//
// Reine Verhaltenstests (KEIN Mock, KEINE Dateiinhalt-Prüfung): treiben
// `buildComparePresetSavePayload` mit echten ComparePreset-Objekten und prüfen
// das beobachtbare Ergebnis — Round-Trip der 5 Slot-Felder + den
// End-Datum-Lösch-Sentinel (`end_date: ""`).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_versand_slot_payload.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from '../compareEditorSave.ts';
import type { ComparePreset } from '../../../types.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'preset-slot-1',
		name: 'Skitouren Hochkönig',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 7,
		hour_to: 16,
		forecast_hours: 48,
		empfaenger: ['a@example.com'],
		created_at: '2026-07-01T08:00:00Z',
		display_config: { region: 'Salzburger Land' },
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: false,
		evening_time: '18:00:00',
		end_date: '2026-08-01',
		...overrides
	};
}

const baseEdits = {
	name: 'Skitouren Hochkönig',
	activityProfile: 'wandern' as const,
	pickedIds: ['loc-1', 'loc-2'],
	region: 'Salzburger Land',
	idealRanges: {},
	channelLayouts: null
};

describe('buildComparePresetSavePayload — Slot-Felder Round-Trip (AC-2)', () => {
	test('ohne Slot-Edits bleiben alle 5 Werte aus original unveraendert im Body', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, { ...baseEdits });

		assert.equal(body.morning_enabled, true);
		assert.equal(body.morning_time, '07:00:00');
		assert.equal(body.evening_enabled, false);
		assert.equal(body.evening_time, '18:00:00');
		assert.equal(body.end_date, '2026-08-01');
	});

	test('nur morningTime gesetzt: NUR morning_time wird ueberschrieben, die anderen 4 Felder kommen unveraendert aus original', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits,
			morningTime: '08:15'
		});

		assert.equal(body.morning_time, '08:15:00', 'HH:MM wird auf HH:MM:SS normalisiert');
		assert.equal(body.morning_enabled, true, 'morning_enabled round-trippt unveraendert');
		assert.equal(body.evening_enabled, false, 'evening_enabled round-trippt unveraendert');
		assert.equal(body.evening_time, '18:00:00', 'evening_time round-trippt unveraendert');
		assert.equal(body.end_date, '2026-08-01', 'end_date round-trippt unveraendert');
	});

	test('alle 5 Slot-Felder explizit geaendert werden alle uebernommen', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits,
			morningEnabled: false,
			morningTime: '06:30',
			eveningEnabled: true,
			eveningTime: '19:45',
			endDate: '2026-10-01'
		});

		assert.equal(body.morning_enabled, false);
		assert.equal(body.morning_time, '06:30:00');
		assert.equal(body.evening_enabled, true);
		assert.equal(body.evening_time, '19:45:00');
		assert.equal(body.end_date, '2026-10-01');
	});
});

describe('buildComparePresetSavePayload — End-Datum-Lösch-Sentinel (AC-3)', () => {
	test('edits.endDate = null (Preset hatte ein gesetztes end_date) → Body enthaelt end_date: ""', () => {
		const original = makePreset({ end_date: '2026-08-01' });
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits,
			endDate: null
		});

		assert.equal(body.end_date, '', 'null wird zum Loesch-Sentinel Leerstring');
	});

	test('edits.endDate = "2026-09-01" → Body enthaelt genau dieses Datum', () => {
		const original = makePreset({ end_date: undefined });
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits,
			endDate: '2026-09-01'
		});

		assert.equal(body.end_date, '2026-09-01');
	});

	test('edits.endDate = undefined (unangetastet) → end_date round-trippt aus original', () => {
		const original = makePreset({ end_date: '2026-08-01' });
		const { body } = buildComparePresetSavePayload(original, { ...baseEdits });

		assert.equal(body.end_date, '2026-08-01', 'Round-Trip: kein Sentinel ohne explizite edits.endDate');
	});
});
