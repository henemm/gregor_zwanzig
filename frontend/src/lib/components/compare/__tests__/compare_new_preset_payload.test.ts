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
