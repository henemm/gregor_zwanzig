// TDD RED — Feature #1435 Etappe E1a-2, AC-9: einheitlicher Wortlaut der drei
// Aenderungs-Alarme, an JEDER Stelle der Oberflaeche gleich geschrieben.
// Spec: docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md
//       (PO-Entscheidung 2026-07-31, AC-9)
//
// Die Beschriftungen fuehrt die zentrale Tabelle `ALERT_METRIC_LABELS`.
// Die fruehere zweite Stelle, die Voreinstellungs-Auswahl
// (`alerts-tab/AlertPresetSelector.svelte`), ist mit #1895 S4 als toter Code
// entfernt; der Gleichlauf-Test mit ihr ist mit dem Pruefling entfallen.
//
// Ablage in `utils/__tests__/` statt co-located neben `alertMetricLabels.ts`:
// der edit_gate blockt in Phase phase5_tdd_red jede `.ts`-Datei ausserhalb
// eines `__tests__/`-Verzeichnisses (s. #1107/#1070).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/utils/__tests__/alert_metric_change_labels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { ALERT_METRIC_LABELS } from '../alertMetricLabels.ts';
import type { AlertMetric } from '../../types.ts';

// Die drei Aenderungs-Alarme mit ihrem neuen, einheitlichen Wortlaut
// (PO-Entscheidung 2026-07-31: Stil wie „Temperatur (Minimum)").
const AENDERUNGS_ALARME: Array<[AlertMetric, string]> = [
	['wind_change', 'Wind (Änderung)'],
	['temperature_change', 'Temperatur (Änderung)'],
	['precipitation_change', 'Niederschlag (Änderung)']
];

// Der bisherige Wortlaut — darf nach dieser Etappe nicht mehr stehen.
// („Niederschlagsänd." ist die abgekuerzte Form der frueheren
// Voreinstellungs-Auswahl.)
const ALTE_WORTLAUTE = [
	'Windänderung',
	'Temperaturänderung',
	'Niederschlagsänderung',
	'Niederschlagsänd.'
];

describe('#1435 E1a-2 AC-9: einheitlicher Wortlaut der Aenderungs-Alarme', () => {
	for (const [metric, wortlaut] of AENDERUNGS_ALARME) {
		test(`ALERT_METRIC_LABELS: ${metric} heisst „${wortlaut}"`, () => {
			assert.equal(
				ALERT_METRIC_LABELS[metric].label_de,
				wortlaut,
				'Der Wortlaut folgt nicht dem Stil „Temperatur (Minimum)" (AC-9).'
			);
		});
	}

	test('Einheit und Vergleichsrichtung bleiben unveraendert (nur der Text aendert sich)', () => {
		assert.equal(ALERT_METRIC_LABELS['wind_change'].unit, 'km/h');
		assert.equal(ALERT_METRIC_LABELS['temperature_change'].unit, '°C');
		assert.equal(ALERT_METRIC_LABELS['precipitation_change'].unit, 'mm');
		for (const [metric] of AENDERUNGS_ALARME) {
			assert.equal(ALERT_METRIC_LABELS[metric].comparison, '>');
		}
	});

	test('Die beiden Temperatur-Zeilen bleiben voneinander unterscheidbar', () => {
		const texte = [
			ALERT_METRIC_LABELS['temperature_min'].label_de,
			ALERT_METRIC_LABELS['temperature_max'].label_de,
			ALERT_METRIC_LABELS['temperature_change'].label_de
		];
		assert.equal(new Set(texte).size, 3, `Doppeltext in der Alarm-Tabelle: ${texte.join(' / ')}`);
	});
});

describe('#1435 E1a-2 AC-9: der alte Wortlaut ist verschwunden', () => {
	test('ALERT_METRIC_LABELS fuehrt keinen alten Wortlaut mehr', () => {
		const zentral = Object.values(ALERT_METRIC_LABELS).map((e) => e.label_de);
		for (const alt of ALTE_WORTLAUTE) {
			assert.equal(
				zentral.includes(alt),
				false,
				`ALERT_METRIC_LABELS fuehrt weiterhin „${alt}" (AC-9).`
			);
		}
	});
});
