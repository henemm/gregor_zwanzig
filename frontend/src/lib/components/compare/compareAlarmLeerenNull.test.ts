// TDD RED — Optionale Alarm-Felder im Ortsvergleich per explizitem `null` leeren.
//
// Spec: docs/specs/bugfix/optional_felder_null_leert.md (AC-2, AC-4, AC-5, AC-13)
//
// Beobachtung: Der Alarme-Reiter setzt beim Leeren Pause bzw. Ruhezeit auf
// `undefined`; `alarmSnapshotAus` (JSON-Rundreise) laesst `undefined` fallen,
// `baueAlarmNutzlast`/`buildComparePresetSavePayload` senden nur bei
// `!== undefined`. Der Key fehlt im PUT -> der Go-Merge behaelt den alten Wert.
//
// Diese Tests laufen ueber den ECHTEN Speicherweg des Reiters
// (alarmSnapshotAus -> flushPendingAlarmSave -> baueAlarmNutzlast ->
// buildComparePresetSavePayload -> waehleEigenfelder), nicht ueber eine
// Hilfsfunktion allein. Keine Mocks.
//
// Regel (festgelegt): `null` NUR bei Bestandswert im gespeicherten Preset UND
// leerem Zustand; sonst Key weglassen (Schutz vor nicht hydriertem Zustand).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/compareAlarmLeerenNull.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	alarmSnapshotAus,
	baueAlarmNutzlast,
	flushPendingAlarmSave,
	type AlarmHydrationTarget
} from '../shared/alarmeVergleichSpeicherung.ts';
import type { ComparePreset } from '../../types.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'preset-null-1',
		name: 'Skitouren Hochkoenig',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 4,
		profil: 'wintersport',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['a@example.com'],
		created_at: '2026-06-01T08:00:00Z',
		display_config: { region: 'Salzburger Land' },
		alert_cooldown_minutes: 45,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00',
		...overrides
	} as ComparePreset;
}

// Editor-Zustand wie ihn der Alarme-Reiter haelt (Feldnamen der Wizard-Seite).
function zustand(overrides: Partial<AlarmHydrationTarget> = {}): AlarmHydrationTarget {
	return {
		officialAlertsEnabled: true,
		officialWarningsEnabled: false,
		radarAlertEnabled: false,
		metricAlertLevels: {},
		alertCooldownMinutes: 45,
		alertQuietFrom: '22:00',
		alertQuietTo: '06:00',
		...overrides
	};
}

function body(preset: ComparePreset, wiz: AlarmHydrationTarget): Record<string, unknown> {
	const r = baueAlarmNutzlast(preset, alarmSnapshotAus(wiz));
	return r.body as unknown as Record<string, unknown>;
}

describe('Ortsvergleich Alarme leeren — explizites null (AC-2, AC-4)', () => {
	test('Pause geleert, Bestand 45 -> alert_cooldown_minutes === null im Payload', () => {
		const p = body(makePreset(), zustand({ alertCooldownMinutes: undefined }));
		assert.strictEqual(p.alert_cooldown_minutes, null);
	});

	test('Ruhezeit ausgeschaltet, Bestand 22:00/06:00 -> beide null im Payload', () => {
		const p = body(makePreset(), zustand({ alertQuietFrom: undefined, alertQuietTo: undefined }));
		assert.strictEqual(p.alert_quiet_from, null);
		assert.strictEqual(p.alert_quiet_to, null);
	});

	test('Ruhezeit als Leerstring geleert, Bestand 22:00/06:00 -> beide null im Payload', () => {
		const p = body(makePreset(), zustand({ alertQuietFrom: '', alertQuietTo: '' }));
		assert.strictEqual(p.alert_quiet_from, null);
		assert.strictEqual(p.alert_quiet_to, null);
	});

	test('ueber den Diff-Gate-Weg (flushPendingAlarmSave): Leeren erzeugt PUT mit null', () => {
		const preset = makePreset();
		const before = alarmSnapshotAus(zustand());
		const current = alarmSnapshotAus(zustand({ alertCooldownMinutes: undefined }));
		const r = flushPendingAlarmSave(preset, current, before);
		assert.ok(r, 'geleerte Pause muss als Aenderung erkannt werden');
		assert.strictEqual((r!.body as unknown as Record<string, unknown>).alert_cooldown_minutes, null);
	});
});

describe('Ortsvergleich Alarme — Anti-Regression Datenverlust (AC-5, AC-13)', () => {
	test('AC-5: nur Ruhezeit geaendert, Pause 45 bleibt 45 im Payload', () => {
		const p = body(makePreset(), zustand({ alertQuietFrom: '23:00', alertQuietTo: '05:00' }));
		assert.strictEqual(p.alert_cooldown_minutes, 45);
		assert.strictEqual(p.alert_quiet_from, '23:00');
	});

	test('AC-5: Pause geleert, Ruhezeit unveraendert -> Ruhezeit bleibt, nicht null', () => {
		const p = body(makePreset(), zustand({ alertCooldownMinutes: undefined }));
		assert.strictEqual(p.alert_quiet_from, '22:00');
		assert.strictEqual(p.alert_quiet_to, '06:00');
	});

	test('AC-13: Bestand ohne Pause, Zustand leer -> KEIN Key (kein stilles null)', () => {
		const preset = makePreset({ alert_cooldown_minutes: undefined });
		const p = body(preset, zustand({ alertCooldownMinutes: undefined }));
		assert.ok(!('alert_cooldown_minutes' in p), 'Key darf ohne Bestandswert nicht gesendet werden');
	});

	test('AC-13: Bestand ohne Ruhezeit, Zustand leer -> KEINE Keys', () => {
		const preset = makePreset({ alert_quiet_from: undefined, alert_quiet_to: undefined });
		const p = body(preset, zustand({ alertQuietFrom: undefined, alertQuietTo: undefined }));
		assert.ok(!('alert_quiet_from' in p));
		assert.ok(!('alert_quiet_to' in p));
	});

	test('Wert gesetzt -> Wert im Payload (Wert setzt)', () => {
		const preset = makePreset({ alert_cooldown_minutes: undefined });
		const p = body(preset, zustand({ alertCooldownMinutes: 30 }));
		assert.strictEqual(p.alert_cooldown_minutes, 30);
	});
});
