// TDD RED — Issue #3276 (Epic #3122, Spec-AC-38 zweiter Teil): der Ortsvergleich schreibt
// beim Anlegen (POST) und Speichern (PUT) keinen der sechs Altschluessel mehr; die alten
// Bedienflaechen Stundenverlauf/Ausblick entfallen im Vergleich.
// Spec: docs/specs/modules/feat_3276_vergleich_altfelder_entfernen.md (AC-1, AC-2, AC-3, AC-6)
//
// Reine Verhaltenstests ohne Mocks: die echten Payload-Bildner werden mit echten
// Eingaben (Anlege-Feldsatz, Preset mit Altfeldern im Bestand) getrieben, geprueft wird der
// Rumpf, der tatsaechlich an den Server ginge.
//
// RED heute:
//   - buildNewComparePresetPayload schreibt hourly_*/outlook_*/channel_active_metrics,
//     sobald der Anlege-Feldsatz Werte traegt (AC-1).
//   - baueWetterMetrikenNutzlast sendet hourly_*/outlook_*/channel_active_metrics im PUT (AC-2).
//   - buildComparePresetSavePayload ueberschreibt Bestands-Altwerte mit Editor-Werten (AC-2).
//   - weatherMetricsTabSections('vergleich', …) enthaelt 'stundenverlauf' und 'ausblick' (AC-3).
//
// Ausfuehren (aus frontend/):
//   npm test -- src/lib/components/compare/feat3276_vergleich_ohne_altfelder.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
	buildComparePresetSavePayload,
	baueVergleichAnlegeRumpf,
	legeVergleichAn,
	buildNewComparePresetPayload,
	compareFeldsatzStandard,
	type CompareEditorEdits,
	type CompareFeldsatz,
	type NewComparePresetFields
} from './compareEditorSave.ts';
import {
	baueWetterMetrikenNutzlast,
	type WetterMetrikenLayoutSnapshot
} from '../shared/weather-metrics-tab/weatherMetricsCompareSave.ts';
import { baueVersandNutzlast } from '../shared/versandVergleichSpeicherung.ts';
import { baueAlarmNutzlast } from '../shared/alarmeVergleichSpeicherung.ts';
import { baueWertebereichNutzlast } from '../shared/wetter-tab/wertebereicheVergleichSpeicherung.ts';
import type { ComparePreset } from '../../types.ts';

const ALTSCHLUESSEL = [
	'channel_layouts',
	'outlook_metrics',
	'outlook_metric_formats',
	'channel_active_metrics',
	'hourly_metrics',
	'hourly_metric_formats'
] as const;

function altschluesselIn(dc: unknown): string[] {
	const o = (dc ?? {}) as Record<string, unknown>;
	return ALTSCHLUESSEL.filter((k) => Object.prototype.hasOwnProperty.call(o, k));
}

// Bestand eines Vergleichs, der noch vor #3237 mit allen Altfeldern gespeichert wurde.
const BESTAND_ALT = {
	channel_layouts: { email: ['temp_max_c'], telegram: ['wind_max_kmh'] },
	outlook_metrics: ['temp_max_c', 'precip_sum_mm'],
	outlook_metric_formats: { temp_max_c: true },
	channel_active_metrics: { sms: [{ metric_id: 'temp', aggregation: 'max' }] },
	hourly_metrics: ['temp_c', 'wind_kmh'],
	hourly_metric_formats: { temp_c: true }
};

function presetMitAltfeldern(): ComparePreset {
	return {
		id: 'cp-3276',
		name: 'Dolomiten-Vergleich',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		profil: 'allgemein',
		hour_from: 7,
		hour_to: 18,
		empfaenger: [],
		hourly_enabled: true,
		outlook_enabled: true,
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: false,
		evening_time: '18:00:00',
		day_window_start_hour: 4,
		day_window_end_hour: 19,
		corridors: [],
		display_config: {
			region: 'Dolomiten',
			active_metrics: [{ metric_id: 'temp', aggregation: 'max' }],
			placements: { rows: [{ metric: 'temp_max_c', places: { email: ['stundenverlauf'] } }] },
			...structuredClone(BESTAND_ALT)
		}
	} as unknown as ComparePreset;
}

// Anlege-Feldsatz, in dem die (alten) Editor-Felder Werte tragen — so wie der Wizard sie
// heute fuellt, wenn jemand Stundenverlauf/Ausblick/Kanal-Auswahl angefasst hat.
function anlegeFelderMitAltwerten(): NewComparePresetFields {
	const f = compareFeldsatzStandard();
	return {
		...f,
		name: 'Neu 3276',
		pickedIds: ['loc-1', 'loc-2'],
		region: 'Dolomiten',
		activeMetricKeys: null,
		channelActiveMetricKeys: { email: ['temp_max_c'], telegram: [], sms: null },
		hourlyMetricKeys: ['temp_c'],
		outlookMetricKeys: ['temp_max_c'],
		outlookMetricFormats: { temp_max_c: true },
		hourlyMetricFormats: { temp_c: true }
	} as unknown as NewComparePresetFields;
}

