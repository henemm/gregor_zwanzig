// Issue #2792 S1a (AC-14): Anwenden einer Vorlage im Trip-Editor uebernimmt
// deren Profil-Ampel samt alarm_ab nach display_config.ampel; Zustellung
// (report_config) geht dabei nicht mit.
//
// SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md §2 „Eigene Vorlagen"
//
// Lauf:
//     cd frontend && npm test -- \
//       src/lib/components/shared/weather-metrics-tab/__tests__/vorlage_anwenden_uebernimmt_ampel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { ampelBeimAnwenden } from '../weatherMetricsSavePayload.ts';
import { pickEigenfelder, WETTER_DISPLAY_KEYS } from '../../pickEigenfelder.ts';

const meinGipfel = {
	id: 'p-1',
	name: 'Mein Gipfel',
	is_default: false,
	created_at: '2026-11-01T10:00:00Z',
	metrics: [{ metric_id: 'wind', enabled: true, use_friendly_format: false }],
	ampel: {
		template: 'wandern',
		metrics: { wind: { upper: { yellow: 25, orange: 50, red: 70 }, alarm_ab: 'yellow' } },
	},
};

describe('ampelBeimAnwenden', () => {
	test('eigene Vorlage: Ampel samt alarm_ab wird als Kopie uebernommen', () => {
		const ampel = ampelBeimAnwenden(meinGipfel, 'p-1');
		assert.deepEqual(ampel, meinGipfel.ampel);
		(ampel.metrics as Record<string, unknown>).wind = null;
		assert.equal(meinGipfel.ampel.metrics.wind.alarm_ab, 'yellow', 'Vorlage selbst bleibt unveraendert');
	});

	test('eigene Vorlage ohne Ampel (Bestand) wird zur Vorlage allgemein', () => {
		const alt = { ...meinGipfel, ampel: undefined };
		assert.deepEqual(ampelBeimAnwenden(alt, 'p-1'), { template: 'allgemein' });
	});

	test('eingebaute Vorlage setzt nur die Vorlagen-ID, alte Abweichungen entfallen', () => {
		assert.deepEqual(ampelBeimAnwenden(undefined, 'skitouren'), { template: 'skitouren' });
	});
});

test('Speicher-Nutzlast traegt die Ampel unter display_config, Zustellung nicht', () => {
	const ampel = ampelBeimAnwenden(meinGipfel, 'p-1');
	const body = pickEigenfelder(
		{
			display_config: { metrics: [], preset_name: 'p-1', ampel },
			report_config: { send_email: false, send_sms: true },
		},
		{ display: WETTER_DISPLAY_KEYS },
	);
	assert.deepEqual(body, { display_config: { metrics: [], preset_name: 'p-1', ampel } });
});
