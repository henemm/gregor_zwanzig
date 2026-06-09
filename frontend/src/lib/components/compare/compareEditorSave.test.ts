// TDD RED — Issue #679 (Epic #677): Compare-Editor Slice 2 — Edit-Save-Payload
//
// Spec: docs/specs/modules/issue_679_compare_editor_edit.md  § Acceptance Criteria
//
// `compareEditorSave.ts` existiert in der RED-Phase noch NICHT → der Import
// wirft einen Modul-Resolve-Fehler und alle Tests scheitern (RED).
//
// Reine Verhaltenstests (KEIN Mock, KEINE Dateiinhalt-Prüfung): sie treiben die
// Payload-Bildung des Edit-Speicherns mit echten ComparePreset-Objekten und
// prüfen das beobachtbare Ergebnis. Das ist der Kern von AC-3:
//   1. RICHTIGER Endpoint  — `/api/compare/presets/{id}` (NICHT `/api/subscriptions`).
//   2. DATENVERLUST-SCHUTZ — nicht editierte Felder (insb. `empfaenger`, `schedule`,
//      `hour_from`/`hour_to`, `weekday`, `previous_schedule`) round-trippen unverändert,
//      nur explizit geänderte Felder werden überschrieben (Read-Modify-Write-Spread).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorSave.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import type { ComparePreset } from '../../types.ts';

// ─── Fixture: echtes, vollständiges ComparePreset (keine Mocks) ──────────────
function makePreset(): ComparePreset {
	return {
		id: 'preset-abc-123',
		name: 'Skitouren Hochkönig',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 4,
		profil: 'skitour',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['a@example.com', 'b@example.com'],
		created_at: '2026-06-01T08:00:00Z',
		display_config: { region: 'Salzburger Land', ideal_ranges: { temp: { min: -5, max: 5 } } }
	};
}

describe('buildComparePresetSavePayload — Endpoint (AC-3)', () => {
	test('zielt auf den Compare-Presets-Store, NICHT auf /api/subscriptions', () => {
		const { url } = buildComparePresetSavePayload(makePreset(), {
			name: 'Skitouren Hochkönig',
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});
		assert.equal(url, '/api/compare/presets/preset-abc-123');
		assert.ok(!url.includes('/api/subscriptions'), 'falscher Store (subscriptions)');
	});
});

describe('buildComparePresetSavePayload — Datenverlust-Schutz (AC-3)', () => {
	test('empfaenger bleibt erhalten, wenn nur der Name geändert wird', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: 'Neuer Name',
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});
		assert.deepEqual(body.empfaenger, ['a@example.com', 'b@example.com']);
		assert.equal(body.name, 'Neuer Name');
	});

	test('schedule/hour_from/hour_to/weekday/previous_schedule round-trippen unverändert', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: 'X',
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});
		assert.equal(body.schedule, 'daily');
		assert.equal(body.hour_from, 7);
		assert.equal(body.hour_to, 16);
		assert.equal(body.weekday, 4);
		assert.equal(body.previous_schedule, 'daily');
	});

	test('geänderte Felder (location_ids, profil) werden überschrieben', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: 'Skitouren Hochkönig',
			activityProfile: 'trekking',
			pickedIds: ['loc-1', 'loc-2', 'loc-9'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});
		assert.deepEqual(body.location_ids, ['loc-1', 'loc-2', 'loc-9']);
		assert.equal(body.profil, 'trekking');
	});

	test('display_config: editierte region überschreibt, fremde Schlüssel bleiben erhalten', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: 'Skitouren Hochkönig',
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Tirol',
			idealRanges: {},
			channelLayouts: null
		});
		const dc = body.display_config as Record<string, unknown>;
		assert.equal(dc.region, 'Tirol');
		// ideal_ranges aus dem Original darf NICHT verloren gehen
		assert.deepEqual(dc.ideal_ranges, { temp: { min: -5, max: 5 } });
	});

	test('id wird nie geändert (server-managed, aus Original)', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: 'Y',
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});
		assert.equal(body.id, 'preset-abc-123');
	});
});
