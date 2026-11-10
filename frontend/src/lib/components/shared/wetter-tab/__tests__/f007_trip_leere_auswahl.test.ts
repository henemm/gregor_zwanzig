// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Finding F007 (Geist von AC-39):
// Ein Trip mit `display_config.metrics: []` (Anlage per API, Altbestand) hat fuer
// Renderer und Alarm-Engine KEINE leere Auswahl: Python behandelt die leere Liste
// als „kein Maximum, Standard gilt" (src/app/models.py, D4). Der Reiter muss dieselbe
// Regel lesen — Auswahl aus der aufgeloesten Ampel bzw. Vorlage — sonst zeigt er
// „Keine der gewaehlten Metriken" und der erste Speichervorgang mit einer
// Plus-Metrik verengt die Mail auf genau diese eine Metrik.
//
// Abgrenzung: eine Liste MIT Eintraegen, die alle `enabled: false` sind, ist eine
// echte Abwahl und bleibt leer (Python: get_metrics_for_report_type liefert dann
// die leere Menge, nicht None).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/f007_trip_leere_auswahl.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { live } from './wetterTabDaten.ts';
import { aktiveMetriken, auswahlLesen, verschmelzen, vorlagenAusTemplates } from '../ampelModell.ts';
import { mitMetrik, standAusAbo, type AboSicht } from '../wetterZustand.ts';
import { tripNutzlast } from '../wetterTabSpeicherung.ts';

const vorlagen = () => vorlagenAusTemplates(live().templates);
const sortiert = (a: string[]) => [...a].sort();

const TRIP_LEER: AboSicht = {
	id: 'trip-f007',
	profil: 'wandern',
	report_config: {},
	display_config: { metrics: [], ampel: { template: 'wandern' } }
};

describe('F007: Trip mit metrics: [] zeigt die Auswahl der Vorlage, keine leere Auswahl', () => {
	test('auswahlLesen(route, {metrics: []}) = aktive Metriken der aufgeloesten Ampel', () => {
		const v = vorlagen();
		const a = verschmelzen(v.wandern, { template: 'wandern' });
		const aus = auswahlLesen('route', { metrics: [] }, a);
		assert.ok(aus.length > 0, 'leere Trip-Liste wird als leere Auswahl gelesen');
		assert.deepEqual(sortiert(aus), sortiert(aktiveMetriken(a)));
	});

	test('Oeffnen des Reiters: Auswahl = Vorlage', () => {
		const v = vorlagen();
		const s = standAusAbo('route', TRIP_LEER, v);
		assert.deepEqual(sortiert(s.auswahl), sortiert(aktiveMetriken(v.wandern)));
	});

	test('Erstes Speichern mit einer Plus-Metrik schreibt die volle Liste, nicht nur die neue Metrik', () => {
		const v = vorlagen();
		const start = standAusAbo('route', TRIP_LEER, v);
		const neu = 'dewpoint';
		assert.ok(!start.auswahl.includes(neu), `Messaufbau: ${neu} ist schon in der Vorlage`);
		const s = mitMetrik(start, neu);
		const n = tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => v, abo: () => TRIP_LEER });
		const aktiv = n.weatherConfig.metrics.filter((m) => m.enabled).map((m) => m.metric_id);
		assert.deepEqual(sortiert(aktiv), sortiert([...aktiveMetriken(v.wandern), neu]), 'Speichern verengt die Mail');
	});

	test('Abgrenzung: eine Liste nur mit abgewaehlten Eintraegen bleibt eine leere Auswahl', () => {
		const v = vorlagen();
		const a = verschmelzen(v.wandern, null);
		assert.deepEqual(auswahlLesen('route', { metrics: [{ metric_id: 'wind', enabled: false }] }, a), []);
	});
});
