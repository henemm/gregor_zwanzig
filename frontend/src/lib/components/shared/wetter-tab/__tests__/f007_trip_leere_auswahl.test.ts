// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Finding F007 (Geist von AC-39):
// Ein Trip mit `display_config.metrics: []` (Anlage per API, Altbestand) hat fuer
// Renderer und Alarm-Engine KEINE leere Auswahl: Python behandelt die leere Liste
// als Altbestand (#1394 Fall A) und zeigt den Register-Standard (#3047 N1/#3048,
// loader.py `_register_standard_metrics`). Sonst zeigt der Reiter „Keine der gewaehlten
// Metriken" und der erste Speichervorgang mit einer Plus-Metrik verengt die Mail.
//
// Umgestellt mit #3047 Runde 7 (Spec feat_3047 „Nachtrag Runde 7", Tech-Lead-Entscheidung,
// Befund E1): Der Reiter zeigt fuer „nie eingestellt" den MAIL-Standard (Register-Standard aus
// `/api/metrics`, `trip_default_rank`), nicht mehr die Vorlage; der Vorlagen-Rueckfall (AC-39)
// gilt nur noch in der Anlege-Kette (`alsVorlage`).
//
// Abgrenzung: eine Liste MIT Eintraegen, die alle `enabled: false` sind, ist eine
// echte Abwahl und bleibt leer (Python: get_metrics_for_report_type liefert dann
// die leere Menge, nicht None).
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/f007_trip_leere_auswahl.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { live } from './wetterTabDaten.ts';
import { aktiveMetriken, auswahlLesen, eigenschaftenAusKatalog, registerStandard, verschmelzen, vorlagenAusTemplates } from '../ampelModell.ts';
import { mitMetrik, standAusAbo, type AboSicht } from '../wetterZustand.ts';
import { tripNutzlast } from '../wetterTabSpeicherung.ts';

const vorlagen = () => vorlagenAusTemplates(live().templates);
const EIG = eigenschaftenAusKatalog(live().metrics);
const STANDARD = registerStandard(EIG);
const sortiert = (a: string[]) => [...a].sort();

const TRIP_LEER: AboSicht = {
	id: 'trip-f007',
	profil: 'wandern',
	report_config: {},
	display_config: { metrics: [], ampel: { template: 'wandern' } }
};

describe('F007 (#3047 E1): Trip mit metrics: [] zeigt den Mail-Standard, keine leere Auswahl', () => {
	test('Messaufbau: Register-Standard aus /api/metrics ist belegt und weicht von der Vorlage ab', () => {
		assert.ok(STANDARD.length > 0);
		assert.notDeepEqual(sortiert(STANDARD), sortiert(aktiveMetriken(vorlagen().wandern)));
	});

	test('auswahlLesen(route, {metrics: []}) = Register-Standard', () => {
		const v = vorlagen();
		const a = verschmelzen(v.wandern, { template: 'wandern' });
		assert.deepEqual(auswahlLesen('route', { metrics: [] }, a, {}, { eig: EIG }), STANDARD);
	});

	test('Oeffnen des Reiters: Auswahl = Register-Standard', () => {
		const s = standAusAbo('route', TRIP_LEER, vorlagen(), {}, { eig: EIG });
		assert.deepEqual(s.auswahl, STANDARD);
	});

	test('Anlege-Kette: ohne Liste gilt die Vorlage', () => {
		const v = vorlagen();
		const s = standAusAbo('route', TRIP_LEER, v, {}, { eig: EIG, alsVorlage: true });
		assert.deepEqual(sortiert(s.auswahl), sortiert(aktiveMetriken(v.wandern)));
	});

	test('Erstes Speichern mit einer Plus-Metrik schreibt die volle Liste, nicht nur die neue Metrik', () => {
		const v = vorlagen();
		const start = standAusAbo('route', TRIP_LEER, v, {}, { eig: EIG });
		const neu = 'dewpoint';
		assert.ok(!start.auswahl.includes(neu), `Messaufbau: ${neu} ist schon im Standard`);
		const s = mitMetrik(start, neu);
		const n = tripNutzlast({ client: null as never, stand: () => s, vorlagen: () => v, abo: () => TRIP_LEER });
		const aktiv = n.weatherConfig.metrics.filter((m) => m.enabled).map((m) => m.metric_id);
		assert.deepEqual(aktiv, [...STANDARD, neu], 'Speichern verengt die Mail');
	});

	test('Abgrenzung: eine Liste nur mit abgewaehlten Eintraegen bleibt eine leere Auswahl', () => {
		const v = vorlagen();
		const a = verschmelzen(v.wandern, null);
		assert.deepEqual(auswahlLesen('route', { metrics: [{ metric_id: 'wind', enabled: false }] }, a, {}, { eig: EIG }), []);
	});
});