describe('#3276 AC-1: Anlegen (POST) ohne Altschluessel', () => {
	test('POST-Rumpf traegt keinen der sechs Altschluessel, auch wenn der Feldsatz Werte hat', () => {
		const body = buildNewComparePresetPayload(anlegeFelderMitAltwerten());
		assert.deepEqual(altschluesselIn(body.display_config), []);
	});

	test('POST-Rumpf traegt keinen Altschluessel als Leerwert (weder [] noch {} noch null)', () => {
		const f = {
			...anlegeFelderMitAltwerten(),
			channelActiveMetricKeys: { email: [], telegram: [], sms: [] },
			hourlyMetricKeys: [],
			outlookMetricKeys: [],
			outlookMetricFormats: {},
			hourlyMetricFormats: {}
		} as unknown as NewComparePresetFields;
		assert.deepEqual(altschluesselIn(buildNewComparePresetPayload(f).display_config), []);
	});

	test('POST-Rumpf behaelt die uebrigen Anlage-Felder (Region, Vorlage, Kanaele)', () => {
		const body = buildNewComparePresetPayload(anlegeFelderMitAltwerten());
		const dc = body.display_config as Record<string, unknown>;
		assert.equal(dc.region, 'Dolomiten');
		assert.ok(dc.ampel, 'ampel (Vorlage) fehlt im POST');
		assert.deepEqual(body.location_ids, ['loc-1', 'loc-2']);
		assert.equal(body.send_sms, false);
	});
});

describe('#3276 AC-2: Speichern (PUT) ohne Altschluessel, Bestand bleibt', () => {
	test('Zustellungs-Speicherer sendet keinen Altschluessel, auch nach Aenderung', () => {
		const preset = presetMitAltfeldern();
		// #3298: die camelCase-Altfelder kennt der Snapshot-Typ nicht mehr; Fremdlast per Cast.
		const { body } = baueWetterMetrikenNutzlast(preset, {
			activeMetricKeys: ['temp_max_c'],
			channelActiveMetricKeys: { email: ['wind_max_kmh'], telegram: null, sms: [] },
			officialAlertsEnabled: true,
			dayWindowStartHour: 4,
			dayWindowEndHour: 19,
			hourlyMetricKeys: ['temp_c', 'precip_mm'],
			hourlyEnabled: false,
			outlookMetricKeys: ['temp_max_c'],
			outlookMetricFormats: { temp_max_c: false },
			outlookEnabled: true,
			hourlyMetricFormats: { temp_c: false }
		} as WetterMetrikenLayoutSnapshot);
		assert.deepEqual(altschluesselIn((body as unknown as Record<string, unknown>).display_config), []);
	});

	test('Versand-, Alarm- und Wertebereiche-Speicherer senden keinen Altschluessel (Bestand mit Altfeldern)', () => {
		const preset = presetMitAltfeldern();
		const versand = baueVersandNutzlast(preset, {
			sendTelegram: true,
			sendSms: false,
			sendPremiumSms: false,
			morningEnabled: true,
			morningTime: '06:30',
			eveningEnabled: false,
			eveningTime: '18:00',
			endDate: null
		} as never).body as unknown as Record<string, unknown>;
		const alarm = baueAlarmNutzlast(preset, {
			metricAlertLevels: {},
			channelThresholds: {},
			channels: { email: true, telegram: true, sms: false, premium_sms: false },
			alertMetricChannels: {},
			officialAlertsEnabled: true,
			officialWarningsEnabled: true,
			radarAlertEnabled: false,
			telegramStyle: 'rich'
		} as never).body as unknown as Record<string, unknown>;
		const werte = baueWertebereichNutzlast(preset, {
			corridors: [],
			idealRanges: {},
			activeMetricKeys: ['temp_max_c'],
			metricAlertLevels: {}
		} as never).body as unknown as Record<string, unknown>;
		assert.deepEqual(altschluesselIn(versand.display_config), [], 'Versand');
		assert.deepEqual(altschluesselIn(alarm.display_config), [], 'Alarme');
		assert.deepEqual(altschluesselIn(werte.display_config), [], 'Wertebereiche');
	});

	test('Voll-Rumpf ueberschreibt Bestands-Altwerte nicht mehr mit Editor-Werten (Read-Modify-Write)', () => {
		const preset = presetMitAltfeldern();
		const edits = {
			name: preset.name,
			activityProfile: null,
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Dolomiten',
			idealRanges: {},
			channelActiveMetricKeys: { email: [], telegram: [], sms: [] },
			hourlyMetricKeys: [],
			outlookMetricKeys: [],
			outlookMetricFormats: {},
			hourlyMetricFormats: {}
		} as unknown as CompareEditorEdits;
		const dc = buildComparePresetSavePayload(preset, edits).body.display_config as Record<string, unknown>;
		for (const k of ALTSCHLUESSEL) {
			assert.deepEqual(dc[k], (BESTAND_ALT as Record<string, unknown>)[k], `Bestand ${k} veraendert`);
		}
		assert.deepEqual(
			(dc.placements as { rows: unknown[] }).rows.length,
			1,
			'placements aus dem Bestand muessen erhalten bleiben'
		);
	});
});

