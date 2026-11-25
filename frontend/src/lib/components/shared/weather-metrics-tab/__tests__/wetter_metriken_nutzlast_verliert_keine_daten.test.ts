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

// Issue #3276: der Zustellungs-Speicherer schreibt keinen display_config-Schluessel mehr
// (`channel_active_metrics`, `hourly_metrics`, `outlook_metrics`, `outlook_metric_formats`
// waren Altschluessel; `active_metrics` gehoert seit #2794 F006 dem Reiter Wetter). Jeder
// display_config-Schluessel muss nach dem Speichern byte-gleich zum Bestand sein.
const WETTER_METRIKEN_FELDER_DC = new Set<string>([]);
const WETTER_METRIKEN_FELDER_TOP = new Set([
	'official_alerts_enabled',
	'hourly_enabled',
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
	// #2794 S3a Teil 3 (F006, AC-38): Metrikauswahl, Amtliche Warnungen und Tagesfenster gehoeren
	// dem Reiter Wetter — sie stehen auch dann nicht im Rumpf, wenn sie sich in der Kopie aendern.
	// Issue #3276 (AC-2): vorher „die Kanal-Auswahl ist neu" — `channel_active_metrics` ist
	// Altschluessel und reist nicht mehr mit, der Bestand bleibt ueber den Go-Merge stehen.
	test('Kanal-Auswahl geändert → der Rumpf trägt nur Eigenfelder, keinen Altschluessel (#3276)', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		ws.channelActiveMetricKeys = { email: ['wind_max_kmh'], telegram: null, sms: null };
		ws.hourlyEnabled = false;

		const { url, body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		assert.equal(url, `/api/compare/presets/${PRESET_ID}`);
		assertNurEigenfelderGesendet(body);
		assert.ok(!('display_config' in (body as unknown as Record<string, unknown>)), 'display_config im Zustellungs-PUT');
		assert.equal((body as unknown as Record<string, unknown>).hourly_enabled, false);
	});

	test('Tagesfenster und Metrikauswahl in der Kopie geändert → weder sie noch Wertebereiche/Alarme/Versand stehen im Rumpf', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		wetterMetrikenBedienung(ws).setDayWindow(6, 21);
		wetterMetrikenBedienung(ws).toggleMetric('gust_max_kmh');

		const { body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		assertNurEigenfelderGesendet(body);
		const roh = body as unknown as Record<string, unknown>;
		for (const k of ['day_window_start_hour', 'day_window_end_hour', 'official_alerts_enabled']) {
			assert.ok(!(k in roh), `${k} gehört dem Reiter Wetter`);
		}
		assert.ok(!('active_metrics' in dc(body)), 'active_metrics gehört dem Reiter Wetter');
		assert.equal(dc(body).metric_alert_levels, undefined, 'metric_alert_levels gehört dem Alarme-Reiter');
	});
});

// Issue #3276 (AC-2): die drei Rueckfall-Tests („current.<feld> == null → PUT traegt den Bestand")
// pruefen jetzt das Gegenteil: der Rumpf traegt die Altschluessel gar nicht mehr, weder als
// Bestand noch als null — der Go-Merge laesst den Bestand unberuehrt (siehe Orchestrierung unten).
// Issue #3298: die camelCase-Altfelder des Zustands sind entfallen; geprueft bleibt, dass der
// Rumpf bei einem Bestand MIT Altschluesseln keinen davon traegt (auch kein `outlook_enabled`).
describe('AC-12 (Rueckfall, #3276/#3298): Bestand mit Altfeldern — der PUT traegt keinen Altschluessel', () => {
	test('Stundenverlauf-Schalter geaendert → kein display_config, kein outlook_enabled im PUT', () => {
		const preset = reicherVergleich();
		const ws = hydrierterWs(preset);
		ws.hourlyEnabled = false;

		const { body } = baueWetterMetrikenNutzlast(preset, wetterMetrikenSnapshotAus(ws));

		for (const k of ['hourly_metrics', 'outlook_metrics', 'outlook_metric_formats', 'hourly_metric_formats', 'channel_active_metrics']) {
			assert.ok(!(k in dc(body)), `${k} im Zustellungs-PUT`);
		}
		assert.ok(!('outlook_enabled' in (body as unknown as Record<string, unknown>)), 'outlook_enabled im Zustellungs-PUT');
		assert.equal((body as unknown as Record<string, unknown>).hourly_enabled, false);
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

	test('Zustand ohne Altfelder (#3298) → nach dem echten PUT steht der Preset-Bestand, nicht null', async () => {
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

		// echte Geste unabhaengig von den drei Rueckfall-Feldern, damit
		// ueberhaupt gespeichert wird (AC-4: kein Schreiben ohne Nutzer-Geste)
		ws.hourlyEnabled = false; // #2794 F006: eigenes Feld statt Amtliche Warnungen (Reiter Wetter)
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

	// Issue #3276: die Stundenverlauf-Reihenfolge (`hourly_metrics`) ist Altschluessel; gemessen
	// wird mit dem verbliebenen eigenen Feld `hourly_enabled`. Alle display_config-Schluessel
	// (inkl. der Altfelder im Bestand) muessen danach unveraendert stehen.
	test('Stundenverlauf-Schalter ändern → speichern → Server-Stand trägt alle übrigen Einstellungen unverändert', async () => {
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

		wetterMetrikenBedienung(ws).hourlyEnabledToggle();
		speicherung.aenderungMelden();
		await ctl.flush();

		assert.equal(puts().length, 1);
		const stand = server.stand(PRESET_ID);
		assertNurWetterMetrikenFelderGeaendert(preset, stand);
		assert.equal(stand.hourly_enabled, false);
		assert.deepEqual(dc(stand).hourly_metrics, ['wind_max_kmh', 'temp_max_c'], 'Bestand hourly_metrics veraendert');
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
