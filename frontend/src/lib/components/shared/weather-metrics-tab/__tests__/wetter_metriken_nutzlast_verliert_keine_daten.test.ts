// TDD RED — Issue #2276 Scheibe S4 (Epic #2345), AC-12: das Speichern der
// Wetter-Metriken/Layout-Domänen verliert keine anderen Einstellungen des
// Ortsvergleichs (Orte, Versandzeiten, Kanäle, Alarm-Schwellen, Wertebereiche).
// Nur die zehn Wetter-Metriken/Layout-Felder dürfen vom Ausgangsstand
// abweichen.
//
// Spec: docs/specs/modules/rework_2276_s4_wetter_metriken.md — AC-12
// Design-Entscheidung 5 (Voll-Spread über buildComparePresetSavePayload; der
// Go-Merge-Kernel mergt display_config nur auf Ebene 1, ein Teil-PUT wäre ein
// Verlustpfad).
//
// Zielschnittstelle (existiert noch NICHT → RED):
//   shared/weather-metrics-tab/weatherMetricsCompareSave.ts
//     wetterMetrikenSnapshotAus(wiz): WetterMetrikenLayoutSnapshot
//     baueWetterMetrikenNutzlast(preset, current): { url, body }
//
// Ausführen:
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/wetter_metriken_nutzlast_verliert_keine_daten.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';

import { api } from '../../../../api.ts';
import { clearEtagRegistry } from '../../../../etagRegistry.ts';
import { createGoMergeServer, type GoMergeServer } from '../../__tests__/goMergeServerPruefstand.ts';
import type { ComparePreset } from '../../../../types.ts';
import { createPutQueue } from '../../../compare/compareHubPersistenz.ts';
import {
	baueWetterMetrikenNutzlast,
	erstelleWetterMetrikenVergleichSpeicherung,
	wetterMetrikenSnapshotAus
} from '../weatherMetricsCompareSave.ts';
import { createController, dc, hydrierterWs, makePreset, wetterMetrikenBedienung } from './wetterMetrikenVergleichPruefstand.ts';

const PRESET_ID = 'cp-2276-s4-daten';

/** Ein Vergleich mit Orten, Versandzeiten, Kanälen, Alarm-Schwellen und Wertebereichen. */
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
		official_alerts_enabled: true,
		official_warnings: { enabled: true },
		radar_alert_enabled: true,
		send_telegram: true,
		send_sms: true,
		send_premium_sms: true,
		alert_cooldown_minutes: 90,
		alert_quiet_from: '21:30',
		alert_quiet_to: '06:15',
		alert_channel_thresholds: { telegram: 'hoch', sms: 'gering', premium_sms: 'hoch', email: 'gering' },
		corridors: [{ metric: 'wind_max_kmh', range: [0, 40], notify: true, mark: true }],
		display_config: {
			metric_alert_levels: { wind_max_kmh: 'standard' },
			ideal_ranges: { wind_max_kmh: { min: 0, max: 40 } },
			active_metrics: ['wind_max_kmh', 'snow_depth_cm', 'temp_max_c'],
			channel_active_metrics: {},
			telegram_style: 'kurzform',
			region: 'Dolomiten',
			hourly_metrics: ['wind_max_kmh', 'temp_max_c'],
			outlook_metrics: ['temp_max_c'],
			outlook_metric_formats: { temp_max_c: true }
		}
	} as Partial<ComparePreset>);
}

const WETTER_METRIKEN_FELDER_DC = new Set([
	'active_metrics',
	'channel_active_metrics',
	'hourly_metrics',
	'outlook_metrics',
	'outlook_metric_formats'
]);
const WETTER_METRIKEN_FELDER_TOP = new Set([
	'official_alerts_enabled',
	'hourly_enabled',
	'outlook_enabled',
	'day_window_start_hour',
	'day_window_end_hour'
]);

