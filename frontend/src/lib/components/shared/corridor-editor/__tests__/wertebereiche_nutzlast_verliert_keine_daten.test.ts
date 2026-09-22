// TDD RED — Issue #2276 Scheibe S3 (Epic #2345), AC-11: das Speichern der
// Wertebereiche verliert keine anderen Einstellungen des Ortsvergleichs (Orte,
// Versand, Kanäle, Alarm-Schwellen, Anzeige). Nur die Korridor-Felder
// (corridors, display_config.ideal_ranges/active_metrics/metric_alert_levels)
// dürfen vom Ausgangsstand abweichen.
//
// Spec: docs/specs/modules/rework_2276_s3_wertebereiche.md — AC-11, Design Punkt 2
// (Voll-Spread über buildComparePresetSavePayload; der Go-Merge-Kernel mergt
// display_config nur auf Ebene 1, ein Teil-PUT wäre ein Verlustpfad).
//
// Zielschnittstelle (existiert noch NICHT → RED):
//   shared/corridor-editor/wertebereicheVergleichSpeicherung.ts
//     corridorSnapshotAus(zustand): CorridorSnapshot
//     baueWertebereichNutzlast(preset, current: CorridorSnapshot): { url, body }
//   (Spec „Affected Files" schreibt `baueWertebereichNutzlast`; der AC-11-Text
//    nennt `baueWertebereicheNutzlast` — dieser Test legt den Namen aus
//    „Affected Files" fest.)
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/wertebereiche_nutzlast_verliert_keine_daten.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createFakeTripServer, type FakeTripServer } from '../../../../__tests__/fakeTripServer.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubWizardBridge.ts';
import {
	baueWertebereichNutzlast,
	corridorSnapshotAus,
	erstelleWertebereicheVergleichSpeicherung
} from '../wertebereicheVergleichSpeicherung.ts';
import {
	createController,
	hydrierterWs,
	korridor,
	makePreset,
	wertebereicheBedienung
} from './wertebereicheVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s3-daten';

/** Ein Vergleich mit Orten, Versandzeiten, Kanälen, Alarm-Schwellen und Anzeige-Einstellungen. */
function reicherVergleich(): ComparePreset {
	return makePreset(PRESET_ID, {
		name: 'Dolomiten Vergleich',
		location_ids: ['loc-a', 'loc-b', 'loc-c', 'loc-d'],
		schedule: 'weekly',
		previous_schedule: 'daily',
		hour_from: 5,
		hour_to: 11,
		forecast_hours: 72,
		empfaenger: ['a@example.com', 'b@example.com'],
		official_alerts_enabled: false,
		official_warnings: { enabled: false },
		radar_alert_enabled: true,
		send_telegram: true,
		send_sms: true,
		send_premium_sms: true,
		alert_cooldown_minutes: 90,
		alert_quiet_from: '21:30',
		alert_quiet_to: '06:15',
		alert_channel_thresholds: { telegram: 'hoch', sms: 'gering', premium_sms: 'hoch', email: 'gering' },
		hourly_enabled: true,
		outlook_enabled: false,
		day_window_start_hour: 7,
		day_window_end_hour: 19,
		display_config: {
			metric_alert_levels: { wind_max_kmh: 'standard', snow_depth_cm: 'sensibel' },
			ideal_ranges: { wind_max_kmh: { min: 0, max: 40 }, snow_depth_cm: { min: 30, max: 200 } },
			active_metrics: ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c'],
			telegram_style: 'kurzform',
			region: 'Dolomiten',
			hourly_metrics: ['temp_max_c', 'wind_max_kmh'],
			outlook_metrics: ['temp_max_c'],
			outlook_metric_formats: { temp_max_c: true },
			alert_channels: { telegram: true, sms: false }
		}
	} as Partial<ComparePreset>);
}

const KORRIDOR_FELDER_DC = new Set(['ideal_ranges', 'active_metrics', 'metric_alert_levels']);