// #3297/#3020: der Block „AC-3/AC-6: keine alte Bedienflaeche Stundenverlauf/Ausblick“ pruefte
// weatherMetricsTabSections.ts; die Datei ist samt WeatherMetricsTab geloescht (die Bedienflaeche
// existiert in keinem Kontext mehr, Nachweis trip_pfad_altfeld_loeschnachweis_3297.test.ts).

describe('#3276 F002: Rumpf des Anlege-Editors (CompareNewEditor) ohne Altschluessel', () => {
	// Feldsatz, wie ihn der Anlege-Editor haelt, mit befuellten Alt-Feldern. #3298: die
	// camelCase-Altfelder kennt der Typ nicht mehr; sie werden als Fremdlast untergeschoben.
	function wizMitAltwerten(): CompareFeldsatz {
		return {
			...compareFeldsatzStandard(),
			name: 'Neu 3276 Editor',
			pickedIds: ['loc-1', 'loc-2'],
			region: 'Dolomiten',
			activeMetricKeys: ['temp_max_c'],
			channelActiveMetricKeys: { email: ['temp_max_c'], telegram: ['wind_max_kmh'], sms: [] },
			hourlyMetricKeys: ['temp_c', 'wind_kmh'],
			outlookMetricKeys: ['temp_max_c', 'precip_sum_mm'],
			outlookMetricFormats: { temp_max_c: true },
			hourlyMetricFormats: { temp_c: true }
		} as CompareFeldsatz;
	}
	const AMPEL = { template: 'wandern', overrides: {} };
	const AUSWAHL = [{ metric_id: 'temp', aggregation: 'max' }];

	test('kein Altschluessel top-level oder in display_config; Ampel und Auswahl reisen mit', () => {
		const body = baueVergleichAnlegeRumpf(wizMitAltwerten(), { ampel: AMPEL, auswahl: AUSWAHL });
		assert.deepEqual(altschluesselIn(body), [], 'top-level');
		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(altschluesselIn(dc), [], 'display_config');
		assert.deepEqual(dc.ampel, AMPEL);
		assert.deepEqual(dc.active_metrics, AUSWAHL);
		assert.equal(dc.region, 'Dolomiten');
		assert.deepEqual(body.location_ids, ['loc-1', 'loc-2']);
	});

	test('auch mit leeren Alt-Feldern und ohne Wetter-Stand kein Altschluessel (nicht einmal leer)', () => {
		const wiz = {
			...wizMitAltwerten(),
			channelActiveMetricKeys: { email: [], telegram: [], sms: [] },
			hourlyMetricKeys: [],
			outlookMetricKeys: [],
			outlookMetricFormats: {},
			hourlyMetricFormats: {}
		} as CompareFeldsatz;
		const body = baueVergleichAnlegeRumpf(wiz);
		assert.deepEqual(altschluesselIn(body), [], 'top-level');
		assert.deepEqual(altschluesselIn(body.display_config), [], 'display_config');
	});

	// F-ADV1: der ganze Anlege-Schritt (Rumpf + POST) -- geprueft wird der Koerper, der
	// tatsaechlich an der Netzgrenze ankommt (Aufzeichnungs-Objekt statt Mock-Framework).
	test('legeVergleichAn: genau ein POST an /api/compare/presets, Koerper ohne Altschluessel, id zurueck', async () => {
		const gesendet: { url: string; body: Record<string, unknown> }[] = [];
		const api = {
			async post<T>(url: string, body: unknown): Promise<T> {
				gesendet.push({ url, body: body as Record<string, unknown> });
				return { id: 'x' } as T;
			}
		};
		const created = await legeVergleichAn(api, wizMitAltwerten(), { ampel: AMPEL, auswahl: AUSWAHL });
		assert.deepEqual(created, { id: 'x' });
		assert.equal(gesendet.length, 1, 'genau ein POST');
		assert.equal(gesendet[0].url, '/api/compare/presets');
		const body = gesendet[0].body;
		assert.deepEqual(altschluesselIn(body), [], 'top-level');
		const dc = body.display_config as Record<string, unknown>;
		assert.deepEqual(altschluesselIn(dc), [], 'display_config');
		assert.deepEqual(dc.ampel, AMPEL);
		assert.deepEqual(dc.active_metrics, AUSWAHL);
		assert.deepEqual(body.location_ids, ['loc-1', 'loc-2']);
	});
});
