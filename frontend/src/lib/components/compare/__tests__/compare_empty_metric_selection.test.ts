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

// Issue #3276 (Spec-AC-38, AC-1): `hourly_metrics` ist Altschluessel. Vorher unterschied die
// Neuanlage „nie eingestellt" (Schluessel fehlt) von „bewusst leer" ([] gesendet). Jetzt sendet
// der POST den Schluessel in KEINEM Fall — auch nicht als [] (Spec: nie leer senden).
describe('buildNewComparePresetPayload — hourly_metrics wird nie gesendet (#3276)', () => {
	for (const wert of [null, [], ['temp_c']]) {
		test(`hourlyMetricKeys=${JSON.stringify(wert)} -> Schluessel hourly_metrics fehlt`, () => {
			const fields = { ...fullFields(), hourlyMetricKeys: wert } as ReturnType<typeof fullFields>;
			const displayConfig = buildNewComparePresetPayload(fields).display_config as Record<string, unknown>;
			assert.equal(Object.prototype.hasOwnProperty.call(displayConfig, 'hourly_metrics'), false);
		});
	}
});

// Issue #3301: der Block „applyHourlyMetricToggle — AC-8" ist mit compareHourlyMetricDefs.ts
// entfallen (kein Produktionscode nutzte die Umschalt-Hilfe mehr).
