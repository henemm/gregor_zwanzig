// Issue #3097 Fix-Schleife 1 (Adversary F001, F002, F003) — Roh/Einfach im
// Orte-Stundenverlauf, geprueft dort, wo die Zusicherung WIRKT.
// SPEC: docs/specs/modules/feat_3097_orte_stundenverlauf_darstellung.md (AC-8)
//
//   F001: der Hub-Speicherweg des Reiters (`baueWetterMetrikenNutzlast` ->
//         `flushPendingWetterMetrikenSave`) sendet `hourly_metric_formats`;
//         die uebrigen eigenen display_config-Felder bleiben erhalten, fremde
//         Felder werden gar nicht erst gesendet (Server-Merge laesst sie stehen).
//   F002: Laden eines gespeicherten Presets hydriert die Zuordnung (Wind bleibt
//         nach dem Neuladen auf Einfach).
//   F003: der Umschalter im Stundenverlauf-Editor arbeitet Read-Modify-Write —
//         eine umgeschaltete Zeile verliert die Einstellung der anderen nicht.
//
// Issue #3276 (Spec-AC-38): `hourly_metric_formats` ist Altschluessel. F001 prueft jetzt
// das Gegenteil (der Hub-Speicherweg sendet das Feld NICHT mehr, der Bestand bleibt ueber
// den Go-Merge stehen); F003 entfaellt mit CompareHourlyLayoutControls.svelte (geloescht,
// Stundenverlauf-Formate stellt der Nutzer in „Was steht wo" ein). F002 (Lesen fuer die
// Vorlagen-Uebernahme) bleibt.
//
// Kein Mock: echte ComparePreset-Objekte durch die echten Funktionen.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/compare_hourly_metric_formats_wirkorte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	baueWetterMetrikenNutzlast,
	flushPendingWetterMetrikenSave,
	hydrateLayoutFieldsFromPreset,
	type WetterMetrikenLayoutSnapshot
} from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import type { ComparePreset } from '../../../types.ts';

function makePreset(dc: Record<string, unknown> = {}): ComparePreset {
	return {
		id: 'preset-3097-wirkorte',
		name: 'Ortsvergleich Wirkorte',
		location_ids: ['loc-a', 'loc-b'],
		schedule: 'daily',
		previous_schedule: 'daily',
		weekday: 3,
		profil: 'wandern',
		hour_from: 6,
		hour_to: 20,
		empfaenger: ['gregor-test@henemm.com'],
		forecast_hours: 72,
		created_at: '2026-08-01T08:00:00Z',
		hourly_enabled: true,
		outlook_enabled: true,
		display_config: {
			region: 'Dolomiten',
			active_metrics: [{ metric_id: 'temperature', aggregation: 'max' }],
			hourly_metrics: ['wind', 'temperature', 'precipitation'],
			outlook_metrics: ['gust'],
			outlook_metric_formats: { gust: true },
			metric_alert_levels: { wind_max_kmh: 'sensibel' },
			...dc
		}
	} as ComparePreset;
}

function snapshot(zusatz: Partial<WetterMetrikenLayoutSnapshot> = {}): WetterMetrikenLayoutSnapshot {
	return {
		activeMetricKeys: ['temp_max_c'],
		channelActiveMetricKeys: { email: null, telegram: null, sms: null },
		officialAlertsEnabled: true,
		dayWindowStartHour: 4,
		dayWindowEndHour: 19,
		hourlyMetricKeys: ['wind', 'temperature', 'precipitation'],
		hourlyEnabled: true,
		outlookMetricKeys: ['gust'],
		outlookMetricFormats: { gust: true },
		outlookEnabled: true,
		hourlyMetricFormats: null,
		...zusatz
	};
}

const dc = (body: ComparePreset) => body.display_config as Record<string, unknown>;

describe('#3097 F001 / #3276 AC-2 — Hub-Speicherweg sendet hourly_metric_formats NICHT mehr', () => {
	test('gesetztes Feld im Snapshot -> kein display_config im PUT, nur die eigenen Schalter', () => {
		const { body } = baueWetterMetrikenNutzlast(makePreset(), snapshot({ hourlyMetricFormats: { wind: true } }));
		assert.equal(dc(body), undefined, `display_config im Zustellungs-PUT: ${JSON.stringify(dc(body))}`);
		assert.deepEqual(Object.keys(body).sort(), ['hourly_enabled', 'outlook_enabled']);
	});

	test('reine Umschaltung im Stundenverlauf erzeugt keinen PUT (kein Altschluessel-Schreiben)', () => {
		const vorher = snapshot();
		const nachher = snapshot({ hourlyMetricFormats: { wind: true } });
		assert.equal(flushPendingWetterMetrikenSave(makePreset(), nachher, vorher), null);
	});
});

describe('#3097 F002 — Laden hydriert hourly_metric_formats', () => {
	test('Preset mit Wind auf Einfach -> nach dem Laden steht Wind auf Einfach', () => {
		const geladen = hydrateLayoutFieldsFromPreset(makePreset({ hourly_metric_formats: { wind: true } }), []);
		assert.deepEqual(geladen.hourlyMetricFormats, { wind: true });
	});

	test('ohne Feld -> null (nie eingestellt)', () => {
		assert.equal(hydrateLayoutFieldsFromPreset(makePreset(), []).hourlyMetricFormats, null);
	});
});
