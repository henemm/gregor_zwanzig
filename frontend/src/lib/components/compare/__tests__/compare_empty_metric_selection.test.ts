// Leerauswahl heisst leer — Issue #1366 + #1361 Befund 3, S3 Scheibe B (#1372).
// Spec: docs/specs/modules/compare_empty_metric_selection.md § AC-7/AC-8
//
// Reine Verhaltenstests (KEIN Mock, KEINE Dateiinhalt-Pruefung).
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_empty_metric_selection.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildNewComparePresetPayload,
	type NewComparePresetFields
} from '../compareEditorSave.ts';
import { applyHourlyMetricToggle } from '../compareHourlyMetricDefs.ts';

function fullFields(): NewComparePresetFields {
	return {
		name: 'Skitouren Hochkönig',
		pickedIds: ['loc-1', 'loc-2'],
		activityProfile: 'wintersport',
		schedule: 'daily_morning',
		officialAlertsEnabled: true,
		radarAlertEnabled: false,
		hourlyEnabled: true,
		officialAlertTriggersEnabled: true,
		sendTelegram: false,
		sendSms: false,
		sendPremiumSms: false,
		officialWarningsEnabled: false,
		morningEnabled: true,
		morningTime: '07:00',
		eveningEnabled: false,
		eveningTime: '18:00',
		endDate: null,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19,
		corridors: [],
		region: 'Salzburger Land',
		idealRanges: {},
		activeMetricKeys: [],
		hourlyMetricKeys: [],
		metricAlertLevels: {},
		telegramStyle: 'rich'
	};
}

describe('buildNewComparePresetPayload — AC-7: bewusste Leerauswahl beim Anlegen', () => {
	test('leere activeMetricKeys senden display_config.active_metrics ausdruecklich als []', () => {
		const payload = buildNewComparePresetPayload(fullFields());
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.equal(
			Object.prototype.hasOwnProperty.call(displayConfig, 'active_metrics'),
			true,
			'RED: display_config.active_metrics fehlt komplett bei leerer Auswahl — ' +
				'die bewusste Leerauswahl geht beim ersten Speichern verloren (kippt in "alle")'
		);
		assert.deepEqual(
			displayConfig.active_metrics,
			[],
			`Erwartet display_config.active_metrics: [], erhalten ${JSON.stringify(displayConfig.active_metrics)}`
		);
	});
});

describe('buildNewComparePresetPayload — active_metrics: "nie eingestellt" vs. bewusst leer (Issue #1366 F002)', () => {
	test('activeMetricKeys=null (Wetter-Metriken-Bereich nie geoeffnet) -> Schluessel active_metrics fehlt (Default bleibt "alle")', () => {
		const fields = fullFields();
		fields.activeMetricKeys = null;
		const payload = buildNewComparePresetPayload(fields);
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.equal(
			Object.prototype.hasOwnProperty.call(displayConfig, 'active_metrics'),
			false,
			'F002-Regression: ein nie geoeffneter Wetter-Metriken-Bereich darf beim Anlegen ' +
				'keine Leerauswahl senden — sonst zeigt die erste Vergleichs-Mail keine Wettergroesse'
		);
	});

	test('activeMetricKeys=[] (Bereich geoeffnet, bewusst alles abgewaehlt) -> active_metrics wird explizit als [] gesendet (AC-7 bleibt gueltig)', () => {
		const fields = fullFields();
		fields.activeMetricKeys = [];
		const payload = buildNewComparePresetPayload(fields);
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.deepEqual(displayConfig.active_metrics, []);
	});

	test('drei gewaehlte Groessen -> genau diese drei, in der gewaehlten Reihenfolge', () => {
		const fields = fullFields();
		fields.activeMetricKeys = ['thunder_level_max', 'temp_max_c', 'wind_max_kmh'];
		const payload = buildNewComparePresetPayload(fields);
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.deepEqual(displayConfig.active_metrics, ['thunder_level_max', 'temp_max_c', 'wind_max_kmh']);
	});
});

describe('buildNewComparePresetPayload — hourly_metrics: "nie eingestellt" vs. bewusst leer (F001-Folgefix)', () => {
	test('hourlyMetricKeys=null (nie eingestellt) -> Schluessel hourly_metrics fehlt (Default bleibt "alle")', () => {
		const fields = fullFields();
		fields.hourlyMetricKeys = null;
		const payload = buildNewComparePresetPayload(fields);
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.equal(
			Object.prototype.hasOwnProperty.call(displayConfig, 'hourly_metrics'),
			false,
			'ein nie beruehrter Stundenverlauf-Tab darf beim Anlegen keine Leerauswahl senden'
		);
	});

	test('hourlyMetricKeys=[] (bewusst leer) -> hourly_metrics wird explizit als [] gesendet', () => {
		const fields = fullFields();
		fields.hourlyMetricKeys = [];
		const payload = buildNewComparePresetPayload(fields);
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.deepEqual(displayConfig.hourly_metrics, []);
	});
});

describe('applyHourlyMetricToggle — AC-8: aus echter Leerauswahl heraus anhaken', () => {
	test('ein Klick aus leerer Auswahl ergibt genau die eine angehakte Spalte', () => {
		const result = applyHourlyMetricToggle([], 'temp_c', true);

		assert.deepEqual(
			result,
			['temp_c'],
			`RED: erwartet genau ['temp_c'], erhalten ${JSON.stringify(result)} — ` +
				'aus "nichts" wird heute die volle Vorgabemenge minus zuletzt abgewaehlter Spalte gebaut'
		);
	});
});
