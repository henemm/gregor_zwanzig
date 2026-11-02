// Issue #2654 (i18n F5, Epic #2644) — AC-2: der volle Metrik-Name kommt aus dem
// Register (GET /api/metrics: `label` = label_de, `label_en` seit P1 #2662) und
// wechselt mit der Sprache; fehlt `label_en` (Altdaten) oder ist es leer, steht der
// deutsche Name — nie ein leerer Text. Kurzform (`col_label`) und Kuerzel
// (`sms_code`) laufen NIE durch diese Funktion (ADR-0042, ADR-0104).
// Spec: docs/specs/modules/i18n_f5_wertebereiche_tab_2654.md
//
//   cd frontend && npm test -- src/lib/i18n/__tests__/metricLabel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { metricLabel, metricAlertLabel, metricAggregationLabel } from '../metricLabel.ts';

const HIER = dirname(fileURLToPath(import.meta.url));

describe('AC-2: metricLabel — Auswahl nach Sprache und Rueckfall', () => {
	const voll = { label: 'Temperatur', label_en: 'Temperature', col_label: 'Temp', sms_code: 'T' };

	test('de: label, en: label_en', () => {
		assert.equal(metricLabel(voll, 'de'), 'Temperatur');
		assert.equal(metricLabel(voll, 'en'), 'Temperature');
	});

	test('fehlendes label_en (Altdaten): en zeigt den deutschen Namen', () => {
		assert.equal(metricLabel({ label: 'Böen' }, 'en'), 'Böen');
		assert.equal(metricLabel({ label: 'Böen' }, 'de'), 'Böen');
	});

	test('leeres oder nur aus Leerraum bestehendes label_en: deutscher Name, nie ""', () => {
		assert.equal(metricLabel({ label: 'Böen', label_en: '' }, 'en'), 'Böen');
		assert.equal(metricLabel({ label: 'Böen', label_en: '   ' }, 'en'), 'Böen');
	});

	test('label_de hat Vorrang vor label (falls P1 es mitliefert), in beiden Sprachen als Rueckfall', () => {
		assert.equal(metricLabel({ label: 'alt', label_de: 'Taupunkt' }, 'de'), 'Taupunkt');
		assert.equal(metricLabel({ label: 'alt', label_de: 'Taupunkt', label_en: '' }, 'en'), 'Taupunkt');
		assert.equal(metricLabel({ label: 'alt', label_de: 'Taupunkt', label_en: 'Dew point' }, 'en'), 'Dew point');
	});

	test('Kurzform und Kuerzel bleiben unberuehrt (Eingabe byte-gleich)', () => {
		const vorher = JSON.stringify(voll);
		metricLabel(voll, 'en');
		assert.equal(JSON.stringify(voll), vorher);
		assert.notEqual(metricLabel(voll, 'en'), voll.col_label);
		assert.notEqual(metricLabel(voll, 'en'), voll.sms_code);
	});

	test('aufgezeichnetes Register: jeder Eintrag liefert in en label_en, in de label', () => {
		const register = JSON.parse(
			readFileSync(join(HIER, '..', '..', 'components', 'shared', 'weather-metrics-tab', '__tests__', 'fixtures', 'f5_register_namen.json'), 'utf-8')
		) as Record<string, { label_en: string }>;
		const katalog = JSON.parse(
			readFileSync(join(HIER, '..', '..', 'components', 'shared', 'weather-metrics-tab', '__tests__', 'fixtures', 'metric_catalog_selectable.json'), 'utf-8')
		) as Record<string, { id: string; label: string }[]>;
		let n = 0;
		for (const liste of Object.values(katalog)) {
			for (const m of liste) {
				const e = { ...m, label_en: register[m.id].label_en };
				assert.equal(metricLabel(e, 'de'), m.label, m.id);
				assert.equal(metricLabel(e, 'en'), register[m.id].label_en || m.label, m.id);
				assert.ok(metricLabel(e, 'en').trim().length > 0, m.id);
				n++;
			}
		}
		assert.ok(n >= 25, `Messaufbau: nur ${n} Register-Eintraege`);
	});
});

describe('metricAlertLabel — Alarm-Kurzform nach Sprache', () => {
	test('en: alert_label_en, sonst alert_label; de: alert_label', () => {
		assert.equal(metricAlertLabel({ label: 'Böen', alert_label: 'Böen', alert_label_en: 'Gusts' }, 'en'), 'Gusts');
		assert.equal(metricAlertLabel({ label: 'Böen', alert_label: 'Böen', alert_label_en: '' }, 'en'), 'Böen');
		assert.equal(metricAlertLabel({ label: 'Böen', alert_label: 'Böen', alert_label_en: 'Gusts' }, 'de'), 'Böen');
	});
	test('beides fehlt: leer (Aufrufer entscheidet ueber den Rueckfall)', () => {
		assert.equal(metricAlertLabel({ label: 'Böen' }, 'en'), '');
		assert.equal(metricAlertLabel({ label: 'Böen' }, 'de'), '');
	});
});

describe('metricAggregationLabel — Auswertung ueber die Kennung (Annahme A1)', () => {
	test('bekannte Kennungen je Sprache', () => {
		assert.deepEqual(['min', 'max', 'avg', 'sum'].map((a) => metricAggregationLabel(a, 'x', 'de')), ['Minimum', 'Maximum', 'Mittel', 'Summe']);
		assert.deepEqual(['min', 'max', 'avg', 'sum'].map((a) => metricAggregationLabel(a, 'x', 'en')), ['Minimum', 'Maximum', 'Average', 'Total']);
	});
	test('unbekannte oder fehlende Kennung: die mitgelieferte Beschriftung', () => {
		assert.equal(metricAggregationLabel('p90', 'P90', 'en'), 'P90');
		assert.equal(metricAggregationLabel(undefined, 'Mittel', 'en'), 'Mittel');
		assert.equal(metricAggregationLabel(undefined, undefined, 'en'), '');
	});
});
