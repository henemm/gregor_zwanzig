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
import type { ComparePreset, Corridor } from '../../types.ts';

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

// ─── Issue #1170 (Epic #1095 Scheibe 3/3): Alarm-Konfiguration im Save-Payload ──
describe('buildComparePresetSavePayload — Alarm-Konfiguration (Issue #1170)', () => {
	test('gesetzte Alarm-Felder landen im Payload (display_config.metric_alert_levels + top-level cooldown/quiet), Rest round-trippt', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null,
			metricAlertLevels: { wind_gust: 'sensibel', temperature_min: 'standard' },
			alertCooldownMinutes: 90,
			alertQuietFrom: '22:00',
			alertQuietTo: '07:00'
		});

		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(dc.metric_alert_levels, { wind_gust: 'sensibel', temperature_min: 'standard' });
		assert.equal(body.alert_cooldown_minutes, 90);
		assert.equal(body.alert_quiet_from, '22:00');
		assert.equal(body.alert_quiet_to, '07:00');

		// Datenverlust-Schutz: nicht editierte Felder bleiben unveraendert.
		assert.deepEqual(body.empfaenger, ['a@example.com', 'b@example.com']);
		assert.equal(body.schedule, 'daily');
	});

	test('fehlende Alarm-Felder in edits lassen bereits gesetzte Werte aus original unangetastet (Round-Trip)', () => {
		const original: ComparePreset = {
			...makePreset(),
			alert_cooldown_minutes: 60,
			alert_quiet_from: '21:00',
			alert_quiet_to: '06:00',
			display_config: {
				region: 'Salzburger Land',
				metric_alert_levels: { wind_gust: 'entspannt' }
			}
		};
		const { body } = buildComparePresetSavePayload(original, {
			name: 'Nur der Name ändert sich',
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});

		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(dc.metric_alert_levels, { wind_gust: 'entspannt' });
		assert.equal(body.alert_cooldown_minutes, 60);
		assert.equal(body.alert_quiet_from, '21:00');
		assert.equal(body.alert_quiet_to, '06:00');
	});
});

// ─── Issue #1216 Slice 2b: Amtliche-Warnungen-Alarm-Trigger + Kanal-Felder ──
describe('buildComparePresetSavePayload — Alarm-Trigger + Kanäle (#1216)', () => {
	test('gesetzte Trigger-/Kanal-Felder landen als JSON-Keys im PUT-Body', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null,
			officialAlertTriggersEnabled: false,
			sendTelegram: true,
			sendSms: true
		});

		assert.equal(body.official_alert_triggers_enabled, false);
		assert.equal(body.send_telegram, true);
		assert.equal(body.send_sms, true);

		// Datenverlust-Schutz: nicht editierte Felder round-trippen.
		assert.deepEqual(body.empfaenger, ['a@example.com', 'b@example.com']);
	});

	test('fehlende Trigger-/Kanal-Felder in edits ändern den Round-Trip nicht (Keys fehlen)', () => {
		const original = makePreset();
		const { body } = buildComparePresetSavePayload(original, {
			name: 'Nur Name',
			activityProfile: 'skitour',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});

		assert.ok(
			!Object.prototype.hasOwnProperty.call(body, 'official_alert_triggers_enabled'),
			'official_alert_triggers_enabled darf ohne edits nicht im Body erscheinen'
		);
		assert.ok(
			!Object.prototype.hasOwnProperty.call(body, 'send_telegram'),
			'send_telegram darf ohne edits nicht im Body erscheinen'
		);
		assert.ok(
			!Object.prototype.hasOwnProperty.call(body, 'send_sms'),
			'send_sms darf ohne edits nicht im Body erscheinen'
		);
	});
});

// ─── Issue #1231 Slice 4: corridors — TOP-LEVEL Feld (nicht in display_config,
// analog Go-Model ComparePreset.Corridors `json:"corridors"`) ──
describe('buildComparePresetSavePayload — corridors (#1231 Slice 4)', () => {
	test('gesetztes corridors-Array landet als Top-Level-Feld im PUT-Body', () => {
		const original = makePreset();
		const edits: Corridor[] = [
			{ metric: 'temp_max_c', range: [null, 30], notify: false, mark: true },
		];
		const { body } = buildComparePresetSavePayload(original, {
			name: original.name,
			activityProfile: 'wandern',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null,
			corridors: edits
		});
		assert.deepEqual(body.corridors, edits);
		// Nicht in display_config verschachtelt (Go-Model erwartet Top-Level).
		const dc = body.display_config as Record<string, unknown>;
		assert.equal('corridors' in dc, false);
	});

	test('fehlendes corridors in edits laesst den Key im Body komplett weg (Round-Trip via Original)', () => {
		const original: ComparePreset = {
			...makePreset(),
			corridors: [{ metric: 'wind_max_kmh', range: [0, 50], notify: true, mark: false }]
		};
		const { body } = buildComparePresetSavePayload(original, {
			name: 'Nur Name',
			activityProfile: 'wandern',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Salzburger Land',
			idealRanges: {},
			channelLayouts: null
		});
		// Round-Trip-Spread (`...original`) traegt original.corridors weiter —
		// kein expliziter edits-Key noetig, da der Spread es bereits enthaelt.
		assert.deepEqual(body.corridors, original.corridors);
	});
});
