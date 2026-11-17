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
// Kein Mock: echte ComparePreset-Objekte durch die echten Funktionen; F003
// wertet das ECHTE Instanz-Skript von CompareHourlyLayoutControls.svelte aus
// (svelteInstanzPruefstand) und ruft dessen Handler auf.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/compare/__tests__/compare_hourly_metric_formats_wirkorte.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
	baueWetterMetrikenNutzlast,
	flushPendingWetterMetrikenSave,
	hydrateLayoutFieldsFromPreset,
	type WetterMetrikenLayoutSnapshot
} from '../../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import { umgebungFuer, werte, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import type { ComparePreset } from '../../../types.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const KIND = join(HIER, '..', 'CompareHourlyLayoutControls.svelte');

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

describe('#3097 F001 — Hub-Speicherweg sendet hourly_metric_formats', () => {
	test('gesetztes Feld im Snapshot -> im PUT, eigene Nachbarfelder unveraendert, fremde nicht gesendet', () => {
		const { body } = baueWetterMetrikenNutzlast(makePreset(), snapshot({ hourlyMetricFormats: { wind: true } }));
		assert.deepEqual(dc(body).hourly_metric_formats, { wind: true }, 'hourly_metric_formats fehlt im Hub-PUT');
		assert.deepEqual(dc(body).hourly_metrics, ['wind', 'temperature', 'precipitation']);
		assert.deepEqual(dc(body).outlook_metric_formats, { gust: true });
		assert.ok(!('metric_alert_levels' in dc(body)), 'fremdes Feld darf nicht mitgesendet werden');
	});

	test('reine Umschaltung im Stundenverlauf erzeugt einen PUT mit dem Feld', () => {
		const vorher = snapshot();
		const jetzt = snapshot({ hourlyMetricFormats: { wind: true } });
		const payload = flushPendingWetterMetrikenSave(makePreset(), jetzt, vorher);
		assert.ok(payload, 'Roh/Einfach-Umschaltung im Stundenverlauf wird nie gespeichert');
		assert.deepEqual(dc(payload.body).hourly_metric_formats, { wind: true });
	});

	test('nie eingestellt (null) -> gespeicherter Stand round-trippt, wird nicht verworfen', () => {
		const preset = makePreset({ hourly_metric_formats: { precipitation: true } });
		const { body } = baueWetterMetrikenNutzlast(preset, snapshot({ hourlyMetricFormats: null }));
		assert.deepEqual(dc(body).hourly_metric_formats, { precipitation: true });
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

describe('#3097 F003 — Umschalter im Stundenverlauf-Editor ist Read-Modify-Write', () => {
	async function umschalten(metricFormats: Record<string, boolean> | null, id: string, einfach: boolean) {
		const gemeldet: Record<string, boolean>[] = [];
		const { u } = await umgebungFuer(KIND, {
			metricKeys: ['wind', 'gust', 'temperature'],
			onMetricKeys: () => {},
			catalog: [],
			smsSymbols: {},
			enabled: true,
			metricFormats,
			onMetricFormats: (f: Record<string, boolean>) => gemeldet.push(f)
		} as Knoten);
		const handler = werte('onHourlyMode', u) as (id: string, v: boolean) => void;
		assert.equal(typeof handler, 'function', 'onHourlyMode laesst sich nicht herleiten');
		handler(id, einfach);
		return gemeldet;
	}

	test('Wind auf Einfach umschalten erhaelt Boeen=Einfach und Niederschlag=Roh', async () => {
		const gemeldet = await umschalten({ gust: true, precipitation: false }, 'wind', true);
		assert.deepEqual(gemeldet, [{ gust: true, precipitation: false, wind: true }]);
	});

	test('Zuruecksetzen auf Roh schreibt false und erhaelt die uebrigen Eintraege', async () => {
		const gemeldet = await umschalten({ gust: true, wind: true }, 'wind', false);
		assert.deepEqual(gemeldet, [{ gust: true, wind: false }]);
	});

	test('ohne gespeicherte Zuordnung (null) entsteht genau der eine Eintrag', async () => {
		const gemeldet = await umschalten(null, 'gust', true);
		assert.deepEqual(gemeldet, [{ gust: true }]);
	});
});
