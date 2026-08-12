// Issue #1552 — TripNewEditor verwirft die Wetter-Metrik-Auswahl still.
//
// Spec: docs/specs/modules/fix_1552_neuanlage_metrikauswahl.md § Test 4
//
// Source-Inspection-Muster (kein Mount möglich, s. shared/__tests__/
// weather_metrics_tab_create_mode_callback.test.ts): beweist, dass
// `weatherMetrics` einen echten Schreibpfad aus WeatherMetricsTab bekommt
// (vorher: 0 Schreibstellen, Bug-Ursache aus der Spec) UND dass beide Mounts
// (Desktop/Mobile) ihn verdrahten — ein Duplizierungsfehler haette sonst nur
// eine Ansicht repariert.
//
// Ausführung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/trip_new_editor_weather_metrics_wiring.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';
import { buildCreateTripPayload, type CreateTripState } from '../tripNewLogic.ts';

const FILE = join(dirname(fileURLToPath(import.meta.url)), '..', 'TripNewEditor.svelte');
const code = readFileSync(FILE, 'utf-8');

describe('AC-1/AC-2/AC-3 (Test 4): handleWeatherMetricsChange schreibt weatherMetrics', () => {
	test('ein handleWeatherMetricsChange-Handler existiert und schreibt weatherMetrics', () => {
		// Fix-Loop 2: der Handler prueft jetzt zuerst auf Inhaltsgleichheit
		// (JSON.stringify) und schreibt nur bei echter Aenderung -- die
		// Zuweisung folgt deshalb nicht mehr direkt auf die oeffnende Klammer.
		assert.match(
			code,
			/function handleWeatherMetricsChange\([^)]*\)\s*\{[\s\S]*?weatherMetrics\s*=/,
			'Kein handleWeatherMetricsChange-Handler gefunden, der weatherMetrics schreibt — ' +
				'ohne ihn bleibt weatherMetrics dauerhaft [] (Bug-Ursache #1552)'
		);
	});

	test('handleWeatherMetricsChange ueberspringt inhaltsgleiche Aufrufe (Fix-Loop 2, Regressionsschutz)', () => {
		const fnMatch = code.match(/function handleWeatherMetricsChange\([^)]*\)\s*\{[\s\S]*?\n\t\}/);
		assert.ok(fnMatch, 'handleWeatherMetricsChange nicht gefunden');
		assert.match(
			fnMatch[0],
			/JSON\.stringify\(m\)\s*===\s*JSON\.stringify\(weatherMetrics\)/,
			'Kein Inhaltsgleichheits-Guard vor dem Schreiben -- zwei WeatherMetricsTab-' +
				'Mounts (Desktop+Mobile) koennten sich sonst mit unterschiedlichem Inhalt ' +
				'gegenseitig ueberschreiben (Fix-Loop-2/3-Regression, effect_update_depth_exceeded)'
		);
	});

	test('beide WeatherMetricsTab-Mounts (Desktop+Mobile) uebergeben onWeatherMetricsChange', () => {
		const mounts = code.match(/<WeatherMetricsTab\b[^>]*\/>/g) ?? [];
		assert.equal(mounts.length, 2, `Erwartet genau 2 WeatherMetricsTab-Mounts, gefunden: ${mounts.length}`);
		for (const [i, m] of mounts.entries()) {
			assert.match(
				m,
				/onWeatherMetricsChange=\{handleWeatherMetricsChange\}/,
				`Mount #${i + 1} uebergibt onWeatherMetricsChange nicht — ` +
					`nur eine Ansicht (Desktop ODER Mobile) waere repariert`
			);
			// Regression: der bestehende Kanal-Ruckkanal darf nicht verloren gehen.
			assert.match(m, /onChannelsChange=\{handleChannelsChange\}/, `Mount #${i + 1} verliert onChannelsChange`);
		}
	});
});

