// Regressionstest — Issue #1360 F002: ersatzloser Rückbau von
// display_config.top_n im Anlege-Pfad (POST /api/compare/presets).
//
// Belegter Ist-Zustand (vor dem Fix): ein über /compare/new angelegter
// Ortsvergleich trug weiterhin `display_config.top_n` im POST-Body — Ballast
// aus dem mit #1360 abgeschafften Layout-Reiter, den kein Render-Pfad mehr
// liest (report_config_resolver.py:192-194, compare_html.py:1094).
// scripts/migrate_1360_drop_compare_top_n.py raeumt Bestand auf, wurde aber
// von jeder Neuanlage wieder unterlaufen — genau diese Luecke deckte bisher
// KEIN Test ab (nur der Bearbeiten-Pfad war über compareEditorTopN.test.ts
// abgesichert, das mit diesem Fix ersatzlos entfaellt).
//
// Reiner Verhaltenstest (KEIN Mock, KEINE Dateiinhalt-Pruefung): treibt
// `buildNewComparePresetPayload` — die ECHTE Payload-Bau-Funktion, die
// `CompareWizardState.saveNewPreset()` fuer den POST-Body verwendet — mit
// einem vollstaendig befuellten Feld-Objekt und prueft das beobachtbare
// Ergebnis.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/compare_new_preset_payload.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildNewComparePresetPayload,
	type NewComparePresetFields
} from '../compareEditorSave.ts';

/** Vollstaendig befuelltes Feld-Objekt, wie es CompareWizardState.saveNewPreset()
 *  aus den $state-Runen des Wizards baut, wenn der Nutzer alle Content-Tabs
 *  (Wertebereiche/Metriken/Alarme) vor der Neuanlage befuellt hat. */
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
		idealRanges: { wind_max_kmh: { min: 0, max: 30 } },
		activeMetricKeys: ['wind_max_kmh', 'temp_max_c'],
		hourlyMetricKeys: ['temp_c'],
		metricAlertLevels: { wind_max_kmh: 'sensibel' },
		telegramStyle: 'rich'
	};
}

describe('buildNewComparePresetPayload — Issue #1360 F002: top_n ersatzlos entfernt', () => {
	test('die Create-Payload enthaelt KEIN display_config.top_n', () => {
		const payload = buildNewComparePresetPayload(fullFields());
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.equal(
			Object.prototype.hasOwnProperty.call(displayConfig, 'top_n'),
			false,
			`display_config.top_n darf im POST-Body nicht mehr vorkommen, ` +
				`ist aber: ${JSON.stringify(displayConfig.top_n)}`
		);
	});

	test('die uebrigen display_config-Schluessel bleiben vom Rueckbau unberuehrt', () => {
		const payload = buildNewComparePresetPayload(fullFields());
		const displayConfig = payload.display_config as Record<string, unknown>;

		assert.equal(displayConfig.region, 'Salzburger Land');
		assert.deepEqual(displayConfig.active_metrics, ['wind_max_kmh', 'temp_max_c']);
		assert.deepEqual(displayConfig.hourly_metrics, ['temp_c']);
		assert.deepEqual(displayConfig.ideal_ranges, { wind_max_kmh: { min: 0, max: 30 } });
		assert.deepEqual(displayConfig.metric_alert_levels, { wind_max_kmh: 'sensibel' });
	});
});

describe('Issue #1361/#1372 S1b: das Tagesfenster wird auch beim Anlegen mitgesendet', () => {
	test('day_window_start_hour/_end_hour stehen TOP-LEVEL im POST-Body (nicht in display_config)', () => {
		const fields = fullFields();
		fields.dayWindowStartHour = 6;
		fields.dayWindowEndHour = 20;
		const payload = buildNewComparePresetPayload(fields);

		assert.equal(
			payload.day_window_start_hour,
			6,
			'day_window_start_hour fehlt im Anlege-POST — das Tagesfenster ginge beim Anlegen eines ' +
				'Vergleichs verloren (buildNewComparePresetPayload kannte das Feld vor diesem Fix nicht)'
		);
		assert.equal(payload.day_window_end_hour, 20);
	});

	test('Default-Werte (4/19) werden ebenfalls gesendet, nicht nur abweichende Werte', () => {
		const payload = buildNewComparePresetPayload(fullFields());
		assert.equal(payload.day_window_start_hour, 4);
		assert.equal(payload.day_window_end_hour, 19);
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// TDD RED — Issue #1745 Scheibe A (AC-11): der ZWEITE, unabhängige
// Persistenzweg des Ortsvergleichs. Spec:
//   docs/specs/modules/fix_1745_a_alarm_kanal_premium_sms_ui.md (AC-11,
//   „Eigener Fund: /compare/new hat einen zweiten Persistenzpfad")
//
// `/compare/new` speichert NICHT über die Hub-Bridge (AC-9), sondern über
// `CompareWizardState.saveNewPreset()` → `buildNewComparePresetPayload()` →
// POST. Ein im Alarme-Schritt gesetzter Premium-SMS-Haken geht deshalb ohne
// eigene Verdrahtung beim Aktivieren verloren — unabhängig von Landmine 1 und
// 3, die beide nur den Hub-Pfad betreffen.
//
// RED HEUTE: `NewComparePresetFields` kennt `sendPremiumSms` nicht, der
// POST-Body trägt keinen `send_premium_sms`-Schlüssel.
// Mutation (Spec): das Feld wird der Interface hinzugefügt, aber nicht in das
// Rückgabe-Objekt von buildNewComparePresetPayload() aufgenommen.
// ─────────────────────────────────────────────────────────────────────────────
describe('#1745 AC-11: sendPremiumSms_landet_im_post_body_der_neuanlage', () => {
	test('ein im Alarme-Schritt gesetzter Haken steht als send_premium_sms:true im POST-Body', () => {
		const fields = { ...fullFields(), sendPremiumSms: true } as NewComparePresetFields;
		const payload = buildNewComparePresetPayload(fields);

		assert.equal(
			payload.send_premium_sms,
			true,
			'Der Premium-SMS-Haken geht auf dem Weg zur Neuanlage verloren — der Nutzer legt einen ' +
				'Vergleich mit sichtbarem Haken an und bekommt einen ohne. Erhalten: ' +
				`${JSON.stringify(payload.send_premium_sms)}`
		);
	});

	test('der Schlüssel wird UNBEDINGT gesendet, auch wenn der Kanal aus ist (Pflichtfeld, analog send_telegram/send_sms)', () => {
		const fields = { ...fullFields(), sendPremiumSms: false } as NewComparePresetFields;
		const payload = buildNewComparePresetPayload(fields);

		assert.equal(
			Object.prototype.hasOwnProperty.call(payload, 'send_premium_sms'),
			true,
			'send_premium_sms muss wie seine beiden Geschwister-Booleans immer im Create-Body stehen ' +
				'— ein weggelassener Schlüssel überliesse den Default dem Server.'
		);
		assert.equal(payload.send_premium_sms, false);
	});

	test('die beiden Geschwister-Kanäle bleiben unverändert (kein Kollateralschaden)', () => {
		const fields = { ...fullFields(), sendTelegram: true, sendPremiumSms: true } as NewComparePresetFields;
		const payload = buildNewComparePresetPayload(fields);
		assert.equal(payload.send_telegram, true);
		assert.equal(payload.send_sms, false);
	});
});
