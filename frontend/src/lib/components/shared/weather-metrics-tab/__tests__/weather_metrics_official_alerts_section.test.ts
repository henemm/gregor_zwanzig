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

import type { ComparePreset } from '../../../../types.ts';
import { weatherMetricsTabSections } from '../weatherMetricsTabSections.ts';
import { flushPendingWeatherMetricsSave, type WeatherMetricsSnapshot } from '../weatherMetricsCompareSave.ts';

function makePreset(overrides: Partial<ComparePreset> = {}): ComparePreset {
	return {
		id: 'cmp-42',
		name: 'Alpenorte',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		profil: 'wandern',
		hour_from: 6,
		hour_to: 9,
		empfaenger: ['urlauber@example.com'],
		created_at: '2026-01-01T00:00:00Z',
		official_alerts_enabled: true,
		display_config: { active_metrics: ['temp_max', 'wind'] },
		...overrides
	};
}

function makeSnapshot(overrides: Partial<WeatherMetricsSnapshot> = {}): WeatherMetricsSnapshot {
	return {
		activeMetricKeys: ['temp_max', 'wind'],
		officialAlertsEnabled: true,
		...overrides
	};
}

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

describe('AC-6: flushPendingWeatherMetricsSave — officialAlertsEnabled-Toggle persistiert ohne Datenverlust', () => {
	test('reiner Toggle-Wechsel (activeMetricKeys unveraendert) loest trotzdem einen PUT aus', () => {
		const preset = makePreset({ official_alerts_enabled: true });
		const before = makeSnapshot({ officialAlertsEnabled: true });
		const current = makeSnapshot({ officialAlertsEnabled: false });

		const result = flushPendingWeatherMetricsSave(preset, current, before);

		assert.ok(
			result,
			'AC-6 FAIL: ein reiner officialAlertsEnabled-Toggle (ohne Metrik-Aenderung) muss einen PUT-Payload liefern — ' +
				'sonst bleibt der Toggle unwirksam, obwohl er sichtbar geschaltet wurde.'
		);
		assert.strictEqual(result!.body.official_alerts_enabled, false);
	});

	test('identischer Snapshot (weder Metriken noch Toggle geaendert) -> kein PUT (null)', () => {
		const preset = makePreset();
		const snap = makeSnapshot();
		assert.strictEqual(
			flushPendingWeatherMetricsSave(preset, snap, makeSnapshot()),
			null,
			'unveraenderter Snapshot darf keinen PUT ausloesen (#1234-Kontext)'
		);
	});

	test('Round-Trip: activeMetricKeys UND officialAlertsEnabled landen gemeinsam im Payload, andere Preset-Felder bleiben unangetastet (RMW)', () => {
		const preset = makePreset({
			official_alerts_enabled: true,
			empfaenger: ['urlauber@example.com'],
			schedule: 'daily'
		});
		const before = makeSnapshot({ activeMetricKeys: ['temp_max'], officialAlertsEnabled: true });
		const current = makeSnapshot({ activeMetricKeys: ['temp_max', 'niederschlag'], officialAlertsEnabled: false });

		const result = flushPendingWeatherMetricsSave(preset, current, before);

		assert.ok(result);
		assert.strictEqual(result!.body.official_alerts_enabled, false);
		assert.deepStrictEqual(
			(result!.body.display_config as Record<string, unknown>).active_metrics,
			['temp_max', 'niederschlag']
		);
		assert.deepStrictEqual(
			result!.body.empfaenger,
			preset.empfaenger,
			'Read-Modify-Write: Nicht-Wetter-Metriken-Felder (z. B. Empfaenger) duerfen nicht verloren gehen'
		);
		assert.strictEqual(result!.body.schedule, preset.schedule);
	});
});
