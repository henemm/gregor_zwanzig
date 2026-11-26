// Issue #3389 (Spec rework_3389_tote_exporte.md, AC-4/AC-10): Ersatztest für die lebende
// Hydration `hydrateDayWindowFromPreset`. Bisher prüfte sie kein Test direkt (nur indirekt über
// CompareTabs.svelte); mit der Löschung der toten Nachbar-Exporte bekommt sie einen eigenen
// Regressionsschutz. Gespeichertes Tagesfenster wird übernommen, fehlendes oder `null` fällt auf
// den Trip-Standard 4 bis 19 zurück (wie day_window.resolve_configured_window() im Renderer).
//
// Mutations-Gegenprobe: Standardwert 19 auf 20 ändern macht Fall 2 und 3 rot.

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import type { ComparePreset } from '../../../../types.ts';
import {
	hydrateDayWindowFromPreset,
	hydrateLayoutFieldsFromPreset,
	hydrateWeatherMetricsFromPreset
} from '../weatherMetricsCompareSave.ts';
import { registerCompareMetricCatalog, type CompareSelectionEntry } from '../compareMetricSelection.ts';

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

// #3389 Gegenprüfung F001: der gespeicherte Stundenverlauf-Schalter (aus) muss nach dem Öffnen aus bleiben.
// Mutations-Gegenprobe: `hydrateLayoutFieldsFromPreset` liefert fest `hourlyEnabled: true` ⇒ rot.
describe('#3389 AC-10: hydrateLayoutFieldsFromPreset übernimmt den gespeicherten Stundenverlauf-Schalter', () => {
	test('Preset mit hourly_enabled: false ⇒ Schalter nach dem Hydrieren aus', () => {
		assert.deepEqual(hydrateLayoutFieldsFromPreset(preset({ hourly_enabled: false })), { hourlyEnabled: false });
	});
});

// #3389 Gegenprüfung F002: ohne Katalog-Argument nimmt die Hydration den registrierten Katalog
// (die geladene Antwort von GET /api/compare/metrics) und führt Größe+Auswertung auf Auswahl-Schlüssel zurück.
// Mutations-Gegenprobe: Standard-Katalog `[]` statt `registeredCompareMetricCatalog()` ⇒ rot.
describe('#3389 AC-10: hydrateWeatherMetricsFromPreset nutzt ohne Argument den registrierten Katalog', () => {
	const KATALOG: CompareSelectionEntry[] = [
		{ metric: 'wind_max_kmh', label: 'Wind', metric_id: 'wind', aggregation: 'max' },
		{ metric: 'temp_min_c', label: 'Temperatur min', metric_id: 'temp', aggregation: 'min' }
	];
	afterEach(() => registerCompareMetricCatalog([]));

	test('gespeicherte Auswahl im Neuformat wird ohne Katalog-Argument auf Auswahl-Schlüssel zurückgeführt', () => {
		registerCompareMetricCatalog(KATALOG);
		const p = preset({
			display_config: {
				active_metrics: [
					{ metric_id: 'temp', aggregation: 'min' },
					{ metric_id: 'wind', aggregation: 'max' }
				]
			}
		});
		assert.deepEqual(hydrateWeatherMetricsFromPreset(p), ['temp_min_c', 'wind_max_kmh']);
	});
});
