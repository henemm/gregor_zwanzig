// Fix-Loop 2 der Scheibe D2 von #1301 (#1292 P4) — Staging-Befund BROKEN:
// der Amtliche-Warnungen-Toggle im Hub-Tab "Wetter-Metriken" (WeatherMetricsTab
// context='vergleich') muss fuer BESTEHENDE Vergleiche erreichbar sein und
// persistieren, weil `CompareInhaltSection` seit Epic #1273 S3 nur im
// Anlege-Wizard erreichbar ist und der Alarm-Tab-Toggle mit D2 entfaellt.
//
// Spec: docs/specs/modules/d2_1301_official_alerts_single_control.md
//   § Punkt 6, AC-6
//
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/weather-metrics-tab/__tests__/weather_metrics_official_alerts_section.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { weatherMetricsTabSections } from '../weatherMetricsTabSections.ts';

describe('AC-6: weatherMetricsTabSections — official_alerts fuer BEIDE Kontexte sichtbar', () => {
	test('vergleich enthaelt official_alerts (Erreichbarkeit fuer bestehende Vergleiche, Staging-Fund)', () => {
		const sections = weatherMetricsTabSections('vergleich');
		assert.ok(
			sections.includes('official_alerts'),
			'AC-6 FAIL: der Hub-Tab "Wetter-Metriken" zeigt im vergleich-Kontext keinen Amtliche-Warnungen-Abschnitt — ' +
				'bestehende Vergleiche haetten dann GAR KEINEN erreichbaren Schalter mehr (CompareInhaltSection ist nur ' +
				'im Anlege-Wizard erreichbar, der Alarm-Tab-Toggle entfaellt mit D2).'
		);
	});

	test('route enthaelt official_alerts (Regressionsschutz, Trip-Inhalt-Heimat bleibt erreichbar)', () => {
		const sections = weatherMetricsTabSections('route');
		assert.ok(sections.includes('official_alerts'), 'AC-6 FAIL: route verliert den Amtliche-Warnungen-Abschnitt.');
	});
});

// #3276 (F005): der Block zu `flushPendingWeatherMetricsSave` entfaellt mit der Funktion (ohne
// Produktions-Aufrufer). Den Amtliche-Warnungen-Schalter speichert der WetterTab-Speicherer.
