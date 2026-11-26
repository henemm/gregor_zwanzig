// Issue #3389 (Spec rework_3389_tote_exporte.md, AC-4/AC-10): Ersatztest für die lebende
// Hydration `hydrateDayWindowFromPreset`. Bisher prüfte sie kein Test direkt (nur indirekt über
// CompareTabs.svelte); mit der Löschung der toten Nachbar-Exporte bekommt sie einen eigenen
// Regressionsschutz. Gespeichertes Tagesfenster wird übernommen, fehlendes oder `null` fällt auf
// den Trip-Standard 4 bis 19 zurück (wie day_window.resolve_configured_window() im Renderer).
//
// Mutations-Gegenprobe: Standardwert 19 auf 20 ändern macht Fall 2 und 3 rot.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../../types.ts';
import { hydrateDayWindowFromPreset } from '../weatherMetricsCompareSave.ts';

function preset(extra: Record<string, unknown>): ComparePreset {
	return {
		id: 'cmp-tagesfenster',
		name: 'Tagesfenster-Vergleich',
		location_ids: ['ort-a', 'ort-b'],
		...extra
	} as unknown as ComparePreset;
}

describe('#3389 AC-4: hydrateDayWindowFromPreset liest das gespeicherte Tagesfenster', () => {
	test('gespeichertes Tagesfenster 6 bis 21 wird übernommen', () => {
		assert.deepEqual(hydrateDayWindowFromPreset(preset({ day_window_start_hour: 6, day_window_end_hour: 21 })), {
			dayWindowStartHour: 6,
			dayWindowEndHour: 21
		});
	});

	test('Altbestand ohne Tagesfenster-Felder liefert den Trip-Standard 4 bis 19', () => {
		assert.deepEqual(hydrateDayWindowFromPreset(preset({})), { dayWindowStartHour: 4, dayWindowEndHour: 19 });
	});

	test('Tagesfenster-Felder mit null liefern den Trip-Standard 4 bis 19', () => {
		assert.deepEqual(hydrateDayWindowFromPreset(preset({ day_window_start_hour: null, day_window_end_hour: null })), {
			dayWindowStartHour: 4,
			dayWindowEndHour: 19
		});
	});
});
