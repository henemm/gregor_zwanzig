// TDD RED — Issue #1104: Compare-Editor — top_n im Save-Payload (AC-2/AC-3)
//
// Spec: docs/specs/modules/issue_1104_compare_config_foundation.md § AC-2/AC-3
//
// Reine Verhaltenstests auf der Pure-Function `buildComparePresetSavePayload`
// (KEIN Mock, KEINE Dateiinhalt-Pruefung). Sie treiben die Payload-Bildung mit
// echten ComparePreset-Objekten und pruefen das beobachtbare Ergebnis:
//
//   1. GEAENDERTER topN — ein im Editor gewaehlter edits.topN (z.B. 5) landet
//      im Body als `display_config.top_n: 5`, waehrend andere
//      display_config-Felder (region, ideal_ranges) unveraendert erhalten
//      bleiben (Round-Trip-Beweis, AC-3).
//   2. UNGESETZT — ohne edits.topN bleibt `display_config.top_n` unangetastet
//      (kein neues Feld im Body), andere Felder unberuehrt.
//
// RED-Erwartung (vor Fix):
//   - `CompareEditorEdits` kennt das Feld `topN` (noch) nicht, und
//     `buildComparePresetSavePayload` setzt `display_config.top_n` im Body
//     nicht aus dem Edit-Wert. Uebergeben wir topN=5, fehlt
//     `display_config.top_n` im Body bzw. bleibt undefined → die
//     5-Assertion schlaegt fehl.
//   - Der TypeScript-Strip-Runner akzeptiert das Zusatzfeld (Strukturtypen);
//     der Verhaltenstest ist der harte RED-Beweis.
//
// Standort: `__tests__/` statt co-located (wie `compareEditorForecastHours.test.ts`),
// weil der `edit_gate`-Hook in Phase phase5_tdd_red Code-Dateien (`.ts`) nur
// unterhalb literaler Test-Verzeichnisse zulaesst (`tests/`, `__tests__/`, ...).
// `frontend/src/lib/components/compare/__tests__/` ist ein bereits etabliertes
// Verzeichnis fuer genau diesen Zweck (siehe z.B. issue_627_send_action.test.ts).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compareEditorTopN.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildComparePresetSavePayload } from '../compareEditorSave.ts';
import type { ComparePreset } from '../../../types.ts';

// ─── Fixture: echtes ComparePreset mit mehreren befuellten display_config-Feldern ───
function makePresetWithDisplayConfig(): ComparePreset {
	return {
		id: 'preset-1104-xyz',
		name: 'Skitouren Hochkönig',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 4,
		profil: 'skitour',
		hour_from: 7,
		hour_to: 16,
		empfaenger: ['a@example.com', 'b@example.com'],
		forecast_hours: 48,
		created_at: '2026-06-01T08:00:00Z',
		display_config: {
			region: 'Salzburger Land',
			ideal_ranges: { wind_max_kmh: { min: 0, max: 30 } },
			channel_layouts: {
				email: [{ metric_id: 'wind_max_kmh', enabled: true }],
				sms: [{ metric_id: 'temp_max_c', enabled: true }]
			}
		}
	} as ComparePreset;
}

function baseEdits() {
	return {
		name: 'Skitouren Hochkönig',
		activityProfile: 'skitour' as const,
		pickedIds: ['loc-1', 'loc-2'],
		region: 'Salzburger Land',
		idealRanges: { wind_max_kmh: { min: 0, max: 30 } },
		channelLayouts: null
	};
}

describe('buildComparePresetSavePayload — top_n (AC-2/AC-3)', () => {
	test('geänderter Editor-topN (5) landet als display_config.top_n im Body, andere Felder bleiben erhalten', () => {
		const original = makePresetWithDisplayConfig();
		const { body } = buildComparePresetSavePayload(original, {
			...baseEdits(),
			topN: 5
		});

		const displayConfig = body.display_config as Record<string, unknown>;
		assert.equal(
			displayConfig.top_n,
			5,
			'display_config.top_n muss aus dem Edit-Wert (5) gesetzt werden'
		);
		// Round-Trip: andere display_config-Felder bleiben unveraendert (AC-3)
		assert.equal(displayConfig.region, 'Salzburger Land');
		assert.deepEqual(displayConfig.ideal_ranges, { wind_max_kmh: { min: 0, max: 30 } });
		// AC-3 nennt channel_layouts explizit als zu erhaltendes Feld.
		assert.deepEqual(displayConfig.channel_layouts, {
			email: [{ metric_id: 'wind_max_kmh', enabled: true }],
			sms: [{ metric_id: 'temp_max_c', enabled: true }]
		});
	});

	test('ohne edits.topN bleibt display_config.top_n unangetastet, andere Felder unberührt', () => {
		const original = makePresetWithDisplayConfig();
		const { body } = buildComparePresetSavePayload(original, baseEdits());

		const displayConfig = body.display_config as Record<string, unknown>;
		assert.equal(
			displayConfig.top_n,
			undefined,
			'Ohne edits.topN darf display_config.top_n nicht gesetzt werden'
		);
		assert.equal(displayConfig.region, 'Salzburger Land');
		assert.deepEqual(displayConfig.ideal_ranges, { wind_max_kmh: { min: 0, max: 30 } });
		// AC-3 nennt channel_layouts explizit als zu erhaltendes Feld.
		assert.deepEqual(displayConfig.channel_layouts, {
			email: [{ metric_id: 'wind_max_kmh', enabled: true }],
			sms: [{ metric_id: 'temp_max_c', enabled: true }]
		});
	});
});
