// TDD RED — Feature #1435 Etappe E1a-2, AC-9: einheitlicher Wortlaut der drei
// Aenderungs-Alarme, an JEDER Stelle der Oberflaeche gleich geschrieben.
// Spec: docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md
//       (PO-Entscheidung 2026-07-31, AC-9)
//
// Zwei Stellen fuehren dieselben Beschriftungen: die zentrale Tabelle
// `ALERT_METRIC_LABELS` und die Voreinstellungs-Auswahl
// (`alerts-tab/AlertPresetSelector.svelte`, POPOVER_ROWS — traegt zusaetzlich
// Schwellwerte, deshalb bleibt die Zusammenfuehrung #1435 E4 vorbehalten).
// Dieser Test sichert den Gleichlauf: er wird rot, sobald die beiden Stellen
// auseinanderlaufen — in BEIDE Richtungen.
//
// AST-Auswertung mit dem echten Svelte-Compiler statt eines Dateiinhalt-Greps;
// der Pruefling wird relativ zu DIESER Datei aufgeloest (Pfadregel #1409).
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
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

import { ALERT_METRIC_LABELS } from '../alertMetricLabels.ts';
import type { AlertMetric } from '../../types.ts';

const here = dirname(fileURLToPath(import.meta.url));
const PRESET_SELECTOR = join(
	here,
	'..',
	'..',
	'components',
	'alerts-tab',
	'AlertPresetSelector.svelte'
);

/** Die `label`-Werte der POPOVER_ROWS-Tabelle aus AlertPresetSelector.svelte. */
function presetSelectorLabels(): string[] {
	const ast: any = parse(readFileSync(PRESET_SELECTOR, 'utf-8'), { modern: true });
	const decl = (ast.instance?.content?.body ?? [])
		.filter((n: any) => n.type === 'VariableDeclaration')
		.flatMap((n: any) => n.declarations)
		.find((d: any) => d.id?.type === 'Identifier' && d.id.name === 'POPOVER_ROWS');
	assert.ok(decl, 'Keine `POPOVER_ROWS`-Tabelle in AlertPresetSelector.svelte gefunden.');

	const init = decl.init?.type === 'TSAsExpression' ? decl.init.expression : decl.init;
	assert.equal(init?.type, 'ArrayExpression', '`POPOVER_ROWS` ist kein Array-Literal mehr.');

	return init.elements.map((el: any) => {
		const prop = (el?.properties ?? []).find((p: any) => p.key?.name === 'label');
		return String(prop?.value?.value ?? '');
	});
}

// Die drei Aenderungs-Alarme mit ihrem neuen, einheitlichen Wortlaut
// (PO-Entscheidung 2026-07-31: Stil wie „Temperatur (Minimum)").
const AENDERUNGS_ALARME: Array<[AlertMetric, string]> = [
	['wind_change', 'Wind (Änderung)'],
	['temperature_change', 'Temperatur (Änderung)'],
	['precipitation_change', 'Niederschlag (Änderung)']
];

// Der bisherige Wortlaut — darf nach dieser Etappe an keiner der beiden
// Stellen mehr stehen. („Niederschlagsänd." ist die abgekuerzte Form, die
// heute nur die Voreinstellungs-Auswahl fuehrt.)
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

describe('#1435 E1a-2 AC-9: Gleichlauf mit der Voreinstellungs-Auswahl', () => {
	test('AlertPresetSelector fuehrt exakt dieselben drei Wortlaute', () => {
		const labels = presetSelectorLabels();
		assert.ok(labels.length >= 13, `POPOVER_ROWS wirkt leer/unlesbar: ${JSON.stringify(labels)}`);

		for (const [metric] of AENDERUNGS_ALARME) {
			const wortlaut = ALERT_METRIC_LABELS[metric].label_de;
			assert.ok(
				labels.includes(wortlaut),
				`Die Voreinstellungs-Auswahl kennt „${wortlaut}" (${metric}) nicht — die beiden ` +
					`Beschriftungs-Stellen laufen auseinander (AC-9). Ist: ${JSON.stringify(labels)}`
			);
		}
	});

	test('Der alte Wortlaut steht an keiner der beiden Stellen mehr', () => {
		const labels = presetSelectorLabels();
		const zentral = Object.values(ALERT_METRIC_LABELS).map((e) => e.label_de);
		for (const alt of ALTE_WORTLAUTE) {
			assert.equal(
				labels.includes(alt),
				false,
				`Die Voreinstellungs-Auswahl fuehrt weiterhin „${alt}" (AC-9).`
			);
			assert.equal(
				zentral.includes(alt),
				false,
				`ALERT_METRIC_LABELS fuehrt weiterhin „${alt}" (AC-9).`
			);
		}
	});
});
