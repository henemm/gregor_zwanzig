// TDD RED — Issue #764: Compare-Editor — forecast_hours im Save-Payload
//
// Spec: docs/specs/modules/issue_764_compare_forecast_hours.md § AC-1/AC-2/AC-3
//
// Reine Verhaltenstests auf der Pure-Function `buildComparePresetSavePayload`
// (KEIN Mock, KEINE Dateiinhalt-Prüfung). Sie treiben die Payload-Bildung mit
// echten ComparePreset-Objekten und prüfen das beobachtbare Ergebnis:
//
//   1. GEÄNDERTER Horizont — ein im Editor gewählter forecastHours (z.B. 72)
//      landet im Body als `forecast_hours: 72` und überschreibt den Spread.
//   2. ROUND-TRIP — ohne Horizont-Änderung kommt der gespeicherte Wert aus
//      `original` unverändert durch (kein Reset auf 48).
//
// RED-Erwartung (vor Fix):
//   - `CompareEditorEdits` kennt das Feld `forecastHours` (noch) nicht, und
//     `buildComparePresetSavePayload` setzt `forecast_hours` im Body nicht aus
//     dem Edit-Wert. Übergeben wir forecastHours=72, bleibt im Body der alte
//     Spread-Wert (48) bzw. das Feld fehlt → die 72-Assertion schlägt fehl.
//   - Der TypeScript-Strip-Runner akzeptiert das Zusatzfeld (Strukturtypen);
//     der Verhaltenstest ist der harte RED-Beweis.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/compareEditorForecastHours.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from './compareEditorSave.ts';
import type { ComparePreset } from '../../types.ts';

// ─── Fixture: echtes ComparePreset mit gespeichertem forecast_hours=72 ───────
function makePreset72(): ComparePreset {
	return {
		id: 'preset-764-xyz',
		name: 'Skitouren Hochkönig',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 4,
		profil: 'skitour',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['a@example.com', 'b@example.com'],
		forecast_hours: 72,
		created_at: '2026-06-01T08:00:00Z',
		display_config: { region: 'Salzburger Land' }
	} as ComparePreset;
}

function baseEdits() {
	return {
		name: 'Skitouren Hochkönig',
		activityProfile: 'skitour' as const,
		pickedIds: ['loc-1', 'loc-2'],
		region: 'Salzburger Land',
		idealRanges: {},
		channelLayouts: null
	};
}

describe('buildComparePresetSavePayload — forecast_hours (AC-1)', () => {
	test('geänderter Editor-Horizont (72) landet als forecast_hours im Body', () => {
		// Preset war 48; im Editor auf 72 gestellt
		const original = { ...makePreset72(), forecast_hours: 48 } as ComparePreset;
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			forecastHours: 72
		});
		assert.equal(
			(body as ComparePreset).forecast_hours,
			72,
			'forecast_hours muss aus dem Edit-Wert (72) gesetzt werden, nicht aus dem Spread (48)'
		);
	});

	test('geänderter Editor-Horizont (24) überschreibt den Spread', () => {
		const original = makePreset72(); // forecast_hours=72
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			forecastHours: 24
		});
		assert.equal((body as ComparePreset).forecast_hours, 24);
	});
});

describe('buildComparePresetSavePayload — forecast_hours Round-Trip (AC-3)', () => {
	test('ohne Horizont-Änderung kommt der gespeicherte Wert (72) unverändert durch', () => {
		const original = makePreset72(); // forecast_hours=72
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			forecastHours: 72
		});
		assert.equal(
			(body as ComparePreset).forecast_hours,
			72,
			'Round-Trip: gespeicherter 72h-Horizont darf nicht auf 48 zurückfallen'
		);
		// Andere Felder bleiben erhalten (kein Datenverlust)
		assert.deepEqual(body.empfaenger, ['a@example.com', 'b@example.com']);
		assert.equal(body.schedule, 'daily');
	});
});