describe('AC-2/AC-3/AC-6 (Test 4-6, Issue #1775): handleDayWindowChange + stubTrip.report_config', () => {
	// Spec: docs/specs/modules/fix_1775_tagesfenster_anlegen.md § Test 4, Test 5, Test 6

	test('ein handleDayWindowChange-Handler existiert und mergt additiv in reportConfig', () => {
		assert.match(
			code,
			/function handleDayWindowChange\([^)]*\)\s*\{\s*reportConfig\s*=\s*\{\s*\.\.\.\(reportConfig\s*\?\?\s*\{\}\),\s*\.\.\.w\s*\};?\s*\}/,
			'Kein handleDayWindowChange-Handler gefunden, der additiv in reportConfig mergt — ' +
				'ohne ihn erreicht das Tagesfenster nie den POST-Payload (#1775)'
		);
	});

	test('beide WeatherMetricsTab-Mounts (Desktop+Mobile) uebergeben onDayWindowChange', () => {
		const mounts = code.match(/<WeatherMetricsTab\b[^>]*\/>/g) ?? [];
		assert.equal(mounts.length, 2, `Erwartet genau 2 WeatherMetricsTab-Mounts, gefunden: ${mounts.length}`);
		for (const [i, m] of mounts.entries()) {
			assert.match(
				m,
				/onDayWindowChange=\{handleDayWindowChange\}/,
				`Mount #${i + 1} uebergibt onDayWindowChange nicht`
			);
			// Regression: bestehende Rueckkanaele duerfen nicht verloren gehen.
			assert.match(m, /onChannelsChange=\{handleChannelsChange\}/, `Mount #${i + 1} verliert onChannelsChange`);
			assert.match(m, /onWeatherMetricsChange=\{handleWeatherMetricsChange\}/, `Mount #${i + 1} verliert onWeatherMetricsChange`);
		}
	});

	test('stubTrip traegt report_config (AC-6 — Viewport-Wechsel verliert sonst einen gesetzten Wert)', () => {
		// Ohne dieses Feld startet eine neu gemountete WeatherMetricsTab-Instanz
		// (Desktop<->Mobile-Remount) immer bei {} -> Default 4/19 und ueberschreibt
		// damit einen zuvor bewusst gesetzten Wert in TripNewEditor.reportConfig
		// stillschweigend (s. Spec "Implementation Details" B).
		const stubMatch = code.match(/const stubTrip = \$derived<Trip>\(\{[\s\S]*?\}\);/);
		assert.ok(stubMatch, 'stubTrip-Definition nicht gefunden');
		assert.match(
			stubMatch[0],
			/report_config:\s*reportConfig/,
			'stubTrip traegt kein report_config -- ein Viewport-Wechsel wuerde ein ' +
				'bereits gesetztes Tagesfenster beim Remount auf 4/19 zuruecksetzen (AC-6)'
		);
	});
});

describe('Test 4 (Ende-zu-Ende der Anlage): buildCreateTripPayload uebernimmt eine geaenderte Auswahl', () => {
	// Beweist die Kehrseite: SOBALD weatherMetrics tatsaechlich befuellt ist
	// (was der oben bewiesene Handler jetzt leistet), landet die geaenderte
	// Auswahl unveraendert im POST-Payload -- nicht die anfaengliche [].
	test('eine im Dialog abgewaehlte Groesse (enabled=false) bleibt im Payload erhalten', () => {
		const state: CreateTripState = {
			name: 'Testtour',
			startDate: '2026-06-15',
			stages: [{ id: 1, name: 'Etappe 1', waypoints: [] }],
			weatherMetrics: [
				{ metric_id: 'temperature', enabled: true },
				{ metric_id: 'wind', enabled: false },
			],
			channels: { email: true, telegram: true, sms: false },
		};
		const payload = buildCreateTripPayload(state);
		assert.deepEqual(payload.display_config!.metrics, [
			{ metric_id: 'temperature', enabled: true },
			{ metric_id: 'wind', enabled: false },
		]);
	});
});