/** Alles außer den Wetter-Metriken/Layout-Feldern muss byte-gleich zum Ausgangsstand sein. */
function assertNurWetterMetrikenFelderGeaendert(vorher: ComparePreset, nachher: Record<string, unknown>): void {
	const v = vorher as unknown as Record<string, unknown>;
	for (const key of Object.keys(v)) {
		if (key === 'display_config' || WETTER_METRIKEN_FELDER_TOP.has(key)) continue;
		assert.deepEqual(nachher[key], v[key], `Bestandsfeld „${key}" ging beim Wetter-Metriken-Speichern verloren/verändert`);
	}
	const vdc = v.display_config as Record<string, unknown>;
	const ndc = (nachher.display_config as Record<string, unknown>) ?? {};
	for (const key of Object.keys(vdc)) {
		if (WETTER_METRIKEN_FELDER_DC.has(key)) continue;
		assert.deepEqual(ndc[key], vdc[key], `display_config.${key} ging beim Wetter-Metriken-Speichern verloren/verändert`);
	}
}

/** Seit #2375: der Rumpf trägt NUR Eigenfelder (Top-Level + display_config-Schlüssel). */
function assertNurEigenfelderGesendet(body: unknown): void {
	const roh = body as Record<string, unknown>;
	for (const key of Object.keys(roh)) {
		assert.ok(
			key === 'display_config' || WETTER_METRIKEN_FELDER_TOP.has(key),
			`Fremdfeld „${key}" im Wetter-Metriken-PUT`
		);
	}
	for (const key of Object.keys((roh.display_config as Record<string, unknown>) ?? {})) {
		assert.ok(WETTER_METRIKEN_FELDER_DC.has(key), `Fremder display_config-Schlüssel „${key}" im Wetter-Metriken-PUT`);
	}
}

describe('AC-12 (Kern, seit #2375 Teilfeld): baueWetterMetrikenNutzlast — nur die eigenen Felder im Rumpf', () => {
	test('Metrik hinzugefügt → der Rumpf trägt nur Eigenfelder, die Auswahl ist neu', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		wetterMetrikenBedienung(ws).toggleMetric('gust_max_kmh');

		const { url, body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		assert.equal(url, `/api/compare/presets/${PRESET_ID}`);
		assertNurEigenfelderGesendet(body);
		assert.ok((dc(body).active_metrics as string[]).includes('gust_max_kmh'));
	});

	test('Tagesfenster geändert → Wertebereiche/Alarme/Versand stehen nicht im Rumpf', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		wetterMetrikenBedienung(ws).setDayWindow(6, 21);

		const { body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		assertNurEigenfelderGesendet(body);
		assert.equal((body as unknown as Record<string, unknown>).day_window_start_hour, 6);
		assert.equal((body as unknown as Record<string, unknown>).day_window_end_hour, 21);
		assert.equal(dc(body).metric_alert_levels, undefined, 'metric_alert_levels gehört dem Alarme-Reiter');
	});
});

describe('AC-12 (Rueckfall): current.<feld> == null faellt auf den Preset-Bestand zurueck, nie auf null im PUT', () => {
	test('hourlyMetricKeys == null im Snapshot → PUT traegt display_config.hourly_metrics aus dem Bestand', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		ws.hourlyMetricKeys = null;
		wetterMetrikenBedienung(ws).setDayWindow(6, 21);

		const { body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		assert.deepEqual(
			dc(body).hourly_metrics,
			(preset.display_config as Record<string, unknown>).hourly_metrics,
			'hourly_metrics darf beim Rueckfall NICHT auf null geschrieben werden'
		);
	});

	test('outlookMetricKeys == null im Snapshot → PUT traegt display_config.outlook_metrics aus dem Bestand', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		ws.outlookMetricKeys = null;
		wetterMetrikenBedienung(ws).setDayWindow(6, 21);

		const { body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		assert.deepEqual(
			dc(body).outlook_metrics,
			(preset.display_config as Record<string, unknown>).outlook_metrics,
			'outlook_metrics darf beim Rueckfall NICHT auf null geschrieben werden'
		);
	});

	test('outlookMetricFormats == null im Snapshot → PUT traegt display_config.outlook_metric_formats aus dem Bestand', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		ws.outlookMetricFormats = null;
		wetterMetrikenBedienung(ws).setDayWindow(6, 21);

		const { body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		assert.deepEqual(
			dc(body).outlook_metric_formats,
			(preset.display_config as Record<string, unknown>).outlook_metric_formats,
			'outlook_metric_formats darf beim Rueckfall NICHT auf null geschrieben werden'
		);
	});
});