/** Alles außer den Korridor-Feldern muss byte-gleich zum Ausgangsstand sein. */
function assertNurKorridorFelderGeaendert(vorher: ComparePreset, nachher: Record<string, unknown>): void {
	const v = vorher as unknown as Record<string, unknown>;
	for (const key of Object.keys(v)) {
		if (key === 'corridors' || key === 'display_config') continue;
		assert.deepEqual(nachher[key], v[key], `Bestandsfeld „${key}" ging beim Wertebereiche-Speichern verloren/verändert`);
	}
	const vdc = v.display_config as Record<string, unknown>;
	const ndc = (nachher.display_config as Record<string, unknown>) ?? {};
	for (const key of Object.keys(vdc)) {
		if (KORRIDOR_FELDER_DC.has(key)) continue;
		assert.deepEqual(ndc[key], vdc[key], `display_config.${key} ging beim Wertebereiche-Speichern verloren/verändert`);
	}
}

describe('AC-11 (Kern): baueWertebereichNutzlast — Voll-Spread, nur Korridor-Felder neu', () => {
	test('geänderter Korridor → alle Bestandsfelder aus dem Preset bleiben, der Korridor ist neu', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		wertebereicheBedienung(ws).patch('wind_max_kmh', { max: 65 });

		const { url, body } = baueWertebereichNutzlast(preset, corridorSnapshotAus(ws));

		assert.equal(url, `/api/compare/presets/${PRESET_ID}`);
		assertNurKorridorFelderGeaendert(preset, body as unknown as Record<string, unknown>);
		assert.deepEqual(korridor(body, 'wind_max_kmh')?.range, [0, 65], 'der geänderte Korridor muss im Rumpf stehen');
		assert.deepEqual(
			(body.display_config as Record<string, unknown>).ideal_ranges,
			{ wind_max_kmh: { min: 0, max: 65 }, snow_depth_cm: { min: 30, max: 200 } },
			'der markierte Idealbereich folgt dem Korridor'
		);
	});

	test('metric_alert_levels kommt aus dem aktuellen Zustand, nicht aus dem Preset', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		ws.metricAlertLevels = { wind_max_kmh: 'entspannt', snow_depth_cm: 'sensibel' };
		wertebereicheBedienung(ws).patch('wind_max_kmh', { max: 65 });

		const { body } = baueWertebereichNutzlast(preset, corridorSnapshotAus(ws));

		assert.deepEqual((body.display_config as Record<string, unknown>).metric_alert_levels, {
			wind_max_kmh: 'entspannt',
			snow_depth_cm: 'sensibel'
		});
	});
});

describe('AC-11 (Rundlauf): gespeichert und neu geladen — nur der Wertebereich weicht ab', () => {
	let server: FakeTripServer;

	beforeEach(() => {
		clearEtagRegistry();
		server = createFakeTripServer();
		server.install();
	});

	afterEach(() => server.restore());

	test('Korridor ändern → speichern → Server-Stand trägt alle übrigen Einstellungen unverändert', async () => {
		const preset = reicherVergleich();
		let basis = preset;
		const ws = hydrierterWs(basis);
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();
		const speicherung = erstelleWertebereicheVergleichSpeicherung({
			client: api,
			zustand: ws,
			preset: () => basis,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: ctl
		});

		wertebereicheBedienung(ws).patch('snow_depth_cm', { max: 250 });
		speicherung.aenderungMelden();
		await ctl.flush();

		const stand = server.storedBody(PRESET_ID) as Record<string, unknown>;
		assertNurKorridorFelderGeaendert(preset, stand);
		assert.deepEqual(korridor(stand, 'snow_depth_cm')?.range, [30, 250]);
		assert.deepEqual(korridor(stand, 'wind_max_kmh')?.range, [0, 40], 'ein nicht bedienter Korridor bleibt unverändert');
	});
});
