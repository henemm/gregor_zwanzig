// TDD RED — Fix #1544/#1545, Falle 4 (Kontext-Dokument): AC-6, der
// Datenverlust-Waechter. `buildAlarmeDeliveryPayload` sendet
// `metric_alert_levels` beim Speichern als VOLLSTAENDIGEN Ersatz
// (alarmeDeliveryPayload.ts:117-121), der Go-Merge ist flach
// (internal/handler/config_merge.go:11-22). Die neue, gefilterte
// Zeilen-Ableitung (`deriveActiveAlertMetricsForTrip`, s.
// trip_active_alert_metrics_derivation.test.ts) darf deshalb NUR in
// `activeMetrics` (Zeilen-Sichtbarkeit) einfliessen, NIE in `metricLevels`
// (Speicher-Quelle) -- sonst verliert eine deaktivierte Groesse beim
// naechsten Speichern ihre zuvor gesetzte Stufe unwiderruflich.
// Spec: docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md
//   Implementation Details Punkt 4, Acceptance Criteria AC-6.
//
// Zwei Ebenen, weil eine reine Payload-Pruefung die eigentliche
// Fehlerquelle NICHT sieht (`buildAlarmeDeliveryPayload` selbst aendert sich
// in dieser Scheibe nicht -- der Fehler entstuende beim Umverdrahten von
// `AlarmeScheduleTab.svelte`):
//
//  1. Datenfluss-Nachweis: die neue Ableitung (gefiltert) UND der bestehende
//     Passthrough (ungefiltert) nebeneinander in eine Payload gefuehrt --
//     die deaktivierte Groesse bleibt im gesendeten Dict.
//  2. Verdrahtungs-Wächter (AST, Vorbild
//     shared/__tests__/alarme_tab_catalog_prop_structure.test.ts): in
//     `AlarmeScheduleTab.svelte` duerfen `activeMetrics` und `metricLevels`
//     NICHT aus derselben Quelle rechnen -- das ist der Punkt, an dem die
//     Mutations-Gegenprobe aus der Spec ("die Trennung activeMetrics/
//     metricLevels gezielt aufheben") tatsaechlich rot werden muss.
//
// RED heute: `deriveActiveAlertMetricsForTrip` fehlt (Ebene 1) UND
// `AlarmeScheduleTab.svelte` berechnet `activeMetrics` noch als
// `Object.keys(metricLevels)` -- am Register vorbei UND von `metricLevels`
// abhaengig (Ebene 2, verletzt die geforderte Trennung schon heute).
//
// #3047 Runde 7 (p11): Ebene 2 (AST-Waechter) und Ebene 3 (SSR-Kette) massen den
// Trip-Hub-Container AlarmeScheduleTab.svelte; der war toter Code (nirgends
// eingebettet) und ist entfernt, mit ihm die beiden Ebenen. Ebene 1 bleibt.
//
// Pfadregel #1409: alle Importe/Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/shared/alarme-tab/__tests__/alarme_delivery_payload_preserves_inactive_levels.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { buildAlarmeDeliveryPayload } from '../alarmeDeliveryPayload.ts';
import type { AlertMetric, MetricEntry, WeatherConfigMetric } from '../../../../types.ts';
import type { MetricCatalog } from '../../../trip-detail/metricsEditor.ts';

type DeriveTripFn = (
	metrics: WeatherConfigMetric[] | undefined,
	catalog: MetricCatalog
) => AlertMetric[];

async function loadDeriveActiveAlertMetricsForTrip(): Promise<DeriveTripFn> {
	try {
		const mod = await import('../tripAlertMetricsFromCatalog.ts');
		const fn = (mod as Record<string, unknown>).deriveActiveAlertMetricsForTrip;
		if (typeof fn !== 'function') {
			assert.fail(
				'`deriveActiveAlertMetricsForTrip` ist in ' +
					'shared/alarme-tab/tripAlertMetricsFromCatalog.ts nicht exportiert (#1544/#1545).'
			);
		}
		return fn as DeriveTripFn;
	} catch (err) {
		assert.fail(
			'Die trip-weite Ableitung fehlt noch: erwartet wird ' +
				'`shared/alarme-tab/tripAlertMetricsFromCatalog.ts` mit ' +
				`\`deriveActiveAlertMetricsForTrip(metrics, catalog)\` (#1544/#1545). Ursache: ${String(err)}`
		);
	}
}

const CATALOG: MetricCatalog = {
	temperature: [
		{
			id: 'temperature',
			label: 'Temperatur',
			unit: '°C',
			category: 'temperature',
			default_enabled: true,
			has_friendly_format: false,
			change_alert_metric: 'temperature_change',
			aggregations: [
				{ id: 'min', label: 'Minimum', alert_metric: 'temperature_min' },
				{ id: 'max', label: 'Maximum', alert_metric: 'temperature_max' },
				{ id: 'avg', label: 'Mittel', alert_metric: null }
			]
		} as unknown as MetricEntry
	],
	wind: [
		{
			id: 'gust',
			label: 'Böen',
			unit: 'km/h',
			category: 'wind',
			default_enabled: true,
			has_friendly_format: false,
			change_alert_metric: null,
			aggregations: [{ id: 'max', label: 'Maximum', alert_metric: 'wind_gust' }]
		} as unknown as MetricEntry
	]
};

describe('#1544/#1545 AC-6 Ebene 1: gesendete Payload behaelt die Stufe der deaktivierten Groesse', () => {
	test('Böen deaktiviert -> Zeile verschwindet, gespeicherter Wert bleibt im Payload', async () => {
		const derive = await loadDeriveActiveAlertMetricsForTrip();

		// Bestand: der Nutzer hatte "Böen" (wind_gust) frueher auf "sensibel"
		// gesetzt, deaktiviert die Groesse jetzt aber im Wetter-Reiter.
		const persistierteStufen: Record<string, string> = {
			wind_gust: 'sensibel',
			temperature_max: 'standard'
		};
		const metrics: WeatherConfigMetric[] = [
			{ metric_id: 'gust', enabled: false },
			{ metric_id: 'temperature', enabled: true }
		];

		const zeilen = derive(metrics, CATALOG);
		assert.ok(
			!zeilen.includes('wind_gust'),
			'Vorbedingung: die deaktivierte Groesse zeigt keine Zeile mehr.'
		);

		// `metricLevels` bleibt der UNGEFILTERTE Passthrough -- exakt das
		// heutige Verhalten von AlarmeScheduleTab.svelte:36-38
		// (`trip.display_config?.metric_alert_levels ?? {}`), das diese Etappe
		// NICHT aendern darf.
		const payload = buildAlarmeDeliveryPayload({
			officialWarningsEnabled: false,
			channels: { email: true, telegram: false, sms: false, premium_sms: false },
			metricLevels: persistierteStufen
		}) as { display_config?: { metric_alert_levels?: Record<string, string> } };

		assert.equal(
			payload.display_config?.metric_alert_levels?.wind_gust,
			'sensibel',
			'Die Stufe der deaktivierten Groesse "Böen" fehlt im gesendeten Payload ' +
				`-- Datenverlust (AC-6). Erhalten: ${JSON.stringify(payload.display_config)}`
		);
	});
});