describe('AC-12 (Rueckfall via Orchestrierung): erstelleWetterMetrikenVergleichSpeicherung schreibt den echten Bestand, nicht null', () => {
	// Seit #2375: Ersatz-Server, der wie der Go-Handler zusammenfuehrt (der
	// fakeTripServer ersetzt den gespeicherten Rumpf komplett).
	let server: GoMergeServer;

	beforeEach(() => {
		clearEtagRegistry();
		server = createGoMergeServer({ [PRESET_ID]: reicherVergleich() as unknown as Record<string, unknown> });
		server.install();
	});

	afterEach(() => server.restore());

	test('alle drei Rueckfall-Felder == null im wiz → echter PUT-Body traegt den Preset-Bestand statt null', async () => {
		const preset = reicherVergleich();
		let basis = preset;
		const ws = hydrierterWs(basis);
		ws.hourlyMetricKeys = null;
		ws.outlookMetricKeys = null;
		ws.outlookMetricFormats = null;
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();
		const speicherung = erstelleWetterMetrikenVergleichSpeicherung({
			client: api,
			zustand: ws,
			preset: () => basis,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: ctl
		});

		// echte Geste unabhaengig von den drei Rueckfall-Feldern, damit
		// ueberhaupt gespeichert wird (AC-4: kein Schreiben ohne Nutzer-Geste)
		wetterMetrikenBedienung(ws).toggleOfficialAlerts();
		speicherung.aenderungMelden();
		await ctl.flush();

		const stand = server.stand(PRESET_ID);
		const vorherDc = preset.display_config as Record<string, unknown>;
		assert.deepEqual(dc(stand).hourly_metrics, vorherDc.hourly_metrics, 'hourly_metrics darf im echten PUT nicht auf null fallen');
		assert.deepEqual(dc(stand).outlook_metrics, vorherDc.outlook_metrics, 'outlook_metrics darf im echten PUT nicht auf null fallen');
		assert.deepEqual(
			dc(stand).outlook_metric_formats,
			vorherDc.outlook_metric_formats,
			'outlook_metric_formats darf im echten PUT nicht auf null fallen'
		);
	});
});

describe('AC-12 (Rundlauf): gespeichert und neu geladen — nur die Wetter-Metriken/Layout-Felder weichen ab', () => {
	let server: GoMergeServer;

	beforeEach(() => {
		clearEtagRegistry();
		server = createGoMergeServer({ [PRESET_ID]: reicherVergleich() as unknown as Record<string, unknown> });
		server.install();
	});

	afterEach(() => server.restore());

	const puts = () => server.putRuempfe();

	test('Stundenverlauf-Reihenfolge ändern → speichern → Server-Stand trägt alle übrigen Einstellungen unverändert', async () => {
		const preset = reicherVergleich();
		let basis = preset;
		const ws = hydrierterWs(basis);
		const ctl = createController(PRESET_ID);
		const queue = createPutQueue();
		const speicherung = erstelleWetterMetrikenVergleichSpeicherung({
			client: api,
			zustand: ws,
			preset: () => basis,
			enqueueHubWrite: (fn) => queue.enqueue(fn),
			onCompareUpdate: (p: ComparePreset) => {
				basis = p;
			},
			saveController: ctl
		});

		wetterMetrikenBedienung(ws).hourlyDragEnd(['temp_max_c', 'wind_max_kmh']);
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		const stand = server.stand(PRESET_ID);
		assertNurWetterMetrikenFelderGeaendert(preset, stand);
		assert.deepEqual(dc(stand).hourly_metrics, ['temp_max_c', 'wind_max_kmh']);
		assert.equal(stand.name, 'Dolomiten Vergleich', 'der Name darf nicht verloren gehen');
		assert.deepEqual(stand.location_ids, ['loc-a', 'loc-b', 'loc-c', 'loc-d']);
		assert.equal(stand.send_premium_sms, true);
		assert.deepEqual(
			stand.alert_channel_thresholds,
			{ telegram: 'hoch', sms: 'gering', premium_sms: 'hoch', email: 'gering' }
		);
		assert.deepEqual(dc(stand).ideal_ranges, { wind_max_kmh: { min: 0, max: 40 } });
	});
});
